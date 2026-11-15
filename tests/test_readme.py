"""Testes do README: a documentação das colunas que ainda não sai dos schemas."""

import re
from pathlib import Path

import pytest

from raspe.abstract_scraper import AbstractScraper
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.senado import ScraperSenadoFederal

README = Path(__file__).resolve().parent.parent / "README.md"

# Câmara e Senado ainda não têm schema de saída, então ``docs/colunas.md`` não os cobre
# e a tabela de colunas deles fica no README, escrita à mão. Quando ganharem schema,
# saem daqui e do README.
SEM_SCHEMA: dict[str, type[AbstractScraper]] = {
    "camara": ScraperCamaraDeputados,
    "senado": ScraperSenadoFederal,
}


def _tabela_de_colunas(fabrica: str) -> list[str]:
    """Colunas listadas na tabela logo abaixo do título ``Colunas de `raspe.<fabrica>()`:`` no README."""
    titulo = f"Colunas de `raspe.{fabrica}()`:"
    linhas = README.read_text(encoding="utf-8").splitlines()
    assert titulo in linhas, f"README sem a linha '{titulo}'"
    # O título, uma linha em branco e a tabela, que acaba na primeira linha que não começa com "|".
    tabela: list[str] = []
    for linha in linhas[linhas.index(titulo) + 2:]:
        if not linha.startswith("|"):
            break
        tabela.append(linha)
    assert len(tabela) > 2, f"'{titulo}' sem tabela logo abaixo"
    colunas = []
    for linha in tabela[2:]:  # pula cabeçalho e separador
        nome = re.match(r"\|\s*`([^`]+)`\s*\|", linha)
        assert nome, f"linha da tabela '{titulo}' sem o nome da coluna entre crases: {linha}"
        colunas.append(nome.group(1))
    return colunas


@pytest.mark.parametrize("fabrica", list(SEM_SCHEMA))
def test_readme_lista_as_colunas_do_raspador_sem_schema(fabrica):
    """A tabela do README traz as colunas declaradas do raspador e ``termo_busca``, nessa ordem."""
    classe = SEM_SCHEMA[fabrica]
    assert classe.schema_saida is None, f"{classe.__name__} ganhou schema: tire a tabela do README e daqui"
    assert _tabela_de_colunas(fabrica) == [*classe.colunas, "termo_busca"]
