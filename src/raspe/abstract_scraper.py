"""
Módulo com a classe abstrata base para todos os scrapers.

Este módulo fornece a classe AbstractScraper, que define a interface comum
e funcionalidades compartilhadas entre scrapers HTTP (BaseScraper) e
scrapers baseados em Selenium (SeleniumScraper).
"""

import glob
import logging
import os
import shutil
import sys
import tempfile
import warnings
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar, Literal

import pandas as pd
from tqdm import tqdm

from raspe.exceptions import ScraperError
from raspe.utils import validar_intervalo_datas


class _HandlerRaspe(logging.StreamHandler):
    """Handler de console do raspe, no logger pai ``raspe``.

    Escreve sempre no ``sys.stderr`` do momento (como o ``logging.lastResort``),
    para a saída acompanhar trocas do ``stderr`` feitas depois da importação,
    como as do Jupyter e do ``capsys`` do pytest.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stderr
        super().emit(record)


def _configurar_logger_raspe() -> None:
    """Põe o handler de console no logger ``raspe``. Roda uma vez, na importação.

    O logger ``raspe`` não propaga para o root (evita linhas duplicadas quando o
    usuário configura o ``logging``) e começa em DEBUG, para o filtro ficar com
    cada instância (ver ``_LoggerDaInstancia``). Depois disso o raspe não mexe
    mais nele: ``logging.getLogger("raspe").setLevel(logging.WARNING)`` silencia
    todas as fontes, e outras mudanças do usuário também ficam.
    """
    raiz = logging.getLogger("raspe")
    raiz.addHandler(_HandlerRaspe())
    raiz.propagate = False
    if raiz.level == logging.NOTSET:
        raiz.setLevel(logging.DEBUG)


_configurar_logger_raspe()


class _LoggerDaInstancia(logging.LoggerAdapter):
    """Logger de uma instância de raspador, com nível próprio.

    As instâncias de uma fonte compartilham o logger ``raspe.<FONTE>``. O nível
    (DEBUG com ``debug=True``, INFO sem) fica no adaptador, então criar uma nova
    instância não muda o que as anteriores mostram. O resto da API de
    ``logging.Logger`` (``addHandler``, ``handlers``...) vai para o logger da fonte.

    Args:
        logger: Logger ``raspe.<FONTE>``, compartilhado pelas instâncias da fonte.
        nivel: Nível mínimo das mensagens desta instância.
    """

    def __init__(self, logger: logging.Logger, nivel: int):
        super().__init__(logger, {})
        self.level = nivel

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.logger, nome)

    def isEnabledFor(self, level: int) -> bool:
        """Diz se uma mensagem de nível ``level`` sai por esta instância.

        Args:
            level: Nível da mensagem.

        Returns:
            bool: True se passa pelo nível da instância e pelo dos loggers pais.
        """
        return level >= self.level and self.logger.isEnabledFor(level)

    def getEffectiveLevel(self) -> int:
        """Nível efetivo: o mais alto entre o da instância e o dos loggers pais.

        Returns:
            int: Nível efetivo.
        """
        efetivo: int = self.logger.getEffectiveLevel()
        return max(self.level, efetivo)

    def setLevel(self, level: int | str) -> None:
        """Muda o nível só desta instância (o ``LoggerAdapter`` mudaria o logger compartilhado).

        Args:
            level: Nível, como ``logging.WARNING`` ou ``"WARNING"``.

        Raises:
            ValueError: Se ``level`` for um nome de nível desconhecido.
        """
        if isinstance(level, str):
            niveis = logging.getLevelNamesMapping()
            if level not in niveis:
                raise ValueError(f"Nível de log desconhecido: {level!r}")
            level = niveis[level]
        self.level = level


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
        download_path: Diretório base para arquivos temporários. Por padrão, uma
            pasta do ``tempfile.mkdtemp()``, criada na primeira busca.
        debug: Flag para modo de depuração.
        exclude_cols_from_dedup: Colunas a excluir na deduplicação.
        logger: Logger da instância (``logging.LoggerAdapter`` sobre ``raspe.<nome_buscador>``),
            com nível próprio.
        colunas: Colunas do DataFrame que o scraper devolve. Uma busca sem
            resultados devolve um DataFrame vazio com estas colunas.
    """

    colunas: ClassVar[list[str]] = []

    def __init__(self, nome_buscador: str, debug: bool = True):
        """Inicializa o AbstractScraper com configuração comum."""
        self.nome_buscador: str = nome_buscador
        self._download_path: str | None = None
        self._raiz_temporaria: str | None = None
        self.debug: bool = debug
        self.exclude_cols_from_dedup: list[str] = []

        self._start_logger()

    @property
    @abstractmethod
    def type(self) -> Literal['JSON', 'HTML']:
        """Tipo de arquivo de dados baixados ('JSON' ou 'HTML')."""
        ...

    def _start_logger(self) -> None:
        """Configura o logger para o scraper.

        As mensagens vão para o logger ``raspe.<nome_buscador>``, filho de
        ``raspe``, que tem o handler de console. O nível é de cada instância
        (ver ``_LoggerDaInstancia``). Para silenciar o raspe inteiro, use
        ``logging.getLogger("raspe").setLevel(logging.WARNING)``.
        """
        self.logger = _LoggerDaInstancia(
            logging.getLogger(f"raspe.{self.nome_buscador}"),
            logging.DEBUG if self.debug else logging.INFO,
        )

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

    @property
    def download_path(self) -> str:
        """Diretório base dos arquivos baixados (por padrão, criado com ``tempfile.mkdtemp()``)."""
        if self._download_path is None:
            self._download_path = self._raiz_temporaria = tempfile.mkdtemp()
        return self._download_path

    @download_path.setter
    def download_path(self, valor: str) -> None:
        self._download_path = valor

    def _limpar_download(self, path: str) -> None:
        """Apaga a pasta de uma busca e, se for a do raspe, a raiz temporária vazia.

        Remove ``path`` (``{download_path}/{nome_buscador}/{timestamp}``). Se o
        ``download_path`` é a raiz criada pelo ``mkdtemp()``, remove também a
        pasta da fonte e a raiz, quando ficam vazias. Numa pasta escolhida pelo
        usuário, só a pasta da busca sai.

        Args:
            path: Pasta criada por ``_create_download_dir``.
        """
        shutil.rmtree(path)
        raiz = self._raiz_temporaria
        if raiz is None or self._download_path != raiz:
            return
        for pasta in (os.path.dirname(path), raiz):
            try:
                os.rmdir(pasta)
            except OSError:
                break

    def _parse_data(self, path: str) -> pd.DataFrame:
        """Analisa os dados de um arquivo ou diretório e os consolida em um DataFrame.

        Se 'path' for um arquivo, ele será processado diretamente. Se for um diretório,
        todos os arquivos correspondentes a 'self.type' dentro do diretório (recursivamente)
        serão processados.

        Args:
            path: Caminho para o arquivo ou diretório contendo os dados a serem analisados.

        Returns:
            pd.DataFrame: DataFrame consolidado com todos os dados analisados. Sem
                arquivos, um DataFrame vazio com as colunas de ``self.colunas``.

        Raises:
            ScraperError: Se havia arquivos e nenhum rendeu linhas. Só se baixam
                páginas quando a contagem diz que há resultados, então isso indica
                layout novo ou páginas de bloqueio, não busca vazia.

        Warns:
            UserWarning: Se parte das páginas não rendeu linhas (erro de leitura ou
                página vazia), porque o resultado pode estar incompleto.
        """
        self.logger.debug(f"Analisando dados de: {path}")

        result = []
        sem_linhas = []
        arquivos = glob.glob(f"{path}/**/*.{self.type.lower()}", recursive=True)
        arquivos = sorted(f for f in arquivos if os.path.isfile(f))
        if not arquivos:
            return pd.DataFrame(columns=self.colunas)

        for file in tqdm(arquivos, desc="Processando documentos"):
            try:
                single_result = self._parse_page(file)
            except Exception as e:
                self.logger.error(f"Erro ao processar {file}: {e}")
                sem_linhas.append(file)
                continue

            if single_result is None or single_result.empty:
                sem_linhas.append(file)
            else:
                result.append(single_result)

        if not result:
            raise ScraperError(
                f"{self.nome_buscador}: nenhuma das {len(arquivos)} páginas baixadas rendeu resultados, "
                "embora a contagem indicasse que havia. O site pode ter mudado de layout ou devolvido "
                f"páginas de bloqueio; os arquivos ficam em {path}."
            )
        if sem_linhas:
            warnings.warn(
                f"{self.nome_buscador}: {len(sem_linhas)} de {len(arquivos)} páginas baixadas não renderam "
                "resultados (erro de leitura, página de bloqueio ou layout novo), e o resultado pode estar "
                f"incompleto. Páginas: {', '.join(os.path.basename(f) for f in sem_linhas)}.",
                stacklevel=3,
            )

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
