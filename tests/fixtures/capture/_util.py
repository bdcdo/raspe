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


def requisitar_sem_url(enviar: Callable[[], requests.Response], arquivo: str) -> requests.Response:
    """Faz a requisição e, se ela falhar, levanta um erro que não cita a URL.

    O ``HTTPError`` de ``raise_for_status`` e os erros de rede do ``requests``
    trazem a URL completa na mensagem, e em alguns scrapers ela leva chave de
    API (o ``api-key`` do NYT). Aqui a mensagem leva só o arquivo e o status.

    Args:
        enviar: Função sem argumentos que faz a requisição.
        arquivo: Nome do sample, para identificar o cenário na mensagem.

    Returns:
        A resposta, já conferida como 2xx.

    Raises:
        RuntimeError: Se a requisição falhar ou não devolver 2xx.
    """
    try:
        resp = enviar()
    except requests.RequestException as e:
        raise RuntimeError(f"{arquivo}: falha de rede ({type(e).__name__})") from None
    if not resp.ok:
        raise RuntimeError(f"{arquivo}: HTTP {resp.status_code}")
    return resp


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
    imprime a URL, que em alguns scrapers leva chave de API, e as falhas
    passam por :func:`requisitar_sem_url` pelo mesmo motivo. O
    ``_find_n_pags`` roda antes de gravar: uma página de manutenção ou de
    verificação anti-robô levanta ``ScraperError`` sem sobrescrever o sample.

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
        resp = requisitar_sem_url(lambda q=query: scraper._set_r(q), arquivo)
        n_pags = scraper._find_n_pags(resp)
        conteudo = resp.content if enxugar is None else enxugar(resp.content)
        (saida / arquivo).write_bytes(conteudo)
        print(
            f"{arquivo}: HTTP {resp.status_code}, {len(resp.content)} bytes recebidos, "
            f"{len(conteudo)} gravados, "
            f"{scraper.query_page_name}={query[scraper.query_page_name]}, "
            f"_find_n_pags={n_pags}"
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


def dump_html_enxuto(resp: requests.Response, path: Path, max_opcoes: int = 5) -> None:
    """Salva uma página HTML sem o que não importa ao parser, para o sample ficar pequeno.

    Remove ``<script>``, ``<style>``, ``<svg>`` e comentários, e corta cada
    ``<select>`` nas primeiras ``max_opcoes`` opções (o filtro de autores do
    IPEA sozinho passa de 800 KB). O resto da página fica como o site devolveu.

    Args:
        resp: Resposta HTML retornada por `requests`.
        path: Caminho onde gravar o HTML.
        max_opcoes: Quantas ``<option>`` manter em cada ``<select>``.
    """
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()
    for comentario in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comentario.extract()
    for select in soup.find_all("select"):
        for opcao in select.find_all("option")[max_opcoes:]:
            opcao.decompose()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(soup), encoding="utf-8")


def capturar_busca_vazia(raspador: Any, path: Path, **query: Any) -> None:
    """Faz a busca inicial pelo próprio raspador e grava a página enxuta em ``path``.

    Args:
        raspador: Instância de um raspador HTTP (``BaseScraper``).
        path: Caminho do sample, em geral ``.../no_results.html``.
        **query: Parâmetros de busca, como em ``raspador.raspar()``.
    """
    dump_html_enxuto(raspador._set_r(raspador._set_query_base(**query)), path)
