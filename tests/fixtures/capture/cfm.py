"""Script ad-hoc para capturar samples do scraper CFM.

Como executar (faz requisições reais à internet — fora do CI):

    cd /caminho/para/raspe
    uv run python tests/fixtures/capture/cfm.py

Captura só ``no_results.html`` (busca real sem resultados, enxuta por
``dump_html_enxuto``). Os demais samples de ``tests/cfm/samples/raspar/``
foram construídos à mão replicando a estrutura do portal. O portal do CFM
costuma demorar a responder, por isso o timeout de leitura maior.
"""

from pathlib import Path

from raspe.scrapers.cfm import ScraperCFM
from tests.fixtures.capture._util import capturar_busca_vazia as _capturar

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "cfm" / "samples" / "raspar"


def main() -> None:
    raspador = ScraperCFM(debug=False)
    raspador.timeout = (20, 120)
    _capturar(raspador, SAMPLES_DIR / "no_results.html", texto="xqzwvkjh")


if __name__ == "__main__":
    main()
