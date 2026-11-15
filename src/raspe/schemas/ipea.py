"""Schemas de ``raspe.ipea().raspar()``: publicações do IPEA."""

from pydantic import Field

from .base import OutputBase, PaginasMixin, PesquisaObrigatoriaMixin


class InputIpea(PaginasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperIpea.raspar()``."""


class OutputIpea(OutputBase):
    """Publicações da central de conteúdo do IPEA."""

    titulo: str = Field(
        description="Título da publicação.",
        examples=["Regras do governo brasileiro sobre serviços de telessaúde : revisão integrativa"],
    )
    link: str = Field(
        description="Endereço da publicação no portal do IPEA.",
        examples=["https://www.ipea.gov.br/portal/publicacao-item?id=61d484f0-c674-4e16-a421-3e7a22e842d7"],
    )
    autores: str = Field(
        description="Autores, como o portal os lista; vazio quando o portal deixa o campo em branco.", examples=[""]
    )
    data: str = Field(
        description="Data de publicação, como o portal a mostra: mês abreviado e ano, ou só o ano.",
        examples=["Jun-2015", "2022"],
    )
    assuntos: str = Field(
        description="Assuntos, cada um uma vez, separados por vírgula.", examples=["Economia da Saúde"]
    )
