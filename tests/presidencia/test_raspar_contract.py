"""Contrato offline para ``ScraperPresidencia.raspar``.

Os samples em ``tests/presidencia/samples/raspar/`` foram construídos
manualmente replicando a estrutura HTML observada nas respostas da
pesquisa de legislação da Presidência da República (POST AJAX para
``resultado_pesquisa_legislacao.php``). O sample no_results.html simula a
ausência de ``div.card-body.p-0`` que o parser usa para iterar.

O scraper usa ``session.verify=False`` (cadeia SSL incompleta no servidor
real) — testamos apenas essa configuração isoladamente; o ``responses``
mock não verifica TLS.
"""

import pytest
import responses
from responses import matchers

from raspe.scrapers.presidencia import ScraperPresidencia
from tests._helpers import load_sample_bytes

API_URL = (
    "https://legislacao.presidencia.gov.br/pesquisa/ajax/"
    "resultado_pesquisa_legislacao.php"
)
COLUNAS_OBRIGATORIAS = {"nome", "link", "ficha", "revogacao", "descricao"}


@pytest.fixture
def scraper():
    return ScraperPresidencia()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """15 resultados → 2 páginas (10 por página)."""
        mocker.patch("time.sleep")
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="meio ambiente")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 3 itens, page_02 tem 2 → total 5
        assert len(df) == 5
        assert (df["termo_busca"] == "meio ambiente").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 resultados → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="educação")
        assert len(df) == 3
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """``0 resultados encontrados`` → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termo_inexistente_xyzabc")
        assert df.empty

    @responses.activate
    def test_payload_post_formato_form(self, scraper, mocker):
        """A request inicial usa POST form-urlencoded com termo, ordenação e posição."""
        mocker.patch("time.sleep")
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.urlencoded_params_matcher({
                "termo": "educação",
                "ordenacao": "maior_data",
                "posicao": "0",
            })],
        )
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper.raspar(pesquisa="educação")


class TestConfiguracao:
    def test_ssl_verify_desabilitado(self, scraper):
        """O scraper desabilita SSL devido a cadeia incompleta no servidor."""
        assert scraper.session.verify is False

    def test_paginacao_com_multiplier_e_increment(self, scraper):
        """multiplier=10 e increment=-10: page 1 → 0, page 2 → 10, page 3 → 20."""
        assert scraper.query_page_multiplier == 10
        assert scraper.query_page_increment == -10

    def test_metodo_post_html(self, scraper):
        assert scraper.api_method == 'POST'
        assert scraper.type == 'HTML'

    def test_query_page_name_eh_posicao(self, scraper):
        assert scraper.query_page_name == 'posicao'

    def test_headers_origem_e_referer(self, scraper):
        """Headers de Origin/Referer são obrigatórios para a API funcionar."""
        assert "legislacao.presidencia.gov.br" in scraper.session.headers["Origin"]
        assert "legislacao.presidencia.gov.br" in scraper.session.headers["Referer"]
        assert scraper.session.headers["X-Requested-With"] == "XMLHttpRequest"
