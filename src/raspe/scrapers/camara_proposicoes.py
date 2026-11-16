"""Raspador de proposições da Câmara dos Deputados pela API oficial de Dados Abertos.

Consulta ``https://dadosabertos.camara.leg.br/api/v2/proposicoes``, que devolve
JSON. A fonte é outra em relação a ``raspe.camara()``: aquele lê a busca de
legislação (normas já publicadas) no portal; este lista proposições (projetos
de lei, PECs, requerimentos...), tenham virado norma ou não.

Exemplo:
    >>> import raspe
    >>> df = raspe.camara_proposicoes().raspar(pesquisa="telemedicina", ano=2020)
    >>> df[["sigla_tipo", "numero", "ano", "ementa"]].head()
"""

import json
from typing import Any, Literal

import pandas as pd
import requests

from ..base_scraper import BaseScraper
from ..exceptions import APIError, ValidationError
from ..schemas.camara_proposicoes import InputCamaraProposicoes, OutputCamaraProposicoes

# Coluna do DataFrame -> campo de cada item de ``dados`` na resposta da API.
_CAMPOS = {
    'id': 'id',
    'uri': 'uri',
    'sigla_tipo': 'siglaTipo',
    'cod_tipo': 'codTipo',
    'numero': 'numero',
    'ano': 'ano',
    'ementa': 'ementa',
    'data_apresentacao': 'dataApresentacao',
}


class ScraperCamaraProposicoes(BaseScraper):
    """Raspador das proposições da Câmara dos Deputados, pela API de Dados Abertos.

    Duas regras da API, vistas ao vivo em 2026-11-16:

    - Sem filtro de tempo, ela só lista as proposições apresentadas ou
      movimentadas nos últimos 30 dias. Para a busca sem ``ano``,
      ``data_inicio`` nem ``data_fim`` cobrir a base inteira, como nas outras
      fontes do raspe, o raspador envia ``INICIO_DA_BASE`` como data inicial de
      apresentação quando nenhum dos três vem.
    - A base inteira só sai com ``pesquisa``: sem termo, a API não responde a
      tempo (504). Por isso ``raspar()`` sem ``pesquisa`` exige ``ano``,
      ``data_inicio`` ou ``data_fim``.
    - ``data_inicio`` e ``data_fim`` juntas não podem distar mais de 3 meses: a
      API responde 400, e o raspador levanta ``APIError`` com a explicação dela.
      Uma data só (ou ``ano``) não tem esse limite.
    """

    schema_entrada = InputCamaraProposicoes
    schema_saida = OutputCamaraProposicoes

    # Máximo de itens por página que a API aceita (visto ao vivo em 2026-11-16).
    ITENS_POR_PAGINA = 100
    INICIO_DA_BASE = "1900-01-01"

    def __init__(self, debug: bool = True):
        super().__init__("CAMARA_PROPOSICOES", debug)
        self.session.headers.update({"Accept": "application/json"})

        self._api_base = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
        self._type: Literal['JSON'] = 'JSON'
        self._query_page_name = 'pagina'
        self._api_method: Literal['GET'] = 'GET'

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['JSON']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET']:
        return self._api_method

    def _validar_parametros(self, **kwargs) -> dict[str, Any]:
        """Valida os parâmetros e recusa a busca sem termo e sem filtro de tempo.

        Args:
            **kwargs: Parâmetros de ``raspar()``.

        Returns:
            dict: Parâmetros validados, com as datas em YYYY-MM-DD.

        Raises:
            ValidationError: Se algum parâmetro for inválido, ou se faltarem
                ``pesquisa`` e os três filtros de tempo (a API não responde a
                essa consulta; ver a docstring da classe).
        """
        kwargs = super()._validar_parametros(**kwargs)
        if not any(kwargs.get(nome) for nome in ('pesquisa', 'ano', 'data_inicio', 'data_fim')):
            raise ValidationError(
                f"{type(self).__name__}.raspar() precisa de 'pesquisa' ou de um filtro de tempo "
                "('ano', 'data_inicio' ou 'data_fim'): sem eles, a API da Câmara não responde a tempo."
            )
        return kwargs

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Monta os parâmetros da consulta à API.

        Args:
            **kwargs: Parâmetros já validados; as datas chegam em YYYY-MM-DD.

        Returns:
            dict: Parâmetros comuns a todas as páginas. A ordenação por ``id``
            mantém a paginação estável entre uma requisição e a seguinte.
        """
        pesquisa = kwargs.get('pesquisa')
        ano = kwargs.get('ano')
        sigla_tipo = kwargs.get('sigla_tipo')
        data_inicio = kwargs.get('data_inicio')
        data_fim = kwargs.get('data_fim')

        query: dict[str, Any] = {
            'itens': self.ITENS_POR_PAGINA,
            'ordenarPor': 'id',
            'ordem': 'ASC',
        }
        if pesquisa:
            query['keywords'] = pesquisa
        if sigla_tipo:
            query['siglaTipo'] = sigla_tipo
        if ano:
            query['ano'] = ano
        if not ano and not data_inicio and not data_fim:
            # Sem isto a API se limitaria aos últimos 30 dias (ver a docstring da classe).
            data_inicio = self.INICIO_DA_BASE
        if data_inicio:
            query['dataApresentacaoInicio'] = data_inicio
        if data_fim:
            query['dataApresentacaoFim'] = data_fim
        return query

    def _find_n_pags(self, r0: requests.Response) -> int:
        """Conta as páginas pelo header ``X-Total-Count`` da página 1.

        Args:
            r0: Resposta da página 1.

        Returns:
            int: Número de páginas (0 sem resultados).

        Raises:
            APIError: Se a API recusar a consulta (4xx), com a explicação que
                ela dá, ou se a resposta vier sem o header ``X-Total-Count`` ou
                com valor que não é um número.
        """
        if r0.status_code >= 400:
            try:
                detalhe = r0.json()['detail']
            except (ValueError, KeyError, TypeError):
                detalhe = r0.text
            raise APIError(
                f"{self.nome_buscador}: a API recusou a consulta (HTTP {r0.status_code}): {detalhe}",
                status_code=r0.status_code,
                response_text=r0.text,
            )
        total = r0.headers.get('X-Total-Count', '')
        if not total.isdigit():
            raise APIError(
                f"{self.nome_buscador}: resposta da API sem a contagem de resultados "
                f"(header X-Total-Count: {total!r})",
                status_code=r0.status_code,
                response_text=r0.text,
            )
        return self._paginas_para(int(total), self.ITENS_POR_PAGINA)

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Lê uma página JSON da API, um item de ``dados`` por linha.

        Args:
            path: Caminho do arquivo JSON salvo.

        Returns:
            pd.DataFrame: DataFrame com as colunas de ``self.colunas``.

        Raises:
            KeyError: Se a resposta ou um item vier sem um campo esperado. A API
                mudou de formato, e :meth:`_parse_data` leva o erro a quem chamou.
        """
        with open(path, 'r', encoding='utf-8') as f:
            dados = json.load(f)['dados']

        registros = [{coluna: item[campo] for coluna, campo in _CAMPOS.items()} for item in dados]
        return pd.DataFrame(registros, columns=self.colunas)
