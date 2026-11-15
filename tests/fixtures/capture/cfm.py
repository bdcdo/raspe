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

Os samples ``page_01``, ``page_02`` e ``single_page`` commitados foram
construídos à mão replicando a estrutura do portal (``"N registros
encontrados"``, ``div.pt-3`` com ``"Mostrando página X de Y"`` e
``div#resultsNormas > article``); o ``no_results`` é uma busca real. Este
script só é necessário se algum teste de contrato começar a falhar por
mudança real no site. O portal do CFM costuma demorar a responder, por
isso o timeout de leitura maior.

As requisições saem da sessão e da query do próprio ``ScraperCFM``
(headers, ``tipo[0..4]``, ``pagina``), para que o sample reflita o que o
scraper envia em produção. O fragmento ``#resultado`` de ``api_base`` não
chega ao servidor: a linha de requisição HTTP leva só o caminho e a query.
"""

from pathlib import Path

from raspe.scrapers.cfm import ScraperCFM
from tests.fixtures.capture._util import capturar_cenarios, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "cfm" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas; a single_page, de uma só; a
# no_results, de zero registros.
CENARIOS = (
    ("page_01.html", {"pesquisa": "publicidade médica"}, 1),
    ("page_02.html", {"pesquisa": "publicidade médica"}, 2),
    ("single_page.html", {"pesquisa": "medicamento órfão"}, 1),
    ("no_results.html", {"pesquisa": "termoextremamenteimprovavelxyz"}, 1),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    scraper = ScraperCFM(debug=False)
    scraper.timeout = (20, 120)
    capturar_cenarios(scraper, CENARIOS, saida)


if __name__ == "__main__":
    main()
