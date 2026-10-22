"""Exemplo 3: série temporal da produção acadêmica sobre um tema.

Coleta no Portal de Periódicos da CAPES os trabalhos que tratam de "judicialização de
medicamentos", conta quantos saíram em cada ano de um período e desenha um gráfico de barras.

Como rodar, a partir da raiz do repositório:

    python examples/03_analise_temporal.py

O gráfico precisa do matplotlib (pip install matplotlib). Sem ele, o script salva as
tabelas e avisa que pulou o gráfico.

Requisições: uma para contar os resultados e uma por página, até 21. Em outubro de 2026 a
busca tinha 18 páginas de 30 trabalhos, e a coleta levou cerca de um minuto.
"""

import logging
from pathlib import Path

import pandas as pd

import raspe

TERMO = "judicialização de medicamentos"

# Período da análise. O ano corrente fica de fora porque ainda não terminou: comparado
# com anos completos, ele sempre parece uma queda.
ANO_INICIAL = 2000
ANO_FINAL = 2025

# Para uma série temporal, a coleta precisa cobrir todas as páginas. O portal ordena os
# resultados por relevância, e as primeiras páginas sozinhas não são uma amostra fiel da
# distribuição por ano. O teto de 20 páginas só evita uma coleta enorme se o termo for
# trocado por um mais genérico; se a busca passar dele, o script avisa.
PAGINAS = range(1, 21)

# Só estas colunas vão para o CSV. O resumo de cada trabalho ocupa a maior parte do
# tamanho da tabela e não entra na análise.
COLUNAS = ["id", "tipo", "titulo", "ano", "doi", "acesso_aberto", "revisado_por_pares", "link"]

PASTA_EXEMPLOS = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_EXEMPLOS / "datasets"


def coletar_publicacoes(termo: str) -> pd.DataFrame:
    """Coleta os trabalhos da CAPES para um termo, com o ano já convertido em número.

    Args:
        termo: Termo de busca.

    Returns:
        DataFrame com as colunas de COLUNAS. Trabalhos sem ano legível ficam com ano vazio.
    """
    raspador = raspe.capes()
    # Deixa na tela só avisos e erros e apaga a pasta temporária das páginas baixadas.
    raspador.logger.setLevel(logging.WARNING)
    raspador.debug = False
    publicacoes = raspador.raspar(pesquisa=termo, paginas=PAGINAS)

    # O mesmo trabalho pode aparecer em duas páginas se o portal reordenar os resultados
    # durante a coleta; o id do OpenAlex identifica o trabalho.
    publicacoes = publicacoes.reindex(columns=COLUNAS).drop_duplicates(subset="id")
    # O ano chega como texto. errors="coerce" transforma o que não for número em vazio,
    # em vez de interromper o script.
    return publicacoes.assign(ano=pd.to_numeric(publicacoes["ano"], errors="coerce").astype("Int64"))


def contar_por_ano(publicacoes: pd.DataFrame, ano_inicial: int, ano_final: int) -> pd.Series:
    """Conta os trabalhos de cada ano do período, inclusive os anos sem nenhum.

    Args:
        publicacoes: Saída de coletar_publicacoes().
        ano_inicial: Primeiro ano do período.
        ano_final: Último ano do período.

    Returns:
        Série indexada pelo ano, com o número de trabalhos.
    """
    no_periodo = publicacoes[publicacoes["ano"].between(ano_inicial, ano_final)]
    # O reindex põe zero nos anos sem trabalho. Sem ele, um ano vazio some do eixo e o
    # gráfico liga os vizinhos como se fossem consecutivos.
    anos = range(ano_inicial, ano_final + 1)
    return no_periodo["ano"].value_counts().reindex(anos, fill_value=0).rename_axis("ano").rename("publicacoes")


def desenhar_grafico(por_ano: pd.Series, titulo: str, caminho: Path) -> bool:
    """Desenha e salva um gráfico de barras com o número de trabalhos por ano.

    Args:
        por_ano: Saída de contar_por_ano().
        titulo: Título do gráfico.
        caminho: Arquivo PNG de destino.

    Returns:
        True se o gráfico foi salvo, False se o matplotlib não estiver instalado.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")  # desenha direto no arquivo, sem abrir janela
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    figura, eixo = plt.subplots(figsize=(8, 4), dpi=100)
    eixo.bar(por_ano.index, por_ano.to_numpy(), color="#2a78d6", width=0.8)
    eixo.set_title(titulo, loc="left", fontsize=11)
    eixo.set_xlabel("Ano de publicação")
    eixo.set_ylabel("Trabalhos")
    eixo.set_xticks(list(por_ano.index[::5]))
    eixo.spines[["top", "right"]].set_visible(False)
    eixo.grid(axis="y", color="#e2e1dd", linewidth=0.8)
    eixo.set_axisbelow(True)
    figura.tight_layout()
    figura.savefig(caminho)
    plt.close(figura)
    return True


def main() -> None:
    """Coleta os trabalhos, conta por ano, salva as tabelas e o gráfico."""
    publicacoes = coletar_publicacoes(TERMO)
    por_ano = contar_por_ano(publicacoes, ANO_INICIAL, ANO_FINAL)

    print(f"\n{len(publicacoes)} trabalhos coletados para {TERMO!r}.")
    print(f"{por_ano.sum()} deles saíram entre {ANO_INICIAL} e {ANO_FINAL}.")
    print(f"Sem ano legível: {publicacoes['ano'].isna().sum()}.\n")
    print(por_ano.to_string())

    # A CAPES devolve 30 trabalhos por página (outubro de 2026). Se todas as páginas do teto
    # vieram cheias, é provável que a busca tenha mais páginas do que o teto deixou coletar.
    if len(publicacoes) >= 30 * len(PAGINAS):
        print(f"\nAviso: a coleta chegou ao teto de {len(PAGINAS)} páginas e a série pode estar incompleta.")

    PASTA_DADOS.mkdir(exist_ok=True)
    caminho_publicacoes = PASTA_DADOS / "03_capes_judicializacao_medicamentos.csv"
    caminho_por_ano = PASTA_DADOS / "03_publicacoes_por_ano.csv"
    caminho_grafico = PASTA_DADOS / "03_publicacoes_por_ano.png"
    publicacoes.to_csv(caminho_publicacoes, index=False, encoding="utf-8-sig")
    por_ano.to_csv(caminho_por_ano, encoding="utf-8-sig")

    print()
    for caminho in (caminho_publicacoes, caminho_por_ano):
        print(f"Salvo: {caminho.relative_to(PASTA_EXEMPLOS.parent)}")
    titulo = f'Trabalhos sobre "{TERMO}" no Portal de Periódicos da CAPES, por ano'
    if desenhar_grafico(por_ano, titulo, caminho_grafico):
        print(f"Salvo: {caminho_grafico.relative_to(PASTA_EXEMPLOS.parent)}")
    else:
        print("Gráfico não gerado: instale o matplotlib com  pip install matplotlib")


if __name__ == "__main__":
    main()
