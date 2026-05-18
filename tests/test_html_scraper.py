"""Testes unitários para o mixin HTMLScraper."""

from bs4 import BeautifulSoup

from raspe.html_scraper import HTMLScraper


class _DummyHTMLClient(HTMLScraper):
    """Subclasse mínima para instanciar o mixin em testes."""


class TestHTMLScraper:
    def test_soup_it_aceita_string(self):
        client = _DummyHTMLClient()
        soup = client.soup_it("<html><body><p>oi</p></body></html>")
        assert isinstance(soup, BeautifulSoup)
        assert soup.find("p").text == "oi"

    def test_soup_it_aceita_bytes(self):
        client = _DummyHTMLClient()
        soup = client.soup_it(b"<html><body><p>bytes</p></body></html>")
        assert isinstance(soup, BeautifulSoup)
        assert soup.find("p").text == "bytes"

    def test_soup_it_html_invalido_nao_levanta(self):
        """BeautifulSoup é permissivo; entrada inválida vira soup com o texto cru.

        Assertiva por substring para tolerar diferenças entre parsers
        (``html.parser`` vs. ``lxml`` vs. ``html5lib`` quanto a whitespace).
        """
        client = _DummyHTMLClient()
        soup = client.soup_it("texto sem tags")
        assert isinstance(soup, BeautifulSoup)
        assert "texto sem tags" in soup.get_text()
