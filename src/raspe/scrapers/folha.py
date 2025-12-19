"""Raspador para busca de notícias da Folha de São Paulo."""

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from ..utils import validar_data
from ..exceptions import ValidationError
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
        site: 'todos', 'online' ou 'jornal' (padrão: 'todos')
        data_inicio: Data inicial no formato YYYY-MM-DD (opcional)
        data_fim: Data final no formato YYYY-MM-DD (opcional)
    """

    SITES_VALIDOS = ('todos', 'online', 'jornal')

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

    def _formatar_data_br(self, data_iso: str) -> str:
        """Converte data normalizada (YYYY-MM-DD) para formato brasileiro (DD/MM/YYYY).

        Args:
            data_iso: Data no formato ISO (YYYY-MM-DD), já validada por validar_data().

        Returns:
            Data no formato DD/MM/YYYY para a API da Folha.
        """
        if not data_iso:
            return ""
        ano, mes, dia = data_iso.split("-")
        return f"{dia}/{mes}/{ano}"

    def _validar_parametros(self, **kwargs) -> dict[str, Any]:
        """Valida e normaliza parâmetros de busca.

        Sobrescreve o método base para adicionar validação do parâmetro 'site'.

        Args:
            **kwargs: Parâmetros de busca.

        Returns:
            Parâmetros validados e normalizados.

        Raises:
            ValidationError: Se 'site' não for um valor válido.
        """
        params = super()._validar_parametros(**kwargs)

        site = params.get('site', 'todos')
        if site not in self.SITES_VALIDOS:
            raise ValidationError(
                f"'site' deve ser um dos valores: {', '.join(self.SITES_VALIDOS)}. "
                f"Valor recebido: '{site}'"
            )

        return params

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Monta a query base para busca na Folha.

        Args:
            pesquisa: Termo de busca.
            site: 'todos', 'online' ou 'jornal'.
            data_inicio: Data inicial (aceita vários formatos, será normalizada).
            data_fim: Data final (aceita vários formatos, será normalizada).

        Returns:
            Dicionário com os parâmetros da query.
        """
        pesquisa = kwargs.get('pesquisa', '')
        site = kwargs.get('site', 'todos')

        query = {
            'q': pesquisa,
            'site': site,
            'periodo': 'todos',
            'sr': 1
        }

        # Datas já foram validadas e normalizadas para YYYY-MM-DD pelo BaseScraper
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')

        if data_inicio or data_fim:
            query['periodo'] = 'personalizado'
            if data_inicio:
                query['sd'] = self._formatar_data_br(data_inicio)
            if data_fim:
                query['ed'] = self._formatar_data_br(data_fim)

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

        Extrai link, título, resumo e data de cada notícia.

        Args:
            path: Caminho do arquivo HTML salvo.

        Returns:
            DataFrame com as colunas: link, titulo, resumo, data.
        """
        columns = ['link', 'titulo', 'resumo', 'data']

        try:
            with open(path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = self.soup_it(html_content)

            # Estrutura: ol.u-list-unstyled.c-search > li (cada notícia)
            lista_noticias = soup.find("ol", class_="u-list-unstyled c-search")
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
