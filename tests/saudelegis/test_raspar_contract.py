"""Contrato offline de ``ScraperSaudeLegis.raspar`` com páginas reais do portal.

O navegador não abre: a página falsa de ``navegador_falso`` devolve, na
ordem em que o raspador lê, os samples de ``samples/raspar/`` (capturados por
``tests/fixtures/capture/saudelegis.py``). A primeira leitura é a da contagem
de páginas, e as seguintes, as páginas salvas.
"""

import asyncio
import sys

import pytest

from raspe.exceptions import ScraperError
from raspe.schemas.saudelegis import OutputSaudeLegis
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from tests._helpers import load_sample, navegador_falso


def _sample(nome: str) -> str:
    return load_sample("saudelegis", f"raspar/{nome}")


def _raspador(mocker, *htmls: str) -> ScraperSaudeLegis:
    """Raspador com a página falsa devolvendo ``htmls``, um por leitura, nessa ordem."""
    raspador = navegador_falso(mocker, ScraperSaudeLegis(debug=False))
    raspador.pagina_falsa.content.side_effect = htmls
    return raspador


class TestRaspar:
    def test_typical_le_as_duas_paginas(self, mocker):
        """O rodapé "Mostrando 1 a 10 de 14 registros" dá duas páginas; a segunda vem pelo link numerado.

        Roda sem o Playwright, como com só o extra ``dev``: o navegador falso não o importa.
        """
        mocker.patch.dict(sys.modules, dict.fromkeys(["playwright", "playwright.async_api", "playwright_stealth"]))
        raspador = _raspador(mocker, _sample("page_01.html"), _sample("page_01.html"), _sample("page_02.html"))
        df = raspador.raspar(pesquisa="doença rara")
        assert len(df) == 14
        assert list(df.columns) == OutputSaudeLegis.colunas()
        assert df["link_url"].str.startswith("http").all()
        cliques = [c.args[0] for c in raspador.pagina_falsa.click.await_args_list]
        assert cliques == ['input[type="submit"][value="Consultar"]', "a[id*='form:']:text-is('2')"]

    def test_single_page(self, mocker):
        raspador = _raspador(mocker, _sample("single_page.html"), _sample("single_page.html"))
        df = raspador.raspar(pesquisa="talidomida")
        assert len(df) == 6
        assert list(df.columns) == OutputSaudeLegis.colunas()

    def test_no_results(self, mocker):
        raspador = _raspador(mocker, _sample("no_results.html"), _sample("no_results.html"))
        df = raspador.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        assert list(df.columns) == OutputSaudeLegis.colunas()

    def test_tabela_sem_contagem_levanta_scraper_error(self, mocker):
        """Sem o rodapé, a página não vira busca vazia: a tabela de origens não vale como aviso."""
        html = _sample("page_01.html").replace("Mostrando 1 a 10 de 14 registros.", "")
        raspador = _raspador(mocker, html, html)
        with pytest.raises(ScraperError, match="aviso de busca vazia"):
            raspador.raspar(pesquisa="doença rara")


@pytest.mark.parametrize("arquivo, paginas", [
    ("page_01.html", 2), ("single_page.html", 1), ("no_results.html", 0),
])
def test_contagem_pelo_rodape_da_tabela(mocker, arquivo, paginas):
    """O rodapé da tabela escondida de origens ("0 a 0 de 0 registro") não entra na conta."""
    raspador = _raspador(mocker, _sample(arquivo))
    raspador._page = raspador.pagina_falsa
    assert asyncio.run(raspador._encontrar_total_paginas()) == paginas
