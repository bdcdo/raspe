"""Contrato offline para ``ScraperFolha.raspar``.

Os samples em ``tests/folha/samples/raspar/`` são respostas reais da busca
pública da Folha, capturadas em 21/10/2026 com
``python -m tests.fixtures.capture.folha``. O único ajuste é o do
pre-commit, que tira o espaço no fim das linhas. A contagem fica em
``div.c-search__result`` ("N Resultados para ...") e cada notícia em
``ol.u-list-unstyled.c-search > li``, com ``a[href]``, ``h2``, ``p``, ``time``.

- ``page_01.html`` e ``page_02.html``: busca "Elevidys", ``sr=1`` e
  ``sr=26``. O site diz "28 Resultados"; a página 1 tem 25 notícias e a
  página 2, 3.
- ``single_page.html``: busca "natjus", "6 Resultados".
- ``no_results.html``: busca "termoextremamenteimprovavelxyz", "0 Resultados".
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import ScraperError, ValidationError
from raspe.schemas.folha import OutputFolha
from raspe.scrapers.folha import ScraperFolha
from tests._helpers import load_sample_bytes

API_URL = "https://search.folha.uol.com.br/search"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputFolha, na ordem de colunas().
COLUNAS = OutputFolha.colunas()


@pytest.fixture
def scraper():
    return ScraperFolha()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """28 resultados → 2 páginas (25 por página)."""
        mocker.patch("time.sleep")

        # Initial + page 1 + page 2 = 3 requests
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="Elevidys")

        assert not df.empty
        assert list(df.columns) == COLUNAS
        # page_01 tem 25 notícias e page_02 tem 3: as 28 que o site anuncia.
        assert len(df) == 28
        assert (df["termo_busca"] == "Elevidys").all()

    @responses.activate(registry=registries.OrderedRegistry, assert_all_requests_are_fired=True)
    @pytest.mark.parametrize(
        ("paginas", "esperado"),
        [
            (range(1, 2), [("1", "page_01.html")]),
            (range(2, 3), [("26", "page_02.html")]),
            (range(1, 3), [("1", "page_01.html"), ("26", "page_02.html")]),
        ],
    )
    def test_parametro_sr_avanca_de_25_em_25(self, scraper, mocker, paginas, esperado):
        """A página 1 pede ``sr=1`` e a página 2 pede ``sr=26``.

        ``sr`` é a posição do primeiro resultado da página (25 por página).
        A requisição inicial também vai com ``sr=1``, que vem de
        ``_set_query_base``. O ``query_param_matcher`` é estrito, e a ordem
        do registry prende cada valor à sua página.
        """
        mocker.patch("time.sleep")
        query_base = {"q": "Elevidys", "site": "todos", "periodo": "todos"}
        # Inicial: page_01 diz 28 resultados, ou seja, 2 páginas.
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({**query_base, "sr": "1"})],
        )
        for sr, sample in esperado:
            responses.add(
                responses.GET, API_URL,
                body=load_sample_bytes("folha", f"raspar/{sample}"),
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher({**query_base, "sr": sr})],
            )

        df = scraper.raspar(pesquisa="Elevidys", paginas=paginas)

        assert len(responses.calls) == 1 + len(esperado)
        noticias_por_sample = {"page_01.html": 25, "page_02.html": 3}
        assert len(df) == sum(noticias_por_sample[sample] for _, sample in esperado)

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """6 resultados → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="natjus")
        assert len(df) == 6
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Busca real sem resultados: ``0 Resultados para ...`` em ``c-search__result`` → 0 páginas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_pagina_que_nao_e_de_resultados_levanta_erro(self, scraper, mocker):
        """Sem a contagem e sem o aviso de busca vazia (manutenção, anti-robô), não vira 0 resultados."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("presidencia", "raspar/manutencao.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        with pytest.raises(ScraperError, match="indispon"):
            scraper.raspar(pesquisa="educação")

    @responses.activate
    def test_sem_contagem_levanta_erro(self, scraper, mocker):
        """Sem ``div.c-search__result`` e sem o número, a busca falha alto.

        Parte do sample page_01, que tem 25 notícias, e tira a classe do
        container da contagem e o número de "28 Resultados para". Sem o
        container, ``_find_n_pags`` procura "N resultado" em qualquer texto
        da página; o número só aparecia ali, e a página não traz o aviso de
        busca vazia. O contrato fixa que a falta da contagem levanta
        ``ScraperError``, mesmo com as notícias na página, em vez de
        devolver um DataFrame vazio.
        """
        mocker.patch("time.sleep")
        html = load_sample_bytes("folha", "raspar/page_01.html").decode("utf-8")
        for trecho, troca in [('c-search__result">', '">'), ("28 Resultados para", "Resultados para")]:
            assert html.count(trecho) == 1, "o sample page_01.html mudou; ajuste o trecho trocado"
            html = html.replace(trecho, troca)
        # As notícias continuam na página; só a contagem sumiu.
        assert 'class="u-list-unstyled c-search"' in html

        responses.add(
            responses.GET, API_URL,
            body=html.encode("utf-8"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        with pytest.raises(ScraperError, match="contagem de resultados"):
            scraper.raspar(pesquisa="Elevidys")

        # Só a requisição inicial: nenhuma página é pedida.
        assert len(responses.calls) == 1


class TestTetoDeResultados:
    def test_contagem_no_limite_de_10000_avisa(self, scraper, mocker):
        """A busca da Folha para em 10.000 resultados, e a contagem também."""
        r0 = mocker.Mock(content=b'<div class="c-search__result">10000 Resultados para x</div>')
        with pytest.warns(UserWarning, match="10,000 resultados, mas o limite é 10,000"):
            assert scraper._find_n_pags(r0) == 400

    def test_abaixo_do_limite_nao_avisa(self, scraper, mocker):
        r0 = mocker.Mock(content=b'<div class="c-search__result">386 Resultados para x</div>')
        assert scraper._find_n_pags(r0) == 16


class TestValidacao:
    def test_site_invalido_levanta_validation_error(self, scraper):
        with pytest.raises(ValidationError, match="site"):
            scraper.raspar(pesquisa="x", site="invalido")

    def test_sites_validos_vem_do_schema(self):
        assert ScraperFolha.SITES_VALIDOS == ("todos", "online", "jornal")

    def test_data_com_erro_de_digitacao_levanta_com_sugestao(self, scraper):
        """Antes do schema, 'data_incio' era ignorado e a busca rodava sem período."""
        with pytest.raises(ValidationError, match="você quis dizer 'data_inicio'"):
            scraper.raspar(pesquisa="x", data_incio="2024-01-01")

    def test_pesquisa_obrigatoria(self, scraper):
        with pytest.raises(ValidationError, match="'pesquisa': parâmetro obrigatório ausente"):
            scraper.raspar(site="online")

    @responses.activate
    @pytest.mark.parametrize("site", ["todos", "online", "jornal"])
    def test_sites_validos_aceitos(self, scraper, site, mocker):
        """'todos', 'online' e 'jornal' são aceitos sem erro de validação."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="x", site=site)
        assert df.empty
        assert list(df.columns) == COLUNAS


class TestFormatacaoData:
    def test_formatar_data_br(self, scraper):
        assert scraper._formatar_data_br("2024-01-15") == "15/01/2024"

    def test_formatar_data_br_vazia(self, scraper):
        assert scraper._formatar_data_br("") == ""

    @responses.activate
    def test_query_com_datas_envia_periodo_personalizado(self, scraper, mocker):
        """Quando data_inicio e data_fim são fornecidas, query usa periodo=personalizado."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        scraper.raspar(
            pesquisa="x",
            data_inicio="2024-01-01",
            data_fim="2024-12-31",
        )

        # Inspeciona a request enviada
        call = responses.calls[0]
        assert "periodo=personalizado" in call.request.url
        assert "sd=01%2F01%2F2024" in call.request.url
        assert "ed=31%2F12%2F2024" in call.request.url
