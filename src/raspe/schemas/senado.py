"""Schema de entrada de ``raspe.senado().raspar()``: legislação federal na busca do Senado.

O schema de saída ainda não existe; as colunas estão documentadas no README.
"""

from pydantic import Field

from .base import AnoMixin, PaginasMixin, PesquisaOpcionalMixin


class InputSenado(PaginasMixin, AnoMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperSenadoFederal.raspar()``."""

    ano: int | None = Field(default=None, description="Ano da norma, com quatro dígitos.", examples=[2023])
    tipo_materia: str = Field(
        default="",
        description='Tipo de norma, escrito como no filtro da busca do Senado ("sigla - nome"); vazio não filtra.',
        examples=["LEI - Lei"],
    )
