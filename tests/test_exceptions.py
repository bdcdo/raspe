"""Testes unitários para raspe.exceptions.

Cobre a hierarquia de exceções customizadas, atributos opcionais e o alias
de retrocompatibilidade ``SeleniumError``.
"""

import pytest

from raspe.exceptions import (
    APIError,
    APIKeyError,
    BrowserError,
    DriverNotInstalledError,
    RateLimitError,
    ScraperError,
    SeleniumError,
    ValidationError,
)


class TestScraperError:
    """ScraperError é a raiz da hierarquia de exceções."""

    def test_eh_subclasse_de_exception(self):
        assert issubclass(ScraperError, Exception)

    def test_mensagem_preserved(self):
        exc = ScraperError("mensagem de teste")
        assert str(exc) == "mensagem de teste"

    def test_pode_ser_levantada_e_capturada(self):
        with pytest.raises(ScraperError, match="boom"):
            raise ScraperError("boom")


class TestAPIKeyError:
    """APIKeyError herda de ScraperError."""

    def test_hierarquia(self):
        exc = APIKeyError("chave inválida")
        assert isinstance(exc, ScraperError)
        assert isinstance(exc, APIKeyError)

    def test_capturavel_como_scraper_error(self):
        with pytest.raises(ScraperError):
            raise APIKeyError("falta API key")


class TestRateLimitError:
    """RateLimitError carrega retry_after opcional."""

    def test_hierarquia(self):
        exc = RateLimitError("rate limit")
        assert isinstance(exc, ScraperError)

    def test_sem_retry_after(self):
        exc = RateLimitError("rate limit")
        assert exc.retry_after is None

    def test_com_retry_after(self):
        exc = RateLimitError("rate limit", retry_after=60)
        assert exc.retry_after == 60

    def test_mensagem_preserved(self):
        exc = RateLimitError("excedeu limite", retry_after=30)
        assert "excedeu limite" in str(exc)


class TestAPIError:
    """APIError carrega status_code e response_text (truncado em 500 chars)."""

    def test_hierarquia(self):
        exc = APIError("erro na api")
        assert isinstance(exc, ScraperError)

    def test_defaults(self):
        exc = APIError("falha")
        assert exc.status_code is None
        assert exc.response_text == ""

    def test_com_status_code_e_texto(self):
        exc = APIError("erro 500", status_code=500, response_text="server panic")
        assert exc.status_code == 500
        assert exc.response_text == "server panic"

    def test_response_text_truncado_em_500(self):
        texto_longo = "x" * 1000
        exc = APIError("erro", response_text=texto_longo)
        assert len(exc.response_text) == 500

    def test_response_text_none_safe(self):
        exc = APIError("erro", response_text="")
        assert exc.response_text == ""


class TestValidationError:
    """ValidationError herda de ScraperError."""

    def test_hierarquia(self):
        exc = ValidationError("data inválida")
        assert isinstance(exc, ScraperError)

    def test_capturavel_via_value_error_nao(self):
        """ValidationError NÃO é um ValueError; capturar especificamente."""
        with pytest.raises(ValidationError):
            raise ValidationError("erro")


class TestBrowserError:
    """BrowserError e seus alias/sub-classes."""

    def test_hierarquia(self):
        exc = BrowserError("timeout")
        assert isinstance(exc, ScraperError)

    def test_selenium_error_eh_alias(self):
        """SeleniumError é mantido como alias de BrowserError."""
        assert SeleniumError is BrowserError

    def test_driver_not_installed_eh_browser_error(self):
        exc = DriverNotInstalledError("instale playwright")
        assert isinstance(exc, BrowserError)
        assert isinstance(exc, ScraperError)
