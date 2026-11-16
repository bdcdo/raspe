"""``capturar_paginas_lidas`` falha sozinho quando a busca não dá o que o cenário espera.

Sem a conferência, um ``no_results`` que trouxe linhas, ou um acesso recusado no
lugar da busca vazia, virava sample, e só a saída impressa mostrava o engano.
"""

import asyncio

import pytest

from raspe.exceptions import ScraperError
from tests.fixtures.capture._util import capturar_paginas_lidas


class _RaspadorFalso:
    """Lê ``paginas`` pelo ``_obter_html`` e devolve ``linhas`` linhas, ou levanta ``erro``."""

    def __init__(self, paginas: list[str], linhas: int = 0, erro: ScraperError | None = None):
        self._paginas = iter(paginas)
        self._n_paginas = len(paginas)
        self._linhas = linhas
        self._erro = erro

    async def _obter_html(self) -> str:
        return next(self._paginas)

    def raspar(self, pesquisa: str) -> list[int]:
        for _ in range(self._n_paginas):
            asyncio.run(self._obter_html())
        if self._erro:
            raise self._erro
        return [0] * self._linhas


def _capturar(raspador: _RaspadorFalso, arquivos: tuple[str, ...], saida, espera) -> None:
    capturar_paginas_lidas(raspador, "termo", arquivos, saida, espera)  # type: ignore[arg-type]


def test_grava_as_paginas_salvas_quando_ha_linhas(tmp_path):
    raspador = _RaspadorFalso(["<p>contagem</p>", "<p>um</p>", "<p>dois</p>"], linhas=60)
    _capturar(raspador, ("page_01.html", "page_02.html"), tmp_path, "linhas")
    assert (tmp_path / "page_01.html").read_text(encoding="utf-8") == "<p>um</p>"
    assert (tmp_path / "page_02.html").read_text(encoding="utf-8") == "<p>dois</p>"


def test_grava_a_pagina_da_contagem_quando_o_erro_e_esperado(tmp_path):
    raspador = _RaspadorFalso(["<p>URL inválida</p>"], erro=ScraperError("acesso recusado"))
    _capturar(raspador, ("acesso_negado.html",), tmp_path, "erro")
    assert (tmp_path / "acesso_negado.html").read_text(encoding="utf-8") == "<p>URL inválida</p>"


@pytest.mark.parametrize(
    ("paginas", "linhas", "erro", "espera", "mensagem"),
    [
        (["<p>c</p>", "<p>um</p>"], 3, None, "vazia", "espera 'vazia', e a busca deu 3 linhas"),
        (
            ["<p>URL inválida</p>"], 0, "acesso recusado", "vazia",
            "espera 'vazia', e a busca deu ScraperError: acesso recusado",
        ),
        (["<p>nada</p>"], 0, None, "erro", "espera 'erro', e a busca deu 0 linhas"),
        (["<p>nada</p>"], 0, None, "linhas", "espera 'linhas', e a busca deu 0 linhas"),
    ],
    ids=["no_results_com_linhas", "no_results_com_erro", "erro_que_nao_veio", "typical_vazia"],
)
def test_cenario_que_nao_bate_falha_sem_gravar(paginas, linhas, erro, espera, mensagem, tmp_path):
    raspador = _RaspadorFalso(paginas, linhas, ScraperError(erro) if erro else None)
    with pytest.raises(RuntimeError, match=mensagem):
        _capturar(raspador, ("no_results.html",), tmp_path, espera)
    assert not list(tmp_path.iterdir())
