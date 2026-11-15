"""Contrato offline para ``ScraperCapes.raspar``.

Os samples em ``tests/capes/samples/raspar/`` foram capturados do buscador
público do Portal de Periódicos da CAPES
(``https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html``)
usando ``requests`` com User-Agent realista. O HTML é Joomla! server-rendered
com cards ``div.col-md-12.br-item[id^="conteudo-"]``.

Termos de busca e contagens de cada sample: ``tests/fixtures/capture/capes.py``.
"""

import pytest
import responses
from responses import matchers

from raspe.exceptions import ScraperError
from raspe.schemas.capes import OutputCapes
from raspe.scrapers.capes import ScraperCapes
from tests._helpers import load_sample_bytes

API_URL = "https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputCapes, na ordem de colunas().
COLUNAS = OutputCapes.colunas()


def _registrar(termo: str, *amostras: str) -> None:
    """Registra as respostas de uma busca: a contagem, sem ``page``, e uma por página.

    A contagem recebe a amostra da página 1, como no portal. Cada resposta só
    casa com a query completa daquela requisição.
    """
    query = {"q": f"all:contains({termo})", "mode": "advanced", "source": "all"}
    for pagina, amostra in [(None, amostras[0]), *enumerate(amostras, start=1)]:
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", f"raspar/{amostra}.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher(query if pagina is None else {**query, "page": str(pagina)})],
        )


@pytest.fixture
def scraper():
    return ScraperCapes()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """Página 1 dá a contagem (41 em cards de 30 → 2 páginas); raspar() baixa as duas."""
        mocker.patch("time.sleep")

        _registrar("natjus OR nat-jus", "page_01", "page_02")

        df = scraper.raspar(pesquisa="natjus OR nat-jus")

        assert list(df.columns) == COLUNAS
        assert len(df) == 41
        assert df["id"].is_unique
        assert df["link"].str.startswith("https://www.periodicos.capes.gov.br").all()
        assert (df["termo_busca"] == "natjus OR nat-jus").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """1 página → 17 resultados, com id, título e ano extraídos."""
        mocker.patch("time.sleep")

        _registrar("natjus saude judicializacao", "single_page")

        df = scraper.raspar(pesquisa="natjus saude judicializacao")

        assert len(df) == 17
        assert list(df.columns) == COLUNAS
        assert df["id"].str.match(r"^W\d+$").all()
        assert df["titulo"].str.len().min() > 0
        # Tolerância de 2 cards sem ano de 4 dígitos (ex.: "no prelo",
        # "in press" ou registros do OpenAlex sem ano publicado).
        assert (df["ano"].str.match(r"^\d{4}$")).sum() >= 15

    @responses.activate
    def test_no_results(self, scraper, mocker):
        """Sem nav.br-pagination → 0 páginas → DataFrame vazio."""
        mocker.patch("time.sleep")

        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/no_results.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="termo_inexistente_xyz123")
        assert df.empty
        assert list(df.columns) == COLUNAS

    @responses.activate
    def test_pagina_sem_paginacao_nem_aviso_levanta_erro(self, scraper, mocker):
        """Sem paginação e sem o aviso de busca vazia (manutenção, anti-robô) → erro, não 0."""
        mocker.patch("time.sleep")

        responses.add(
            responses.GET, API_URL,
            body="<html><head><title>Portal em manutenção</title></head>"
                 "<body><h1>Voltamos em breve</h1></body></html>",
            status=200,
            content_type="text/html; charset=utf-8",
        )

        with pytest.raises(ScraperError, match="Portal em manutenção"):
            scraper.raspar(pesquisa="saude")

    @responses.activate
    def test_paginas_limita_a_coleta(self, scraper, mocker):
        """paginas=range(1, 2) baixa só a página 1 de 2; um pedido da página 2 não casaria com nenhum mock."""
        mocker.patch("time.sleep")
        _registrar("natjus OR nat-jus", "page_01")

        df = scraper.raspar(pesquisa="natjus OR nat-jus", paginas=range(1, 2))
        assert len(df) == 30


class TestFindNPags:
    def test_tamanho_da_pagina_vem_dos_cards_da_pagina_1(self, scraper, mocker):
        """O nav declara data-per-page="20", mas o portal serve 30 (436 = 14 x 30 + 16, ao vivo)."""
        cards = "".join(f'<div class="col-md-12 br-item" id="conteudo-{i}"></div>' for i in range(30))
        r0 = mocker.Mock(content=(
            f'<nav class="br-pagination" data-total="436" data-per-page="20"></nav>{cards}'
        ).encode())
        assert scraper._find_n_pags(r0) == 15
