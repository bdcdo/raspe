# raspe - Raspadores para Pesquisas Acadêmicas 🔍📊

**Coleta automática de dados de fontes oficiais brasileiras para pesquisa empírica**

---

## 📖 Para quem é esta ferramenta?

O **raspe** foi desenvolvido para **pesquisadores** que precisam coletar grandes volumes de dados de fontes oficiais brasileiras, mas têm pouco ou nenhum conhecimento de programação.

**Exemplo prático:** Imagine que você precisa analisar todas as publicações sobre "políticas públicas" dos últimos anos. Fazer isso manualmente levaria semanas. Com o raspe, você consegue em minutos.

---

## 🎯 O que o raspe faz?

O raspe automatiza a coleta de dados de fontes oficiais brasileiras:

- 🏛️ **Presidência da República** - Leis, decretos e legislação federal
- 📋 **Câmara dos Deputados** - Proposições e projetos de lei
- 📜 **Senado Federal** - Projetos de lei e atividade legislativa
- ⚖️ **CNJ (Conselho Nacional de Justiça)** - Comunicados e normas
- 📊 **IPEA** - Estudos e pesquisas econômicas aplicadas
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

### Exemplo 2: Buscar projetos de lei sobre "educação" na Câmara

```python
import raspe

camara = raspe.camara()
dados = camara.raspar(pesquisa="educação")

# Salvar em Excel
dados.to_excel("projetos_educacao.xlsx", index=False)
```

### Exemplo 3: Buscar múltiplos temas de uma vez

```python
import raspe

# Buscar três temas diferentes ao mesmo tempo
senado = raspe.senado()
dados = senado.raspar(pesquisa=["educação", "saúde", "segurança"])

# O resultado terá uma coluna 'termo_busca' identificando cada tema
dados.to_excel("projetos_multiplos.xlsx", index=False)
```

### Exemplo 4: Limitar o número de páginas (para testes rápidos)

```python
import raspe

# Buscar apenas as primeiras 5 páginas (para testar rapidamente)
cnj = raspe.cnj()
dados = cnj.raspar(pesquisa="resolução", paginas=range(1, 6))

dados.to_excel("cnj_teste.xlsx", index=False)
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

---

## 🔧 Fontes Disponíveis e Como Usar

| Fonte | Comando | O que busca |
|-------|---------|-------------|
| Presidência | `raspe.presidencia()` | Leis, decretos e legislação federal |
| Câmara | `raspe.camara()` | Proposições e projetos de lei da Câmara |
| Senado | `raspe.senado()` | Projetos de lei e atividades do Senado |
| CNJ | `raspe.cnj()` | Comunicados e normas do CNJ |
| IPEA | `raspe.ipea()` | Publicações e estudos do IPEA |
| Folha | `raspe.folha()` | Notícias da Folha de São Paulo |
| NYT | `raspe.nyt(api_key="...")` | Artigos do New York Times (requer API key) |

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

Depende da busca. Termos genéricos podem ter milhares de resultados e levar horas. Comece testando com `paginas=range(1, 6)` para ver uma amostra rápida.

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

## ⚖️ Precisa raspar dados de Tribunais?

O raspe não possui raspadores para tribunais estaduais e federais. Para isso, recomendamos o **[juscraper](https://github.com/jtrecenti/juscraper)**, um projeto Python mantido por [Julio Trecenti](https://github.com/jtrecenti) especializado em raspagem de dados do sistema judiciário brasileiro.

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
