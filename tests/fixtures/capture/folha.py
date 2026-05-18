"""Script ad-hoc para capturar samples do scraper Folha.

Como executar (faz requisições reais à internet — fora do CI):

    cd /caminho/para/raspe
    uv run python tests/fixtures/capture/folha.py

Os samples são salvos em ``tests/folha/samples/raspar/``. Os arquivos
atuais foram construídos manualmente replicando a estrutura observada
no site de busca da Folha; este script só é necessário se algum teste
de contrato começar a falhar por mudança real no site.
"""

from pathlib import Path

import requests

from tests.fixtures.capture._util import attach_capture_hook  # noqa: E402

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "folha" / "samples" / "raspar"
API_URL = "https://search.folha.uol.com.br/search"


def main() -> None:
    session = requests.Session()
    attach_capture_hook(session, SAMPLES_DIR, prefix="page", extension="html")

    # Cenário typical/single_page: busca real
    session.get(
        API_URL,
        params={"q": "educação", "site": "todos", "periodo": "todos", "sr": "1"},
        timeout=30,
    )

    # Cenário no_results: termo improvável
    session.get(
        API_URL,
        params={
            "q": "zzzzzzz_termo_inexistente_xyzabc",
            "site": "todos",
            "periodo": "todos",
            "sr": "1",
        },
        timeout=30,
    )


if __name__ == "__main__":
    main()
