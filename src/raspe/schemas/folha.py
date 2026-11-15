"""Schemas de ``raspe.folha().raspar()``: busca de notícias da Folha de S.Paulo."""

from typing import Literal

from pydantic import Field

from .base import IntervaloDatasMixin, OutputBase, PaginasMixin, PesquisaObrigatoriaMixin

SiteFolha = Literal["todos", "online", "jornal"]


class InputFolha(PaginasMixin, IntervaloDatasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperFolha.raspar()``."""

    site: SiteFolha = Field(
        default="todos",
        description="Onde buscar: `todos`, `online` (site) ou `jornal` (edição impressa).",
        examples=["online"],
    )


class OutputFolha(OutputBase):
    """Notícias da busca da Folha de S.Paulo.

    Campo que a notícia não traz chega como `N/A`.
    """

    link: str = Field(
        description="Endereço da notícia.",
        examples=[
            "https://www1.folha.uol.com.br/equilibrioesaude/2026/08/"
            "anvisa-aprova-novo-remedio-para-distrofia-muscular-de-duchenne.shtml"
        ],
    )
    titulo: str = Field(
        description="Título da notícia.",
        examples=["Anvisa aprova novo remédio para distrofia muscular de Duchenne"],
    )
    resumo: str = Field(
        description="Resumo que a busca mostra abaixo do título.",
        examples=[
            "Em 2024, a Anvisa também aprovou o Elevidys, uma terapia gênica para o tratamento "
            "da distrofia muscular de Duchenne. ..."
        ],
    )
    data: str = Field(
        description="Data e hora de publicação, como a busca as mostra.", examples=["13.ago.2026 às 14h20"]
    )
