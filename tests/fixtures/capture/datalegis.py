"""Script ad-hoc para capturar samples dos raspadores Datalegis (ANS e ANVISA).

Como executar (abre o Chromium do Playwright e faz requisições reais, fora
do CI), a partir da raiz do repositório:

    uv run python -m tests.fixtures.capture.datalegis
    uv run python -m tests.fixtures.capture.datalegis --saida /tmp/captura-datalegis

Os raspadores com navegador não passam por ``capturar_cenarios``, que
repete as requisições HTTP de um ``BaseScraper``. Aqui o raspador real faz
a busca no navegador, e o HTML da página de resultados é gravado no momento
em que ``_encontrar_total_paginas`` a lê, antes do teste de busca vazia, e
passa por ``enxugar_html`` (sem ``<script>`` e ``<style>``).

Cenários:

* ``acesso_negado.html``: o ANSLegis recusando o módulo público
  ("URL inválida. Acesse o sistema novamente"), como em 15/11/2026.
* ``no_results.html``: busca sem resultados no AnvisaLegis
  ("Nenhum ato encontrado para a pesquisa efetuada").
"""

from pathlib import Path

from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.datalegis import ScraperDatalegis
from tests.fixtures.capture._util import enxugar_html, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "datalegis" / "samples" / "raspar"

CENARIOS: tuple[tuple[str, type[ScraperDatalegis], str], ...] = (
    ("acesso_negado.html", ScraperANS, "doença rara"),
    ("no_results.html", ScraperANVISA, "termoextremamenteimprovavelxyz"),
)


def _capturar(saida: Path, arquivo: str, classe: type[ScraperDatalegis], pesquisa: str) -> None:
    """Faz a busca com o raspador real e grava a página que ``_encontrar_total_paginas`` lê."""
    scraper = classe(debug=False)
    contar = scraper._encontrar_total_paginas

    async def _gravar_e_contar() -> int:
        (saida / arquivo).write_bytes(enxugar_html((await scraper._obter_html()).encode()))
        return await contar()

    scraper._encontrar_total_paginas = _gravar_e_contar  # type: ignore[method-assign]
    try:
        print(f"{arquivo}: {len(scraper.raspar(pesquisa=pesquisa))} linhas")
    except Exception as e:  # pylint: disable=broad-except
        print(f"{arquivo}: {type(e).__name__}: {e}")


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    saida.mkdir(parents=True, exist_ok=True)
    for cenario in CENARIOS:
        _capturar(saida, *cenario)


if __name__ == "__main__":
    main()
