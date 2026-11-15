# Scripts de captura de samples

Cada scraper HTTP do raspe tem um script aqui que **exercita o scraper real
contra o backend** e salva as respostas cruas em
`tests/<scraper>/samples/<endpoint>/<cenario>.<ext>`.

Esses samples são a **fonte de verdade** dos contratos offline em
`tests/<scraper>/test_*_contract.py`. Se o backend do scraper mudar e o
contrato quebrar, re-rode o script de captura, inspecione o diff, ajuste
o parser se necessário e commite samples + parser num único PR.

## Por que scripts ad-hoc em vez de gravadores automáticos?

Cassetes VCR (via `pytest-recording`) são úteis para fluxos com estado
(ViewState, JWT, crypto token), mas para a maioria dos scrapers do raspe
um script simples que salva cada resposta é mais legível, mais fácil de
re-rodar e gera samples menores. Adoção de VCR fica caso a caso.

## Como rodar

```bash
# Pré-requisitos:
uv pip install -e ".[dev]"

# Rodar a captura de um scraper específico, a partir da raiz do repositório:
python -m tests.fixtures.capture.presidencia

# Gravar numa pasta fora do repositório, para comparar com os samples commitados:
python -m tests.fixtures.capture.presidencia --saida /tmp/captura-presidencia
```

A forma `-m` é necessária porque os scripts importam `tests.fixtures`. Rodado como arquivo (`python tests/fixtures/capture/presidencia.py`), o Python põe a pasta do script no `sys.path` no lugar da raiz, e o import falha com `ModuleNotFoundError: No module named 'tests'`.

Sem `--saida`, cada script grava em `tests/<scraper>/samples/<endpoint>/` e sobrescreve os samples commitados. Páginas grandes
demais para o limite de 500 KB do hook `check-added-large-files` passam por
`enxugar_html` (em `_util.py`), que tira `<script>`, `<style>`, `<svg>`,
comentários e o excesso de `<option>` e mantém o resto como o site devolveu. A exceção é o
`ipea.py`, que só esvazia os `<select>` (`_esvaziar_selects`) e grava o resto byte a byte, e o `capes.py`, que
grava as páginas inteiras e fica abaixo do limite pela escolha dos termos de busca. Os samples
ficam **commitados no repositório**, fora do `.gitignore`.

## Quando re-rodar

- O contrato `test_*_contract.py` falhou e a causa parece ser mudança no
  backend (HTML/JSON diferente) e não bug no scraper.
- Adição de um novo cenário de teste (ex.: novo filtro suportado).
- Curadoria periódica (ex.: 1× por trimestre) para detectar drift silencioso.

## Variáveis de ambiente necessárias

| Scraper | Env var | Como obter |
|---|---|---|
| nyt | `NYT_API_KEY` | https://developer.nytimes.com/get-started |

Outros scrapers não exigem auth.

## Cenários mínimos a capturar por scraper

Cada script deve produzir pelo menos 3 cenários por método público
(`raspar`, etc.):

1. **typical** — busca que retorna múltiplas páginas (≥2 páginas).
2. **single_page** — busca que cabe numa página só.
3. **no_results** — busca que retorna zero resultados.

Convenção de nomes dos arquivos:

```
tests/<scraper>/samples/<endpoint>/
    page_01.html       # primeira página da consulta typical
    page_02.html       # segunda página da consulta typical
    single_page.html   # cenário de página única
    no_results.html    # cenário sem resultados
```

## Helper compartilhado

`_util.py` fornece `capturar_cenarios(scraper, cenarios, saida)`, que baixa cada cenário com a query e o método HTTP do próprio scraper, e `pasta_saida(padrao, descricao)`, que lê o `--saida` dos scripts. Fornece também `enxugar_html(html)`, para passar como `enxugar` a `capturar_cenarios`, e `dump_response(resp, path)`, para a resposta que não sai de `raspar` (o 401 do NYT).
