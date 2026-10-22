"""Script ad-hoc para capturar samples do scraper NYT.

Como executar (faz requisições reais à Article Search API, fora do CI),
a partir da raiz do repositório:

    export NYT_API_KEY="sua-chave"
    uv run python -m tests.fixtures.capture.nyt
    uv run python -m tests.fixtures.capture.nyt --saida /tmp/captura-nyt

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/nyt/samples/raspar/`` e sobrescrevem os commitados.

Os samples commitados são JSON sintético que replica a estrutura da API
(``response.docs[]`` e ``response.meta.hits``). Este script só é
necessário se algum teste de contrato começar a falhar por mudança real
na API.

Notas operacionais:

* Sem ``NYT_API_KEY`` no ambiente, ``ScraperNYT`` levanta ``APIKeyError``
  antes de qualquer requisição.
* A chave vai na query string (``api-key``). Por isso o script nunca
  imprime ``resp.url``, e só o body da resposta vai para o disco.
* A API limita a 5 requisições por minuto; o script espera
  ``ScraperNYT.sleep_time`` segundos entre uma requisição e a seguinte.
* As requisições saem da query do próprio ``ScraperNYT``, com a página
  convertida por ``_set_query_atual``: a página 1 do raspe vira
  ``page=0`` na API.
* O termo de ``single_page`` e o de ``no_results`` dependem do acervo do
  dia. O script avisa quando o número de hits não cabe no cenário, e aí
  é preciso trocar o termo ou o intervalo de datas.
"""

import argparse
import time
from pathlib import Path
from typing import Any

import requests

from raspe.scrapers.nyt import ScraperNYT
from tests.fixtures.capture._util import dump_response

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "nyt" / "samples" / "raspar"

# (arquivo de saída, parâmetros de busca, página do raspe, faixa de hits
# aceita). A busca typical precisa de pelo menos duas páginas de 10.
CENARIOS: tuple[tuple[str, dict[str, Any], int, range], ...] = (
    ("page_01.json", {"texto": "Brazil"}, 1, range(11, 10**9)),
    ("page_02.json", {"texto": "Brazil"}, 2, range(11, 10**9)),
    (
        "single_page.json",
        {"texto": "Supremo Tribunal Federal", "data_inicio": "2024-01-01", "data_fim": "2024-01-31"},
        1,
        range(1, 11),
    ),
    ("no_results.json", {"texto": "termoextremamenteimprovavelxyz123"}, 1, range(0, 1)),
)


def _consultar(scraper: ScraperNYT, params: dict[str, Any], pagina: int) -> requests.Response:
    return scraper._set_r(scraper._set_query_atual(scraper._set_query_base(**params), pagina))


def _hits(resp: requests.Response) -> int:
    resposta = resp.json().get("response", {})
    meta = resposta.get("meta") or resposta.get("metadata") or {}
    return int(meta.get("hits", 0))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAMPLES_DIR,
        help="pasta de saída (padrão: os samples commitados do NYT)",
    )
    saida: Path = parser.parse_args().saida
    saida.mkdir(parents=True, exist_ok=True)
    scraper = ScraperNYT()

    for i, (arquivo, params, pagina, hits_aceitos) in enumerate(CENARIOS):
        if i:
            time.sleep(scraper.sleep_time)
        resp = _consultar(scraper, params, pagina)
        resp.raise_for_status()
        dump_response(resp, saida / arquivo)
        hits = _hits(resp)
        aviso = "" if hits in hits_aceitos else f"  AVISO: {hits} hits não cabe no cenário, troque o termo"
        print(f"{arquivo}: HTTP {resp.status_code}, {len(resp.content)} bytes, hits={hits}{aviso}")

    # unauthorized.json: a mesma busca com uma chave que a API recusa (401).
    time.sleep(scraper.sleep_time)
    invalido = ScraperNYT(api_key="chave-invalida-para-captura")
    resp = _consultar(invalido, {"texto": "Brazil"}, 1)
    dump_response(resp, saida / "unauthorized.json")
    print(f"unauthorized.json: HTTP {resp.status_code}, {len(resp.content)} bytes")


if __name__ == "__main__":
    main()
