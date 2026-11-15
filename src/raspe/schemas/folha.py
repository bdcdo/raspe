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
        examples=["https://www1.folha.uol.com.br/cotidiano/2024/01/noticia-1.shtml"],
    )
    titulo: str = Field(description="Título da notícia.", examples=["Educação pública avança em 2024"])
    resumo: str = Field(
        description="Resumo que a busca mostra abaixo do título.",
        examples=["Pesquisa mostra ampliação de vagas no ensino médio em todo o país."],
    )
    data: str = Field(
        description="Data e hora de publicação, como a busca as mostra.", examples=["15.jan.2024 às 10h00"]
    )
