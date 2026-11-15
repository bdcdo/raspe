"""O erro de leitura de uma página chega a quem chamou, em vez de virar página vazia.

Cada ``_parse_page`` deixa a exceção subir, e o ``_parse_data`` a põe na mensagem
do ``ScraperError`` (todas as páginas falharam) ou do aviso (parte delas).
"""

import pytest

from raspe.abstract_scraper import AbstractScraper
from raspe.exceptions import ScraperError
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.capes import ScraperCapes
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.ipea import ScraperIpea
from raspe.scrapers.nyt import ScraperNYT
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from raspe.scrapers.senado import ScraperSenadoFederal

RASPADORES = [
    ScraperANVISA, ScraperCamaraDeputados, ScraperCapes, ScraperCFM, ScraperFolha,
    ScraperIpea, ScraperNYT, ScraperPresidencia, ScraperSaudeLegis, ScraperSenadoFederal,
]


@pytest.mark.parametrize("classe", RASPADORES, ids=lambda c: c.__name__)
def test_pagina_ilegivel_leva_o_erro_original_ao_scraper_error(classe: type[AbstractScraper], tmp_path):
    raspador = classe(api_key="x") if classe is ScraperNYT else classe()
    # Bytes que não são UTF-8: a leitura do arquivo falha com UnicodeDecodeError.
    (tmp_path / f"pagina_00001.{raspador.type.lower()}").write_bytes(b"\xff\xfe\x00 quebrado")
    with pytest.raises(ScraperError, match=r"pagina_00001\.\w+ \(UnicodeDecodeError: ") as erro:
        raspador._parse_data(str(tmp_path))
    assert isinstance(erro.value.__cause__, UnicodeDecodeError)
