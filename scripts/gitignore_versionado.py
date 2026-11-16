"""Reprova arquivo versionado que algum ``.gitignore`` do repositório cobre.

O ``.gitignore`` só vale para arquivo que ainda não está no índice. O que entrou
antes de a regra existir, ou por ``git add -f``, continua versionado, e cada
regeração dele vira alteração. Este script lista esses arquivos com a regra que
casou (``git check-ignore -v``) e sai com código 1. Roda no hook
``gitignore-versionado`` do pre-commit e em ``tests/test_repositorio.py``.

Só os ``.gitignore`` contam, versionados ou não: o ignore global e o
``info/exclude`` de quem roda reprovariam arquivo legítimo do projeto. Os
caminhos vêm separados por NUL (``-z``), sem as aspas que o git põe em nome não ASCII.

Uso: ``python scripts/gitignore_versionado.py`` em qualquer pasta do repositório.
"""

import subprocess
import sys
from pathlib import Path


def _git(raiz: Path, *args: str, entrada: str | None = None, aceitos: tuple[int, ...] = (0,)) -> str:
    """Roda um comando git na raiz e devolve a saída.

    Args:
        raiz: Pasta onde o git roda.
        *args: Argumentos do git.
        entrada: Texto para a entrada padrão.
        aceitos: Códigos de saída que não são erro.

    Returns:
        str: A saída padrão.

    Raises:
        SystemExit: Se o git sai com código fora de ``aceitos`` (código 2).
    """
    resultado = subprocess.run(
        ["git", *args],
        cwd=raiz,
        input=entrada,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=120,
    )
    if resultado.returncode not in aceitos:
        comando = " ".join(args)
        print(f"git {comando} falhou (código {resultado.returncode}): {resultado.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return resultado.stdout


def versionados_ignorados(raiz: Path) -> list[tuple[str, str]]:
    """Lista os arquivos versionados que um ``.gitignore`` cobre, com a regra que casou.

    Args:
        raiz: Raiz do repositório.

    Returns:
        list[tuple[str, str]]: Pares ``(caminho, regra)``, com a regra no formato
        ``<.gitignore>:<linha>: <padrão>``, como em ``git check-ignore -v``.
    """
    saida = _git(raiz, "ls-files", "-z", "--cached", "--ignored", "--exclude-per-directory=.gitignore")
    caminhos = [caminho for caminho in saida.split("\0") if caminho]
    if not caminhos:
        return []
    # --no-index: sem ele, o check-ignore não olha arquivo que está no índice. O excludesFile
    # vazio tira o ignore global; o info/exclude fica, mas um .gitignore tem precedência sobre ele.
    saida = _git(
        raiz, "-c", "core.excludesFile=/dev/null", "check-ignore", "-v", "-z", "--no-index", "--stdin",
        entrada="\0".join(caminhos) + "\0", aceitos=(0, 1),
    )
    # Com -z, cada caminho vem em quatro campos: fonte, linha, padrão e caminho.
    campos = saida.split("\0")
    regras = {
        caminho: f"{fonte}:{linha}: {padrao}"
        for fonte, linha, padrao, caminho in zip(campos[0::4], campos[1::4], campos[2::4], campos[3::4])
    }
    return [(caminho, regras.get(caminho, "regra não identificada")) for caminho in caminhos]


def main() -> int:
    """Imprime os arquivos versionados que o ``.gitignore`` cobre.

    Returns:
        int: 0 sem nenhum; 1 com algum.
    """
    raiz = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    achados = versionados_ignorados(raiz)
    if not achados:
        return 0
    print(
        "Arquivos versionados que o .gitignore cobre. Tire-os do índice com `git rm --cached <arquivo>` "
        "(o arquivo continua no disco):"
    )
    for caminho, regra in achados:
        print(f"  {caminho}  (regra {regra})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
