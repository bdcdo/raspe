"""Schemas de ``raspe.saudelegis().raspar()``: normas do portal SaudeLegis."""

from typing import ClassVar

from pydantic import Field

from .base import OutputBase, PesquisaNavegadorMixin


class InputSaudeLegis(PesquisaNavegadorMixin):
    """Parâmetros de ``ScraperSaudeLegis.raspar()``.

    Sem ``paginas``: o raspador percorre todas as páginas até o limite interno.
    """

    aliases_deprecados: ClassVar[dict[str, str]] = {"assunto": "pesquisa"}


class OutputSaudeLegis(OutputBase):
    """Normas do portal SaudeLegis do Ministério da Saúde."""

    tipo_norma: str = Field(description="Tipo da norma.", examples=["PORTARIA"])
    numero: str = Field(description="Número e ano da norma.", examples=["123/2024"])
    data_pub: str = Field(description="Data de publicação, em DD/MM/AAAA.", examples=["15/01/2024"])
    origem: str = Field(description="Órgão de origem.", examples=["MS/GM"])
    ementa: str = Field(
        description="Ementa da norma.", examples=["Define diretrizes para atendimento de doenças raras."]
    )
    link_url: str = Field(
        description="Endereço do texto completo, ou vazio quando o portal não o traz.",
        examples=["/doc/portaria-123-2024.pdf"],
    )
