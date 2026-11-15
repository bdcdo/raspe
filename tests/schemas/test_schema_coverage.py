"""Cobertura dos schemas: todo raspador público tem Input e Output, ou está na lista de pendentes.

Este módulo é o registro que os outros testes de ``tests/schemas/`` leem.
Raspador novo em ``src/raspe/scrapers/`` reprova aqui até entrar em
``ESPERADOS`` (com os schemas e as amostras) ou, com razão escrita, em
``PENDENTES``. A descoberta varre os módulos de :mod:`raspe.scrapers` e é
conferida contra as fábricas de :mod:`raspe`, para que um raspador exposto
por fábrica não escape à varredura.
"""

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

import pytest

import raspe.schemas
from raspe.abstract_scraper import AbstractScraper
from raspe.schemas import (
    InputBase,
    InputCapes,
    InputCFM,
    InputDatalegis,
    InputFolha,
    InputIpea,
    InputNYT,
    InputPresidencia,
    InputSaudeLegis,
    OutputBase,
    OutputCapes,
    OutputCFM,
    OutputDatalegis,
    OutputFolha,
    OutputIpea,
    OutputNYT,
    OutputPresidencia,
    OutputSaudeLegis,
)
from raspe.schemas.documentacao import descobrir_raspadores, fabricas_por_raspador
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.capes import ScraperCapes
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.datalegis import ScraperDatalegis
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.ipea import ScraperIpea
from raspe.scrapers.nyt import ScraperNYT
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.saudelegis import ScraperSaudeLegis


@dataclass(frozen=True)
class Registro:
    """O que a suíte anti-drift sabe de um raspador ligado a schema.

    Atributos:
        entrada: Schema dos parâmetros de ``raspar()``.
        saida: Schema das colunas do DataFrame.
        construir: Cria o raspador sem rede (o NYT exige chave, mesmo falsa).
        pasta: Pasta do raspador em ``tests/``, onde ficam as amostras.
        amostras: Caminhos dentro de ``samples/``. A primeira é a ``typical``,
            que o parser lê no teste de paridade de colunas; todas servem à
            conferência dos exemplos dos schemas.
    """

    entrada: type[InputBase]
    saida: type[OutputBase]
    construir: Callable[[], AbstractScraper]
    pasta: str
    amostras: tuple[str, ...]


_PAGINAS_HTML = ("raspar/page_01.html", "raspar/page_02.html", "raspar/single_page.html")
_PAGINAS_JSON = ("raspar/page_01.json", "raspar/page_02.json", "raspar/single_page.json")
_PARSE_HTML = ("parse/typical.html",)

ESPERADOS: dict[type[AbstractScraper], Registro] = {
    ScraperPresidencia: Registro(InputPresidencia, OutputPresidencia, ScraperPresidencia, "presidencia", _PAGINAS_HTML),
    ScraperIpea: Registro(InputIpea, OutputIpea, ScraperIpea, "ipea", _PAGINAS_HTML),
    ScraperCapes: Registro(InputCapes, OutputCapes, ScraperCapes, "capes", _PAGINAS_HTML),
    ScraperCFM: Registro(InputCFM, OutputCFM, ScraperCFM, "cfm", _PAGINAS_HTML),
    ScraperFolha: Registro(InputFolha, OutputFolha, ScraperFolha, "folha", _PAGINAS_HTML),
    ScraperNYT: Registro(InputNYT, OutputNYT, lambda: ScraperNYT(api_key="chave-de-teste"), "nyt", _PAGINAS_JSON),
    ScraperSaudeLegis: Registro(InputSaudeLegis, OutputSaudeLegis, ScraperSaudeLegis, "saudelegis", _PARSE_HTML),
    ScraperANS: Registro(InputDatalegis, OutputDatalegis, ScraperANS, "datalegis", _PARSE_HTML),
    ScraperANVISA: Registro(InputDatalegis, OutputDatalegis, ScraperANVISA, "datalegis", _PARSE_HTML),
}

# Por nome de fábrica, e não por classe, porque a reescrita pode trocar as
# classes de lugar e de nome; a fábrica pública é o que fica.
PENDENTES: dict[str, str] = {
    "camara": (
        "Reescrito sobre a API oficial da Câmara num PR paralelo. As colunas vão mudar, e o schema entra "
        "depois do merge da reescrita, para não fixar a forma antiga."
    ),
    "senado": (
        "Reescrito sobre a API oficial do Senado num PR paralelo. As colunas vão mudar, e o schema entra "
        "depois do merge da reescrita, para não fixar a forma antiga."
    ),
}

BASES_INTERMEDIARIAS: dict[type[AbstractScraper], str] = {
    ScraperDatalegis: "Base de ScraperANS e ScraperANVISA, sem fábrica pública; os schemas são os das filhas.",
}

_FABRICAS = fabricas_por_raspador()


def _fabricas(classe: type[AbstractScraper]) -> list[str]:
    return _FABRICAS.get(classe.__name__, [])


def test_todo_raspador_esta_registrado():
    """Raspador fora das três listas reprova, com o nome dele na mensagem."""
    fora = []
    for classe in descobrir_raspadores():
        if classe in ESPERADOS or classe in BASES_INTERMEDIARIAS:
            continue
        fabricas = _fabricas(classe)
        if not fabricas or not set(fabricas) <= set(PENDENTES):
            fora.append(f"{classe.__name__} (fábricas: {fabricas or 'nenhuma'})")
    assert not fora, (
        "Raspadores sem schema registrado em tests/schemas/test_schema_coverage.py: "
        f"{fora}. Declare schema_entrada e schema_saida e inclua o raspador em ESPERADOS, "
        "ou ponha a fábrica em PENDENTES com a razão."
    )


def test_listas_apontam_para_raspadores_que_existem():
    """Entrada velha nas listas reprova, para o registro não acumular nome morto."""
    descobertos = set(descobrir_raspadores())
    assert set(ESPERADOS) <= descobertos
    assert set(BASES_INTERMEDIARIAS) <= descobertos
    fabricas_existentes = {nome for nomes in _FABRICAS.values() for nome in nomes}
    assert set(PENDENTES) <= fabricas_existentes
    assert not set(ESPERADOS) & set(BASES_INTERMEDIARIAS)


def test_toda_fabrica_publica_devolve_raspador_descoberto():
    """Rede de segurança da descoberta: a fábrica não pode devolver classe que a varredura não viu."""
    nomes_descobertos = {classe.__name__ for classe in descobrir_raspadores()}
    assert set(_FABRICAS) <= nomes_descobertos


@pytest.mark.parametrize("classe", list(ESPERADOS), ids=lambda classe: classe.__name__)
def test_esperado_declara_os_schemas_registrados(classe):
    registro = ESPERADOS[classe]
    assert classe.schema_entrada is registro.entrada
    assert classe.schema_saida is registro.saida
    assert _fabricas(classe), f"{classe.__name__} tem schema mas nenhuma fábrica pública o devolve"


@pytest.mark.parametrize("fabrica", list(PENDENTES))
def test_pendente_continua_sem_schema(fabrica):
    """Quando a reescrita ganhar schema, este teste lembra de mover o raspador para ESPERADOS."""
    classes = [classe for classe in descobrir_raspadores() if fabrica in _fabricas(classe)]
    assert classes, f"nenhum raspador devolvido por raspe.{fabrica}()"
    for classe in classes:
        assert classe.schema_entrada is None and classe.schema_saida is None, (
            f"{classe.__name__} ganhou schema: tire '{fabrica}' de PENDENTES e registre em ESPERADOS."
        )


def test_base_intermediaria_tem_os_schemas_das_filhas():
    for base in BASES_INTERMEDIARIAS:
        filhas = [classe for classe in ESPERADOS if issubclass(classe, base)]
        assert filhas, f"{base.__name__} não tem filha registrada"
        for filha in filhas:
            assert filha.schema_entrada is base.schema_entrada
            assert filha.schema_saida is base.schema_saida


def _schemas_definidos(base: type) -> set[type]:
    """Subclasses de ``base`` definidas nos módulos de raspe.schemas, fora de raspe.schemas.base.

    As bases e os mixins moram em ``raspe.schemas.base``; os schemas concretos,
    nos módulos por raspador. A varredura lê os módulos, e não ``__all__``, para
    pegar também o schema que alguém esqueceu de exportar.
    """
    encontrados: set[type] = set()
    for info in pkgutil.iter_modules(raspe.schemas.__path__):
        modulo = importlib.import_module(f"raspe.schemas.{info.name}")
        for _, classe in inspect.getmembers(modulo, inspect.isclass):
            if issubclass(classe, base) and classe.__module__ == modulo.__name__ != "raspe.schemas.base":
                encontrados.add(classe)
    return encontrados


def test_todo_schema_do_pacote_tem_raspador():
    """Schema concreto sem raspador é código morto que a documentação mostraria."""
    assert _schemas_definidos(InputBase) == {registro.entrada for registro in ESPERADOS.values()}
    assert _schemas_definidos(OutputBase) == {registro.saida for registro in ESPERADOS.values()}
