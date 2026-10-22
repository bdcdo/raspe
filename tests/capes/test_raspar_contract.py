"""Contrato offline para ``ScraperCapes.raspar``.

Os samples em ``tests/capes/samples/raspar/`` foram capturados do buscador
público do Portal de Periódicos da CAPES
(``https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html``)
usando ``requests`` com User-Agent realista. O HTML é Joomla! server-rendered
com cards ``div.col-md-12.br-item[id^="conteudo-"]``.

- ``page_01.html``: busca "natjus" (20 resultados → 1 página).
- ``page_02.html``: busca "saude", página 2 (30 resultados).
- ``single_page.html``: hoje é cópia bit-a-bit de ``page_01`` (mesma busca
  "natjus" que já cabe em 1 página). Idealmente regenerar com termo
  diferente para detectar drift independente — rodar
  ``tests/fixtures/capture/capes.py`` quando o site não estiver
  rate-limitando.
- ``no_results.html``: termo absurdo, sem ``nav.br-pagination``.
"""

import os
from datetime import datetime

import pytest
import responses
from responses import matchers

from raspe.scrapers.capes import ScraperCapes
from tests._helpers import load_sample_bytes

API_URL = "https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html"
COLUNAS_OBRIGATORIAS = {
    "id", "tipo", "titulo", "link", "autores", "ano", "revista",
    "instituicao", "topicos", "resumo", "doi", "link_editor",
    "acesso_aberto", "producao_nacional", "revisado_por_pares",
}


@pytest.fixture
def scraper():
    return ScraperCapes()


class TestRasparContract:
    @responses.activate
    def test_typical_paginacao(self, scraper, mocker):
        """Page_02 (data-total ~29M) como resposta inicial → range(1,3) sem cap.

        Resultado: page_01 (20 itens) + page_02 (12 itens trimados) = 32 linhas.
        Page_02 trimado para 12 cards (de 30) para ficar abaixo do limite
        de 500KB do pre-commit `check-added-large-files`.
        """
        mocker.patch("time.sleep")

        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/page_01.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/page_02.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="saude", paginas=range(1, 3))

        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        # page_01 contribui com 20 cards; page_02 foi trimada para 12
        # (ver docstring), mas qualquer regeneração pode mudar o trim.
        # Validamos só o limite inferior: page_01 cheia + ≥10 da page_02.
        assert len(df) >= 30
        assert df["link"].iloc[0].startswith("https://www.periodicos.capes.gov.br")
        assert "termo_busca" in df.columns
        assert (df["termo_busca"] == "saude").all()

    @responses.activate
    def test_single_page(self, scraper, mocker):
        """1 página → 20 resultados, todos os campos extraídos."""
        mocker.patch("time.sleep")

        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="natjus")

        assert len(df) == 20
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        assert df["id"].str.match(r"^W\d+$").all()
        assert df["titulo"].str.len().min() > 0
        # Tolerância de 2 cards sem ano de 4 dígitos (ex.: "no prelo",
        # "in press" ou registros do OpenAlex sem ano publicado).
        assert (df["ano"].str.match(r"^\d{4}$")).sum() >= 18

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

    @responses.activate
    def test_busca_por_lista_sem_resultados_no_mesmo_segundo(self, scraper, mocker):
        """Dois termos sem resultado no mesmo segundo ganham diretórios distintos.

        O relógio fica parado para que os dois termos gerem o mesmo timestamp
        em ``_create_download_dir``, de forma determinística. A busca por lista
        precisa terminar sem ``FileExistsError`` e, com ``debug=True`` (o
        default, que mantém os arquivos), deixar um diretório por termo
        (issue #43).
        """
        mocker.patch("time.sleep")
        relogio = mocker.patch("raspe.abstract_scraper.datetime")
        relogio.now.return_value = datetime(2026, 1, 1, 12, 0, 0)

        corpo = load_sample_bytes("capes", "raspar/no_results.html")
        # Sem ``nav.br-pagination``, ``_find_n_pags`` devolve 0 e cada termo
        # faz só a requisição inicial. Se uma recaptura trouxer paginação, o
        # teste deixa de exercitar o caso de borda e precisa falhar aqui.
        assert b"br-pagination" not in corpo
        termos = ["termo_inexistente_a", "termo_inexistente_b"]
        for termo in termos:
            responses.add(
                responses.GET, API_URL,
                body=corpo,
                status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher({
                    "q": f"all:contains({termo})",
                    "mode": "advanced",
                    "source": "all",
                })],
            )

        df = scraper.raspar(pesquisa=termos)

        assert df.empty
        assert len(responses.calls) == len(termos)
        diretorios = os.listdir(os.path.join(scraper.download_path, scraper.nome_buscador))
        assert len(diretorios) == len(termos)

    @responses.activate
    def test_query_params_corretos(self, scraper, mocker):
        """A query base deve usar a sintaxe 'all:contains({termo})'."""
        mocker.patch("time.sleep")

        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({
                "q": "all:contains(saude)",
                "mode": "advanced",
                "source": "all",
                "page": "1",
            })],
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("capes", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="saude", paginas=range(1, 2))
        assert not df.empty
