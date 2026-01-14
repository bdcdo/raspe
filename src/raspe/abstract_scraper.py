"""
Módulo com a classe abstrata base para todos os scrapers.

Este módulo fornece a classe AbstractScraper, que define a interface comum
e funcionalidades compartilhadas entre scrapers HTTP (BaseScraper) e
scrapers baseados em Selenium (SeleniumScraper).
"""

from abc import ABC, abstractmethod
from typing import Any, Literal
from datetime import datetime
from tqdm import tqdm
from raspe.utils import validar_intervalo_datas
from raspe.exceptions import ValidationError
import pandas as pd
import os
import glob
import logging
import tempfile


class AbstractScraper(ABC):
    """Classe abstrata base para todos os tipos de scrapers.

    Fornece funcionalidades comuns como logging, validação de parâmetros,
    gerenciamento de diretórios de download e parsing de dados.

    Subclasses:
        - BaseScraper: Para scrapers baseados em requisições HTTP (requests)
        - SeleniumScraper: Para scrapers baseados em automação de navegador

    Args:
        nome_buscador: Identificador único para a instância do scraper.
        debug: Se True, ativa logs de depuração e mantém arquivos baixados.

    Atributos:
        nome_buscador: Nome identificador do scraper.
        download_path: Diretório base para arquivos temporários.
        debug: Flag para modo de depuração.
        exclude_cols_from_dedup: Colunas a excluir na deduplicação.
        logger: Logger configurado para o scraper.
    """

    def __init__(self, nome_buscador: str, debug: bool = True):
        """Inicializa o AbstractScraper com configuração comum."""
        self.nome_buscador: str = nome_buscador
        self.download_path: str = tempfile.mkdtemp()
        self.debug: bool = debug
        self.exclude_cols_from_dedup: list[str] = []

        self._start_logger()

    @property
    @abstractmethod
    def type(self) -> Literal['JSON', 'HTML']:
        """Tipo de arquivo de dados baixados ('JSON' ou 'HTML')."""
        ...

    def _start_logger(self) -> None:
        """Configura o logger para o scraper."""
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

    @abstractmethod
    def raspar(self, **kwargs) -> pd.DataFrame:
        """Método principal para executar o processo de raspagem de dados.

        Args:
            **kwargs: Parâmetros de busca para o raspador.

        Returns:
            pd.DataFrame: DataFrame com os dados raspados.
        """
        ...

    def scrape(self, **kwargs) -> pd.DataFrame:
        """Alias para raspar() mantido para retrocompatibilidade.

        Este método existe apenas para manter compatibilidade com código antigo.
        Use raspar() em novos projetos.
        """
        return self.raspar(**kwargs)
