"""Schemas de ``raspe.camara_proposicoes().raspar()``: proposições na API de Dados Abertos da Câmara."""

from pydantic import Field

from .base import AnoMixin, IntervaloDatasMixin, OutputBase, PaginasMixin, PesquisaOpcionalMixin


class InputCamaraProposicoes(PaginasMixin, AnoMixin, IntervaloDatasMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperCamaraProposicoes.raspar()``.

    ``data_inicio`` e ``data_fim`` (do mixin) filtram pela data de apresentação da proposição.
    """

    ano: int | None = Field(
        default=None,
        description=(
            "Ano da identificação da proposição (o 2020 de PL 696/2020), com quatro dígitos. Pode não ser o ano "
            "de apresentação, que se filtra com `data_inicio` e `data_fim`."
        ),
        examples=[2020],
    )
    sigla_tipo: str = Field(
        default="",
        description="Sigla do tipo de proposição, como a Câmara a escreve; vazio não filtra.",
        examples=["PL", "PEC"],
    )


class OutputCamaraProposicoes(OutputBase):
    """Proposições da API de Dados Abertos da Câmara dos Deputados (``/proposicoes``)."""

    id: int = Field(description="Identificador da proposição na Câmara.", examples=[2239462])
    uri: str = Field(
        description="Endereço da proposição na API, que devolve os detalhes dela.",
        examples=["https://dadosabertos.camara.leg.br/api/v2/proposicoes/2239462"],
    )
    sigla_tipo: str = Field(description="Sigla do tipo de proposição.", examples=["PL"])
    cod_tipo: int = Field(description="Código numérico do tipo de proposição.", examples=[139])
    numero: int = Field(description="Número da proposição.", examples=[696])
    ano: int = Field(
        description="Ano da identificação da proposição, que pode diferir do ano de `data_apresentacao`.",
        examples=[2020],
    )
    ementa: str = Field(
        description="Ementa da proposição.",
        examples=["Dispõe sobre o uso da telemedicina durante a crise causada pelo coronavírus"],
    )
    data_apresentacao: str = Field(
        description="Data e hora de apresentação, em ISO 8601 sem fuso, como a API devolve.",
        examples=["2020-03-18T10:54"],
    )
