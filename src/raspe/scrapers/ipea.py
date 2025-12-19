from typing import Any, Literal
import pandas as pd

from ..html_scraper import HTMLScraper
from ..base_scraper import BaseScraper

class IpeaScraper(BaseScraper, HTMLScraper):
    def __init__(self, download_path = None):
        super().__init__("IPEA")
        
        self._api_base = "https://www.ipea.gov.br/portal/coluna-5/central-de-conteudo/busca-publicacoes"
        self._api_method = 'GET'
        self._type = 'HTML'
        self._query_page_name = 'pagina'

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
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"
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
        pesquisa = kwargs.get('pesquisa')

        query_inicial = {
                'palavra_chave': pesquisa,
                'tipo': '',
                'assunto': '',
                'autor': '',
                'timeperiods': 'all',
                'data-inicial': '',
                'data-final': '',
                'pagina': '1',
            }
        
        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        num_text = '0'
        if r0s:
            h4_tag = r0s.find('div', class_="col clearfix").find('h4').find('strong')           
            if h4_tag:
                num_text = h4_tag.text
                self.logger.debug(f"Found h4 text: '{num_text}'")

        num = int(num_text)
        
        self.logger.debug(f"Extracted number of results: {num}")
        
        pages = (num + 9) // 10
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup
        
        columns = ['titulo', 'link', 'autores', 'data', 'assuntos']
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            lista_infos = []

            soup = BeautifulSoup(html_content, 'html.parser')
            card_body = soup.find('div', class_='lista-publicacoes')
            
            if not card_body:
                # Return empty pandas DataFrame
                return pd.DataFrame(columns=columns)
                
            container = card_body.find('div')
            if not container:
                # Return empty pandas DataFrame
                return pd.DataFrame(columns=columns)
                
            itens = container.find_all('div', class_="row")

            for i in range(len(itens)):
                try:
                    item = itens[i]
                    item = item.find('div', class_='publi-conteudo')
                    
                    link = 'https://www.ipea.gov.br' + item.find('h3').find('a')['href']
                    titulo = item.find('h3').find('a').text.strip()
                    autores = item.find('div', class_='autores').text.strip()
                    data = item.find('p').text.strip() if item.find('p') else ""
                    assuntos = item.find('div', class_='assuntos').text.strip()

                    lista_infos.append([titulo, link, autores, data, assuntos])
                except Exception as e:
                    self.logger.warning(f"Error parsing item in {path}: {e}")
                    continue

            # Directly create a pandas DataFrame since the base scraper expects pandas
            return pd.DataFrame(lista_infos, columns=columns)
            
        except Exception as e:
            self.logger.error(f"Error parsing page {path}: {e}")
            # Return empty pandas DataFrame
            return pd.DataFrame(columns=columns)