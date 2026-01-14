"""
Módulo base para scrapers baseados em Selenium.

Este módulo fornece a classe SeleniumScraper para automação de navegador,
suportando sites que requerem JavaScript, interação com formulários,
e navegação complexa.

Dependências:
    - selenium (instalação opcional: pip install raspe[selenium])

Exemplo de uso:
    class MeuScraperSelenium(SeleniumScraper):
        def __init__(self):
            super().__init__("meu_scraper", headless=True)
            self._url_base = "https://exemplo.com/busca"
            self._pagination_strategy = PaginationStrategy.NUMBERED_LINKS

        @property
        def url_base(self) -> str:
            return self._url_base

        def _executar_busca(self, **kwargs) -> None:
            self._preencher_campo(By.ID, "campo-busca", kwargs.get("termo"))
            self._clicar_elemento(By.ID, "btn-buscar")

        def _encontrar_total_paginas(self) -> int:
            # Lógica para determinar número de páginas
            return 1

        def _parse_page(self, path: str) -> pd.DataFrame:
            # Lógica para extrair dados do HTML
            ...
"""

from abc import abstractmethod
from typing import Literal
from enum import Enum
from contextlib import contextmanager
from datetime import datetime
import time
import os

from raspe.abstract_scraper import AbstractScraper
from raspe.html_scraper import HTMLScraper
from raspe.exceptions import SeleniumError, DriverNotInstalledError
import pandas as pd


def _import_selenium():
    """Importa Selenium de forma lazy.

    Returns:
        dict: Dicionário com módulos e classes do Selenium.

    Raises:
        DriverNotInstalledError: Se Selenium não estiver instalado.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import (
            TimeoutException,
            NoSuchElementException,
            WebDriverException,
        )
        return {
            'webdriver': webdriver,
            'Options': Options,
            'By': By,
            'WebDriverWait': WebDriverWait,
            'EC': EC,
            'TimeoutException': TimeoutException,
            'NoSuchElementException': NoSuchElementException,
            'WebDriverException': WebDriverException,
        }
    except ImportError:
        raise DriverNotInstalledError(
            "Selenium não está instalado. Instale com: pip install raspe[selenium]"
        )


class PaginationStrategy(Enum):
    """Estratégias de paginação suportadas pelo SeleniumScraper."""
    NUMBERED_LINKS = "numbered_links"   # Clica em links numerados (1, 2, 3...)
    NEXT_BUTTON = "next_button"         # Clica em botão "Próximo"
    LOAD_MORE = "load_more"             # Clica em "Carregar mais"
    INFINITE_SCROLL = "infinite_scroll"  # Rola a página para carregar mais
    NONE = "none"                        # Sem paginação


class SeleniumScraper(AbstractScraper, HTMLScraper):
    """Classe base para scrapers que usam automação de navegador.

    Fornece gerenciamento de WebDriver, opções anti-detecção,
    e diferentes estratégias de paginação para sites JavaScript.

    Args:
        nome_buscador: Identificador único para o scraper.
        debug: Se True, mantém navegador visível e arquivos baixados.
        headless: Se True, executa navegador em modo headless.
        anti_detection: Se True, aplica configurações anti-detecção.

    Atributos:
        driver: Instância do WebDriver (None até inicialização).
        wait_timeout: Tempo máximo de espera para elementos (segundos).
        page_load_wait: Tempo de espera após carregar página (segundos).
        between_pages_wait: Tempo de espera entre páginas (segundos).

    Exemplo:
        >>> class MeuScraper(SeleniumScraper):
        ...     @property
        ...     def url_base(self):
        ...         return "https://exemplo.com"
        ...
        ...     def _executar_busca(self, **kwargs):
        ...         # Implementação da busca
        ...         pass
        ...
        ...     def _encontrar_total_paginas(self):
        ...         return 1
        ...
        ...     def _parse_page(self, path):
        ...         # Implementação do parsing
        ...         return pd.DataFrame()
    """

    def __init__(
        self,
        nome_buscador: str,
        debug: bool = True,
        headless: bool = True,
        anti_detection: bool = True,
    ):
        """Inicializa o SeleniumScraper com configuração de navegador."""
        super().__init__(nome_buscador, debug)

        self._selenium = None  # Lazy loaded
        self._driver = None
        self._headless = headless
        self._anti_detection = anti_detection

        # Timeouts configuráveis
        self.wait_timeout: int = 15
        self.page_load_wait: float = 2.0
        self.between_pages_wait: float = 3.0

        # Tipo sempre HTML para scrapers Selenium
        self._type: Literal['HTML'] = 'HTML'

        # Estratégia de paginação padrão
        self._pagination_strategy: PaginationStrategy = PaginationStrategy.NONE
        self._max_pages: int = 100  # Limite de segurança

    @property
    def type(self) -> Literal['HTML']:
        """Tipo de arquivo baixado (sempre HTML para Selenium)."""
        return self._type

    @property
    def driver(self):
        """Instância do WebDriver (inicializada sob demanda)."""
        return self._driver

    @property
    @abstractmethod
    def url_base(self) -> str:
        """URL inicial para o scraper."""
        ...

    @property
    def pagination_strategy(self) -> PaginationStrategy:
        """Estratégia de paginação a ser usada."""
        return self._pagination_strategy

    # =========================================================================
    # Gerenciamento do WebDriver
    # =========================================================================

    def _get_chrome_options(self):
        """Configura opções do Chrome com anti-detecção opcional.

        Returns:
            Options: Objeto Options configurado para o Chrome.
        """
        sel = self._ensure_selenium()
        options = sel['Options']()

        # Opções básicas
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if self._headless:
            options.add_argument("--headless=new")

        if self._anti_detection:
            # Opções anti-detecção
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            # User-agent realista
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )

        return options

    def _iniciar_driver(self) -> None:
        """Inicializa o WebDriver do Chrome.

        Raises:
            SeleniumError: Se não for possível iniciar o driver.
        """
        sel = self._ensure_selenium()

        try:
            options = self._get_chrome_options()
            self._driver = sel['webdriver'].Chrome(options=options)
            self._driver.implicitly_wait(10)
            self.logger.info("WebDriver Chrome iniciado com sucesso")
        except sel['WebDriverException'] as e:
            raise SeleniumError(f"Erro ao iniciar WebDriver: {e}")

    def _encerrar_driver(self) -> None:
        """Encerra o WebDriver de forma segura."""
        if self._driver:
            try:
                self._driver.quit()
                self.logger.info("WebDriver encerrado")
            except Exception as e:
                self.logger.warning(f"Erro ao encerrar driver: {e}")
            finally:
                self._driver = None

    @contextmanager
    def _driver_context(self):
        """Context manager para gerenciar ciclo de vida do driver.

        Garante que o driver seja encerrado mesmo em caso de exceção.

        Yields:
            webdriver.Chrome: Instância do driver.
        """
        try:
            self._iniciar_driver()
            yield self._driver
        finally:
            self._encerrar_driver()

    def _ensure_selenium(self):
        """Garante que Selenium está importado.

        Returns:
            dict: Módulos do Selenium.

        Raises:
            DriverNotInstalledError: Se Selenium não estiver instalado.
        """
        if self._selenium is None:
            self._selenium = _import_selenium()
        return self._selenium

    # =========================================================================
    # Helpers para Interação com Elementos
    # =========================================================================

    def _aguardar_elemento(
        self,
        by: str,
        value: str,
        timeout: int | None = None,
        condition: str = "clickable"
    ):
        """Aguarda um elemento estar disponível na página.

        Args:
            by: Tipo de localizador (By.ID, By.XPATH, etc.)
            value: Valor do localizador.
            timeout: Tempo máximo de espera (usa self.wait_timeout se None).
            condition: Condição esperada ("clickable", "visible", "present").

        Returns:
            WebElement: O elemento encontrado.

        Raises:
            SeleniumError: Se o elemento não for encontrado no tempo limite.
        """
        sel = self._ensure_selenium()
        timeout = timeout or self.wait_timeout

        conditions = {
            "clickable": sel['EC'].element_to_be_clickable,
            "visible": sel['EC'].visibility_of_element_located,
            "present": sel['EC'].presence_of_element_located,
        }

        try:
            wait = sel['WebDriverWait'](self._driver, timeout)
            element = wait.until(conditions[condition]((by, value)))
            return element
        except sel['TimeoutException']:
            raise SeleniumError(
                f"Timeout aguardando elemento: {by}='{value}' "
                f"(condição: {condition}, timeout: {timeout}s)"
            )

    def _clicar_elemento(
        self,
        by: str,
        value: str,
        use_javascript: bool = False
    ) -> None:
        """Clica em um elemento da página.

        Args:
            by: Tipo de localizador.
            value: Valor do localizador.
            use_javascript: Se True, usa JavaScript para clicar.
        """
        element = self._aguardar_elemento(by, value)

        if use_javascript:
            self._driver.execute_script("arguments[0].click();", element)
        else:
            element.click()

    def _preencher_campo(
        self,
        by: str,
        value: str,
        texto: str,
        limpar: bool = True
    ) -> None:
        """Preenche um campo de formulário.

        Args:
            by: Tipo de localizador.
            value: Valor do localizador.
            texto: Texto a ser inserido.
            limpar: Se True, limpa o campo antes de preencher.
        """
        element = self._aguardar_elemento(by, value)

        if limpar:
            element.clear()

        element.send_keys(texto)

    def _salvar_html_pagina(self, numero_pagina: int, download_dir: str) -> str:
        """Salva o HTML da página atual em arquivo.

        Args:
            numero_pagina: Número da página para nomear o arquivo.
            download_dir: Diretório onde salvar.

        Returns:
            str: Caminho do arquivo salvo.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.nome_buscador}_{numero_pagina:05d}_{timestamp}.html"
        filepath = os.path.join(download_dir, filename)

        page_source = self._driver.page_source

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(page_source)

        self.logger.debug(f"HTML salvo: {filepath}")
        return filepath

    # =========================================================================
    # Estratégias de Paginação
    # =========================================================================

    def _navegar_proxima_pagina(self, pagina_atual: int) -> bool:
        """Navega para a próxima página usando a estratégia configurada.

        Args:
            pagina_atual: Número da página atual (1-indexed).

        Returns:
            bool: True se conseguiu navegar, False se não há mais páginas.
        """
        strategy = self.pagination_strategy

        if strategy == PaginationStrategy.NONE:
            return False

        elif strategy == PaginationStrategy.NUMBERED_LINKS:
            return self._paginar_por_numero(pagina_atual + 1)

        elif strategy == PaginationStrategy.NEXT_BUTTON:
            return self._paginar_por_botao_proximo()

        elif strategy == PaginationStrategy.LOAD_MORE:
            return self._paginar_por_carregar_mais()

        elif strategy == PaginationStrategy.INFINITE_SCROLL:
            return self._paginar_por_scroll()

        return False

    def _paginar_por_numero(self, numero: int) -> bool:
        """Clica em link de página numerada.

        Subclasses podem sobrescrever para customizar o seletor.

        Args:
            numero: Número da página destino.

        Returns:
            bool: True se encontrou e clicou no link.
        """
        sel = self._ensure_selenium()

        try:
            # Padrão: procura link com texto igual ao número
            xpath = f"//a[text()='{numero}']"
            link = sel['WebDriverWait'](self._driver, 5).until(
                sel['EC'].element_to_be_clickable((sel['By'].XPATH, xpath))
            )
            self._driver.execute_script("arguments[0].click();", link)
            time.sleep(self.between_pages_wait)
            return True
        except sel['TimeoutException']:
            self.logger.debug(f"Link para página {numero} não encontrado")
            return False

    def _paginar_por_botao_proximo(self) -> bool:
        """Clica no botão 'Próximo' ou 'Next'.

        Subclasses devem sobrescrever para definir o seletor correto.

        Returns:
            bool: True se encontrou e clicou no botão.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(
            "Subclasse deve implementar _paginar_por_botao_proximo()"
        )

    def _paginar_por_carregar_mais(self) -> bool:
        """Clica no botão 'Carregar mais'.

        Subclasses devem sobrescrever para definir o seletor correto.

        Returns:
            bool: True se encontrou e clicou no botão.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(
            "Subclasse deve implementar _paginar_por_carregar_mais()"
        )

    def _paginar_por_scroll(self) -> bool:
        """Rola a página para carregar mais conteúdo.

        Returns:
            bool: True se carregou mais conteúdo.
        """
        # Obtém altura atual do scroll
        last_height = self._driver.execute_script(
            "return document.body.scrollHeight"
        )

        # Rola até o final
        self._driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(self.between_pages_wait)

        # Verifica se carregou mais conteúdo
        new_height = self._driver.execute_script(
            "return document.body.scrollHeight"
        )

        return new_height > last_height

    # =========================================================================
    # Métodos Abstratos (implementados pelas subclasses)
    # =========================================================================

    @abstractmethod
    def _executar_busca(self, **kwargs) -> None:
        """Executa a busca no site (preenche formulário, clica em buscar).

        Este método deve:
        1. Preencher os campos do formulário de busca
        2. Clicar no botão de busca
        3. Aguardar os resultados carregarem

        Args:
            **kwargs: Parâmetros de busca passados para raspar().
        """
        ...

    @abstractmethod
    def _encontrar_total_paginas(self) -> int:
        """Determina o número total de páginas de resultados.

        Returns:
            int: Número total de páginas (0 se nenhum resultado).
        """
        ...

    # =========================================================================
    # Método Principal de Raspagem
    # =========================================================================

    def raspar(self, **kwargs) -> pd.DataFrame:
        """Executa o processo completo de raspagem.

        Args:
            **kwargs: Parâmetros de busca específicos do scraper.

        Returns:
            pd.DataFrame: Dados raspados consolidados.
        """
        import shutil

        # Valida parâmetros
        kwargs = self._validar_parametros(**kwargs)
        self.logger.info(f"Iniciando raspagem Selenium: {kwargs}")

        download_dir = self._create_download_dir()

        with self._driver_context():
            try:
                # Navega até a URL base
                self.logger.debug(f"Navegando para: {self.url_base}")
                self._driver.get(self.url_base)
                time.sleep(self.page_load_wait)

                # Executa a busca
                self._executar_busca(**kwargs)
                time.sleep(self.page_load_wait)

                # Determina paginação
                total_paginas = self._encontrar_total_paginas()
                total_paginas = min(total_paginas, self._max_pages)
                self.logger.info(f"Total de páginas: {total_paginas}")

                if total_paginas == 0:
                    self.logger.warning("Nenhum resultado encontrado")
                    return pd.DataFrame()

                # Salva primeira página
                self._salvar_html_pagina(1, download_dir)

                # Navega pelas páginas restantes
                for pagina in range(2, total_paginas + 1):
                    self.logger.debug(f"Navegando para página {pagina}")

                    if not self._navegar_proxima_pagina(pagina - 1):
                        self.logger.info(f"Fim da paginação na página {pagina - 1}")
                        break

                    self._salvar_html_pagina(pagina, download_dir)

            except Exception as e:
                self.logger.error(f"Erro durante raspagem: {e}")
                raise

        # Processa arquivos salvos
        result = self._parse_data(download_dir)

        # Adiciona termo de busca se disponível
        termo_param = next((k for k in kwargs if k in ['assunto', 'pesquisa', 'termo', 'q', 'query']), None)
        if termo_param:
            termo_busca = str(kwargs[termo_param])
            result = result.assign(termo_busca=termo_busca)
            self.logger.debug(f"Adicionada coluna termo_busca={termo_busca}")

        # Limpa diretório se não estiver em modo debug
        if not self.debug:
            shutil.rmtree(download_dir)

        self.logger.info(f"Raspagem concluída: {len(result)} registros")
        return result
