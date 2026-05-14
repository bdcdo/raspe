"""Contrato offline para ``ScraperFolha.raspar``.

Os samples em ``tests/folha/samples/raspar/`` foram construídos manualmente
replicando a estrutura HTML observada na busca pública da Folha
(``div.c-search__result`` para contagem, ``ol.u-list-unstyled.c-search > li``
para cada notícia, com ``a[href]``, ``h2``, ``p``, ``time``).
"""

import pytest
import responses

from raspe.exceptions import ValidationError
from raspe.scrapers.folha import ScraperFolha
from tests._helpers import load_sample_bytes

API_URL = "https://search.folha.uol.com.br/search"
COLUNAS_OBRIGATORIAS = {"link", "titulo", "resumo", "data"}


@pytest.fixture
def scraper():
    return ScraperFolha()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """40 resultados → 2 páginas (25 por página)."""
        mocker.patch("time.sleep")

        # Initial + page 1 + page 2 = 3 requests
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="educação")

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 tem 3 notícias, page_02 tem 2 → total 5
        assert len(df) == 5
        assert (df["termo_busca"] == "educação").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """3 resultados → 1 página."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="saúde")
        assert len(df) == 3
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Sem ``c-search__result`` no HTML → ``_find_n_pags`` retorna 0."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termo_inexistente_xyzabc")
        assert df.empty


class TestValidacao:
    def test_site_invalido_levanta_validation_error(self, scraper):
        with pytest.raises(ValidationError, match="site"):
            scraper.raspar(pesquisa="x", site="invalido")

    @pytest.mark.parametrize("site", ["todos", "online", "jornal"])
    def test_sites_validos_aceitos(self, site, mocker):
        """'todos', 'online' e 'jornal' são aceitos sem erro de validação."""
        mocker.patch("time.sleep")
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET, API_URL,
                body=load_sample_bytes("folha", "raspar/no_results.html"),
                status=200,
                content_type="text/html; charset=utf-8",
            )
            # Não levanta — site válido. Instancia fresh para evitar
            # colisão de timestamp em _create_download_dir.
            df = ScraperFolha().raspar(pesquisa="x", site=site)
            assert df.empty


class TestFormatacaoData:
    def test_formatar_data_br(self, scraper):
        assert scraper._formatar_data_br("2024-01-15") == "15/01/2024"

    def test_formatar_data_br_vazia(self, scraper):
        assert scraper._formatar_data_br("") == ""

    @responses.activate
    def test_query_com_datas_envia_periodo_personalizado(self, scraper, mocker):
        """Quando data_inicio e data_fim são fornecidas, query usa periodo=personalizado."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("folha", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        scraper.raspar(
            pesquisa="x",
            data_inicio="2024-01-01",
            data_fim="2024-12-31",
        )

        # Inspeciona a request enviada
        call = responses.calls[0]
        assert "periodo=personalizado" in call.request.url
        assert "sd=01%2F01%2F2024" in call.request.url
        assert "ed=31%2F12%2F2024" in call.request.url
