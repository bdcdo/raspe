"""Testes offline do fluxo ``PlaywrightScraper.raspar``.

O navegador não é aberto: ``_browser_context`` vira um context manager que só
entrega uma página falsa (``AsyncMock``), e as esperas de ``asyncio.sleep`` e do
Cloudflare são anuladas. Assim dá para exercitar o fluxo de ``_raspar_async``
(busca, contagem, pasta de download, ``_parse_data``, ``termo_busca``) sem rede.
"""

import os
from contextlib import asynccontextmanager

import pandas as pd
import pytest

from raspe.playwright_scraper import PlaywrightScraper


class _DummyPlaywright(PlaywrightScraper):
    """Raspador Playwright mínimo, sem resultados."""

    colunas = ["titulo", "link"]

    def __init__(self, debug: bool = False):
        super().__init__("DUMMY_PW", debug=debug)
        self.buscas: list[dict] = []

    @property
    def url_base(self) -> str:
        return "https://exemplo.gov.br/busca"

    async def _executar_busca(self, **kwargs) -> None:
        self.buscas.append(kwargs)

    async def _encontrar_total_paginas(self) -> int:
        return 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        raise AssertionError("sem resultados, nenhuma página deveria ser lida")


def _raspador(mocker, pasta=None, debug: bool = False) -> _DummyPlaywright:
    """Raspador com navegador falso; ``pasta`` troca o ``download_path`` (padrão: mkdtemp)."""
    r = _DummyPlaywright(debug=debug)
    if pasta is not None:
        r.download_path = str(pasta)
    r.page_load_wait = r.between_pages_wait = 0
    r.pagina_falsa = mocker.AsyncMock()

    @asynccontextmanager
    async def _contexto_falso():
        r._page = r.pagina_falsa
        try:
            yield r._page
        finally:
            r._page = None

    mocker.patch.object(r, "_browser_context", _contexto_falso)
    mocker.patch.object(r, "_aguardar_cloudflare", mocker.AsyncMock())
    return r


class TestRasparSemResultados:
    def test_devolve_as_colunas_da_fonte_e_o_termo(self, mocker):
        raspador = _raspador(mocker)
        df = raspador.raspar(assunto="termo inexistente")
        assert df.empty
        assert {"titulo", "link", "termo_busca"} <= set(df.columns)
        assert raspador.buscas == [{"assunto": "termo inexistente"}]
        raspador.pagina_falsa.goto.assert_awaited_once()

    def test_limpa_a_pasta_de_download_sem_debug(self, mocker):
        """Sem debug, não sobra nem a raiz criada pelo mkdtemp()."""
        raspador = _raspador(mocker)
        raspador.raspar(assunto="x")
        assert not os.path.exists(raspador.download_path)

    def test_mantem_a_pasta_com_debug(self, mocker, tmp_path):
        raspador = _raspador(mocker, tmp_path, debug=True)
        raspador.raspar(assunto="x")
        assert os.listdir(raspador.download_path)
