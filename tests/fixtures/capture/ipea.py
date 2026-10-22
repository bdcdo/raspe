"""Script ad-hoc para capturar samples do scraper IPEA.

Como executar (faz requisições reais à internet, fora do CI), a partir
da raiz do repositório:

    uv run python -m tests.fixtures.capture.ipea
    uv run python -m tests.fixtures.capture.ipea --saida /tmp/captura-ipea

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/ipea/samples/raspar/`` e sobrescrevem os commitados. Para
comparar o site atual com os samples sem tocá-los, passe uma pasta de
saída fora do repositório.

Notas operacionais:

* As requisições saem da sessão e da query do próprio ``ScraperIpea``
  (headers de navegador, ``palavra_chave``, ``pagina``).
* Antes de gravar, o script esvazia os ``<select>`` do formulário de
  busca (ver ``_esvaziar_selects``). O resto da página fica como o site
  mandou.
* O termo de ``single_page`` e o de ``no_results`` dependem do acervo do
  dia. A linha impressa por cenário traz o ``_find_n_pags`` da resposta:
  se ``single_page`` não der 1 ou ``no_results`` não der 0, troque o termo.
"""

import argparse
import re
from pathlib import Path

from raspe.scrapers.ipea import ScraperIpea
from tests.fixtures.capture._util import capturar_cenarios

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "ipea" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas de 10; a single_page, de uma
# só; a no_results, de zero resultados.
CENARIOS = (
    ("page_01.html", {"pesquisa": "renda básica"}, 1),
    ("page_02.html", {"pesquisa": "renda básica"}, 2),
    ("single_page.html", {"pesquisa": "telemedicina"}, 1),
    ("no_results.html", {"pesquisa": "termoextremamenteimprovavelxyz"}, 1),
)


def _esvaziar_selects(html: bytes) -> bytes:
    """Esvazia os ``<select>`` do formulário de busca.

    A lista de autores do formulário tem milhares de opções e leva cada
    página a mais de 2 MB, acima do limite de 500 KB do hook
    ``check-added-large-files``. O scraper não lê o formulário: a contagem
    vem de ``div.col.clearfix`` e as publicações de ``div.lista-publicacoes``,
    que ficam intactas, e o parse da página enxugada é igual ao da original.

    Args:
        html: Body cru da resposta.

    Returns:
        O mesmo HTML, com cada ``<select>`` vazio.
    """
    return re.sub(rb"(<select\b[^>]*>).*?(</select>)", rb"\1\2", html, flags=re.S)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados do IPEA)",
    )
    capturar_cenarios(ScraperIpea(), CENARIOS, parser.parse_args().saida, enxugar=_esvaziar_selects)


if __name__ == "__main__":
    main()
