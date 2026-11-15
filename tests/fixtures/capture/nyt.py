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
  imprime ``resp.url``, as falhas saem por ``requisitar_sem_url`` (sem a
  URL na mensagem) e só o body da resposta vai para o disco.
* A API limita a 5 requisições por minuto; o script espera
  ``ScraperNYT.sleep_time`` segundos entre uma requisição e a seguinte.
* As requisições saem da query do próprio ``ScraperNYT``, com a página
  convertida por ``_set_query_atual``: a página 1 do raspe vira
  ``page=0`` na API.
* O termo de ``single_page`` e o de ``no_results`` dependem do acervo do
  dia. A linha impressa por cenário traz o ``_find_n_pags`` da resposta:
  se ``page_01`` não der 2 ou mais, ``single_page`` não der 1 ou
  ``no_results`` não der 0, troque o termo ou o intervalo de datas.
"""

import time
from pathlib import Path

from raspe.scrapers.nyt import ScraperNYT
from tests.fixtures.capture._util import capturar_cenarios, dump_response, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "nyt" / "samples" / "raspar"

# (arquivo de saída, parâmetros de raspar, página do raspe). A busca
# typical precisa de pelo menos duas páginas de 10; a single_page, de uma
# só; a no_results, de zero hits.
CENARIOS = (
    ("page_01.json", {"pesquisa": "Brazil"}, 1),
    ("page_02.json", {"pesquisa": "Brazil"}, 2),
    (
        "single_page.json",
        {"pesquisa": "Supremo Tribunal Federal", "data_inicio": "2024-01-01", "data_fim": "2024-01-31"},
        1,
    ),
    ("no_results.json", {"pesquisa": "termoextremamenteimprovavelxyz123"}, 1),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    scraper = ScraperNYT()
    capturar_cenarios(scraper, CENARIOS, saida)

    # unauthorized.json: a mesma busca com uma chave que a API recusa (401).
    # A chave inválida pode aparecer em mensagem de erro sem expor a real.
    time.sleep(scraper.sleep_time)
    invalido = ScraperNYT(api_key="chave-invalida-para-captura")
    resp = invalido._set_r(invalido._set_query_atual(invalido._set_query_base(pesquisa="Brazil"), 1))
    dump_response(resp, saida / "unauthorized.json")
    print(f"unauthorized.json: HTTP {resp.status_code}, {len(resp.content)} bytes")


if __name__ == "__main__":
    main()
