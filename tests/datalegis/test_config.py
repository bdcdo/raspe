"""Testes de configuração e parsing síncrono para ScraperDatalegis e subclasses.

O fluxo principal (``raspar``) usa Playwright e não pode ser exercitado
offline sem mockar a API async inteira. Aqui testamos apenas:

* O construtor (atributos, propriedades, ``url_base``).
* O parser síncrono ``_parse_page`` / ``_extrair_atos_do_html``, com
  samples HTML representativos.
* Que ``ANS`` e ``ANVISA`` herdam configuração corretamente.
"""

import pytest

from raspe.playwright_scraper import PaginationStrategy
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.datalegis import ScraperDatalegis
from tests._helpers import load_sample_bytes


@pytest.fixture
def scraper_ans():
    return ScraperANS()


@pytest.fixture
def scraper_anvisa():
    return ScraperANVISA()


class TestConstrutor:
    def test_pagination_strategy_select_dropdown(self, scraper_ans):
        """Datalegis usa combobox de paginação."""
        assert scraper_ans.pagination_strategy == PaginationStrategy.SELECT_DROPDOWN

    def test_max_pages_limite(self, scraper_ans):
        assert scraper_ans._max_pages == 100

    def test_eh_playwright_scraper(self, scraper_ans):
        from raspe.playwright_scraper import PlaywrightScraper
        assert isinstance(scraper_ans, PlaywrightScraper)
        assert isinstance(scraper_ans, ScraperDatalegis)

    def test_type_html(self, scraper_ans):
        assert scraper_ans.type == 'HTML'


class TestUrlBase:
    def test_ans_url_base(self, scraper_ans):
        url = scraper_ans.url_base
        assert "anslegis.datalegis.net" in url
        assert "cod_modulo=583" in url
        assert "cod_menu=8431" in url

    def test_anvisa_url_base(self, scraper_anvisa):
        url = scraper_anvisa.url_base
        assert "anvisalegis.datalegis.net" in url
        assert "cod_modulo=134" in url
        assert "cod_menu=1696" in url


class TestExtrairAtosDoHtml:
    def test_typical_extrai_atos_e_situacao(self, scraper_ans):
        html = load_sample_bytes("datalegis", "parse/typical.html").decode("utf-8")
        atos = scraper_ans._extrair_atos_do_html(html)

        # 3 atos válidos (o quarto não tem âncora)
        assert len(atos) == 3
        # Primeiro tem situação "Em vigor"
        assert atos[0]["situacao"] == "Em vigor"
        assert "500/2024" in atos[0]["titulo"]
        # URL absoluta com prefixo do domínio
        assert atos[0]["url"].startswith("https://anslegis.datalegis.net")
        # Segundo tem situação "Revogado"
        assert atos[1]["situacao"] == "Revogado"
        # Terceiro tem URL absoluta original (já começa com http)
        assert atos[2]["url"].startswith("https://outro.dominio")
        assert atos[2]["situacao"] is None
        # Descrição extraída do <p>
        assert "doenças raras" in atos[0]["descricao"]

    def test_no_results_retorna_lista_vazia(self, scraper_ans):
        html = load_sample_bytes("datalegis", "parse/no_results.html").decode("utf-8")
        atos = scraper_ans._extrair_atos_do_html(html)
        assert atos == []


class TestParsePage:
    def test_parse_page_le_arquivo_e_retorna_dataframe(self, scraper_ans, tmp_path):
        sample = tmp_path / "page.html"
        sample.write_bytes(load_sample_bytes("datalegis", "parse/typical.html"))

        df = scraper_ans._parse_page(str(sample))
        assert len(df) == 3
        assert set(df.columns) == {"url", "titulo", "descricao", "situacao"}

    def test_parse_page_arquivo_inexistente_retorna_df_vazio(self, scraper_ans):
        df = scraper_ans._parse_page("/tmp/inexistente-zzzz.html")
        assert df.empty
        assert set(df.columns) == {"url", "titulo", "descricao", "situacao"}


class TestSubclasses:
    def test_ans_tem_dominio_e_codigos(self, scraper_ans):
        assert scraper_ans._dominio == "anslegis.datalegis.net"
        assert scraper_ans._cod_modulo == "583"
        assert scraper_ans._cod_menu == "8431"
        assert scraper_ans.nome_buscador == "ANS"

    def test_anvisa_tem_dominio_e_codigos(self, scraper_anvisa):
        assert scraper_anvisa._dominio == "anvisalegis.datalegis.net"
        assert scraper_anvisa._cod_modulo == "134"
        assert scraper_anvisa._cod_menu == "1696"
        assert scraper_anvisa.nome_buscador == "ANVISA"

    def test_sgl_tipos_definido(self, scraper_ans, scraper_anvisa):
        """Listas de tipos de atos são strings não vazias."""
        assert isinstance(scraper_ans._sgl_tipos, str)
        assert "RES" in scraper_ans._sgl_tipos
        assert isinstance(scraper_anvisa._sgl_tipos, str)
        assert "RDC" in scraper_anvisa._sgl_tipos
