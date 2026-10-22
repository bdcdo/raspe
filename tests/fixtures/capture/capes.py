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

Cenários capturados:

- ``page_01.html`` — busca ``natjus`` (≈20 resultados, 1 página).
- ``page_02.html`` — busca ``saude``, página 2. **Após a captura, abra o
  arquivo e remova manualmente os últimos cards** (``div.col-md-12.br-item``)
  para deixar ~12, ficando abaixo do limite de 500KB do hook
  ``check-added-large-files``. O teste ``test_typical_paginacao``
  espera apenas que page_02 contribua com ao menos 10 cards.
- ``single_page.html`` — busca ``natjus_brasil`` (termo composto pouco
  comum, costuma retornar 1 página). Caso retorne 0 ou >1, troque por
  outro termo restritivo (ex.: ``natjus saude judicializacao``).
- ``no_results.html`` — termo absurdo, sem paginação.
"""

import argparse
from pathlib import Path

import requests

from tests.fixtures.capture._util import attach_capture_hook, dump_response

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "capes" / "samples" / "raspar"
API_URL = "https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html"

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,en-US;q=0.7,en;q=0.3",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
}


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_HEADERS)
    return session


def _get(session: requests.Session, pesquisa: str, page: int = 1) -> requests.Response:
    return session.get(
        API_URL,
        params={
            "q": f"all:contains({pesquisa})",
            "mode": "advanced",
            "source": "all",
            "page": page,
        },
        timeout=60,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados da CAPES)",
    )
    saida: Path = parser.parse_args().saida
    saida.mkdir(parents=True, exist_ok=True)

    # page_01.html — typical primeira página (busca "natjus", ~20 resultados)
    session = _make_session()
    detach = attach_capture_hook(session, saida, prefix="page", extension="html")
    _get(session, "natjus", page=1)
    detach()

    # page_02.html — segunda página de uma busca genérica
    # (busca "saude" gera ~29M resultados; pegamos a página 2 cheia e
    # depois trimamos manualmente para ~12 cards no arquivo). O hook já foi
    # removido acima, então a página 2 é gravada explicitamente.
    resp = _get(session, "saude", page=2)
    dump_response(resp, saida / "page_02.html")

    # single_page.html — termo restritivo que costuma retornar 1 página
    resp = _get(_make_session(), "natjus_brasil", page=1)
    dump_response(resp, saida / "single_page.html")

    # no_results.html — termo absurdo, sem nav.br-pagination
    resp = _get(_make_session(), "termo_inexistente_xyz12345abc", page=1)
    dump_response(resp, saida / "no_results.html")


if __name__ == "__main__":
    main()
