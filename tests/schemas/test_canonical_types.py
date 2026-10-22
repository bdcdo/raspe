"""Nomes e tipos canônicos dos schemas.

Os parâmetros comuns a vários raspadores (pesquisa, páginas, período, ano)
têm nome, tipo e validação definidos uma vez, nos mixins de
:mod:`raspe.schemas.base`. Este módulo reprova o schema concreto que declara
um desses campos sem herdar o mixin, que muda o tipo ao redeclarar, ou que usa
um sinônimo no lugar do nome canônico. Confere também a forma dos nomes, o
``extra="forbid"``, a presença de descrição e exemplo em todo campo, e que as
linhas das amostras passam no schema de saída.
"""

import math
import re

import pytest
from pydantic import TypeAdapter

from raspe.schemas import (
    AnoMixin,
    IntervaloDatasMixin,
    OutputBase,
    PaginasMixin,
    PesquisaNavegadorMixin,
    PesquisaObrigatoriaMixin,
    PesquisaOpcionalMixin,
)
from tests.schemas.test_output_parity import extrair
from tests.schemas.test_schema_coverage import ESPERADOS

# Campo canônico para os mixins que o declaram. O tipo aceito sai do próprio
# mixin, para que mudar a anotação no mixin não exija mexer aqui.
MIXINS_CANONICOS = {
    "pesquisa": (PesquisaObrigatoriaMixin, PesquisaOpcionalMixin, PesquisaNavegadorMixin),
    "paginas": (PaginasMixin,),
    "data_inicio": (IntervaloDatasMixin,),
    "data_fim": (IntervaloDatasMixin,),
    "ano": (AnoMixin,),
}

# Nomes que os raspadores usavam, ou que um raspador novo tenderia a usar, no
# lugar dos canônicos. Podem aparecer como alias deprecado, nunca como campo.
SINONIMOS = {
    "texto", "termo", "assunto", "q", "query", "busca", "keyword",
    "pagina", "page", "pages",
    "data_inicial", "data_final", "inicio", "fim", "begin_date", "end_date",
    "year",
}

_SNAKE_CASE_ASCII = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")

_ENTRADAS = sorted({registro.entrada for registro in ESPERADOS.values()}, key=lambda schema: schema.__name__)
_SAIDAS = sorted({registro.saida for registro in ESPERADOS.values()}, key=lambda schema: schema.__name__)
_TODOS = _ENTRADAS + _SAIDAS


def _ids(schema):
    return schema.__name__


@pytest.mark.parametrize("schema", _ENTRADAS, ids=_ids)
def test_campo_canonico_vem_do_mixin_com_o_mesmo_tipo(schema):
    for campo, mixins in MIXINS_CANONICOS.items():
        if campo not in schema.model_fields:
            continue
        donos = [mixin for mixin in mixins if issubclass(schema, mixin)]
        assert donos, f"{schema.__name__}.{campo} declarado sem herdar {[m.__name__ for m in mixins]}"
        esperado = donos[0].model_fields[campo].annotation
        assert schema.model_fields[campo].annotation == esperado, (
            f"{schema.__name__}.{campo} mudou o tipo canônico {esperado}"
        )


@pytest.mark.parametrize("schema", _ENTRADAS, ids=_ids)
def test_todo_schema_de_entrada_tem_pesquisa(schema):
    """Sem 'pesquisa' o raspador não ganharia a coluna termo_busca."""
    assert "pesquisa" in schema.model_fields


@pytest.mark.parametrize("schema", _ENTRADAS, ids=_ids)
def test_sinonimo_nao_vira_campo(schema):
    assert not set(schema.model_fields) & SINONIMOS


@pytest.mark.parametrize("schema", _ENTRADAS, ids=_ids)
def test_alias_deprecado_aponta_para_campo_e_nao_e_campo(schema):
    for antigo, canonico in schema.aliases_deprecados.items():
        assert canonico in schema.model_fields, f"alias '{antigo}' aponta para '{canonico}', que não é campo"
        assert antigo not in schema.model_fields


@pytest.mark.parametrize("schema", _TODOS, ids=_ids)
def test_nomes_em_snake_case_ascii(schema):
    fora = [nome for nome in schema.model_fields if not _SNAKE_CASE_ASCII.match(nome)]
    assert not fora


@pytest.mark.parametrize("schema", _TODOS, ids=_ids)
def test_schema_recusa_campo_extra(schema):
    assert schema.model_config.get("extra") == "forbid"


@pytest.mark.parametrize("schema", _TODOS, ids=_ids)
def test_todo_campo_tem_descricao_e_exemplo_valido(schema):
    for nome, campo in schema.model_fields.items():
        assert campo.description, f"{schema.__name__}.{nome} sem descrição"
        if nome == "paginas":
            # range não tem forma JSON; o exemplo está na descrição do mixin.
            continue
        assert campo.examples, f"{schema.__name__}.{nome} sem exemplo"
        adaptador = TypeAdapter(campo.annotation)
        for exemplo in campo.examples:
            adaptador.validate_python(exemplo, strict=True)


@pytest.mark.parametrize("classe", list(ESPERADOS), ids=lambda classe: classe.__name__)
def test_linhas_da_amostra_passam_no_schema_de_saida(classe):
    """Tipo de coluna errado (número como texto, booleano como texto) reprova aqui."""
    registro = ESPERADOS[classe]
    df = extrair(registro, registro.amostras[0]).assign(termo_busca="natjus")
    for linha in df.to_dict(orient="records"):
        # O pandas guarda texto ausente como NaN; o schema o declara como None.
        normalizada = {
            coluna: None if isinstance(valor, float) and math.isnan(valor) else valor
            for coluna, valor in linha.items()
        }
        registro.saida.model_validate(normalizada, strict=True)


def test_colunas_poe_termo_busca_por_ultimo():
    """A ordem de colunas() é a do DataFrame: campos do raspador, depois os da base."""

    class Exemplo(OutputBase):
        primeira: str
        segunda: int

    assert Exemplo.colunas() == ["primeira", "segunda", "termo_busca"]
