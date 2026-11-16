"""Script ad-hoc para capturar samples do scraper CAPES.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.capes
    saida=$(mktemp -d)
    uv run python -m tests.fixtures.capture.capes --saida "$saida"

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples são salvos em
``tests/capes/samples/raspar/`` e sobrescrevem os commitados; devem ser
re-commitados quando o HTML do Portal de Periódicos da CAPES mudar.

As requisições saem da sessão e da query do próprio ``ScraperCapes``.

Cenários capturados:

- ``page_01.html`` e ``page_02.html`` — páginas 1 e 2 da busca
  ``natjus OR nat-jus`` (41 resultados em 15/11/2026: 30 + 11). Termo
  escolhido por dar duas páginas pequenas o bastante para o limite de
  500 KB do hook ``check-added-large-files``, sem corte.
- ``single_page.html`` — busca ``natjus saude judicializacao`` (17
  resultados em 15/11/2026, 1 página). Se passar de 30 resultados ou
  zerar, troque por outro termo restritivo.
- ``no_results.html`` — termo absurdo, sem paginação.
"""

from pathlib import Path

from raspe.scrapers.capes import ScraperCapes
from tests.fixtures.capture._util import capturar_cenarios, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "capes" / "samples" / "raspar"

TERMO_PAGINADO = "natjus OR nat-jus"

# (arquivo de saída, parâmetros de raspar, página do raspe)
CENARIOS = (
    ("page_01.html", {"pesquisa": TERMO_PAGINADO}, 1),
    ("page_02.html", {"pesquisa": TERMO_PAGINADO}, 2),
    ("single_page.html", {"pesquisa": "natjus saude judicializacao"}, 1),
    ("no_results.html", {"pesquisa": "termo_inexistente_xyz12345abc"}, 1),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    capturar_cenarios(ScraperCapes(debug=False), CENARIOS, saida)


if __name__ == "__main__":
    main()
