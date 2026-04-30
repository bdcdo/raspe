"""Configuração compartilhada do pytest para a suíte raspe.

Fornece fixtures básicas para localização de samples. Não inclui fixture
autouse para mockar `time.sleep` — cada teste com paginação deve usar
`mocker.patch("time.sleep")` explicitamente para deixar a intenção clara.
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def tests_dir() -> Path:
    """Diretório raiz da suíte de testes (`tests/`)."""
    return Path(__file__).parent
