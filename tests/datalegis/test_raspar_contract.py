"""Contrato offline de ``ScraperANVISA.raspar`` (base ``ScraperDatalegis``) com páginas reais.

O navegador não abre: a página falsa de ``navegador_falso`` devolve, na
ordem em que o raspador lê, os samples de ``samples/raspar/`` (capturados por
``tests/fixtures/capture/datalegis.py``). A primeira leitura é a da contagem
de páginas, e as seguintes, as páginas salvas.
"""

import asyncio
import os

import pytest

from raspe.exceptions import ScraperError
from raspe.schemas.datalegis import OutputDatalegis
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.datalegis import ScraperDatalegis
from tests._helpers import load_sample, navegador_falso


def _sample(nome: str) -> str:
    return load_sample("datalegis", f"raspar/{nome}")


def _raspador(mocker, *htmls: str, classe: type[ScraperDatalegis] = ScraperANVISA) -> ScraperDatalegis:
    """Raspador com a página falsa devolvendo ``htmls``, um por leitura, nessa ordem."""
    mocker.patch("asyncio.sleep", mocker.AsyncMock())
    raspador = navegador_falso(mocker, classe(debug=False))
    raspador.pagina_falsa.content.side_effect = htmls
    return raspador


class TestRaspar:
    def test_typical_le_as_duas_paginas(self, mocker):
        """A contagem "1 - 50 de 62 itens" dá duas páginas; a segunda vem pelo combobox de paginação."""
        raspador = _raspador(mocker, _sample("page_01.html"), _sample("page_01.html"), _sample("page_02.html"))
        combobox = mocker.AsyncMock()
        raspador.pagina_falsa.query_selector.return_value = combobox
        df = raspador.raspar(pesquisa="doenças raras")
        assert len(df) == 62
        assert list(df.columns) == OutputDatalegis.colunas()
        combobox.select_option.assert_awaited_once_with(label="2")
        # A página 2 só é salva depois que a contagem passa a começar no item 51.
        espera = raspador.pagina_falsa.wait_for_selector.await_args_list[-1]
        assert espera.args == ("#numeroRegistroInicial:text-is('51')",)

    def test_single_page(self, mocker):
        raspador = _raspador(mocker, _sample("single_page.html"), _sample("single_page.html"))
        df = raspador.raspar(pesquisa="medicamento órfão")
        assert len(df) == 6
        assert list(df.columns) == OutputDatalegis.colunas()
        raspador.pagina_falsa.query_selector.assert_not_awaited()

    def test_no_results(self, mocker):
        raspador = _raspador(mocker, _sample("no_results.html"), _sample("no_results.html"))
        df = raspador.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        assert list(df.columns) == OutputDatalegis.colunas()

    def test_acesso_recusado_levanta_scraper_error(self, mocker):
        html = _sample("acesso_negado.html")
        raspador = _raspador(mocker, html, html, classe=ScraperANS)
        with pytest.raises(ScraperError, match="ANSlegis"):
            raspador.raspar(pesquisa="doença rara")

    def test_pagina_que_nao_abre_levanta_scraper_error_e_apaga_a_pasta(self, mocker):
        """Sem o combobox, a página 2 não abre: o erro não vira resultado com só a página 1."""
        raspador = _raspador(mocker, _sample("page_01.html"), _sample("page_01.html"))
        raspador.pagina_falsa.query_selector.return_value = None
        with pytest.raises(ScraperError, match="página 2 de 2"):
            raspador.raspar(pesquisa="doenças raras")
        assert not os.path.exists(raspador.download_path)


@pytest.mark.parametrize("arquivo, paginas", [
    ("page_01.html", 2), ("single_page.html", 1), ("no_results.html", 0), ("acesso_negado.html", 0),
])
def test_contagem_pela_linha_de_itens(mocker, arquivo, paginas):
    """Sem a contagem "1 - 50 de 62 itens", dá 0, e ``raspar`` confere o aviso de busca vazia."""
    raspador = _raspador(mocker, _sample(arquivo))
    raspador._page = raspador.pagina_falsa
    assert asyncio.run(raspador._encontrar_total_paginas()) == paginas


@pytest.mark.parametrize("contagem, paginas", [("1 - 50 de 1.234 itens.", 25), ("1 - 1 de 1 item.", 1)])
def test_contagem_com_milhar_e_no_singular(mocker, contagem, paginas):
    raspador = _raspador(mocker, f"<html><body><label>{contagem}</label></body></html>")
    raspador._page = raspador.pagina_falsa
    assert asyncio.run(raspador._encontrar_total_paginas()) == paginas
