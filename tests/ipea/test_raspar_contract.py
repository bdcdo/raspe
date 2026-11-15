"""Contrato offline para ``IpeaScraper.raspar``.

Os samples em ``tests/ipea/samples/raspar/`` são respostas reais da busca
de publicações do portal IPEA, capturadas em 21/10/2026 com
``python -m tests.fixtures.capture.ipea``. Há dois ajustes: o script
esvazia os ``<select>`` do formulário de busca, que o scraper não lê e que
levavam cada página a mais de 2 MB, e o pre-commit tira o espaço no fim
das linhas.

- ``page_01.html`` e ``page_02.html``: busca "renda básica", ``pagina=1``
  e ``pagina=2``. O ``h4`` diz "Resultado de 1 a 10 de <strong>13</strong>";
  a página 1 tem 10 publicações e a página 2, 3.
- ``single_page.html``: busca "telemedicina", 1 publicação.
- ``no_results.html``: busca "termoextremamenteimprovavelxyz", "Resultado
  de 0 a 0 de <strong>0</strong>".

O ``div.autores`` vem vazio no HTML do site, por isso a coluna ``autores``
sai vazia nos samples.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import ScraperError
from raspe.schemas.ipea import OutputIpea
from raspe.scrapers.ipea import IpeaScraper
from tests._helpers import load_sample_bytes

API_URL = "https://www.ipea.gov.br/portal/coluna-5/central-de-conteudo/busca-publicacoes"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputIpea, na ordem de colunas().
COLUNAS = OutputIpea.colunas()


@pytest.fixture
def scraper():
    return IpeaScraper()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """13 resultados → 2 páginas: 1 request inicial + 2 de página."""
        mocker.patch("time.sleep")

        # Inicial (pagina=1), página 1 (pagina=1) e página 2 (pagina=2).
        for pagina, sample in [("1", "page_01.html"), ("1", "page_01.html"), ("2", "page_02.html")]:
            responses.add(
                responses.GET, API_URL,
                body=load_sample_bytes("ipea", f"raspar/{sample}"),
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher(
                    {"palavra_chave": "renda básica", "pagina": pagina}, strict_match=False,
                )],
            )

        df = scraper.raspar(pesquisa="renda básica")

        assert not df.empty
        assert list(df.columns) == COLUNAS
        # page_01 tem 10 publicações e page_02 tem 3: as 13 que o site anuncia.
        assert len(df) == 13
        # Links têm prefixo ipea.gov.br
        assert df["link"].iloc[0].startswith("https://www.ipea.gov.br")
        assert "termo_busca" in df.columns
        assert (df["termo_busca"] == "renda básica").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """1 resultado → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="telemedicina")
        assert len(df) == 1
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Busca real sem resultados: ``Resultado de 0 a 0 de <strong>0</strong>`` → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        assert list(df.columns) == COLUNAS
        # Só a requisição inicial: com 0 páginas, nenhuma página é pedida.
        assert len(responses.calls) == 1

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
    def test_sem_div_col_clearfix_levanta_erro(self, scraper, mocker):
        """Sem ``div.col.clearfix``, a busca falha alto e nenhuma página é baixada.

        Parte do sample single_page, que tem 1 publicação, e tira só a
        classe do container da contagem. ``_find_n_pags`` não tem outro
        lugar onde procurar o número, e a página não traz o aviso de busca
        vazia; o contrato fixa que a falta da contagem levanta
        ``ScraperError`` em vez de devolver um DataFrame vazio.
        """
        mocker.patch("time.sleep")
        trecho = '<div class="col clearfix">'
        original = load_sample_bytes("ipea", "raspar/single_page.html").decode("utf-8")
        assert trecho in original, "o sample single_page.html mudou; ajuste o trecho trocado"
        sem_container = original.replace(trecho, '<div class="col">')
        # As publicações continuam na página; só a contagem ficou sem container.
        assert 'class="publi-conteudo"' in sem_container

        responses.add(
            responses.GET, API_URL,
            body=sem_container.encode("utf-8"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        with pytest.raises(ScraperError, match="contagem de resultados"):
            scraper.raspar(pesquisa="telemedicina")

        # Só a requisição inicial: nenhuma página é pedida.
        assert len(responses.calls) == 1

    @responses.activate
    def test_query_params_obrigatorios(self, scraper, mocker):
        """A query base contém os parâmetros esperados pela API IPEA."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({
                "palavra_chave": "telemedicina",
                "tipo": "",
                "assunto": "",
                "autor": "",
                "timeperiods": "all",
                "data-inicial": "",
                "data-final": "",
                "pagina": "1",
            })],
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper.raspar(pesquisa="telemedicina")


class TestParsePage:
    def test_assuntos_sem_rotulo_quebras_nem_repeticao(self, scraper, tmp_path):
        """O ``div.assuntos`` traz "Temas:", quebras de linha e cada tema duas vezes.

        ``assuntos`` fica com cada tema uma vez, na ordem em que aparece,
        separados por vírgula.
        """
        caminho = tmp_path / "single_page.html"
        caminho.write_bytes(load_sample_bytes("ipea", "raspar/single_page.html"))
        df = scraper._parse_page(str(caminho))
        assert df["assuntos"].tolist() == [
            "Ciência. Pesquisa. Metodologia. Análise Estatística, Economia da Saúde, Saúde"
        ]


class TestDownloadPathDescontinuado:
    def test_download_path_emite_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="download_path") as avisos:
            IpeaScraper(download_path="/tmp/qualquer")
        assert avisos[0].filename == __file__

    def test_aviso_pela_fabrica_aponta_para_o_codigo_do_usuario(self):
        """Atribuído a ``raspe/__init__.py``, o filtro padrão do Python esconderia o aviso."""
        import raspe

        with pytest.warns(DeprecationWarning, match="download_path") as avisos:
            raspe.ipea(download_path="/tmp/qualquer")
        assert avisos[0].filename == __file__

    def test_sem_download_path_nao_avisa(self):
        """O ``filterwarnings = error`` da suíte transformaria qualquer aviso em falha."""
        IpeaScraper()
