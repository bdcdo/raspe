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

## Versionamento e CHANGELOG

- Projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/): `MAJOR.MINOR.PATCH`. Versão atual em `pyproject.toml`.
- `CHANGELOG.md` segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
- **Toda mudança visível ao usuário** (novo scraper, novo parâmetro, mudança de comportamento, correção de bug, breaking change, mudança de dependência mínima) deve adicionar uma linha sob `## [Não lançado]`, na categoria adequada:
  - **Adicionado** — novas funcionalidades
  - **Modificado** — mudanças em funcionalidades existentes
  - **Descontinuado** — funcionalidades que serão removidas em breve
  - **Removido** — funcionalidades removidas
  - **Corrigido** — correções de bugs
  - **Segurança** — correções com impacto de segurança
- Mudanças puramente internas (refatoração sem efeito observável, reorganização de testes, ajuste de hooks de lint) **não** entram no CHANGELOG.
- Ao lançar uma nova versão:
  1. Renomear `## [Não lançado]` para `## [X.Y.Z] - YYYY-MM-DD`
  2. Criar uma nova seção `## [Não lançado]` vazia logo acima
  3. Atualizar `version` em `pyproject.toml`
  4. Atualizar os links de comparação no rodapé do `CHANGELOG.md`
  5. Criar a tag git `vX.Y.Z` apontando para o commit do release
- Escrever em português brasileiro, frases curtas no particípio passado ("Adicionado scraper X", "Corrigido erro Y").

## Desenvolvimento

- Python >= 3.11, gerenciador `uv`
- Instalar deps de dev: `uv pip install -e ".[dev]"`
- Ativar hooks: `pre-commit install`
- Hooks rodam em cada commit: trailing whitespace, isort, pylint, flake8, mypy, pyright
- Comprimento máximo de linha: 120
- Para rodar todos os hooks manualmente: `pre-commit run --all-files`

## Testes

A suíte usa `pytest` + `responses` + `pytest-mock` para contratos offline,
sem tocar a rede. Convenção:

- Por scraper: `tests/<scraper>/test_<método>_contract.py`.
- Samples reais commitados em `tests/<scraper>/samples/<endpoint>/<cenario>.<ext>`.
- Helpers: `tests/_helpers.py` expõe `load_sample()` e `load_sample_bytes()`.
- Captura de samples: `tests/fixtures/capture/<scraper>.py` (script ad-hoc).

Comandos úteis:

```bash
pytest                                # padrão (exclui integração via addopts)
pytest -m integration                 # só testes de integração
pytest tests/<scraper>/ -v            # só um scraper
pytest --cov=src/raspe                # com cobertura
```

Markers disponíveis: `slow`, `integration`. `filterwarnings = ["error"]`
está ativo — qualquer warning não capturado vira erro de teste.

### Checklist obrigatória ao adicionar um novo scraper

Todo scraper novo em `src/raspe/scrapers/<xx>.py` deve entrar acompanhado
de **pelo menos um teste de contrato** por método público (`raspar` e
qualquer método adicional). O PR fica bloqueado sem isso.

1. **Script de captura** em `tests/fixtures/capture/<xx>.py` que exercita
   o scraper real e salva as respostas cruas em
   `tests/<xx>/samples/<endpoint>/<cenario>.<ext>`. Mínimo 3 cenários por
   endpoint: typical (paginação), single_page, no_results.
2. **Samples commitados** em `tests/<xx>/samples/<endpoint>/`.
   Convenção: `page_01.html`, `page_02.html`, `single_page.html`,
   `no_results.html` (ou extensão apropriada — `.json`, etc.).
3. **Teste de contrato** em `tests/<xx>/test_raspar_contract.py`:
   - `@responses.activate` decorator.
   - `mocker.patch("time.sleep")` em toda função com paginação.
   - `responses.add(..., body=load_sample_bytes("<xx>", "raspar/<cenario>.<ext>"))`
     para cada request esperado.
   - Matcher de payload sempre que possível:
     - `urlencoded_params_matcher(..., strict_match=False)` para POST form.
     - `json_params_matcher(...)` para POST JSON.
     - `query_param_matcher(...)` para GET.
   - Schema validado por **subset**: `{"col_a", "col_b"} <= set(df.columns)`.
     Nunca igualdade.
   - Pelo menos 3 casos: typical, single_page, no_results.
4. **Sem `@pytest.mark.integration`** no contrato.
5. **Sem dependência de rede, relógio ou TLS real**. Adapter custom
   (ex.: SSL desabilitado): testar só configuração (`isinstance`).
6. **Fluxos multi-step com ordem obrigatória** usam
   `responses.registries.OrderedRegistry`.
7. **Captchas, tokens dinâmicos, lazy imports** (ex.: `txtcaptcha`,
   `browser_cookie3`) são **mockados** via `mocker.patch.dict(sys.modules, ...)`,
   nunca invocados de verdade.
8. **CHANGELOG**: a adição de novo scraper já é uma entrada `Adicionado`;
   adicionar testes para scraper existente é mudança interna e não
   precisa de entrada (ver "Versionamento e CHANGELOG" acima).
