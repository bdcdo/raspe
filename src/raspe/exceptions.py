"""
Exceções customizadas para o raspe.

Este módulo define exceções específicas para erros comuns durante
operações de web scraping, permitindo tratamento de erros mais
granular e mensagens mais informativas.
"""


class ScraperError(Exception):
    """Exceção base para erros de scraping."""
    pass


class APIKeyError(ScraperError):
    """Exceção para erros relacionados a chaves de API.

    Levantada quando:
    - API key não foi fornecida mas é obrigatória
    - API key é inválida ou expirada
    - API key não tem permissão para o recurso solicitado
    """
    pass


class RateLimitError(ScraperError):
    """Exceção para erros de rate limit (HTTP 429).

    Levantada quando a API retorna erro 429 (Too Many Requests)
    após esgotar todas as tentativas de retry.

    Attributes:
        retry_after: Tempo em segundos sugerido para aguardar (se disponível).
    """

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class APIError(ScraperError):
    """Exceção para erros genéricos de API.

    Levantada quando a API retorna um erro não tratado especificamente.

    Attributes:
        status_code: Código HTTP retornado pela API.
        response_text: Texto da resposta (truncado se muito longo).
    """

    def __init__(self, message: str, status_code: int | None = None, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text[:500] if response_text else ""


class ValidationError(ScraperError):
    """Exceção para erros de validação de parâmetros.

    Levantada quando parâmetros fornecidos pelo usuário são inválidos,
    como datas em formato incorreto ou valores fora do range permitido.
    """
    pass
