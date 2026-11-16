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

import argparse
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Callable, Literal

import requests

from raspe.base_scraper import BaseScraper
from raspe.exceptions import ScraperError
from raspe.playwright_scraper import PlaywrightScraper


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


def pasta_saida(padrao: Path, descricao: str) -> Path:
    """Lê ``--saida`` da linha de comando, a pasta onde o script grava os samples.

    Args:
        padrao: Pasta usada sem ``--saida``, em geral a dos samples commitados.
        descricao: Descrição do script na ajuda do ``argparse``.

    Returns:
        A pasta de saída.
    """
    parser = argparse.ArgumentParser(description=descricao)
    parser.add_argument("--saida", type=Path, default=padrao, help=f"pasta de saída (padrão: {padrao})")
    saida: Path = parser.parse_args().saida
    return saida


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

    A linha impressa por cenário traz o valor do parâmetro de página (``None``
    no raspador de API sem paginação, que não envia o parâmetro) e o
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
            f"{scraper.query_page_name or 'sem página'}={query.get(scraper.query_page_name)}, "
            f"_find_n_pags={n_pags}"
        )


def enxugar_html(html: bytes, max_opcoes: int = 5) -> bytes:
    """Tira da página HTML o que não importa ao parser, para o sample ficar pequeno.

    Remove ``<script>``, ``<style>``, ``<svg>`` e comentários, e corta cada
    ``<select>`` nas primeiras ``max_opcoes`` opções. O resto da página fica
    como o site devolveu. Serve de ``enxugar`` para :func:`capturar_cenarios`.

    Args:
        html: Body cru da resposta.
        max_opcoes: Quantas ``<option>`` manter em cada ``<select>``.

    Returns:
        A página enxuta, em UTF-8.
    """
    from bs4 import BeautifulSoup, Comment

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "svg"]):
        tag.decompose()
    for comentario in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comentario.extract()
    for select in soup.find_all("select"):
        for opcao in select.find_all("option")[max_opcoes:]:
            opcao.decompose()
    return str(soup).encode("utf-8")


# O que a busca de um cenário tem de dar: resultados, zero linhas sem erro, ou ScraperError.
Espera = Literal["linhas", "vazia", "erro"]


def capturar_paginas_lidas(
    scraper: PlaywrightScraper,
    pesquisa: str,
    arquivos: tuple[str, ...],
    saida: Path,
    espera: Espera,
) -> None:
    """Faz a busca com um raspador com navegador e grava as páginas que ele lê.

    Grava as páginas de resultados que o raspador salva ou, sem resultados (ou
    com ``ScraperError``), a página que a contagem lê. O HTML passa por
    ``enxugar_html``. Antes de gravar, confere se a busca deu o que o cenário
    espera, para um ``no_results`` que trouxe linhas, ou um acesso recusado no
    lugar da busca vazia, não virar sample.

    Args:
        scraper: Raspador real, de uma subclasse de ``PlaywrightScraper``.
        pesquisa: Termo de busca.
        arquivos: Nomes dos arquivos, um por página.
        saida: Pasta onde gravar.
        espera: O que a busca tem de dar: ``"linhas"`` (resultados), ``"vazia"``
            (zero linhas, sem erro) ou ``"erro"`` (``ScraperError``, como o
            acesso recusado).

    Raises:
        RuntimeError: Se a busca não deu o que ``espera`` pede ou se o número de
            páginas lidas não bate com ``arquivos``. Nada é gravado.
    """
    obter_html = scraper._obter_html
    lidas: list[str] = []

    async def _obter_e_guardar() -> str:
        lidas.append(await obter_html())
        return lidas[-1]

    scraper._obter_html = _obter_e_guardar  # type: ignore[method-assign]
    erro: ScraperError | None = None
    linhas = 0
    try:
        linhas = len(scraper.raspar(pesquisa=pesquisa))
    except ScraperError as e:
        erro = e
    deu = "erro" if erro else "linhas" if linhas else "vazia"
    if deu != espera:
        detalhe = f"ScraperError: {erro}" if erro else f"{linhas} linhas"
        raise RuntimeError(f"'{pesquisa}': o cenário espera {espera!r}, e a busca deu {detalhe}")
    # A primeira leitura é a da contagem; as seguintes, as páginas salvas.
    paginas = lidas[1:] if linhas else lidas[:1]
    if len(paginas) != len(arquivos):
        raise RuntimeError(f"'{pesquisa}': {len(paginas)} páginas, esperadas {len(arquivos)}")
    for arquivo, html in zip(arquivos, paginas):
        (saida / arquivo).write_bytes(enxugar_html(html.encode()))
    print(f"'{pesquisa}': {erro or f'{linhas} linhas'}, {len(paginas)} páginas gravadas")
