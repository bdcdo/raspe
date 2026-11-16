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
4. Declarar `schema_entrada` e `schema_saida` (em `src/raspe/schemas/`), registrar em `tests/schemas/test_schema_coverage.py` e regerar `docs/colunas.md` com `python -m raspe.schemas.documentacao`
5. Declarar as colunas do resultado no atributo de classe `colunas` e usá-lo no
   `_parse_page()`; a busca sem resultados devolve um `DataFrame` vazio com essas colunas.
   Com `schema_saida`, não declarar `colunas`: a base as tira do schema de saída
6. No `_find_n_pags()`, quando a página não traz o marcador de contagem, devolver
   `self._confirmar_busca_vazia(soup)` (de `HTMLScraper`) em vez de 0: ele só aceita 0
   se a página traz o aviso de busca vazia e levanta `ScraperError` em página de
   manutenção ou anti-robô

## Versionamento e CHANGELOG

- Projeto segue [Versionamento Semântico](https://semver.org/lang/pt-BR/): `MAJOR.MINOR.PATCH`. Versão atual em `pyproject.toml`.
- `CHANGELOG.md` segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
- **Toda mudança visível ao usuário** (novo scraper, novo parâmetro, mudança de comportamento, correção de bug, breaking change, mudança de dependência mínima) deve adicionar uma linha sob `## [Não lançado]`, na categoria adequada: Adicionado, Modificado, Descontinuado, Removido, Corrigido ou Segurança.
- Mudanças puramente internas (refatoração sem efeito observável, reorganização de testes, ajuste de hooks de lint) **não** entram no CHANGELOG.
- Ao lançar uma nova versão:
  1. Renomear `## [Não lançado]` para `## [X.Y.Z] - YYYY-MM-DD`
  2. Criar uma nova seção `## [Não lançado]` vazia logo acima
  3. Atualizar `version` em `pyproject.toml`
  4. Atualizar os links de comparação no rodapé do `CHANGELOG.md`
  5. Com o commit do release na `main` remota, enviar a tag `vX.Y.Z` (`git push origin vX.Y.Z`). Ela dispara `.github/workflows/release.yml`, que confere, testa e publica no PyPI. Se falhar antes de publicar: corrigir, apagar a tag local e a remota (`git tag -d vX.Y.Z && git push --delete origin vX.Y.Z`) e recriá-la. Versão publicada não se republica.
- Uma vez, antes do primeiro release: Trusted Publisher pendente no PyPI (https://pypi.org/manage/account/publishing/) com projeto `raspe`, dono `bdcdo`, repositório `raspe`, workflow `release.yml` e environment `pypi`; no GitHub, o environment `pypi` (Settings > Environments, revisor opcional); no commit do release, o README passa a instalar pelo PyPI e seus links relativos viram absolutos (`https://github.com/bdcdo/raspe/blob/main/...`), porque no PyPI eles não resolvem.
- Escrever em português brasileiro, frases curtas no particípio passado ("Adicionado scraper X", "Corrigido erro Y").

## Desenvolvimento

- Python >= 3.11, gerenciador `uv`
- Criar o ambiente e instalar tudo (dev + browser; o pyright precisa do
  Playwright instalado para resolver os imports de `playwright_scraper.py`):

  ```bash
  uv venv -p 3.11 .venv
  uv pip install -e ".[all]"
  source .venv/bin/activate
  ```

- Os hooks locais (mypy, pyright, pytest) chamam `.venv/bin/...`, então o
  ambiente precisa estar em `.venv/` na raiz do repo.
- Ativar hooks: `pre-commit install`
- Hooks rodam no commit: trailing whitespace, isort, pylint, flake8, mypy, pyright e pytest
  (suíte offline, ~15 s), cada um só quando o commit traz arquivo do tipo ou pasta que ele
  cobre (o pytest, por exemplo, só com `src/` ou `tests/`). O `gitignore-versionado` roda em
  todo commit e reprova arquivo versionado que o `.gitignore` cobre
- Comprimento máximo de linha: 120
- Para rodar todos os hooks manualmente: `pre-commit run --all-files`
- Comandos isolados (use o hook, não o binário solto: `flake8` e `pylint`
  rodados direto do `.venv` ignoram os args do `.pre-commit-config.yaml` e
  acusam falsos positivos):

  ```bash
  pytest                                   # testes + gate de cobertura (fail_under=80)
  pre-commit run isort --all-files         # lint
  pre-commit run pylint --all-files        # lint (só src/)
  pre-commit run flake8 --all-files        # lint
  pre-commit run mypy --all-files          # typecheck
  pre-commit run pyright --all-files       # typecheck (warnings não falham; erros sim)
  ```

- CI (`.github/workflows/ci.yml`), em todo PR e em push na `main`: o job `testes` roda
  `pytest` na matriz de Python do workflow, e o job `lint` roda `pre-commit run --all-files` com todos
  os hooks do `.pre-commit-config.yaml`, menos o `pytest`. Sem deploy e sem segredos.
- Os testes de Playwright não abrem navegador; não é preciso `playwright install`.

## Estrutura do repositório

```
src/raspe/
  __init__.py            # API pública: funções de conveniência por fonte
  abstract_scraper.py    # interface mínima
  base_scraper.py        # BaseScraper: paginação, retry, montagem do DataFrame
  html_scraper.py        # HTMLScraper: helpers de parsing com BeautifulSoup
  playwright_scraper.py  # base async para fontes que exigem navegador
  scraper_manager.py     # registro/despacho dos scrapers
  exceptions.py          # ScraperError e derivadas
  utils.py
  scrapers/<fonte>.py    # um arquivo por fonte (presidencia, camara, senado, ipea, capes, ...)
tests/
  <scraper>/test_raspar_contract.py   # contratos offline
  <scraper>/samples/                  # respostas reais commitadas
  fixtures/capture/<scraper>.py       # scripts de captura de samples
  test_<modulo>.py                    # testes dos módulos core
notebooks/               # exemplos de uso por fonte (não são testados)
```

## Git e PRs

- Branch por mudança; nada de push direto na `main`. PRs entram por squash,
  com o número do PR no título do commit.
- Mensagens no estilo Conventional Commits em português:
  `feat: adiciona scraper X`, `fix(base_scraper): ...`, `test(scrapers): ...`, `chore: ...`.

## Testes

A suíte usa `pytest` + `responses` + `pytest-mock` para contratos offline,
sem tocar a rede. Convenção:

- Por scraper: `tests/<scraper>/test_<método>_contract.py`.
- Samples reais commitados em `tests/<scraper>/samples/<endpoint>/<cenario>.<ext>`.
- Helpers: `tests/_helpers.py` expõe `load_sample()` e `load_sample_bytes()`.
- Captura de samples: `tests/fixtures/capture/<scraper>.py` (script ad-hoc).

`pytest` exclui os testes de integração pelo `addopts`; `pytest -m integration` roda só eles. `filterwarnings = ["error"]` está ativo: qualquer warning não capturado vira erro de teste.

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
   - Colunas por igualdade: `list(df.columns) == OutputXx.colunas()`, também no no_results.
   - Pelo menos 3 casos: typical, single_page, no_results.
4. **Sem `@pytest.mark.integration`** no contrato.
5. **Sem dependência de rede, relógio ou TLS real**. Adapter custom
   (ex.: SSL desabilitado): testar só configuração (`isinstance`).
6. **Fluxos multi-step com ordem obrigatória** usam
   `responses.registries.OrderedRegistry`.
7. **Captchas, tokens dinâmicos, lazy imports** (ex.: `txtcaptcha`,
   `browser_cookie3`) são **mockados** via `mocker.patch.dict(sys.modules, ...)`,
   nunca invocados de verdade.
8. **CHANGELOG**: scraper novo é entrada `Adicionado` (ver "Versionamento e CHANGELOG").
