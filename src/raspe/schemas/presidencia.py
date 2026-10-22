"""Schemas de ``raspe.presidencia().raspar()``: legislação federal da Presidência da República."""

from pydantic import Field

from .base import OutputBase, PaginasMixin, PesquisaObrigatoriaMixin


class InputPresidencia(PaginasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperPresidencia.raspar()``."""


class OutputPresidencia(OutputBase):
    """Atos da pesquisa de legislação do portal da Presidência da República."""

    nome: str = Field(description="Nome do ato, com tipo, número e ano.", examples=["Decreto nº 11.000/2024"])
    link: str = Field(
        description="Endereço do texto do ato, como o portal o devolve.",
        examples=["/atos/decreto-11000-2024.html"],
    )
    ficha: str = Field(
        description="Endereço da ficha do ato no portal.",
        examples=["/fichas/decreto-11000-2024.html"],
    )
    revogacao: str = Field(description="Situação de revogação informada pelo portal.", examples=["Sem revogação"])
    descricao: str = Field(description="Ementa do ato.", examples=["Dispõe sobre política ambiental nacional."])
