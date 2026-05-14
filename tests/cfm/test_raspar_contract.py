"""Contrato offline para ``ScraperCFM.raspar``.

CFM tem ``_find_n_pags`` baseado em "X registros encontrados" + parsing
de "Mostrando página X de Y" para descobrir total de páginas.
"""

import pytest
import responses

from raspe.scrapers.cfm import ScraperCFM
from tests._helpers import load_sample_bytes

API_URL = "https://portal.cfm.org.br/buscar-normas-cfm-e-crm/"
COLUNAS_OBRIGATORIAS = {"Tipo", "UF", "Nº/Ano", "Situação", "Ementa", "Link"}


@pytest.fixture
def scraper():
    return ScraperCFM()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """20 registros, "Mostrando página 1 de 2" → 2 páginas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/page_02.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(texto="doenças raras")
        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        assert len(df) == 3  # 2 + 1

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 registros, "Mostrando página 1 de 1" → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(texto="medicamentos órfãos")
        assert len(df) == 3
        # Tipos válidos do CFM
        assert set(df["Tipo"]) <= {"Resolução", "Parecer", "Emenda", "Norma", "Decisão"}

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Sem 'X registros encontrados' no HTML → 0 páginas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(texto="xxxxxx_inexistente")
        assert df.empty


class TestConfiguracao:
    def test_propriedades(self, scraper):
        assert scraper.api_method == 'GET'
        assert scraper.type == 'HTML'
        assert scraper.query_page_name == 'pagina'

    def test_query_inclui_tipos_de_norma(self, scraper):
        """A query base inclui todos os 5 tipos de norma do CFM."""
        query = scraper._set_query_base(texto="x")
        assert query["tipo[0]"] == "R"  # Resolução
        assert query["tipo[1]"] == "P"  # Parecer
        assert query["tipo[2]"] == "E"  # Emenda
        assert query["tipo[3]"] == "N"  # Norma
        assert query["tipo[4]"] == "D"  # Decisão

    def test_query_inclui_filtros_opcionais(self, scraper):
        query = scraper._set_query_base(
            texto="x", uf="SP", revogada="N", numero="100", ano="2024",
        )
        assert query["uf"] == "SP"
        assert query["revogada"] == "N"
        assert query["numero"] == "100"
        assert query["ano"] == "2024"

    def test_parse_article_retorna_none_sem_tipo(self, scraper):
        """Articles sem campo 'Tipo' são descartados."""
        from bs4 import BeautifulSoup
        html = """
        <article>
          <div class="card-header"><ul>
            <li><strong>UF</strong><p>SP</p></li>
          </ul></div>
          <div class="card-body"><span>Ementa</span></div>
        </article>
        """
        article = BeautifulSoup(html, 'html.parser').find('article')
        assert scraper._parse_article(article) is None
