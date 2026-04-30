# Diretrizes para o Projeto raspe

## Idioma

- **Docstrings**: Sempre em português brasileiro
- **Comentários no código**: Português brasileiro
- **Mensagens de erro**: Português brasileiro
- **Nomes de variáveis e funções**: Podem ser em português ou inglês, mas manter consistência dentro do mesmo arquivo
- **README e documentação**: Português brasileiro

## Estilo de Código

- Usar type hints em todas as funções públicas
- Docstrings no formato Google (Args, Returns, Raises, Examples)
- Exceções customizadas devem herdar de `ScraperError`

## Estrutura de Scrapers

Novos scrapers devem:
1. Herdar de `BaseScraper` (e `HTMLScraper` se necessário)
2. Implementar as propriedades abstratas: `api_base`, `type`, `query_page_name`, `api_method`
3. Implementar os métodos: `_set_query_base()`, `_find_n_pags()`, `_parse_page()`
4. Validar parâmetros em `_validar_parametros()` (sobrescrevendo o método base)

## Desenvolvimento

- Python >= 3.11, gerenciador `uv`
- Instalar deps de dev: `uv pip install -e ".[dev]"`
- Ativar hooks: `pre-commit install`
- Hooks rodam em cada commit: trailing whitespace, isort, pylint, flake8, mypy, pyright
- Comprimento máximo de linha: 120
- Para rodar todos os hooks manualmente: `pre-commit run --all-files`
