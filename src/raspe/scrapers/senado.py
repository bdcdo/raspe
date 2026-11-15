import hashlib
import re
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import Tag

from ..base_scraper import BaseScraper
from ..exceptions import ScraperError
from ..html_scraper import HTMLScraper


class ScraperSenadoFederal(BaseScraper, HTMLScraper):
    colunas = ['titulo', 'link_norma', 'link_detalhes', 'descricao', 'trecho_descricao']

    # Teto de tentativas da prova de trabalho anti-robô, o mesmo do script da página.
    MAX_TENTATIVAS_DESAFIO = 10_000_000

    def __init__(self, debug: bool = True):
        super().__init__("SENADO", debug)
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
            "DNT": "1",
            "Priority": "u=0, i",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
        })

        self._api_base = "https://www6g.senado.leg.br/busca"
        self._type = 'HTML'
        self._query_page_name = 'p'
        self._api_method = 'GET'

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['JSON'] | Literal['HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET'] | Literal['POST']:
        return self._api_method

    def _set_r(self, query_atual) -> requests.Response:
        """Faz a requisição e, se cair na verificação anti-robô, resolve o desafio e repete.

        A verificação do Senado (HTTP 200, título "Verificação de segurança") é uma
        prova de trabalho que o navegador resolve sozinho: achar ``tries`` tal que o
        SHA-256 de ``"<ip>;<host>;<ts>;<tries>"`` comece com ``diff`` zeros
        hexadecimais, e enviar a resposta por POST a ``/_challenge``. Depois disso o
        site libera o IP.

        Args:
            query_atual: Parâmetros da busca.

        Returns:
            requests.Response: A resposta da busca, já sem a verificação.

        Raises:
            ScraperError: Se o desafio não puder ser resolvido ou se a verificação
                continuar depois de resolvida.
        """
        r = super()._set_r(query_atual)
        form = self._form_desafio(r)
        if form is None:
            return r
        self.logger.info("Verificação anti-robô do Senado: resolvendo o desafio")
        self._resolver_desafio(form, r.url)
        r = super()._set_r(query_atual)
        if self._form_desafio(r) is not None:
            raise ScraperError(
                "ScraperSenadoFederal: a verificação anti-robô do site (\"Verificação de segurança\") "
                "continuou depois de resolvida. Tente de novo mais tarde."
            )
        return r

    def _form_desafio(self, r: requests.Response) -> Tag | None:
        """Devolve o formulário do desafio anti-robô, ou None se a resposta não é a verificação."""
        if b'challenge' not in r.content:
            return None
        form = self.soup_it(r.content).find('form', attrs={'name': 'challenge'})
        return form if isinstance(form, Tag) else None

    def _resolver_desafio(self, form: Tag, url_pagina: str) -> None:
        """Calcula a prova de trabalho do formulário ``challenge`` e envia a resposta.

        Args:
            form: Formulário ``challenge`` da página de verificação.
            url_pagina: URL que serviu a verificação; dá o host do hash e a base do POST.

        Raises:
            ScraperError: Se o formulário mudou de formato ou se não há solução
                dentro de ``MAX_TENTATIVAS_DESAFIO``.
        """
        campos = {str(i['name']): str(i.get('value', '')) for i in form.find_all('input') if i.get('name')}
        try:
            prefixo = '0' * int(campos['diff'])
            inicio = hashlib.sha256(f"{campos['ip']};{urlparse(url_pagina).hostname};{campos['ts']};".encode())
        except (KeyError, ValueError) as e:
            raise ScraperError(f"ScraperSenadoFederal: o desafio anti-robô mudou de formato ({e!r})") from e

        for tentativa in range(self.MAX_TENTATIVAS_DESAFIO):
            h = inicio.copy()
            h.update(str(tentativa).encode())
            if h.hexdigest().startswith(prefixo):
                break
        else:
            raise ScraperError("ScraperSenadoFederal: o desafio anti-robô não teve solução no teto de tentativas")

        campos['tries'] = str(tentativa)
        url = urljoin(url_pagina, str(form.get('action') or '/_challenge'))
        self.session.post(url, data=campos, timeout=self.timeout).raise_for_status()

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        pesquisa = kwargs.get('pesquisa')
        ano = kwargs.get('ano')
        tipo_materia = kwargs.get('tipo_materia')

        query_inicial = {
                'colecao': 'Legislação Federal',
                'p': 1
            }

        if tipo_materia:
            query_inicial['tipo-materia'] = tipo_materia

        if ano:
            query_inicial['ano'] = ano

        if pesquisa:
            query_inicial['q'] = pesquisa

        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        a_tag = r0s.find('a', attrs={"data-click-type": "dynnav.colecao.Legislação Federal"})
        # A contagem vem com separador de milhar ("8.950").
        match = re.search(r'\d[\d.]*', a_tag.text) if a_tag else None
        if not match:
            # A busca sem resultados não traz o link da coleção, só o aviso.
            return self._confirmar_busca_vazia(r0s)
        num_text = match.group()
        self.logger.debug(f"Found a text: '{num_text}'")

        num = int(num_text.replace('.', ''))

        self.logger.debug(f"Extracted number of results: {num}")

        # Convert results to pages (assuming 10 results per page)
        pages = (num + 9) // 10  # Round up division
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup

        with open(path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        lista_infos = []

        soup = BeautifulSoup(html_content, 'html.parser')

        container = soup.find('div', class_='col-xs-12 col-md-12 sf-busca-resultados')
        itens = container.find_all('div', class_='sf-busca-resultados-item') if container else []

        for idx, item in enumerate(itens, 1):
            try:
                # Extrair informações passo a passo para identificar onde falha
                h3_element = item.find('h3')
                if not h3_element:
                    raise ValueError("Elemento h3 não encontrado")

                # Verificar links dentro do h3
                links_h3 = h3_element.find_all('a')
                if len(links_h3) < 1:
                    raise ValueError("Nenhum link encontrado no h3")

                titulo = links_h3[0].text.strip()
                link_norma = links_h3[0]['href']
                # Se há apenas 1 link, usar o mesmo para ambos os campos
                link_detalhes = links_h3[1]['href'] if len(links_h3) > 1 else 'NA'

                # Verificar elementos p
                p_elements = item.find_all('p')
                if len(p_elements) < 3:
                    raise ValueError(f"Esperados pelo menos 3 elementos p, encontrados {len(p_elements)}")

                # Tentar diferentes estruturas para descrição
                # Estrutura original: p[0] é a descrição
                # Estrutura nova: p[1] é a descrição (quando p[0] é "Legislação")
                first_p_text = p_elements[0].text.strip()
                if first_p_text == "Legislação" and len(p_elements) > 1:
                    # Nova estrutura: p[1] é a descrição
                    descricao = p_elements[1].text.strip()
                else:
                    # Estrutura original: p[0] é a descrição
                    descricao = first_p_text

                trecho_descricao = p_elements[2].text.strip()

                lista_infos.append([titulo, link_norma, link_detalhes, descricao, trecho_descricao])
            except Exception as e:
                # Coletar informações diagnósticas detalhadas
                h3_diag = item.find('h3')
                links_diag = list(h3_diag.find_all('a')) if h3_diag else []
                p_diag = list(item.find_all('p'))

                item_info = {
                    'has_h3': bool(h3_diag),
                    'links_in_h3': len(links_diag),
                    'links_h3_details': [
                        {'text': a.text.strip()[:50], 'has_href': 'href' in a.attrs}
                        for a in links_diag
                    ],
                    'p_count': len(p_diag),
                    'p_elements_details': [
                        {'text': p.text.strip()[:50], 'class': str(p.get('class', ''))}
                        for p in p_diag
                    ],
                    'item_class': str(item.get('class', '')) if hasattr(item, 'get') else 'unknown'
                }

                self.logger.warning(
                    f"Erro ao processar item {idx} de {len(itens)} em {path}: {e}. "
                    f"Diagnóstico detalhado: {item_info}"
                )
                continue

        return pd.DataFrame(lista_infos, columns=self.colunas)
