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

from raspe.exceptions import ValidationError
from raspe.scrapers.folha import ScraperFolha
from tests._helpers import load_sample_bytes

API_URL = "https://search.folha.uol.com.br/search"
COLUNAS_OBRIGATORIAS = {"link", "titulo", "resumo", "data"}


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
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
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
        # page_01 tem 25 notícias, page_02 tem 3
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
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """``0 Resultados para ...`` em ``c-search__result`` → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty


class TestValidacao:
    def test_site_invalido_levanta_validation_error(self, scraper):
        with pytest.raises(ValidationError, match="site"):
            scraper.raspar(pesquisa="x", site="invalido")

    @responses.activate
    @pytest.mark.parametrize("site", ["todos", "online", "jornal"])
    def test_sites_validos_aceitos(self, site, mocker):
        """'todos', 'online' e 'jornal' são aceitos sem erro de validação."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        # Não levanta — site válido. Instancia fresh para evitar
        # colisão de timestamp em _create_download_dir.
        df = ScraperFolha().raspar(pesquisa="x", site=site)
        assert df.empty


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
