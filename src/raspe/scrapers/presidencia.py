from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from typing import Any, Literal
import pandas as pd
from bs4 import BeautifulSoup as bs
import tempfile
import requests
import re
import time

class ScraperPresidencia(BaseScraper, HTMLScraper):
    def __init__(self):
        super().__init__("PRESIDENCIA")
        self.query_page_multiplier = 10
        self.query_page_increment = -10
        self.session.headers.update({
            "Accept": "*/*",
            "Origin": "https://legislacao.presidencia.gov.br",
            "Referer": "https://legislacao.presidencia.gov.br/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "DNT": "1",
            "Priority": "u=0",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "X-Requested-With": "XMLHttpRequest"
        })

        self._api_base = "https://legislacao.presidencia.gov.br/pesquisa/ajax/resultado_pesquisa_legislacao.php"
        self._type = 'HTML'
        self._query_page_name = 'posicao'
        self._api_method = 'POST'

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['JSON']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['POST']:
        return self._api_method
    
    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        pesquisa = kwargs.get('pesquisa')

        query_inicial = {
                'termo': pesquisa,
                'ordenacao': 'maior_data',
                'posicao': '0'
            }
        
        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        num_text = '0'
        if r0s:
            h4_tag = r0s.find('h4')
            if h4_tag:
                num_text = h4_tag.text
                self.logger.debug(f"Found h4 text: '{num_text}'")

        num = 0
        # Pattern specifically for "1.006 resultados encontrados" (handling thousands separator)
        match = re.search(r'([\d.]+)\s+resultados?\s+encontrados?', num_text, re.IGNORECASE)
        if match:
            # Remove dots used as thousands separators
            num_str = match.group(1).replace('.', '')
            num = int(num_str)
        else:
            # Fallback to first number (with thousands separator handling)
            match = re.search(r'[\d.]+', num_text)
            if match:
                num_str = match.group(0).replace('.', '')
                num = int(num_str)

        self.logger.debug(f"Extracted number of results: {num}")
        
        # Convert results to pages (assuming 10 results per page)
        pages = (num + 9) // 10  # Round up division
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup
        
        columns = ['nome', 'link', 'ficha', 'revogacao', 'descricao']
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            lista_infos = []

            soup = BeautifulSoup(html_content, 'html.parser')
            card_body = soup.find('div', class_='card-body p-0')
            
            if not card_body:
                return pd.DataFrame(columns=columns)
                
            container = card_body.find('div')
            if not container:
                return pd.DataFrame(columns=columns)
                
            itens = container.find_all('div')

            for i in range(len(itens)):
                if i % 2 == 1:
                    continue
                else:
                    try:
                        item = itens[i]
                        links = item.find_all('a')
                        paragraphs = item.find_all('p')
                        
                        if len(links) >= 2 and len(paragraphs) >= 2:
                            nome = links[0].text.strip()
                            link = links[0]['href']
                            ficha = links[1]['href']
                            revogacao = paragraphs[0].text
                            descricao = paragraphs[1].text

                            lista_infos.append([nome, link, ficha, revogacao, descricao])
                    except Exception as e:
                        self.logger.warning(f"Error parsing item in {path}: {e}")
                        continue

            return pd.DataFrame(lista_infos, columns=columns)
            
        except Exception as e:
            self.logger.error(f"Error parsing page {path}: {e}")
            return pd.DataFrame(columns=columns)