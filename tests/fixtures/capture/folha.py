"""Script ad-hoc para capturar samples do scraper Folha.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.folha
    uv run python -m tests.fixtures.capture.folha --saida /tmp/captura-folha

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/folha/samples/raspar/`` e sobrescrevem os commitados. Para
comparar o site atual com os samples sem tocá-los, passe uma pasta de
saída fora do repositório.

As requisições saem da sessão e da query do próprio ``ScraperFolha``
(``q``, ``site``, ``periodo``, ``sr``); a página 1 do raspe vira ``sr=1``
e a página 2, ``sr=26``. O termo de ``single_page`` e o de
``no_results`` dependem do acervo do dia. A linha impressa por cenário
traz o ``_find_n_pags`` da resposta: se ``single_page`` não der 1 ou
``no_results`` não der 0, troque o termo.
"""

import argparse
from pathlib import Path

from raspe.scrapers.folha import ScraperFolha
from tests.fixtures.capture._util import capturar_cenarios

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "folha" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas de 25; a single_page, de uma
# só; a no_results, de zero resultados.
CENARIOS = (
    ("page_01.html", {"pesquisa": "Elevidys"}, 1),
    ("page_02.html", {"pesquisa": "Elevidys"}, 2),
    ("single_page.html", {"pesquisa": "natjus"}, 1),
    ("no_results.html", {"pesquisa": "termoextremamenteimprovavelxyz"}, 1),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados da Folha)",
    )
    capturar_cenarios(ScraperFolha(), CENARIOS, parser.parse_args().saida)


if __name__ == "__main__":
    main()
