# raspe - Raspadores para Pesquisas Acadêmicas 🔍📊

**Coleta automática de dados de fontes oficiais brasileiras para pesquisa empírica**

---

## 📖 Para quem é esta ferramenta?

O **raspe** foi desenvolvido para **pesquisadores** que precisam coletar grandes volumes de dados de fontes oficiais brasileiras, mas têm pouco ou nenhum conhecimento de programação.

**Exemplo prático:** Imagine que você precisa analisar todas as publicações sobre "políticas públicas" dos últimos anos. Fazer isso manualmente levaria semanas. Com o raspe, você consegue em minutos.

---

## 🎯 O que o raspe faz?

O raspe automatiza a coleta de dados de **11 fontes** brasileiras e internacionais:

**Legislação e atividade parlamentar**

- 🏛️ **Presidência da República** - Leis, decretos e legislação federal
- 📋 **Câmara dos Deputados** - Legislação federal indexada pela Câmara
- 📜 **Senado Federal** - Legislação federal indexada pelo Senado

**Saúde e regulação sanitária**

- 🩺 **CFM** - Normas do Conselho Federal de Medicina e dos CRMs
- 💊 **SaudeLegis** - Normas e legislação sanitária do Ministério da Saúde
- 🏥 **ANS** - Atos normativos da Agência Nacional de Saúde Suplementar
- 🧪 **ANVISA** - Atos normativos da Agência Nacional de Vigilância Sanitária

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
pip install git+https://github.com/bdcdo/raspe.git
```

**Pronto!** O raspe está instalado e pronto para uso.

### 🎯 Compatibilidade com Google Colab

O RasPe é **totalmente compatível com Google Colab**! Você pode usar a ferramenta diretamente no navegador, sem precisar instalar Python no seu computador.

Para usar no Google Colab:

1. Acesse [colab.research.google.com](https://colab.research.google.com/)
2. Crie um novo notebook
3. Na primeira célula, instale o RasPe:
   ```python
   !pip install git+https://github.com/bdcdo/raspe.git
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

# Buscar três temas numa chamada só (vale para os raspadores HTTP)
presidencia = raspe.presidencia()
dados = presidencia.raspar(pesquisa=["educação", "saúde", "segurança"])

# O resultado terá uma coluna 'termo_busca' identificando cada tema
dados.to_excel("presidencia_varios_temas.xlsx", index=False)
```

### Exemplo 4: Limitar o número de páginas (para testes rápidos)

```python
import raspe

# Buscar apenas as primeiras 5 páginas (vale para os raspadores HTTP)
presidencia = raspe.presidencia()
dados = presidencia.raspar(pesquisa="reforma tributária", paginas=range(1, 6))

dados.to_excel("presidencia_teste.xlsx", index=False)
```

---

## 📊 Entendendo os Resultados

Após executar o código, você terá um **DataFrame** (uma tabela) com os dados coletados. Você pode:

- **Visualizar na tela:** `print(dados.head())` - mostra as primeiras linhas
- **Salvar em Excel:** `dados.to_excel("meus_dados.xlsx", index=False)`
- **Salvar em CSV:** `dados.to_csv("meus_dados.csv", index=False)`
- **Ver quantas linhas:** `print(len(dados))` - mostra o número total de registros
- **Ver as colunas:** `print(dados.columns)` - mostra quais informações foram coletadas

---

## 🎓 Tutorial Completo para Iniciantes

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

### 📓 Notebooks de exemplo

A pasta [`notebooks/`](notebooks) traz cadernos com exemplos passo a passo para nove das 11 fontes. ANS e ANVISA ainda não têm caderno; os exemplos delas estão na seção dos raspadores com navegador, mais abaixo.

| Notebook | Fonte |
|----------|-------|
| `01_presidencia.ipynb` | Presidência da República |
| `02_camara.ipynb` | Câmara dos Deputados |
| `03_senado.ipynb` | Senado Federal |
| `04_ipea.ipynb` | IPEA |
| `05_capes.ipynb` | CAPES |
| `06_cfm.ipynb` | CFM |
| `07_folha.ipynb` | Folha de São Paulo |
| `08_nyt.ipynb` | New York Times |
| `09_saudelegis.ipynb` | SaudeLegis |

---

## 🔧 Fontes Disponíveis e Como Usar

Esta é a lista completa dos raspadores disponíveis. Todos seguem o mesmo padrão:
crie o raspador e chame `.raspar()` com o termo de busca.

### Raspadores HTTP (não exigem instalação extra)

| Fonte | Comando | O que busca | Termo de busca |
|-------|---------|-------------|----------------|
| Presidência da República | `raspe.presidencia()` | Leis, decretos e legislação federal | `pesquisa=` |
| Câmara dos Deputados | `raspe.camara()` | Legislação federal na busca da Câmara | `pesquisa=` |
| Senado Federal | `raspe.senado()` | Legislação federal na busca do Senado | `pesquisa=` |
| IPEA | `raspe.ipea()` | Publicações e estudos do IPEA | `pesquisa=` |
| CAPES | `raspe.capes()` | Metadados de artigos do Portal de Periódicos | `pesquisa=` |
| CFM | `raspe.cfm()` | Normas do Conselho Federal de Medicina e dos CRMs | `texto=` |
| Folha de São Paulo | `raspe.folha()` | Notícias da Folha de São Paulo | `pesquisa=` |
| New York Times | `raspe.nyt(api_key="...")` | Artigos do NYT (requer API key gratuita) | `texto=` |

### Raspadores com navegador (exigem o extra `browser` e o Chromium)

| Fonte | Comando | O que busca | Termo de busca |
|-------|---------|-------------|----------------|
| SaudeLegis | `raspe.saudelegis()` | Normas sanitárias do Ministério da Saúde | `assunto=` |
| ANS | `raspe.ans()` | Atos da Agência Nacional de Saúde Suplementar | `termo=` |
| ANVISA | `raspe.anvisa()` | Atos da Agência Nacional de Vigilância Sanitária | `termo=` |

Os comandos de instalação do extra `browser` e do Chromium estão na seção dos raspadores com navegador, mais abaixo.

> ⚠️ **Atenção ao nome do parâmetro:** ele muda conforme a fonte (`pesquisa`,
> `texto`, `termo` ou `assunto`). Consulte a coluna "Termo de busca" acima ou a
> seção específica de cada fonte mais abaixo.

**Paginação e vários termos.** Os oito raspadores HTTP aceitam o parâmetro `paginas`, um `range` com as páginas a coletar (ex.: `paginas=range(1, 6)`), e aceitam uma **lista** de termos no lugar de um único texto. Com lista, o raspador faz uma busca para cada termo e junta os resultados, e a coluna `termo_busca` diz de qual busca veio cada linha.

Enquanto a [issue #43](https://github.com/bdcdo/raspe/issues/43) estiver aberta, a busca por lista pode parar com `FileExistsError` quando um termo que não é o último volta sem resultado: a busca do termo seguinte tenta criar a pasta de download com o mesmo nome. Para contornar, faça uma chamada por termo e crie o raspador de novo a cada chamada, como em `raspe.cfm().raspar(texto="doença rara")` seguido de `raspe.cfm().raspar(texto="medicamento órfão")`.

Os três raspadores com navegador (SaudeLegis, ANS e ANVISA) não aceitam nenhum dos dois. Eles ignoram `paginas` e coletam todas as páginas de resultado até um limite interno, e recebem um único termo por chamada: uma lista no lugar do termo dá erro. Para buscar vários termos nessas fontes, chame `.raspar()` uma vez para cada termo.

Com um termo só, a coluna `termo_busca` também aparece quando o parâmetro de busca é `pesquisa`, `termo` ou `assunto`. No CFM e no NYT, que usam `texto`, ela só aparece na busca por lista.

### Escolhendo a fonte pelo nome

Se o nome da fonte vier de uma variável (de um formulário, de um arquivo de configuração, de um laço), use `raspe.scraper_manager.scraper()` em vez de chamar cada factory na mão. Como o nome do parâmetro de busca muda conforme a fonte, guarde os parâmetros junto com o nome:

```python
from raspe.scraper_manager import scraper

buscas = {
    "presidencia": {"pesquisa": "doença rara"},
    "cfm": {"texto": "doença rara"},
    "capes": {"pesquisa": "doença rara"},
}

resultados = {}
for fonte, parametros in buscas.items():
    resultados[fonte] = scraper(fonte).raspar(**parametros)
```

O nome da fonte é o mesmo da factory (`"cfm"` para `raspe.cfm()`, `"saudelegis"` para `raspe.saudelegis()`), não diferencia maiúsculas de minúsculas e cobre as 11 fontes. Parâmetros do construtor são repassados ao raspador, como em `scraper("nyt", api_key="...")` e `scraper("ans", headless=False)`.

---

## 🏛️ Presidência, Câmara, Senado e IPEA

Essas quatro fontes usam o parâmetro `pesquisa` e funcionam da mesma forma.

```python
import raspe

# Presidência da República: leis e decretos federais
df = raspe.presidencia().raspar(pesquisa="meio ambiente")

# Câmara dos Deputados
df = raspe.camara().raspar(pesquisa="educação")

# Senado Federal
df = raspe.senado().raspar(pesquisa="reforma tributária")

# IPEA: publicações e estudos
df = raspe.ipea().raspar(pesquisa="desigualdade")
```

Em outubro de 2026, o site do Senado responde às buscas do raspe com uma página de verificação de segurança. Com um termo, `raspe.senado().raspar()` volta vazio, sem mensagem de erro. Com uma lista de termos, todos voltam sem resultado, e a busca pode parar com `FileExistsError`, pelo motivo descrito em "Paginação e vários termos", acima.

**Filtros extras da Câmara e do Senado**

As duas fontes aceitam `ano`. A Câmara aceita também `tipo_materia`, com o tipo de norma escrito como aparece no site da Câmara (ex.: `"Lei Ordinária"`):

```python
df = raspe.camara().raspar(pesquisa="saúde", ano=2023, tipo_materia="Lei Ordinária")
df = raspe.senado().raspar(pesquisa="saúde", ano=2023)
```

**Dados retornados**

| Fonte | Colunas |
|-------|---------|
| Presidência | `nome`, `link`, `ficha`, `revogacao`, `descricao` |
| Câmara | `link`, `titulo`, `descricao`, `ementa` |
| Senado | `titulo`, `link_norma`, `link_detalhes`, `descricao`, `trecho_descricao` |
| IPEA | `titulo`, `link`, `autores`, `data`, `assuntos` |

---

## 🎓 CAPES (Portal de Periódicos)

Coleta metadados bibliográficos do acervo indexado pela CAPES.

```python
import raspe

df = raspe.capes().raspar(pesquisa="natjus")
df.to_excel("artigos_capes.xlsx", index=False)
```

O parâmetro `pesquisa` é **obrigatório** e não pode ser vazio.

**Dados retornados:** `id`, `tipo`, `titulo`, `link`, `autores`, `ano`, `revista`,
`instituicao`, `topicos`, `resumo`, `doi`, `link_editor`, `acesso_aberto`,
`producao_nacional`, `revisado_por_pares`.

---

## 🩺 CFM (Conselho Federal de Medicina)

Busca normas do CFM e dos Conselhos Regionais de Medicina (CRMs). Cobre
resoluções, pareceres, emendas, normas e decisões.

```python
import raspe

# Busca simples: note que aqui o parâmetro é 'texto', não 'pesquisa'
df = raspe.cfm().raspar(texto="doenças raras")

# Busca por vários termos de uma vez
df = raspe.cfm().raspar(texto=["doença rara", "medicamento órfão", "terapia órfã"])

df.to_excel("normas_cfm.xlsx", index=False)
```

**Parâmetros disponíveis**

| Parâmetro | Descrição |
|-----------|-----------|
| `texto` | Termo de busca |
| `uf` | UF do CRM (vazio = todos) |
| `revogada` | Filtrar normas revogadas |
| `numero` | Número da norma |
| `ano` | Ano da norma |

**Dados retornados:** `Tipo`, `UF`, `Nº/Ano`, `Situação`, `Ementa`, `Link`.

---

## 🌐 Raspadores com Navegador (ANS, ANVISA, SaudeLegis)

Algumas fontes possuem proteção anti-bot (Cloudflare) e requerem automação de navegador. Para usar esses raspadores, instale as dependências extras:

### Instalação

```bash
# Instalar o raspe com suporte a navegador
pip install "raspe[browser] @ git+https://github.com/bdcdo/raspe.git"

# Instalar o navegador Chromium (necessário apenas uma vez)
python -m playwright install chromium
```

### Exemplo: ANS (Agência Nacional de Saúde Suplementar)

```python
import raspe

# Buscar atos normativos sobre doenças raras
df = raspe.ans().raspar(termo="doença rara")
df.to_excel("atos_ans.xlsx", index=False)
```

### Exemplo: ANVISA (Agência de Vigilância Sanitária)

```python
import raspe

# Buscar atos normativos sobre medicamentos
df = raspe.anvisa().raspar(termo="medicamento órfão")
df.to_excel("atos_anvisa.xlsx", index=False)
```

### Exemplo: SaudeLegis (Ministério da Saúde)

```python
import raspe

# Buscar normas sanitárias
df = raspe.saudelegis().raspar(assunto="doença rara")
df.to_excel("normas_saude.xlsx", index=False)
```

### Dados retornados (ANS/ANVISA)

- **url**: Link para o ato normativo
- **titulo**: Tipo e número (ex: RDC nº 205/2017)
- **descricao**: Ementa do ato
- **situacao**: Status (vigente, revogado, etc.)

### Dados retornados (SaudeLegis)

- **tipo_norma**: Tipo da norma (Portaria, Resolução, etc.)
- **numero**: Número da norma
- **data_pub**: Data de publicação
- **origem**: Órgão de origem
- **ementa**: Ementa da norma
- **link_url**: Link para a norma

### Modo visual (debug)

Se precisar visualizar o navegador durante a coleta (útil para debug):

```python
# Executa com navegador visível
df = raspe.ans(headless=False).raspar(termo="doença rara")
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

- **link**: URL da notícia
- **titulo**: Título da matéria
- **resumo**: Resumo/lead da notícia
- **data**: Data de publicação

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
dados = nyt.raspar(texto="climate change", ano=2024)

# Busca com intervalo de datas
dados = nyt.raspar(
    texto="Brazil",
    data_inicio="2024-01-01",
    data_fim="2024-06-30"
)

# Busca com filtros avançados (seção específica)
dados = nyt.raspar(
    texto="election",
    ano=2024,
    filtro='section.name:"Politics"'
)

# Salvar resultados
dados.to_excel("artigos_nyt.xlsx", index=False)
```

### Dados retornados

- **titulo**: Título do artigo
- **url**: Link para o artigo
- **data_publicacao**: Data de publicação
- **secao** / **desk**: Seção e editoria
- **tipo**: Tipo de material
- **resumo**: Resumo do artigo
- **autor**: Autoria
- **palavras**: Contagem de palavras
- **imagem_url**: Link da imagem principal

### Limites da API

- **10 resultados por página**, máximo de **1000 resultados** por busca
- **Rate limit**: 5 requisições por minuto, 500 por dia
- Se precisar de mais resultados, divida sua busca por intervalos de datas

---

## 🛡️ Robustez e Validações

### Retry Automático

O raspe tenta novamente automaticamente quando encontra problemas temporários de conexão ou quando o servidor está sobrecarregado. Você não precisa fazer nada - é tudo automático.

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

Depende da busca. Termos genéricos podem ter milhares de resultados e levar horas. Nos raspadores HTTP, comece testando com `paginas=range(1, 6)` para ver uma amostra rápida. SaudeLegis, ANS e ANVISA ignoram `paginas` e coletam todas as páginas de resultado.

### "Os dados vêm em que formato?"

Em tabelas (DataFrames do Pandas), que você pode exportar para Excel, CSV, ou qualquer formato que precise.

### "Preciso de internet durante a coleta?"

Sim. O raspe acessa os sites oficiais para coletar os dados em tempo real.

### "É legal usar isso?"

Sim! Todos os dados coletados são públicos e disponibilizados pelos próprios órgãos oficiais. O raspe apenas automatiza o que você faria manualmente.

### "E se der erro?"

Os erros mais comuns são:
- **"ModuleNotFoundError"**: O raspe não foi instalado corretamente. Reinstale com `pip install git+https://github.com/bdcdo/raspe.git`
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
