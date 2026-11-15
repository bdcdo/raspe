"""Paridade entre os campos do schema de entrada e os kwargs que o raspador lê.

``raspar(**kwargs)`` não tem parâmetro explícito, então a assinatura do
método não diz nada. O que o raspador aceita de fato é o que o código lê de
``kwargs``: ``kwargs.get('pesquisa')`` em ``_set_query_base``,
``kwargs.get("paginas")`` em ``BaseScraper._download_data``. O teste lê o fonte
de todas as classes do raspe na MRO e reúne as chaves literais lidas. Elas
precisam ser exatamente os campos do schema:

- chave lida e ausente do schema: o schema recusaria um parâmetro que o
  raspador usa, ou o raspador lê um nome antigo;
- campo do schema que ninguém lê: o raspador aceitaria o parâmetro e o
  ignoraria em silêncio, o defeito que os schemas vieram corrigir.

Por isso o código dos raspadores lê os parâmetros sempre por
``kwargs.get('<nome>')`` ou ``kwargs['<nome>']`` com o nome literal.
"""

import ast
import inspect
import textwrap

import pytest

from raspe.abstract_scraper import AbstractScraper
from tests.schemas.test_schema_coverage import ESPERADOS


def _chave_literal(no: ast.AST) -> str | None:
    """Devolve a chave quando ``no`` é ``kwargs.get('x', ...)`` ou ``kwargs['x']``."""
    if (
        isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "get"
        and isinstance(no.func.value, ast.Name)
        and no.func.value.id == "kwargs"
        and no.args
        and isinstance(no.args[0], ast.Constant)
        and isinstance(no.args[0].value, str)
    ):
        return no.args[0].value
    if (
        isinstance(no, ast.Subscript)
        and isinstance(no.value, ast.Name)
        and no.value.id == "kwargs"
        and isinstance(no.slice, ast.Constant)
        and isinstance(no.slice.value, str)
    ):
        return no.slice.value
    return None


def chaves_lidas(classe: type[AbstractScraper]) -> set[str]:
    """Chaves literais de ``kwargs`` lidas pelas classes do raspe na MRO de ``classe``.

    Só o corpo das classes entra: docstring é constante, e o exemplo de código
    dentro dela não vira nó de chamada na árvore.
    """
    chaves: set[str] = set()
    for base in classe.__mro__:
        if not base.__module__.startswith("raspe."):
            continue
        arvore = ast.parse(textwrap.dedent(inspect.getsource(base)))
        for no in ast.walk(arvore):
            chave = _chave_literal(no)
            if chave is not None:
                chaves.add(chave)
    return chaves


@pytest.mark.parametrize("classe", list(ESPERADOS), ids=lambda classe: classe.__name__)
def test_kwargs_lidos_sao_os_campos_do_schema(classe):
    campos = set(ESPERADOS[classe].entrada.model_fields)
    lidas = chaves_lidas(classe)
    nome = classe.__name__
    assert lidas - campos == set(), f"{nome} lê kwargs que o schema não declara: {sorted(lidas - campos)}"
    assert campos - lidas == set(), f"o schema de {nome} declara campos que ninguém lê: {sorted(campos - lidas)}"


def test_leitor_reconhece_as_duas_formas_e_ignora_chave_dinamica():
    """Garante que o leitor de AST não passa por paridade porque deixou de ver chaves."""

    class Exemplo:
        def metodo(self, **kwargs):
            chave = "dinamica"
            return kwargs.get("um"), kwargs["dois"], kwargs.get(chave), kwargs.get("tres", 0)

    arvore = ast.parse(textwrap.dedent(inspect.getsource(Exemplo)))
    chaves = {chave for chave in map(_chave_literal, ast.walk(arvore)) if chave is not None}
    assert chaves == {"um", "dois", "tres"}
