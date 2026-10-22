"""Bases dos schemas pydantic e as funções que ligam os schemas a ``raspar()``.

Cada raspador declara dois schemas:

- **Input** (subclasse de :class:`InputBase`): os parâmetros públicos de
  ``raspar()``. ``extra="forbid"`` faz um kwarg desconhecido virar erro, em vez
  de ser ignorado em silêncio e a busca rodar sem o filtro que o usuário pediu.
- **Output** (subclasse de :class:`OutputBase`): as colunas do DataFrame que
  ``raspar()`` devolve, uma linha por registro.

Os campos com nome canônico (``pesquisa``, ``data_inicio``, ``data_fim``,
``paginas``, ``ano`` e ``termo_busca``) moram nos mixins deste módulo, para que
o tipo e a descrição tenham uma fonte só. ``tests/schemas/test_canonical_types.py``
reprova schema concreto que declare um desses nomes com outro tipo.
"""

import difflib
import inspect
import os
import types
import warnings
from datetime import date
from typing import Any, ClassVar, Literal, Union, get_args, get_origin

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError
from pydantic import field_validator

from raspe.exceptions import ValidationError

# Diretório do pacote ``raspe``, com separador no fim para que um pacote vizinho
# de nome parecido (``raspe_extra``) não seja confundido com ele.
_DIRETORIO_PACOTE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep

_DESCRICAO_PESQUISA = (
    "Termo de busca. Uma lista dispara uma busca por item, e a coluna "
    "`termo_busca` diz de qual item veio cada linha."
)


class InputBase(BaseModel):
    """Base de todo schema de entrada de ``raspar()``.

    Atributos de classe:
        aliases_deprecados: Nomes antigos de parâmetro aceitos por um ciclo de
            versão, mapeados para o nome canônico. O uso emite
            ``DeprecationWarning`` (ver :func:`validar_entrada`).
    """

    # ``arbitrary_types_allowed`` é exigido por ``paginas``, que aceita ``range``,
    # tipo que o pydantic não valida nativamente.
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    aliases_deprecados: ClassVar[dict[str, str]] = {}


class PesquisaObrigatoriaMixin(InputBase):
    """``pesquisa`` obrigatória, para fontes que só buscam por termo."""

    pesquisa: str | list[str] = Field(
        description=_DESCRICAO_PESQUISA,
        examples=["natjus", ["natjus", "saude"]],
    )


class PesquisaOpcionalMixin(InputBase):
    """``pesquisa`` opcional, para fontes que também buscam só por filtros."""

    pesquisa: str | list[str] = Field(
        default="",
        description=_DESCRICAO_PESQUISA + " Vazio busca só pelos demais filtros.",
        examples=["doenças raras", ["doenças raras", "medicamentos órfãos"]],
    )


class PesquisaNavegadorMixin(InputBase):
    """``pesquisa`` de texto único, para os raspadores com navegador.

    Os raspadores com Playwright preenchem um campo de formulário e não
    percorrem listas, por isso o tipo não aceita ``list[str]``.
    """

    pesquisa: str = Field(
        default="",
        description="Termo de busca digitado no formulário do portal. Não aceita lista.",
        examples=["doença rara"],
    )


class PaginasMixin(InputBase):
    """Seleção das páginas de resultado a baixar."""

    # Sem ``examples``: o pydantic serializa os exemplos para JSON ao montar o
    # schema, e ``range`` não tem forma JSON. O exemplo vai na descrição.
    paginas: range | None = Field(
        default=None,
        description=(
            "Páginas de resultado a baixar, como `range`; a primeira página é 1, e "
            "`range(1, 3)` baixa as duas primeiras. Sem valor, baixa todas."
        ),
    )

    @field_validator("paginas")
    @classmethod
    def _validar_paginas(cls, paginas: range | None) -> range | None:
        """Recusa seleções que o paginador não sabe percorrer.

        ``BaseScraper._set_paginas`` corta o ``stop`` no total de páginas, mas
        aceitaria página 0 ou negativa e as mandaria ao servidor como posição
        inválida.
        """
        if paginas is None:
            return paginas
        if paginas.step <= 0:
            raise ValueError("'paginas' não aceita range decrescente.")
        if not paginas:
            raise ValueError("'paginas' não pode ser uma seleção vazia.")
        if paginas.start < 1:
            raise ValueError("'paginas' começa em 1; a página 0 não existe.")
        return paginas


class IntervaloDatasMixin(InputBase):
    """Filtro por período, normalizado depois para ``YYYY-MM-DD``.

    O schema só confere o tipo. A normalização e a checagem de ordem ficam em
    ``AbstractScraper._validar_parametros``, que chama
    :func:`raspe.utils.validar_intervalo_datas` depois deste schema.
    """

    data_inicio: str | date | None = Field(
        default=None,
        description="Data inicial do período, em YYYY-MM-DD, DD/MM/YYYY ou YYYYMMDD.",
        examples=["2024-01-01"],
    )
    data_fim: str | date | None = Field(
        default=None,
        description="Data final do período, em YYYY-MM-DD, DD/MM/YYYY ou YYYYMMDD.",
        examples=["2024-12-31"],
    )


class AnoMixin(InputBase):
    """Filtro por ano. Schemas concretos redeclaram o campo para dizer o que o ano filtra."""

    ano: int | None = Field(default=None, description="Ano.", examples=[2024])


class OutputBase(BaseModel):
    """Base de todo schema de saída: uma linha do DataFrame de ``raspar()``."""

    model_config = ConfigDict(extra="forbid")

    termo_busca: str = Field(
        description=(
            "Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa "
            "busca com lista, o item da lista."
        ),
        examples=["natjus"],
    )

    @classmethod
    def colunas(cls) -> list[str]:
        """Ordem das colunas no DataFrame: as próprias do raspador, depois as da base.

        A ordem dos campos no pydantic põe os da base primeiro; o DataFrame põe
        ``termo_busca`` por último, porque ela é acrescentada depois do parser.

        Returns:
            Lista com o nome das colunas, na ordem em que ``raspar()`` as devolve.
        """
        da_base = list(OutputBase.model_fields)
        proprias = [nome for nome in cls.model_fields if nome not in da_base]
        return proprias + da_base


def _nivel_de_pilha_fora_do_pacote() -> int:
    """Calcula o ``stacklevel`` que atribui um warning ao código de quem usa o raspe.

    O Python só mostra ``DeprecationWarning`` por padrão quando o warning é
    atribuído ao módulo ``__main__`` (ou à célula do notebook). Atribuído a um
    arquivo interno do raspe, ele sumiria. A pilha até aqui varia (``raspar``,
    ``scrape``, raspadores com navegador), por isso o nível é contado subindo
    os frames até o primeiro fora do pacote, como faz o ``skip_file_prefixes``
    do Python 3.12.

    Returns:
        Valor de ``stacklevel`` para o ``warnings.warn`` chamado pela função que
        chamou esta.
    """
    frame = inspect.currentframe()
    # O primeiro frame é o desta função; o seguinte é o de quem vai chamar warn.
    frame = frame.f_back if frame is not None else None
    nivel = 1
    while frame is not None and frame.f_code.co_filename.startswith(_DIRETORIO_PACOTE):
        frame = frame.f_back
        nivel += 1
    return nivel


def _resolver_aliases(schema: type[InputBase], parametros: dict[str, Any]) -> dict[str, Any]:
    """Troca nomes deprecados pelo canônico, avisando com ``DeprecationWarning``.

    Args:
        schema: Schema de entrada com o mapa ``aliases_deprecados``.
        parametros: Kwargs recebidos por ``raspar()``.

    Returns:
        Cópia dos kwargs com os nomes canônicos.

    Raises:
        ValidationError: Se o nome antigo e o canônico vierem juntos.
    """
    resolvidos = dict(parametros)
    for antigo, canonico in schema.aliases_deprecados.items():
        if antigo not in resolvidos:
            continue
        if canonico in resolvidos:
            raise ValidationError(
                f"Não é possível passar '{canonico}' e '{antigo}' ao mesmo tempo. "
                f"Use apenas '{canonico}'."
            )
        resolvidos[canonico] = resolvidos.pop(antigo)
        warnings.warn(
            f"O parâmetro '{antigo}' está descontinuado e será removido. Use '{canonico}'.",
            DeprecationWarning,
            stacklevel=_nivel_de_pilha_fora_do_pacote(),
        )
    return resolvidos


def descrever_tipo(anotacao: Any) -> str:
    """Descreve em português o tipo declarado num campo de schema.

    Serve às mensagens de erro de :func:`validar_entrada` e à tabela de tipos
    de ``docs/colunas.md``.

    Args:
        anotacao: Anotação de tipo do campo (``FieldInfo.annotation``).

    Returns:
        Descrição curta, por exemplo ``"texto ou nulo"``.

    Examples:
        >>> descrever_tipo(str | None)
        'texto ou nulo'
    """
    nomes = {
        str: "texto",
        int: "inteiro",
        bool: "booleano",
        date: "data",
        range: "range",
        type(None): "nulo",
    }
    if anotacao in nomes:
        return nomes[anotacao]
    origem = get_origin(anotacao)
    if origem is Literal:
        return "um de " + ", ".join(repr(valor) for valor in get_args(anotacao))
    if origem is list:
        (item,) = get_args(anotacao)
        return f"lista de {descrever_tipo(item)}s"
    if origem in (Union, types.UnionType):
        return " ou ".join(descrever_tipo(parte) for parte in get_args(anotacao))
    return str(anotacao)


def _sugestao(nome: str, schema: type[InputBase]) -> str:
    """Sugere o parâmetro válido mais parecido com um nome desconhecido."""
    candidatos = {campo: campo for campo in schema.model_fields}
    candidatos.update(schema.aliases_deprecados)
    parecidos = difflib.get_close_matches(nome, list(candidatos), n=1, cutoff=0.7)
    return f" (você quis dizer '{candidatos[parecidos[0]]}'?)" if parecidos else ""


def _mensagem_de_erro(exc: PydanticValidationError, schema: type[InputBase], metodo: str) -> str:
    """Traduz os erros do pydantic para uma mensagem em português, um parâmetro por linha.

    Um campo com união de tipos (``str | list[str]``) gera um erro por variante;
    as linhas se agrupam pelo nome do parâmetro para que ele apareça uma vez.
    """
    por_campo: dict[str, list[Any]] = {}
    for erro in exc.errors():
        por_campo.setdefault(str(erro["loc"][0]), []).append(erro)

    linhas = []
    for campo, erros in por_campo.items():
        tipos = {erro["type"] for erro in erros}
        if "extra_forbidden" in tipos:
            motivo = "parâmetro desconhecido" + _sugestao(campo, schema)
        elif "missing" in tipos:
            motivo = "parâmetro obrigatório ausente"
        elif "value_error" in tipos:
            erro = next(erro for erro in erros if erro["type"] == "value_error")
            motivo = str(erro["ctx"]["error"])
        else:
            esperado = descrever_tipo(schema.model_fields[campo].annotation)
            motivo = f"valor {erros[0]['input']!r} inválido; esperado {esperado}"
        linhas.append(f"  - '{campo}': {motivo}")

    aceitos = ", ".join(schema.model_fields)
    return f"{metodo} recebeu parâmetros inválidos:\n" + "\n".join(linhas) + f"\nParâmetros aceitos: {aceitos}."


def validar_entrada(schema: type[InputBase], parametros: dict[str, Any], metodo: str) -> dict[str, Any]:
    """Valida os kwargs de ``raspar()`` contra o schema de entrada.

    A ordem importa: os aliases deprecados são trocados antes da validação,
    porque ``extra="forbid"`` recusaria o nome antigo.

    Args:
        schema: Schema de entrada do raspador.
        parametros: Kwargs recebidos por ``raspar()``.
        metodo: Nome do método para a mensagem de erro (ex.: ``"ScraperCFM.raspar()"``).

    Returns:
        Todos os campos do schema, com os valores validados e os defaults
        preenchidos. ``pesquisa`` sempre aparece, o que dá a todo raspador a
        coluna ``termo_busca``.

    Raises:
        ValidationError: Se houver parâmetro desconhecido, obrigatório ausente
            ou valor de tipo errado.
    """
    resolvidos = _resolver_aliases(schema, parametros)
    try:
        modelo = schema.model_validate(resolvidos)
    except PydanticValidationError as exc:
        raise ValidationError(_mensagem_de_erro(exc, schema, metodo)) from exc
    return modelo.model_dump()


def conferir_saida(df: pd.DataFrame, schema: type[OutputBase], metodo: str) -> pd.DataFrame:
    """Confere as colunas do DataFrame de ``raspar()`` contra o schema de saída.

    - Sem linhas: devolve um DataFrame vazio com as colunas do schema, para que
      a busca sem resultado tenha a mesma forma da busca com resultado.
    - Com linhas e as colunas do schema: devolve as colunas na ordem do schema.
    - Com linhas e colunas divergentes: emite ``UserWarning`` e devolve os dados
      como vieram. A divergência é defeito do raspe, que a suíte anti-drift
      (``tests/schemas/``) existe para pegar antes do merge; levantar exceção
      aqui jogaria fora uma coleta que pode ter levado horas.

    Args:
        df: DataFrame montado por ``raspar()``.
        schema: Schema de saída do raspador.
        metodo: Nome do método para a mensagem do warning.

    Returns:
        DataFrame conferido.
    """
    colunas = schema.colunas()
    if len(df) == 0:
        return pd.DataFrame(columns=colunas)
    if set(df.columns) == set(colunas):
        return df.reindex(columns=colunas)
    faltando = [coluna for coluna in colunas if coluna not in df.columns]
    sobrando = [coluna for coluna in df.columns if coluna not in colunas]
    warnings.warn(
        f"{metodo} devolveu colunas fora do schema {schema.__name__} "
        f"(faltando: {faltando}; sobrando: {sobrando}). Isso é defeito do raspe; "
        "os dados foram mantidos como vieram.",
        UserWarning,
        stacklevel=_nivel_de_pilha_fora_do_pacote(),
    )
    return df
