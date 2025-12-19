from typing import Any, Literal
import json

import pandas as pd

from ..base_scraper import BaseScraper


class comunicaCNJ_Scraper(BaseScraper):
    """Raspador para o site de Comunicações Processuais do Conselho Nacional de Justiça."""

    def __init__(self):
        super().__init__("CNJ")

        self._api_base = 'https://comunicaapi.pje.jus.br/api/v1/comunicacao'
        self._type = 'JSON'
        self._query_page_name = 'pagina'
        self._api_method = 'GET'

        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,en-US;q=0.7,en;q=0.3",
            "Connection": "keep-alive",
            "Origin": "https://comunica.pje.jus.br",
            "Referer": "https://comunica.pje.jus.br/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"
        })

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['JSON', 'HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET', 'POST']:
        return self._api_method

    def _set_query_base(self, **kwargs):
        pesquisa = kwargs.get('pesquisa')
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')

        query_inicial = {
                'itensPorPagina': 5,
                'texto': pesquisa,
            }
        
        if data_inicio is not None:
            query_inicial['dataDisponibilizacaoInicio'] = data_inicio

        if data_fim is not None :
            query_inicial['dataDisponibilizacaoFim'] = data_fim

        return query_inicial
        
    def _find_n_pags(self, r0):
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()
        try:
            data = r0.json()
            contagem = data.get('count', data.get('total'))
            if contagem is None:
                raise KeyError
            return (contagem // 5) + 1
        except json.JSONDecodeError:
            self.logger.error(f"Failed to decode JSON response. Response text: {r0.text}")
            raise
        except KeyError:
            self.logger.error("JSON response is missing 'count' or 'total' key")
            raise ValueError("JSON response is missing the expected 'count' or 'total' key.")
    
    def _parse_page(self, path: str):
        with open(path, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        
        lista_infos = []
        infos_processos = dados.get('itens', [])

        for processo in infos_processos:
            lista_infos.append(processo)

        return pd.DataFrame(lista_infos)