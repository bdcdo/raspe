"""
Módulo base para scrapers baseados em requisições HTTP.

Este módulo fornece a classe BaseScraper, que estende AbstractScraper
para scrapers que usam requisições HTTP (via requests). Gerencia tarefas como
gerenciamento de sessão, paginação via query params, tentativas com retry
e operações de arquivo.

Exemplo de uso:
    class MeuScraper(BaseScraper):
        def __init__(self):
            super().__init__("meu_scraper")
            self._api_base = "https://api.exemplo.com/dados"
            self._type = 'JSON'

        def _set_query_base(self, **kwargs) -> dict[str, Any]:
            return {"consulta": kwargs.get("termo_busca")}

        def _find_n_pags(self, response) -> int:
            return response.json().get("total_paginas", 1)

        def _parse_page(self, path: str) -> pd.DataFrame:
            # Implementação da análise dos dados baixados
            ...
"""

from abc import abstractmethod
from typing import Any, Literal
from tqdm import tqdm
from raspe.abstract_scraper import AbstractScraper
from raspe.utils import start_session
from raspe.exceptions import RateLimitError, APIError
import pandas as pd
import requests
import shutil
import time
import json

class BaseScraper(AbstractScraper):
    """Classe base para scrapers baseados em requisições HTTP.

    Estende AbstractScraper com funcionalidades específicas para web scraping
    via requisições HTTP, incluindo gerenciamento de sessão requests,
    paginação via query params e retry automático.

    Args:
        nome_buscador: Identificador único para a instância do scraper.
        debug: Se True, ativa logs de depuração e mantém arquivos baixados.

    Atributos:
        session: Instância de requests.Session para fazer requisições HTTP.
        api_base: URL base da API ou site a ser raspado.
        sleep_time: Atraso entre requisições em segundos.
        query_page_name: Nome do parâmetro de consulta usado para paginação.
        query_page_multiplier: Multiplicador para números de página na paginação.
        query_page_increment: Valor a ser adicionado aos números de página.
        timeout: Tupla (connect_timeout, read_timeout) para requisições.
        api_method: Método HTTP a ser usado nas requisições ('GET' ou 'POST').
        old_page_name: Nome do parâmetro para a página anterior.
        max_retries: Número máximo de tentativas para rate limit e erros 5xx.
    """

    def __init__(self, nome_buscador: str, debug: bool = True):
        """Inicializa o BaseScraper com configuração HTTP."""
        super().__init__(nome_buscador, debug)

        # Atributos específicos de HTTP
        self.session: requests.Session = start_session()
        self.sleep_time: int = 2
        self.query_page_multiplier: int = 1
        self.query_page_increment: int = 0
        self.timeout: tuple[int, int] = (10, 30)
        self.old_page_name: str | None = None
        self.max_retries: int = 3

        # Propriedades a serem definidas pelas subclasses
        self._api_base: str
        self._type: Literal['JSON', 'HTML']
        self._query_page_name: str
        self._api_method: Literal['GET', 'POST']

    @property
    @abstractmethod
    def api_base(self) -> str:
        ...

    @property
    @abstractmethod
    def type(self) -> Literal['JSON', 'HTML']:
        ...

    @property
    @abstractmethod
    def query_page_name(self) -> str:
        ...

    @property
    @abstractmethod
    def api_method(self) -> Literal['GET', 'POST']:
        ...

    def raspar(self, **kwargs) -> pd.DataFrame:
        """Método principal para executar o processo de raspagem de dados.

        Args:
            **kwargs: Parâmetros de busca para o raspador. Se algum parâmetro for
                uma lista/tupla, o raspador processará cada valor na sequência.
                O parâmetro especial 'paginas' pode ser um objeto range para
                especificar as páginas.

        Returns:
            pd.DataFrame: DataFrame combinado com todos os dados raspados.

        Raises:
            ValueError: Se múltiplos parâmetros forem fornecidos como listas/tuplas.
            ValidationError: Se algum parâmetro for inválido.
        """

        # Valida parâmetros antes de iniciar
        kwargs = self._validar_parametros(**kwargs)

        self.logger.info(f"Iniciando raspagem com parâmetros {kwargs}")
        # Suporte a lista de valores de busca
        list_keys = [k for k, v in kwargs.items() if isinstance(v, (list, tuple)) and k != "paginas"]
        if list_keys:
            if len(list_keys) > 1:
                raise ValueError("raspar() só suporta lista de valores de busca para um parâmetro")
            key = list_keys[0]
            static_kwargs = {k: v for k, v in kwargs.items() if k != key}
            dfs: list[pd.DataFrame] = []
            for val in kwargs[key]:
                self.logger.info(f"Iniciando raspagem para {key}={val}")
                loop_kwargs = {**static_kwargs, key: val}
                path_result = self._download_data(**loop_kwargs)
                df = self._parse_data(path_result)
                
                termo_busca_val = str(val)
                df = df.assign(termo_busca=termo_busca_val)
                self.logger.debug(f"Adicionada coluna termo_busca={termo_busca_val} aos resultados")
                
                dfs.append(df)
                if self.debug is False:
                    shutil.rmtree(path_result)
            result = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
                
            return result
        # Fallback para busca única
        else:
            path_result = self._download_data(**kwargs)
            result = self._parse_data(path_result)

            # Determina qual parâmetro contém o termo de busca
            termo_param = next((k for k in kwargs if k in ['pesquisa', 'termo', 'q', 'query']), None)
            if termo_param:
                termo_busca = str(kwargs[termo_param])
                result = result.assign(termo_busca=termo_busca)
                self.logger.debug(f"Adicionada coluna termo_busca={termo_busca} aos resultados")

            self.logger.info(f"Raspagem finalizada, limpando diretório {path_result}")
            if self.debug is False:
                shutil.rmtree(path_result)
            
            return result

    def _download_data(self, **kwargs) -> str:
        self.logger.debug(f"Definindo consulta")
        query_base = self._set_query_base(**kwargs)
        self.logger.debug(query_base)
        
        self.logger.debug(f"Definindo n_pags")
        n_pags = self._get_n_pags(query_base)

        self.logger.debug(f"Definindo paginas")
        paginas = kwargs.get("paginas")
        paginas = self._set_paginas(paginas, n_pags)

        # Verificação de sanidade - certifique-se de que paginas é iterável
        if not hasattr(paginas, '__iter__'):
            self.logger.error(f"paginas não é iterável: {paginas}")
            paginas = range(0) # range vazio como fallback

        download_dir = self._create_download_dir()      

        # Força a conversão para lista para garantir que tqdm funcione corretamente
        total_pages = list(paginas)
        
        for pag in tqdm(total_pages, desc="Baixando documentos"):
            time.sleep(self.sleep_time)
            self.logger.debug(f"Baixando página {pag}")

            query_atual = self._set_query_atual(query_base, pag)
            self.logger.debug(query_atual)

            try:
                r = self._set_r(query_atual)
                self.logger.debug(f"Response status: {r.status_code}")
                
                # Se erro de servidor, registra e pula esta página
                if r.status_code >= 500:
                    self.logger.warning(f"Server error {r.status_code} para URL {r.url}, ignorando página {pag}")
                    continue

                file_name = f"{download_dir}/{self.nome_buscador}_{pag:05d}.{self.type.lower()}"
                
                with open(file_name, "w", encoding="utf-8") as f:
                    # Write response content: use text or JSON dump fallback
                    content = r.text if r.text and r.text.strip() else json.dumps(r.json(), ensure_ascii=False)
                    f.write(content)
                self.logger.debug(f"Arquivo salvo: {file_name}")
                
            except Exception as e:
                self.logger.error(f"Erro ao baixar página {pag}: {e}")
                continue

        return download_dir

    def _get_n_pags(self, query_inicial):
        """
        Obtém o número total de páginas para uma consulta.

        Usa _request_with_retry() para fazer a requisição inicial com retry
        automático para erros de rate limit (429) e erros de servidor (5xx).

        Args:
            query_inicial: Dicionário com a query a ser enviada para a API.

        Returns:
            int: Número total de páginas encontradas para a consulta.
                 Retorna 0 em caso de erro.
        """
        self.logger.debug("Enviando requisição inicial com retry automático")

        try:
            r0 = self._request_with_retry(query_inicial)
        except (RateLimitError, APIError) as e:
            self.logger.error(f"Erro na requisição inicial: {e}")
            return 0

        self.logger.debug(f"Encontrando n_pags (status: {r0.status_code})")
        contagem = self._find_n_pags(r0)

        if contagem is None:
            self.logger.error(f"Erro ao extrair n_pags: {r0.text[:200] if r0.text else 'sem conteúdo'}")
            contagem = 0

        self.logger.debug(f"Encontradas {contagem} páginas")
        return contagem

    def _set_paginas(self, paginas, n_pags):
        # TODO: repensar essa escolha
        if n_pags is None:
            self.logger.warning("n_pags é None, definindo como 0")
            n_pags = 0
        
        # Se não especificado, pega todas as páginas
        if paginas is None:
            paginas = range(1, n_pags + 1)
        else:
            start, stop, step = paginas.start, min(paginas.stop, n_pags + 1), paginas.step
            paginas = range(start, stop, step)
        return paginas

    def _set_query_atual(self, query_real, pag) -> dict[str, str]:
        query_atual = query_real
        
        query_atual[self.query_page_name] = pag * self.query_page_multiplier + self.query_page_increment
        
        if self.old_page_name is not None:
            query_atual[self.old_page_name] = query_atual[self.query_page_name] - 1
        
        return query_atual

    def _set_r(self, query_atual):
        if self.api_method == 'POST':
            r = self.session.post(
                self.api_base,
                data=query_atual,
                timeout=self.timeout
            )
        elif self.api_method == 'GET':
            r = self.session.get(
                self.api_base,
                params=query_atual,
                timeout=self.timeout
            )
        else:
            raise ValueError(f"Método de API inválido: {self.api_method}")

        return r

    def _request_with_retry(self, query: dict, max_retries: int | None = None) -> requests.Response:
        """Faz uma requisição com retry automático para rate limit e erros de servidor.

        Implementa exponential backoff para erros 429 (rate limit) e 5xx (servidor).
        Para 429, tenta usar o header Retry-After se disponível.

        Args:
            query: Parâmetros da requisição.
            max_retries: Número máximo de tentativas. Se None, usa self.max_retries.

        Returns:
            requests.Response: Resposta da requisição.

        Raises:
            RateLimitError: Se o rate limit persistir após todas as tentativas.
            APIError: Se ocorrer erro de servidor após todas as tentativas.
        """
        retries = max_retries if max_retries is not None else self.max_retries

        for attempt in range(retries):
            r = self._set_r(query)

            # Sucesso ou erro de cliente (exceto 429)
            if r.status_code < 400 or (400 <= r.status_code < 500 and r.status_code != 429):
                return r

            # Rate limit (429)
            if r.status_code == 429:
                retry_after = r.headers.get('Retry-After')
                if retry_after:
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 2 ** attempt
                else:
                    wait_time = 2 ** attempt

                if attempt < retries - 1:
                    self.logger.warning(
                        f"Rate limit (429). Aguardando {wait_time}s antes de tentar novamente "
                        f"(tentativa {attempt + 1}/{retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise RateLimitError(
                        f"Rate limit excedido após {retries} tentativas. "
                        f"Aguarde alguns minutos antes de tentar novamente.",
                        retry_after=int(retry_after) if retry_after else None
                    )

            # Erro de servidor (5xx)
            if r.status_code >= 500:
                wait_time = 2 ** attempt
                if attempt < retries - 1:
                    self.logger.warning(
                        f"Erro de servidor ({r.status_code}). Aguardando {wait_time}s "
                        f"(tentativa {attempt + 1}/{retries})"
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise APIError(
                        f"Erro de servidor após {retries} tentativas",
                        status_code=r.status_code,
                        response_text=r.text
                    )

        return r

    @abstractmethod
    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Cria os parâmetros base para a requisição à API.
        
        Este método deve ser implementado pelas subclasses para definir como
        construir os parâmetros iniciais da consulta com base nos argumentos
        fornecidos.
        
        Args:
            **kwargs: Parâmetros de busca passados para o método scrape().
            
        Returns:
            dict: Parâmetros de consulta para a requisição inicial à API.
        """
        ...

    @abstractmethod
    def _find_n_pags(self, r0: requests.Response) -> int:
        """Determina o número total de páginas a serem raspadas.

        Este método deve ser implementado pelas subclasses para analisar a resposta
        inicial e determinar quantas páginas de dados estão disponíveis.

        Args:
            r0: A resposta inicial da API ou website.

        Returns:
            int: Número total de páginas a serem raspadas.
        """
        ...