"""Script ad-hoc para capturar samples do scraper CFM.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.cfm
    uv run python -m tests.fixtures.capture.cfm --saida /tmp/captura-cfm

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/cfm/samples/raspar/`` e sobrescrevem os commitados. Para comparar
o site atual com os samples sem tocá-los, passe uma pasta de saída fora
do repositório.

Os samples commitados foram construídos à mão replicando a estrutura do
portal (``"N registros encontrados"``, ``div.pt-3`` com ``"Mostrando
página X de Y"`` e ``div#resultsNormas > article``). Este script só é
necessário se algum teste de contrato começar a falhar por mudança real
no site.

As requisições saem da sessão e da query do próprio ``ScraperCFM``
(headers, ``tipo[0..4]``, ``pagina``), para que o sample reflita o que o
scraper envia em produção. O fragmento ``#resultado`` de ``api_base`` não
chega ao servidor: a linha de requisição HTTP leva só o caminho e a query.
"""

import argparse
from pathlib import Path

from raspe.scrapers.cfm import ScraperCFM
from tests.fixtures.capture._util import capturar_cenarios

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "cfm" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas; a single_page, de uma só; a
# no_results, de zero registros.
CENARIOS = (
    ("page_01.html", {"texto": "publicidade médica"}, 1),
    ("page_02.html", {"texto": "publicidade médica"}, 2),
    ("single_page.html", {"texto": "medicamento órfão"}, 1),
    ("no_results.html", {"texto": "termoextremamenteimprovavelxyz"}, 1),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados do CFM)",
    )
    capturar_cenarios(ScraperCFM(), CENARIOS, parser.parse_args().saida)


if __name__ == "__main__":
    main()
