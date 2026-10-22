"""Paridade entre o schema de saída e o que o parser extrai das amostras.

Duas conferências por raspador registrado em ``ESPERADOS``:

- as colunas que ``_parse_page`` tira da amostra ``typical``, mais
  ``termo_busca`` (que ``raspar()`` acrescenta), são as colunas de
  ``Output.colunas()``, na mesma ordem;
- cada exemplo declarado no schema aparece nos valores extraídos das
  amostras, para que a documentação gerada não mostre valor inventado.
  ``termo_busca`` fica de fora, porque o valor dele vem de quem chama.
"""

from pathlib import Path

import pandas as pd
import pytest

from tests.schemas.test_schema_coverage import ESPERADOS, Registro

_TESTES = Path(__file__).resolve().parents[1]


def extrair(registro: Registro, amostra: str) -> pd.DataFrame:
    """Roda o parser do raspador sobre uma amostra versionada."""
    caminho = _TESTES / registro.pasta / "samples" / amostra
    return registro.construir()._parse_page(str(caminho))  # pylint: disable=protected-access


def _aparece(exemplo: object, valores: list[object]) -> bool:
    """Igualdade, ou trecho de texto: o exemplo de um campo longo pode ser recorte do valor."""
    for valor in valores:
        if valor == exemplo:
            return True
        if isinstance(exemplo, str) and isinstance(valor, str) and exemplo in valor:
            return True
    return False


@pytest.mark.parametrize("classe", list(ESPERADOS), ids=lambda classe: classe.__name__)
def test_colunas_da_amostra_typical_sao_as_do_schema(classe):
    registro = ESPERADOS[classe]
    df = extrair(registro, registro.amostras[0])
    assert len(df) > 0, "a amostra typical precisa ter linhas para a paridade dizer algo"
    assert list(df.columns) + ["termo_busca"] == registro.saida.colunas()


# Agrupado por schema: ANS e ANVISA dividem o OutputDatalegis, e o exemplo de
# URL de cada portal só aparece na saída do raspador daquele portal.
_SCHEMAS_DE_SAIDA = sorted({registro.saida for registro in ESPERADOS.values()}, key=lambda schema: schema.__name__)


@pytest.mark.parametrize("schema", _SCHEMAS_DE_SAIDA, ids=lambda schema: schema.__name__)
def test_exemplos_do_schema_saem_das_amostras(schema):
    registros = [registro for registro in ESPERADOS.values() if registro.saida is schema]
    df = pd.concat(
        [extrair(registro, amostra) for registro in registros for amostra in registro.amostras], ignore_index=True
    )
    ausentes = []
    for coluna, campo in schema.model_fields.items():
        if coluna == "termo_busca":
            continue
        assert campo.examples, f"{schema.__name__}.{coluna} sem exemplo"
        valores = df[coluna].tolist()
        ausentes.extend(f"{coluna}={exemplo!r}" for exemplo in campo.examples if not _aparece(exemplo, valores))
    assert not ausentes, f"exemplos de {schema.__name__} que nenhuma amostra contém: {ausentes}"
