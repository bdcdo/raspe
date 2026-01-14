"""
raspe - Raspadores para Pesquisas Acadêmicas

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
from .scrapers.folha import ScraperFolha
from .utils import expand, remove_duplicates, extract, check, validar_data, validar_intervalo_datas
from .exceptions import (
    ScraperError,
    APIKeyError,
    RateLimitError,
    APIError,
    ValidationError,
    SeleniumError,
    DriverNotInstalledError,
)

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

def nyt(api_key: str | None = None, **kwargs):
    """
    Cria um raspador para o New York Times (requer API key).

    Obtenha uma API key gratuita em: https://developer.nytimes.com/get-started

    Args:
        api_key: Chave de API do NYT Developer Portal.
                 Também pode ser configurada via variável de ambiente NYT_API_KEY.

    Returns:
        ScraperNYT: Instância configurada do raspador.

    Raises:
        APIKeyError: Se nenhuma API key for fornecida ou encontrada.
    """
    return ScraperNYT(api_key=api_key, **kwargs)

def folha(**kwargs):
    """
    Cria um raspador para a Folha de São Paulo.

    Args:
        pesquisa: Termo de busca.
        site: 'todos', 'online' ou 'jornal' (default: 'todos').
        data_inicio: Data inicial no formato YYYY-MM-DD.
        data_fim: Data final no formato YYYY-MM-DD.

    Returns:
        ScraperFolha: Instância configurada do raspador.
    """
    return ScraperFolha(**kwargs)


def saudelegis(**kwargs):
    """
    Cria um raspador para o portal SaudeLegis do Ministério da Saúde.

    Este scraper usa Selenium para automação de navegador.
    Requer instalação das dependências: pip install raspe[selenium]

    Args:
        assunto: Termo de busca no campo assunto.
        headless: Se True, executa em modo headless (default: True).
        debug: Se True, mantém arquivos baixados (default: True).

    Returns:
        ScraperSaudeLegis: Instância configurada do raspador.

    Raises:
        DriverNotInstalledError: Se Selenium não estiver instalado.

    Exemplo:
        >>> import raspe
        >>> df = raspe.saudelegis().raspar(assunto="doença rara")
    """
    from .scrapers.saudelegis import ScraperSaudeLegis
    return ScraperSaudeLegis(**kwargs)


__all__ = [
    # Scrapers HTTP
    "presidencia",
    "cnj",
    "ipea",
    "senado",
    "camara",
    "cfm",
    "nyt",
    "folha",
    # Scrapers Selenium
    "saudelegis",
    # Utilitários
    "expand",
    "remove_duplicates",
    "extract",
    "check",
    "validar_data",
    "validar_intervalo_datas",
    # Exceções
    "ScraperError",
    "APIKeyError",
    "RateLimitError",
    "APIError",
    "ValidationError",
    "SeleniumError",
    "DriverNotInstalledError",
]
