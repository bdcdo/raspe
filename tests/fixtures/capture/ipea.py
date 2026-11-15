"""Script ad-hoc para capturar samples do scraper IPEA.

Como executar (faz requisições reais à internet — fora do CI):

    cd /caminho/para/raspe
    uv run python tests/fixtures/capture/ipea.py

Os samples são salvos em ``tests/ipea/samples/raspar/`` e podem ser
re-commitados quando o HTML do site mudar de estrutura. Os arquivos
atuais foram construídos manualmente replicando a estrutura observada
no portal, então este script só é necessário se algum teste de
contrato começar a falhar por mudança real no site.
"""

from pathlib import Path

import requests

from raspe.scrapers.ipea import ScraperIpea
from tests.fixtures.capture._util import attach_capture_hook
from tests.fixtures.capture._util import capturar_busca_vazia as _capturar  # noqa: E402

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "ipea" / "samples" / "raspar"
API_URL = (
    "https://www.ipea.gov.br/portal/coluna-5/"
    "central-de-conteudo/busca-publicacoes"
)


def main() -> None:
    session = requests.Session()
    attach_capture_hook(session, SAMPLES_DIR, prefix="page", extension="html")

    # Cenário typical: busca com paginação (assunto comum)
    session.get(
        API_URL,
        params={
            "palavra_chave": "pobreza",
            "tipo": "",
            "assunto": "",
            "autor": "",
            "timeperiods": "all",
            "data-inicial": "",
            "data-final": "",
            "pagina": "1",
        },
        timeout=30,
    )


def capturar_busca_vazia() -> None:
    """Grava ``no_results.html``: busca real sem resultados, feita pelo próprio raspador."""
    raspador = ScraperIpea(debug=False)
    _capturar(raspador, SAMPLES_DIR / "no_results.html", pesquisa="xqzwvkjh")


if __name__ == "__main__":
    main()
    capturar_busca_vazia()
