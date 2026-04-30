"""Utilitário para scripts de captura de samples.

Cada scraper tem um script em `tests/fixtures/capture/<scraper>.py` que
exercita o scraper real, captura as respostas HTTP cruas e salva em
`tests/<scraper>/samples/<endpoint>/<cenario>.<ext>`. Esses samples
viram a fonte de verdade dos contratos offline.

Uso típico em um script de captura:

    from pathlib import Path
    import requests
    from tests.fixtures.capture._util import attach_capture_hook

    samples_dir = Path("tests/presidencia/samples/raspar")
    samples_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    attach_capture_hook(session, samples_dir, prefix="page")
    # ... usa a session para exercitar o scraper ...
"""

from pathlib import Path
from typing import Callable

import requests


def dump_response(resp: requests.Response, path: Path) -> None:
    """Salva o body bruto de uma resposta HTTP em disco.

    Cria diretórios pais se necessário. Preserva o encoding original via
    `resp.content` (bytes), evitando problemas com latin-1/utf-8 mistos.

    Args:
        resp: Resposta retornada por `requests`.
        path: Caminho absoluto onde gravar o body.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(resp.content)


def attach_capture_hook(
    session: requests.Session,
    samples_dir: Path,
    *,
    prefix: str = "response",
    extension: str | None = None,
) -> Callable[[], None]:
    """Anexa um hook `response` à sessão que salva cada resposta automaticamente.

    Numera os arquivos sequencialmente: `<prefix>_01.<ext>`, `<prefix>_02.<ext>`,
    etc. A extensão padrão é inferida do `Content-Type` (`html`, `json`, ou `bin`).

    Args:
        session: Sessão `requests` a instrumentar.
        samples_dir: Diretório de saída (será criado).
        prefix: Prefixo do nome dos arquivos.
        extension: Extensão fixa; se None, infere de Content-Type.

    Returns:
        Função para remover o hook (chamar quando terminar a captura).
    """
    samples_dir.mkdir(parents=True, exist_ok=True)
    counter = {"i": 0}

    def _hook(resp: requests.Response, *args, **kwargs) -> requests.Response:
        counter["i"] += 1
        ext = extension or _guess_extension(resp)
        filename = f"{prefix}_{counter['i']:02d}.{ext}"
        dump_response(resp, samples_dir / filename)
        return resp

    session.hooks.setdefault("response", []).append(_hook)

    def _detach() -> None:
        hooks = session.hooks.get("response", [])
        if _hook in hooks:
            hooks.remove(_hook)

    return _detach


def _guess_extension(resp: requests.Response) -> str:
    """Infere a extensão do arquivo a partir do Content-Type da resposta."""
    content_type = resp.headers.get("Content-Type", "").lower()
    if "json" in content_type:
        return "json"
    if "html" in content_type or "xml" in content_type:
        return "html"
    return "bin"
