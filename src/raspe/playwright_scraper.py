"""
Módulo base para scrapers baseados em Playwright.

Este módulo fornece a classe PlaywrightScraper para automação de navegador,
suportando sites que requerem JavaScript, interação com formulários,
navegação complexa e bypass de proteções anti-bot como Cloudflare.

Dependências:
    - playwright (instalação opcional: pip install raspe[browser])
    - playwright-stealth (incluído no extra browser)

Exemplo de uso:
    class MeuScraperPlaywright(PlaywrightScraper):
        def __init__(self):
            super().__init__("meu_scraper", headless=True)
            self._url_base = "https://exemplo.com/busca"
            self._pagination_strategy = PaginationStrategy.NUMBERED_LINKS

        @property
        def url_base(self) -> str:
            return self._url_base

        async def _executar_busca(self, **kwargs) -> None:
            await self._preencher_campo("#campo-busca", kwargs.get("termo"))
            await self._clicar_elemento("#btn-buscar")

        async def _encontrar_total_paginas(self) -> int:
            # Lógica para determinar número de páginas
            return 1

        async def _paginar_por_numero(self, numero: int) -> bool:
            try:
                await self._clicar_elemento(f"a:text-is('{numero}')")
                # Espera a página nova, e não um tempo fixo
                await self._aguardar_elemento(f".pagina-atual:text-is('{numero}')")
            except BrowserError:
                return False
            return True

        def _parse_page(self, path: str) -> pd.DataFrame:
            # Lógica para extrair dados do HTML
            ...
"""

import asyncio
import os
import time
from abc import abstractmethod
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from typing import Literal

from raspe.abstract_scraper import AbstractScraper
from raspe.exceptions import BrowserError, DriverNotInstalledError, ScraperError
from raspe.html_scraper import HTMLScraper


def _import_playwright():
    """Importa Playwright de forma lazy.

    Returns:
        dict: Dicionário com módulos e classes do Playwright.

    Raises:
        DriverNotInstalledError: Se Playwright não estiver instalado.
    """
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth
        return {
            'async_playwright': async_playwright,
            'PlaywrightTimeout': PlaywrightTimeout,
            'Stealth': Stealth,
        }
    except ImportError as e:
        raise DriverNotInstalledError(
            "Playwright não está instalado. Instale com:\n"
            "  pip install raspe[browser]\n"
            "  playwright install chromium"
        ) from e


class PaginationStrategy(Enum):
    """Estratégias de paginação suportadas pelo PlaywrightScraper."""
    NUMBERED_LINKS = "numbered_links"   # Clica em links numerados (1, 2, 3...)
    NEXT_BUTTON = "next_button"         # Clica em botão "Próximo"
    LOAD_MORE = "load_more"             # Clica em "Carregar mais"
    INFINITE_SCROLL = "infinite_scroll"  # Rola a página para carregar mais
    SELECT_DROPDOWN = "select_dropdown"  # Seleciona página via dropdown/combobox
    NONE = "none"                        # Sem paginação


class PlaywrightScraper(AbstractScraper, HTMLScraper):
    """Classe base para scrapers que usam automação de navegador com Playwright.

    Fornece gerenciamento de browser, opções anti-detecção via playwright-stealth,
    bypass de Cloudflare e diferentes estratégias de paginação.

    Args:
        nome_buscador: Identificador único para o scraper.
        debug: Se True, mantém navegador visível e arquivos baixados.
        headless: Se True, executa navegador em modo headless.

    Atributos:
        _page: Instância da página Playwright (None até inicialização).
        wait_timeout: Tempo máximo de espera para elementos (segundos).
        cloudflare_timeout: Tempo máximo para bypass do Cloudflare (segundos).
        page_load_wait: Tempo de espera após carregar página (segundos).
        between_pages_wait: Tempo de espera entre páginas (segundos).

    Exemplo:
        >>> class MeuScraper(PlaywrightScraper):
        ...     @property
        ...     def url_base(self):
        ...         return "https://exemplo.com"
        ...
        ...     async def _executar_busca(self, **kwargs):
        ...         # Implementação da busca
        ...         pass
        ...
        ...     async def _encontrar_total_paginas(self):
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
    ):
        """Inicializa o PlaywrightScraper com configuração de navegador."""
        super().__init__(nome_buscador, debug)

        self._playwright_modules = None  # Lazy loaded
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = headless

        # Timeouts configuráveis
        self.wait_timeout: int = 15
        self.cloudflare_timeout: int = 60
        self.page_load_wait: float = 2.0
        self.between_pages_wait: float = 3.0

        # Tipo sempre HTML para scrapers Playwright
        self._type: Literal['HTML'] = 'HTML'

        # Estratégia de paginação padrão
        self._pagination_strategy: PaginationStrategy = PaginationStrategy.NONE
        self._max_pages: int = 100  # Limite de segurança
        # Páginas da contagem da última busca; o aviso de teto sai em _download_data.
        self._total_paginas: int = 0
        # Resultados por página, lido da contagem por _paginas_pela_contagem.
        self._por_pagina: int = 1

    @property
    def type(self) -> Literal['HTML']:
        """Tipo de arquivo baixado (sempre HTML para Playwright)."""
        return self._type

    @property
    def page(self):
        """Instância da página Playwright (inicializada sob demanda)."""
        return self._page

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
    # Gerenciamento do Browser
    # =========================================================================

    def _ensure_playwright(self):
        """Garante que Playwright está importado.

        Returns:
            dict: Módulos do Playwright.

        Raises:
            DriverNotInstalledError: Se Playwright não estiver instalado.
        """
        if self._playwright_modules is None:
            self._playwright_modules = _import_playwright()
        return self._playwright_modules

    @asynccontextmanager
    async def _browser_context(self):
        """Context manager assíncrono para gerenciar ciclo de vida do browser.

        Garante que o browser seja encerrado mesmo em caso de exceção.
        Aplica playwright-stealth automaticamente para bypass de anti-bot.

        Yields:
            Page: Instância da página com stealth aplicado.
        """
        pw = self._ensure_playwright()

        try:
            self._playwright = await pw['async_playwright']().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )

            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )

            self._page = await self._context.new_page()

            # Aplica stealth para bypass de anti-bot (nova API)
            stealth = pw['Stealth'](
                navigator_languages_override=('pt-BR', 'pt', 'en-US', 'en'),
            )
            await stealth.apply_stealth_async(self._page)

            self.logger.info("Browser Playwright iniciado com stealth")
            yield self._page

        finally:
            await self._encerrar_browser()

    async def _encerrar_browser(self) -> None:
        """Encerra o browser de forma segura."""
        if self._page:
            try:
                await self._page.close()
            except Exception as e:
                self.logger.warning(f"Erro ao fechar página: {e}")
            finally:
                self._page = None

        if self._context:
            try:
                await self._context.close()
            except Exception as e:
                self.logger.warning(f"Erro ao fechar contexto: {e}")
            finally:
                self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                self.logger.warning(f"Erro ao fechar browser: {e}")
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                self.logger.warning(f"Erro ao parar Playwright: {e}")
            finally:
                self._playwright = None

        self.logger.info("Browser encerrado")

    # =========================================================================
    # Bypass do Cloudflare
    # =========================================================================

    async def _aguardar_cloudflare(self, selector_pagina_real: str | None = None) -> None:
        """Aguarda até 60s pelo challenge do Cloudflare resolver.

        Detecta página real quando:
        - Cookie cf_clearance existe, ou
        - Elemento específico do site aparece, ou
        - Página tem conteúdo substancial sem sinais de challenge

        Args:
            selector_pagina_real: Seletor CSS de elemento que indica página carregou.
                                  Se None, usa heurísticas genéricas.

        Raises:
            BrowserError: Se o Cloudflare não resolver no timeout.
        """
        pw = self._ensure_playwright()
        start_time = time.time()

        self.logger.info("Verificando proteção Cloudflare...")

        while (time.time() - start_time) < self.cloudflare_timeout:
            # Verifica se elemento da página real existe (prioridade máxima)
            if selector_pagina_real:
                try:
                    # Usa state='attached' porque elementos podem não estar visíveis ainda
                    await self._page.wait_for_selector(
                        selector_pagina_real,
                        timeout=5000,
                        state='attached'
                    )
                    self.logger.info("Página real carregada")
                    return
                except pw['PlaywrightTimeout']:
                    pass

            # Verifica se tem cookie cf_clearance (indica que Cloudflare foi bypassado)
            cookies = await self._context.cookies()
            cf_cookie = next((c for c in cookies if c['name'] == 'cf_clearance'), None)

            if cf_cookie:
                self.logger.info("Cookie cf_clearance obtido - Cloudflare bypassado")
                await asyncio.sleep(2)
                return

            # Verifica heurísticas: página sem challenge e com conteúdo
            content = await self._page.content()
            has_challenge = (
                "Checking" in content or
                "challenge" in content.lower() or
                "Just a moment" in content or
                "cf-browser-verification" in content
            )

            if not has_challenge and len(content) > 5000:
                # Página com conteúdo real, sem Cloudflare
                self.logger.info("Página carregada (sem proteção Cloudflare)")
                return

            await asyncio.sleep(1)

        raise BrowserError(
            f"Timeout ({self.cloudflare_timeout}s) aguardando bypass do Cloudflare. "
            "Tente executar com headless=False para verificar manualmente."
        )

    # =========================================================================
    # Helpers para Interação com Elementos
    # =========================================================================

    async def _aguardar_elemento(
        self,
        selector: str,
        timeout: int | None = None,
        state: str = "visible"
    ):
        """Aguarda um elemento estar disponível na página.

        Args:
            selector: Seletor CSS do elemento.
            timeout: Tempo máximo de espera em ms (usa self.wait_timeout * 1000 se None).
            state: Estado esperado ("visible", "attached", "hidden").

        Returns:
            ElementHandle: O elemento encontrado.

        Raises:
            BrowserError: Se o elemento não for encontrado no tempo limite.
        """
        pw = self._ensure_playwright()
        timeout_ms = (timeout or self.wait_timeout) * 1000

        try:
            element = await self._page.wait_for_selector(
                selector,
                timeout=timeout_ms,
                state=state
            )
            return element
        except pw['PlaywrightTimeout'] as exc:
            raise BrowserError(
                f"Timeout aguardando elemento: '{selector}' "
                f"(estado: {state}, timeout: {timeout_ms}ms)"
            ) from exc

    async def _clicar_elemento(
        self,
        selector: str,
        force: bool = False
    ) -> None:
        """Clica em um elemento da página.

        Args:
            selector: Seletor CSS do elemento.
            force: Se True, força o clique mesmo se elemento não estiver visível.
        """
        await self._aguardar_elemento(selector)
        await self._page.click(selector, force=force)

    async def _preencher_campo(
        self,
        selector: str,
        texto: str,
    ) -> None:
        """Preenche um campo de formulário.

        Args:
            selector: Seletor CSS do campo.
            texto: Texto a ser inserido.
        """
        await self._aguardar_elemento(selector)
        await self._page.fill(selector, texto)

    async def _obter_html(self) -> str:
        """Retorna HTML atual da página.

        Returns:
            str: Conteúdo HTML da página.
        """
        return await self._page.content()

    async def _salvar_html_pagina(self, numero_pagina: int, download_dir: str) -> str:
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

        page_source = await self._obter_html()

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(page_source)

        self.logger.debug(f"HTML salvo: {filepath}")
        return filepath

    # =========================================================================
    # Estratégias de Paginação
    # =========================================================================

    def _paginas_pela_contagem(self, fim: str, total: str) -> int:
        """Calcula o número de páginas pela contagem da primeira página, como "1 a 10 de 14".

        Lida na primeira página, a posição final (``fim``) é o tamanho da página,
        guardado em ``_por_pagina`` para :meth:`_inicio_da_pagina`.

        Args:
            fim: Posição do último resultado da primeira página ("10"). O ponto, se
                vier, é separador de milhar.
            total: Total de resultados ("14").

        Returns:
            int: Número de páginas (0 se o total é 0).
        """
        self._por_pagina, quantos = (int(n.replace('.', '')) for n in (fim, total))
        return self._paginas_para(quantos, self._por_pagina)

    def _inicio_da_pagina(self, numero: int) -> int:
        """Posição do primeiro resultado da página ``numero`` (11 na página 2, com 10 por página).

        Args:
            numero: Número da página (1-indexed).

        Returns:
            int: Posição, contada a partir de 1.
        """
        return (numero - 1) * self._por_pagina + 1

    async def _navegar_proxima_pagina(self, pagina_atual: int) -> bool:
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
            return await self._paginar_por_numero(pagina_atual + 1)

        elif strategy == PaginationStrategy.NEXT_BUTTON:
            return await self._paginar_por_botao_proximo()

        elif strategy == PaginationStrategy.LOAD_MORE:
            return await self._paginar_por_carregar_mais()

        elif strategy == PaginationStrategy.INFINITE_SCROLL:
            return await self._paginar_por_scroll()

        elif strategy == PaginationStrategy.SELECT_DROPDOWN:
            return await self._paginar_por_numero(pagina_atual + 1)

        return False

    async def _paginar_por_numero(self, numero: int) -> bool:
        """Abre a página ``numero`` (estratégias NUMBERED_LINKS e SELECT_DROPDOWN).

        Subclasses devem sobrescrever com o seletor do site e, depois do clique,
        esperar a página nova aparecer (como ``ScraperSaudeLegis`` e
        ``ScraperDatalegis`` fazem): sem isso, a página salva pode ainda ser a anterior.

        Args:
            numero: Número da página destino.

        Returns:
            bool: True se a página nova abriu.

        Raises:
            NotImplementedError: Se não implementado pela subclasse.
        """
        raise NotImplementedError(
            "Subclasse deve implementar _paginar_por_numero()"
        )

    async def _paginar_por_botao_proximo(self) -> bool:
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

    async def _paginar_por_carregar_mais(self) -> bool:
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

    async def _paginar_por_scroll(self) -> bool:
        """Rola a página para carregar mais conteúdo.

        Returns:
            bool: True se carregou mais conteúdo.
        """
        # Obtém altura atual do scroll
        last_height = await self._page.evaluate("document.body.scrollHeight")

        # Rola até o final
        await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

        await asyncio.sleep(self.between_pages_wait)

        # Verifica se carregou mais conteúdo
        new_height = await self._page.evaluate("document.body.scrollHeight")

        return new_height > last_height

    # =========================================================================
    # Métodos Abstratos (implementados pelas subclasses)
    # =========================================================================

    @abstractmethod
    async def _executar_busca(self, **kwargs) -> None:
        """Executa a busca no site (preenche formulário, clica em buscar).

        Este método deve:
        1. Preencher os campos do formulário de busca
        2. Clicar no botão de busca
        3. Aguardar os resultados carregarem

        Args:
            **kwargs: Parâmetros de busca já validados por :meth:`AbstractScraper.raspar`.
        """
        ...

    @abstractmethod
    async def _encontrar_total_paginas(self) -> int:
        """Determina o número total de páginas de resultados.

        Returns:
            int: Número total de páginas (0 se nenhum resultado). Com 0, a página
            precisa trazer o aviso de busca vazia; senão, ``raspar`` levanta
            ``ScraperError`` (ver :meth:`HTMLScraper._confirmar_busca_vazia`).
        """
        ...

    # =========================================================================
    # Método Principal de Raspagem
    # =========================================================================

    async def _baixar_async(self, **kwargs) -> str:
        """Abre o navegador, faz a busca e salva o HTML de cada página.

        Args:
            **kwargs: Parâmetros de busca já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            str: Pasta com as páginas salvas.
        """
        self.logger.info(f"Iniciando raspagem Playwright: {kwargs}")

        async with self._browser_context():
            download_dir = self._create_download_dir()
            try:
                # Navega até a URL base
                self.logger.debug(f"Navegando para: {self.url_base}")
                await self._page.goto(self.url_base, wait_until="domcontentloaded")

                # Aguarda bypass do Cloudflare se necessário
                await self._aguardar_cloudflare()

                await asyncio.sleep(self.page_load_wait)

                # Executa a busca
                await self._executar_busca(**kwargs)
                await asyncio.sleep(self.page_load_wait)

                # Determina paginação
                total_paginas = await self._encontrar_total_paginas()
                self._total_paginas = total_paginas
                total_paginas = min(total_paginas, self._max_pages)
                self.logger.info(f"Total de páginas: {total_paginas}")

                if total_paginas:
                    # Salva primeira página
                    await self._salvar_html_pagina(1, download_dir)
                else:
                    # Levanta ScraperError se a página não traz o aviso de busca vazia.
                    self._confirmar_busca_vazia(self.soup_it(await self._obter_html()))
                    # Segue para o fluxo normal: o _parse_data da pasta vazia devolve as
                    # colunas da fonte, e o termo de busca e a limpeza da pasta valem igual.
                    self.logger.warning("Nenhum resultado encontrado")

                # Navega pelas páginas restantes
                for pagina in range(2, total_paginas + 1):
                    self.logger.debug(f"Navegando para página {pagina}")

                    # A contagem diz que a página existe: parar aqui truncaria o
                    # resultado em silêncio, como no BaseScraper._download_data.
                    if not await self._navegar_proxima_pagina(pagina - 1):
                        raise ScraperError(
                            f"{self.nome_buscador}: não foi possível abrir a página {pagina} de "
                            f"{total_paginas}, e o resultado ficaria incompleto. O site pode ter "
                            "mudado o paginador ou demorado a responder. "
                            f"{self._onde_ficam_os_arquivos(download_dir)}"
                        )

                    await self._salvar_html_pagina(pagina, download_dir)

            except BaseException as e:
                # BaseException: o Ctrl+C chega aqui como CancelledError.
                self.logger.error(f"Erro durante raspagem: {e!r}")
                self._apagar_sem_debug(download_dir)
                raise

        return download_dir

    def _download_data(self, **kwargs) -> str:
        """Roda :meth:`_baixar_async` até o fim, com ou sem loop do asyncio já ativo.

        No Jupyter e no Colab a célula roda dentro de um loop, e ``asyncio.run``
        recusa outro loop na mesma thread. Nesse caso o download roda num loop
        próprio em outra thread, e esta espera o resultado.

        O aviso de teto de páginas sai daqui, fora do loop, e a leitura das
        páginas, em :meth:`AbstractScraper._raspar`, também: dentro do loop, os
        avisos apontariam para o asyncio, e não para quem chamou ``raspar()``, e
        sairiam uma vez só por sessão.

        Args:
            **kwargs: Parâmetros já validados por :meth:`AbstractScraper.raspar`.

        Returns:
            str: Pasta com as páginas salvas.

        Warns:
            UserWarning: Se a contagem passa de ``_max_pages`` páginas.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            download_dir = asyncio.run(self._baixar_async(**kwargs))
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                download_dir = executor.submit(lambda: asyncio.run(self._baixar_async(**kwargs))).result()
        if self._total_paginas > self._max_pages:
            try:
                self._avisar_teto(self._total_paginas, self._max_pages, "páginas de resultados")
            except BaseException:
                # Com o aviso virando erro (filterwarnings), a pasta não chega a _raspar.
                self._apagar_sem_debug(download_dir)
                raise
        return download_dir
