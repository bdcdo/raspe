"""
Scraper para o portal SaudeLegis do Ministério da Saúde.

Este scraper usa Playwright para navegar no portal SaudeLegis,
que requer JavaScript para funcionar corretamente.

Exemplo:
    >>> import raspe
    >>> df = raspe.saudelegis().raspar(assunto="doença rara")
    >>> print(df.head())
"""

import asyncio
import pandas as pd

from raspe.playwright_scraper import PlaywrightScraper, PaginationStrategy


class ScraperSaudeLegis(PlaywrightScraper):
    """Scraper para o portal SaudeLegis do Ministério da Saúde.

    Coleta normas e legislação sanitária do portal SaudeLegis.

    Args:
        debug: Se True, mantém navegador visível e arquivos.
        headless: Se True, executa em modo headless.

    Atributos:
        Herda todos os atributos de PlaywrightScraper.

    Exemplo:
        >>> scraper = ScraperSaudeLegis()
        >>> df = scraper.raspar(assunto="doença rara")
        >>> print(df.columns.tolist())
        ['tipo_norma', 'numero', 'data_pub', 'origem', 'ementa', 'link_url']
    """

    def __init__(self, debug: bool = True, headless: bool = True):
        """Inicializa o ScraperSaudeLegis."""
        super().__init__(
            nome_buscador="SAUDELEGIS",
            debug=debug,
            headless=headless,
        )

        self._url_base = "https://saudelegis.saude.gov.br/saudelegis/secure/norma/listPublic.xhtml"
        self._pagination_strategy = PaginationStrategy.NUMBERED_LINKS
        self._max_pages = 50

    @property
    def url_base(self) -> str:
        """URL do portal SaudeLegis."""
        return self._url_base

    async def _executar_busca(self, **kwargs) -> None:
        """Preenche o formulário de busca e executa a pesquisa.

        Args:
            **kwargs: Deve conter 'assunto' com o termo de busca.
        """
        assunto = kwargs.get('assunto', '')

        if not assunto:
            self.logger.warning("Nenhum termo de busca (assunto) fornecido")

        # Aguarda o campo de formulário estar disponível
        self.logger.debug("Aguardando campo 'assunto'...")
        selector_assunto = '#form\\:assunto'
        await self._aguardar_elemento(selector_assunto)

        # Preenche o campo de busca
        await self._preencher_campo(selector_assunto, assunto)
        self.logger.debug(f"Termo de busca: '{assunto}'")

        # Aguarda um momento para garantir que o texto foi inserido
        await asyncio.sleep(1)

        # Clica no botão de busca
        self.logger.debug("Clicando no botão de busca...")
        selector_botao = 'input[type="submit"][value="Buscar"], input.ui-button'
        await self._clicar_elemento(selector_botao)

        self.logger.info("Busca executada")

    async def _encontrar_total_paginas(self) -> int:
        """Determina o número total de páginas de resultados.

        Returns:
            int: Número de páginas encontradas.
        """
        pw = self._ensure_playwright()

        try:
            # Procura links de paginação numérica
            pagination_links = await self._page.query_selector_all(
                "a[id*='form:'][id*='paginator']"
            )

            page_numbers = []
            for link in pagination_links:
                text = await link.text_content()
                if text and text.strip().isdigit():
                    page_numbers.append(int(text.strip()))

            if page_numbers:
                total = max(page_numbers)
                self.logger.debug(f"Páginas encontradas via links: {total}")
                return total

            # Se não houver paginação, verifica se há resultados
            table = await self._page.query_selector("#form\\:grid")
            if table:
                self.logger.debug("Tabela encontrada, assumindo 1 página")
                return 1

            return 0

        except Exception as e:
            self.logger.warning(f"Erro ao determinar páginas: {e}")
            return 1

    async def _paginar_por_numero(self, numero: int) -> bool:
        """Navega para página específica via link numerado.

        Sobrescreve o método base para usar seletor específico do SaudeLegis.

        Args:
            numero: Número da página destino.

        Returns:
            bool: True se navegou com sucesso.
        """
        pw = self._ensure_playwright()

        try:
            # Seletor específico do SaudeLegis
            selector = f"a[id*='form:']:text-is('{numero}')"
            await self._page.wait_for_selector(selector, timeout=5000)
            await self._page.click(selector)

            await asyncio.sleep(self.between_pages_wait)
            return True

        except pw['PlaywrightTimeout']:
            self.logger.debug(f"Link página {numero} não encontrado")
            return False

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Extrai dados de uma página HTML salva.

        Args:
            path: Caminho para o arquivo HTML.

        Returns:
            pd.DataFrame: Dados extraídos da página.
        """
        columns = ['tipo_norma', 'numero', 'data_pub', 'origem', 'ementa', 'link_url']

        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = self.soup_it(html_content)
            results_table = soup.find('table', id='form:grid')

            if not results_table:
                self.logger.debug(f"Tabela não encontrada em {path}")
                return pd.DataFrame(columns=columns)

            tbody = results_table.find('tbody')
            if not tbody:
                self.logger.debug(f"Tbody não encontrado em {path}")
                return pd.DataFrame(columns=columns)

            rows = tbody.find_all('tr')
            data = []

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 8:
                    continue

                tipo_norma = cells[3].text.strip()
                numero = cells[1].text.strip()
                data_pub = cells[4].text.strip()
                origem = cells[2].text.strip()
                ementa = cells[5].text.strip()

                link_tag = cells[7].find('a', {'title': 'Texto Completo'})
                link_url = link_tag['href'] if link_tag else ''

                data.append([tipo_norma, numero, data_pub, origem, ementa, link_url])

            self.logger.debug(f"Extraídos {len(data)} registros de {path}")
            return pd.DataFrame(data, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao processar {path}: {e}")
            return pd.DataFrame(columns=columns)
