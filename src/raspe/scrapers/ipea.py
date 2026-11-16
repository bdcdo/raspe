import warnings
from typing import Any, Literal

import pandas as pd

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from ..schemas.ipea import InputIpea, OutputIpea
from ..utils import nivel_de_pilha_fora_do_pacote


class ScraperIpea(BaseScraper, HTMLScraper):
    schema_entrada = InputIpea
    schema_saida = OutputIpea

    def __init__(self, download_path: str | None = None, debug: bool = True):
        """Inicializa o raspador do IPEA.

        Args:
            download_path: Descontinuado e ignorado. Para mudar a pasta dos
                arquivos baixados, atribua ``raspador.download_path``.
            debug: Se True, ativa logs de depuração e mantém arquivos baixados.
        """
        super().__init__("IPEA", debug)
        if download_path is not None:
            warnings.warn(
                "O parâmetro `download_path` de ScraperIpea é ignorado e será removido. Para mudar a pasta "
                "dos arquivos baixados, atribua `raspador.download_path` depois de criar o raspador.",
                DeprecationWarning,
                stacklevel=nivel_de_pilha_fora_do_pacote(),
            )

        self._api_base = "https://www.ipea.gov.br/portal/coluna-5/central-de-conteudo/busca-publicacoes"
        self._api_method: Literal['GET'] = 'GET'
        self._type: Literal['HTML'] = 'HTML'
        self._query_page_name = 'pagina'

        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "pt-BR,en-US;q=0.7,en;q=0.3",
            "Connection": "keep-alive",
            "DNT": "1",
            "Priority": "u=0, i",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0"
        })

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET']:
        return self._api_method

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        pesquisa = kwargs.get('pesquisa')

        query_inicial = {
                'palavra_chave': pesquisa,
                'tipo': '',
                'assunto': '',
                'autor': '',
                'timeperiods': 'all',
                'data-inicial': '',
                'data-final': '',
                'pagina': '1',
            }

        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        # "Resultado de 1 a 10 de <strong>3193</strong>"
        container = r0s.find('div', class_="col clearfix")
        h4 = container.find('h4') if container else None
        h4_tag = h4.find('strong') if h4 else None
        if not h4_tag:
            return self._confirmar_busca_vazia(r0s)
        num_text = h4_tag.get_text(strip=True)
        self.logger.debug(f"Found h4 text: '{num_text}'")

        num = int(num_text)

        self.logger.debug(f"Extracted number of results: {num}")

        pages = self._paginas_para(num, 10)
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup

        with open(path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        lista_infos = []

        soup = BeautifulSoup(html_content, 'html.parser')
        card_body = soup.find('div', class_='lista-publicacoes')

        if not card_body:
            return pd.DataFrame(columns=self.colunas)

        container = card_body.find('div')
        if not container:
            return pd.DataFrame(columns=self.colunas)

        itens = container.find_all('div', class_="row")
        erros: list[Exception] = []

        for original_item in itens:
            try:
                item = original_item.find('div', class_='publi-conteudo')
                if not item:
                    continue

                h3 = item.find('h3')
                if not h3:
                    continue
                anchor = h3.find('a')
                if not anchor:
                    continue

                autores_div = item.find('div', class_='autores')
                assuntos_div = item.find('div', class_='assuntos')
                p_element = item.find('p')

                link = 'https://www.ipea.gov.br' + str(anchor.get('href', ''))
                titulo = anchor.text.strip()
                autores = autores_div.text.strip() if autores_div else ''
                data = p_element.text.strip() if p_element else ''
                assuntos = self._limpar_assuntos(assuntos_div.get_text()) if assuntos_div else ''

                lista_infos.append([titulo, link, autores, data, assuntos])
            except Exception as e:
                self.logger.warning(f"Erro ao processar item em {path}: {e}")
                erros.append(e)

        self._conferir_itens(path, erros, len(lista_infos))
        return pd.DataFrame(lista_infos, columns=self.colunas)

    @staticmethod
    def _limpar_assuntos(texto: str) -> str:
        """Junta os temas do ``div.assuntos`` sem o rótulo "Temas:" e sem repetir tema.

        O portal escreve "Temas:" antes da lista, separa os temas com vírgula,
        quebra linha entre eles e repete alguns, ora como link, ora como texto solto.

        Args:
            texto: Texto do ``div.assuntos`` do card.

        Returns:
            Os temas, cada um uma vez, na ordem em que aparecem, separados por ", ".
        """
        sem_rotulo = texto.lstrip().removeprefix('Temas:')
        temas = (' '.join(parte.split()) for parte in sem_rotulo.split(','))
        return ', '.join(dict.fromkeys(tema for tema in temas if tema))


# Alias mantido por retrocompatibilidade: a classe foi renomeada de
# IpeaScraper para ScraperIpea, mas código existente que importa o nome
# antigo (`from raspe.scrapers.ipea import IpeaScraper`) continua funcionando.
IpeaScraper = ScraperIpea
