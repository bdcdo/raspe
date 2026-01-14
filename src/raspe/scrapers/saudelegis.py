"""
Scraper para o portal SaudeLegis do Ministério da Saúde.

Este scraper usa Selenium para navegar no portal SaudeLegis,
que requer JavaScript para funcionar corretamente.

Exemplo:
    >>> import raspe
    >>> df = raspe.saudelegis().raspar(assunto="doença rara")
    >>> print(df.head())
"""

import pandas as pd

from raspe.selenium_scraper import SeleniumScraper, PaginationStrategy


class ScraperSaudeLegis(SeleniumScraper):
    """Scraper para o portal SaudeLegis do Ministério da Saúde.

    Coleta normas e legislação sanitária do portal SaudeLegis.

    Args:
        debug: Se True, mantém navegador visível e arquivos.
        headless: Se True, executa em modo headless.

    Atributos:
        Herda todos os atributos de SeleniumScraper.

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
            anti_detection=True,
        )

        self._url_base = "https://saudelegis.saude.gov.br/saudelegis/secure/norma/listPublic.xhtml"
        self._pagination_strategy = PaginationStrategy.NUMBERED_LINKS
        self._max_pages = 50

    @property
    def url_base(self) -> str:
        """URL do portal SaudeLegis."""
        return self._url_base

    def _executar_busca(self, **kwargs) -> None:
        """Preenche o formulário de busca e executa a pesquisa.

        Args:
            **kwargs: Deve conter 'assunto' com o termo de busca.
        """
        sel = self._ensure_selenium()
        assunto = kwargs.get('assunto', '')

        if not assunto:
            self.logger.warning("Nenhum termo de busca (assunto) fornecido")

        # Aguarda o campo de formulário estar disponível
        self.logger.debug("Aguardando campo 'assunto'...")
        campo_assunto = self._aguardar_elemento(
            sel['By'].XPATH,
            '//*[@id="form:assunto"]'
        )

        # Preenche o campo de busca
        campo_assunto.clear()
        campo_assunto.send_keys(assunto)
        self.logger.debug(f"Termo de busca: '{assunto}'")

        # Aguarda um momento para garantir que o texto foi inserido
        import time
        time.sleep(1)

        # Clica no botão de busca
        self.logger.debug("Clicando no botão de busca...")
        self._clicar_elemento(
            sel['By'].XPATH,
            '/html/body/div[2]/div/div/div[2]/div/div/form/fieldset/div[7]/div/div/input[1]'
        )

        self.logger.info("Busca executada")

    def _encontrar_total_paginas(self) -> int:
        """Determina o número total de páginas de resultados.

        Returns:
            int: Número de páginas encontradas.
        """
        sel = self._ensure_selenium()

        try:
            # Procura links de paginação numérica
            pagination_links = self._driver.find_elements(
                sel['By'].XPATH,
                "//a[contains(@id, 'form:') and string-length(text()) < 3]"
            )

            page_numbers = []
            for link in pagination_links:
                text = link.text.strip()
                if text.isdigit():
                    page_numbers.append(int(text))

            if page_numbers:
                total = max(page_numbers)
                self.logger.debug(f"Páginas encontradas via links: {total}")
                return total

            # Se não houver paginação, verifica se há resultados
            try:
                table = self._driver.find_element(sel['By'].ID, "form:grid")
                if table:
                    self.logger.debug("Tabela encontrada, assumindo 1 página")
                    return 1
            except sel['NoSuchElementException']:
                pass

            return 0

        except Exception as e:
            self.logger.warning(f"Erro ao determinar páginas: {e}")
            return 1

    def _paginar_por_numero(self, numero: int) -> bool:
        """Navega para página específica via link numerado.

        Sobrescreve o método base para usar seletor específico do SaudeLegis.

        Args:
            numero: Número da página destino.

        Returns:
            bool: True se navegou com sucesso.
        """
        sel = self._ensure_selenium()

        try:
            # Seletor específico do SaudeLegis
            xpath = f"//a[text()='{numero}' and contains(@id, 'form:')]"
            link = sel['WebDriverWait'](self._driver, 5).until(
                sel['EC'].element_to_be_clickable((sel['By'].XPATH, xpath))
            )

            self._driver.execute_script("arguments[0].click();", link)

            import time
            time.sleep(self.between_pages_wait)
            return True

        except sel['TimeoutException']:
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
