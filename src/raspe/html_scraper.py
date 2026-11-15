import re
from typing import TYPE_CHECKING

from raspe.exceptions import ScraperError

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

# Aviso que as fontes exibem quando a busca não tem resultados, como
# "Nenhum resultado encontrado" (Senado) ou "Nenhum registro encontrado" (CAPES).
# Exige o "encontrad" para não casar com textos como "Nenhuma área selecionada",
# que a CAPES exibe também nas páginas com resultados.
_AVISO_SEM_RESULTADOS = re.compile(r'nenhuma?\s+\w+\s+encontrad', re.IGNORECASE)


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

    def _confirmar_busca_vazia(self, soup: "BeautifulSoup") -> int:
        """Confirma que uma página sem contagem de resultados é mesmo uma busca vazia.

        Os ``_find_n_pags`` chamam este método quando não acham o marcador de
        contagem. Se a página traz o aviso de busca sem resultados, devolve 0.
        Senão, a resposta não é uma página de resultados (manutenção,
        verificação anti-robô, layout novo), e devolver 0 esconderia o problema.

        Args:
            soup: Página da resposta inicial, já analisada.

        Returns:
            int: Sempre 0.

        Raises:
            ScraperError: Se a página não traz o aviso de busca sem resultados.
        """
        if _AVISO_SEM_RESULTADOS.search(soup.get_text(" ")):
            return 0
        titulo = soup.title.get_text(strip=True) if soup.title else ""
        raise ScraperError(
            f"{type(self).__name__}: a resposta não traz a contagem de resultados nem o aviso "
            f"de busca vazia (título da página: '{titulo}'). O site pode estar fora do ar, "
            "em manutenção ou exigindo verificação anti-robô."
        )
