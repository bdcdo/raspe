"""Contrato offline para ``ScraperSenadoFederal.raspar``.

Os samples em ``tests/senado/samples/raspar/`` foram construídos à mão,
com a estrutura que o parser lê (``a[data-click-type]`` com a contagem e
``div.sf-busca-resultados-item``) e texto de enchimento. Não há script de
captura para eles: a busca HTML sai de cena com a reescrita do scraper
sobre a API oficial do Senado (#29).
"""

import pytest
import responses
from responses import registries

from raspe.scrapers.senado import ScraperSenadoFederal
from tests._helpers import load_sample_bytes

API_URL = "https://www6g.senado.leg.br/busca"
COLUNAS_OBRIGATORIAS = {"titulo", "link_norma", "link_detalhes", "descricao", "trecho_descricao"}


@pytest.fixture
def scraper():
    return ScraperSenadoFederal()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/page_02.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="tributário")
        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        assert len(df) == 3  # 2 + 1

    @responses.activate
    def test_single_page(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="lei")
        assert len(df) == 3
        # O terceiro item tem só 1 link no h3 → link_detalhes = 'NA'
        assert "NA" in df["link_detalhes"].values

    @responses.activate
    def test_descricao_nos_dois_layouts_do_item(self, scraper, mocker):
        """``descricao`` sai de ``p[0]``, ou de ``p[1]`` quando ``p[0]`` é "Legislação".

        O sample single_page traz os dois layouts que ``_parse_page`` trata:
        a Lei e o Decreto no layout original (descrição, tipo, trecho) e a
        Portaria no layout em que o primeiro ``<p>`` é o rótulo
        "Legislação". Nos dois, ``trecho_descricao`` é o terceiro ``<p>``.
        """
        mocker.patch("time.sleep")
        body = load_sample_bytes("senado", "raspar/single_page.html")
        assert "<p>Legislação</p>".encode() in body, "o sample perdeu o layout com rótulo 'Legislação'"
        for _ in range(2):
            responses.add(
                responses.GET, API_URL,
                body=body,
                status=200, content_type="text/html; charset=utf-8",
            )

        df = scraper.raspar(pesquisa="lei").set_index("titulo")

        lei = df.loc["Lei nº 14.999/2024"]
        assert lei["descricao"] == "Altera o código tributário nacional."
        assert lei["trecho_descricao"] == "Estabelece regras de tributação para empresas de tecnologia."

        portaria = df.loc["Portaria nº 12/2024"]
        assert portaria["descricao"] == "Cria comissão técnica."
        assert portaria["trecho_descricao"] == "Designa servidores para análise de propostas."

        # O rótulo nunca vaza para a coluna.
        assert "Legislação" not in df["descricao"].values

    @responses.activate
    def test_no_results(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="xxxxxx_inexistente")
        assert df.empty

    @responses.activate
    def test_query_inclui_filtros_opcionais(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        scraper.raspar(pesquisa="x", ano=2024, tipo_materia="Lei")
        # Verifica que ano e tipo-materia foram incluídos na query
        call_url = responses.calls[0].request.url
        assert "ano=2024" in call_url
        assert "tipo-materia=Lei" in call_url
