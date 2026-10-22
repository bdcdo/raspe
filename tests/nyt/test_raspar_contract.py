"""Contrato offline para ``ScraperNYT.raspar``.

Os samples em ``tests/nyt/samples/raspar/`` são JSON sintético replicando
a estrutura da Article Search API v2 do NYT
(``response.docs[]`` + ``response.meta.hits`` ou ``response.metadata.hits``).
O script ``python -m tests.fixtures.capture.nyt`` grava os cenários reais,
mas exige ``NYT_API_KEY`` e ainda não rodou.
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

    @responses.activate(registry=registries.OrderedRegistry, assert_all_requests_are_fired=True)
    @pytest.mark.parametrize(
        ("paginas", "esperado"),
        [
            (range(1, 2), [("0", "page_01.json")]),
            (range(2, 3), [("1", "page_02.json")]),
            (range(1, 3), [("0", "page_01.json"), ("1", "page_02.json")]),
        ],
    )
    def test_parametro_page_comeca_em_zero(self, scraper, mocker, paginas, esperado):
        """A página 1 do raspe vira ``page=0`` na API, e a página 2 vira ``page=1``.

        A requisição inicial, que só lê ``meta.hits``, vai sem ``page``. O
        ``query_param_matcher`` é estrito: um ``page`` a mais ou a menos em
        qualquer requisição a faz não casar, e a ordem do registry prende
        cada valor à sua página.
        """
        mocker.patch("time.sleep")
        query_base = {"api-key": "test-key-12345", "q": "politics", "sort": "newest"}
        # Inicial: page_01 diz 15 hits, ou seja, 2 páginas.
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/page_01.json"),
            status=200, content_type="application/json",
            match=[matchers.query_param_matcher(query_base)],
        )
        for page, sample in esperado:
            responses.add(
                responses.GET, API_URL,
                body=load_sample_bytes("nyt", f"raspar/{sample}"),
                status=200, content_type="application/json",
                match=[matchers.query_param_matcher({**query_base, "page": page})],
            )

        df = scraper.raspar(texto="politics", paginas=paginas)

        assert len(responses.calls) == 1 + len(esperado)
        # page_01 tem 2 docs, page_02 tem 1
        docs_por_sample = {"page_01.json": 2, "page_02.json": 1}
        assert len(df) == sum(docs_por_sample[sample] for _, sample in esperado)

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
    @pytest.mark.parametrize("body", [
        '{"status": "OK", "response": {"docs": []}}',
        '{"status": "OK", "response": {"meta": {"hits": null}}}',
        "[]",
        "<html><title>Service Unavailable</title></html>",
    ])
    def test_resposta_sem_contagem_levanta_apierror(self, scraper, mocker, body):
        """Sem ``meta.hits`` (ou sem JSON), a resposta não vira 0 resultados."""
        mocker.patch("time.sleep")
        responses.add(responses.GET, API_URL, body=body, status=200)
        with pytest.raises(APIError, match="NYT"):
            scraper.raspar(pesquisa="climate")

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

    @responses.activate
    def test_ano_preenche_so_a_data_que_falta(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("nyt", "raspar/no_results.json"),
            status=200, content_type="application/json",
            match=[matchers.query_param_matcher(
                {"begin_date": "20240101", "end_date": "20240630"}, strict_match=False,
            )],
        )
        scraper.raspar(pesquisa="election", ano=2024, data_fim="2024-06-30")

    @responses.activate
    @pytest.mark.parametrize(
        ("datas", "mensagem"),
        [
            pytest.param(
                {"data_fim": "2023-06-01"},
                r"'ano' \(2024-01-01\) não pode ser posterior a 'data_fim' \(2023-06-01\)",
                id="data_fim_antes_do_ano",
            ),
            pytest.param(
                {"data_inicio": "2025-01-01"},
                r"'data_inicio' \(2025-01-01\) não pode ser posterior a 'ano' \(2024-12-31\)",
                id="data_inicio_depois_do_ano",
            ),
        ],
    )
    def test_ano_que_inverte_o_periodo_levanta(self, scraper, datas, mensagem):
        """A ordem é conferida depois do preenchimento; ``responses`` sem rota prova que nada sai."""
        with pytest.raises(ValidationError, match=mensagem):
            scraper.raspar(pesquisa="election", ano=2024, **datas)

    @responses.activate
    @pytest.mark.parametrize("ano", [24, 0])
    def test_ano_sem_quatro_digitos_levanta_antes_da_api(self, scraper, ano):
        """``ano=24`` dava erro de formato de data, e ``ano=0`` desligava o filtro em silêncio."""
        with pytest.raises(ValidationError, match="'ano' precisa ter quatro dígitos"):
            scraper.raspar(pesquisa="election", ano=ano)

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
