"""Script ad-hoc para capturar samples do scraper de processos legislativos do Senado Federal.

Como executar (faz requisições reais à API de Dados Abertos, fora do CI),
a partir da raiz do repositório:

    uv run python -m tests.fixtures.capture.senado_processos
    saida=$(mktemp -d)
    uv run python -m tests.fixtures.capture.senado_processos --saida "$saida"

A forma ``-m`` é necessária porque o script importa ``tests.fixtures``;
rodado como arquivo, o Python não põe a raiz do repositório no
``sys.path``. Sem ``--saida``, os samples vão para
``tests/senado_processos/samples/raspar/`` e sobrescrevem os commitados.

As requisições saem da sessão e da query do próprio ``ScraperSenadoProcessos``.
A API não pagina: cada sample é a resposta inteira de uma consulta, e a linha
impressa por cenário traz ``_find_n_pags`` 1 (com processos) ou 0 (lista vazia).

Cenários capturados (contagens de 16/11/2026):

- ``janela_01.json`` e ``janela_02.json`` — as duas consultas em que o
  raspador divide a busca ``inteligência artificial`` de 2023-01-01 a
  2024-12-31, uma por ano (29 processos em cada).
- ``single_page.json`` — busca ``telemedicina`` com ``ano=2020`` (6
  processos, 1 consulta).
- ``no_results.json`` — termo absurdo, lista vazia.
"""

from pathlib import Path

from raspe.scrapers.senado_processos import ScraperSenadoProcessos
from tests.fixtures.capture._util import capturar_cenarios, pasta_saida

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "senado_processos" / "samples" / "raspar"

TERMO_DIVIDIDO = "inteligência artificial"

# (arquivo de saída, parâmetros de raspar, página do raspe). As duas janelas levam as
# datas que ``_dividir_busca`` dá a cada consulta da busca de 2023-01-01 a 2024-12-31.
CENARIOS = (
    ("janela_01.json", {"pesquisa": TERMO_DIVIDIDO, "data_inicio": "2023-01-01", "data_fim": "2023-12-31"}, 1),
    ("janela_02.json", {"pesquisa": TERMO_DIVIDIDO, "data_inicio": "2024-01-01", "data_fim": "2024-12-31"}, 1),
    ("single_page.json", {"pesquisa": "telemedicina", "ano": 2020}, 1),
    ("no_results.json", {"pesquisa": "termoinexistentexyz123", "ano": 2020}, 1),
)


def main() -> None:
    saida = pasta_saida(SAMPLES_DIR, __doc__.splitlines()[0])
    capturar_cenarios(ScraperSenadoProcessos(debug=False), CENARIOS, saida)


if __name__ == "__main__":
    main()
