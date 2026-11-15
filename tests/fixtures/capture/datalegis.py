"""Script ad-hoc para capturar samples dos raspadores Datalegis (ANS e ANVISA).

Como executar (abre o Chromium do Playwright e faz requisições reais, fora
do CI), a partir da raiz do repositório:

    uv run python -m tests.fixtures.capture.datalegis
    uv run python -m tests.fixtures.capture.datalegis --saida /tmp/captura-datalegis

O raspador real faz cada busca no navegador, e o script grava o HTML que ele
lê: as páginas de resultados que ele salva ou, sem resultados, a página que
a contagem lê. O HTML passa por ``enxugar_html`` (sem ``<script>`` e
``<style>``).

Cenários:

* ``page_01.html`` e ``page_02.html``: "doenças raras" no AnvisaLegis, 62
  itens em duas páginas de 50 (15/11/2026).
* ``single_page.html``: "medicamento órfão" no AnvisaLegis, 6 itens.
* ``no_results.html``: busca sem resultados no AnvisaLegis
  ("Nenhum ato encontrado para a pesquisa efetuada").
* ``acesso_negado.html``: o ANSLegis recusando o módulo público
  ("URL inválida. Acesse o sistema novamente"), como em 15/11/2026.
"""

from pathlib import Path

from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.anvisa import ScraperANVISA
from raspe.scrapers.datalegis import ScraperDatalegis
from tests.fixtures.capture._util import capturar_paginas_lidas, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "datalegis" / "samples" / "raspar"

# (raspador, pesquisa, arquivos): um arquivo por página lida.
CENARIOS: tuple[tuple[type[ScraperDatalegis], str, tuple[str, ...]], ...] = (
    (ScraperANVISA, "doenças raras", ("page_01.html", "page_02.html")),
    (ScraperANVISA, "medicamento órfão", ("single_page.html",)),
    (ScraperANVISA, "termoextremamenteimprovavelxyz", ("no_results.html",)),
    (ScraperANS, "doença rara", ("acesso_negado.html",)),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    saida.mkdir(parents=True, exist_ok=True)
    for classe, pesquisa, arquivos in CENARIOS:
        capturar_paginas_lidas(classe(debug=False), pesquisa, arquivos, saida)


if __name__ == "__main__":
    main()
