"""Gera ``docs/colunas.md`` a partir dos schemas de saída.

O documento é derivado, nunca editado à mão: as colunas, os tipos, as
descrições e os exemplos vêm dos ``Output*`` de :mod:`raspe.schemas`, e as
seções seguem as fábricas públicas de :mod:`raspe`. O teste
``tests/schemas/test_documentacao.py`` reprova quando o arquivo versionado
diverge do gerado.

Uso::

    python -m raspe.schemas.documentacao                # reescreve docs/colunas.md
    python -m raspe.schemas.documentacao --saida outro.md

Este módulo importa os raspadores, e por isso :mod:`raspe.schemas` não o
reexporta: os raspadores importam :mod:`raspe.schemas.base`, e o reexport
criaria importação circular.
"""

import argparse
import ast
import importlib
import inspect
import pkgutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import raspe
import raspe.scrapers
from raspe.abstract_scraper import AbstractScraper
from raspe.schemas.base import OutputBase, descrever_tipo

_CABECALHO = """\
# Colunas devolvidas por `raspar()`

<!-- Gerado por `python -m raspe.schemas.documentacao` a partir dos schemas de saída em `src/raspe/schemas/`. \
Não editar à mão. -->

Cada raspador devolve um `pandas.DataFrame` com exatamente estas colunas, nesta ordem, inclusive quando a busca não \
tem resultado. A coluna `termo_busca` repete o termo pesquisado, o que permite empilhar buscas diferentes num mesmo \
DataFrame. Os exemplos saem das amostras usadas nos testes do pacote.
"""


def descobrir_raspadores() -> list[type[AbstractScraper]]:
    """Lista os raspadores concretos definidos nos módulos de :mod:`raspe.scrapers`.

    Uma classe conta no módulo em que foi definida. Um nome alternativo
    (``IpeaScraper = ScraperIpea``) aponta para a mesma classe e sai uma vez só.

    Returns:
        Classes ordenadas pelo nome.
    """
    encontrados: set[type[AbstractScraper]] = set()
    for info in pkgutil.iter_modules(raspe.scrapers.__path__):
        modulo = importlib.import_module(f"{raspe.scrapers.__name__}.{info.name}")
        for _, classe in inspect.getmembers(modulo, inspect.isclass):
            if (
                issubclass(classe, AbstractScraper)
                and classe.__module__ == modulo.__name__
                and not inspect.isabstract(classe)
            ):
                encontrados.add(classe)
    return sorted(encontrados, key=lambda classe: classe.__name__)


def fabricas_por_raspador() -> dict[str, list[str]]:
    """Mapeia o nome de cada classe de raspador às fábricas públicas que a devolvem.

    Lê o fonte de ``raspe/__init__.py`` em vez de chamar as fábricas, porque
    algumas exigem credencial (``nyt``) e outras importam o Playwright. Conta
    como fábrica a função listada em ``raspe.__all__`` que devolve a chamada de
    uma classe, como em ``return ScraperCFM(**kwargs)``.

    Returns:
        Nome da classe para a lista ordenada de nomes de fábrica.
    """
    publicos = set(raspe.__all__)
    arvore = ast.parse(Path(raspe.__file__).read_text(encoding="utf-8"))
    fabricas: dict[str, list[str]] = {}
    for no in arvore.body:
        if not isinstance(no, ast.FunctionDef) or no.name not in publicos:
            continue
        for interno in ast.walk(no):
            if (
                isinstance(interno, ast.Return)
                and isinstance(interno.value, ast.Call)
                and isinstance(interno.value.func, ast.Name)
            ):
                fabricas.setdefault(interno.value.func.id, []).append(no.name)
    return {classe: sorted(nomes) for classe, nomes in fabricas.items()}


def _celula(valor: Any) -> str:
    """Formata um valor para célula de tabela Markdown, escapando a barra vertical."""
    texto = str(valor).replace("\n", " ")
    return texto.replace("|", "\\|")


def _tabela(schema: type[OutputBase]) -> list[str]:
    """Monta as linhas da tabela de colunas de um schema de saída."""
    linhas = ["| Coluna | Tipo | Descrição | Exemplo |", "| --- | --- | --- | --- |"]
    for coluna in schema.colunas():
        campo = schema.model_fields[coluna]
        exemplo = _celula(campo.examples[0]) if campo.examples else ""
        linhas.append(
            f"| `{coluna}` | {descrever_tipo(campo.annotation)} | {_celula(campo.description or '')} | {exemplo} |"
        )
    return linhas


def gerar_documento_colunas() -> str:
    """Gera o conteúdo de ``docs/colunas.md``.

    Uma seção por schema de saída. Raspadores que dividem o schema (ANS e
    ANVISA herdam o do Datalegis) dividem a seção. As seções seguem a ordem
    alfabética da primeira fábrica.

    Returns:
        Documento Markdown, terminado em quebra de linha.
    """
    fabricas = fabricas_por_raspador()
    grupos: dict[type[OutputBase], list[str]] = {}
    sem_schema: list[str] = []
    for classe in descobrir_raspadores():
        nomes = fabricas.get(classe.__name__, [])
        if classe.schema_saida is None:
            sem_schema.extend(nomes)
            continue
        grupos.setdefault(classe.schema_saida, []).extend(nomes)

    secoes = sorted(
        ((sorted(nomes), schema) for schema, nomes in grupos.items() if nomes),
        key=lambda par: par[0][0],
    )

    linhas = [_CABECALHO]
    for nomes, schema in secoes:
        titulo = " e ".join(f"`raspe.{nome}()`" for nome in nomes)
        linhas.append(f"## {titulo}\n")
        linhas.append(f"Schema: `{schema.__name__}`.\n")
        linhas.extend(_tabela(schema))
        linhas.append("")
    if sem_schema:
        pendentes = ", ".join(f"`raspe.{nome}()`" for nome in sorted(sem_schema))
        linhas.append(f"## Raspadores ainda sem schema de saída\n\n{pendentes}. As colunas deles estão no README.\n")
    return "\n".join(linhas).rstrip("\n") + "\n"


def main(argv: Sequence[str] | None = None) -> None:
    """Grava o documento gerado no caminho pedido.

    Args:
        argv: Argumentos de linha de comando; ``None`` lê ``sys.argv``.
    """
    analisador = argparse.ArgumentParser(description="Gera a documentação das colunas de raspar().")
    analisador.add_argument("--saida", default="docs/colunas.md", help="Arquivo de destino.")
    argumentos = analisador.parse_args(argv)
    destino = Path(argumentos.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(gerar_documento_colunas(), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
