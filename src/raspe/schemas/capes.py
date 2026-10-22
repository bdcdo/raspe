"""Schemas de ``raspe.capes().raspar()``: metadados do Portal de Periódicos da CAPES."""

from pydantic import Field

from .base import OutputBase, PaginasMixin, PesquisaObrigatoriaMixin


class InputCapes(PaginasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperCapes.raspar()``."""


class OutputCapes(OutputBase):
    """Registros bibliográficos do buscador do Portal de Periódicos da CAPES.

    Campos que o card não traz chegam como texto vazio, não como nulo.
    """

    id: str = Field(description="Identificador do registro, o mesmo do OpenAlex.", examples=["W4387465478"])
    tipo: str = Field(description="Tipo do registro.", examples=["Artigo"])
    titulo: str = Field(
        description="Título do registro.",
        examples=["Judicialização de produtos à base de canabidiol no Brasil: uma análise de 2019 a 2022"],
    )
    link: str = Field(
        description="Endereço da página de detalhes no portal da CAPES.",
        examples=[
            "https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html"
            "?task=detalhes&source=all&id=W4387465478"
        ],
    )
    autores: str = Field(
        description="Autores separados por `; `.",
        examples=["João Paulo Kulczynski Forster; Najwa Dagash; Paula Franciele Da Silva"],
    )
    ano: str = Field(description="Ano de publicação, com quatro dígitos, ou vazio.", examples=["2023"])
    revista: str = Field(description="Periódico em que o registro saiu.", examples=["Cadernos de Saúde Pública"])
    instituicao: str = Field(
        description="Instituição informada no card.",
        examples=["Escola Nacional de Saúde Pública, Fundação Oswaldo Cruz"],
    )
    topicos: str = Field(
        description="Tópico de pesquisa atribuído ao registro.", examples=["Cannabis and Cannabinoid Research"]
    )
    resumo: str = Field(
        description="Trechos do resumo que o buscador destaca, não o resumo inteiro.",
        # Recorte sem o termo destacado: o espaço em volta do <b> depende de como
        # o parser junta os nós de texto, e o exemplo não deve depender disso.
        examples=["... the Center for Technical Support of the Judiciary"],
    )
    doi: str = Field(description="DOI, sem o prefixo `https://doi.org/`.", examples=["10.1590/0102-311xpt024723"])
    link_editor: str = Field(
        description="Endereço do DOI na editora.", examples=["https://doi.org/10.1590/0102-311xpt024723"]
    )
    acesso_aberto: bool = Field(description="O card traz o selo de acesso aberto.", examples=[True])
    producao_nacional: bool = Field(description="O card traz o selo de produção nacional.", examples=[True])
    revisado_por_pares: bool = Field(description="O card traz o selo de revisão por pares.", examples=[True])
