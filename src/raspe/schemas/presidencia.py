"""Schemas de ``raspe.presidencia().raspar()``: legislação federal da Presidência da República."""

from pydantic import Field

from .base import OutputBase, PaginasMixin, PesquisaObrigatoriaMixin


class InputPresidencia(PaginasMixin, PesquisaObrigatoriaMixin):
    """Parâmetros de ``ScraperPresidencia.raspar()``."""


class OutputPresidencia(OutputBase):
    """Atos da pesquisa de legislação do portal da Presidência da República."""

    nome: str = Field(
        description="Nome do ato, com tipo, número e ano.",
        examples=["Decreto nº 12.725 de 18 de novembro de 2025"],
    )
    link: str = Field(
        description="Endereço do texto do ato, como o portal o devolve.",
        examples=["https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12725.htm"],
    )
    ficha: str = Field(
        description="Endereço da ficha do ato no portal.",
        examples=[
            "https://legislacao.presidencia.gov.br/atos"
            "?tipo=DEC&numero=12725&ano=2025&data=18/11/2025&ato=499cXVU9UNZpWT45a"
        ],
    )
    revogacao: str = Field(
        description="Situação de revogação informada pelo portal.",
        examples=["Não consta revogação expressa"],
    )
    descricao: str = Field(
        description="Ementa do ato.",
        examples=[
            "Aprova a Política Nacional de Defesa, a Estratégia Nacional de Defesa e o Livro Branco de Defesa Nacional."
        ],
    )
