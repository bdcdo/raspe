"""Testes de higiene do próprio repositório git do raspe."""

import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parent.parent


def test_nenhum_arquivo_versionado_esta_coberto_pelo_gitignore():
    """Reprova quando algum arquivo rastreado pelo git casa com uma regra do ``.gitignore``.

    O ``.gitignore`` só vale para arquivo que ainda não está no índice. O que entrou antes
    de a regra existir, ou por ``git add -f``, continua versionado, e cada regeração dele
    vira alteração: o ``.coverage`` reescrito a cada ``pytest`` sujava o ``git status``, e
    ``.pyc`` de módulos já renomeados ou removidos seguiam no repositório. O teste barra a
    classe inteira, em vez de um arquivo por vez.
    """
    if shutil.which("git") is None:
        pytest.skip("executável git ausente")
    # Instalação a partir de sdist não traz o ``.git``. Olhar a raiz, e não só se o git
    # responde, evita rodar contra um repositório que por acaso contenha esta pasta e
    # mantém a falha visível quando o checkout existe mas o git não consegue lê-lo.
    # Em worktree o ``.git`` é arquivo, não diretório; ``exists`` cobre os dois.
    if not (RAIZ_DO_REPOSITORIO / ".git").exists():
        pytest.skip("fora de um checkout git do raspe")

    resultado = subprocess.run(
        # ``core.excludesFile`` vazio tira do ``--exclude-standard`` o ignore global de quem
        # roda a suíte (por padrão ``$XDG_CONFIG_HOME/git/ignore``), que reprovaria arquivo
        # legítimo do projeto. Ficam as regras versionadas e o ``info/exclude`` do clone.
        # ``-z`` separa os caminhos por NUL, sem as aspas que o git põe em nome não ASCII.
        ["git", "-c", "core.excludesFile=", "ls-files", "--cached", "--ignored", "--exclude-standard", "-z"],
        cwd=RAIZ_DO_REPOSITORIO,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if resultado.returncode != 0:
        pytest.fail(f"git ls-files falhou (código {resultado.returncode}): {resultado.stderr.strip()}")

    versionados_e_ignorados = sorted(caminho for caminho in resultado.stdout.split("\0") if caminho)
    assert not versionados_e_ignorados, (
        "Arquivos versionados que o .gitignore cobre. Tire-os do índice com `git rm --cached <arquivo>` "
        "(o arquivo continua no disco):\n" + "\n".join(versionados_e_ignorados)
    )
