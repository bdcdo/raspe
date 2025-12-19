"""
Módulo base para funcionalidades de web scraping.

Este módulo fornece a classe base abstrata BaseScraper, que serve como fundamento
para construção de web scrapers de buscadores. Gerencia tarefas comuns
como gerenciamento de sessão, paginação, tentativas de requisição e operações de arquivo.

Exemplo de uso:
    class MeuScraper(BaseScraper):
        def __init__(self):
            super().__init__("meu_scraper")
            self.api_base = "https://api.exemplo.com/dados"
            self.type = 'json'  # ou 'html' se usar HTMLScraper

        def _set_query_base(self, **kwargs) -> dict[str, Any]:
            return {"consulta": kwargs.get("termo_busca")}

        def _find_n_pags(self, response) -> int:
            return response.json().get("total_paginas", 1)

        def _parse_page(self, path: str) -> pd.DataFrame:
            # Implementação da análise dos dados baixados
            ...
"""

from abc import ABC, abstractmethod
from typing import Any, Literal
from datetime import datetime
from tqdm import tqdm
from raspe.utils import start_session, validar_intervalo_datas
from raspe.exceptions import RateLimitError, APIError, ValidationError
import pandas as pd
import requests
import os
import shutil
import time
import logging
import glob
import json
import tempfile

class BaseScraper(ABC):
    """Classe base para criação de web scrapers.
    
    Fornece funcionalidades comuns para tarefas de web scraping, incluindo
    gerenciamento de sessão, paginação, tentativas de requisição e operações
    de arquivo. As subclasses devem implementar os métodos abstratos para
    definir o comportamento específico de scraping.
    
    Args:
        nome_buscador: Identificador único para a instância do scraper.
        debug: Se True, ativa logs de depuração e mantém arquivos baixados.
    
    Atributos:
        session: Instância de requests.Session para fazer requisições HTTP.
        api_base: URL base da API ou site a ser raspado.
        download_path: Diretório onde os arquivos baixados serão armazenados.
        sleep_time: Atraso entre requisições em segundos.
        type: Tipo do arquivo de dados baixados ('json', 'html', etc.).
        query_page_name: Nome do parâmetro de consulta usado para paginação.
        query_page_multiplier: Multiplicador para números de página na paginação.
        query_page_increment: Valor a ser adicionado aos números de página.
        debug: Flag para modo de depuração.
        timeout: Tupla (connect_timeout, read_timeout) para requisições.
        api_method: Método HTTP a ser usado nas requisições ('GET' ou 'POST').
        old_page_name: Nome do parâmetro para a página anterior.
    """
    
    def __init__(self, nome_buscador: str, debug: bool = True):
        """Inicializa o BaseScraper com configuração comum."""
        self.nome_buscador: str = nome_buscador
        self.download_path: str = tempfile.mkdtemp()
        self.session: requests.Session = start_session()
        self.sleep_time: int = 2
        self.query_page_multiplier: int = 1
        self.query_page_increment: int = 0
        self.debug: bool = debug
        self.timeout: tuple[int, int] = (10, 30)
        self.old_page_name: str | None = None
        self.exclude_cols_from_dedup: list[str] = []
        self.max_retries: int = 3

        self._api_base: str # Deve ser definido pela subclasse
        self._type: Literal['JSON'] | Literal ['HTML'] # Deve ser definido pela subclasse
        self._query_page_name: str # Deve ser definido pela subclasse
        self._api_method: Literal['GET'] | Literal['POST']

        self._start_logger()

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

    def _start_logger(self):
        # Configuração do logger
        self.logger = logging.getLogger(self.nome_buscador)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.propagate = False
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

    def _validar_parametros(self, **kwargs) -> dict[str, Any]:
        """Valida e normaliza parâmetros de busca antes da raspagem.

        Este método valida parâmetros comuns como datas. Subclasses podem
        sobrescrever para adicionar validações específicas, mas devem chamar
        super()._validar_parametros(**kwargs) para manter as validações base.

        Args:
            **kwargs: Parâmetros de busca a serem validados.

        Returns:
            dict: Parâmetros validados e normalizados.

        Raises:
            ValidationError: Se algum parâmetro for inválido.
        """
        params = dict(kwargs)

        # Valida parâmetros de data comuns
        # Detecta automaticamente parâmetros que parecem ser datas
        data_params = [
            ('data_inicio', 'data_fim'),
            ('data_inicial', 'data_final'),
            ('inicio', 'fim'),
            ('begin_date', 'end_date'),
        ]

        for inicio_key, fim_key in data_params:
            if inicio_key in params or fim_key in params:
                data_inicio = params.get(inicio_key)
                data_fim = params.get(fim_key)

                inicio_norm, fim_norm = validar_intervalo_datas(
                    data_inicio, data_fim,
                    nome_inicio=inicio_key,
                    nome_fim=fim_key
                )

                if inicio_norm:
                    params[inicio_key] = inicio_norm
                if fim_norm:
                    params[fim_key] = fim_norm

        return params

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

    def scrape(self, **kwargs) -> pd.DataFrame:
        """Alias para raspar() mantido para retrocompatibilidade.

        Este método existe apenas para manter compatibilidade com código antigo.
        Use raspar() em novos projetos.
        """
        return self.raspar(**kwargs)

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
        
    def _parse_data(self, path: str) -> pd.DataFrame:
        """Analisa os dados de um arquivo ou diretório e os consolida em um DataFrame.

        Se 'path' for um arquivo, ele será processado diretamente. Se for um diretório,
        todos os arquivos correspondentes a 'self.type' dentro do diretório (recursivamente)
        serão processados.

        Args:
            path: Caminho para o arquivo ou diretório contendo os dados a serem analisados.

        Returns:
            pd.DataFrame: DataFrame consolidado com todos os dados analisados.
        """
        self.logger.debug(f"Analisando dados de: {path}")
        
        result = []
        arquivos = glob.glob(f"{path}/**/*.{self.type.lower()}", recursive=True)
        arquivos = [f for f in arquivos if os.path.isfile(f)]

        for file in tqdm(arquivos, desc="Processando documentos"):
            try:
                single_result = self._parse_page(file)
            except Exception as e:
                self.logger.error(f"Erro ao processar {file}: {e}")
                single_result = None
                continue

            if single_result is not None:
                result.append(single_result)
        
        if not result:
            return pd.DataFrame()
        
        return pd.concat(result, ignore_index=True)

    @abstractmethod
    def _parse_page(self, path: str) -> pd.DataFrame:
        """Analisa uma única página de dados baixados.
        
        Este método deve ser implementado pelas subclasses para definir como
        converter os dados baixados em um DataFrame do pandas.
        
        Args:
            path: Caminho para o arquivo baixado a ser analisado.
            
        Returns:
            pd.DataFrame: Dados analisados como um DataFrame.
        """
        ...

    
    def _create_download_dir(self) -> str:
        """Cria um diretório para armazenar os arquivos baixados.
        
        Gera um caminho único usando um timestamp para garantir que cada
        sessão de scraping tenha seu próprio diretório.
        
        Returns:
            str: Caminho do diretório criado.
        """
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        path = f"{self.download_path}/{self.nome_buscador}/{timestamp}"
        os.makedirs(path)
        self.logger.debug(f"Criando diretório de download em {path}")
        return path