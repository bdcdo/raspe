import random
import re
import time
from typing import Any, Literal

import pandas as pd
from bs4 import Tag

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from ..schemas.camara import InputCamara


class ScraperCamaraDeputados(BaseScraper, HTMLScraper):
    schema_entrada = InputCamara
    colunas = ['link', 'titulo', 'descricao', 'ementa']

    # O portal exibe 20 resultados por página e responde HTTP 500 a partir da
    # página 501 (visto ao vivo em 2026-11-14).
    RESULTADOS_POR_PAGINA = 20
    LIMITE_PAGINAS = 500

    def __init__(self, debug: bool = True):
        super().__init__("CAMARA", debug)
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept': (
                'text/html,application/xhtml+xml,application/xml;q=0.9,'
                'image/avif,image/webp,image/apng,*/*;q=0.8'
            ),
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'DNT': '1',
        })

        self._api_base = "https://www.camara.leg.br/legislacao/busca"
        self._type = 'HTML'
        self._query_page_name = 'pagina'
        self._api_method = 'GET'

        self._sessao_preparada = False

    def _set_r(self, query_atual):
        if not self._sessao_preparada:
            self._prep_scrape()
            self._sessao_preparada = True
        return super()._set_r(query_atual)

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

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        pesquisa = kwargs.get('pesquisa')
        ano = kwargs.get('ano')
        tipo_materia = kwargs.get('tipo_materia')

        query_inicial = {
                "ordenacao": "data:ASC",
                "abrangencia": "Legislação Federal",
                "pagina": 1,
            }

        if tipo_materia:
            query_inicial['tipo'] = tipo_materia

        if ano:
            query_inicial['ano'] = ano

        if pesquisa:
            query_inicial['geral'] = pesquisa

        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        div_element = r0s.find('div', class_='busca-info__resultado busca-info__resultado--informado')
        # "Exibindo resultados de 1 a 20 de 59889": o total é o último número após "de".
        numeros = re.findall(r'de (\d+)', div_element.get_text(" ", strip=True)) if div_element else []
        if not numeros:
            return self._confirmar_busca_vazia(r0s)

        num = int(numeros[-1])
        self.logger.debug(f"Extracted number of results: {num}")

        # O portal só exibe os 10.000 primeiros (500 páginas de 20).
        pages = self._paginas_para(
            num, self.RESULTADOS_POR_PAGINA, self.LIMITE_PAGINAS * self.RESULTADOS_POR_PAGINA,
            dica="por ano ou tipo de matéria, por exemplo",
        )
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup

        with open(path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        lista_infos = []

        soup = BeautifulSoup(html_content, 'html.parser')

        resultado_busca = soup.find('div', class_='resultado-busca')
        if not resultado_busca or not isinstance(resultado_busca, Tag):
            return pd.DataFrame(columns=self.colunas)

        ul_element = resultado_busca.find('ul')
        if not ul_element or not isinstance(ul_element, Tag):
            return pd.DataFrame(columns=self.colunas)

        itens = ul_element.find_all('li')
        erros: list[Exception] = []

        for item in itens:
            try:
                link_element = item.find('a')
                if not link_element or not isinstance(link_element, Tag):
                    continue

                link = link_element.get('href', '')
                titulo = link_element.text or ''

                div_element = item.find('div')
                descricao = ''
                if div_element and isinstance(div_element, Tag):
                    p_element = div_element.find('p')
                    if p_element and isinstance(p_element, Tag):
                        descricao = p_element.text.strip()

                ementa_element = item.find('p', class_='busca-resultados__situacao')
                ementa = ''
                if ementa_element and isinstance(ementa_element, Tag):
                    ementa = ementa_element.text.strip()

                lista_infos.append([link, titulo, descricao, ementa])
            except Exception as e:
                self.logger.warning(f"Erro ao processar item em {path}: {e}")
                erros.append(e)

        self._conferir_itens(path, erros, len(lista_infos))
        return pd.DataFrame(lista_infos, columns=self.colunas)

    def _acessar_pagina_inicial(self):
        """Primeiro acessa a página inicial para estabelecer sessão"""
        try:
            print("Acessando página inicial...")
            response = self.session.get('https://www.camara.leg.br/')
            print(f"Status página inicial: {response.status_code}")

            # Pequena pausa para simular comportamento humano
            time.sleep(random.uniform(1, 3))

            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao acessar página inicial: {e}")
            return False

    def _acessar_legislacao_busca(self):
        """Acessa a página de busca de legislação"""
        try:
            print("Acessando página de busca...")
            url_busca = 'https://www.camara.leg.br/legislacao/busca'

            # Atualiza referer
            self.session.headers.update({
                'Referer': 'https://www.camara.leg.br/',
            })

            response = self.session.get(url_busca)
            print(f"Status página de busca: {response.status_code}")

            time.sleep(random.uniform(1, 3))

            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao acessar página de busca: {e}")
            return False

    def _prep_scrape(self, **kwargs) -> dict[str, Any]:
        self._acessar_pagina_inicial()
        self._acessar_legislacao_busca()

        self.session.headers.update({
                    'Referer': 'https://www.camara.leg.br/legislacao/busca',
                })

        return {}
