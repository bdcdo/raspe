"""Contrato offline para ``ScraperPresidencia.raspar``.

Os samples em ``tests/presidencia/samples/raspar/`` são respostas reais do
POST AJAX da pesquisa de legislação da Presidência da República
(``resultado_pesquisa_legislacao.php``), capturadas em 21/10/2026 com
``python -m tests.fixtures.capture.presidencia``. O único ajuste é o do
pre-commit, que tira o espaço no fim das linhas.

- ``page_01.html`` e ``page_02.html``: busca "telemedicina",
  ``posicao=0`` e ``posicao=10``. O site diz "19 resultados encontrados";
  a página 1 tem 10 atos e a página 2, 9.
- ``single_page.html``: busca "fenilcetonúria", "2 resultados encontrados".
- ``no_results.html``: busca "termoextremamenteimprovavelxyz"; o ``h4``
  diz "Nenhum resultado encontrado", sem número.

O scraper usa ``session.verify=False`` (cadeia SSL incompleta no servidor
real) — testamos apenas essa configuração isoladamente; o ``responses``
mock não verifica TLS.
"""

import pytest
import responses
from responses import matchers, registries

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
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """19 resultados → 2 páginas (10 por página), e todos os 19 atos saem."""
        mocker.patch("time.sleep")
        # Inicial (posicao=0), página 1 (posicao=0) e página 2 (posicao=10).
        for posicao, sample in [("0", "page_01.html"), ("0", "page_01.html"), ("10", "page_02.html")]:
            responses.add(
                responses.POST, API_URL,
                body=load_sample_bytes("presidencia", f"raspar/{sample}"),
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.urlencoded_params_matcher(
                    {"termo": "telemedicina", "posicao": posicao}, strict_match=False,
                )],
            )

        df = scraper.raspar(pesquisa="telemedicina")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 10 atos e page_02 tem 9: os 19 que o site anuncia.
        assert len(df) == 19
        assert (df["termo_busca"] == "telemedicina").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """2 resultados → 1 página."""
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

        df = scraper.raspar(pesquisa="fenilcetonúria")
        assert len(df) == 2
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate(registry=registries.OrderedRegistry)
    @pytest.mark.parametrize(
        ("contagem", "n_pags"),
        [("1.006", 101), ("1.234.567", 123_457)],
    )
    def test_contagem_com_separador_de_milhar(self, scraper, mocker, contagem, n_pags):
        """``"1.006 resultados encontrados"`` vira 1006 resultados, não 1 nem 6.

        O ponto separa milhar na contagem do site. O teste pede as páginas
        ``n_pags - 1`` até ``n_pags + 1``: só as duas primeiras existem, e a
        terceira tem de ser cortada por ``_set_paginas``. Isso fixa
        ``n_pags`` exato pela API pública, sem baixar as 101 páginas. Se o
        ponto fosse lido como decimal ou cortasse o número, ``n_pags`` cairia
        para 1 e nenhuma página seria pedida.
        """
        mocker.patch("time.sleep")
        trecho = '<h4 class="pb-2 fw-bold">19 resultados encontrados</h4>'
        original = load_sample_bytes("presidencia", "raspar/page_01.html").decode("utf-8")
        assert trecho in original, "o sample page_01.html mudou; ajuste o trecho trocado"
        inicial = original.replace(trecho, f'<h4 class="pb-2 fw-bold">{contagem} resultados encontrados</h4>')

        # A posição de cada página segue posicao = pagina * 10 - 10.
        pedidos = [
            ("0", inicial.encode("utf-8")),
            (str((n_pags - 2) * 10), load_sample_bytes("presidencia", "raspar/page_01.html")),
            (str((n_pags - 1) * 10), load_sample_bytes("presidencia", "raspar/page_02.html")),
        ]
        for posicao, body in pedidos:
            responses.add(
                responses.POST, API_URL,
                body=body,
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.urlencoded_params_matcher(
                    {"termo": "telemedicina", "posicao": posicao}, strict_match=False,
                )],
            )

        df = scraper.raspar(pesquisa="telemedicina", paginas=range(n_pags - 1, n_pags + 2))

        # Inicial + as duas páginas existentes; a página n_pags + 1 não sai.
        assert len(responses.calls) == 3
        # page_01 tem 10 atos e page_02 tem 9
        assert len(df) == 19
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """``Nenhum resultado encontrado``, sem número → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.POST, API_URL,
            body=load_sample_bytes("presidencia", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        # Só a requisição inicial: com 0 páginas, nenhuma página é pedida.
        assert len(responses.calls) == 1

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
                "termo": "fenilcetonúria",
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

        scraper.raspar(pesquisa="fenilcetonúria")


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
