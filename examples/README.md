# Exemplos reproduzíveis

Quatro scripts mostram, do mais simples ao mais completo, como usar o raspe numa pesquisa de direito e saúde. O tema comum é doenças raras e judicialização de medicamentos. Cada script roda sozinho, pode ser copiado para fora do repositório e deixa as tabelas que gerou em `datasets/`.

## Antes de rodar

Instale o raspe como descrito no [README principal](../README.md). O exemplo 3 desenha um gráfico com o matplotlib, que não vem com o raspe; instale com `pip install matplotlib`. Sem ele, o script salva as tabelas e avisa que pulou o gráfico.

Rode os scripts a partir da raiz do repositório, por exemplo `python examples/01_busca_basica.py`. Os arquivos vão sempre para `examples/datasets/`, qualquer que seja a pasta de onde o script foi chamado. O termo de busca e as páginas ficam em constantes no topo de cada script (`TERMO`, `TERMOS`, `PAGINAS`): para adaptar um exemplo à sua pesquisa, comece por elas.

## Os quatro scripts

| Script | O que faz | Fonte | Requisições | Tempo |
|---|---|---|---|---|
| [`01_busca_basica.py`](01_busca_basica.py) | Busca "doenças raras" na legislação federal, mostra os dez primeiros resultados e salva a tabela em CSV e em Excel. | Presidência | até 4 | 11 s |
| [`02_multiplas_fontes.py`](02_multiplas_fontes.py) | Faz a mesma busca em três bases legislativas, põe os resultados num formato comum, conta quantos citam o termo no título ou na ementa e lista as normas que aparecem em mais de uma base. | Presidência, Câmara e Senado | até 20 | 35 s |
| [`03_analise_temporal.py`](03_analise_temporal.py) | Coleta todas as páginas da busca por "judicialização de medicamentos", conta os trabalhos de cada ano entre 2000 e 2025 e desenha um gráfico de barras. | CAPES | até 21 | 55 s |
| [`04_pipeline_completo.py`](04_pipeline_completo.py) | Coleta, limpa, analisa e exporta as publicações sobre "judicialização da saúde" e "saúde suplementar". Tenta de novo quando o site falha, salva os dados brutos antes da limpeza e registra data, versão do raspe e resultado de cada termo. | IPEA | 9, sem contar novas tentativas | 20 s a 2 min |

Os números são da execução de 21 de outubro de 2026. Cada busca faz uma requisição para contar os resultados e uma por página, e a Câmara faz mais duas para abrir a sessão. Entre uma página e outra, o raspe espera 2 segundos. O tempo do exemplo 4 varia porque o site do IPEA às vezes leva 20 segundos para responder.

Três observações da execução que ajudam a ler os resultados:

- **Senado.** O site do Senado respondeu com uma página de verificação contra robôs, e o raspador voltou sem resultados. O exemplo 2 trata isso como fonte vazia e segue com as outras; as tabelas de `datasets/` registram o Senado com zero.
- **CAPES.** Depois de cerca de 25 requisições seguidas, o portal passou a responder com erro 403 por alguns minutos. Se isso acontecer, espere e rode de novo. Os títulos de `03_capes_judicializacao_medicamentos.csv` têm palavras coladas, um defeito do raspador descrito na issue #40; rodar o exemplo 3 depois da correção atualiza a tabela.
- **Sintaxe da busca.** A Presidência aceita aspas para pedir a expressão exata. A Câmara responde com erro 400 quando a busca tem aspas, por isso o exemplo 2 busca sem elas na Câmara e no Senado.

## Notebooks

Três notebooks em [`notebooks/`](../notebooks/) importam as funções destes scripts e explicam, célula por célula, o que cada etapa faz e por quê. Eles precisam de um clone do repositório, porque leem os scripts desta pasta.

| Notebook | Parte de | O que acrescenta |
|---|---|---|
| [`10_pipeline_completo.ipynb`](../notebooks/10_pipeline_completo.ipynb) | exemplo 4 | Mostra os dados brutos antes e depois de cada etapa e simula uma queda do site para ver as novas tentativas e o registro da coleta. Faz 5 requisições ao IPEA. |
| [`11_multiplas_fontes.ipynb`](../notebooks/11_multiplas_fontes.ipynb) | exemplo 2 | Compara as colunas de cada fonte, mostra a mesma norma em duas bases e cruza o período que cada base cobre. Faz até 20 requisições. |
| [`12_analise_longitudinal.ipynb`](../notebooks/12_analise_longitudinal.ipynb) | exemplo 3 | Lê a coleta salva pelo exemplo 3 e calcula média móvel, crescimento acumulado, comparação de períodos e composição por tipo e por acesso aberto. Não acessa a rede, a menos que `COLETAR_DE_NOVO` seja `True`. |

## Arquivos em `datasets/`

Todas as tabelas estão em CSV com codificação UTF-8 com BOM, a marca que faz o Excel abrir o arquivo com os acentos certos. O `.xlsx` do exemplo 1 não fica versionado, porque repete o CSV.

| Arquivo | Gerado por | Conteúdo |
|---|---|---|
| `01_presidencia_doencas_raras.csv` | exemplo 1 | 29 normas, como o raspador da Presidência as devolve |
| `02_normas_doencas_raras.csv` | exemplo 2 | 88 resultados das três fontes no formato comum, com a chave da norma e a marca de menção ao termo |
| `02_resumo_por_fonte.csv` | exemplo 2 | resultados e menções ao termo por fonte |
| `02_normas_em_comum.csv` | exemplo 2 | 19 normas presentes na Presidência e na Câmara |
| `03_capes_judicializacao_medicamentos.csv` | exemplo 3 | 355 trabalhos, sem o resumo, que ocupa a maior parte do tamanho e não entra na análise |
| `03_publicacoes_por_ano.csv` | exemplo 3 | trabalhos por ano, de 2000 a 2025 |
| `03_publicacoes_por_ano.png` | exemplo 3 | gráfico de barras da tabela anterior |
| `04_ipea_bruto.csv` | exemplo 4 | 56 linhas como vieram do site, antes da limpeza |
| `04_ipea_publicacoes.csv` | exemplo 4 | 56 publicações depois da limpeza |
| `04_ipea_por_ano.csv`, `04_ipea_por_termo.csv`, `04_ipea_temas.csv` | exemplo 4 | publicações por ano, por termo de busca e os dez temas mais frequentes |
| `04_ipea_registro_da_coleta.csv` | exemplo 4 | data, versão do raspe, situação e número de registros de cada termo |

Rodar um script de novo sobrescreve os arquivos dele com a coleta do dia.
