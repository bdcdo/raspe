"""Contrato offline para ``ScraperNYT.raspar``.

Os samples em ``tests/nyt/samples/raspar/`` são JSON sintético replicando
a estrutura da Article Search API v2 do NYT
(``response.docs[]`` + ``response.meta.hits`` ou ``response.metadata.hits``).
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import APIError, APIKeyError, ValidationError
from raspe.schemas.nyt import OutputNYT
from raspe.scrapers.nyt import ScraperNYT
from tests._helpers import load_sample_bytes

API_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputNYT, na ordem de colunas().
COLUNAS = OutputNYT.colunas()


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

        df = scraper.raspar(pesquisa="politics")
        assert not df.empty
        assert list(df.columns) == COLUNAS
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

        df = scraper.raspar(pesquisa="climate")
        assert len(df) == 3
        assert list(df.columns) == COLUNAS
        assert (df["termo_busca"] == "climate").all()
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

        df = scraper.raspar(pesquisa="xxxxxxxx_inexistente")
        assert df.empty
        assert list(df.columns) == COLUNAS

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
            scraper.raspar(pesquisa="test")

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
            scraper.raspar(pesquisa="test")
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

        scraper.raspar(pesquisa="election", data_inicio="2024-01-01", data_fim="2024-12-31")


class TestValidacao:
    @responses.activate
    def test_texto_avisa_e_vira_pesquisa(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/no_results.json"),
            status=200, content_type="application/json",
            match=[matchers.query_param_matcher({"q": "election"}, strict_match=False)],
        )

        with pytest.warns(DeprecationWarning, match="'texto'.*'pesquisa'") as avisos:
            df = scraper.raspar(texto="election")

        assert avisos[0].filename == __file__
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_ano_preenche_o_periodo(self, scraper, mocker):
        """ano='2024' passa pelo schema como int e vira begin_date/end_date."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/no_results.json"),
            status=200, content_type="application/json",
            match=[matchers.query_param_matcher(
                {"begin_date": "20240101", "end_date": "20241231"}, strict_match=False,
            )],
        )
        scraper.raspar(pesquisa="election", ano="2024")

    def test_sort_fora_da_lista_levanta(self, scraper):
        with pytest.raises(ValidationError, match="'sort'"):
            scraper.raspar(pesquisa="x", sort="aleatorio")


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
