from ..base_scraper import BaseScraper
from typing import Any, Literal
import pandas as pd
import json
import base64
import time
from datetime import datetime
from tqdm import tqdm
import os


class ScraperNYT(BaseScraper):
    """Scraper para o buscador do New York Times via GraphQL.

    Busca artigos do NYT por termo de pesquisa e intervalo de datas.

    Exemplo de uso:
        scraper = ScraperNYT()

        # Busca simples
        df = scraper.raspar(texto="supreme court", ano=2024)

        # Busca com datas específicas
        df = scraper.raspar(
            texto="climate change",
            data_inicio="2024-01-01",
            data_fim="2024-06-30"
        )

        # Limitar número de resultados
        df = scraper.raspar(texto="election", ano=2024, max_resultados=100)
    """

    GRAPHQL_ENDPOINT = "https://samizdat-graphql.nytimes.com/graphql/v2"
    PERSISTED_QUERY_HASH = "2f5041641b9de748b42e5732e25b735d26f0ae188c900e15029287f391427ddf"
    RESULTS_PER_PAGE = 10

    def __init__(self):
        super().__init__("NYT")

        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": "https://www.nytimes.com",
            "Referer": "https://www.nytimes.com/",
            "nyt-app-type": "project-vi",
            "nyt-app-version": "0.0.5",
            "nyt-token": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAs+/oUCTBmD/cLdmcecrnBMHiU/pxQCn2DDyaPKUOXxi4p0uUSZQzsuq1pJ1m5z1i0YGPd1U1OeGHAChWtqoxC7bFMCXcwnE1oyui9G1uobgpm1GdhtwkR7ta7akVTcsF8zxiXx7DNXIPd2nIJFH83rmkZueKrC4JVaNzjvD+Z03piLn5bHWU6+w+rA+kyJtGgZNTXKyPh6EC6o5N+rknNMG5+CdTq35p8f99WjFawSvYgP9V64kgckbTbtdJ6YhVP58TnuYgr12urtwnIqWP9KSJ1e5vmgf3tunMqWNm6+AnsqNj8mCLdCuc5cEB74CwUeQcP2HQQmbCddBy2y0mEwIDAQAB",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        })

        self._api_base = self.GRAPHQL_ENDPOINT
        self._type = 'JSON'
        self._query_page_name = 'cursor'  # Usamos cursor, não page number
        self._api_method = 'GET'

        # Atributos internos para controle de paginação por cursor
        self._current_cursor = None
        self._has_next_page = True

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
        """Monta os parâmetros base da query GraphQL.

        Args:
            texto: Termo de busca
            ano: Ano para filtrar (usa ano inteiro)
            data_inicio: Data inicial no formato YYYY-MM-DD
            data_fim: Data final no formato YYYY-MM-DD
            sort: Ordenação ('best', 'newest', 'oldest')
            max_resultados: Limite máximo de resultados

        Returns:
            dict: Parâmetros da query
        """
        texto = kwargs.get('texto', '')
        ano = kwargs.get('ano')
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')
        sort = kwargs.get('sort', 'best')
        self._max_resultados = kwargs.get('max_resultados')

        # Se ano foi especificado, usar ano inteiro
        if ano and not data_inicio:
            data_inicio = f"{ano}-01-01"
        if ano and not data_fim:
            data_fim = f"{ano}-12-31"

        # Formatar datas para o formato esperado pelo NYT
        if data_inicio:
            begin_date = f"{data_inicio}T00:00:00-05:00"
        else:
            begin_date = ""

        if data_fim:
            end_date = f"{data_fim}T23:59:59-05:00"
        else:
            end_date = ""

        # Reset do cursor para nova busca
        self._current_cursor = None
        self._has_next_page = True

        return {
            "texto": texto,
            "beginDate": begin_date,
            "endDate": end_date,
            "sort": sort
        }

    def _build_graphql_url(self, texto: str, begin_date: str, end_date: str,
                           sort: str, cursor: str = None) -> str:
        """Constrói a URL completa para a requisição GraphQL."""
        variables = {
            "first": self.RESULTS_PER_PAGE,
            "sort": sort,
            "beginDate": begin_date,
            "endDate": end_date,
            "lang": "EN",
            "text": texto,
            "sectionFacetFilterQuery": "",
            "typeFacetFilterQuery": "",
            "sectionFacetActive": False,
            "typeFacetActive": False
        }

        if cursor:
            variables["cursor"] = cursor

        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": self.PERSISTED_QUERY_HASH
            }
        }

        params = {
            "operationName": "SearchRootQuery",
            "variables": json.dumps(variables, separators=(',', ':')),
            "extensions": json.dumps(extensions, separators=(',', ':'))
        }

        return params

    def _find_n_pags(self, r0) -> int:
        """Extrai o número total estimado de páginas.

        Como o NYT usa cursor-based pagination, estimamos baseado no total de hits.
        """
        if r0.status_code >= 400:
            self.logger.warning(f"Erro {r0.status_code}: {r0.text[:200]}")
            return 0

        try:
            data = r0.json()

            # Verificar se o hash da persisted query expirou
            errors = data.get('errors', [])
            for error in errors:
                if 'PersistedQueryNotFound' in str(error):
                    self.logger.error(
                        "PERSISTED_QUERY_HASH expirou! O NYT atualizou a API. "
                        "Acesse https://www.nytimes.com/search e inspecione as "
                        "requisições GraphQL para obter o novo hash."
                    )
                    return 0

            search_data = data.get('data', {}).get('search', {})
            hits_data = search_data.get('hits', {})
            total_hits = hits_data.get('totalCount', 0)

            # Salvar informações de paginação
            page_info = hits_data.get('pageInfo', {})
            self._has_next_page = page_info.get('hasNextPage', False)
            self._current_cursor = page_info.get('endCursor')

            n_pags = (total_hits + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE

            # Se max_resultados definido, limitar páginas
            if self._max_resultados:
                max_pags = (self._max_resultados + self.RESULTS_PER_PAGE - 1) // self.RESULTS_PER_PAGE
                n_pags = min(n_pags, max_pags)

            self.logger.info(f"Total de resultados: {total_hits}, páginas estimadas: {n_pags}")
            return n_pags

        except Exception as e:
            self.logger.error(f"Erro ao extrair n_pags: {e}")
            return 0

    def _download_data(self, **kwargs) -> str:
        """Override do método de download para usar cursor-based pagination."""
        self.logger.debug("Definindo consulta")
        query_base = self._set_query_base(**kwargs)
        self.logger.debug(query_base)

        # Primeira requisição para obter total de resultados
        params = self._build_graphql_url(
            texto=query_base["texto"],
            begin_date=query_base["beginDate"],
            end_date=query_base["endDate"],
            sort=query_base["sort"]
        )

        r0 = self.session.get(self.api_base, params=params, timeout=self.timeout)
        n_pags = self._find_n_pags(r0)

        if n_pags == 0:
            self.logger.warning("Nenhum resultado encontrado")
            download_dir = self._create_download_dir()
            return download_dir

        download_dir = self._create_download_dir()

        # Salvar primeira página
        file_name = f"{download_dir}/{self.nome_buscador}_00001.json"
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(r0.text)
        self.logger.debug(f"Arquivo salvo: {file_name}")

        # Limitar páginas se necessário
        paginas = kwargs.get("paginas")
        if paginas:
            max_pag = min(paginas.stop, n_pags + 1) if hasattr(paginas, 'stop') else n_pags
        else:
            max_pag = n_pags

        # Download das páginas seguintes usando cursor
        current_cursor = self._current_cursor

        for pag in tqdm(range(2, max_pag + 1), desc="Baixando resultados"):
            if not current_cursor:
                self.logger.debug("Sem cursor, finalizando")
                break

            time.sleep(self.sleep_time)
            self.logger.debug(f"Baixando página {pag}, cursor: {current_cursor[:20]}...")

            params = self._build_graphql_url(
                texto=query_base["texto"],
                begin_date=query_base["beginDate"],
                end_date=query_base["endDate"],
                sort=query_base["sort"],
                cursor=current_cursor
            )

            try:
                r = self.session.get(self.api_base, params=params, timeout=self.timeout)

                if r.status_code >= 500:
                    self.logger.warning(f"Erro {r.status_code}, ignorando página {pag}")
                    continue

                # Extrair próximo cursor
                data = r.json()
                hits_data = data.get('data', {}).get('search', {}).get('hits', {})
                page_info = hits_data.get('pageInfo', {})
                current_cursor = page_info.get('endCursor')
                has_next = page_info.get('hasNextPage', False)

                file_name = f"{download_dir}/{self.nome_buscador}_{pag:05d}.json"
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(r.text)
                self.logger.debug(f"Arquivo salvo: {file_name}")

                if not has_next:
                    self.logger.debug("Última página alcançada")
                    break

            except Exception as e:
                self.logger.error(f"Erro ao baixar página {pag}: {e}")
                continue

        return download_dir

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Analisa uma página JSON e extrai os artigos."""
        columns = ['titulo', 'url', 'data_publicacao', 'secao', 'subsecao',
                   'tipo', 'resumo', 'autores', 'imagem_url']

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            search_data = data.get('data', {}).get('search', {})
            hits_data = search_data.get('hits', {})
            edges = hits_data.get('edges', [])

            if not edges:
                return pd.DataFrame(columns=columns)

            articles = []
            for edge in edges:
                node = edge.get('node', {})

                # Extrair autores do renderedRepresentation
                bylines = node.get('bylines', [])
                autores = []
                for byline in bylines:
                    rendered = byline.get('renderedRepresentation', '')
                    if rendered:
                        # Remove "By " do início se presente
                        autor = rendered.replace('By ', '').strip()
                        if autor:
                            autores.append(autor)

                # Extrair imagem do promotionalMedia
                imagem_url = ''
                promo_media = node.get('promotionalMedia', {})
                if promo_media and promo_media.get('__typename') == 'Image':
                    crops = promo_media.get('crops', [])
                    if crops:
                        renditions = crops[0].get('renditions', [])
                        if renditions:
                            imagem_url = renditions[0].get('url', '')

                # Extrair seção e subseção
                section = node.get('section', {})
                subsection = node.get('subsection', {})

                article = {
                    'titulo': node.get('creativeWorkHeadline', {}).get('default', ''),
                    'url': node.get('url', ''),
                    'data_publicacao': node.get('firstPublished', ''),
                    'secao': section.get('displayName', '') if section else '',
                    'subsecao': subsection.get('displayName', '') if subsection else '',
                    'tipo': node.get('__typename', ''),
                    'resumo': node.get('creativeWorkSummary', ''),
                    'autores': ', '.join(autores),
                    'imagem_url': imagem_url
                }
                articles.append(article)

            return pd.DataFrame(articles, columns=columns)

        except Exception as e:
            self.logger.error(f"Erro ao processar {path}: {e}")
            return pd.DataFrame(columns=columns)
