"""Schemas de ``raspe.nyt().raspar()``: Article Search API do New York Times."""

from typing import ClassVar, Literal

from pydantic import Field

from .base import AnoMixin, IntervaloDatasMixin, OutputBase, PaginasMixin, PesquisaOpcionalMixin


class InputNYT(PaginasMixin, AnoMixin, IntervaloDatasMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperNYT.raspar()``."""

    aliases_deprecados: ClassVar[dict[str, str]] = {"texto": "pesquisa"}

    ano: int | None = Field(
        default=None,
        description=(
            "Ano de publicação. Preenche `data_inicio` com 1º de janeiro e `data_fim` "
            "com 31 de dezembro quando elas não vêm."
        ),
        examples=[2024],
    )
    sort: Literal["newest", "oldest", "relevance", "best"] = Field(
        default="newest", description="Ordenação dos resultados na API.", examples=["newest"]
    )
    filtro: str = Field(
        default="",
        description="Filtro em sintaxe Lucene, enviado como `fq` à API.",
        examples=['section.name:"Politics"'],
    )


class OutputNYT(OutputBase):
    """Artigos da Article Search API do New York Times."""

    titulo: str = Field(description="Manchete principal.", examples=["Supreme Court Ruling on Climate Policy"])
    url: str = Field(
        description="Endereço do artigo.", examples=["https://www.nytimes.com/2024/01/15/climate-ruling.html"]
    )
    data_publicacao: str = Field(
        description="Data e hora de publicação, em ISO 8601, como a API devolve.",
        examples=["2024-01-15T14:00:00+0000"],
    )
    secao: str = Field(description="Seção do jornal.", examples=["U.S."])
    desk: str = Field(description="Editoria responsável.", examples=["National"])
    tipo: str = Field(description="Tipo de material.", examples=["News"])
    resumo: str = Field(
        description="Trecho do artigo que a API devolve (`snippet`).",
        examples=["The court ruled 6-3 in favor of new climate regulations."],
    )
    autor: str = Field(description="Assinatura do artigo.", examples=["By Jane Doe"])
    palavras: int = Field(description="Número de palavras do artigo.", examples=[1200])
    imagem_url: str = Field(
        description="Endereço da imagem principal, ou vazio sem imagem.",
        examples=["https://www.nytimes.com/images/2024/01/15/climate.jpg"],
    )
