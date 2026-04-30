# Changelog

Todas as mudanças relevantes neste projeto serão documentadas aqui.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

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
