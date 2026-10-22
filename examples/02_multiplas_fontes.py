"""Exemplo 2: a mesma busca em três fontes legislativas.

Busca "doenças raras" na Presidência da República, na Câmara dos Deputados e no Senado
Federal, põe os três resultados num formato comum e faz duas análises cruzadas simples:
quantos resultados de cada fonte citam a expressão no título ou na ementa, e quais normas
aparecem em mais de uma fonte.

Como rodar, a partir da raiz do repositório:

    python examples/02_multiplas_fontes.py

Requisições: até 4 na Presidência, até 9 na Câmara (duas para abrir a sessão, uma para
contar os resultados e até 6 páginas) e até 7 no Senado. Leva de um a dois minutos.

Se uma fonte falhar ou voltar vazia, o script avisa e segue com as outras.
"""

import logging
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests

import raspe

PASTA_EXEMPLOS = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_EXEMPLOS / "datasets"

# Cada fonte devolve colunas com nomes e conteúdos diferentes. Este dicionário diz, para
# cada uma, como criar o raspador, o que buscar e quais colunas fazem o papel de título,
# link e texto descritivo. É a única parte do script que muda ao trocar ou acrescentar fonte.
FONTES: list[dict[str, Any]] = [
    {
        "nome": "Presidência",
        "criar": raspe.presidencia,
        # O buscador da Presidência aceita aspas para pedir a expressão exata.
        "pesquisa": '"doenças raras"',
        "paginas": range(1, 4),
        "coluna_titulo": "nome",
        "coluna_link": "link",
        "colunas_texto": ["descricao"],
    },
    {
        "nome": "Câmara",
        "criar": raspe.camara,
        # O buscador da Câmara responde com erro 400 quando a busca tem aspas.
        "pesquisa": "doenças raras",
        "paginas": range(1, 7),
        "coluna_titulo": "titulo",
        "coluna_link": "link",
        "colunas_texto": ["descricao", "ementa"],
    },
    {
        "nome": "Senado",
        "criar": raspe.senado,
        "pesquisa": "doenças raras",
        "paginas": range(1, 7),
        "coluna_titulo": "titulo",
        "coluna_link": "link_norma",
        "colunas_texto": ["descricao", "trecho_descricao"],
    },
]

# Aceita singular e plural, com ou sem cedilha: "doença rara", "doenças raras", "doencas raras".
PADRAO_TERMO = re.compile(r"doen[çc]as?\s+raras?", re.IGNORECASE)

# Títulos de norma têm forma fixa: tipo, "nº", número e, mais adiante, o ano. Exemplos reais:
# "Lei nº 14.593 de 02 de junho de 2023" (Presidência) e "Decreto nº 12.343, de 5 de Maio de
# 1943" (Câmara). O ano é o primeiro número de quatro dígitos depois do número da norma, o que
# pula o dia do mês e não confunde o número "1.316" (com ponto) com um ano.
PADRAO_NORMA = re.compile(
    r"^\s*(?P<tipo>\D+?)\s+n[º°o]?\.?\s*(?P<numero>\d[\d.]*)\D.*?(?P<ano>(?:18|19|20)\d{2})",
    re.IGNORECASE,
)


def coletar_fonte(fonte: dict[str, Any]) -> pd.DataFrame:
    """Coleta os resultados de uma fonte com o termo e as páginas definidos em FONTES.

    Args:
        fonte: Um dos dicionários de FONTES.

    Returns:
        DataFrame com as colunas originais da fonte.

    Raises:
        requests.RequestException: Se o site não responder ou responder com erro.
        raspe.ScraperError: Se o raspador recusar os parâmetros da busca.
    """
    raspador = fonte["criar"]()
    # Deixa na tela só avisos e erros e apaga a pasta temporária das páginas baixadas.
    raspador.logger.setLevel(logging.WARNING)
    raspador.debug = False
    return raspador.raspar(pesquisa=fonte["pesquisa"], paginas=fonte["paginas"])


def padronizar(dados: pd.DataFrame, fonte: dict[str, Any]) -> pd.DataFrame:
    """Converte o resultado de uma fonte para as colunas comuns fonte, titulo, link e texto.

    Args:
        dados: DataFrame devolvido por coletar_fonte().
        fonte: O dicionário de FONTES que gerou os dados.

    Returns:
        DataFrame com as colunas fonte, titulo, link e texto, uma linha por resultado.
    """
    colunas = [fonte["coluna_titulo"], fonte["coluna_link"], *fonte["colunas_texto"]]
    # Busca sem resultado volta como DataFrame sem as colunas da fonte. O reindex cria as
    # colunas que faltam, vazias, para que a seleção abaixo não levante KeyError.
    dados = dados.reindex(columns=colunas).fillna("").astype(str)
    # Junta as colunas descritivas num texto só.
    primeira, *demais = fonte["colunas_texto"]
    texto = dados[primeira]
    for coluna in demais:
        texto = texto + " " + dados[coluna]
    return pd.DataFrame({
        "fonte": fonte["nome"],
        "titulo": dados[fonte["coluna_titulo"]].str.strip(),
        "link": dados[fonte["coluna_link"]].str.strip(),
        # split() seguido de join() colapsa quebras de linha e espaços repetidos.
        "texto": texto.str.split().str.join(" "),
    })


def identificar_norma(titulo: str) -> str | None:
    """Extrai do título uma chave de norma no formato "tipo número/ano".

    Args:
        titulo: Título da norma, como "Lei nº 14.593 de 02 de junho de 2023".

    Returns:
        A chave, como "lei 14593/2023", ou None se o título não seguir a forma esperada.

    Examples:
        >>> identificar_norma("Decreto nº 12.343, de 5 de Maio de 1943")
        'decreto 12343/1943'
    """
    achado = PADRAO_NORMA.search(titulo)
    if achado is None:
        return None
    tipo = " ".join(achado["tipo"].lower().split())
    numero = achado["numero"].replace(".", "")
    return f"{tipo} {numero}/{achado['ano']}"


def coletar_todas(fontes: list[dict[str, Any]]) -> dict[str, pd.DataFrame]:
    """Coleta cada fonte em sequência; a que falhar volta vazia, com um aviso na tela.

    Args:
        fontes: Lista no formato de FONTES.

    Returns:
        Dicionário do nome da fonte para os dados brutos dela.
    """
    brutos = {}
    for fonte in fontes:
        print(f"Coletando {fonte['nome']} ({fonte['pesquisa']})")
        try:
            bruto = coletar_fonte(fonte)
        except (requests.RequestException, raspe.ScraperError) as erro:
            # Uma fonte fora do ar não deve derrubar a coleta das outras.
            print(f"  A coleta falhou ({type(erro).__name__}: {erro}). Seguindo com as outras fontes.")
            bruto = pd.DataFrame()
        if bruto.empty:
            print("  Nenhum resultado.")
        brutos[fonte["nome"]] = bruto
    return brutos


def juntar(brutos: dict[str, pd.DataFrame], fontes: list[dict[str, Any]]) -> pd.DataFrame:
    """Padroniza os dados de cada fonte, junta tudo e acrescenta a chave da norma.

    Args:
        brutos: Saída de coletar_todas().
        fontes: A lista de fontes que gerou os dados.

    Returns:
        Uma linha por resultado, sem links repetidos dentro de cada fonte, com as colunas de
        padronizar() mais chave_norma e menciona_termo.
    """
    padronizados = [padronizar(brutos[fonte["nome"]], fonte) for fonte in fontes]
    resultados = pd.concat(padronizados, ignore_index=True)
    # Um resultado repetido dentro da mesma fonte contaria duas vezes no resumo. O link
    # identifica o resultado; a mesma norma em fontes diferentes tem links diferentes e fica.
    resultados = resultados.drop_duplicates(subset=["fonte", "link"]).reset_index(drop=True)
    return resultados.assign(
        chave_norma=resultados["titulo"].map(identificar_norma),
        menciona_termo=(resultados["titulo"] + " " + resultados["texto"]).str.contains(PADRAO_TERMO),
    )


def resumir_por_fonte(resultados: pd.DataFrame, nomes_fontes: list[str]) -> pd.DataFrame:
    """Conta, por fonte, os resultados e os que citam o termo no título ou na ementa.

    Args:
        resultados: Saída de juntar().
        nomes_fontes: Nomes de todas as fontes consultadas, inclusive as que voltaram vazias.

    Returns:
        DataFrame com uma linha por fonte e as colunas resultados, citam_o_termo e
        percentual_que_cita.
    """
    resumo = (
        resultados.groupby("fonte")
        .agg(resultados=("link", "size"), citam_o_termo=("menciona_termo", "sum"))
        # O reindex mantém no resumo as fontes que voltaram vazias, com zero.
        .reindex(nomes_fontes, fill_value=0)
    )
    # where() troca o zero por vazio no denominador: fonte sem resultado fica sem percentual,
    # em vez de uma divisão por zero.
    percentual = 100 * resumo["citam_o_termo"] / resumo["resultados"].where(resumo["resultados"] > 0)
    return resumo.assign(percentual_que_cita=percentual.round(1)).reset_index()


def normas_em_comum(resultados: pd.DataFrame) -> pd.DataFrame:
    """Lista as normas que aparecem em mais de uma fonte.

    Args:
        resultados: Saída de juntar().

    Returns:
        DataFrame com chave_norma, a lista de fontes e o número de fontes, da norma mais
        citada para a menos citada.
    """
    com_chave = resultados.dropna(subset=["chave_norma"])
    por_norma = com_chave.groupby("chave_norma")["fonte"].agg(lambda fontes: sorted(set(fontes)))
    tabela = pd.DataFrame({
        "chave_norma": por_norma.index,
        "fontes": por_norma.map(", ".join).to_numpy(),
        "n_fontes": por_norma.map(len).to_numpy(),
    })
    return tabela[tabela["n_fontes"] > 1].sort_values(["n_fontes", "chave_norma"], ascending=[False, True])


def main() -> None:
    """Coleta as três fontes, cruza os resultados e salva as tabelas."""
    brutos = coletar_todas(FONTES)
    resultados = juntar(brutos, FONTES)
    resumo = resumir_por_fonte(resultados, list(brutos))
    em_comum = normas_em_comum(resultados)

    print("\nResultados por fonte:\n")
    print(resumo.to_string(index=False))
    print(f"\nNormas que aparecem em mais de uma fonte: {len(em_comum)}\n")
    if not em_comum.empty:
        print(em_comum.to_string(index=False))

    PASTA_DADOS.mkdir(exist_ok=True)
    arquivos = {
        "02_normas_doencas_raras.csv": resultados,
        "02_resumo_por_fonte.csv": resumo,
        "02_normas_em_comum.csv": em_comum,
    }
    print()
    for nome_arquivo, tabela in arquivos.items():
        caminho = PASTA_DADOS / nome_arquivo
        tabela.to_csv(caminho, index=False, encoding="utf-8-sig")
        print(f"Salvo: {caminho.relative_to(PASTA_EXEMPLOS.parent)}")


if __name__ == "__main__":
    main()
