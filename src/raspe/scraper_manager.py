"""Factory que resolve um raspador a partir do nome da fonte.

Permite escolher a fonte dinamicamente, a partir de uma string:

    from raspe.scraper_manager import scraper

    df = scraper("CFM").raspar(texto="doença rara")

É uma alternativa às factories de `raspe` (`raspe.cfm()`, `raspe.ans()`, ...),
útil quando o nome da fonte vem de configuração ou entrada do usuário.
"""

from typing import Type

from .abstract_scraper import AbstractScraper
from .scrapers.ans import ScraperANS
from .scrapers.anvisa import ScraperANVISA
from .scrapers.camara import ScraperCamaraDeputados
from .scrapers.capes import ScraperCapes
from .scrapers.cfm import ScraperCFM
from .scrapers.folha import ScraperFolha
from .scrapers.ipea import ScraperIpea
from .scrapers.nyt import ScraperNYT
from .scrapers.presidencia import ScraperPresidencia
from .scrapers.saudelegis import ScraperSaudeLegis
from .scrapers.senado import ScraperSenadoFederal

# Mapeia o nome da fonte (em maiúsculas) para a classe do raspador.
# Deve cobrir todas as factories expostas em `raspe.__all__`.
_MAPPING: dict[str, Type[AbstractScraper]] = {
    # Raspadores HTTP
    "PRESIDENCIA": ScraperPresidencia,
    "IPEA": ScraperIpea,
    "SENADO": ScraperSenadoFederal,
    "CAMARA": ScraperCamaraDeputados,
    "CAPES": ScraperCapes,
    "CFM": ScraperCFM,
    "FOLHA": ScraperFolha,
    "NYT": ScraperNYT,
    # Raspadores Playwright (requerem `pip install raspe[browser]` para rodar)
    "SAUDELEGIS": ScraperSaudeLegis,
    "ANS": ScraperANS,
    "ANVISA": ScraperANVISA,
}


def scraper(nome_buscador: str, **kwargs) -> AbstractScraper:
    """Retorna o raspador correspondente à fonte solicitada.

    Args:
        nome_buscador: Nome da fonte, sem diferenciar maiúsculas de minúsculas
            (ex.: "CFM", "cfm", "Folha").
        **kwargs: Repassados ao construtor do raspador (ex.: `api_key` para o
            NYT, `headless` para os raspadores com navegador).

    Returns:
        AbstractScraper: Instância do raspador correspondente.

    Raises:
        ValueError: Se a fonte não for suportada.

    Examples:
        >>> scraper("CFM").raspar(texto="doença rara")  # doctest: +SKIP
        >>> scraper("ans", headless=False)  # doctest: +SKIP
    """

    nome = nome_buscador.upper()

    try:
        klas = _MAPPING[nome]
    except KeyError as exc:
        suportados = ", ".join(sorted(_MAPPING))
        raise ValueError(
            f"Buscador '{nome}' ainda não é suportado. Disponíveis: {suportados}."
        ) from exc

    return klas(**kwargs)
