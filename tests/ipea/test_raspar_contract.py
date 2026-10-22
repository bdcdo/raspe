"""Contrato offline para ``IpeaScraper.raspar``.

Os samples em ``tests/ipea/samples/raspar/`` são respostas reais da busca
de publicações do portal IPEA, capturadas em 21/10/2026 com
``python -m tests.fixtures.capture.ipea``. Há dois ajustes: o script
esvazia os ``<select>`` do formulário de busca, que o scraper não lê e que
levavam cada página a mais de 2 MB, e o pre-commit tira o espaço no fim
das linhas.

- ``page_01.html`` e ``page_02.html``: busca "renda básica", ``pagina=1``
  e ``pagina=2``. O ``h4`` diz "Resultado de 1 a 10 de <strong>13</strong>";
  a página 1 tem 10 publicações e a página 2, 3.
- ``single_page.html``: busca "telemedicina", 1 publicação.
- ``no_results.html``: busca "termoextremamenteimprovavelxyz", "Resultado
  de 0 a 0 de <strong>0</strong>".

O ``div.autores`` vem vazio no HTML do site, por isso a coluna ``autores``
sai vazia nos samples.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.scrapers.ipea import IpeaScraper
from tests._helpers import load_sample_bytes

API_URL = "https://www.ipea.gov.br/portal/coluna-5/central-de-conteudo/busca-publicacoes"
COLUNAS_OBRIGATORIAS = {"titulo", "link", "autores", "data", "assuntos"}


@pytest.fixture
def scraper():
    return IpeaScraper()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        """13 resultados → 2 páginas: 1 request inicial + 2 de página."""
        mocker.patch("time.sleep")

        # Inicial (pagina=1), página 1 (pagina=1) e página 2 (pagina=2).
        for pagina, sample in [("1", "page_01.html"), ("1", "page_01.html"), ("2", "page_02.html")]:
            responses.add(
                responses.GET, API_URL,
                body=load_sample_bytes("ipea", f"raspar/{sample}"),
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher(
                    {"palavra_chave": "renda básica", "pagina": pagina}, strict_match=False,
                )],
            )

        df = scraper.raspar(pesquisa="renda básica")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 10 publicações e page_02 tem 3: as 13 que o site anuncia.
        assert len(df) == 13
        # Links têm prefixo ipea.gov.br
        assert df["link"].iloc[0].startswith("https://www.ipea.gov.br")
        assert "termo_busca" in df.columns
        assert (df["termo_busca"] == "renda básica").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """1 resultado → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="telemedicina")
        assert len(df) == 1
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """``Resultado de 0 a 0 de <strong>0</strong>`` → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termoextremamenteimprovavelxyz")
        assert df.empty
        # Só a requisição inicial: com 0 páginas, nenhuma página é pedida.
        assert len(responses.calls) == 1

    @responses.activate
    def test_sem_div_col_clearfix_retorna_vazio(self, scraper, mocker):
        """Sem ``div.col.clearfix``, a contagem vira 0 e nenhuma página é baixada.

        Parte do sample single_page, que tem 1 publicação, e tira só a
        classe do container da contagem. ``_find_n_pags`` não tem outro
        lugar onde procurar o número; o contrato fixa que a falta dele dá
        DataFrame vazio, sem exceção, em vez de um parse parcial.
        """
        mocker.patch("time.sleep")
        trecho = '<div class="col clearfix">'
        original = load_sample_bytes("ipea", "raspar/single_page.html").decode("utf-8")
        assert trecho in original, "o sample single_page.html mudou; ajuste o trecho trocado"
        sem_container = original.replace(trecho, '<div class="col">')
        # As publicações continuam na página; só a contagem ficou sem container.
        assert 'class="publi-conteudo"' in sem_container

        responses.add(
            responses.GET, API_URL,
            body=sem_container.encode("utf-8"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="telemedicina")

        assert df.empty
        # Só a requisição inicial: com 0 páginas, nenhuma página é pedida.
        assert len(responses.calls) == 1

    @responses.activate
    def test_query_params_obrigatorios(self, scraper, mocker):
        """A query base contém os parâmetros esperados pela API IPEA."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({
                "palavra_chave": "telemedicina",
                "tipo": "",
                "assunto": "",
                "autor": "",
                "timeperiods": "all",
                "data-inicial": "",
                "data-final": "",
                "pagina": "1",
            })],
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper.raspar(pesquisa="telemedicina")
