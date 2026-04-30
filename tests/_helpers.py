"""Helpers compartilhados pela suíte de testes.

Funções para carregar samples (HTML/JSON/etc.) capturados de respostas reais
e versionados em `tests/<scraper>/samples/`. Usados pelos contratos offline
com `responses`.
"""

from pathlib import Path

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
            f"Capture com `python tests/fixtures/capture/{scraper}.py`."
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
