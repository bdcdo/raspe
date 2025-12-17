"""
RasPe - Raspadores para Pesquisas Acadêmicas

Biblioteca Python para coleta automatizada de dados de fontes brasileiras.
Fornece acesso simplificado a dados legislativos, jurídicos e acadêmicos.

Exemplo de uso:
    import raspe

    # Criar raspador da Presidência
    dados = raspe.presidencia(pesquisa="meio ambiente")

    # Criar raspador da Câmara
    dados = raspe.camara(pesquisa="educação")
"""

from importlib.metadata import version
from .scrapers.camara import ScraperCamaraDeputados
from .scrapers.senado import ScraperSenadoFederal
from .scrapers.presidencia import ScraperPresidencia
from .scrapers.comunicaCNJ import comunicaCNJ_Scraper
from .scrapers.ipea import IpeaScraper
from .scrapers.cfm import ScraperCFM
from .scrapers.nyt import ScraperNYT
from .utils import expand, remove_duplicates, extract, check

__version__ = version("raspe")

def presidencia(**kwargs):
    """
    Cria um raspador para dados da Presidência da República.

    Returns:
        ScraperPresidencia: Instância configurada do raspador.
    """
    return ScraperPresidencia(**kwargs)

def cnj(**kwargs):
    """
    Cria um raspador para comunicados do CNJ (Conselho Nacional de Justiça).

    Returns:
        comunicaCNJ_Scraper: Instância configurada do raspador.
    """
    return comunicaCNJ_Scraper(**kwargs)

def ipea(**kwargs):
    """
    Cria um raspador para dados do IPEA (Instituto de Pesquisa Econômica Aplicada).

    Returns:
        IpeaScraper: Instância configurada do raspador.
    """
    return IpeaScraper(**kwargs)

def senado(**kwargs):
    """
    Cria um raspador para dados do Senado Federal.

    Returns:
        ScraperSenadoFederal: Instância configurada do raspador.
    """
    return ScraperSenadoFederal(**kwargs)

def camara(**kwargs):
    """
    Cria um raspador para dados da Câmara dos Deputados.

    Returns:
        ScraperCamaraDeputados: Instância configurada do raspador.
    """
    return ScraperCamaraDeputados(**kwargs)

def cfm(**kwargs):
    """
    Cria um raspador para normas do CFM (Conselho Federal de Medicina).

    Returns:
        ScraperCFM: Instância configurada do raspador.
    """
    return ScraperCFM(**kwargs)

def nyt(api_key: str, **kwargs):
    """
    Cria um raspador para o New York Times (requer API key).

    Obtenha uma API key gratuita em: https://developer.nytimes.com/get-started

    Args:
        api_key: Chave de API do NYT Developer Portal.

    Returns:
        ScraperNYT: Instância configurada do raspador.
    """
    return ScraperNYT(api_key=api_key, **kwargs)

__all__ = [
    "presidencia",
    "cnj",
    "ipea",
    "senado",
    "camara",
    "cfm",
    "nyt",
    "expand",
    "remove_duplicates",
    "extract",
    "check"
]
