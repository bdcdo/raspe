"""Testes unitários para o mixin HTMLScraper."""

import pytest
from bs4 import BeautifulSoup

from raspe.exceptions import ScraperError
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


class TestConfirmarBuscaVazia:
    """Distingue a busca sem resultados de uma página que não é de resultados."""

    def test_aviso_de_busca_vazia_devolve_zero(self):
        client = _DummyHTMLClient()
        for aviso in ("Nenhum resultado encontrado", "Nenhum registro encontrado",
                      "Nenhuma legislação encontrada", "Nenhum resultado foi encontrado",
                      "Não há resultados para esses parâmetros de busca."):
            soup = client.soup_it(f"<html><body><h2>&nbsp;{aviso}</h2></body></html>")
            assert client._confirmar_busca_vazia(soup) == 0

    def test_pagina_sem_aviso_levanta_erro_com_titulo(self):
        client = _DummyHTMLClient()
        soup = client.soup_it(
            "<html><head><title>SEI indisponível temporariamente</title></head>"
            "<body><h2>Sistema indisponível temporariamente!</h2></body></html>"
        )
        with pytest.raises(ScraperError, match="SEI indisponível temporariamente"):
            client._confirmar_busca_vazia(soup)

    def test_nenhuma_area_selecionada_nao_conta_como_busca_vazia(self):
        """A CAPES mostra "Nenhuma área selecionada" também nas páginas com resultados."""
        client = _DummyHTMLClient()
        soup = client.soup_it("<html><body><p>Nenhuma área selecionada</p></body></html>")
        with pytest.raises(ScraperError):
            client._confirmar_busca_vazia(soup)
