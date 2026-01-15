"""
Classe base para scrapers de portais Datalegis (ANS, ANVISA).

Os portais ANSLegis e ANVISALegis usam o mesmo sistema Datalegis,
com proteção Cloudflare que requer bypass via playwright-stealth.

Este módulo fornece a classe base ScraperDatalegis que implementa
a lógica comum de navegação, busca e extração de atos normativos.
"""

import asyncio

import pandas as pd

from raspe.playwright_scraper import PlaywrightScraper, PaginationStrategy


class ScraperDatalegis(PlaywrightScraper):
    """Classe base para scrapers de portais Datalegis.

    Implementa a lógica comum para navegar e extrair dados dos portais
    ANSLegis e ANVISALegis, que usam o mesmo sistema.

    Subclasses devem definir:
        - _dominio: Domínio do portal (ex: "anslegis.datalegis.net")
        - _cod_modulo: Código do módulo
        - _cod_menu: Código do menu

    Args:
        nome_buscador: Identificador único para o scraper.
        debug: Se True, mantém navegador visível e arquivos.
        headless: Se True, executa em modo headless.

    Atributos:
        Herda todos os atributos de PlaywrightScraper.
    """

    # Subclasses devem definir estes atributos
    _dominio: str = ""
    _cod_modulo: str = ""
    _cod_menu: str = ""

    def __init__(
        self,
        nome_buscador: str,
        debug: bool = True,
        headless: bool = True,
    ):
        """Inicializa o ScraperDatalegis."""
        super().__init__(
            nome_buscador=nome_buscador,
            debug=debug,
            headless=headless,
        )

        self._pagination_strategy = PaginationStrategy.SELECT_DROPDOWN
        self._max_pages = 100
        self._pagination_selector = '#fieldPage, select[onchange*="openPage"]'

    @property
    def url_base(self) -> str:
        """URL inicial do portal para bypass do Cloudflare."""
        return (
            f"https://{self._dominio}/action/ActionDatalegis.php?"
            f"acao=consultarAtosInicial&cod_modulo={self._cod_modulo}&cod_menu={self._cod_menu}"
        )

    async def _executar_busca(self, **kwargs) -> None:
        """Preenche o formulário de busca e executa a pesquisa.

        Args:
            **kwargs: Deve conter 'termo' com o texto de busca.
        """
        termo = kwargs.get('termo', '')

        if not termo:
            self.logger.warning("Nenhum termo de busca fornecido")

        # Preenche o campo de busca
        # O campo usa name="txt_texto[]" com id="nolivesearchGadget"
        selector_busca = '#nolivesearchGadget, input[name="txt_texto[]"]'
        self.logger.debug(f"Preenchendo campo de busca com: '{termo}'")
        await self._preencher_campo(selector_busca, termo)

        await asyncio.sleep(1)

        # Clica no botão de busca
        # O botão de busca geralmente é um input type="submit" ou button
        selector_botao = 'button.btn-buscar, input[type="submit"][value*="Buscar"], button:has-text("Buscar")'
        self.logger.debug("Clicando no botão de busca...")

        try:
            await self._clicar_elemento(selector_botao)
        except Exception:
            # Tenta encontrar qualquer botão que pareça de busca
            buttons = await self._page.query_selector_all('button, input[type="submit"]')
            for btn in buttons:
                text = await btn.text_content() or ''
                value = await btn.get_attribute('value') or ''
                if 'buscar' in text.lower() or 'buscar' in value.lower() or 'pesquisar' in text.lower():
                    await btn.click()
                    break

        self.logger.info("Busca executada")

        # Aguarda resultados carregarem
        await asyncio.sleep(2)

    async def _encontrar_total_paginas(self) -> int:
        """Determina o número total de páginas de resultados.

        O sistema Datalegis usa um combobox (select) para navegação entre páginas.
        Cada option representa uma página disponível.

        Returns:
            int: Número de páginas encontradas.
        """
        try:
            # Procura o combobox de paginação
            # O sistema Datalegis usa um select#fieldPage com onchange="openPage()"
            select_element = await self._page.query_selector(
                '#fieldPage, select[onchange*="openPage"]'
            )

            if select_element:
                # Conta as options no select para determinar total de páginas
                options = await select_element.query_selector_all('option')
                if options:
                    total = len(options)
                    self.logger.debug(f"Páginas encontradas via combobox: {total}")
                    return min(total, self._max_pages)

            # Fallback: verifica se há resultados sem paginação
            atos = await self._page.query_selector_all('.ato, a[href*="abrirTextoAto"]')
            if atos:
                self.logger.debug(f"Encontrados {len(atos)} atos, assumindo 1 página")
                return 1

            return 0

        except Exception as e:
            self.logger.warning(f"Erro ao determinar páginas: {e}")
            return 1

    async def _paginar_por_numero(self, numero: int) -> bool:
        """Navega para página específica via combobox de paginação.

        O sistema Datalegis usa um select com onchange para navegação.
        Selecionar uma option dispara a navegação para a página correspondente.

        Args:
            numero: Número da página destino.

        Returns:
            bool: True se navegou com sucesso.
        """
        pw = self._ensure_playwright()

        try:
            # Seletor para o combobox de paginação
            # O select de paginação usa id="fieldPage" e onchange="openPage()"
            select_selector = '#fieldPage, select[onchange*="openPage"]'
            select_element = await self._page.query_selector(select_selector)

            if not select_element:
                self.logger.debug("Combobox de paginação não encontrado com seletor #fieldPage")
                # Tenta um seletor mais genérico baseado na estrutura da página
                select_element = await self._page.query_selector(
                    '.paginacao select, select.form-control'
                )

            if not select_element:
                self.logger.debug("Combobox de paginação não encontrado")
                return False

            # Seleciona a página pelo label (texto visível) ao invés do value
            # O label é o número da página como string
            self.logger.debug(f"Selecionando página {numero} no combobox...")
            await select_element.select_option(label=str(numero))

            # Aguarda a página carregar
            await asyncio.sleep(self.between_pages_wait)

            # Verifica se a navegação funcionou aguardando novos resultados
            await self._page.wait_for_selector('.ato, a[href*="abrirTextoAto"]', timeout=10000)

            self.logger.debug(f"Navegação para página {numero} concluída")
            return True

        except pw['PlaywrightTimeout']:
            self.logger.debug(f"Timeout ao navegar para página {numero}")
            return False
        except Exception as e:
            self.logger.debug(f"Erro ao navegar para página {numero}: {e}")
            return False

    def _extrair_atos_do_html(self, html: str) -> list[dict]:
        """Parseia o HTML e extrai informações dos atos.

        Args:
            html: String HTML contendo os atos normativos.

        Returns:
            Lista de dicionários com informações dos atos.
        """
        soup = self.soup_it(html)
        atos = soup.find_all('div', class_='ato')
        registros = []

        for ato in atos:
            conteudo = ato.find('a')
            if not conteudo:
                continue

            href = conteudo.get('href', '')
            url = f'https://{self._dominio}{href}' if href and not href.startswith('http') else href

            # Extrair elemento strong
            strong_element = conteudo.find('strong')
            if not strong_element:
                continue

            # Extrair situação (se houver span com status - ex: "Revogado")
            situacao = None
            span_element = strong_element.find('span')
            if span_element:
                situacao = span_element.text.strip()
                span_element.extract()  # Remove do DOM para obter texto limpo

            titulo = strong_element.get_text().strip()

            # Extrair descrição
            descricao = None
            p_element = conteudo.find('p')
            if p_element:
                descricao = p_element.text.strip()

            registros.append({
                'url': url,
                'titulo': titulo,
                'descricao': descricao,
                'situacao': situacao
            })

        return registros

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Extrai dados de uma página HTML salva.

        Args:
            path: Caminho para o arquivo HTML.

        Returns:
            pd.DataFrame: Dados extraídos da página.
        """
        columns = ['url', 'titulo', 'descricao', 'situacao']

        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            registros = self._extrair_atos_do_html(html_content)
            self.logger.debug(f"Extraídos {len(registros)} atos de {path}")

            return pd.DataFrame(registros, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao processar {path}: {e}")
            return pd.DataFrame(columns=columns)
