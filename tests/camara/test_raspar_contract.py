"""Contrato offline para ``ScraperCamaraDeputados.raspar``.

O construtor de ``ScraperCamaraDeputados`` invoca ``_prep_scrape``, que
faz GET na página inicial da Câmara para estabelecer sessão. Mockamos
esse método antes de instanciar — o foco do contrato é o fluxo de busca,
não a inicialização da sessão.
"""

import pytest
import responses

from raspe.scrapers.camara import ScraperCamaraDeputados
from tests._helpers import load_sample_bytes

API_URL = "https://www.camara.leg.br/legislacao/busca"
COLUNAS_OBRIGATORIAS = {"link", "titulo", "descricao", "ementa"}


@pytest.fixture(autouse=True)
def _mock_prep_scrape(mocker):
    """Evita rede no __init__ de ScraperCamaraDeputados."""
    mocker.patch.object(ScraperCamaraDeputados, "_prep_scrape", return_value={})


@pytest.fixture
def scraper():
    return ScraperCamaraDeputados()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """15 resultados → 2 páginas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/page_02.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="educação")
        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        assert len(df) == 3  # 2 + 1

    @responses.activate
    def test_single_page(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="tributário")
        assert len(df) == 3
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("camara", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="xxxxxx_inexistente")
        assert df.empty


class TestConfiguracao:
    def test_propriedades(self, scraper):
        assert scraper.api_method == 'GET'
        assert scraper.type == 'HTML'
        assert scraper.query_page_name == 'pagina'

    def test_query_inclui_filtros_opcionais(self, scraper, mocker):
        mocker.patch("time.sleep")
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET, API_URL,
                body=load_sample_bytes("camara", "raspar/no_results.html"),
                status=200, content_type="text/html; charset=utf-8",
            )
            scraper.raspar(pesquisa="x", ano=2024, tipo_materia="PL")
            url = rsps.calls[0].request.url
            assert "ano=2024" in url
            assert "tipo=PL" in url
            assert "geral=x" in url
