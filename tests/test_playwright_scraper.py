"""Testes offline do fluxo ``PlaywrightScraper.raspar``.

O navegador não é aberto: ``_browser_context`` vira um context manager que só
entrega uma página falsa (``AsyncMock``), e as esperas de ``asyncio.sleep`` e do
Cloudflare são anuladas. Assim dá para exercitar o fluxo de ``raspar``
(busca, contagem, pasta de download, ``_parse_data``, ``termo_busca``) sem rede.
"""

import asyncio
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


def _raspador(
    mocker, pasta=None, debug: bool = False, classe: type[_DummyPlaywright] = _DummyPlaywright
) -> _DummyPlaywright:
    """Raspador com navegador falso; ``pasta`` troca o ``download_path`` (padrão: mkdtemp)."""
    r = classe(debug=debug)
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


class _DuasPaginas(_DummyPlaywright):
    """Duas páginas: a primeira rende uma linha, a segunda vem vazia."""

    async def _encontrar_total_paginas(self) -> int:
        return 2

    async def _navegar_proxima_pagina(self, pagina_atual: int) -> bool:
        return True

    def _parse_page(self, path: str) -> pd.DataFrame:
        if "_00002_" in os.path.basename(path):
            return pd.DataFrame(columns=self.colunas)
        return pd.DataFrame([{"titulo": "t", "link": "l"}])


class TestAvisoDePaginaSemLinhas:
    def test_aviso_aponta_para_quem_chamou_raspar(self, mocker):
        """O aviso do ``_parse_data`` não pode ficar com o asyncio, que roda o navegador."""
        raspador = _raspador(mocker, classe=_DuasPaginas)
        raspador.pagina_falsa.content.return_value = "<html></html>"
        with pytest.warns(UserWarning, match="1 de 2 páginas") as avisos:
            df = raspador.raspar(assunto="x")
        assert len(df) == 1
        [aviso] = [a for a in avisos if "1 de 2 páginas" in str(a.message)]
        assert aviso.filename == __file__


def _raspar_dentro_de_um_loop(raspador: _DummyPlaywright, **kwargs) -> pd.DataFrame:
    """Chama ``raspar()`` como numa célula do Jupyter ou do Colab, com um loop do asyncio já rodando."""

    async def _celula_do_notebook() -> pd.DataFrame:
        return raspador.raspar(**kwargs)

    return asyncio.run(_celula_do_notebook())


class TestRasparComLoopAtivo:
    def test_funciona_dentro_de_um_loop_do_asyncio(self, mocker):
        raspador = _raspador(mocker)
        df = _raspar_dentro_de_um_loop(raspador, assunto="x")
        assert df.empty
        assert raspador.buscas == [{"assunto": "x"}]

    def test_erro_do_navegador_chega_a_quem_chamou(self, mocker):
        """O erro levantado na thread do navegador sobe em ``raspar()``, e o contexto do navegador fecha."""
        raspador = _raspador(mocker)
        raspador.pagina_falsa.goto.side_effect = TimeoutError("portal fora do ar")
        with pytest.raises(TimeoutError, match="portal fora do ar"):
            _raspar_dentro_de_um_loop(raspador, assunto="x")
        assert raspador._page is None
