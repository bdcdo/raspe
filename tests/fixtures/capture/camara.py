"""Script ad-hoc para capturar samples do scraper Câmara dos Deputados.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.camara

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``.

Captura só ``no_results.html`` (busca real sem resultados, enxuta por
``dump_html_enxuto``). Os demais samples de ``tests/camara/samples/raspar/``
foram construídos à mão replicando a estrutura do portal.
"""

from pathlib import Path

from raspe.scrapers.camara import ScraperCamaraDeputados
from tests.fixtures.capture._util import capturar_busca_vazia as _capturar

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "camara" / "samples" / "raspar"


def main() -> None:
    raspador = ScraperCamaraDeputados(debug=False)
    _capturar(raspador, SAMPLES_DIR / "no_results.html", pesquisa="xqzwvkjh")


if __name__ == "__main__":
    main()
