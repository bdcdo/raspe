"""Testes unitários para BaseScraper.

Usa ``_DummyHTTPScraper`` (subclasse mínima) para exercitar o fluxo
``raspar()`` → ``_download_data()`` → ``_request_with_retry()`` →
``_parse_data()`` sem tocar a rede (via ``responses``) e sem tocar o relógio
(via ``mocker.patch("time.sleep")``).
"""

import re
from typing import Any, Literal

import pandas as pd
import pytest
import requests
import responses
from responses import matchers, registries

from raspe.base_scraper import BaseScraper
from raspe.exceptions import APIError, RateLimitError


class _DummyHTTPScraper(BaseScraper):
    """Subclasse concreta com lógica mínima para alimentar os testes."""

    def __init__(self, debug: bool = False, api_method: Literal['GET', 'POST'] = 'GET'):
        super().__init__("DUMMY", debug=debug)
        self._api_base = "http://example.com/api"
        self._type: Literal['HTML'] = 'HTML'
        self._query_page_name = 'page'
        self._api_method: Literal['GET', 'POST'] = api_method
        self.sleep_time = 0  # eliminamos sleep entre páginas além do mock

    @property
    def api_base(self) -> str:
        return self._api_base

    @property
    def type(self) -> Literal['HTML']:
        return self._type

    @property
    def query_page_name(self) -> str:
        return self._query_page_name

    @property
    def api_method(self) -> Literal['GET', 'POST']:
        return self._api_method

    def _set_query_base(self, **kwargs) -> dict[str, Any]:
        return {"q": str(kwargs.get("termo", "default"))}

    def _find_n_pags(self, r0: requests.Response) -> int:
        m = re.search(r"<total>(\d+)</total>", r0.text)
        return int(m.group(1)) if m else 0

    def _parse_page(self, path: str) -> pd.DataFrame:
        with open(path, "r", encoding="utf-8") as f:
            return pd.DataFrame({"content": [f.read()]})


# ---------------------------------------------------------------------------
# Fluxo principal: raspar() → _download_data()
# ---------------------------------------------------------------------------


class TestRasparBuscaUnica:
    @responses.activate
    def test_raspar_uma_pagina(self, mocker):
        """Fluxo completo com 1 página: 1 request inicial + 1 de página.

        Como 'termo' está na lista de parâmetros reconhecidos como busca
        (junto com 'pesquisa', 'q', 'query'), o DataFrame final ganha
        coluna ``termo_busca``.
        """
        mocker.patch("time.sleep")
        responses.add(
            responses.GET,
            "http://example.com/api",
            body="<total>1</total>",
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({"q": "termo1"})],
        )
        responses.add(
            responses.GET,
            "http://example.com/api",
            body="<resultado>item</resultado>",
            status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({"q": "termo1", "page": "1"})],
        )

        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo="termo1")

        assert not df.empty
        assert "termo_busca" in df.columns
        assert df["termo_busca"].iloc[0] == "termo1"

    @responses.activate
    def test_raspar_adiciona_termo_busca_para_param_pesquisa(self, mocker):
        """Quando o param de busca é 'pesquisa', o DataFrame ganha coluna 'termo_busca'."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>1</total>", status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body="<resultado>item</resultado>", status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper = _DummyHTTPScraper()

        # Sobrescreve _set_query_base para usar 'pesquisa' como termo
        scraper._set_query_base = lambda **kw: {"q": str(kw.get("pesquisa", ""))}

        df = scraper.raspar(pesquisa="meio ambiente")
        assert "termo_busca" in df.columns
        assert df["termo_busca"].iloc[0] == "meio ambiente"

    @responses.activate
    def test_raspar_paginacao_completa(self, mocker):
        """3 páginas: 1 request inicial + 3 de página, cada uma com body próprio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>3</total>", status=200,
            content_type="text/html; charset=utf-8",
            match=[matchers.query_param_matcher({"q": "x"})],
        )
        for pag in range(1, 4):
            responses.add(
                responses.GET, "http://example.com/api",
                body=f"<r>pagina{pag}</r>", status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher({"q": "x", "page": str(pag)})],
            )

        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo="x")
        assert len(df) == 3

    @responses.activate
    def test_raspar_zero_paginas(self, mocker):
        """Quando _find_n_pags retorna 0, nenhuma página é baixada."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>0</total>", status=200,
            content_type="text/html; charset=utf-8",
        )
        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo="vazio")
        assert df.empty

    @responses.activate(registry=registries.OrderedRegistry)
    def test_raspar_pula_pagina_com_erro_5xx(self, mocker):
        """Páginas individuais com 5xx são puladas (não levantam) - apenas
        a request inicial usa _request_with_retry; downloads de página
        seguem fluxo direto.
        """
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>2</total>", status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body="<r>ok</r>", status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body="erro", status=503,
        )

        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo="x")
        # Apenas 1 página foi salva (a outra deu 503 e foi pulada)
        assert len(df) == 1

    @responses.activate(registry=registries.OrderedRegistry)
    def test_raspar_pula_pagina_com_excecao(self, mocker):
        """Exceções de rede em páginas individuais são logadas e puladas."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>2</total>", status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body=ConnectionError("falha de rede"),
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body="<r>ok</r>", status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo="x")
        assert len(df) == 1

    @responses.activate
    def test_raspar_paginas_nao_iteravel_usa_fallback(self, mocker):
        """Se _set_paginas devolver algo não iterável, usa range vazio."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>1</total>", status=200,
            content_type="text/html; charset=utf-8",
        )

        scraper = _DummyHTTPScraper()
        mocker.patch.object(scraper, "_set_paginas", return_value=42)  # int não iterável
        df = scraper.raspar(termo="x")
        assert df.empty

    @responses.activate
    def test_debug_true_preserva_download_dir(self, mocker):
        """Com debug=True, o diretório de download não é removido após raspar()."""
        import os

        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            body="<total>1</total>", status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            body="<r>x</r>", status=200,
            content_type="text/html; charset=utf-8",
        )

        # Captura o path retornado por _download_data para verificar depois
        captured: dict[str, str] = {}
        scraper = _DummyHTTPScraper(debug=True)
        original_download = scraper._download_data

        def capture_path(**kwargs):
            path = original_download(**kwargs)
            captured["path"] = path
            return path

        mocker.patch.object(scraper, "_download_data", side_effect=capture_path)

        scraper.raspar(termo="x")
        assert "path" in captured
        # Com debug=True, o diretório deve continuar existindo
        assert os.path.isdir(captured["path"])


class TestRasparListaTermos:
    @responses.activate
    def test_lista_de_termos_concatena_resultados(self, mocker):
        """termo=['a','b'] dispara 2 buscas com termo_busca correspondente."""
        mocker.patch("time.sleep")
        for termo in ["a", "b"]:
            responses.add(
                responses.GET, "http://example.com/api",
                body="<total>1</total>", status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher({"q": termo})],
            )
            responses.add(
                responses.GET, "http://example.com/api",
                body=f"<r>{termo}</r>", status=200,
                content_type="text/html; charset=utf-8",
                match=[matchers.query_param_matcher({"q": termo, "page": "1"})],
            )

        scraper = _DummyHTTPScraper()
        df = scraper.raspar(termo=["a", "b"])
        assert len(df) == 2
        assert set(df["termo_busca"]) == {"a", "b"}

    def test_lista_em_multiplos_params_levanta_valueerror(self, mocker):
        """raspar() só suporta lista em um único parâmetro."""
        mocker.patch("time.sleep")
        scraper = _DummyHTTPScraper()
        with pytest.raises(ValueError, match="só suporta lista"):
            scraper.raspar(termo=["a"], outro=["x"])


# ---------------------------------------------------------------------------
# _request_with_retry: 429, 5xx e 4xx
# ---------------------------------------------------------------------------


class TestRequestWithRetry:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_429_com_retry_after_aguarda_e_retenta(self, mocker):
        sleep_mock = mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            status=429, headers={"Retry-After": "5"}, body="",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            status=200, body="ok",
        )

        scraper = _DummyHTTPScraper()
        r = scraper._request_with_retry({"q": "x"})
        assert r.status_code == 200
        # Deve ter chamado sleep com 5s (do Retry-After)
        sleep_mock.assert_any_call(5)

    @responses.activate(registry=registries.OrderedRegistry)
    def test_429_retry_after_invalido_cai_em_backoff(self, mocker):
        sleep_mock = mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            status=429, headers={"Retry-After": "nao-numero"}, body="",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            status=200, body="ok",
        )

        scraper = _DummyHTTPScraper()
        r = scraper._request_with_retry({"q": "x"})
        assert r.status_code == 200
        # Backoff exponencial: 2**0 = 1
        sleep_mock.assert_any_call(1)

    @responses.activate(registry=registries.OrderedRegistry)
    def test_429_sem_retry_after_usa_backoff_exponencial(self, mocker):
        sleep_mock = mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            status=429, body="",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            status=200, body="ok",
        )

        scraper = _DummyHTTPScraper()
        r = scraper._request_with_retry({"q": "x"})
        assert r.status_code == 200
        sleep_mock.assert_any_call(1)

    @responses.activate(registry=registries.OrderedRegistry)
    def test_429_esgota_levanta_rate_limit_error(self, mocker):
        mocker.patch("time.sleep")
        # 3 tentativas (max_retries padrão), todas 429
        for _ in range(3):
            responses.add(
                responses.GET, "http://example.com/api",
                status=429, headers={"Retry-After": "1"}, body="",
            )

        scraper = _DummyHTTPScraper()
        with pytest.raises(RateLimitError) as exc_info:
            scraper._request_with_retry({"q": "x"})
        assert exc_info.value.retry_after == 1

    @responses.activate(registry=registries.OrderedRegistry)
    def test_5xx_recupera_apos_retry(self, mocker):
        mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            status=500, body="err",
        )
        responses.add(
            responses.GET, "http://example.com/api",
            status=200, body="ok",
        )

        scraper = _DummyHTTPScraper()
        r = scraper._request_with_retry({"q": "x"})
        assert r.status_code == 200

    @responses.activate(registry=registries.OrderedRegistry)
    def test_5xx_esgota_levanta_api_error(self, mocker):
        mocker.patch("time.sleep")
        for _ in range(3):
            responses.add(
                responses.GET, "http://example.com/api",
                status=503, body="indisponivel",
            )

        scraper = _DummyHTTPScraper()
        with pytest.raises(APIError) as exc_info:
            scraper._request_with_retry({"q": "x"})
        assert exc_info.value.status_code == 503
        assert "indisponivel" in exc_info.value.response_text

    @responses.activate
    def test_4xx_nao_retenta(self, mocker):
        """Erros 4xx (exceto 429) retornam imediatamente sem retry."""
        sleep_mock = mocker.patch("time.sleep")
        responses.add(
            responses.GET, "http://example.com/api",
            status=404, body="not found",
        )

        scraper = _DummyHTTPScraper()
        r = scraper._request_with_retry({"q": "x"})
        assert r.status_code == 404
        # Nenhum sleep deve ter sido chamado para 4xx
        sleep_mock.assert_not_called()

    @responses.activate(registry=registries.OrderedRegistry)
    def test_max_retries_override(self, mocker):
        """O parâmetro max_retries sobrescreve self.max_retries."""
        mocker.patch("time.sleep")
        # 2 tentativas, ambas 503 → deve levantar após a segunda
        for _ in range(2):
            responses.add(
                responses.GET, "http://example.com/api",
                status=503, body="indisponivel",
            )

        scraper = _DummyHTTPScraper()
        # self.max_retries=3, mas o override fixa em 2
        with pytest.raises(APIError) as exc_info:
            scraper._request_with_retry({"q": "x"}, max_retries=2)
        assert exc_info.value.status_code == 503


# ---------------------------------------------------------------------------
# Helpers internos: _set_query_atual, _set_paginas, _set_r
# ---------------------------------------------------------------------------


class TestSetQueryAtual:
    def test_aplica_multiplier_e_increment(self):
        scraper = _DummyHTTPScraper()
        scraper.query_page_multiplier = 10
        scraper.query_page_increment = -10
        query = scraper._set_query_atual({"q": "x"}, pag=2)
        # page = 2*10 + (-10) = 10
        assert query["page"] == 10

    def test_old_page_name_recebe_pagina_anterior(self):
        scraper = _DummyHTTPScraper()
        scraper.old_page_name = "page_anterior"
        query = scraper._set_query_atual({"q": "x"}, pag=3)
        assert query["page"] == 3
        assert query["page_anterior"] == 2


class TestSetPaginas:
    def test_sem_paginas_pega_todas(self):
        scraper = _DummyHTTPScraper()
        result = scraper._set_paginas(None, 5)
        assert list(result) == [1, 2, 3, 4, 5]

    def test_paginas_explicitas_clipam_em_n_pags(self):
        scraper = _DummyHTTPScraper()
        # Pediu 1-100 mas só há 3 páginas; deve clipar
        result = scraper._set_paginas(range(1, 100), 3)
        assert list(result) == [1, 2, 3]

    def test_n_pags_none_vira_zero(self):
        scraper = _DummyHTTPScraper()
        result = scraper._set_paginas(None, None)
        assert list(result) == []

    def test_paginas_com_step_custom(self):
        """``range`` com step != 1 preserva o step ao clipar em n_pags."""
        scraper = _DummyHTTPScraper()
        result = scraper._set_paginas(range(1, 10, 2), 8)
        # start=1, stop=min(10, 9)=9, step=2 → [1, 3, 5, 7]
        assert list(result) == [1, 3, 5, 7]


class TestSetR:
    @responses.activate
    def test_post_envia_data(self):
        responses.add(
            responses.POST, "http://example.com/api",
            body="ok", status=200,
            match=[matchers.urlencoded_params_matcher({"q": "x"})],
        )
        scraper = _DummyHTTPScraper(api_method='POST')
        r = scraper._set_r({"q": "x"})
        assert r.status_code == 200

    @responses.activate
    def test_get_envia_params(self):
        responses.add(
            responses.GET, "http://example.com/api",
            body="ok", status=200,
            match=[matchers.query_param_matcher({"q": "x"})],
        )
        scraper = _DummyHTTPScraper(api_method='GET')
        r = scraper._set_r({"q": "x"})
        assert r.status_code == 200

    def test_metodo_invalido_levanta_valueerror(self):
        scraper = _DummyHTTPScraper()
        scraper._api_method = 'PATCH'  # type: ignore[assignment]
        with pytest.raises(ValueError, match="Método de API inválido"):
            scraper._set_r({"q": "x"})


# ---------------------------------------------------------------------------
# _get_n_pags: tratamento de erro da requisição inicial
# ---------------------------------------------------------------------------


class TestGetNPags:
    @responses.activate(registry=registries.OrderedRegistry)
    def test_erro_persistente_retorna_zero(self, mocker):
        """Quando _request_with_retry levanta APIError, _get_n_pags devolve 0."""
        mocker.patch("time.sleep")
        for _ in range(3):
            responses.add(
                responses.GET, "http://example.com/api",
                status=500, body="erro",
            )

        scraper = _DummyHTTPScraper()
        assert scraper._get_n_pags({"q": "x"}) == 0

    @responses.activate(registry=registries.OrderedRegistry)
    def test_rate_limit_persistente_retorna_zero(self, mocker):
        """Rate limit que esgota retries também é absorvido por _get_n_pags."""
        mocker.patch("time.sleep")
        for _ in range(3):
            responses.add(
                responses.GET, "http://example.com/api",
                status=429, headers={"Retry-After": "1"}, body="",
            )

        scraper = _DummyHTTPScraper()
        assert scraper._get_n_pags({"q": "x"}) == 0
