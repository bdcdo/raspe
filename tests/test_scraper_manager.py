"""Testes unitários para a função `scraper()` do scraper_manager.

A função é uma factory que mapeia nomes ("PRESIDENCIA", "IPEA", ...) para
classes de scraper. Os scrapers não devem fazer rede em seus testes — para
``ScraperCamaraDeputados``, que invoca ``_prep_scrape`` no ``__init__``
(que faz GET na página inicial), mockamos o método antes da instanciação.
"""

import inspect

import pytest

import raspe
from raspe.scraper_manager import scraper
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.capes import ScraperCapes
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.ipea import IpeaScraper
from raspe.scrapers.nyt import ScraperNYT
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from raspe.scrapers.senado import ScraperSenadoFederal


@pytest.fixture(autouse=True)
def _mock_camara_prep_scrape(mocker):
    """Evita rede no __init__ de ScraperCamaraDeputados (faz GET inicial)."""
    mocker.patch.object(ScraperCamaraDeputados, "_prep_scrape", return_value={})


class TestScraperFactory:
    def test_presidencia(self):
        instance = scraper("presidencia")
        assert isinstance(instance, ScraperPresidencia)

    def test_ipea(self):
        instance = scraper("ipea")
        assert isinstance(instance, IpeaScraper)

    def test_senado(self):
        instance = scraper("senado")
        assert isinstance(instance, ScraperSenadoFederal)

    def test_camara(self):
        instance = scraper("camara")
        assert isinstance(instance, ScraperCamaraDeputados)

    def test_capes(self):
        instance = scraper("capes")
        assert isinstance(instance, ScraperCapes)

    def test_cfm(self):
        instance = scraper("cfm")
        assert isinstance(instance, ScraperCFM)

    def test_folha(self):
        instance = scraper("folha")
        assert isinstance(instance, ScraperFolha)

    def test_nyt(self):
        """O NYT exige API key — repassada via **kwargs ao construtor."""
        instance = scraper("nyt", api_key="chave-de-teste")
        assert isinstance(instance, ScraperNYT)

    def test_saudelegis(self):
        instance = scraper("saudelegis")
        assert isinstance(instance, ScraperSaudeLegis)

    def test_ans(self):
        instance = scraper("ans")
        assert isinstance(instance, ScraperANS)

    def test_anvisa(self):
        instance = scraper("anvisa")
        assert isinstance(instance, ScraperANVISA)

    def test_kwargs_repassados_ao_construtor(self):
        """kwargs chegam ao raspador — `headless` desliga o modo headless."""
        instance = scraper("ans", headless=False)
        assert instance._headless is False

    def test_nome_case_insensitive(self):
        """A função normaliza o nome com .upper(), aceitando minúsculas/misturas."""
        assert isinstance(scraper("Presidencia"), ScraperPresidencia)
        assert isinstance(scraper("IPEA"), IpeaScraper)

    def test_nome_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="não é suportado"):
            scraper("desconhecido")

    def test_erro_lista_fontes_suportadas(self):
        """A mensagem de erro enumera as fontes válidas."""
        with pytest.raises(ValueError, match="Disponíveis:.*CFM.*"):
            scraper("desconhecido")

    def test_cobre_todas_as_factories_publicas(self):
        """O mapping não pode ficar para trás das factories de `raspe`.

        Toda factory pública (`raspe.cfm()`, `raspe.ans()`, ...) deve ter
        entrada correspondente em `scraper()`, com o mesmo nome em maiúsculas.

        As factories saem de `raspe.__all__`, e não de uma lista escrita aqui:
        com a lista à mão, uma factory nova entraria no `__all__` sem entrar no
        teste, e o mapping voltaria a ficar defasado sem ninguém notar. O filtro
        por `__module__ == "raspe"` separa as funções definidas no próprio
        `raspe/__init__.py` dos utilitários que ele reexporta de `raspe.utils`;
        as exceções do `__all__` ficam de fora por serem classes.
        """
        factories = {
            nome
            for nome in raspe.__all__
            if inspect.isfunction(getattr(raspe, nome)) and getattr(raspe, nome).__module__ == "raspe"
        }

        from raspe.scraper_manager import _MAPPING
        assert {nome.upper() for nome in factories} == set(_MAPPING)
