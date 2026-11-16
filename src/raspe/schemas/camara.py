"""Schema de entrada de ``raspe.camara().raspar()``: legislação federal na busca da Câmara.

O schema de saída ainda não existe; as colunas estão documentadas no README.
"""

from pydantic import Field

from .base import AnoMixin, PaginasMixin, PesquisaOpcionalMixin


class InputCamara(PaginasMixin, AnoMixin, PesquisaOpcionalMixin):
    """Parâmetros de ``ScraperCamaraDeputados.raspar()``."""

    ano: int | None = Field(default=None, description="Ano da norma, com quatro dígitos.", examples=[2023])
    tipo_materia: str = Field(
        default="",
        description="Tipo de norma, escrito como no filtro da busca da Câmara; vazio não filtra.",
        examples=["Lei Ordinária"],
    )
