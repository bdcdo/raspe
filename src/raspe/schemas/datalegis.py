"""Schemas de ``raspe.ans().raspar()`` e ``raspe.anvisa().raspar()``, os portais Datalegis."""

from typing import ClassVar

from pydantic import Field

from .base import OutputBase, PesquisaNavegadorMixin


class InputDatalegis(PesquisaNavegadorMixin):
    """Parâmetros de ``ScraperANS.raspar()`` e ``ScraperANVISA.raspar()``.

    Sem ``paginas``: o raspador percorre todas as páginas até o limite interno.
    """

    aliases_deprecados: ClassVar[dict[str, str]] = {"termo": "pesquisa"}


class OutputDatalegis(OutputBase):
    """Atos normativos dos portais ANSLegis e ANVISALegis."""

    url: str = Field(
        description="Endereço do texto do ato.",
        examples=["https://anslegis.datalegis.net/acao/abrirTextoAto.php?id=12345"],
    )
    titulo: str = Field(description="Tipo e número do ato.", examples=["RESOLUÇÃO NORMATIVA Nº 500/2024"])
    descricao: str | None = Field(
        description="Ementa do ato, ou nulo quando o portal não a traz.",
        examples=["Define diretrizes para cobertura de doenças raras."],
    )
    situacao: str | None = Field(
        description="Situação do ato (vigente, revogado etc.), ou nulo quando o portal não a traz.",
        examples=["Em vigor"],
    )
