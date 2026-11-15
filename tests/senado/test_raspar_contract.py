"""Contrato offline para ``ScraperSenadoFederal.raspar``.

Os samples ``page_01``, ``page_02`` e ``single_page`` foram construídos à
mão, com a estrutura que o parser lê (``a[data-click-type]`` com a contagem
e ``div.sf-busca-resultados-item``) e texto de enchimento. Não há script de
captura para eles: a busca HTML sai de cena com a reescrita do scraper
sobre a API oficial do Senado (#29).

``no_results.html`` e ``anti_robo.html`` são reais (2026-11-14). A busca sem
resultados não traz o link da coleção com a contagem, só o aviso "Nenhum
resultado encontrado" (capturada com navegador). ``anti_robo.html`` é a
verificação anti-robô, servida com HTTP 200, que o raspador resolve sozinho;
o IP do cliente foi trocado por um IP de documentação.
"""

import hashlib
from urllib.parse import parse_qs

import pytest
import requests
import responses
from responses import registries

from raspe.exceptions import ScraperError
from raspe.scrapers.senado import ScraperSenadoFederal
from tests._helpers import load_sample_bytes

API_URL = "https://www6g.senado.leg.br/busca"
DESAFIO_URL = "https://www6g.senado.leg.br/_challenge"
COLUNAS_OBRIGATORIAS = {"titulo", "link_norma", "link_detalhes", "descricao", "trecho_descricao"}


@pytest.fixture
def scraper():
    return ScraperSenadoFederal()


class TestRasparContract:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_typical_paginacao(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/page_01.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/page_02.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="tributário")
        assert not df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)
        assert len(df) == 3  # 2 + 1

    @responses.activate
    def test_single_page(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/single_page.html"),
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="lei")
        assert len(df) == 3
        # O terceiro item tem só 1 link no h3 → link_detalhes = 'NA'
        assert "NA" in df["link_detalhes"].values

    @responses.activate
    def test_descricao_nos_dois_layouts_do_item(self, scraper, mocker):
        """``descricao`` sai de ``p[0]``, ou de ``p[1]`` quando ``p[0]`` é "Legislação".

        O sample single_page traz os dois layouts que ``_parse_page`` trata:
        a Lei e o Decreto no layout original (descrição, tipo, trecho) e a
        Portaria no layout em que o primeiro ``<p>`` é o rótulo
        "Legislação". Nos dois, ``trecho_descricao`` é o terceiro ``<p>``.
        """
        mocker.patch("time.sleep")
        body = load_sample_bytes("senado", "raspar/single_page.html")
        assert "<p>Legislação</p>".encode() in body, "o sample perdeu o layout com rótulo 'Legislação'"
        responses.add(
            responses.GET, API_URL,
            body=body,
            status=200, content_type="text/html; charset=utf-8",
        )

        df = scraper.raspar(pesquisa="lei").set_index("titulo")

        lei = df.loc["Lei nº 14.999/2024"]
        assert lei["descricao"] == "Altera o código tributário nacional."
        assert lei["trecho_descricao"] == "Estabelece regras de tributação para empresas de tecnologia."

        portaria = df.loc["Portaria nº 12/2024"]
        assert portaria["descricao"] == "Cria comissão técnica."
        assert portaria["trecho_descricao"] == "Designa servidores para análise de propostas."

        # O rótulo nunca vaza para a coluna.
        assert "Legislação" not in df["descricao"].values

    @responses.activate
    def test_no_results(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        df = scraper.raspar(pesquisa="xxxxxx_inexistente")
        assert df.empty
        assert COLUNAS_OBRIGATORIAS <= set(df.columns)

    @responses.activate(registry=registries.OrderedRegistry)
    def test_resolve_a_verificacao_anti_robo_e_segue(self, scraper, mocker):
        """Resolve a prova de trabalho, envia a resposta e repete a busca da página 1."""
        mocker.patch("time.sleep")
        respostas_ao_desafio = []

        def _desafio(request):
            respostas_ao_desafio.append({k: v[0] for k, v in parse_qs(request.body).items()})
            return (200, {}, "<!doctype html><html><body>OK</body></html>")

        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/anti_robo.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add_callback(responses.POST, DESAFIO_URL, callback=_desafio)
        for sample in ("page_01", "page_02"):
            responses.add(
                responses.GET, API_URL,
                body=load_sample_bytes("senado", f"raspar/{sample}.html"),
                status=200, content_type="text/html; charset=utf-8",
            )

        df = scraper.raspar(pesquisa="tributário")
        assert len(df) == 3

        (campos,) = respostas_ao_desafio
        assert campos["ip"] == "203.0.113.10"
        entrada = f"{campos['ip']};www6g.senado.leg.br;{campos['ts']};{campos['tries']}"
        assert hashlib.sha256(entrada.encode()).hexdigest().startswith("0" * int(campos["diff"]))

    @responses.activate(registry=registries.OrderedRegistry)
    def test_verificacao_anti_robo_persistente_levanta_erro(self, scraper, mocker):
        """Se a verificação volta depois de resolvida, não pode virar 0 resultados."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/anti_robo.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        responses.add(responses.POST, DESAFIO_URL, body="OK", status=200)
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/anti_robo.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        with pytest.raises(ScraperError, match="Verificação de segurança"):
            scraper.raspar(pesquisa="meio ambiente")

    @pytest.mark.parametrize("inputs, erro", [
        ('<input name="ip" value="203.0.113.10"><input name="ts" value="1">', "mudou de formato"),
        ('<input name="ip" value="203.0.113.10"><input name="ts" value="1"><input name="diff" value="64">',
         "não teve solução"),
    ])
    def test_desafio_fora_do_formato_ou_sem_solucao_levanta_erro(self, scraper, inputs, erro):
        """Formulário mudado ou desafio impossível viram ``ScraperError``, sem POST nem nova busca."""
        scraper.MAX_TENTATIVAS_DESAFIO = 100
        form = scraper.soup_it(f'<form name="challenge" action="/_challenge">{inputs}</form>').form
        with pytest.raises(ScraperError, match=erro):
            scraper._resolver_desafio(form, API_URL)

    def test_contagem_com_separador_de_milhar(self, scraper):
        """O site mostra a contagem como "8.950" (markup real de 2026-11-14)."""
        r0 = requests.Response()
        r0.status_code = 200
        r0._content = (
            '<a href="/busca/?q=meio+ambiente" data-click-type="dynnav.colecao.Legislação Federal">'
            '<span>Legislação</span>&nbsp;<span class="badge">8.950</span></a>'
        ).encode("utf-8")
        assert scraper._find_n_pags(r0) == 895

    @responses.activate
    def test_query_inclui_filtros_opcionais(self, scraper, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, API_URL,
            body=load_sample_bytes("senado", "raspar/no_results.html"),
            status=200, content_type="text/html; charset=utf-8",
        )
        scraper.raspar(pesquisa="x", ano=2024, tipo_materia="Lei")
        # Verifica que ano e tipo-materia foram incluídos na query
        call_url = responses.calls[0].request.url
        assert "ano=2024" in call_url
        assert "tipo-materia=Lei" in call_url
