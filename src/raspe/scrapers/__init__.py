"""Raspadores concretos do pacote raspe.

Reexporta todas as classes de raspador para permitir importação direta:

    from raspe.scrapers import ScraperCFM, ScraperANS

Os raspadores baseados em Playwright (``ScraperSaudeLegis``, ``ScraperANS``,
``ScraperANVISA``) podem ser importados sem o extra ``browser`` instalado: o
Playwright só é carregado quando o navegador é efetivamente aberto.
"""

from .ans import ScraperANS
from .anvisa import ScraperANVISA
from .camara import ScraperCamaraDeputados
from .capes import ScraperCapes
from .cfm import ScraperCFM
from .datalegis import ScraperDatalegis
from .folha import ScraperFolha
from .ipea import IpeaScraper, ScraperIpea
from .nyt import ScraperNYT
from .presidencia import ScraperPresidencia
from .saudelegis import ScraperSaudeLegis
from .senado import ScraperSenadoFederal

__all__ = [
    # Raspadores HTTP
    "ScraperCamaraDeputados",
    "ScraperCapes",
    "ScraperCFM",
    "ScraperFolha",
    "ScraperIpea",
    "ScraperNYT",
    "ScraperPresidencia",
    "ScraperSenadoFederal",
    # Raspadores Playwright
    "ScraperANS",
    "ScraperANVISA",
    "ScraperDatalegis",
    "ScraperSaudeLegis",
    # Alias de retrocompatibilidade
    "IpeaScraper",
]
