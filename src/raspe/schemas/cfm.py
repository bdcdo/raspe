"""Schemas de ``raspe.cfm().raspar()``: normas do CFM e dos CRMs."""

from typing import ClassVar

from pydantic import Field

from .base import AnoMixin, OutputBase, PaginasMixin, PesquisaOpcionalMixin


class InputCFM(PaginasMixin, AnoMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperCFM.raspar()``."""

    aliases_deprecados: ClassVar[dict[str, str]] = {"texto": "pesquisa"}

    uf: str = Field(default="", description="Sigla da UF do CRM; vazio busca em todos.", examples=["DF"])
    revogada: str = Field(
        default="", description="Filtro de revogação repassado ao portal; vazio não filtra.", examples=["N"]
    )
    numero: str = Field(default="", description="Número da norma.", examples=["2350"])
    ano: int | None = Field(default=None, description="Ano da norma.", examples=[2023])


class OutputCFM(OutputBase):
    """Normas do Conselho Federal de Medicina e dos Conselhos Regionais.

    Campos que o card não traz chegam como texto vazio.
    """

    tipo: str = Field(
        description="Tipo da norma (Resolução, Parecer, Emenda, Norma ou Decisão).", examples=["Resolução"]
    )
    uf: str = Field(description="UF do conselho que emitiu a norma.", examples=["DF"])
    numero_ano: str = Field(description="Número e ano da norma, como `número/ano`.", examples=["2350/2023"])
    situacao: str = Field(description="Situação da norma.", examples=["Em vigor"])
    ementa: str = Field(
        description="Ementa da norma.", examples=["Define diretrizes para atendimento de doenças raras no SUS."]
    )
    link: str = Field(
        description="Endereço do texto da norma, como o portal o devolve.", examples=["/normas/2350-2023.pdf"]
    )
