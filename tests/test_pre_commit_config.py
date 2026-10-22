"""Contrato do ``.pre-commit-config.yaml`` com o passo de lint do CI.

O job de lint roda ``pre-commit run --all-files`` num checkout recém-feito: o
índice coincide com o HEAD e não há merge em curso. Nesse estado, um hook que
decide pelo estado do git, e não pelo conteúdo dos arquivos que recebe, passa
sempre, e o CI mostra ``Passed`` sem ter examinado nada. Estes testes reprovam a
configuração quando um hook desse tipo entra sem o argumento que o faz examinar
os arquivos.
"""

from pathlib import Path

import pytest
import yaml

_CONFIG = Path(__file__).resolve().parent.parent / ".pre-commit-config.yaml"

# Hooks do pre-commit-hooks que, sem o argumento, consultam o estado do git:
# - check-added-large-files mede só os arquivos adicionados no índice
#   (``git diff --staged --diff-filter=A``), que no CI é vazio; com
#   ``--enforce-all`` mede todos os arquivos que recebe.
# - check-merge-conflict retorna 0 quando não acha MERGE_HEAD nem rebase em
#   curso; com ``--assume-in-merge`` procura os marcadores em qualquer estado.
_ARGUMENTO_OBRIGATORIO = {
    "check-added-large-files": "--enforce-all",
    "check-merge-conflict": "--assume-in-merge",
}

# Hooks sem argumento que os faça examinar os arquivos. O forbid-new-submodules
# lê só ``git diff --staged`` ou o intervalo entre PRE_COMMIT_FROM_REF e
# PRE_COMMIT_TO_REF, que o CI não define; o forbid-submodules, do mesmo
# repositório, examina os arquivos e serve no lugar dele.
_INERTES_NO_CI = {"forbid-new-submodules"}


def _hooks() -> list[dict]:
    """Lista os hooks de todos os repositórios do ``.pre-commit-config.yaml``."""
    config = yaml.safe_load(_CONFIG.read_text(encoding="utf-8"))
    return [hook for repo in config["repos"] for hook in repo["hooks"]]


@pytest.mark.parametrize(("hook_id", "argumento"), sorted(_ARGUMENTO_OBRIGATORIO.items()))
def test_hook_dependente_do_git_recebe_argumento(hook_id, argumento):
    entradas = [hook for hook in _hooks() if hook["id"] == hook_id]
    assert entradas, f"{hook_id} saiu do .pre-commit-config.yaml; se a saída é intencional, tire-o deste teste."
    for hook in entradas:
        assert argumento in hook.get("args", []), (
            f"{hook_id} sem {argumento}: no checkout do CI ele passa sem examinar os arquivos."
        )


def test_nenhum_hook_inerte_no_ci():
    presentes = sorted(_INERTES_NO_CI & {hook["id"] for hook in _hooks()})
    assert not presentes, f"{presentes} passam sempre no checkout do CI; use um hook que examine os arquivos."
