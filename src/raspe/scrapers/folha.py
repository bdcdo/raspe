"""Scraper para busca de notícias da Folha de São Paulo."""

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from typing import Any, Literal
import pandas as pd
import re


class ScraperFolha(BaseScraper, HTMLScraper):
    """Raspador para busca de notícias no site da Folha de São Paulo.

    Permite buscar artigos por termo de pesquisa, filtrar por site (online/jornal)
    e período de datas.

    Exemplo de uso:
        scraper = ScraperFolha()
        df = scraper.raspar(
            pesquisa="educação",
            data_inicio="2024-01-01",
            data_fim="2024-12-31"
        )

    Parâmetros de busca:
        pesquisa: Termo de busca (obrigatório)
        site: 'todos', 'online' ou 'jornal' (default: 'todos')
        data_inicio: Data inicial no formato YYYY-MM-DD (opcional)
        data_fim: Data final no formato YYYY-MM-DD (opcional)
    """

    def __init__(self):
        super().__init__("FOLHA")

        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3",
            "Connection": "keep-alive",
            "DNT": "1",
            "Priority": "u=0, i",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:146.0) Gecko/20100101 Firefox/146.0"
        })

        self._api_base = "https://search.folha.uol.com.br/search"
        self._type = 'HTML'
        self._query_page_name = 'sr'
        self._api_method = 'GET'

        # Paginação: sr=1, sr=26, sr=51... (incrementos de 25)
        self.query_page_multiplier = 25
        self.query_page_increment = -24  # página 1 = 1*25 + (-24) = 1

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

    def _format_date_to_br(self, date_str: str) -> str:
        """Converte data de YYYY-MM-DD para DD/MM/YYYY."""
        if not date_str:
            return ""
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
        return date_str

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Monta a query base para busca na Folha.

        Args:
            pesquisa: Termo de busca
            site: 'todos', 'online' ou 'jornal'
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)
        """
        pesquisa = kwargs.get('pesquisa', '')
        site = kwargs.get('site', 'todos')

        query = {
            'q': pesquisa,
            'site': site,
            'periodo': 'todos',
            'sr': 1
        }

        # Se datas fornecidas, usar periodo='personalizado'
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')

        if data_inicio or data_fim:
            query['periodo'] = 'personalizado'
            if data_inicio:
                query['sd'] = self._format_date_to_br(data_inicio)
            if data_fim:
                query['ed'] = self._format_date_to_br(data_fim)

        return query

    def _find_n_pags(self, r0) -> int:
        """Extrai o número total de páginas da resposta inicial.

        Procura pela contagem de resultados na div com classe c-search__result.
        """
        r0.raise_for_status()

        soup = self.soup_it(r0.content)

        # Procurar pela div que contém a contagem de resultados
        # Exemplo: "386 resultados"
        result_div = soup.find("div", class_=re.compile(r"c-search__result"))

        if not result_div:
            # Fallback: procurar em qualquer elemento com o texto de resultados
            result_div = soup.find(string=re.compile(r'\d+\s+resultado'))
            if result_div:
                match = re.search(r'(\d+)', result_div)
                if match:
                    num_results = int(match.group(1))
                    pages = (num_results + 24) // 25
                    self.logger.debug(f"Encontrados {num_results} resultados, {pages} páginas")
                    return pages

        if result_div:
            text = result_div.get_text()
            match = re.search(r'(\d+)', text)
            if match:
                num_results = int(match.group(1))
                pages = (num_results + 24) // 25
                self.logger.debug(f"Encontrados {num_results} resultados, {pages} páginas")
                return pages

        self.logger.warning("Não foi possível encontrar o número de resultados")
        return 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Analisa uma página de resultados da Folha.

        Extrai: link, título, resumo, data de cada notícia.
        """
        columns = ['link', 'titulo', 'resumo', 'data']

        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = self.soup_it(html_content)

            # Estrutura: ol > li (cada notícia)
            lista_noticias = soup.find("ol")
            if not lista_noticias:
                self.logger.warning(f"Lista de notícias não encontrada em {path}")
                return pd.DataFrame(columns=columns)

            noticias = lista_noticias.find_all("li")

            infos = []
            for noticia in noticias:
                try:
                    # Link
                    link_tag = noticia.find("a")
                    link = link_tag["href"] if link_tag and link_tag.has_attr("href") else "N/A"

                    # Título
                    h2_tag = noticia.find("h2")
                    titulo = h2_tag.text.strip() if h2_tag else "N/A"

                    # Resumo
                    p_tag = noticia.find("p")
                    resumo = p_tag.text.strip() if p_tag else "N/A"

                    # Data
                    time_tag = noticia.find("time")
                    data = time_tag.text.strip() if time_tag else "N/A"

                    infos.append([link, titulo, resumo, data])

                except Exception as e:
                    self.logger.warning(f"Erro ao processar notícia: {e}")
                    continue

            return pd.DataFrame(infos, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao analisar página {path}: {e}")
            return pd.DataFrame(columns=columns)
