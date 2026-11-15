"""Contrato offline para ``ScraperCFM.raspar``.

CFM tem ``_find_n_pags`` baseado em "X registros encontrados" + parsing
de "Mostrando página X de Y" para descobrir total de páginas.

Os samples ``page_01``, ``page_02`` e ``single_page`` foram construídos à
mão, com essa estrutura (e ``div#resultsNormas > article``) e texto de
enchimento; ``no_results.html`` é uma busca real. O script ``python -m
tests.fixtures.capture.cfm`` grava os quatro cenários reais, mas não rodou
contra o portal para os três primeiros: em 21/10/2026 a conexão com
``portal.cfm.org.br`` não abriu.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import ScraperError, ValidationError
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
                {"texto": "doenças raras", "ano": "2023", "uf": "DF", "pagina": "1"}, strict_match=False,
            )],
        )

        # ano chega como texto e o schema o converte em int; a query volta a texto.
        scraper.raspar(pesquisa="doenças raras", ano="2023", uf="DF")

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Busca real sem resultados: sem 'X registros encontrados', só o aviso "Não há resultados"."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("cfm", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="xxxxxx_inexistente")
        assert df.empty
        assert list(df.columns) == COLUNAS


    @responses.activate
    def test_rotulo_desconhecido_avisa_e_mantem_as_linhas(self, scraper, mocker):
        """Rótulo de card fora do mapa de colunas não some em silêncio: avisa e mantém o resto."""
        mocker.patch("time.sleep")
        corpo = load_sample_bytes("cfm", "raspar/single_page.html").replace(
            "<strong>Situação</strong>".encode(), "<strong>Órgão</strong>".encode()
        )
        assert "Órgão".encode() in corpo
        responses.add(
            responses.GET, API_URL, body=corpo, status=200, content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({"texto": "medicamentos órfãos"}, strict_match=False)],
        )

        with pytest.warns(UserWarning, match=r"rótulos que o raspe não conhece.*\['Órgão'\]") as avisos:
            df = scraper.raspar(pesquisa="medicamentos órfãos")

        # Um aviso por página, não um por card, apontando para quem chamou raspar().
        assert len(avisos) == 1
        assert avisos[0].filename == __file__
        assert len(df) == 3
        assert list(df.columns) == COLUNAS
        assert (df["situacao"] == "").all()


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
            scraper.raspar(pesquisa="doenças raras")


class TestFindNPags:
    def test_um_registro_no_singular(self, scraper, mocker):
        """Com um resultado só, o portal escreve "1 registro encontrado"."""
        r0 = mocker.Mock(content="<p>1 registro encontrado</p>".encode())
        assert scraper._find_n_pags(r0) == 1


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
