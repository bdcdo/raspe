import re
import warnings
from typing import Any, Literal

import pandas as pd
import urllib3

from ..base_scraper import BaseScraper
from ..html_scraper import HTMLScraper
from ..schemas.presidencia import InputPresidencia, OutputPresidencia
from ..utils import nivel_de_pilha_fora_do_pacote


class ScraperPresidencia(BaseScraper, HTMLScraper):
    schema_entrada = InputPresidencia
    schema_saida = OutputPresidencia

    def __init__(self, debug: bool = True):
        super().__init__("PRESIDENCIA", debug)

        # Workaround: O servidor da Presidência tem cadeia de certificados SSL incompleta.
        # Desabilita verificação SSL para evitar SSLError.
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False

        self.query_page_multiplier = 10
        self.query_page_increment = -10
        self.session.headers.update({
            "Accept": "*/*",
            "Origin": "https://legislacao.presidencia.gov.br",
            "Referer": "https://legislacao.presidencia.gov.br/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "DNT": "1",
            "Priority": "u=0",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
            "X-Requested-With": "XMLHttpRequest"
        })

        self._api_base = "https://legislacao.presidencia.gov.br/pesquisa/ajax/resultado_pesquisa_legislacao.php"
        self._type: Literal['HTML'] = 'HTML'
        self._query_page_name = 'posicao'
        self._api_method: Literal['POST'] = 'POST'

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
    def api_method(self) -> Literal['POST']:
        return self._api_method

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        pesquisa = kwargs.get('pesquisa')

        query_inicial = {
                'termo': pesquisa,
                'ordenacao': 'maior_data',
                'posicao': '0'
            }

        return query_inicial

    def _find_n_pags(self, r0) -> int:
        # Erros 429 e 5xx são tratados automaticamente pelo BaseScraper._request_with_retry()
        r0.raise_for_status()

        r0s = self.soup_it(r0.content)
        h4_tag = r0s.find('h4')
        num_text = h4_tag.text if h4_tag else ''
        self.logger.debug(f"Found h4 text: '{num_text}'")

        # "1.006 resultados encontrados"; na falta, o primeiro número do h4.
        # O ponto é separador de milhar.
        match = (re.search(r'([\d.]+)\s+resultados?\s+encontrados?', num_text, re.IGNORECASE)
                 or re.search(r'(\d[\d.]*)', num_text))
        if not match:
            return self._confirmar_busca_vazia(r0s)
        num = int(match.group(1).replace('.', ''))

        self.logger.debug(f"Extracted number of results: {num}")

        # Convert results to pages (assuming 10 results per page)
        pages = (num + 9) // 10  # Round up division
        self.logger.debug(f"Calculated pages: {pages}")
        return pages

    def _parse_page(self, path) -> pd.DataFrame:
        from bs4 import BeautifulSoup

        with open(path, 'r', encoding='utf-8') as file:
            html_content = file.read()

        lista_infos = []
        sem_ficha: list[str] = []

        soup = BeautifulSoup(html_content, 'html.parser')
        card_body = soup.find('div', class_='card-body p-0')

        if not card_body:
            return pd.DataFrame(columns=self.colunas)

        container = card_body.find('div')
        if not container:
            return pd.DataFrame(columns=self.colunas)

        itens = container.find_all('div')

        for i, item in enumerate(itens):
            if i % 2 == 1:
                continue
            try:
                titulo = item.select_one('h4 a')
                paragraphs = item.find_all('p')

                if titulo and len(paragraphs) >= 2:
                    link = titulo['href']
                    # Selos como "Veto Parcial" vêm num <span class="badge"> no título, colados ao nome.
                    rotulo = ', '.join(selo.extract().get_text(strip=True)
                                       for selo in item.select('h4 span.badge'))
                    nome = titulo.text.strip()
                    # A ficha é o botão "Ficha"; os outros links do card citam leis na ementa.
                    ficha = next((a.get('href', '') for a in item.select('a.btn')
                                  if a.get_text(strip=True) == 'Ficha'), '')
                    if not ficha:
                        sem_ficha.append(nome)
                    revogacao = paragraphs[0].text
                    descricao = paragraphs[1].text

                    lista_infos.append([nome, link, ficha, revogacao, descricao, rotulo])
            except Exception as e:
                self.logger.warning(f"Erro ao processar item em {path}: {e}")
                continue

        df = pd.DataFrame(lista_infos, columns=self.colunas)

        # Fora do try de cada ato, para o aviso (erro, com warnings virando erro) não descartar um ato.
        if sem_ficha:
            warnings.warn(
                f"Presidência: {len(sem_ficha)} ato(s) sem o botão \"Ficha\", com a coluna ficha vazia: "
                f"{sem_ficha}. O portal pode ter mudado de layout.",
                UserWarning,
                stacklevel=nivel_de_pilha_fora_do_pacote(),
            )
        return df
