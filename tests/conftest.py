"""Configuração compartilhada do pytest para a suíte raspe.

Não inclui fixture autouse para mockar `time.sleep` — cada teste com
paginação deve usar `mocker.patch("time.sleep")` explicitamente para
deixar a intenção clara.
"""
