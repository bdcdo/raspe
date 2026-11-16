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
from typing import Any

from .exceptions import SeleniumError  # Alias para compatibilidade
from .exceptions import (
    APIError,
    APIKeyError,
    BrowserError,
    DriverNotInstalledError,
    RateLimitError,
    ScraperError,
    ValidationError,
)
from .scrapers.ans import ScraperANS
from .scrapers.anvisa import ScraperANVISA
from .scrapers.camara import ScraperCamaraDeputados
from .scrapers.camara_proposicoes import ScraperCamaraProposicoes
from .scrapers.capes import ScraperCapes
from .scrapers.cfm import ScraperCFM
from .scrapers.folha import ScraperFolha
from .scrapers.ipea import ScraperIpea
from .scrapers.nyt import ScraperNYT
from .scrapers.presidencia import ScraperPresidencia
from .scrapers.saudelegis import ScraperSaudeLegis
from .scrapers.senado import ScraperSenadoFederal
from .scrapers.senado_processos import ScraperSenadoProcessos
from .utils import check, expand, extract, remove_duplicates, validar_data, validar_intervalo_datas

__version__ = version("raspe")


def presidencia(**kwargs):
    """
    Cria um raspador para dados da Presidência da República.

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperPresidencia: Instância configurada do raspador.
    """
    return ScraperPresidencia(**kwargs)


def ipea(**kwargs):
    """
    Cria um raspador para dados do IPEA (Instituto de Pesquisa Econômica Aplicada).

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperIpea: Instância configurada do raspador.
    """
    return ScraperIpea(**kwargs)


def senado(**kwargs):
    """
    Cria um raspador para dados do Senado Federal.

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperSenadoFederal: Instância configurada do raspador.
    """
    return ScraperSenadoFederal(**kwargs)


def camara(**kwargs):
    """
    Cria um raspador para dados da Câmara dos Deputados.

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperCamaraDeputados: Instância configurada do raspador.
    """
    return ScraperCamaraDeputados(**kwargs)


def camara_proposicoes(**kwargs: Any) -> ScraperCamaraProposicoes:
    """
    Cria um raspador para as proposições da Câmara dos Deputados, pela API oficial de Dados Abertos.

    Lista projetos de lei, PECs, requerimentos e demais proposições, tenham
    virado norma ou não. Para a legislação já publicada, use ``raspe.camara()``.

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperCamaraProposicoes: Instância configurada do raspador.

    Exemplo:
        >>> import raspe
        >>> df = raspe.camara_proposicoes().raspar(pesquisa="telemedicina", ano=2020)
    """
    return ScraperCamaraProposicoes(**kwargs)


def senado_processos(**kwargs: Any) -> ScraperSenadoProcessos:
    """
    Cria um raspador para os processos legislativos do Senado Federal, pela API oficial de Dados Abertos.

    Lista projetos de lei, PECs, requerimentos e demais processos do Senado e
    do Congresso Nacional, tenham virado norma ou não. Para a legislação já
    publicada, use ``raspe.senado()``.

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperSenadoProcessos: Instância configurada do raspador.

    Exemplo:
        >>> import raspe
        >>> df = raspe.senado_processos().raspar(pesquisa="telemedicina", ano=2020)
    """
    return ScraperSenadoProcessos(**kwargs)


def cfm(**kwargs):
    """
    Cria um raspador para normas do CFM (Conselho Federal de Medicina).

    Args:
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

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
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

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
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperFolha: Instância configurada do raspador.
    """
    return ScraperFolha(**kwargs)


def capes(**kwargs):
    """
    Cria um raspador para o Portal de Periódicos da CAPES.

    Coleta metadados (título, autores, ano, revista, DOI, etc.) da
    base bibliográfica acadêmica indexada pela CAPES via OpenAlex.

    Args:
        pesquisa: Termo de busca.
        debug: Se True, ativa logs de depuração e mantém arquivos baixados (default: True).

    Returns:
        ScraperCapes: Instância configurada do raspador.

    Exemplo:
        >>> import raspe
        >>> df = raspe.capes().raspar(pesquisa="natjus")
    """
    return ScraperCapes(**kwargs)


def saudelegis(**kwargs):
    """
    Cria um raspador para o portal SaudeLegis do Ministério da Saúde.

    Este scraper usa Playwright para automação de navegador.
    Requer instalação das dependências: pip install raspe[browser]

    Args:
        headless: Se True, executa em modo headless (default: True).
        debug: Se True, mantém arquivos baixados (default: True).

    Returns:
        ScraperSaudeLegis: Instância configurada do raspador.

    Raises:
        DriverNotInstalledError: Se Playwright não estiver instalado.

    Exemplo:
        >>> import raspe
        >>> df = raspe.saudelegis().raspar(pesquisa="doença rara")
    """
    return ScraperSaudeLegis(**kwargs)


def ans(**kwargs):
    """
    Cria um raspador para o portal ANSLegis da ANS.

    Este scraper usa Playwright com stealth para bypass do Cloudflare.
    Requer instalação das dependências: pip install raspe[browser]

    Args:
        headless: Se True, executa em modo headless (default: True).
        debug: Se True, mantém arquivos baixados (default: True).

    Returns:
        ScraperANS: Instância configurada do raspador.

    Raises:
        DriverNotInstalledError: Se Playwright não estiver instalado.

    Exemplo:
        >>> import raspe
        >>> df = raspe.ans().raspar(pesquisa="doença rara")
    """
    return ScraperANS(**kwargs)


def anvisa(**kwargs):
    """
    Cria um raspador para o portal ANVISALegis da ANVISA.

    Este scraper usa Playwright com stealth para bypass do Cloudflare.
    Requer instalação das dependências: pip install raspe[browser]

    Args:
        headless: Se True, executa em modo headless (default: True).
        debug: Se True, mantém arquivos baixados (default: True).

    Returns:
        ScraperANVISA: Instância configurada do raspador.

    Raises:
        DriverNotInstalledError: Se Playwright não estiver instalado.

    Exemplo:
        >>> import raspe
        >>> df = raspe.anvisa().raspar(pesquisa="doença rara")
    """
    return ScraperANVISA(**kwargs)


__all__ = [
    # Scrapers HTTP
    "presidencia",
    "ipea",
    "senado",
    "senado_processos",
    "camara",
    "camara_proposicoes",
    "cfm",
    "nyt",
    "folha",
    "capes",
    # Scrapers Browser (Playwright)
    "saudelegis",
    "ans",
    "anvisa",
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
    "BrowserError",
    "SeleniumError",  # Alias para compatibilidade
    "DriverNotInstalledError",
]
