"""Script ad-hoc para capturar samples do scraper Presidência.

Como executar (faz requisições reais à internet — fora do CI):

    cd /caminho/para/raspe
    uv run python tests/fixtures/capture/presidencia.py

Os samples são salvos em ``tests/presidencia/samples/raspar/``. Os
arquivos atuais foram construídos manualmente replicando a estrutura
HTML observada no AJAX de pesquisa de legislação da Presidência. Este
script só é necessário se algum teste de contrato começar a falhar por
mudança real no site.

Notas operacionais:

* O servidor real tem cadeia de certificados SSL incompleta; o script
  desativa a verificação como o scraper faz em produção
  (``session.verify = False``).
* A API é POST AJAX (``X-Requested-With: XMLHttpRequest``) com payload
  ``application/x-www-form-urlencoded``.
"""

from pathlib import Path

import requests
import urllib3

from tests.fixtures.capture._util import attach_capture_hook  # noqa: E402

SAMPLES_DIR = (
    Path(__file__).resolve().parents[2] / "presidencia" / "samples" / "raspar"
)
API_URL = (
    "https://legislacao.presidencia.gov.br/pesquisa/ajax/"
    "resultado_pesquisa_legislacao.php"
)


def main() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Origin": "https://legislacao.presidencia.gov.br",
        "Referer": "https://legislacao.presidencia.gov.br/",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    })
    attach_capture_hook(session, SAMPLES_DIR, prefix="page", extension="html")

    # Cenário typical: termo com vários resultados
    session.post(
        API_URL,
        data={
            "termo": "meio ambiente",
            "ordenacao": "maior_data",
            "posicao": "0",
        },
        timeout=30,
    )

    # Cenário no_results: termo improvável
    session.post(
        API_URL,
        data={
            "termo": "zzzzzzz_termo_inexistente_xyzabc",
            "ordenacao": "maior_data",
            "posicao": "0",
        },
        timeout=30,
    )


if __name__ == "__main__":
    main()
