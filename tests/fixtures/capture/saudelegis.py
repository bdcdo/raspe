"""Script ad-hoc para capturar samples do raspador SaudeLegis.

Como executar (abre o Chromium do Playwright e faz requisições reais, fora
do CI), a partir da raiz do repositório:

    uv run python -m tests.fixtures.capture.saudelegis
    uv run python -m tests.fixtures.capture.saudelegis --saida /tmp/captura-saudelegis

O raspador real faz cada busca no navegador, e o script grava o HTML que ele
lê: as páginas de resultados que ele salva ou, na busca sem resultados, a
página que a contagem lê. O HTML passa por ``enxugar_html`` (sem
``<script>`` e ``<style>``).
"""

from pathlib import Path

from raspe.scrapers.saudelegis import ScraperSaudeLegis
from tests.fixtures.capture._util import capturar_paginas_lidas, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "saudelegis" / "samples" / "raspar"

# (pesquisa, arquivos): um arquivo por página. A typical tem duas páginas; a
# single_page, uma; a no_results, nenhuma.
CENARIOS = (
    ("doença rara", ("page_01.html", "page_02.html")),
    ("talidomida", ("single_page.html",)),
    ("termoextremamenteimprovavelxyz", ("no_results.html",)),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    saida.mkdir(parents=True, exist_ok=True)
    for pesquisa, arquivos in CENARIOS:
        capturar_paginas_lidas(ScraperSaudeLegis(debug=False), pesquisa, arquivos, saida)


if __name__ == "__main__":
    main()
