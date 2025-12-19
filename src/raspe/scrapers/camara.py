from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from typing import Any, Literal
import pandas as pd
from bs4 import BeautifulSoup as bs
from bs4 import Tag
from bs4.element import NavigableString
import tempfile
import requests
import re
import time
import random

class ScraperCamaraDeputados(BaseScraper, HTMLScraper):
    def __init__(self):
        super().__init__("CAMARA")
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
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

        self._prep_scrape()

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
        num_text = '0'
        if r0s:
            div_element = r0s.find('div', class_='busca-info__resultado busca-info__resultado--informado')
            if div_element:
                text = div_element.text.strip()
                # Captura o número total (último número após "de")
                match = re.search(r'de (\d+)(?!.*de)', text)
                if not match:
                    # Se não encontrou, tenta padrão alternativo
                    match = re.search(r'de (\d+)$', text)
                num_text = match.group(1) if match else '0'
                self.logger.debug(f"Found full text: '{text}', extracted number: '{num_text}'")

        num = int(num_text)

        self.logger.debug(f"Extracted number of results: {num}")
        
        # Convert results to pages (assuming 10 results per page)
        pages = (num + 9) // 10  # Round up division
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup
        
        columns = ['link', 'titulo', 'descricao', 'ementa']
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            lista_infos = []

            soup = BeautifulSoup(html_content, 'html.parser')
            
            resultado_busca = soup.find('div', class_='resultado-busca')
            if not resultado_busca or not isinstance(resultado_busca, Tag):
                return pd.DataFrame(columns=columns)
            
            ul_element = resultado_busca.find('ul')
            if not ul_element or not isinstance(ul_element, Tag):
                return pd.DataFrame(columns=columns)
                
            itens = ul_element.find_all('li')

            for item in itens:
                if not isinstance(item, Tag):
                    continue
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
                    self.logger.warning(f"Error parsing item in {path}: {e}")
                    continue

            return pd.DataFrame(lista_infos, columns=columns)
            
        except Exception as e:
            self.logger.error(f"Error parsing page {path}: {e}")
            return pd.DataFrame(columns=columns)
        
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
