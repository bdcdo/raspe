"""Contrato offline para ``IpeaScraper.raspar``.

Os samples em ``tests/ipea/samples/raspar/`` foram construídos manualmente
replicando a estrutura HTML observada em respostas reais do portal IPEA
(``div.lista-publicacoes`` → ``div.row`` → ``div.publi-conteudo``).
Para regenerar a partir do site real, ver
``tests/fixtures/capture/ipea.py``.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.scrapers.ipea import IpeaScraper
from tests._helpers import load_sample_bytes

API_URL = "https://www.ipea.gov.br/portal/coluna-5/central-de-conteudo/busca-publicacoes"
COLUNAS_OBRIGATORIAS = {"titulo", "link", "autores", "data", "assuntos"}


@pytest.fixture
def scraper():
    return IpeaScraper()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """15 resultados → 2 páginas: 1 request inicial + 2 de página."""
        mocker.patch("time.sleep")

        # 1 request inicial + 2 requests de página = 3 GETs no mesmo endpoint
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="economia")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 3 publicações, page_02 tem 2 → total 5
        assert len(df) == 5
        # Links têm prefixo ipea.gov.br
        assert df["link"].iloc[0].startswith("https://www.ipea.gov.br")
        assert "termo_busca" in df.columns
        assert (df["termo_busca"] == "economia").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 resultados → 1 página."""
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

        df = scraper.raspar(pesquisa="pobreza")
        assert len(df) == 3
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """0 resultados → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termo_inexistente_xyzabc")
        assert df.empty

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
                "palavra_chave": "economia",
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

        scraper.raspar(pesquisa="economia")
