"""Testes do README: a documentação das colunas que ainda não sai dos schemas."""

import re
from itertools import takewhile
from pathlib import Path

import pytest

from raspe.schemas.documentacao import descobrir_raspadores, fabricas_por_raspador
from tests.schemas.test_schema_coverage import PENDENTES

README = Path(__file__).resolve().parent.parent / "README.md"


def _tabela_de_colunas(fabrica: str) -> list[str]:
    """Colunas listadas na tabela logo abaixo do título ``Colunas de `raspe.<fabrica>()`:`` no README."""
    titulo = f"Colunas de `raspe.{fabrica}()`:"
    linhas = README.read_text(encoding="utf-8").splitlines()
    assert titulo in linhas, f"README sem a linha '{titulo}'"
    # O título, uma linha em branco e a tabela; cabeçalho e separador ficam de fora.
    tabela = list(takewhile(lambda linha: linha.startswith("|"), linhas[linhas.index(titulo) + 2:]))[2:]
    return [re.sub(r"^\|\s*`([^`]*)`.*", r"\1", linha) for linha in tabela]


# Os raspadores ainda sem schema de saída ficam fora de ``docs/colunas.md``, e a tabela de
# colunas deles fica no README, escrita à mão. Quando ganharem schema, saem de PENDENTES
# e deste teste; a tabela do README passa para o documento gerado.
@pytest.mark.parametrize("fabrica", list(PENDENTES))
def test_readme_lista_as_colunas_do_raspador_sem_schema(fabrica):
    """A tabela do README traz as colunas declaradas do raspador e ``termo_busca``, nessa ordem."""
    fabricas = fabricas_por_raspador()
    for classe in descobrir_raspadores():
        if fabrica in fabricas.get(classe.__name__, []):
            assert _tabela_de_colunas(fabrica) == [*classe.colunas, "termo_busca"]
