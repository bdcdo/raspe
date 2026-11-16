"""Contrato offline para ``ScraperSenadoProcessos.raspar``.

Os samples em ``tests/senado_processos/samples/raspar/`` são respostas reais
da API de Dados Abertos do Senado (``https://legis.senado.leg.br/dadosabertos/processo``),
gravadas por ``python -m tests.fixtures.capture.senado_processos``. A API não
pagina: o cenário ``typical`` é a busca que o raspador divide em duas consultas,
uma por janela de um ano.
"""

import json

import pytest
import responses
from responses import matchers

from raspe.exceptions import APIError, ScraperError, ValidationError
from raspe.schemas.senado_processos import OutputSenadoProcessos
from raspe.scrapers import senado_processos
from raspe.scrapers.senado_processos import ScraperSenadoProcessos
from tests._helpers import load_sample, load_sample_bytes

API_URL = "https://legis.senado.leg.br/dadosabertos/processo"
COLUNAS = OutputSenadoProcessos.colunas()


def _registrar(query: dict[str, str], amostra: str | bytes, status: int = 200) -> None:
    """Registra a resposta de uma consulta, que só casa com a query completa (o matcher é estrito).

    A amostra é o nome de um sample (``str``) ou o próprio corpo da resposta (``bytes``).
    """
    responses.add(
        responses.GET, API_URL,
        body=amostra if isinstance(amostra, bytes) else load_sample_bytes("senado_processos", f"raspar/{amostra}.json"),
        status=status,
        content_type="application/json",
        match=[matchers.query_param_matcher(query)],
    )


def _janela(inicio: str, fim: str, **filtros: str) -> dict[str, str]:
    return {**filtros, "dataInicioApresentacao": inicio, "dataFimApresentacao": fim}


@pytest.fixture
def scraper():
    return ScraperSenadoProcessos()


class TestRasparContract:
    @responses.activate(assert_all_requests_are_fired=True)
    def test_typical_periodo_dividido_em_janelas(self, scraper, mocker):
        """Dois anos sem ``ano`` → duas consultas de um ano, juntas num DataFrame só (29 + 29 processos)."""
        dormir = mocker.patch("time.sleep")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="inteligência artificial"), "janela_01")
        _registrar(_janela("2024-01-01", "2024-12-31", termo="inteligência artificial"), "janela_02")

        df = scraper.raspar(pesquisa="inteligência artificial", data_inicio="2023-01-01", data_fim="2024-12-31")

        assert list(df.columns) == COLUNAS
        assert len(df) == 58
        assert df["id"].is_unique
        assert df["data_apresentacao"].between("2023-01-01", "2024-12-31").all()
        assert (df["termo_busca"] == "inteligência artificial").all()
        dormir.assert_called_once_with(scraper.sleep_time)

    @responses.activate(assert_all_requests_are_fired=True)
    def test_single_page(self, scraper):
        """Com ``ano``, a busca sai numa consulta só, sem datas e sem parâmetro de página."""
        _registrar({"termo": "telemedicina", "ano": "2020"}, "single_page")

        df = scraper.raspar(pesquisa="telemedicina", ano=2020)

        assert list(df.columns) == COLUNAS
        assert len(df) == 6
        primeira = df.iloc[0]
        assert (primeira["id"], primeira["codigo_materia"], primeira["identificacao"]) == (
            7879650, 141263, "PL 696/2020",
        )
        assert primeira["ementa"].startswith("Dispõe sobre o uso da telemedicina")
        assert primeira["data_apresentacao"] == "2020-03-26"
        assert primeira["tramitando"] == "Não"
        assert primeira["norma_gerada"] == "Lei nº 13.989 de 15/04/2020"
        # Campo que a API só manda para parte dos processos: nulo, não erro.
        assert primeira["apelido"] is None

    @responses.activate(assert_all_requests_are_fired=True)
    def test_no_results(self, scraper):
        """Lista vazia → DataFrame vazio com as colunas do schema."""
        _registrar({"termo": "termoinexistentexyz123", "ano": "2020"}, "no_results")

        df = scraper.raspar(pesquisa="termoinexistentexyz123", ano=2020)

        assert df.empty
        assert list(df.columns) == COLUNAS


class TestJanelas:
    @responses.activate(assert_all_requests_are_fired=True)
    def test_sem_data_fim_o_periodo_vai_ate_hoje(self, scraper, mocker):
        """Só com ``data_inicio`` a API cortaria o resultado em um ano, calada; o raspador segue até hoje."""
        mocker.patch("time.sleep")
        mocker.patch.object(senado_processos, "_hoje", return_value="2024-06-30")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="inteligência artificial"), "janela_01")
        _registrar(_janela("2024-01-01", "2024-06-30", termo="inteligência artificial"), "janela_02")

        df = scraper.raspar(pesquisa="inteligência artificial", data_inicio="2023-01-01")

        assert len(df) == 58

    @responses.activate(assert_all_requests_are_fired=True)
    def test_processo_repetido_entre_janelas_sai_uma_vez(self, scraper, mocker):
        """Vale o ``id``: o processo que mudou de situação entre as duas consultas também sai uma vez."""
        mocker.patch("time.sleep")
        repetidos = json.loads(load_sample("senado_processos", "raspar/janela_01.json"))
        for processo in repetidos:
            processo["situacaoAtual"] = "MUDOU ENTRE AS CONSULTAS"
        _registrar(_janela("2023-01-01", "2023-12-31", sigla="PL"), "janela_01")
        _registrar(_janela("2024-01-01", "2024-12-31", sigla="PL"), json.dumps(repetidos).encode())

        df = scraper.raspar(sigla_tipo="PL", data_inicio="2023-01-01", data_fim="2024-12-31")

        assert len(df) == 29
        assert df["id"].is_unique
        assert (df["termo_busca"] == "").all()

    @responses.activate(assert_all_requests_are_fired=True)
    def test_janela_vazia_nao_derruba_as_outras(self, scraper, mocker):
        mocker.patch("time.sleep")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="inteligência artificial"), "no_results")
        _registrar(_janela("2024-01-01", "2024-12-31", termo="inteligência artificial"), "janela_02")

        df = scraper.raspar(pesquisa="inteligência artificial", data_inicio="2023-01-01", data_fim="2024-12-31")

        assert len(df) == 29
        assert df["id"].dtype == "int64"

    @responses.activate(assert_all_requests_are_fired=True)
    def test_todas_as_janelas_vazias_devolvem_as_colunas(self, scraper, mocker):
        mocker.patch("time.sleep")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="xyz"), "no_results")
        _registrar(_janela("2024-01-01", "2024-12-31", termo="xyz"), "no_results")

        df = scraper.raspar(pesquisa="xyz", data_inicio="2023-01-01", data_fim="2024-12-31")

        assert df.empty
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_janela_que_falha_interrompe_a_busca(self, scraper, mocker):
        """Seguir sem a janela devolveria um período com um buraco: o erro sobe."""
        mocker.patch("time.sleep")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="inteligência artificial"), "janela_01")
        _registrar(
            _janela("2024-01-01", "2024-12-31", termo="inteligência artificial"),
            json.dumps({"detail": "Invalid request content.", "status": 400}).encode(), status=400,
        )

        with pytest.raises(APIError, match=r"HTTP 400\): Invalid request content\."):
            scraper.raspar(pesquisa="inteligência artificial", data_inicio="2023-01-01", data_fim="2024-12-31")

    @responses.activate(assert_all_requests_are_fired=True)
    def test_com_ano_o_periodo_longo_sai_numa_consulta(self, scraper):
        """Com ``ano``, a API não limita o período (visto ao vivo em 2026-11-16)."""
        _registrar(_janela("2019-06-01", "2023-12-31", termo="telemedicina", ano="2020"), "single_page")

        df = scraper.raspar(pesquisa="telemedicina", ano=2020, data_inicio="2019-06-01", data_fim="2023-12-31")

        assert len(df) == 6

    @responses.activate(assert_all_requests_are_fired=True)
    def test_paginas_baixa_a_resposta_inteira_de_cada_consulta(self, scraper, mocker):
        """A API não pagina: ``paginas=range(1, 2)`` não corta nada, com uma consulta ou com várias."""
        mocker.patch("time.sleep")
        _registrar({"termo": "telemedicina", "ano": "2020"}, "single_page")
        _registrar(_janela("2023-01-01", "2023-12-31", termo="inteligência artificial"), "janela_01")
        _registrar(_janela("2024-01-01", "2024-12-31", termo="inteligência artificial"), "janela_02")

        assert len(scraper.raspar(pesquisa="telemedicina", ano=2020, paginas=range(1, 2))) == 6
        df = scraper.raspar(
            pesquisa="inteligência artificial", data_inicio="2023-01-01", data_fim="2024-12-31", paginas=range(1, 2)
        )
        assert len(df) == 58

    def test_data_inicio_no_futuro_sem_data_fim_levanta_antes_da_busca(self, scraper, mocker):
        mocker.patch.object(senado_processos, "_hoje", return_value="2024-06-30")
        with pytest.raises(ValidationError, match=r"'data_inicio' \(2030-01-01\) não pode ser posterior a hoje"):
            scraper.raspar(pesquisa="x", data_inicio="2030-01-01")


class TestFiltros:
    @responses.activate(assert_all_requests_are_fired=True)
    def test_sigla_tipo_e_datas_no_formato_brasileiro(self, scraper):
        _registrar(_janela("2020-03-01", "2020-03-31", sigla="PL"), "single_page")

        df = scraper.raspar(sigla_tipo="PL", data_inicio="01/03/2020", data_fim="31/03/2020")

        assert len(df) == 6

    @pytest.mark.parametrize(
        "parametros",
        [{}, {"pesquisa": "telemedicina"}, {"pesquisa": "telemedicina", "data_fim": "2020-12-31"}],
        ids=str,
    )
    def test_sem_ano_e_sem_data_inicio_levanta_antes_da_busca(self, scraper, parametros):
        """Nesses casos a API devolveria só parte dos processos, sem avisar (visto ao vivo em 2026-11-16)."""
        with pytest.raises(ValidationError, match="precisa de 'ano' ou de 'data_inicio'"):
            scraper.raspar(**parametros)

    def test_parametro_desconhecido_levanta_antes_da_busca(self, scraper):
        with pytest.raises(ValidationError, match="'tipo_materia': parâmetro desconhecido"):
            scraper.raspar(pesquisa="telemedicina", ano=2020, tipo_materia="PL")


_QUERY_TELEMEDICINA = {"termo": "telemedicina", "ano": "2020"}


class TestErros:
    @responses.activate
    def test_consulta_recusada_pela_api_leva_a_explicacao_dela(self, scraper):
        corpo = {"detail": "Invalid request content.", "instance": "/dadosabertos/processo", "status": 400}
        _registrar(_QUERY_TELEMEDICINA, json.dumps(corpo).encode(), status=400)

        padrao = r"SENADO_PROCESSOS: a API recusou a consulta \(HTTP 400\): Invalid request content\."
        with pytest.raises(APIError, match=padrao) as erro:
            scraper.raspar(pesquisa="telemedicina", ano=2020)
        assert erro.value.status_code == 400

    @responses.activate
    @pytest.mark.parametrize("corpo", [b"<html>manutencao</html>", b'{"processos": []}'], ids=["nao_json", "objeto"])
    def test_resposta_que_nao_e_lista_levanta_erro(self, scraper, corpo):
        """Resposta em outro formato não vira busca vazia: vira erro."""
        _registrar(_QUERY_TELEMEDICINA, corpo)

        with pytest.raises(APIError, match="não é a lista de processos esperada"):
            scraper.raspar(pesquisa="telemedicina", ano=2020)

    @responses.activate
    def test_processo_sem_campo_esperado_levanta_erro(self, scraper):
        """Mudança de formato da API (campo que sumiu) não vira coluna vazia: vira erro com a causa."""
        processos = json.loads(load_sample("senado_processos", "raspar/single_page.json"))
        del processos[0]["identificacao"]
        _registrar(_QUERY_TELEMEDICINA, json.dumps(processos).encode())

        with pytest.raises(ScraperError, match=r"KeyError: 'identificacao'"):
            scraper.raspar(pesquisa="telemedicina", ano=2020)
