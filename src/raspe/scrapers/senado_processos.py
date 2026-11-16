"""Raspador de processos legislativos do Senado Federal pela API oficial de Dados Abertos.

Consulta ``https://legis.senado.leg.br/dadosabertos/processo``, que devolve
JSON. A fonte é outra em relação a ``raspe.senado()``: aquele lê a busca de
legislação (normas já publicadas) no portal; este lista os processos
legislativos (projetos de lei, PECs, requerimentos...) do Senado e do
Congresso Nacional, tenham virado norma ou não.

Exemplo:
    >>> import raspe
    >>> df = raspe.senado_processos().raspar(pesquisa="telemedicina", ano=2020)
    >>> df[["identificacao", "ementa", "situacao_atual"]].head()
"""

import json
from datetime import date
from typing import Any, Literal

import pandas as pd
import requests

from ..base_scraper import BaseScraper
from ..exceptions import APIError, ValidationError
from ..schemas.senado_processos import InputSenadoProcessos, OutputSenadoProcessos
from ..utils import dividir_periodo

# Coluna do DataFrame -> campo de cada processo na resposta da API. Estes vêm em todo processo.
_CAMPOS_OBRIGATORIOS = {
    'id': 'id',
    'codigo_materia': 'codigoMateria',
    'identificacao': 'identificacao',
    'ementa': 'ementa',
    'tipo_documento': 'tipoDocumento',
    'tipo_conteudo': 'tipoConteudo',
    'autoria': 'autoria',
    'casa_identificadora': 'casaIdentificadora',
    'ente_identificador': 'enteIdentificador',
    'data_apresentacao': 'dataApresentacao',
    'tramitando': 'tramitando',
}
# Estes a API só manda para parte dos processos; na falta, a coluna fica nula.
_CAMPOS_OPCIONAIS = {
    'apelido': 'apelido',
    'objetivo': 'objetivo',
    'situacao_atual': 'situacaoAtual',
    'data_situacao_atual': 'dataSituacaoAtual',
    'data_deliberacao': 'dataDeliberacao',
    'sigla_tipo_deliberacao': 'siglaTipoDeliberacao',
    'norma_gerada': 'normaGerada',
    'ultima_informacao_atualizada': 'ultimaInformacaoAtualizada',
    'data_ultima_atualizacao': 'dataUltimaAtualizacao',
    'url_documento': 'urlDocumento',
}


def _hoje() -> str:
    """Devolve a data de hoje em YYYY-MM-DD (função própria para os testes fixarem o dia)."""
    return date.today().isoformat()


class ScraperSenadoProcessos(BaseScraper):
    """Raspador dos processos legislativos do Senado Federal, pela API de Dados Abertos.

    Quatro regras da API, vistas ao vivo em 2026-11-16:

    - Ela devolve a consulta inteira numa resposta só, sem paginação.
    - Só com ``pesquisa``, ela devolveria apenas os processos que ainda
      tramitam, e só com ``data_fim``, apenas os do ano anterior a essa data.
      Para o resultado não sair cortado sem aviso, ``raspar()`` exige ``ano``
      ou ``data_inicio``.
    - Sem ``ano``, o período de uma consulta não passa de um ano: com as duas
      datas mais distantes, a API responde 400; só com ``data_inicio``, ela
      corta o resultado em um ano, sem avisar. O raspador divide o período
      (até ``data_fim`` ou, sem ela, até hoje) em janelas seguidas de até
      ``MESES_POR_CONSULTA`` meses, faz uma consulta por janela e junta os
      processos sem repetir.
    - Com ``ano``, o período não tem limite, e a busca sai numa consulta só.
    """

    schema_entrada = InputSenadoProcessos
    schema_saida = OutputSenadoProcessos

    # Maior período que a API aceita numa consulta sem ``ano``.
    MESES_POR_CONSULTA = 12

    def __init__(self, debug: bool = True):
        super().__init__("SENADO_PROCESSOS", debug)
        self.session.headers.update({"Accept": "application/json"})
        # A API admite 10 requisições por segundo; 1 s entre janelas basta.
        self.sleep_time = 1

        self._api_base = "https://legis.senado.leg.br/dadosabertos/processo"
        self._type: Literal['JSON'] = 'JSON'
        # A API não pagina: ver _set_query_atual.
        self._query_page_name = ''
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
        """Valida os parâmetros e recusa a busca sem ``ano`` e sem ``data_inicio``.

        Args:
            **kwargs: Parâmetros de ``raspar()``.

        Returns:
            dict: Parâmetros validados, com as datas em YYYY-MM-DD.

        Raises:
            ValidationError: Se algum parâmetro for inválido, ou se faltarem
                ``ano`` e ``data_inicio`` (ver a docstring da classe).
        """
        kwargs = super()._validar_parametros(**kwargs)
        if not kwargs.get('ano') and not kwargs.get('data_inicio'):
            raise ValidationError(
                f"{type(self).__name__}.raspar() precisa de 'ano' ou de 'data_inicio': sem eles, a API do Senado "
                "só devolve os processos que ainda tramitam ou, com 'data_fim', os do ano anterior a ela."
            )
        return kwargs

    def _dividir_busca(self, **kwargs) -> list[dict[str, Any]]:
        """Sem ``ano``, divide o período em janelas de até ``MESES_POR_CONSULTA`` meses.

        Args:
            **kwargs: Parâmetros já validados; as datas chegam em YYYY-MM-DD.

        Returns:
            list[dict]: Com ``ano``, a busca como veio. Sem ele, uma consulta
            por janela, de ``data_inicio`` até ``data_fim`` ou, sem ela, até hoje.
        """
        if kwargs.get('ano'):
            return [kwargs]
        janelas = dividir_periodo(kwargs['data_inicio'], kwargs.get('data_fim') or _hoje(), self.MESES_POR_CONSULTA)
        return [{**kwargs, 'data_inicio': inicio, 'data_fim': fim} for inicio, fim in janelas]

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        """Monta os parâmetros da consulta à API.

        Args:
            **kwargs: Parâmetros já validados; as datas chegam em YYYY-MM-DD.

        Returns:
            dict: Parâmetros da consulta.
        """
        nomes = {
            'termo': kwargs.get('pesquisa'),
            'sigla': kwargs.get('sigla_tipo'),
            'ano': kwargs.get('ano'),
            'dataInicioApresentacao': kwargs.get('data_inicio'),
            'dataFimApresentacao': kwargs.get('data_fim'),
        }
        return {nome: valor for nome, valor in nomes.items() if valor}

    def _set_query_atual(self, query_real: dict[str, Any], pag: int) -> dict[str, Any]:
        """Devolve a consulta sem parâmetro de página, que a API não tem.

        Args:
            query_real: Parâmetros de :meth:`_set_query_base`.
            pag: Página pedida (sempre 1).

        Returns:
            dict: Cópia de ``query_real``.
        """
        return dict(query_real)

    def _find_n_pags(self, r0: requests.Response) -> int:
        """Conta 1 página se a resposta traz processos e 0 se a lista vem vazia.

        Args:
            r0: Resposta da consulta.

        Returns:
            int: 1 com resultados, 0 sem.

        Raises:
            APIError: Se a API recusar a consulta (4xx), com a explicação que
                ela dá, ou se a resposta não for uma lista JSON.
        """
        self._levantar_se_recusada(r0)
        try:
            processos = r0.json()
        except ValueError:
            processos = None
        if not isinstance(processos, list):
            raise APIError(
                f"{self.nome_buscador}: a resposta da API não é a lista de processos esperada",
                status_code=r0.status_code,
                response_text=r0.text,
            )
        return 1 if processos else 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        """Lê a resposta JSON da API, um processo por linha.

        Args:
            path: Caminho do arquivo JSON salvo.

        Returns:
            pd.DataFrame: DataFrame com as colunas de ``self.colunas``.

        Raises:
            KeyError: Se um processo vier sem um campo que a API manda sempre. A API
                mudou de formato, e :meth:`_parse_data` leva o erro a quem chamou.
        """
        with open(path, 'r', encoding='utf-8') as f:
            processos = json.load(f)

        registros = [
            {
                **{coluna: processo[campo] for coluna, campo in _CAMPOS_OBRIGATORIOS.items()},
                **{coluna: processo.get(campo) for coluna, campo in _CAMPOS_OPCIONAIS.items()},
            }
            for processo in processos
        ]
        return pd.DataFrame(registros, columns=self.colunas)
