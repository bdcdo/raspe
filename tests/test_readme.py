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
    """Colunas listadas na tabela que segue o título ``Colunas de `raspe.<fabrica>()` `` no README."""
    texto = README.read_text(encoding="utf-8")
    titulo = f"Colunas de `raspe.{fabrica}()`"
    assert titulo in texto, f"README sem a tabela '{titulo}'"
    depois = texto.split(titulo, 1)[1]
    linhas = re.search(r"\n\n((?:\|.*\n)+)", depois)
    assert linhas, f"'{titulo}' sem tabela logo abaixo"
    corpo = linhas.group(1).splitlines()[2:]  # pula cabeçalho e separador
    return [re.match(r"\|\s*`([^`]+)`", linha).group(1) for linha in corpo]  # type: ignore[union-attr]


@pytest.mark.parametrize("fabrica", list(SEM_SCHEMA))
def test_readme_lista_as_colunas_do_raspador_sem_schema(fabrica):
    """A tabela do README traz exatamente as colunas do DataFrame, na ordem dele."""
    classe = SEM_SCHEMA[fabrica]
    assert classe.schema_saida is None, f"{classe.__name__} ganhou schema: tire a tabela do README e daqui"
    assert _tabela_de_colunas(fabrica) == [*classe.colunas, "termo_busca"]
