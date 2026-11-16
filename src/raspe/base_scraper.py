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

import time
import warnings
from abc import abstractmethod
from typing import Any, ClassVar, Literal

import pandas as pd
import requests
from tqdm import tqdm

from raspe.abstract_scraper import AbstractScraper
from raspe.exceptions import APIError, RateLimitError, ScraperError
from raspe.utils import dividir_periodo, nivel_de_pilha_fora_do_pacote, start_session


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
        max_retries: Número máximo de tentativas para rate limit, erros 5xx e falhas de rede.
        max_retry_after: Espera máxima, em segundos, pedida pelo header Retry-After de um 429.
    """

    # Coluna que identifica o registro na fonte, para a busca dividida em várias consultas
    # (ver _coletar) não repetir linha. ``None`` não tira repetição.
    coluna_id: ClassVar[str | None] = None

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
        self.max_retry_after: int = 300

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

    def _raspar(self, **kwargs) -> pd.DataFrame:
        """Baixa e lê as páginas de resultado, uma busca por item quando um parâmetro é lista.

        A busca única segue o caminho de :meth:`AbstractScraper._raspar`. Exceções e
        avisos estão documentados em :meth:`AbstractScraper.raspar`.

        Args:
            **kwargs: Parâmetros já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            pd.DataFrame: DataFrame combinado com todos os dados raspados.
        """
        self.logger.info(f"Iniciando raspagem com parâmetros {kwargs}")
        # Suporte a lista de valores de busca
        list_keys = [k for k, v in kwargs.items() if isinstance(v, (list, tuple)) and k != "paginas"]
        if list_keys:
            if len(list_keys) > 1:
                raise ValueError("raspar() só suporta lista de valores de busca para um parâmetro")
            key = list_keys[0]
            static_kwargs = {k: v for k, v in kwargs.items() if k != key}
            dfs: list[pd.DataFrame] = []
            erros: list[tuple[Any, Exception]] = []
            nao_tentados: list[Any] = []
            for i, val in enumerate(kwargs[key]):
                self.logger.info(f"Iniciando raspagem para {key}={val}")
                loop_kwargs = {**static_kwargs, key: val}
                # Um termo que falha não descarta os já coletados: segue para os demais
                # e avisa no fim. Erros de programação (fora destas classes) sobem direto.
                try:
                    df = self._coletar(**loop_kwargs)
                except (ScraperError, requests.RequestException) as e:
                    self.logger.error(f"Raspagem de {key}={val} falhou: {e}")
                    erros.append((val, e))
                    if isinstance(e, RateLimitError):
                        # Insistir nos demais valores só agravaria o bloqueio.
                        nao_tentados = list(kwargs[key][i + 1:])
                        break
                    continue

                termo_busca_val = str(val)
                df = df.assign(termo_busca=termo_busca_val)
                self.logger.debug(f"Adicionada coluna termo_busca={termo_busca_val} aos resultados")

                dfs.append(df)
            if erros:
                if not dfs:
                    # Nenhum termo foi coletado: não há resultado parcial a preservar.
                    raise erros[0][1]
                aviso = (
                    f"{self.nome_buscador}: {len(erros)} de {len(kwargs[key])} valores de '{key}' falharam "
                    "e ficaram fora do resultado: "
                    + "; ".join(f"{val!r} ({type(e).__name__}: {e})" for val, e in erros)
                )
                if nao_tentados:
                    aviso += f". Por causa do rate limit, ficaram sem coletar: {nao_tentados!r}"
                warnings.warn(aviso, stacklevel=nivel_de_pilha_fora_do_pacote())
            if not dfs:
                return pd.DataFrame(columns=[*self.colunas, 'termo_busca'])
            # Termos sem resultados entram só se todos vierem vazios: concatenar um DataFrame
            # vazio (colunas object) com os demais alargaria os tipos das colunas.
            return pd.concat([df for df in dfs if not df.empty] or dfs, ignore_index=True)
        return super()._raspar(**kwargs)

    def _dividir_busca(self, **kwargs) -> list[dict[str, Any]]:
        """Divide a busca nas consultas que a fonte aceita; por padrão, uma só.

        A subclasse sobrescreve quando a fonte limita o período de uma consulta
        (ver :meth:`_consultas_por_janela`).

        Args:
            **kwargs: Parâmetros já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            list[dict]: Os parâmetros de cada consulta, na ordem em que saem; ao menos uma.
        """
        return [kwargs]

    @staticmethod
    def _consultas_por_janela(
        parametros: dict[str, Any], data_inicio: str, data_fim: str, meses: int
    ) -> list[dict[str, Any]]:
        """Repete a busca em janelas seguidas do período (ver :func:`raspe.utils.dividir_periodo`).

        Args:
            parametros: Parâmetros da busca.
            data_inicio: Primeiro dia do período, em YYYY-MM-DD.
            data_fim: Último dia do período, em YYYY-MM-DD, não anterior a ``data_inicio``.
            meses: Maior período que a fonte aceita numa consulta.

        Returns:
            list[dict]: Os parâmetros com ``data_inicio`` e ``data_fim`` de cada janela.
        """
        return [
            {**parametros, 'data_inicio': inicio, 'data_fim': fim}
            for inicio, fim in dividir_periodo(data_inicio, data_fim, meses)
        ]

    def _coletar(self, **kwargs) -> pd.DataFrame:
        """Baixa e lê cada consulta de :meth:`_dividir_busca` e junta as linhas sem repetir.

        A consulta que falha interrompe a busca: seguir sem ela devolveria um
        período com um buraco. Linha repetida é a que tem o mesmo valor em
        ``coluna_id``; sem essa coluna declarada, nada é tirado.

        Args:
            **kwargs: Parâmetros já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            pd.DataFrame: As linhas de todas as consultas.
        """
        consultas = self._dividir_busca(**kwargs)
        if len(consultas) == 1:
            return super()._coletar(**consultas[0])
        self.logger.info(f"Busca dividida em {len(consultas)} consultas")
        dfs: list[pd.DataFrame] = []
        for i, consulta in enumerate(consultas):
            if i:
                time.sleep(self.sleep_time)
            dfs.append(super()._coletar(**consulta))
        # Como na busca por lista: consulta vazia só entra se todas vierem vazias.
        juntas = pd.concat([df for df in dfs if not df.empty] or dfs[:1], ignore_index=True)
        if self.coluna_id is None:
            return juntas
        return juntas.drop_duplicates(subset=self.coluna_id, ignore_index=True)

    def _levantar_se_recusada(self, r0: requests.Response) -> None:
        """Levanta ``APIError`` se a API recusou a consulta, com a explicação que ela dá.

        Serve às APIs que respondem o erro em JSON com o campo ``detail``; sem
        ele, a mensagem leva o corpo da resposta.

        Args:
            r0: Resposta da página 1.

        Raises:
            APIError: Se o status for de erro (400 ou mais).
        """
        if r0.status_code < 400:
            return
        try:
            detalhe = r0.json()['detail']
        except (ValueError, KeyError, TypeError):
            detalhe = r0.text
        raise APIError(
            f"{self.nome_buscador}: a API recusou a consulta (HTTP {r0.status_code}): {detalhe}",
            status_code=r0.status_code,
            response_text=r0.text,
        )

    def _download_data(self, **kwargs) -> str:
        """Pede a página 1, conta as páginas por ela e baixa as de ``paginas``.

        A página 1 é pedida uma vez só: a mesma resposta dá a contagem e, se
        ``paginas`` a inclui, é gravada como página 1.

        Args:
            **kwargs: Parâmetros já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            str: Pasta com as páginas baixadas.

        Raises:
            RateLimitError: Se o rate limit (429) persistir após todas as tentativas.
            APIError: Se o erro de servidor (5xx) persistir após todas as tentativas.
            requests.RequestException: Se uma página falhar com outro erro HTTP ou de rede.
            ScraperError: Se a página 1 não traz a contagem nem o aviso de busca vazia
                (ver :meth:`HTMLScraper._confirmar_busca_vazia`).
        """
        self.logger.debug("Definindo consulta")
        query_base = self._set_query_base(**kwargs)
        self.logger.debug(query_base)

        self.logger.debug("Definindo n_pags")
        # A contagem vem da própria página 1, que o laço grava sem pedir de novo.
        r0 = self._request_with_retry(self._set_query_atual(query_base, 1))
        self.logger.debug(f"Encontrando n_pags (status: {r0.status_code})")
        n_pags = self._find_n_pags(r0)
        self.logger.debug(f"Encontradas {n_pags} páginas")

        self.logger.debug("Definindo paginas")
        paginas = kwargs.get("paginas")
        paginas = self._set_paginas(paginas, n_pags)

        # Verificação de sanidade - certifique-se de que paginas é iterável
        if not hasattr(paginas, '__iter__'):
            self.logger.error(f"paginas não é iterável: {paginas}")
            paginas = range(0)  # range vazio como fallback

        download_dir = self._create_download_dir()

        # Força a conversão para lista para garantir que tqdm funcione corretamente
        total_pages = list(paginas)

        for pag in tqdm(total_pages, desc="Baixando documentos"):
            # Página que falha (429 ou 5xx depois das tentativas, outro 4xx, erro de rede)
            # interrompe a coleta: pular a página truncaria o resultado em silêncio. Com
            # Ctrl+C também, e sem debug a pasta sai.
            try:
                if pag == 1:
                    self.logger.debug("Página 1 já baixada com a contagem")
                    r = r0
                else:
                    time.sleep(self.sleep_time)
                    self.logger.debug(f"Baixando página {pag}")

                    query_atual = self._set_query_atual(query_base, pag)
                    self.logger.debug(query_atual)

                    r = self._request_with_retry(query_atual)
                self.logger.debug(f"Response status: {r.status_code}")
                r.raise_for_status()

                file_name = f"{download_dir}/{self.nome_buscador}_{pag:05d}.{self.type.lower()}"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(r.text)
                self.logger.debug(f"Arquivo salvo: {file_name}")
            except BaseException:
                self.logger.error(
                    f"Coleta interrompida na página {pag}. {self._onde_ficam_os_arquivos(download_dir)}"
                )
                self._apagar_sem_debug(download_dir)
                raise

        return download_dir

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

    def _set_query_atual(self, query_real: dict[str, Any], pag: int) -> dict[str, Any]:
        # Cópia rasa para não mutar o dicionário do caller (valores são str/int).
        query_atual = dict(query_real)

        query_atual[self.query_page_name] = pag * self.query_page_multiplier + self.query_page_increment

        if self.old_page_name is not None:
            query_atual[self.old_page_name] = query_atual[self.query_page_name] - 1

        return query_atual

    def _set_r(self, query_atual) -> requests.Response:
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

        Implementa exponential backoff para erros 429 (rate limit), 5xx (servidor)
        e falhas de conexão. Para 429, tenta usar o header Retry-After
        se disponível, limitado a ``self.max_retry_after`` segundos.

        Args:
            query: Parâmetros da requisição.
            max_retries: Número máximo de tentativas. Se None, usa self.max_retries.

        Returns:
            requests.Response: Resposta da requisição.

        Raises:
            RateLimitError: Se o rate limit persistir após todas as tentativas.
            APIError: Se ocorrer erro de servidor após todas as tentativas.
            requests.ConnectionError: Se a conexão falhar em todas as tentativas.
            requests.ReadTimeout: Se o servidor não responder dentro de ``self.timeout``.
        """
        retries = max_retries if max_retries is not None else self.max_retries

        for attempt in range(retries):
            try:
                r = self._set_r(query)
            except requests.ConnectionError as e:
                # Inclui ConnectTimeout. O ReadTimeout sobe direto: o servidor recebeu o
                # pedido e travou, e repetir só multiplicaria a espera.
                if attempt == retries - 1:
                    raise
                self.logger.warning(
                    f"Falha de rede ({type(e).__name__}). Aguardando {2 ** attempt}s "
                    f"(tentativa {attempt + 1}/{retries})"
                )
                time.sleep(2 ** attempt)
                continue

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
                wait_time = min(wait_time, self.max_retry_after)

                if attempt < retries - 1:
                    self.logger.warning(
                        f"Rate limit (429). Aguardando {wait_time}s antes de tentar novamente "
                        f"(tentativa {attempt + 1}/{retries})"
                    )
                    time.sleep(wait_time)
                    continue
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
            dict: Parâmetros de consulta comuns a todas as páginas; o de página entra em
            :meth:`_set_query_atual`.
        """
        ...

    @abstractmethod
    def _find_n_pags(self, r0: requests.Response) -> int:
        """Determina o número total de páginas a serem raspadas.

        Este método deve ser implementado pelas subclasses para analisar a resposta
        inicial e determinar quantas páginas de dados estão disponíveis.

        Args:
            r0: A resposta da página 1, da API ou do site.

        Returns:
            int: Número total de páginas a serem raspadas.
        """
        ...
