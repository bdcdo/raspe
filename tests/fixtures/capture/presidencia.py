"""Script ad-hoc para capturar samples do scraper Presidência.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.presidencia
    uv run python -m tests.fixtures.capture.presidencia --saida /tmp/captura-presidencia

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/presidencia/samples/raspar/`` e sobrescrevem os commitados. Para
comparar o site atual com os samples sem tocá-los, passe uma pasta de
saída fora do repositório.

Notas operacionais:

* As requisições saem da sessão do próprio ``ScraperPresidencia``, que
  desativa a verificação SSL (o servidor tem cadeia de certificados
  incompleta) e manda os headers do AJAX (``X-Requested-With``,
  ``Origin``, ``Referer``).
* A API é POST com payload ``application/x-www-form-urlencoded``; a
  página 1 do raspe vira ``posicao=0`` e a página 2, ``posicao=10``.
* O termo de ``single_page`` e o de ``no_results`` dependem do acervo do
  dia. A linha impressa por cenário traz o ``_find_n_pags`` da resposta:
  se ``single_page`` não der 1 ou ``no_results`` não der 0, troque o termo.
"""

import argparse
from pathlib import Path

from raspe.scrapers.presidencia import ScraperPresidencia
from tests.fixtures.capture._util import capturar_cenarios

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "presidencia" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas de 10; a single_page, de uma
# só; a no_results, de zero resultados. O termo sem resultado não leva
# dígitos: a busca casa cada palavra em separado, e "123" sozinho acha os
# atos de número 123.
CENARIOS = (
    ("page_01.html", {"pesquisa": "telemedicina"}, 1),
    ("page_02.html", {"pesquisa": "telemedicina"}, 2),
    ("single_page.html", {"pesquisa": "fenilcetonúria"}, 1),
    ("no_results.html", {"pesquisa": "termoextremamenteimprovavelxyz"}, 1),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados da Presidência)",
    )
    capturar_cenarios(ScraperPresidencia(), CENARIOS, parser.parse_args().saida)


if __name__ == "__main__":
    main()
