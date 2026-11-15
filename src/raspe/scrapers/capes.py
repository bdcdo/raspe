"""Raspador para o Portal de Periódicos da CAPES.

Base bibliográfica acadêmica brasileira mantida pela CAPES, que indexa
metadados de artigos, livros e capítulos via integração com o OpenAlex.
Acesso aos textos completos geralmente exige login institucional (CAFe);
o raspador coleta apenas os metadados da página pública de busca.

Exemplo:
    >>> import raspe
    >>> df = raspe.capes().raspar(pesquisa="natjus")
    >>> df[["titulo", "autores", "ano", "revista"]].head()
"""

import copy
import re
from typing import Any, Literal
from urllib.parse import urljoin

import pandas as pd
from bs4 import Tag

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from ..schemas.capes import InputCapes, OutputCapes

_BASE_DOMAIN = "https://www.periodicos.capes.gov.br"


# Elementos que o navegador exibe em bloco: os que aparecem nos cards e
# ``li``, de lista. Antes e depois de cada um ele quebra a linha, mesmo sem
# espaço no HTML.
_ELEMENTOS_DE_BLOCO = ['blockquote', 'div', 'li', 'p']


def _texto_exibido(elemento: Tag) -> str:
    """Extrai o texto de um elemento como o navegador o exibe.

    O portal destaca o termo buscado com ``<b>`` no título e no resumo, e o
    espaço em volta do destaque vem do HTML: em ``E-<b>NATJUS</b> NA`` há
    espaço só depois do ``<b>``. Entre nós inline, o navegador emenda o texto
    como está e reduz cada sequência de espaço em branco (quebra de linha e
    recuo incluídos) a um espaço. Juntar os nós sem separador e depois
    normalizar o espaço reproduz isso. ``get_text(strip=True)`` corta o espaço
    de cada nó e cola as palavras (``E-NATJUSNA``); ``get_text(' ', strip=True)``
    põe espaço em toda fronteira de nó, inclusive onde o HTML não tem
    (``E- NATJUS``).

    ``<br>`` e os elementos de ``_ELEMENTOS_DE_BLOCO`` são a exceção: neles o
    navegador quebra a linha mesmo sem espaço no HTML (``Color</p><p>Book.``
    aparece em duas linhas), e as palavras dos dois lados colariam. Por isso
    cada um recebe um espaço antes e outro depois, que a normalização reduz a
    um só. A inserção é feita numa cópia para não alterar a árvore do card.

    Args:
        elemento: Tag cujo texto será extraído.

    Returns:
        Texto com o espaço em branco normalizado e sem espaço nas pontas.
    """
    copia = copy.copy(elemento)
    for fronteira in copia.find_all(['br', *_ELEMENTOS_DE_BLOCO]):
        fronteira.insert_before(' ')
        fronteira.insert_after(' ')
    return ' '.join(copia.get_text().split())


class ScraperCapes(BaseScraper, HTMLScraper):
    """Raspador HTTP para o buscador do Portal de Periódicos da CAPES."""

    schema_entrada = InputCapes
    schema_saida = OutputCapes

    _SELETOR_CARD = 'div.col-md-12.br-item[id^="conteudo-"]'

    def __init__(self, debug: bool = True):
        super().__init__("capes", debug)

        self._api_base = f"{_BASE_DOMAIN}/index.php/acervo/buscador.html"
        self._api_method: Literal['GET'] = 'GET'
        self._type: Literal['HTML'] = 'HTML'
        self._query_page_name = 'page'

        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,en-US;q=0.7,en;q=0.3",
            "Connection": "keep-alive",
            "DNT": "1",
            "Priority": "u=0, i",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        })

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET']:
        return self._api_method

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        # O schema (PesquisaObrigatoriaMixin) já recusou pesquisa vazia.
        pesquisa = kwargs.get('pesquisa')
        return {
            'q': f'all:contains({pesquisa})',
            'mode': 'advanced',
            'source': 'all',
        }

    def _find_n_pags(self, r0) -> int:
        r0.raise_for_status()
        soup = self.soup_it(r0.content)

        nav = soup.find('nav', class_='br-pagination')
        if not nav:
            # A busca sem resultados não traz a paginação, só o aviso.
            return self._confirmar_busca_vazia(soup)

        total_attr = str(nav.get('data-total', '') or '')
        total_digits = total_attr.replace('.', '').replace(',', '')
        if not total_digits:
            return self._confirmar_busca_vazia(soup)

        total = int(total_digits)
        if total == 0:
            return 0

        # O nav declara data-per-page="20", mas o portal serve 30 itens por página
        # (visto ao vivo em 2026-11-14: 436 resultados = 14 páginas de 30 + 16).
        # Por isso o tamanho da página vem dos cards da própria página 1; o
        # atributo fica só de reserva.
        per_page_attr = str(nav.get('data-per-page', '') or '').strip()
        per_page = len(soup.select(self._SELETOR_CARD)) or (int(per_page_attr) if per_page_attr.isdigit() else 0) or 20
        return (total + per_page - 1) // per_page

    def _parse_page(self, path: str) -> pd.DataFrame:
        with open(path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        soup = self.soup_it(html_content)
        cards = soup.select(self._SELETOR_CARD)

        registros = []
        for card in cards:
            try:
                registros.append(self._parse_card(card))
            except Exception as e:
                self.logger.warning(f"Erro parseando card em {path}: {e}")
                continue

        return pd.DataFrame(registros, columns=self.colunas)

    def _parse_card(self, card) -> dict[str, Any]:
        out: dict[str, Any] = {}

        tipo_span = next(
            (s for s in card.find_all('span', class_='fw-semibold')
             if len(s.get('class', [])) == 1),
            None,
        )
        out['tipo'] = tipo_span.get_text(strip=True) if tipo_span else ''

        # Grafia "open-acess" (1 c, 2 s) é typo upstream da CAPES no HTML real.
        # Se o portal corrigir para "open-access", o booleano vira False
        # silenciosamente — regenerar samples e atualizar o regex.
        out['acesso_aberto'] = card.find(id=re.compile(r'^open-acess-item-')) is not None
        out['producao_nacional'] = card.find(id=re.compile(r'^national-production-item-')) is not None
        out['revisado_por_pares'] = card.find(id=re.compile(r'^peer-reviewed-item-')) is not None

        titulo_a = card.select_one('a.titulo-busca')
        out['titulo'] = _texto_exibido(titulo_a) if titulo_a else ''

        raw_link = titulo_a.get('href', '') if titulo_a else ''
        out['link'] = urljoin(_BASE_DOMAIN, raw_link) if raw_link else ''

        m_id = re.search(r'[?&]id=([A-Za-z0-9_-]+)', out['link'])
        out['id'] = m_id.group(1) if m_id else ''

        autores = card.select('a.view-autor')
        out['autores'] = '; '.join(
            a.get('data-autor') or a.get_text(strip=True)
            for a in autores
        )

        bq = card.find('blockquote', class_='blockquote-busca')
        out['resumo'] = _texto_exibido(bq) if bq else ''

        out['topicos'] = ''
        out['ano'] = ''
        out['instituicao'] = ''
        out['revista'] = ''
        for p in card.find_all('p', class_='text-down-01'):
            text = p.get_text()
            if 'Tópico' in text:
                span = p.find('span', class_='font-italic') or p.find('span')
                if span:
                    out['topicos'] = span.get_text(strip=True)
                continue

            # Só os <b> filhos do <p>: o destaque do termo buscado é outro <b>,
            # aninhado no da instituição ou da revista.
            bs = p.find_all('b', recursive=False)
            if not bs or out['ano']:
                continue

            ano_text = bs[0].get_text(strip=True).rstrip(' -').strip()
            if re.fullmatch(r'\d{4}', ano_text):
                out['ano'] = ano_text
            # Depois do ano vêm instituição e revista, e a revista vem marcada
            # pelo ``|`` inicial: o card sem instituição traz só ano e revista.
            for b in bs[1:3]:
                texto = _texto_exibido(b)
                if texto.startswith('|'):
                    out['revista'] = texto[1:].strip()
                else:
                    out['instituicao'] = texto

        out['doi'] = ''
        out['link_editor'] = ''
        ver_editor = card.find('a', class_='add-metrics', href=re.compile(r'doi\.org'))
        if ver_editor:
            link_editor = ver_editor.get('href', '')
            out['link_editor'] = link_editor
            m_doi = re.search(r'doi\.org/([^?#]+)', link_editor)
            if m_doi:
                out['doi'] = m_doi.group(1).strip()

        return out
