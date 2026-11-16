"""Contrato offline para ``ScraperCamaraProposicoes.raspar``.

Os samples em ``tests/camara_proposicoes/samples/raspar/`` são respostas
reais da API de Dados Abertos da Câmara
(``https://dadosabertos.camara.leg.br/api/v2/proposicoes``), gravadas por
``python -m tests.fixtures.capture.camara_proposicoes``. O sample guarda só
o corpo; o header ``X-Total-Count``, de onde sai a contagem, é repetido aqui
com o valor que a API devolveu na captura.
"""

import json

import pytest
import responses
from responses import matchers

from raspe.exceptions import APIError, ScraperError, ValidationError
from raspe.schemas.camara_proposicoes import OutputCamaraProposicoes
from raspe.scrapers.camara_proposicoes import ScraperCamaraProposicoes
from tests._helpers import load_sample, load_sample_bytes

API_URL = "https://dadosabertos.camara.leg.br/api/v2/proposicoes"
COLUNAS = OutputCamaraProposicoes.colunas()
# O que toda requisição leva, seja qual for a busca.
QUERY_FIXA = {"itens": "100", "ordenarPor": "id", "ordem": "ASC"}


def _registrar(filtros: dict[str, str], total: int, *amostras: str | bytes) -> None:
    """Registra as respostas de uma busca, uma por página.

    Cada resposta só casa com a query completa daquela requisição (o matcher é
    estrito). Cada amostra é o nome de um sample (``str``) ou o próprio corpo
    da resposta (``bytes``).
    """
    for pagina, amostra in enumerate(amostras, start=1):
        responses.add(
            responses.GET, API_URL,
            body=(
                amostra if isinstance(amostra, bytes)
                else load_sample_bytes("camara_proposicoes", f"raspar/{amostra}.json")
            ),
            status=200,
            content_type="application/json",
            headers={"X-Total-Count": str(total)},
            match=[matchers.query_param_matcher({**QUERY_FIXA, **filtros, "pagina": str(pagina)})],
        )


@pytest.fixture
def scraper():
    return ScraperCamaraProposicoes()


class TestRasparContract:
    @responses.activate(assert_all_requests_are_fired=True)
    def test_typical_paginacao(self, scraper, mocker):
        """178 resultados em páginas de 100 → 2 páginas; sem filtro de tempo, a busca cobre a base inteira."""
        mocker.patch("time.sleep")
        _registrar({"keywords": "doença rara", "dataApresentacaoInicio": "1900-01-01"}, 178, "page_01", "page_02")

        df = scraper.raspar(pesquisa="doença rara")

        assert list(df.columns) == COLUNAS
        assert len(df) == 178
        assert df["id"].is_unique
        assert (df["uri"] == API_URL + "/" + df["id"].astype(str)).all()
        assert (df["termo_busca"] == "doença rara").all()

    @responses.activate(assert_all_requests_are_fired=True)
    def test_single_page(self, scraper, mocker):
        """Com ``ano``, a data inicial de reserva não vai; 9 resultados numa página."""
        mocker.patch("time.sleep")
        _registrar({"keywords": "telemedicina", "ano": "2020"}, 9, "single_page")

        df = scraper.raspar(pesquisa="telemedicina", ano=2020)

        assert list(df.columns) == COLUNAS
        assert len(df) == 9
        assert set(df["ano"]) == {2020}
        primeira = df.iloc[0]
        assert (primeira["id"], primeira["sigla_tipo"], primeira["cod_tipo"], primeira["numero"]) == (
            2239462, "PL", 139, 696,
        )
        assert primeira["ementa"].startswith("Dispõe sobre o uso da telemedicina")
        assert primeira["data_apresentacao"] == "2020-03-18T10:54"

    @responses.activate(assert_all_requests_are_fired=True)
    def test_no_results(self, scraper, mocker):
        """``X-Total-Count: 0`` → DataFrame vazio com as colunas do schema."""
        mocker.patch("time.sleep")
        _registrar({"keywords": "termoinexistentexyz123", "dataApresentacaoInicio": "1900-01-01"}, 0, "no_results")

        df = scraper.raspar(pesquisa="termoinexistentexyz123")

        assert df.empty
        assert list(df.columns) == COLUNAS

    @responses.activate(assert_all_requests_are_fired=True)
    def test_paginas_limita_a_coleta(self, scraper, mocker):
        """paginas=range(1, 2) baixa só a página 1 de 2; um pedido da página 2 não casaria com nenhum mock."""
        mocker.patch("time.sleep")
        _registrar({"keywords": "doença rara", "dataApresentacaoInicio": "1900-01-01"}, 178, "page_01")

        df = scraper.raspar(pesquisa="doença rara", paginas=range(1, 2))

        assert len(df) == 100


class TestFiltros:
    """Cada parâmetro de ``raspar()`` vira o parâmetro certo da API (o matcher é estrito)."""

    @pytest.mark.parametrize(
        ("parametros", "filtros"),
        [
            pytest.param({}, {"dataApresentacaoInicio": "1900-01-01"}, id="sem_filtro_cobre_a_base_inteira"),
            pytest.param({"sigla_tipo": "PL", "ano": 2020}, {"siglaTipo": "PL", "ano": "2020"}, id="sigla_tipo_e_ano"),
            pytest.param(
                {"data_inicio": "01/03/2020", "data_fim": "31/03/2020"},
                {"dataApresentacaoInicio": "2020-03-01", "dataApresentacaoFim": "2020-03-31"},
                id="periodo",
            ),
            pytest.param({"data_inicio": "2020-03-01"}, {"dataApresentacaoInicio": "2020-03-01"}, id="so_data_inicio"),
            # Com a data inicial de reserva, a API recusaria o período por passar de 3 meses.
            pytest.param({"data_fim": "2020-03-31"}, {"dataApresentacaoFim": "2020-03-31"}, id="so_data_fim"),
            pytest.param(
                {"ano": 2020, "data_fim": "2020-03-31"},
                {"ano": "2020", "dataApresentacaoFim": "2020-03-31"},
                id="ano_e_data_fim",
            ),
        ],
    )
    @responses.activate(assert_all_requests_are_fired=True)
    def test_parametro_vira_filtro_da_api(self, scraper, parametros, filtros):
        _registrar(filtros, 9, "single_page")

        df = scraper.raspar(**parametros)

        assert len(df) == 9
        assert (df["termo_busca"] == "").all()

    def test_parametro_desconhecido_levanta_antes_da_busca(self, scraper):
        with pytest.raises(ValidationError, match="'tipo_materia': parâmetro desconhecido"):
            scraper.raspar(pesquisa="telemedicina", tipo_materia="PL")


class TestErros:
    @responses.activate
    def test_periodo_recusado_pela_api_leva_a_explicacao_dela(self, scraper):
        """A API responde 400 a período de mais de 3 meses; a explicação dela chega a quem chamou."""
        detalhe = "A diferença entre as datas não pode ser maior que 3 meses"
        responses.add(
            responses.GET, API_URL, status=400, content_type="application/json",
            json={"title": "Bad Request", "status": 400, "detail": detalhe, "instance": "/api/v2/proposicoes"},
        )

        with pytest.raises(APIError, match=f"CAMARA_PROPOSICOES: a API recusou a consulta: {detalhe}") as erro:
            scraper.raspar(pesquisa="telemedicina", data_inicio="2020-01-01", data_fim="2020-12-31")
        assert erro.value.status_code == 400

    @responses.activate
    def test_400_sem_json_leva_o_corpo_da_resposta(self, scraper):
        responses.add(responses.GET, API_URL, status=400, body="pedido ruim")

        with pytest.raises(APIError, match="a API recusou a consulta: pedido ruim"):
            scraper.raspar(pesquisa="telemedicina")

    @responses.activate
    @pytest.mark.parametrize("headers", [{}, {"X-Total-Count": "muitos"}], ids=["ausente", "nao_numerico"])
    def test_resposta_sem_contagem_levanta_erro(self, scraper, headers):
        """Sem o ``X-Total-Count`` não dá para saber se a busca coube numa página: erro, não uma página só."""
        responses.add(
            responses.GET, API_URL, status=200, content_type="application/json", headers=headers,
            body=load_sample_bytes("camara_proposicoes", "raspar/single_page.json"),
        )

        with pytest.raises(APIError, match="sem a contagem de resultados"):
            scraper.raspar(pesquisa="telemedicina")

    @responses.activate
    def test_item_sem_campo_esperado_levanta_erro(self, scraper):
        """Mudança de formato da API (campo que sumiu) não vira coluna vazia: vira erro com a causa."""
        pagina = json.loads(load_sample("camara_proposicoes", "raspar/single_page.json"))
        del pagina["dados"][0]["siglaTipo"]
        _registrar({"keywords": "telemedicina", "ano": "2020"}, 9, json.dumps(pagina).encode())

        with pytest.raises(ScraperError, match=r"KeyError: 'siglaTipo'"):
            scraper.raspar(pesquisa="telemedicina", ano=2020)
