from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from typing import Any, Literal
import pandas as pd
from bs4 import BeautifulSoup as bs
import tempfile
import requests
import re
import time

class ScraperSenadoFederal(BaseScraper, HTMLScraper):
    def __init__(self):
        super().__init__("SENADO")
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
        num_text = '0'
        if r0s:
            a_tag = r0s.find('a', attrs={"data-click-type":"dynnav.colecao.Legislação Federal"})
            if a_tag:
                num_text = re.search(r'\d+', a_tag.text).group()
                self.logger.debug(f"Found a text: '{num_text}'")

        num = int(num_text)

        self.logger.debug(f"Extracted number of results: {num}")
        
        # Convert results to pages (assuming 10 results per page)
        pages = (num + 9) // 10  # Round up division
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup
        
        columns = ['titulo', 'link_norma', 'link_detalhes', 'descricao', 'trecho_descricao']
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            lista_infos = []

            soup = BeautifulSoup(html_content, 'html.parser')
                
            itens = soup.find('div', class_='col-xs-12 col-md-12 sf-busca-resultados').find_all('div', class_='sf-busca-resultados-item')

            for idx, item in enumerate(itens, 1):
                try:
                    # Extrair informações passo a passo para identificar onde falha
                    h3_element = item.find('h3')
                    if not h3_element:
                        raise ValueError("Elemento h3 não encontrado")
                    
                    # Verificar links dentro do h3
                    links_h3 = h3_element.find_all('a')
                    if len(links_h3) < 1:
                        raise ValueError(f"Nenhum link encontrado no h3")
                    
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
                    h3_element = item.find('h3')
                    links_h3 = h3_element.find_all('a') if h3_element else []
                    p_elements = item.find_all('p')
                    
                    item_info = {
                        'has_h3': bool(h3_element),
                        'links_in_h3': len(links_h3),
                        'links_h3_details': [{'text': a.text.strip()[:50], 'has_href': 'href' in a.attrs} for a in links_h3] if links_h3 else [],
                        'p_count': len(p_elements),
                        'p_elements_details': [{'text': p.text.strip()[:50], 'class': p.get('class', [])} for p in p_elements] if p_elements else [],
                        'item_class': item.get('class', []) if hasattr(item, 'get') else 'unknown'
                    }
                    
                    self.logger.warning(
                        f"Erro ao processar item {idx} de {len(itens)} em {path}: {e}. "
                        f"Diagnóstico detalhado: {item_info}"
                    )
                    continue

            return pd.DataFrame(lista_infos, columns=columns)
            
        except Exception as e:
            self.logger.error(f"Error parsing page {path}: {e}")
            return pd.DataFrame(columns=columns)