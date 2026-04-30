from typing import Type

from .base_scraper import BaseScraper
from .scrapers.camara import ScraperCamaraDeputados
from .scrapers.ipea import IpeaScraper
from .scrapers.presidencia import ScraperPresidencia
from .scrapers.senado import ScraperSenadoFederal


def scraper(nome_buscador: str, **kwargs) -> BaseScraper:
    """Retorna o raspador correspondente ao tribunal solicitado."""

    nome = nome_buscador.upper()
    mapping: dict[str, Type[BaseScraper]] = {
        "PRESIDENCIA": ScraperPresidencia,
        "IPEA": IpeaScraper,
        "SENADO": ScraperSenadoFederal,
        "CAMARA": ScraperCamaraDeputados
    }

    try:
        klas = mapping[nome]
    except KeyError as exc:
        raise ValueError(f"Buscador '{nome}' ainda não é suportado.") from exc

    return klas(**kwargs)
