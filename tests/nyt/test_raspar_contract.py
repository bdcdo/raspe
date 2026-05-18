"""Contrato offline para ``ScraperNYT.raspar``.

Os samples em ``tests/nyt/samples/raspar/`` são JSON sintético replicando
a estrutura da Article Search API v2 do NYT
(``response.docs[]`` + ``response.meta.hits`` ou ``response.metadata.hits``).
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import APIError, APIKeyError
from raspe.scrapers.nyt import ScraperNYT
from tests._helpers import load_sample_bytes

API_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
COLUNAS_OBRIGATORIAS = {
    "titulo", "url", "data_publicacao", "secao", "desk",
    "tipo", "resumo", "autor", "palavras", "imagem_url",
}


@pytest.fixture
def scraper():
    return ScraperNYT(api_key="test-key-12345")


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """15 hits → 2 páginas (10 por página)."""
        mocker.patch("time.sleep")
        # initial + page 1 (mesma URL — page=0) + page 2 (page=1)
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/page_01.json"),
            status=200, content_type="application/json",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/page_01.json"),
            status=200, content_type="application/json",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/page_02.json"),
            status=200, content_type="application/json",
        )

        df = scraper.raspar(texto="politics")
        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 2 docs, page_02 tem 1 doc → 3 total
        assert len(df) == 3

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 hits → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/single_page.json"),
            status=200, content_type="application/json",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/single_page.json"),
            status=200, content_type="application/json",
        )

        df = scraper.raspar(texto="climate")
        assert len(df) == 3
        # imagem_url do primeiro doc deve ter o prefixo do NYT
        assert "nytimes.com" in df["imagem_url"].iloc[0]

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """0 hits → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/no_results.json"),
            status=200, content_type="application/json",
        )

        df = scraper.raspar(texto="xxxxxxxx_inexistente")
        assert df.empty

    @responses.activate
    def test_api_key_invalida_levanta_apikeyerror(self, scraper, mocker):
        """Status 401 → APIKeyError."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/unauthorized.json"),
            status=401, content_type="application/json",
        )
        with pytest.raises(APIKeyError, match="API key inválida"):
            scraper.raspar(texto="test")

    @responses.activate
    def test_status_400_levanta_apierror(self, scraper, mocker):
        """Status >= 400 (não 401) → APIError."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body='{"error": "bad request"}', status=400,
            content_type="application/json",
        )
        with pytest.raises(APIError) as exc_info:
            scraper.raspar(texto="test")
        assert exc_info.value.status_code == 400

    @responses.activate
    def test_query_inclui_api_key_e_filtros(self, scraper, mocker):
        """A API key, sort e begin_date/end_date são enviados na query."""
        mocker.patch("time.sleep")
        # Usa o api_key real do scraper para os matchers
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/no_results.json"),
            status=200, content_type="application/json",
            match=[matchers.query_param_matcher({
                "api-key": "test-key-12345",
                "q": "election",
                "sort": "newest",
                "begin_date": "20240101",
                "end_date": "20241231",
            })],
        )

        scraper.raspar(texto="election", data_inicio="2024-01-01", data_fim="2024-12-31")


class TestConstrutor:
    def test_sem_api_key_levanta_apikeyerror(self, mocker):
        mocker.patch.dict("os.environ", {}, clear=True)
        with pytest.raises(APIKeyError, match="API KEY DO NEW YORK TIMES"):
            ScraperNYT()

    def test_api_key_via_env(self, mocker):
        mocker.patch.dict("os.environ", {"NYT_API_KEY": "env-key"})
        scraper = ScraperNYT()
        assert scraper._api_key == "env-key"

    def test_api_key_explicita_prevalece_sobre_env(self, mocker):
        mocker.patch.dict("os.environ", {"NYT_API_KEY": "env-key"})
        scraper = ScraperNYT(api_key="explicita")
        assert scraper._api_key == "explicita"

    def test_propriedades(self, scraper):
        assert scraper.api_method == 'GET'
        assert scraper.type == 'JSON'
        assert scraper.query_page_name == 'page'
        # page 1 → page=0 (increment=-1)
        assert scraper.query_page_increment == -1
        assert scraper.sleep_time == 12  # 5 req/min
