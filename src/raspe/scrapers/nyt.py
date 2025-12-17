import os

from ..base_scraper import BaseScraper
from ..exceptions import APIKeyError, APIError
from typing import Any, Literal
import pandas as pd
import json


class ScraperNYT(BaseScraper):
    """Scraper para o New York Times via Article Search API oficial.

    Requer uma API key gratuita do NYT Developer Portal:
    https://developer.nytimes.com/get-started

    Busca artigos do NYT por termo de pesquisa e intervalo de datas.

    Exemplo de uso:
        scraper = ScraperNYT(api_key="sua-api-key")

        # Busca simples
        df = scraper.raspar(texto="supreme court", ano=2024)

        # Busca com datas específicas
        df = scraper.raspar(
            texto="climate change",
            data_inicio="2024-01-01",
            data_fim="2024-06-30"
        )

        # Busca com filtros avançados
        df = scraper.raspar(
            texto="election",
            ano=2024,
            filtro='section.name:"Politics"'
        )

    Limites da API:
        - 10 resultados por página
        - Máximo de 100 páginas (1000 resultados) por busca
        - Rate limit: 5 requisições por minuto, 500 por dia
    """

    API_BASE = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
    RESULTS_PER_PAGE = 10
    MAX_PAGES = 100

    def __init__(self, api_key: str | None = None):
        """Inicializa o scraper do NYT.

        Args:
            api_key: Chave de API do NYT Developer Portal.
                     Pode ser passada diretamente ou via variável de ambiente NYT_API_KEY.
                     Obtenha em: https://developer.nytimes.com/get-started
        """
        super().__init__("NYT")

        # Tenta obter API key do parâmetro ou variável de ambiente
        resolved_api_key = api_key or os.environ.get('NYT_API_KEY')

        if not resolved_api_key:
            raise APIKeyError(
                "\n"
                "╔══════════════════════════════════════════════════════════════════╗\n"
                "║  API KEY DO NEW YORK TIMES NECESSÁRIA                            ║\n"
                "╠══════════════════════════════════════════════════════════════════╣\n"
                "║                                                                  ║\n"
                "║  O raspador do NYT requer uma chave de API gratuita.             ║\n"
                "║                                                                  ║\n"
                "║  Como obter sua API key:                                         ║\n"
                "║  1. Acesse: https://developer.nytimes.com/get-started            ║\n"
                "║  2. Crie uma conta gratuita                                      ║\n"
                "║  3. Crie um novo 'App' e ative a 'Article Search API'            ║\n"
                "║  4. Copie sua API key                                            ║\n"
                "║                                                                  ║\n"
                "║  Como usar:                                                      ║\n"
                "║  • Opção 1: raspe.nyt(api_key='sua-chave-aqui')                  ║\n"
                "║  • Opção 2: export NYT_API_KEY='sua-chave-aqui'                  ║\n"
                "║                                                                  ║\n"
                "╚══════════════════════════════════════════════════════════════════╝"
            )

        self._api_key = resolved_api_key
        self._api_base = self.API_BASE
        self._type = 'JSON'
        self._query_page_name = 'page'
        self._api_method = 'GET'

        # Rate limit do NYT: 5 req/min = 12 segundos entre requisições
        self.sleep_time = 12

        # API do NYT usa página 0 como primeira página
        self.query_page_increment = -1

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
            texto: Termo de busca
            ano: Ano para filtrar (usa ano inteiro)
            data_inicio: Data inicial (aceita YYYY-MM-DD, DD/MM/YYYY ou YYYYMMDD)
            data_fim: Data final (aceita YYYY-MM-DD, DD/MM/YYYY ou YYYYMMDD)
            sort: Ordenação ('best', 'newest', 'oldest', 'relevance')
            filtro: Filtro adicional em sintaxe Lucene (fq)

        Returns:
            dict: Parâmetros da query

        Note:
            As datas são validadas automaticamente pelo BaseScraper._validar_parametros()
        """
        texto = kwargs.get('texto', '')
        ano = kwargs.get('ano')
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')
        sort = kwargs.get('sort', 'newest')
        filtro = kwargs.get('filtro', '')

        # Se ano foi especificado, usar ano inteiro
        if ano and not data_inicio:
            data_inicio = f"{ano}-01-01"
        if ano and not data_fim:
            data_fim = f"{ano}-12-31"

        params = {
            "api-key": self._api_key,
            "q": texto,
            "sort": sort,
        }

        # Formatar datas para YYYYMMDD (formato exigido pela API do NYT)
        # Datas já foram validadas e normalizadas para YYYY-MM-DD pelo BaseScraper
        if data_inicio:
            params["begin_date"] = data_inicio.replace("-", "")
        if data_fim:
            params["end_date"] = data_fim.replace("-", "")

        # Filtro adicional (Lucene syntax)
        if filtro:
            params["fq"] = filtro

        return params

    def _find_n_pags(self, r0) -> int:
        """Extrai o número total de páginas.

        Note:
            Erros 429 (rate limit) e 5xx são tratados automaticamente pelo
            BaseScraper._request_with_retry() antes de chegar aqui.

        Raises:
            APIKeyError: Se a API key for inválida ou expirada (401).
            APIError: Se ocorrer outro erro de API.
        """
        if r0.status_code == 401:
            raise APIKeyError(
                "API key inválida ou expirada. Verifique sua chave em:\n"
                "https://developer.nytimes.com/my-apps"
            )

        if r0.status_code >= 400:
            raise APIError(
                f"Erro na API do NYT: {r0.status_code}",
                status_code=r0.status_code,
                response_text=r0.text
            )

        try:
            data = r0.json()

            if data.get('status') != 'OK':
                error_msg = data.get('message', str(data))
                raise APIError(f"Resposta inválida da API: {error_msg}")

            meta = data.get('response', {}).get('meta', {})
            total_hits = meta.get('hits', 0)

            n_pags = (total_hits + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE

            # API limita a 100 páginas
            n_pags = min(n_pags, self.MAX_PAGES)

            self.logger.info(f"Total de resultados: {total_hits}, páginas: {n_pags}")
            return n_pags

        except (APIKeyError, APIError):
            raise
        except Exception as e:
            self.logger.error(f"Erro ao extrair n_pags: {e}")
            return 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Analisa uma página JSON e extrai os artigos."""
        columns = [
            'titulo', 'url', 'data_publicacao', 'secao', 'desk',
            'tipo', 'resumo', 'autor', 'palavras', 'imagem_url'
        ]

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            docs = data.get('response', {}).get('docs', [])

            if not docs:
                return pd.DataFrame(columns=columns)

            articles = []
            for doc in docs:
                # Extrair imagem da lista multimedia
                # A API retorna objetos com 'url', 'type', 'subtype', etc.
                imagem_url = ''
                multimedia = doc.get('multimedia', [])
                if multimedia and isinstance(multimedia, list):
                    for media in multimedia:
                        # Prioriza imagens maiores (xlarge > large > thumbnail)
                        subtype = media.get('subtype', '')
                        if subtype in ('xlarge', 'superJumbo', 'articleLarge'):
                            imagem_url = f"https://www.nytimes.com/{media.get('url', '')}"
                            break
                    # Fallback para qualquer imagem disponível
                    if not imagem_url and multimedia:
                        first_media = multimedia[0]
                        if first_media.get('url'):
                            imagem_url = f"https://www.nytimes.com/{first_media['url']}"

                # Extrair autor
                byline = doc.get('byline', {})
                autor = byline.get('original', '') if byline else ''

                article = {
                    'titulo': doc.get('headline', {}).get('main', ''),
                    'url': doc.get('web_url', ''),
                    'data_publicacao': doc.get('pub_date', ''),
                    'secao': doc.get('section_name', ''),
                    'desk': doc.get('desk', ''),
                    'tipo': doc.get('type_of_material', ''),
                    'resumo': doc.get('snippet', ''),
                    'autor': autor,
                    'palavras': doc.get('word_count', 0),
                    'imagem_url': imagem_url,
                }
                articles.append(article)

            return pd.DataFrame(articles, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao processar {path}: {e}")
            return pd.DataFrame(columns=columns)
