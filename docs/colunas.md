# Colunas devolvidas por `raspar()`

<!-- Gerado por `python -m raspe.schemas.documentacao` a partir dos schemas de saída em `src/raspe/schemas/`. Não editar à mão. -->

Cada raspador devolve um `pandas.DataFrame` com exatamente estas colunas, nesta ordem, inclusive quando a busca não tem resultado. A coluna `termo_busca` repete o termo pesquisado, o que permite empilhar buscas diferentes num mesmo DataFrame. Os exemplos saem das amostras usadas nos testes do pacote.

## `raspe.ans()` e `raspe.anvisa()`

Schema: `OutputDatalegis`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `url` | texto | Endereço do texto do ato, no domínio do portal do órgão. | https://anslegis.datalegis.net/acao/abrirTextoAto.php?id=12345 |
| `titulo` | texto | Tipo e número do ato. | RESOLUÇÃO NORMATIVA Nº 500/2024 |
| `descricao` | texto ou nulo | Ementa do ato, ou nulo quando o portal não a traz. | Define diretrizes para cobertura de doenças raras. |
| `situacao` | texto ou nulo | Situação do ato (vigente, revogado etc.), ou nulo quando o portal não a traz. | Em vigor |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.capes()`

Schema: `OutputCapes`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `id` | texto | Identificador do registro, o mesmo do OpenAlex. | W4387465478 |
| `tipo` | texto | Tipo do registro. | Artigo |
| `titulo` | texto | Título do registro. | Judicialização de produtos à base de canabidiol no Brasil: uma análise de 2019 a 2022 |
| `link` | texto | Endereço da página de detalhes no portal da CAPES. | https://www.periodicos.capes.gov.br/index.php/acervo/buscador.html?task=detalhes&source=all&id=W4387465478 |
| `autores` | texto | Autores separados por `; `. | João Paulo Kulczynski Forster; Najwa Dagash; Paula Franciele Da Silva |
| `ano` | texto | Ano de publicação, com quatro dígitos, ou vazio. | 2023 |
| `revista` | texto | Periódico em que o registro saiu. | Cadernos de Saúde Pública |
| `instituicao` | texto | Instituição informada no card. | Escola Nacional de Saúde Pública, Fundação Oswaldo Cruz |
| `topicos` | texto | Tópico de pesquisa atribuído ao registro. | Cannabis and Cannabinoid Research |
| `resumo` | texto | Trechos do resumo que o buscador destaca, não o resumo inteiro. | ... the Center for Technical Support of the Judiciary ( NatJus ), which supports judicial decisions. |
| `doi` | texto | DOI, sem o prefixo `https://doi.org/`. | 10.1590/0102-311xpt024723 |
| `link_editor` | texto | Endereço do DOI na editora. | https://doi.org/10.1590/0102-311xpt024723 |
| `acesso_aberto` | booleano | O card traz o selo de acesso aberto. | True |
| `producao_nacional` | booleano | O card traz o selo de produção nacional. | True |
| `revisado_por_pares` | booleano | O card traz o selo de revisão por pares. | True |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.cfm()`

Schema: `OutputCFM`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `tipo` | texto | Tipo da norma (Resolução, Parecer, Emenda, Norma ou Decisão). | Resolução |
| `uf` | texto | UF do conselho que emitiu a norma. | DF |
| `numero_ano` | texto | Número e ano da norma, como `número/ano`. | 2350/2023 |
| `situacao` | texto | Situação da norma. | Em vigor |
| `ementa` | texto | Ementa da norma. | Define diretrizes para atendimento de doenças raras no SUS. |
| `link` | texto | Endereço do texto da norma, como o portal o devolve. | /normas/2350-2023.pdf |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.folha()`

Schema: `OutputFolha`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `link` | texto | Endereço da notícia. | https://www1.folha.uol.com.br/cotidiano/2024/01/noticia-1.shtml |
| `titulo` | texto | Título da notícia. | Educação pública avança em 2024 |
| `resumo` | texto | Resumo que a busca mostra abaixo do título. | Pesquisa mostra ampliação de vagas no ensino médio em todo o país. |
| `data` | texto | Data e hora de publicação, como a busca as mostra. | 15.jan.2024 às 10h00 |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.ipea()`

Schema: `OutputIpea`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `titulo` | texto | Título da publicação. | Texto para Discussão 2900 |
| `link` | texto | Endereço da publicação no portal do IPEA. | https://www.ipea.gov.br/portal/publicacao-1.html |
| `autores` | texto | Autores, como o portal os lista. | João da Silva; Maria Souza |
| `data` | texto | Data de publicação por extenso. | 15 de janeiro de 2024 |
| `assuntos` | texto | Assuntos, separados por vírgula. | Economia, Pobreza |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.nyt()`

Schema: `OutputNYT`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `titulo` | texto | Manchete principal. | Supreme Court Ruling on Climate Policy |
| `url` | texto | Endereço do artigo. | https://www.nytimes.com/2024/01/15/climate-ruling.html |
| `data_publicacao` | texto | Data e hora de publicação, em ISO 8601, como a API devolve. | 2024-01-15T14:00:00+0000 |
| `secao` | texto | Seção do jornal. | U.S. |
| `desk` | texto | Editoria responsável. | National |
| `tipo` | texto | Tipo de material. | News |
| `resumo` | texto | Trecho do artigo que a API devolve (`snippet`). | The court ruled 6-3 in favor of new climate regulations. |
| `autor` | texto | Assinatura do artigo. | By Jane Doe |
| `palavras` | inteiro | Número de palavras do artigo. | 1200 |
| `imagem_url` | texto | Endereço da imagem principal, ou vazio sem imagem. | https://www.nytimes.com/images/2024/01/15/climate.jpg |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.presidencia()`

Schema: `OutputPresidencia`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `nome` | texto | Nome do ato, com tipo, número e ano. | Decreto nº 11.000/2024 |
| `link` | texto | Endereço do texto do ato, como o portal o devolve. | /atos/decreto-11000-2024.html |
| `ficha` | texto | Endereço da ficha do ato no portal. | /fichas/decreto-11000-2024.html |
| `revogacao` | texto | Situação de revogação informada pelo portal. | Sem revogação |
| `descricao` | texto | Ementa do ato. | Dispõe sobre política ambiental nacional. |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## `raspe.saudelegis()`

Schema: `OutputSaudeLegis`.

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `tipo_norma` | texto | Tipo da norma. | PORTARIA |
| `numero` | texto | Número e ano da norma. | 123/2024 |
| `data_pub` | texto | Data de publicação, em DD/MM/AAAA. | 15/01/2024 |
| `origem` | texto | Órgão de origem. | MS/GM |
| `ementa` | texto | Ementa da norma. | Define diretrizes para atendimento de doenças raras. |
| `link_url` | texto | Endereço do texto completo, ou vazio quando o portal não o traz. | /doc/portaria-123-2024.pdf |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. | natjus |

## Raspadores ainda sem schema de saída

`raspe.camara()`, `raspe.senado()`. As colunas deles estão no README.
