"""Testes de configuração e parsing síncrono para ScraperSaudeLegis.

O fluxo ``raspar`` real usa Playwright (formulário com JSF/Primefaces);
testamos aqui apenas configuração e ``_parse_page`` com sample HTML
representativo da estrutura observada.
"""

import pytest

from raspe.playwright_scraper import PaginationStrategy, PlaywrightScraper
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from tests._helpers import load_sample_bytes


@pytest.fixture
def scraper():
    return ScraperSaudeLegis()


class TestConstrutor:
    def test_url_base(self, scraper):
        assert "saudelegis.saude.gov.br" in scraper.url_base
        assert "listPublic.xhtml" in scraper.url_base

    def test_pagination_numbered_links(self, scraper):
        assert scraper.pagination_strategy == PaginationStrategy.NUMBERED_LINKS

    def test_max_pages(self, scraper):
        assert scraper._max_pages == 50

    def test_eh_playwright_scraper(self, scraper):
        assert isinstance(scraper, PlaywrightScraper)

    def test_nome_buscador(self, scraper):
        assert scraper.nome_buscador == "SAUDELEGIS"


class TestParsePage:
    def test_typical_extrai_3_registros(self, scraper, tmp_path):
        sample = tmp_path / "page.html"
        sample.write_bytes(load_sample_bytes("saudelegis", "parse/typical.html"))

        df = scraper._parse_page(str(sample))

        # 3 linhas válidas; a 4ª tem menos de 8 td e é pulada
        assert len(df) == 3
        assert set(df.columns) == {
            "tipo_norma", "numero", "data_pub", "origem", "ementa", "link_url",
        }
        # Primeira linha
        assert df.iloc[0]["tipo_norma"] == "PORTARIA"
        assert df.iloc[0]["numero"] == "123/2024"
        assert df.iloc[0]["data_pub"] == "15/01/2024"
        assert df.iloc[0]["origem"] == "MS/GM"
        assert "doenças raras" in df.iloc[0]["ementa"]
        assert df.iloc[0]["link_url"] == "/doc/portaria-123-2024.pdf"
        # Terceira linha não tem link → link_url vazio
        assert df.iloc[2]["link_url"] == ""

    def test_sem_tabela_retorna_df_vazio(self, scraper, tmp_path):
        sample = tmp_path / "page.html"
        sample.write_bytes(load_sample_bytes("saudelegis", "parse/no_results.html"))

        df = scraper._parse_page(str(sample))
        assert df.empty
        assert set(df.columns) == {
            "tipo_norma", "numero", "data_pub", "origem", "ementa", "link_url",
        }

    def test_arquivo_inexistente_retorna_df_vazio(self, scraper):
        df = scraper._parse_page("/tmp/inexistente-zzzzz.html")
        assert df.empty
