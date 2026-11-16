"""Script ad-hoc para capturar samples do scraper de proposições da Câmara dos Deputados.

Como executar (faz requisições reais à API de Dados Abertos, fora do CI),
a partir da raiz do repositório:

    uv run python -m tests.fixtures.capture.camara_proposicoes
    saida=$(mktemp -d)
    uv run python -m tests.fixtures.capture.camara_proposicoes --saida "$saida"

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/camara_proposicoes/samples/raspar/`` e sobrescrevem os commitados.

As requisições saem da sessão e da query do próprio ``ScraperCamaraProposicoes``.

O sample guarda só o corpo da resposta. A contagem de resultados vem no
header ``X-Total-Count``, que o contrato em
``tests/camara_proposicoes/test_raspar_contract.py`` repete à mão: ao
recapturar, confira o ``_find_n_pags`` impresso por cenário e atualize os
totais do contrato.

Cenários capturados (contagens de 16/11/2026):

- ``page_01.json`` e ``page_02.json`` — páginas 1 e 2 da busca
  ``doença rara`` em toda a base (178 resultados: 100 + 78).
- ``single_page.json`` — busca ``telemedicina`` com ``ano=2020`` (9
  resultados, 1 página).
- ``no_results.json`` — termo absurdo, ``dados`` vazio.
"""

from pathlib import Path

from raspe.scrapers.camara_proposicoes import ScraperCamaraProposicoes
from tests.fixtures.capture._util import capturar_cenarios, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "camara_proposicoes" / "samples" / "raspar"

TERMO_PAGINADO = "doença rara"

# (arquivo de saída, parâmetros de raspar, página do raspe)
CENARIOS = (
    ("page_01.json", {"pesquisa": TERMO_PAGINADO}, 1),
    ("page_02.json", {"pesquisa": TERMO_PAGINADO}, 2),
    ("single_page.json", {"pesquisa": "telemedicina", "ano": 2020}, 1),
    ("no_results.json", {"pesquisa": "termoinexistentexyz123"}, 1),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    capturar_cenarios(ScraperCamaraProposicoes(debug=False), CENARIOS, saida)


if __name__ == "__main__":
    main()
