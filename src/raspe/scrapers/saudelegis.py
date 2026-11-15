"""
Scraper para o portal SaudeLegis do Ministério da Saúde.

Este scraper usa Playwright para navegar no portal SaudeLegis,
que requer JavaScript para funcionar corretamente.

Exemplo:
    >>> import raspe
    >>> df = raspe.saudelegis().raspar(pesquisa="doença rara")
    >>> print(df.head())
"""

import asyncio
import math
import re
from typing import TYPE_CHECKING

import pandas as pd

from raspe.playwright_scraper import PaginationStrategy, PlaywrightScraper
from raspe.schemas.saudelegis import InputSaudeLegis, OutputSaudeLegis

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

_CONTAGEM = re.compile(r'Mostrando\s+\d+\s+a\s+(\d+)\s+de\s+(\d+)\s+registro')


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
        >>> df = scraper.raspar(pesquisa="doença rara")

        O resultado traz as colunas de ``ScraperSaudeLegis.colunas``, além de
        ``termo_busca``.

    O nome antigo do parâmetro de busca, ``assunto``, ainda é aceito com
    ``DeprecationWarning``.
    """

    schema_entrada = InputSaudeLegis
    schema_saida = OutputSaudeLegis

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
            **kwargs: Deve conter 'pesquisa' com o termo de busca.
        """
        assunto = kwargs['pesquisa']

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
        selector_botao = 'input[type="submit"][value="Consultar"]'
        await self._clicar_elemento(selector_botao)

        self.logger.info("Busca executada")

    async def _encontrar_total_paginas(self) -> int:
        """Calcula o número de páginas pelo rodapé da tabela de resultados.

        O rodapé diz "Mostrando 1 a 10 de 14 registros.", e os links do
        paginador só mostram uma janela de até cinco páginas. O rodapé lido é o
        primeiro depois da tabela ``form:grid``, porque a tabela de origens tem
        rodapé próprio.

        Returns:
            int: Número de páginas (0 se não há tabela de resultados ou contagem).
        """
        soup = self.soup_it(await self._obter_html())
        tabela = soup.find('table', id='form:grid')
        rodape = tabela.find_next('div', class_='dataTables_info') if tabela else None
        contagem = _CONTAGEM.search(rodape.get_text(' ')) if rodape else None
        if not contagem:
            return 0
        # Lido na primeira página, o "a 10" é o tamanho da página.
        fim, total = (int(n) for n in contagem.groups())
        return math.ceil(total / fim) if total else 0

    def _confirmar_busca_vazia(self, soup: "BeautifulSoup") -> int:
        """Confirma a busca vazia sem a tabela de origens, escondida em toda página.

        A tabela de origens diz "Nenhum Registro Encontrado" mesmo quando há
        resultados, e deixaria passar como busca vazia qualquer página do portal.

        Args:
            soup: Página da resposta, já analisada.

        Returns:
            int: Sempre 0.

        Raises:
            ScraperError: Se a página não traz o aviso de busca sem resultados.
        """
        tabela_origens = soup.find(id='form:grid-origens')
        if tabela_origens:
            tabela_origens.decompose()
        return super()._confirmar_busca_vazia(soup)

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
            pd.DataFrame: Dados extraídos da página, com as colunas de ``self.colunas``.
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = self.soup_it(html_content)
            results_table = soup.find('table', id='form:grid')

            if not results_table:
                self.logger.debug(f"Tabela não encontrada em {path}")
                return pd.DataFrame(columns=self.colunas)

            tbody = results_table.find('tbody')
            if not tbody:
                self.logger.debug(f"Tbody não encontrado em {path}")
                return pd.DataFrame(columns=self.colunas)

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
            return pd.DataFrame(data, columns=self.colunas)

        except Exception as e:
            self.logger.error(f"Erro ao processar {path}: {e}")
            return pd.DataFrame(columns=self.colunas)
