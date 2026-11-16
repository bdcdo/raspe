"""Script ad-hoc para capturar samples do scraper Câmara dos Deputados.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.camara
    saida=$(mktemp -d)
    uv run python -m tests.fixtures.capture.camara --saida "$saida"

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, o sample vai para
``tests/camara/samples/raspar/`` e sobrescreve o commitado.

Captura só ``no_results.html`` (busca real sem resultados, enxuta por
``enxugar_html``). Os demais samples de ``tests/camara/samples/raspar/``
foram construídos à mão replicando a estrutura do portal.
"""

from pathlib import Path

from raspe.scrapers.camara import ScraperCamaraDeputados
from tests.fixtures.capture._util import capturar_cenarios, enxugar_html, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "camara" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe).
CENARIOS = (("no_results.html", {"pesquisa": "xqzwvkjh"}, 1),)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    capturar_cenarios(ScraperCamaraDeputados(debug=False), CENARIOS, saida, enxugar=enxugar_html)


if __name__ == "__main__":
    main()
