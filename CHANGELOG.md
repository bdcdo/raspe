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
- Adicionada a pasta `examples/` com quatro scripts reproduzíveis (busca básica, múltiplas fontes, análise temporal e pipeline completo com tratamento de erro), um README com tempo e número de requisições de cada um e, em `examples/datasets/`, as tabelas que eles geraram numa execução real.
- Adicionados os notebooks `10_pipeline_completo.ipynb`, `11_multiplas_fontes.ipynb` e `12_analise_longitudinal.ipynb`, que reaproveitam as funções de `examples/` e explicam cada etapa.
- Adicionado o parâmetro `debug` aos raspadores da Presidência, do Senado, da Câmara, da CAPES, do CFM, da Folha,
  do IPEA e do NYT, que também passa pelas funções `raspe.<fonte>()`: `raspe.ipea(debug=False)`.

### Modificado
- A espera pedida pelo header `Retry-After` de um 429 passou a ter teto de 5 minutos, configurável no atributo
  `max_retry_after` dos raspadores HTTP.
- Os logs dos raspadores saem pelo logger `raspe.<FONTE>` (antes, `<FONTE>`), filho de `raspe`, que tem o handler de
  console, configurado uma vez na importação. `logging.getLogger("raspe").setLevel(logging.WARNING)` silencia o raspe
  inteiro. `raspador.logger` passou a ser um `logging.LoggerAdapter` com o nível da instância; o resto da API de
  `Logger` (`addHandler`, `handlers`...) vai para `raspe.<FONTE>`.
- Classe `IpeaScraper` renomeada para `ScraperIpea`, alinhando ao padrão
  `Scraper{Fonte}` adotado pelos demais raspadores. Alias
  `IpeaScraper = ScraperIpea` mantido em `raspe.scrapers.ipea` por
  retrocompatibilidade — código existente continua funcionando sem
  alteração. Factory `raspe.ipea()` segue inalterada.
- Adicionado `CAPES` ao mapping de `raspe.scraper_manager.scraper()`,
  permitindo `scraper("CAPES")` além de `raspe.capes()`.
- Requisito mínimo de Python elevado de 3.10 para 3.11. O 3.10 saiu de suporte em outubro de 2026.

### Descontinuado
- Descontinuado o parâmetro `download_path` de `ScraperIpea`, que sempre foi ignorado: agora emite
  `DeprecationWarning`. Para mudar a pasta dos arquivos baixados, atribua `raspador.download_path`.

### Removido
- Removido scraper CNJ (`comunicaCNJ`); migrado para `jtrecenti/juscraper`
  como agregador `comunica_cnj`. Quem dependia de `raspe.cnj()` deve usar
  `juscraper.scraper("comunica_cnj").listar_comunicacoes(...)`.

### Corrigido
- `BaseScraper._set_query_atual` agora copia o dicionário recebido em vez
  de mutar `query_base` in-place. Bug latente (não afetava o fluxo atual
  de `_download_data`), mas vira armadilha em refactors futuros
  (paralelização, cache, uso de `old_page_name`).
- Corrigida a busca sem resultados, que devolvia um `DataFrame` sem colunas: agora traz as colunas da fonte
  (listadas no novo atributo de classe `colunas` de cada raspador), mais `termo_busca`.
- Corrigido o nível de log de um raspador, que mudava ao criar outra instância da mesma fonte (valia o `debug` da
  última): agora cada instância tem o seu, e `raspador.logger.setLevel()` também só vale para ela.
- Corrigidas as mensagens de log repetidas ao criar mais de um raspador da mesma fonte: cada instância
  acrescentava mais um handler ao logger compartilhado.
- Corrigido `raspar()` devolvendo `DataFrame` vazio quando a requisição inicial esbarra em 429 ou 5xx
  persistentes: agora levanta `RateLimitError` ou `APIError`.
- Corrigidos os raspadores da Presidência, do Senado e da CAPES, que tratavam página de manutenção ou de
  verificação anti-robô como busca sem resultados: agora levantam `ScraperError`.
- Corrigidos os raspadores da Câmara, do IPEA, do CFM e da Folha, que tratavam página de manutenção ou de
  verificação anti-robô como busca sem resultados: agora levantam `ScraperError`. O NYT levanta `APIError` quando
  a resposta não traz a contagem de resultados.
- Corrigido `raspar()`, que pulava em silêncio as páginas com erro 5xx ou de rede e gravava respostas 429 como
  páginas de resultados, truncando a coleta: cada página agora passa pelas mesmas tentativas da requisição inicial
  e, se o erro persistir, a coleta para com `RateLimitError`, `APIError` ou o erro do `requests`. As tentativas
  passam a cobrir também falhas de conexão e timeout.
- Corrigido `raspar()` devolvendo resultado vazio quando nenhuma das páginas baixadas é lida (layout novo, página
  de bloqueio): agora levanta `ScraperError`. Se só parte das páginas não render linhas, emite `UserWarning`
  com os nomes dos arquivos.
- Corrigido o modo lista de `raspar()`, em que o erro num valor descartava os já coletados: o valor que falha
  fica de fora com `UserWarning`, e os demais voltam no resultado. Se todos falharem, o primeiro erro sobe. Depois
  de um `RateLimitError`, os valores seguintes não são tentados e entram no aviso.
- Corrigida a paginação da CAPES, que lia 20 itens por página do atributo `data-per-page` (o portal serve 30) e pedia
  páginas vazias no fim: o tamanho da página agora vem dos itens da própria página 1.
- Corrigido o timeout do CFM, cujo portal leva mais de um minuto para responder: o de leitura passou de 30 s para 120 s.
- Corrigida a pasta temporária que ficava para trás depois de `raspar()` bem-sucedido com `debug=False`: além da
  pasta da busca, saem a da fonte e a raiz criada pelo `mkdtemp()`. A raiz só é criada na primeira busca. Numa
  pasta escolhida pelo usuário (`raspador.download_path = ...`), só a pasta da busca sai, como antes.
- Corrigido o raspador do Senado, que sem navegador caía sempre na verificação anti-robô do site: agora resolve
  a prova de trabalho dessa verificação (a mesma conta que o navegador faz) e repete a busca.
- Corrigida a paginação da Câmara, que supunha 10 resultados por página (o portal exibe 20) e pedia páginas além
  da 500ª, que o portal não serve: buscas com mais de 10.000 resultados param na página 500, com aviso no log.
- Corrigida a contagem de resultados do Senado acima de 999, que o separador de milhar truncava ("8.950" virava 8).

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
