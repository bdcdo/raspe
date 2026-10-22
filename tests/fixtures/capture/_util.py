"""Utilitário para scripts de captura de samples.

Cada scraper tem um script em `tests/fixtures/capture/<scraper>.py` que
exercita o scraper real, captura as respostas HTTP cruas e salva em
`tests/<scraper>/samples/<endpoint>/<cenario>.<ext>`. Esses samples
viram a fonte de verdade dos contratos offline.

Os scripts importam ``tests.fixtures`` e por isso rodam como módulo, a
partir da raiz do repositório (``python -m tests.fixtures.capture.<scraper>``).
Rodado como arquivo, o Python põe a pasta do script no ``sys.path`` no
lugar da raiz, e o import de ``tests`` falha.

Uso típico em um script de captura:

    from pathlib import Path

    from raspe.scrapers.presidencia import ScraperPresidencia
    from tests.fixtures.capture._util import capturar_cenarios

    capturar_cenarios(
        ScraperPresidencia(),
        [("page_01.html", {"pesquisa": "saúde"}, 1)],
        Path("tests/presidencia/samples/raspar"),
    )
"""

import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable

import requests

from raspe.base_scraper import BaseScraper


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


def capturar_cenarios(
    scraper: BaseScraper,
    cenarios: Iterable[tuple[str, dict[str, Any], int]],
    saida: Path,
    enxugar: Callable[[bytes], bytes] | None = None,
) -> None:
    """Baixa cada cenário com a query e o método HTTP do próprio scraper.

    A query de cada cenário é a que ``raspar`` montaria para aquela página:
    ``_validar_parametros``, ``_set_query_base`` e ``_set_query_atual``, nessa
    ordem. A requisição sai de ``_set_r``, que escolhe GET ou POST conforme
    ``api_method`` e usa a sessão do scraper, com os headers dele. Assim o
    sample reflete o que o scraper envia em produção.

    A linha impressa por cenário traz o valor do parâmetro de página e o
    ``_find_n_pags`` da resposta, para conferir se o termo cabe no cenário
    (``single_page`` tem de dar 1, ``no_results`` tem de dar 0). Ela não
    imprime a URL, que em alguns scrapers leva chave de API.

    Args:
        scraper: Instância do scraper a exercitar.
        cenarios: Tuplas ``(arquivo de saída, parâmetros de raspar, página do raspe)``.
        saida: Pasta onde os arquivos serão gravados (criada se preciso).
        enxugar: Função aplicada ao body antes de gravar, para cortar o que o
            scraper não lê quando a página passa do limite de tamanho do
            repositório. ``_find_n_pags`` continua lendo a resposta inteira.
    """
    saida.mkdir(parents=True, exist_ok=True)
    for i, (arquivo, params, pagina) in enumerate(cenarios):
        if i:
            # Mesmo intervalo que o scraper usa entre páginas em produção.
            time.sleep(scraper.sleep_time)
        query_base = scraper._set_query_base(**scraper._validar_parametros(**params))
        query = scraper._set_query_atual(query_base, pagina)
        resp = scraper._set_r(query)
        resp.raise_for_status()
        conteudo = resp.content if enxugar is None else enxugar(resp.content)
        (saida / arquivo).write_bytes(conteudo)
        print(
            f"{arquivo}: HTTP {resp.status_code}, {len(resp.content)} bytes recebidos, "
            f"{len(conteudo)} gravados, "
            f"{scraper.query_page_name}={query[scraper.query_page_name]}, "
            f"_find_n_pags={scraper._find_n_pags(resp)}"
        )


def attach_capture_hook(
    session: requests.Session,
    samples_dir: Path,
    *,
    prefix: str = "response",
    extension: str | None = None,
) -> Callable[[], None]:
    """Anexa um hook `response` à sessão que salva cada resposta automaticamente.

    Numera os arquivos sequencialmente: `<prefix>_01.<ext>`, `<prefix>_02.<ext>`,
    etc. A extensão padrão é inferida do `Content-Type` (`html`, `json`, `xml` ou `bin`).

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

    def _hook(resp: requests.Response, *args: Any, **kwargs: Any) -> requests.Response:
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
    if "xml" in content_type:
        return "xml"
    if "html" in content_type:
        return "html"
    return "bin"
