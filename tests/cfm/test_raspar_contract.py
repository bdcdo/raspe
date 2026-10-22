"""Contrato offline para ``ScraperCFM.raspar``.

CFM tem ``_find_n_pags`` baseado em "X registros encontrados" + parsing
de "Mostrando página X de Y" para descobrir total de páginas.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import ValidationError
from raspe.schemas.cfm import OutputCFM
from raspe.scrapers.cfm import ScraperCFM
from tests._helpers import load_sample_bytes

API_URL = "https://portal.cfm.org.br/buscar-normas-cfm-e-crm/"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputCFM, na ordem de colunas().
COLUNAS = OutputCFM.colunas()


@pytest.fixture
def scraper():
    return ScraperCFM()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
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

        df = scraper.raspar(pesquisa="doenças raras")
        assert not df.empty
        assert list(df.columns) == COLUNAS
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

        df = scraper.raspar(pesquisa="medicamentos órfãos")
        assert len(df) == 3
        assert list(df.columns) == COLUNAS
        # Tipos válidos do CFM
        assert set(df["tipo"]) <= {"Resolução", "Parecer", "Emenda", "Norma", "Decisão"}
        # Antes do schema, a busca do CFM não ganhava termo_busca: o parâmetro
        # se chamava 'texto', fora da lista que BaseScraper.raspar reconhecia.
        assert (df["termo_busca"] == "medicamentos órfãos").all()

    @responses.activate
    def test_pesquisa_vai_no_campo_texto_do_portal(self, scraper, mocker):
        """O nome canônico ``pesquisa`` sai na query como ``texto``, o nome do portal."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher(
                {"texto": "doenças raras", "ano": "2023", "uf": "DF"}, strict_match=False,
            )],
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        # ano chega como texto e o schema o converte em int; a query volta a texto.
        scraper.raspar(pesquisa="doenças raras", ano="2023", uf="DF")

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Sem 'X registros encontrados' no HTML → 0 páginas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="xxxxxx_inexistente")
        assert df.empty
        assert list(df.columns) == COLUNAS


class TestAliasDeprecado:
    @responses.activate
    def test_texto_avisa_e_vira_pesquisa(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({"texto": "doenças raras"}, strict_match=False)],
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        with pytest.warns(DeprecationWarning, match="'texto'.*'pesquisa'") as avisos:
            df = scraper.raspar(texto="doenças raras")

        # O aviso aponta para quem chamou raspar(); atribuído a um arquivo do
        # raspe, o Python não o mostraria fora dos testes.
        assert avisos[0].filename == __file__
        assert list(df.columns) == COLUNAS
        assert (df["termo_busca"] == "doenças raras").all()

    def test_texto_e_pesquisa_juntos_levantam(self, scraper):
        with pytest.raises(ValidationError, match="ao mesmo tempo"):
            scraper.raspar(texto="a", pesquisa="b")


class TestConfiguracao:
    def test_propriedades(self, scraper):
        assert scraper.api_method == 'GET'
        assert scraper.type == 'HTML'
        assert scraper.query_page_name == 'pagina'

    def test_query_inclui_tipos_de_norma(self, scraper):
        """A query base inclui todos os 5 tipos de norma do CFM."""
        query = scraper._set_query_base(pesquisa="x")
        assert query["tipo[0]"] == "R"  # Resolução
        assert query["tipo[1]"] == "P"  # Parecer
        assert query["tipo[2]"] == "E"  # Emenda
        assert query["tipo[3]"] == "N"  # Norma
        assert query["tipo[4]"] == "D"  # Decisão

    def test_query_inclui_filtros_opcionais(self, scraper):
        query = scraper._set_query_base(
            pesquisa="x", uf="SP", revogada="N", numero="100", ano="2024",
        )
        assert query["uf"] == "SP"
        assert query["revogada"] == "N"
        assert query["numero"] == "100"
        assert query["ano"] == "2024"

    def test_query_converte_ano_inteiro_em_texto(self, scraper):
        """O schema entrega ano como int; sem ano, o portal recebe o campo vazio."""
        assert scraper._set_query_base(pesquisa="x", ano=2023)["ano"] == "2023"
        assert scraper._set_query_base(pesquisa="x", ano=None)["ano"] == ""

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
