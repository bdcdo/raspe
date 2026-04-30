from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bs4 import BeautifulSoup


class HTMLScraper:
    """Classe mixin para scrapers que precisam analisar conteúdo HTML."""

    def soup_it(self, content: str | bytes) -> "BeautifulSoup":
        """Analisa conteúdo HTML usando BeautifulSoup.

        Args:
            content: Conteúdo HTML para análise, como string ou bytes.

        Returns:
            BeautifulSoup: Documento HTML analisado.

        Note:
            Requer o pacote 'beautifulsoup4' instalado.
        """
        from bs4 import BeautifulSoup
        return BeautifulSoup(content, 'html.parser')
