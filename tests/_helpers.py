"""Helpers compartilhados pela suíte de testes.

Funções para carregar samples (HTML/JSON/etc.) capturados de respostas reais
e versionados em `tests/<scraper>/samples/`. Usados pelos contratos offline
com `responses`.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TypeVar

from pytest_mock import MockerFixture

from raspe.playwright_scraper import PlaywrightScraper

P = TypeVar("P", bound=PlaywrightScraper)

_TESTS_DIR = Path(__file__).parent


def _resolve(scraper: str, relative_path: str) -> Path:
    """Resolve o caminho absoluto de um sample.

    Args:
        scraper: Nome do scraper (ex.: "presidencia", "ipea").
        relative_path: Caminho relativo dentro de `tests/<scraper>/samples/`.

    Returns:
        Path absoluto do arquivo de sample.

    Raises:
        FileNotFoundError: Se o sample não existir no caminho esperado.
    """
    path = _TESTS_DIR / scraper / "samples" / relative_path
    if not path.is_file():
        raise FileNotFoundError(
            f"Sample não encontrado: {path}. "
            f"Capture com `python -m tests.fixtures.capture.{scraper}` a partir da raiz do repositório."
        )
    return path


def load_sample(scraper: str, relative_path: str, *, encoding: str = "utf-8") -> str:
    """Carrega um sample como texto.

    Args:
        scraper: Nome do scraper.
        relative_path: Caminho relativo (ex.: "raspar/page_01.html").
        encoding: Encoding do arquivo (padrão "utf-8"; eSAJ usa "latin-1").

    Returns:
        Conteúdo do arquivo como string.
    """
    return _resolve(scraper, relative_path).read_text(encoding=encoding)


def load_sample_bytes(scraper: str, relative_path: str) -> bytes:
    """Carrega um sample como bytes.

    Útil quando o `responses.add(body=...)` precisa de bytes para preservar
    o encoding original (ex.: páginas em latin-1) ou para arquivos binários.

    Args:
        scraper: Nome do scraper.
        relative_path: Caminho relativo (ex.: "raspar/page_01.html").

    Returns:
        Conteúdo do arquivo como bytes.
    """
    return _resolve(scraper, relative_path).read_bytes()


def navegador_falso(mocker: MockerFixture, raspador: P) -> P:
    """Troca o navegador de um raspador Playwright por uma página falsa, sem abrir o Chromium.

    A página falsa (``AsyncMock``) fica em ``raspador.pagina_falsa``; o teste
    define o HTML que ela devolve em ``pagina_falsa.content``. As esperas
    (``page_load_wait``, ``between_pages_wait`` e Cloudflare) são anuladas.

    Args:
        mocker: Fixture ``mocker`` do pytest-mock.
        raspador: Instância de uma subclasse de ``PlaywrightScraper``.

    Returns:
        O próprio raspador, já com o navegador falso.
    """
    raspador.page_load_wait = raspador.between_pages_wait = 0
    raspador.pagina_falsa = mocker.AsyncMock()

    @asynccontextmanager
    async def _contexto_falso():
        raspador._page = raspador.pagina_falsa
        try:
            yield raspador._page
        finally:
            raspador._page = None

    mocker.patch.object(raspador, "_browser_context", _contexto_falso)
    mocker.patch.object(raspador, "_aguardar_cloudflare", mocker.AsyncMock())
    return raspador
