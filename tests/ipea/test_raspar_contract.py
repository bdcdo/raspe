"""Contrato offline para ``IpeaScraper.raspar``.

Os samples em ``tests/ipea/samples/raspar/`` foram construídos manualmente
replicando a estrutura HTML observada em respostas reais do portal IPEA
(``div.lista-publicacoes`` → ``div.row`` → ``div.publi-conteudo``).
Para regenerar a partir do site real, ver
``tests/fixtures/capture/ipea.py``.
"""

import pytest
import responses
from responses import matchers, registries

from raspe.exceptions import ScraperError
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
        """15 resultados → 2 páginas: 1 request inicial + 2 de página."""
        mocker.patch("time.sleep")

        # 1 request inicial + 2 requests de página = 3 GETs no mesmo endpoint
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="economia")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 3 publicações, page_02 tem 2 → total 5
        assert len(df) == 5
        # Links têm prefixo ipea.gov.br
        assert df["link"].iloc[0].startswith("https://www.ipea.gov.br")
        assert "termo_busca" in df.columns
        assert (df["termo_busca"] == "economia").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 resultados → 1 página."""
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

        df = scraper.raspar(pesquisa="pobreza")
        assert len(df) == 3
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Busca real sem resultados: "Resultado de 0 a 0 de 0" → DataFrame vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("ipea", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termo_inexistente_xyzabc")
        assert df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_pagina_que_nao_e_de_resultados_levanta_erro(self, scraper, mocker):
        """Sem a contagem e sem o aviso de busca vazia (manutenção, anti-robô), não vira 0 resultados."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("presidencia", "raspar/manutencao.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        with pytest.raises(ScraperError, match="indispon"):
            scraper.raspar(pesquisa="educação")

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
                "palavra_chave": "economia",
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

        scraper.raspar(pesquisa="economia")


class TestDownloadPathDescontinuado:
    def test_download_path_emite_deprecation_warning(self):
        with pytest.warns(DeprecationWarning, match="download_path") as avisos:
            IpeaScraper(download_path="/tmp/qualquer")
        assert avisos[0].filename == __file__

    def test_aviso_pela_fabrica_aponta_para_o_codigo_do_usuario(self):
        """Atribuído a ``raspe/__init__.py``, o filtro padrão do Python esconderia o aviso."""
        import raspe

        with pytest.warns(DeprecationWarning, match="download_path") as avisos:
            raspe.ipea(download_path="/tmp/qualquer")
        assert avisos[0].filename == __file__

    def test_sem_download_path_nao_avisa(self):
        """O ``filterwarnings = error`` da suíte transformaria qualquer aviso em falha."""
        IpeaScraper()
