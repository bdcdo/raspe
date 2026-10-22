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

import pytest
import responses
from responses import matchers

from raspe.scrapers.capes import ScraperCapes
from tests._helpers import load_sample, load_sample_bytes

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


def _titulos_por_id(scraper, html: str) -> dict[str, str]:
    """Raspa uma página com ``html`` e devolve ``{id: titulo}``.

    A primeira resposta serve a ``_find_n_pags`` e a segunda ao download da
    página 1, por isso o mesmo corpo entra duas vezes.
    """
    for _ in range(2):
        responses.add(
            responses.GET, API_URL,
            body=html.encode("utf-8"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
    df = scraper.raspar(pesquisa="natjus", paginas=range(1, 2))
    return dict(zip(df["id"], df["titulo"]))


class TestTitulo:
    """O título sai como o navegador exibe o ``a.titulo-busca`` (issue #40).

    O portal destaca o termo buscado com ``<b>`` dentro do título, e o espaço
    em volta do ``<b>`` varia de card para card. Os títulos esperados são o
    ``innerText`` do Chromium para a mesma página, com o espaço em branco
    normalizado. Cada caso confere antes que o trecho ainda existe no sample:
    se uma recaptura mudar o HTML, o teste falha em vez de passar sem
    exercitar o ``<b>``.
    """

    @pytest.mark.parametrize(("id_card", "trecho_html", "titulo_esperado"), [
        pytest.param(
            "W4388508904", "(<b>NATJUS</b> - BA)",
            "Análise das notas técnicas do Núcleo de Apoio ao Judiciário da Bahia (NATJUS - BA) "
            "para os medicamentos Atezolizumabe; Nivolumabe e Pembrolizumabe.",
            id="espaco-so-depois-do-b-parenteses",
        ),
        pytest.param(
            "W4391884248", "E-<b>NATJUS</b> NA",
            "DIREITOS DA PERSONALIDADE, BANCOS DE DADOS E INTELIGÊNCIA ARTIFICIAL: "
            "O IMPACTO DO SISTEMA E-NATJUS NA JUDICIALIZAÇÃO DO DIREITO À SAÚDE",
            id="espaco-so-depois-do-b-hifen",
        ),
        pytest.param(
            "W7118417258", "Rede <b>NatJus</b>:",
            "Blog Rede NatJus: informações estratégicas para apoiar o Judiciário na tomada de decisão em saúde",
            id="espaco-so-antes-do-b",
        ),
        pytest.param(
            "W4410893981", "by <b>NATJUS</b> on",
            "Impact evaluation of technical notes issued by NATJUS on healthcare judicialization",
            id="espaco-dos-dois-lados-do-b",
        ),
        pytest.param(
            "W4212894439", "TÉCNICO (<b>NATJUS</b>) NAS",
            "A PARTICIPAÇÃO DOS NÚCLEOS DE APOIO TÉCNICO (NATJUS) NAS DECISÕES JUDICIAIS",
            id="sem-espaco-em-volta-do-b",
        ),
    ])
    @responses.activate
    def test_titulo_com_termo_destacado(self, scraper, mocker, id_card, trecho_html, titulo_esperado):
        mocker.patch("time.sleep")
        html = load_sample("capes", "raspar/page_01.html")
        assert trecho_html in html, f"Trecho {trecho_html!r} sumiu do sample; recapturar e rever o caso."

        assert _titulos_por_id(scraper, html)[id_card] == titulo_esperado

    @responses.activate
    def test_titulo_com_br_sem_espaco_em_volta(self, scraper, mocker):
        """``<br>`` vira quebra de linha no navegador, e não cola as palavras.

        Nenhuma captura tem ``<br>`` no título; o caso deriva do card real
        ``W4391884248`` trocando o espaço depois do ``<b>`` por ``<br>``.
        """
        mocker.patch("time.sleep")
        html = load_sample("capes", "raspar/page_01.html")
        trecho = "E-<b>NATJUS</b> NA"
        assert html.count(trecho) == 1, f"Trecho {trecho!r} sumiu do sample; recapturar e rever o caso."
        html = html.replace(trecho, "E-<b>NATJUS</b><br>NA")

        assert _titulos_por_id(scraper, html)["W4391884248"] == (
            "DIREITOS DA PERSONALIDADE, BANCOS DE DADOS E INTELIGÊNCIA ARTIFICIAL: "
            "O IMPACTO DO SISTEMA E-NATJUS NA JUDICIALIZAÇÃO DO DIREITO À SAÚDE"
        )
