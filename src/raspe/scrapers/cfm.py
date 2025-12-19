from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from typing import Any, Literal
import pandas as pd
from bs4 import BeautifulSoup
import re


class ScraperCFM(BaseScraper, HTMLScraper):
    """Scraper para normas do Conselho Federal de Medicina (CFM).

    Busca normas do CFM e dos Conselhos Regionais de Medicina (CRM) por termo de pesquisa.

    Exemplo de uso:
        scraper = ScraperCFM()
        # Busca por um termo
        df = scraper.raspar(texto="doenças raras")

        # Busca por múltiplos termos
        termos = ["doença rara", "medicamento órfão", "terapia órfã"]
        df = scraper.raspar(texto=termos)
    """

    def __init__(self):
        super().__init__("CFM")

        # Headers específicos do portal CFM
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,en-US;q=0.7,en;q=0.3",
            "Connection": "keep-alive",
            "DNT": "1",
            "Priority": "u=0, i",
            "Referer": "https://portal.cfm.org.br/buscar-normas-cfm-e-crm",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:141.0) Gecko/20100101 Firefox/141.0"
        })

        self._api_base = "https://portal.cfm.org.br/buscar-normas-cfm-e-crm/#resultado"
        self._type = 'HTML'
        self._query_page_name = 'pagina'
        self._api_method = 'GET'

        # Configuração de paginação: páginas começam em 1
        self.query_page_multiplier = 1
        self.query_page_increment = 0

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['JSON', 'HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET', 'POST']:
        return self._api_method

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Monta os parâmetros base da query.

        Args:
            texto: Termo de busca a ser pesquisado
            uf: UF do CRM (opcional, vazio = todos)
            revogada: Filtrar normas revogadas (opcional)
            numero: Número da norma (opcional)
            ano: Ano da norma (opcional)

        Returns:
            dict: Parâmetros da query
        """
        texto = kwargs.get('texto', '')
        uf = kwargs.get('uf', '')
        revogada = kwargs.get('revogada', '')
        numero = kwargs.get('numero', '')
        ano = kwargs.get('ano', '')

        # Query base com todos os tipos de norma do CFM
        query_inicial = {
            "tipo[0]": "R",  # Resolução
            "tipo[1]": "P",  # Parecer
            "tipo[2]": "E",  # Emenda
            "tipo[3]": "N",  # Norma
            "tipo[4]": "D",  # Decisão
            "uf": uf,
            "revogada": revogada,
            "numero": numero,
            "ano": ano,
            "ta": "OU",      # Operador lógico para assuntos
            "assunto[0]": "",
            "texto": texto,
            "pagina": "1"
        }

        return query_inicial

    def _find_n_pags(self, r0) -> int:
        """Extrai o número total de páginas da resposta inicial.

        Note:
            Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()

        Args:
            r0: Response da requisição inicial

        Returns:
            int: Número total de páginas
        """
        r0.raise_for_status()

        soup = self.soup_it(r0.content)

        # Buscar total de registros no texto da página
        all_text = soup.get_text()
        records_match = re.search(r'(\d+)\s+registros encontrados', all_text)

        if records_match:
            total_records = int(records_match.group(1))
            self.logger.debug(f"Total de registros encontrados: {total_records}")
        else:
            self.logger.warning("Não foi possível extrair o número de registros")
            return 0

        # Buscar informação de paginação
        pagination_info = {}
        page_info_divs = soup.find_all('div', class_='pt-3')

        for div in page_info_divs:
            text = div.text.strip()
            if 'Mostrando página' in text and 'de' in text:
                # Extrair página atual e total
                match = re.search(r'Mostrando página (\d+) de (\d+)', text)
                if match:
                    pagination_info['current_page'] = int(match.group(1))
                    pagination_info['total_pages'] = int(match.group(2))
                    self.logger.debug(f"Paginação encontrada: {pagination_info}")
                    return pagination_info['total_pages']

        # Fallback: buscar por links de paginação
        pagination_links = soup.find_all('a', class_='link-navigation')
        page_numbers = []

        for link in pagination_links:
            text = link.text.strip()
            if text.isdigit():
                page_numbers.append(int(text))

        if page_numbers:
            total_pages = max(page_numbers)
            self.logger.debug(f"Total de páginas encontrado via links: {total_pages}")
            return total_pages

        # Se não encontrou paginação, retorna 1 página (se há registros)
        return 1 if total_records > 0 else 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Analisa uma página HTML baixada e extrai os dados das normas.

        Args:
            path: Caminho para o arquivo HTML

        Returns:
            pd.DataFrame: DataFrame com as normas extraídas
        """
        columns = ['Tipo', 'UF', 'Nº/Ano', 'Situação', 'Ementa', 'Link']

        try:
            with open(path, 'r', encoding='utf-8') as file:
                html_content = file.read()

            soup = BeautifulSoup(html_content, 'html.parser')
            results_div = soup.find('div', attrs={'id': 'resultsNormas'})

            if not results_div:
                self.logger.debug(f"Div 'resultsNormas' não encontrada em {path}")
                return pd.DataFrame(columns=columns)

            articles = results_div.find_all('article')

            if not articles:
                self.logger.debug(f"Nenhum artigo encontrado em {path}")
                return pd.DataFrame(columns=columns)

            parsed_articles = []

            for article in articles:
                try:
                    article_data = self._parse_article(article)
                    if article_data:
                        parsed_articles.append(article_data)
                except Exception as e:
                    self.logger.warning(f"Erro ao processar artigo em {path}: {e}")
                    continue

            return pd.DataFrame(parsed_articles, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao analisar página {path}: {e}")
            return pd.DataFrame(columns=columns)

    def _parse_article(self, article) -> dict[str, str] | None:
        """Extrai informações de um artigo individual.

        Args:
            article: Tag BeautifulSoup do artigo

        Returns:
            dict: Dicionário com os dados do artigo ou None se falhar
        """
        result = {}

        # Extrair informações do cabeçalho
        header = article.find('div', class_='card-header')
        if header:
            ul = header.find('ul')
            if ul:
                items = ul.find_all('li')
                for item in items:
                    strong = item.find('strong')
                    p = item.find('p')
                    if strong and p:
                        key = strong.text.strip()
                        value = p.text.strip()
                        result[key] = value

        # Extrair ementa
        body = article.find('div', class_='card-body')
        if body:
            ementa_span = body.find('span')
            if ementa_span:
                result['Ementa'] = ementa_span.text.strip()

        # Extrair link para a norma
        link = body.find('a', class_='btn btn-primary') if body else None
        if link and link.get('href'):
            result['Link'] = link.get('href')

        # Verificar se conseguiu extrair pelo menos algumas informações essenciais
        if not result or 'Tipo' not in result:
            return None

        # Garantir que todas as colunas esperadas existam
        for col in ['Tipo', 'UF', 'Nº/Ano', 'Situação', 'Ementa', 'Link']:
            if col not in result:
                result[col] = ''

        return result
