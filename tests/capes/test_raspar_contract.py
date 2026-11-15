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
from tests._helpers import load_sample, load_sample_bytes

API_URL = "https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html"
# Igualdade, não subconjunto: com o wiring do schema, raspar() devolve
# exatamente as colunas de OutputCapes, na ordem de colunas().
COLUNAS = OutputCapes.colunas()


def _registrar(termo: str, *amostras: str | bytes) -> None:
    """Registra as respostas de uma busca: a contagem, sem ``page``, e uma por página.

    A contagem recebe a amostra da página 1, como no portal. Cada resposta só
    casa com a query completa daquela requisição. Cada amostra é o nome de um
    sample (``str``) ou o próprio corpo da resposta (``bytes``).
    """
    query = {"q": f"all:contains({termo})", "mode": "advanced", "source": "all"}
    for pagina, amostra in [(None, amostras[0]), *enumerate(amostras, start=1)]:
        responses.add(
            responses.GET, API_URL,
            body=amostra if isinstance(amostra, bytes) else load_sample_bytes("capes", f"raspar/{amostra}.html"),
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


def _coluna_por_id(scraper, html: str, coluna: str) -> dict[str, str]:
    """Raspa só a página 1 servindo ``html`` e devolve ``{id: valor da coluna}``."""
    _registrar("natjus", html.encode("utf-8"))
    df = scraper.raspar(pesquisa="natjus", paginas=range(1, 2))
    return dict(zip(df["id"], df[coluna]))


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

        assert _coluna_por_id(scraper, html, "titulo")[id_card] == titulo_esperado

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

        assert _coluna_por_id(scraper, html, "titulo")["W4391884248"] == (
            "DIREITOS DA PERSONALIDADE, BANCOS DE DADOS E INTELIGÊNCIA ARTIFICIAL: "
            "O IMPACTO DO SISTEMA E-NATJUS NA JUDICIALIZAÇÃO DO DIREITO À SAÚDE"
        )


# innerText do Chromium para o resumo do card real W3032714479 (page_01.html).
RESUMO_W3032714479 = (
    "... e a possibilidade do uso da ferramenta e-NatJus como elemento de suporte técnico aos "
    "magistrados nessas ... y la posibilidad de utilizar la herramienta e-NatJus como elemento de "
    "apoyo técnico para los jueces ... Brazil and the possibility of using the e-NatJus tool as "
    "technical support for judges in these ..."
)


class TestResumo:
    """O resumo sai como o navegador exibe o ``blockquote.blockquote-busca`` (issue #40).

    O resumo tem o mesmo destaque com ``<b>`` do título e vem dentro de um
    ``<p>``. Os resumos esperados são o ``innerText`` do Chromium para a mesma
    página, com o espaço em branco normalizado. Cada caso confere antes que o
    trecho ainda existe no sample.
    """

    @pytest.mark.parametrize(("id_card", "trecho_html", "resumo_esperado"), [
        pytest.param(
            "W3032714479", "ferramenta e-<b>NatJus</b> como", RESUMO_W3032714479,
            id="sem-espaco-antes-do-b",
        ),
        pytest.param(
            "W4387465478", "Judiciary (<b>NatJus</b>), which",
            "... the Center for Technical Support of the Judiciary (NatJus), which supports judicial "
            "decisions. The data were obtained from the e-NatJus system, of the Brazilian Ministry of "
            "Justice, using ... accordance with scientific evidence, denoting the importance of NatJus in the "
            "qualification of access to medicinal products ... emitidas pelos Núcleos de Apoio Técnico do "
            "Judiciário (NatJus), que embasaram as decisões judiciais. Os dados foram obtidos do sistema "
            "e-NatJus, do Ministério da Justiça, utilizando técnicas de web ...",
            id="sem-espaco-em-volta-do-b",
        ),
    ])
    @responses.activate
    def test_resumo(self, scraper, mocker, id_card, trecho_html, resumo_esperado):
        mocker.patch("time.sleep")
        html = load_sample("capes", "raspar/page_01.html")
        assert trecho_html in html, f"Trecho {trecho_html!r} sumiu do sample; recapturar e rever o caso."

        assert _coluna_por_id(scraper, html, "resumo")[id_card] == resumo_esperado

    @pytest.mark.parametrize("substituto", [
        pytest.param("suporte\n                    técnico", id="quebra-de-linha-no-texto"),
        pytest.param('suporte</p><p class="mb-0 small">técnico', id="paragrafos-colados"),
    ])
    @responses.activate
    def test_resumo_com_quebra_de_linha(self, scraper, mocker, substituto):
        """Quebra de linha no HTML vira espaço, e ``</p><p>`` colados não colam as palavras.

        Nenhuma captura atual tem quebra de linha nem mais de um ``<p>`` no
        resumo; os casos derivam do card real ``W3032714479`` trocando o espaço
        entre ``suporte`` e ``técnico``.
        """
        mocker.patch("time.sleep")
        html = load_sample("capes", "raspar/page_01.html")
        trecho = "suporte técnico aos"
        assert html.count(trecho) == 1, f"Trecho {trecho!r} sumiu do sample; recapturar e rever o caso."
        html = html.replace(trecho, substituto + " aos")

        assert _coluna_por_id(scraper, html, "resumo")["W3032714479"] == RESUMO_W3032714479


class TestInstituicaoERevista:
    """``instituicao`` e ``revista`` não se confundem com o destaque do termo buscado (issue #40).

    Os metadados vêm em ``<b>`` dentro de um ``<p>`` (ano, instituição, revista),
    e o destaque do termo buscado é outro ``<b>``, aninhado no da instituição ou
    da revista. Cada caso confere antes que o trecho ainda existe no sample.
    """

    @pytest.mark.parametrize(("id_card", "trecho_html", "instituicao", "revista"), [
        pytest.param(
            "W7118417258", "<b>MINISTÉRIO DA <b>SAÚDE</b> </b>",
            "MINISTÉRIO DA SAÚDE", "Epidemiologia e Serviços de Saúde",
            id="destaque-na-instituicao-e-na-revista",
        ),
        pytest.param(
            "W4387465478", "<b>Escola Nacional de <b>Saúde</b> Pública, Fundação Oswaldo Cruz </b>",
            "Escola Nacional de Saúde Pública, Fundação Oswaldo Cruz", "Cadernos de Saúde Pública",
            id="destaque-no-meio-da-instituicao",
        ),
    ])
    @responses.activate
    def test_metadados_com_termo_destacado(self, scraper, mocker, id_card, trecho_html, instituicao, revista):
        mocker.patch("time.sleep")
        html = load_sample("capes", "raspar/single_page.html")
        assert trecho_html in html, f"Trecho {trecho_html!r} sumiu do sample; recapturar e rever o caso."
        _registrar("natjus", html.encode("utf-8"))

        df = scraper.raspar(pesquisa="natjus", paginas=range(1, 2)).set_index("id")
        assert (df.at[id_card, "instituicao"], df.at[id_card, "revista"]) == (instituicao, revista)
