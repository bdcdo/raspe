"""Schemas de ``raspe.ipea().raspar()``: publicações do IPEA."""

from pydantic import Field

from .base import OutputBase, PaginasMixin, PesquisaObrigatoriaMixin


class InputIpea(PaginasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperIpea.raspar()``."""


class OutputIpea(OutputBase):
    """Publicações da central de conteúdo do IPEA."""

    titulo: str = Field(description="Título da publicação.", examples=["Texto para Discussão 2900"])
    link: str = Field(
        description="Endereço da publicação no portal do IPEA.",
        examples=["https://www.ipea.gov.br/portal/publicacao-1.html"],
    )
    autores: str = Field(description="Autores, como o portal os lista.", examples=["João da Silva; Maria Souza"])
    data: str = Field(description="Data de publicação por extenso.", examples=["15 de janeiro de 2024"])
    assuntos: str = Field(description="Assuntos, separados por vírgula.", examples=["Economia, Pobreza"])
