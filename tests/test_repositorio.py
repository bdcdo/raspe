"""Testes de higiene do próprio repositório git do raspe."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_DO_REPOSITORIO = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ_DO_REPOSITORIO / "scripts" / "gitignore_versionado.py"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="executável git ausente")


# Dentro de um hook, o git exporta GIT_INDEX_FILE e outras variáveis do repositório do raspe;
# herdadas, elas fariam o git do repositório temporário gravar no índice do raspe.
_AMBIENTE_SEM_GIT = {nome: valor for nome, valor in os.environ.items() if not nome.startswith("GIT_")}


def _git(pasta: Path, *args: str) -> None:
    """Roda o git num repositório temporário, isolado do repositório do raspe."""
    subprocess.run(["git", *args], cwd=pasta, env=_AMBIENTE_SEM_GIT, check=True, capture_output=True, timeout=60)


def _rodar_script(pasta: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Roda o script do hook ``gitignore-versionado`` na pasta, como o pre-commit."""
    return subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=pasta, env=env, capture_output=True, encoding="utf-8", check=False,
        timeout=120,
    )


def test_nenhum_arquivo_versionado_esta_coberto_pelo_gitignore():
    """Reprova quando algum arquivo rastreado pelo git casa com uma regra do ``.gitignore``.

    O ``.gitignore`` só vale para arquivo que ainda não está no índice. O que entrou antes
    de a regra existir, ou por ``git add -f``, continua versionado, e cada regeração dele
    vira alteração: o ``.coverage`` reescrito a cada ``pytest`` sujava o ``git status``, e
    ``.pyc`` de módulos já renomeados ou removidos seguiam no repositório. O teste barra a
    classe inteira, em vez de um arquivo por vez, com o mesmo script do hook.
    """
    # Instalação a partir de sdist não traz o ``.git``. Olhar a raiz, e não só se o git
    # responde, evita rodar contra um repositório que por acaso contenha esta pasta e
    # mantém a falha visível quando o checkout existe mas o git não consegue lê-lo.
    # Em worktree o ``.git`` é arquivo, não diretório; ``exists`` cobre os dois.
    if not (RAIZ_DO_REPOSITORIO / ".git").exists():
        pytest.skip("fora de um checkout git do raspe")
    resultado = _rodar_script(RAIZ_DO_REPOSITORIO)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_mensagem_diz_o_arquivo_e_a_regra_que_casou(tmp_path):
    """Nome não ASCII sai sem aspas, e cada arquivo traz o ``.gitignore`` e a linha da regra."""
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / ".gitignore").write_text("# temporários\n*.tmp\n", encoding="utf-8")
    for nome in ("ação.log", "sub/x.tmp", "ok.txt"):
        (tmp_path / nome).write_text("x", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "sub/.gitignore", "ok.txt")
    _git(tmp_path, "add", "-f", "ação.log", "sub/x.tmp")

    resultado = _rodar_script(tmp_path / "sub", _AMBIENTE_SEM_GIT)

    assert resultado.returncode == 1
    assert "  ação.log  (regra .gitignore:1: *.log)" in resultado.stdout
    assert "  sub/x.tmp  (regra sub/.gitignore:2: *.tmp)" in resultado.stdout
    assert "ok.txt" not in resultado.stdout
