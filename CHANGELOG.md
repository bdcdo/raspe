# Changelog

Todas as mudanças relevantes neste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado
- Scraper para o Portal de Periódicos da CAPES (`raspe.capes()`).
  Coleta metadados de artigos, livros e capítulos a partir do
  buscador público (`www.periodicos.capes.gov.br/index.php/acervo/buscador.html`),
  com 15 colunas por registro (id OpenAlex, tipo, título, autores,
  ano, revista, instituição, tópicos, resumo, DOI, link editor e
  flags de acesso aberto / produção nacional / revisado por pares).
  Acompanha contratos offline em `tests/capes/` com samples
  capturados do site real (`natjus`, `saude`, busca sem resultados) e
  script de captura em `tests/fixtures/capture/capes.py`.
- Notebook exemplificativo `notebooks/05_capes.ipynb` para o scraper
  da CAPES, seguindo o padrão dos demais notebooks de demonstração.
- Cobertura de testes ≥80% em todos os módulos não-Playwright, com
  contratos offline (`responses` + samples versionados) para os 11
  scrapers e testes unitários para `base_scraper`, `abstract_scraper`,
  `utils`, `exceptions` e `scraper_manager`. Gate
  `[tool.coverage.report] fail_under = 80` ativo: a suíte agora falha se
  a cobertura cair abaixo da meta. `playwright_scraper.py` foi excluído
  do denominador (testá-lo offline exigiria mockar a API async inteira
  do Playwright).
- Schemas pydantic de entrada e saída em `raspe.schemas` para presidencia, ipea, capes, cfm, folha, nyt, saudelegis, ans e anvisa. O de entrada descreve os parâmetros de `raspar()`; o de saída, as colunas do DataFrame. Cada raspador aponta para os seus em `schema_entrada` e `schema_saida`. Câmara e Senado ficam sem schema até a reescrita sobre as APIs oficiais.
- `docs/colunas.md`, gerado dos schemas de saída por `python -m raspe.schemas.documentacao`, com coluna, tipo, descrição e exemplo de cada fonte.
- Dependência `pydantic>=2`.

### Modificado
- Classe `IpeaScraper` renomeada para `ScraperIpea`, alinhando ao padrão
  `Scraper{Fonte}` adotado pelos demais raspadores. Alias
  `IpeaScraper = ScraperIpea` mantido em `raspe.scrapers.ipea` por
  retrocompatibilidade — código existente continua funcionando sem
  alteração. Factory `raspe.ipea()` segue inalterada.
- Adicionado `CAPES` ao mapping de `raspe.scraper_manager.scraper()`,
  permitindo `scraper("CAPES")` além de `raspe.capes()`.
- Requisito mínimo de Python elevado de 3.10 para 3.11. O 3.10 saiu de suporte em outubro de 2026.
- **Incompatível:** o termo de busca passou a se chamar `pesquisa` em todos os raspadores com schema. Os nomes antigos continuam aceitos, com `DeprecationWarning`, e serão removidos: `texto` em `cfm()` e `nyt()`, `assunto` em `saudelegis()` e `termo` em `ans()` e `anvisa()`. Passar o nome antigo e `pesquisa` juntos levanta `ValidationError`.
- **Incompatível:** as colunas do `cfm()` foram renomeadas para snake_case ASCII: `Tipo` para `tipo`, `UF` para `uf`, `Nº/Ano` para `numero_ano`, `Situação` para `situacao`, `Ementa` para `ementa` e `Link` para `link`.
- **Incompatível:** `raspar()` levanta `ValidationError`, com a lista dos parâmetros aceitos e a sugestão do nome mais parecido, quando recebe parâmetro desconhecido. Antes o parâmetro era ignorado em silêncio, e um erro de digitação como `data_incio` virava uma busca sem filtro.
- **Incompatível:** `pesquisa` passou a ser obrigatória em `presidencia()`, `ipea()`, `capes()` e `folha()`. Em `cfm()` e `nyt()` continua opcional, porque esses portais aceitam busca só por filtro.
- **Incompatível:** `saudelegis()`, `ans()` e `anvisa()` recusam `paginas` e lista em `pesquisa`, que antes eram ignorados em silêncio.
- **Incompatível:** `paginas` precisa ser um `range` crescente, não vazio e começando em 1.
- **Incompatível:** `sort` do `nyt()` aceita só `newest`, `oldest`, `relevance` e `best`, os valores da Article Search API.
- `cfm()` e `nyt()` passaram a devolver a coluna `termo_busca`, como os demais raspadores.
- A busca sem resultado devolve um DataFrame vazio com as colunas do schema, em vez de um DataFrame sem colunas ou só com `termo_busca`.

### Removido
- Removido scraper CNJ (`comunicaCNJ`); migrado para `jtrecenti/juscraper`
  como agregador `comunica_cnj`. Quem dependia de `raspe.cnj()` deve usar
  `juscraper.scraper("comunica_cnj").listar_comunicacoes(...)`.

### Corrigido
- `BaseScraper._set_query_atual` agora copia o dicionário recebido em vez
  de mutar `query_base` in-place. Bug latente (não afetava o fluxo atual
  de `_download_data`), mas vira armadilha em refactors futuros
  (paralelização, cache, uso de `old_page_name`).

## [0.1.0] - 2025-05-15

### Adicionado
- Scrapers iniciais: Presidência da República, Câmara dos Deputados,
  Senado Federal, CNJ (comunicaCNJ) e IPEA.
- Scraper CFM (Conselho Federal de Medicina) para normas médicas.
- Scraper Folha de São Paulo, com filtros por tipo de site e período,
  e aviso quando a busca atinge o limite de 10.000 resultados.
- Scraper New York Times usando a Article Search API oficial (requer
  API key), com validação antecipada de chave.
- Scrapers via Playwright para fontes com proteção anti-bot:
  SaudeLegis (Ministério da Saúde), ANS e ANVISA (Datalegis).
- Hierarquia de exceções customizadas a partir de `ScraperError`
  (`APIError`, `APIKeyError`, `BrowserError`,
  `DriverNotInstalledError`, `RateLimitError`, `ValidationError`).
- Notebooks de exemplo para cada raspador, com outputs.
- Configuração de pre-commit (trailing whitespace, isort, pylint,
  flake8, mypy, pyright) seguindo o padrão do `juscraper`.
- Suporte a `pytest-cov` e arquivo `LICENSE` (MIT).

### Modificado
- Projeto renomeado de `braScraper` para `RasPe` / `raspe`; URLs
  padronizadas em minúsculas.
- Método principal renomeado de `scrape()` para `raspar()`
  (mantido alias `scrape()` por retrocompatibilidade).
- Automação de navegador migrada de Selenium para Playwright
  (alias `SeleniumError` mantido).
- Requisito mínimo de Python reduzido de 3.11 para 3.10
  (compatibilidade com Google Colab).
- Scraper NYT refatorado para usar a API oficial.

### Corrigido
- Erro de SSL no scraper da Presidência.
- Paginação dos scrapers Datalegis (ANS/ANVISA).
- Compatibilidade com a nova API do NYT.

[Não lançado]: https://github.com/bdcdo/raspe/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/bdcdo/raspe/releases/tag/v0.1.0
