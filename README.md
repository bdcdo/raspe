# raspe - Raspadores para Pesquisas Acadêmicas 🔍📊

**Coleta automática de dados de fontes oficiais brasileiras para pesquisa empírica**

---

## 📖 Para quem é esta ferramenta?

O **raspe** foi desenvolvido para **pesquisadores** que precisam coletar grandes volumes de dados de fontes oficiais brasileiras, mas têm pouco ou nenhum conhecimento de programação.

**Exemplo prático:** Imagine que você precisa analisar todas as publicações sobre "políticas públicas" dos últimos anos. Fazer isso manualmente levaria semanas. Com o raspe, você consegue em minutos.

---

## 🎯 O que o raspe faz?

O raspe automatiza a coleta de dados de 11 fontes:

**Legislação federal**
- 🏛️ **Presidência da República** - Leis, decretos e legislação federal
- 📋 **Câmara dos Deputados** - Legislação federal na busca da Câmara
- 📜 **Senado Federal** - Legislação federal na busca do Senado

**Saúde**
- 🩺 **CFM** - Normas do Conselho Federal de Medicina e dos CRMs
- 💊 **SaudeLegis** - Normas sanitárias do Ministério da Saúde
- 🏥 **ANS** - Atos da Agência Nacional de Saúde Suplementar
- 🧪 **ANVISA** - Atos da Agência Nacional de Vigilância Sanitária

**Pesquisa acadêmica**
- 📊 **IPEA** - Estudos e pesquisas econômicas aplicadas
- 🎓 **CAPES** - Metadados acadêmicos do Portal de Periódicos

**Imprensa**
- 📰 **Folha de São Paulo** - Notícias e artigos do jornal brasileiro
- 🗽 **New York Times** - Artigos do jornal americano (requer API key gratuita)

**O resultado:** Todos os dados organizados em tabelas prontas para análise no Excel, Python, R ou qualquer ferramenta de sua preferência.

---

## 🚀 Instalação Passo a Passo

### Pré-requisitos

Você precisará ter o **Python** instalado no seu computador. Se ainda não tem:

1. **Windows/Mac:** Baixe em [python.org/downloads](https://www.python.org/downloads/) (versão 3.11 ou superior)
2. **Linux:** Geralmente já vem instalado. Se não, use: `sudo apt install python3 python3-pip`

### Instalando o raspe

Abra o terminal (no Windows, procure por "Prompt de Comando" ou "PowerShell") e digite:

```bash
pip install raspe
```

**Pronto!** O raspe está instalado e pronto para uso.

#### Versão de desenvolvimento

O comando acima instala a última versão publicada no [PyPI](https://pypi.org/project/raspe/). Para usar as mudanças que ainda não saíram numa versão, instale direto do GitHub:

```bash
pip install git+https://github.com/bdcdo/raspe.git
```

### 🎯 Compatibilidade com Google Colab

O RasPe é **totalmente compatível com Google Colab**! Você pode usar a ferramenta diretamente no navegador, sem precisar instalar Python no seu computador.

Para usar no Google Colab:

1. Acesse [colab.research.google.com](https://colab.research.google.com/)
2. Crie um novo notebook
3. Na primeira célula, instale o RasPe:
   ```python
   !pip install raspe
   ```
4. Execute a célula e comece a usar!

O Google Colab já vem com uma versão do Python compatível com o RasPe.

---

## 💻 Como Usar - Passo a Passo

### Exemplo 1: Buscar leis sobre "meio ambiente" na Presidência

```python
# 1. Importar a biblioteca
import raspe

# 2. Criar um raspador para a Presidência da República
presidencia = raspe.presidencia()

# 3. Buscar dados (isso pode levar alguns minutos)
dados = presidencia.raspar(pesquisa="meio ambiente")

# 4. Salvar os resultados em Excel
dados.to_excel("leis_meio_ambiente.xlsx", index=False)

# Pronto! Agora você tem um arquivo Excel com todos os resultados
```

### Exemplo 2: Buscar legislação federal sobre "educação" na Câmara

```python
import raspe

camara = raspe.camara()
dados = camara.raspar(pesquisa="educação")

# Salvar em Excel
dados.to_excel("camara_educacao.xlsx", index=False)
```

### Exemplo 3: Buscar múltiplos temas de uma vez

```python
import raspe

# Buscar três temas, um depois do outro
senado = raspe.senado()
dados = senado.raspar(pesquisa=["educação", "saúde", "segurança"])

# O resultado terá uma coluna 'termo_busca' identificando cada tema
dados.to_excel("senado_multiplos.xlsx", index=False)
```

### Exemplo 4: Limitar o número de páginas (para testes rápidos)

```python
import raspe

# Buscar apenas as primeiras 5 páginas (para testar rapidamente)
senado = raspe.senado()
dados = senado.raspar(pesquisa="reforma tributária", paginas=range(1, 6))

dados.to_excel("senado_teste.xlsx", index=False)
```

---

## 📊 Entendendo os Resultados

Após executar o código, você terá um **DataFrame** (uma tabela) com os dados coletados. Você pode:

- **Visualizar na tela:** `print(dados.head())` - mostra as primeiras linhas
- **Salvar em Excel:** `dados.to_excel("meus_dados.xlsx", index=False)`
- **Salvar em CSV:** `dados.to_csv("meus_dados.csv", index=False)`
- **Ver quantas linhas:** `print(len(dados))` - mostra o número total de registros
- **Ver as colunas:** `print(dados.columns)` - mostra quais informações foram coletadas

O que cada coluna significa, fonte por fonte, com tipo, descrição e exemplo, está em [`docs/colunas.md`](docs/colunas.md); as da Câmara e do Senado, na [seção dessas fontes](#presidência-câmara-senado-e-ipea). A busca sem resultado devolve uma tabela vazia com as mesmas colunas.

---

## 🎓 Tutorial Completo para Iniciantes

### Exemplos prontos

Para partir de um script que já funciona, a pasta [`examples/`](examples) traz quatro exemplos de uma pesquisa sobre doenças raras e judicialização de medicamentos, do mais simples ao mais completo: busca em uma fonte, a mesma busca em três fontes legislativas, série temporal da produção acadêmica e um pipeline com coleta, limpeza, análise e exportação. O [README da pasta](examples/README.md) diz quanto tempo cada um leva e quantas requisições faz, e `examples/datasets/` guarda as tabelas que eles geraram.

Três notebooks explicam esses exemplos célula por célula:

- [`10_pipeline_completo.ipynb`](notebooks/10_pipeline_completo.ipynb): coleta, limpeza, análise e exportação, com tratamento de erro;
- [`11_multiplas_fontes.ipynb`](notebooks/11_multiplas_fontes.ipynb): a mesma busca na Presidência, na Câmara e no Senado, comparadas;
- [`12_analise_longitudinal.ipynb`](notebooks/12_analise_longitudinal.ipynb): a produção acadêmica sobre judicialização de medicamentos ano a ano.

Há também um notebook por fonte, de [`01_presidencia.ipynb`](notebooks/01_presidencia.ipynb) a [`09_saudelegis.ipynb`](notebooks/09_saudelegis.ipynb), mais [`13_anvisa.ipynb`](notebooks/13_anvisa.ipynb), para dez das 11 fontes (a ANS ainda não tem).

### Passo 1: Criar um arquivo Python

1. Abra um editor de texto (pode ser o Bloco de Notas, mas recomendo o [Visual Studio Code](https://code.visualstudio.com/))
2. Crie um novo arquivo chamado `minha_pesquisa.py`
3. Cole um dos exemplos acima
4. Salve o arquivo

### Passo 2: Executar o código

1. Abra o terminal na pasta onde salvou o arquivo
2. Digite: `python minha_pesquisa.py`
3. Aguarde a coleta (pode levar de alguns minutos a horas, dependendo da busca)
4. O arquivo Excel aparecerá na mesma pasta

### Passo 3: Analisar os dados

Abra o arquivo Excel gerado e analise os dados com as ferramentas que você já conhece!

---

## 🔧 Fontes Disponíveis e Como Usar

Todas as fontes seguem o mesmo padrão: crie o raspador e chame `.raspar(pesquisa=...)`. O que cada coluna do resultado significa está em [`docs/colunas.md`](docs/colunas.md).

| Fonte | Comando | O que busca |
|-------|---------|-------------|
| Presidência | `raspe.presidencia()` | Leis, decretos e legislação federal |
| Câmara | `raspe.camara()` | Legislação federal na busca da Câmara |
| Senado | `raspe.senado()` | Legislação federal na busca do Senado |
| IPEA | `raspe.ipea()` | Publicações e estudos do IPEA |
| CFM | `raspe.cfm()` | Normas do Conselho Federal de Medicina e dos CRMs |
| Folha | `raspe.folha()` | Notícias da Folha de São Paulo |
| CAPES | `raspe.capes()` | Metadados de artigos do Portal de Periódicos da CAPES |
| NYT | `raspe.nyt(api_key="...")` | Artigos do New York Times (requer API key) |
| **SaudeLegis** | `raspe.saudelegis()` | Normas do Ministério da Saúde (requer browser) |
| **ANS** | `raspe.ans()` | Atos da Agência Nacional de Saúde (requer browser) |
| **ANVISA** | `raspe.anvisa()` | Atos da Agência de Vigilância Sanitária (requer browser) |

**Paginação e vários termos.** Os oito raspadores HTTP aceitam `paginas`, um `range` com as páginas a coletar (ex.: `paginas=range(1, 6)`), e uma **lista** em `pesquisa`: o raspador faz uma busca por termo e junta os resultados, e a coluna `termo_busca` diz de qual busca veio cada linha. SaudeLegis, ANS e ANVISA recusam os dois: coletam todas as páginas até um limite interno e recebem um termo por chamada.

### Escolhendo a fonte pelo nome

Se o nome da fonte vier de uma variável (de um arquivo de configuração, de um laço), use `raspe.scraper_manager.scraper()`:

```python
from raspe.scraper_manager import scraper

resultados = {}
for fonte in ["presidencia", "cfm", "capes"]:
    resultados[fonte] = scraper(fonte).raspar(pesquisa="doença rara", paginas=range(1, 2))
```

O nome é o da factory (`"cfm"` para `raspe.cfm()`) e não diferencia maiúsculas de minúsculas. Parâmetros do construtor são repassados ao raspador, como em `scraper("nyt", api_key="...")` e `scraper("ans", headless=False)`.

### Presidência, Câmara, Senado e IPEA

```python
import raspe

df = raspe.presidencia().raspar(pesquisa="meio ambiente")
df = raspe.camara().raspar(pesquisa="educação")
df = raspe.senado().raspar(pesquisa="reforma tributária")
df = raspe.ipea().raspar(pesquisa="desigualdade")
```

A Câmara e o Senado aceitam `ano`. A Câmara aceita também `tipo_materia`, com o tipo de norma escrito como no site da Câmara (ex.: `"Lei Ordinária"`):

```python
df = raspe.camara().raspar(pesquisa="saúde", ano=2023, tipo_materia="Lei Ordinária")
df = raspe.senado().raspar(pesquisa="saúde", ano=2023)
```

A Câmara e o Senado ainda não têm schema de saída, então as colunas deles ficam aqui, e não em `docs/colunas.md`. Os exemplos saem de uma busca real por "doenças raras" em 15/11/2026.

Colunas de `raspe.camara()`:

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `link` | texto | Endereço da norma no portal da Câmara. | https://www2.camara.leg.br/legin/fed/decret/1910-1919/decreto-8332-3-novembro-1910-498462-norma-pe.html |
| `titulo` | texto | Tipo, número e data da norma. | Decreto nº 8.332, de 3 de Novembro de 1910 |
| `descricao` | texto | Ementa da norma, precedida de `Ementa: `, como o site a mostra, inclusive com espaços repetidos no meio do texto. | Ementa: Approva o Codigo do Processo Civil e Commercial do Distrito Federal |
| `ementa` | texto | Apesar do nome, a situação da norma, precedida de `Situação:`, de uma quebra de linha e de espaços, como o site a mostra. A ementa está em `descricao`. | `'Situação:\n' + ' ' * 40 + 'Revogada'` |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. Sem `pesquisa`, a coluna não aparece. | doenças raras |

Colunas de `raspe.senado()`:

| Coluna | Tipo | Descrição | Exemplo |
| --- | --- | --- | --- |
| `titulo` | texto | Tipo, número e data da norma, com a versão do texto entre parênteses. | Decreto nº 10.558 de 03/12/2020 (Publicação Original) |
| `link_norma` | texto | Endereço do texto da norma nessa versão. | https://legis.senado.leg.br/norma/32956034/publicacao/32957954 |
| `link_detalhes` | texto | Endereço da ficha da norma, ou o texto `NA` quando o resultado traz um link só. | https://legis.senado.leg.br/norma/32956034 |
| `descricao` | texto | Ementa da norma. | Institui o Comitê Interministerial de Doenças Raras. |
| `trecho_descricao` | texto | Data da norma, ` - `, uma quebra de linha e o trecho do texto em que a busca achou o termo. | `'03/12/2020 - \nInstitui o Comitê Interministerial de Doenças Raras. ... DECRETA: Art. 1º Fica  instituído o Comitê Interministerial de Doenças Raras no âmbito do Ministério  da Mulher, da Família e dos Direitos Humanos. Art. ...'` |
| `termo_busca` | texto | Termo de busca que gerou a linha: o valor de `pesquisa` ou, numa busca com lista, o item da lista. Sem `pesquisa`, a coluna não aparece. | doenças raras |

### CAPES (Portal de Periódicos)

```python
import raspe

df = raspe.capes().raspar(pesquisa="natjus")
df.to_excel("artigos_capes.xlsx", index=False)
```

### CFM (Conselho Federal de Medicina)

Normas do CFM e dos Conselhos Regionais de Medicina (CRMs): resoluções, pareceres, emendas, normas e decisões.

```python
import raspe

df = raspe.cfm().raspar(pesquisa="doença rara", uf="SP")
df.to_excel("normas_cfm.xlsx", index=False)
```

Além de `pesquisa`, o CFM aceita `uf` (UF do CRM; vazio busca em todos), `revogada`, `numero` e `ano`.

---

## 🌐 Raspadores com Navegador (ANS, ANVISA, SaudeLegis)

Algumas fontes possuem proteção anti-bot (Cloudflare) e requerem automação de navegador. Para usar esses raspadores, instale as dependências extras:

### Instalação

```bash
# Instalar o raspe com suporte a navegador
pip install "raspe[browser]"

# Instalar o navegador Chromium (necessário apenas uma vez)
python -m playwright install chromium
```

Para a versão de desenvolvimento com suporte a navegador, troque o primeiro comando por `pip install "raspe[browser] @ git+https://github.com/bdcdo/raspe.git"`.

### Exemplo: ANS (Agência Nacional de Saúde Suplementar)

```python
import raspe

# Buscar atos normativos sobre doenças raras
df = raspe.ans().raspar(pesquisa="doença rara")
df.to_excel("atos_ans.xlsx", index=False)
```

### Exemplo: ANVISA (Agência de Vigilância Sanitária)

```python
import raspe

# Buscar atos normativos sobre medicamentos
df = raspe.anvisa().raspar(pesquisa="medicamento órfão")
df.to_excel("atos_anvisa.xlsx", index=False)
```

### Exemplo: SaudeLegis (Ministério da Saúde)

```python
import raspe

# Buscar normas sanitárias
df = raspe.saudelegis().raspar(pesquisa="doença rara")
df.to_excel("normas_saude.xlsx", index=False)
```

### Dados retornados (ANS/ANVISA)

As colunas estão em [`docs/colunas.md`](docs/colunas.md#raspeans-e-raspeanvisa).

### Modo visual (debug)

Se precisar visualizar o navegador durante a coleta (útil para debug):

```python
# Executa com navegador visível
df = raspe.ans(headless=False).raspar(pesquisa="doença rara")
```

---

## 📰 Folha de São Paulo

O raspador da Folha de São Paulo permite buscar notícias por termo de pesquisa, filtrar por tipo de conteúdo e período.

### Exemplo de uso

```python
import raspe

# Criar raspador
folha = raspe.folha()

# Busca simples
dados = folha.raspar(pesquisa="educação")

# Busca com filtros
dados = folha.raspar(
    pesquisa="reforma tributária",
    site="online",  # 'todos', 'online' ou 'jornal'
    data_inicio="2024-01-01",
    data_fim="2024-12-31"
)

# Salvar resultados
dados.to_excel("noticias_folha.xlsx", index=False)
```

### Parâmetros disponíveis

| Parâmetro | Descrição | Valores |
|-----------|-----------|---------|
| `pesquisa` | Termo de busca | Texto livre |
| `site` | Tipo de conteúdo | `'todos'` (padrão), `'online'`, `'jornal'` |
| `data_inicio` | Data inicial | `YYYY-MM-DD`, `DD/MM/YYYY` ou `YYYYMMDD` |
| `data_fim` | Data final | `YYYY-MM-DD`, `DD/MM/YYYY` ou `YYYYMMDD` |

### Dados retornados

As colunas estão em [`docs/colunas.md`](docs/colunas.md#raspefolha).

---

## 🗽 New York Times (NYT)

O raspador do New York Times utiliza a **API oficial** do jornal, que requer uma chave de acesso gratuita.

### Obtendo sua API Key

1. Acesse [developer.nytimes.com/get-started](https://developer.nytimes.com/get-started)
2. Crie uma conta gratuita
3. Crie um novo "App" e ative a "Article Search API"
4. Copie sua API key

### Exemplo de uso

```python
import raspe

# Criar raspador com sua API key
nyt = raspe.nyt(api_key="sua-api-key-aqui")

# Busca simples
dados = nyt.raspar(pesquisa="climate change", ano=2024)

# Busca com intervalo de datas
dados = nyt.raspar(
    pesquisa="Brazil",
    data_inicio="2024-01-01",
    data_fim="2024-06-30"
)

# Busca com filtros avançados (seção específica)
dados = nyt.raspar(
    pesquisa="election",
    ano=2024,
    filtro='section.name:"Politics"'
)

# Salvar resultados
dados.to_excel("artigos_nyt.xlsx", index=False)
```

### Limites da API

- **10 resultados por página**, máximo de **1000 resultados** por busca
- **Rate limit**: 5 requisições por minuto, 500 por dia
- Se precisar de mais resultados, divida sua busca por intervalos de datas

---

## 🛡️ Robustez e Validações

### Retry Automático

O raspe tenta novamente automaticamente quando encontra problemas temporários de conexão ou quando o servidor está sobrecarregado. Você não precisa fazer nada - é tudo automático.

### Parâmetros conferidos

O raspe confere os parâmetros de `raspar()` antes de qualquer requisição. Um nome que o raspador não conhece, como `data_incio`, levanta erro com a lista dos parâmetros aceitos e, quando houver, a sugestão do nome certo; um valor de tipo errado também. Os nomes antigos do termo de busca (`texto`, `termo` e `assunto`) ainda funcionam, com aviso de descontinuação: use `pesquisa`.

### Formatos de Data Aceitos

Quando usar datas (como `data_inicio` e `data_fim`), você pode usar qualquer um destes formatos:
- `2024-01-15` (ano-mês-dia)
- `15/01/2024` (dia/mês/ano)
- `20240115` (sem separadores)

---

## ❓ Perguntas Frequentes

### "Não sei programar em Python. Consigo usar?"

**Sim!** Os exemplos acima são tudo que você precisa. Basta copiar, colar e mudar o termo de busca.

### "Quanto tempo leva para coletar os dados?"

Depende da busca. Termos genéricos podem ter milhares de resultados e levar horas. Comece testando com `paginas=range(1, 6)` para ver uma amostra rápida (SaudeLegis, ANS e ANVISA não aceitam `paginas`).

### "Os dados vêm em que formato?"

Em tabelas (DataFrames do Pandas), que você pode exportar para Excel, CSV, ou qualquer formato que precise.

### "Preciso de internet durante a coleta?"

Sim. O raspe acessa os sites oficiais para coletar os dados em tempo real.

### "É legal usar isso?"

Sim! Todos os dados coletados são públicos e disponibilizados pelos próprios órgãos oficiais. O raspe apenas automatiza o que você faria manualmente.

### "E se der erro?"

Os erros mais comuns são:
- **"ModuleNotFoundError"**: O raspe não foi instalado corretamente. Reinstale com `pip install raspe`
- **"Timeout"**: O site demorou para responder. Tente novamente mais tarde.
- **"No results found"**: Não há resultados para sua busca. Tente outros termos.

---

## ⚖️ Precisa raspar dados de Tribunais ou comunicados do CNJ?

O raspe não possui raspadores para tribunais estaduais e federais nem para comunicações processuais do CNJ. Para isso, recomendamos o **[juscraper](https://github.com/jtrecenti/juscraper)**, um projeto Python mantido por [Julio Trecenti](https://github.com/jtrecenti) especializado em raspagem de dados do sistema judiciário brasileiro. As comunicações processuais do CNJ (antigo `raspe.cnj()`) agora vivem lá como o agregador `comunica_cnj`.

---

## 🤝 Contribuindo

Encontrou um bug? Tem uma sugestão? Abra uma [issue no GitHub](https://github.com/bdcdo/raspe/issues) ou envie um email.

---

## 📄 Licença

Este projeto é de código aberto sob a Licença MIT. Isso significa que você pode usar livremente em sua pesquisa, inclusive em publicações.

---

## 📧 Contato

**Bruno da Cunha de Oliveira**
Email: bruno.dcdo@gmail.com
GitHub: [github.com/bdcdo/raspe](https://github.com/bdcdo/raspe)

---

## 📖 Citando o raspe em sua Pesquisa

Se você usar o raspe em artigos, dissertações ou teses, considere citá-lo:

```bibtex
@software{raspe2025,
  author = {Oliveira, Bruno da Cunha de},
  title = {raspe: Raspadores para Pesquisas Acadêmicas},
  year = {2025},
  url = {https://github.com/bdcdo/raspe}
}
```

**Formato ABNT:**
```
OLIVEIRA, Bruno da Cunha de. raspe: Raspadores para Pesquisas Acadêmicas. 2025.
Disponível em: https://github.com/bdcdo/raspe. Acesso em: [data].
```
