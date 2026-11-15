"""Script ad-hoc para capturar samples do scraper CAPES.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.capes
    uv run python -m tests.fixtures.capture.capes --saida /tmp/captura-capes

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples são salvos em
``tests/capes/samples/raspar/`` e sobrescrevem os commitados; devem ser
re-commitados quando o HTML do Portal de Periódicos da CAPES mudar.

As requisições saem da sessão e da query do próprio ``ScraperCapes``.
A linha impressa por cenário traz o ``_find_n_pags`` da resposta: se
``single_page`` não der 1 ou ``no_results`` não der 0, troque o termo.

Cenários capturados:

- ``page_01.html`` — busca ``natjus`` (≈20 resultados, 1 página).
- ``page_02.html`` — busca ``saude``, página 2, cortada nos primeiros
  ``CARDS_PAGE_02`` cards (``_cortar_cards``) para ficar abaixo do limite
  de 500 KB do hook ``check-added-large-files``. O teste
  ``test_typical_paginacao`` espera que page_02 contribua com ao menos
  10 cards.
- ``single_page.html`` — busca ``natjus saude judicializacao`` (17
  resultados, 1 página, em 15/11/2026; ``natjus_brasil``, o termo
  anterior, passou a não achar nada). Caso retorne 0 ou >1, troque por
  outro termo restritivo.
- ``no_results.html`` — termo absurdo, sem paginação.
"""

import time
from pathlib import Path

from raspe.scrapers.capes import ScraperCapes
from tests.fixtures.capture._util import capturar_cenarios, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "capes" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). Estes vão
# para o disco inteiros; a page_02 tem chamada própria, com corte.
CENARIOS = (
    ("page_01.html", {"pesquisa": "natjus"}, 1),
    ("single_page.html", {"pesquisa": "natjus saude judicializacao"}, 1),
    ("no_results.html", {"pesquisa": "termo_inexistente_xyz12345abc"}, 1),
)
CENARIO_PAGE_02 = ("page_02.html", {"pesquisa": "saude"}, 2)
CARDS_PAGE_02 = 12


def _cortar_cards(html: bytes) -> bytes:
    """Mantém só os primeiros ``CARDS_PAGE_02`` cards da página.

    A página 2 de "saude" traz 30 cards e passa do limite de tamanho do
    repositório. O ``_find_n_pags`` lê a resposta inteira antes do corte.

    Args:
        html: Body cru da resposta.

    Returns:
        A página com os cards além do limite removidos, em UTF-8.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for card in soup.select(ScraperCapes._SELETOR_CARD)[CARDS_PAGE_02:]:
        card.decompose()
    return str(soup).encode("utf-8")


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    scraper = ScraperCapes(debug=False)
    capturar_cenarios(scraper, CENARIOS, saida)
    # Mesmo intervalo que capturar_cenarios põe entre os cenários.
    time.sleep(scraper.sleep_time)
    capturar_cenarios(scraper, [CENARIO_PAGE_02], saida, enxugar=_cortar_cards)


if __name__ == "__main__":
    main()
