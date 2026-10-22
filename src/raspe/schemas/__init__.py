"""Schemas pydantic de entrada e saída de ``raspar()``, um módulo por raspador.

O schema de entrada (``Input<Raspador>``) lista os parâmetros que ``raspar()``
aceita; o de saída (``Output<Raspador>``), as colunas do DataFrame que ele
devolve. Cada raspador aponta para os seus nos atributos de classe
``schema_entrada`` e ``schema_saida``. ``docs/colunas.md`` é gerado a partir dos
schemas de saída por :mod:`raspe.schemas.documentacao`.
"""

from .base import (
    AnoMixin,
    InputBase,
    IntervaloDatasMixin,
    OutputBase,
    PaginasMixin,
    PesquisaNavegadorMixin,
    PesquisaObrigatoriaMixin,
    PesquisaOpcionalMixin,
    conferir_saida,
    descrever_tipo,
    validar_entrada,
)
from .capes import InputCapes, OutputCapes
from .cfm import InputCFM, OutputCFM
from .datalegis import InputDatalegis, OutputDatalegis
from .folha import InputFolha, OutputFolha
from .ipea import InputIpea, OutputIpea
from .nyt import InputNYT, OutputNYT
from .presidencia import InputPresidencia, OutputPresidencia
from .saudelegis import InputSaudeLegis, OutputSaudeLegis

__all__ = [
    "AnoMixin",
    "InputBase",
    "InputCFM",
    "InputCapes",
    "InputDatalegis",
    "InputFolha",
    "InputIpea",
    "InputNYT",
    "InputPresidencia",
    "InputSaudeLegis",
    "IntervaloDatasMixin",
    "OutputBase",
    "OutputCFM",
    "OutputCapes",
    "OutputDatalegis",
    "OutputFolha",
    "OutputIpea",
    "OutputNYT",
    "OutputPresidencia",
    "OutputSaudeLegis",
    "PaginasMixin",
    "PesquisaNavegadorMixin",
    "PesquisaObrigatoriaMixin",
    "PesquisaOpcionalMixin",
    "conferir_saida",
    "descrever_tipo",
    "validar_entrada",
]
