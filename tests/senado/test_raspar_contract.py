"""Contrato offline para ``ScraperSenadoFederal.raspar``.

``no_results.html`` e ``anti_robo.html`` são reais (2026-11-14). A busca sem
resultados não traz o link da coleção com a contagem, só o aviso "Nenhum
resultado encontrado" (capturada com navegador, porque o ``requests`` cai na
verificação anti-robô). ``anti_robo.html`` é essa verificação, servida com
HTTP 200; o IP do cliente foi trocado por um IP de documentação.
"""

import pytest
import requests
import responses
from responses import registries

from raspe.exceptions import ScraperError
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
    def test_verificacao_anti_robo_levanta_erro(self, scraper, mocker):
        """A verificação anti-robô (HTTP 200) não pode virar 0 resultados."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/anti_robo.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        with pytest.raises(ScraperError, match="Verificação de segurança"):
            scraper.raspar(pesquisa="meio ambiente")

    def test_contagem_com_separador_de_milhar(self, scraper):
        """O site mostra a contagem como "8.950" (markup real de 2026-11-14)."""
        r0 = requests.Response()
        r0.status_code = 200
        r0._content = (
            '<a href="/busca/?q=meio+ambiente" data-click-type="dynnav.colecao.Legislação Federal">'
            '<span>Legislação</span>&nbsp;<span class="badge">8.950</span></a>'
        ).encode("utf-8")
        assert scraper._find_n_pags(r0) == 895

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
