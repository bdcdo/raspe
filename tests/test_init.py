"""Testes para as factory functions exportadas em raspe.__init__.

Cada função é um wrapper trivial que instancia a classe scraper correspondente.
Os scrapers Playwright (saudelegis, ans, anvisa) carregam o pacote ``playwright``
só quando o navegador abre, portanto podem ser instanciados sem ele em tempo de
teste.
"""

import logging

import pytest

import raspe
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.ipea import IpeaScraper
from raspe.scrapers.nyt import ScraperNYT
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from raspe.scrapers.senado import ScraperSenadoFederal


@pytest.fixture(autouse=True)
def _mock_camara_prep_scrape(mocker):
    """Evita rede no __init__ de ScraperCamaraDeputados."""
    mocker.patch.object(ScraperCamaraDeputados, "_prep_scrape", return_value={})


class TestFactoriesHTTP:
    def test_presidencia(self):
        assert isinstance(raspe.presidencia(), ScraperPresidencia)

    def test_ipea(self):
        assert isinstance(raspe.ipea(), IpeaScraper)

    def test_senado(self):
        assert isinstance(raspe.senado(), ScraperSenadoFederal)

    def test_camara(self):
        assert isinstance(raspe.camara(), ScraperCamaraDeputados)

    def test_cfm(self):
        assert isinstance(raspe.cfm(), ScraperCFM)

    def test_folha(self):
        assert isinstance(raspe.folha(), ScraperFolha)

    def test_nyt_com_api_key(self):
        assert isinstance(raspe.nyt(api_key="chave-de-teste"), ScraperNYT)


class TestFactoriesPlaywright:
    """Factories de scrapers Playwright instanciam sem importar o pacote."""

    def test_saudelegis(self):
        assert isinstance(raspe.saudelegis(), ScraperSaudeLegis)

    def test_ans(self):
        assert isinstance(raspe.ans(), ScraperANS)

    def test_anvisa(self):
        assert isinstance(raspe.anvisa(), ScraperANVISA)


FABRICAS = [
    *[(nome, {}) for nome in (
        "presidencia", "ipea", "senado", "senado_processos", "camara", "camara_proposicoes", "cfm", "folha",
        "capes",
        "saudelegis", "ans", "anvisa",
    )],
    ("nyt", {"api_key": "chave-de-teste"}),
]


@pytest.mark.parametrize("fabrica, extra", FABRICAS)
def test_raspadores_declaram_colunas(fabrica, extra):
    """Sem ``colunas``, a busca sem resultados voltaria como DataFrame sem colunas."""
    assert getattr(raspe, fabrica)(**extra).colunas


@pytest.mark.parametrize("fabrica, extra", FABRICAS)
def test_fabricas_aceitam_debug(fabrica, extra):
    """``raspe.<fonte>(debug=False)`` desliga o modo de depuração já na construção."""
    raspador = getattr(raspe, fabrica)(debug=False, **extra)
    assert raspador.debug is False
    assert raspador.logger.level == logging.INFO


class TestExports:
    def test_version_disponivel(self):
        assert isinstance(raspe.__version__, str)

    def test_funcoes_uteis_reexportadas(self):
        """Funções utilitárias estão acessíveis a partir do pacote."""
        assert callable(raspe.expand)
        assert callable(raspe.remove_duplicates)
        assert callable(raspe.extract)
        assert callable(raspe.check)
        assert callable(raspe.validar_data)
        assert callable(raspe.validar_intervalo_datas)

    def test_excecoes_reexportadas(self):
        """As exceções customizadas são acessíveis pelo pacote raiz."""
        assert raspe.ScraperError is not None
        assert raspe.RateLimitError is not None
        assert raspe.APIError is not None
        assert raspe.ValidationError is not None
        assert raspe.BrowserError is not None
        assert raspe.SeleniumError is raspe.BrowserError
        assert raspe.DriverNotInstalledError is not None
        assert raspe.APIKeyError is not None
