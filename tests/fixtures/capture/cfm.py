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
scraper envia em produção. O fragmento ``#resultado`` de ``api_base``
aparece na URL impressa, mas não chega ao servidor: a linha de requisição
HTTP leva só o caminho e a query.
"""

import argparse
import time
from pathlib import Path

from raspe.scrapers.cfm import ScraperCFM
from tests.fixtures.capture._util import dump_response

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "cfm" / "samples" / "raspar"

# (arquivo de saída, termo, página). A busca typical precisa de pelo menos
# duas páginas; a single_page, de uma só; a no_results, de zero registros.
CENARIOS = (
    ("page_01.html", "publicidade médica", 1),
    ("page_02.html", "publicidade médica", 2),
    ("single_page.html", "medicamento órfão", 1),
    ("no_results.html", "termoextremamenteimprovavelxyz123", 1),
)


def capturar(saida: Path) -> None:
    """Baixa cada cenário de ``CENARIOS`` e grava o HTML cru em ``saida``.

    Args:
        saida: Pasta onde os arquivos serão gravados (criada se preciso).
    """
    saida.mkdir(parents=True, exist_ok=True)
    scraper = ScraperCFM()

    for i, (arquivo, termo, pagina) in enumerate(CENARIOS):
        if i:
            # Mesmo intervalo que o scraper usa entre páginas em produção.
            time.sleep(scraper.sleep_time)
        query = scraper._set_query_atual(scraper._set_query_base(texto=termo), pagina)
        resp = scraper.session.get(scraper.api_base, params=query, timeout=scraper.timeout)
        resp.raise_for_status()
        dump_response(resp, saida / arquivo)
        print(f"{arquivo}: HTTP {resp.status_code}, {len(resp.content)} bytes, {resp.url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados do CFM)",
    )
    capturar(parser.parse_args().saida)


if __name__ == "__main__":
    main()
