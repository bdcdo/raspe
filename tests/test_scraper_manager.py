"""Testes unitários para a função `scraper()` do scraper_manager.

A função é uma factory que mapeia nomes ("PRESIDENCIA", "IPEA", ...) para
classes de scraper. Os scrapers não devem fazer rede em seus testes — para
``ScraperCamaraDeputados``, que invoca ``_prep_scrape`` no ``__init__``
(que faz GET na página inicial), mockamos o método antes da instanciação.
"""

import pytest

from raspe.scraper_manager import scraper
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.ipea import IpeaScraper
from raspe.scrapers.presidencia import ScraperPresidencia
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

    def test_nome_case_insensitive(self):
        """A função normaliza o nome com .upper(), aceitando minúsculas/misturas."""
        assert isinstance(scraper("Presidencia"), ScraperPresidencia)
        assert isinstance(scraper("IPEA"), IpeaScraper)

    def test_nome_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="não é suportado"):
            scraper("desconhecido")
