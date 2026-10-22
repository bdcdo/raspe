"""Exemplo 4: pipeline completo, da coleta à exportação.

Coleta no IPEA as publicações sobre dois temas de saúde, limpa os dados, faz uma análise
descritiva e exporta tudo em CSV, junto com um registro de como a coleta correu. As quatro
etapas ficam em funções separadas, que o notebook 10_pipeline_completo.ipynb reaproveita.

Boas práticas que o script mostra:

- salvar os dados brutos antes de limpar, para poder refazer a limpeza sem coletar de novo;
- tentar de novo quando o site falha, com espera crescente, e seguir com os outros termos
  quando um deles não volta;
- registrar data, versão do raspe e resultado de cada termo, para saber depois de onde
  veio cada tabela;
- tratar formatos de data diferentes na mesma coluna sem perder linhas em silêncio.

Como rodar, a partir da raiz do repositório:

    python examples/04_pipeline_completo.py

Requisições: para cada termo, uma de contagem e uma por página. Em outubro de 2026 foram 9
(os dois termos tinham 1 e 6 páginas) e a execução levou cerca de 2 minutos, porque o site
do IPEA às vezes leva 20 segundos para responder.
"""

import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

import raspe

TERMOS = ["judicialização da saúde", "saúde suplementar"]
PAGINAS = range(1, 8)  # cada página do IPEA tem 10 publicações
TENTATIVAS = 3
ESPERA_INICIAL = 10  # segundos antes da segunda tentativa; dobra a cada nova falha

PASTA_EXEMPLOS = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_EXEMPLOS / "datasets"

# O IPEA publica a data em formatos diferentes na mesma coluna. Na coleta de outubro de
# 2026 apareceram três: só o ano ("2019"), mês abreviado e ano ("Mai-2025") e ano com um
# hífen na frente ("-2004"). Ano e mês são procurados separadamente, o que cobre os três.
MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
PADRAO_MES = re.compile(r"\b(" + "|".join(MESES) + r")\b", re.IGNORECASE)
PADRAO_ANO = re.compile(r"\b(?:19|20)\d{2}\b")


# 1. Coleta ------------------------------------------------------------------------------

def coletar_termo(termo: str, paginas: range = PAGINAS) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Coleta um termo no IPEA, tentando de novo quando o site falha.

    Args:
        termo: Termo de busca.
        paginas: Páginas a coletar.

    Returns:
        Os dados coletados (vazios se todas as tentativas falharem) e uma linha de registro
        com termo, situação, número de registros, tentativas, erro e horário.
    """
    registro: dict[str, Any] = {
        "termo": termo,
        "situacao": "falhou",
        "registros": 0,
        "tentativas": 0,
        "erro": "",
        "coletado_em": datetime.now().isoformat(timespec="seconds"),
        "versao_raspe": raspe.__version__,
    }
    espera = ESPERA_INICIAL
    for tentativa in range(1, TENTATIVAS + 1):
        registro["tentativas"] = tentativa
        try:
            raspador = raspe.ipea()
            # Deixa na tela só avisos e erros e apaga a pasta temporária das páginas baixadas.
            raspador.logger.setLevel(logging.WARNING)
            raspador.debug = False
            dados = raspador.raspar(pesquisa=termo, paginas=paginas)
        except raspe.ValidationError as erro:
            # Parâmetro inválido é erro de quem chamou: tentar de novo não muda o resultado.
            registro["erro"] = f"{type(erro).__name__}: {erro}"
            return pd.DataFrame(), registro
        except requests.RequestException as erro:
            # Timeout, conexão recusada e erro HTTP costumam ser passageiros. Só falhas da
            # requisição de contagem chegam aqui. Erro 429 ou 5xx que persiste na contagem faz
            # o raspe devolver a busca vazia, e a falha de uma página depois da contagem faz o
            # raspe seguir sem ela; nos dois casos o erro aparece no log, que o nível WARNING
            # mantém na tela.
            registro["erro"] = f"{type(erro).__name__}: {erro}"
            if tentativa < TENTATIVAS:
                print(f"  Falha na tentativa {tentativa} ({type(erro).__name__}); nova tentativa em {espera} s.")
                time.sleep(espera)
                espera *= 2
            continue
        registro["situacao"] = "ok" if len(dados) else "sem resultados"
        registro["registros"] = len(dados)
        registro["erro"] = ""
        return dados, registro
    return pd.DataFrame(), registro


def coletar(termos: list[str], paginas: range = PAGINAS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coleta todos os termos e junta os resultados.

    Args:
        termos: Termos de busca.
        paginas: Páginas a coletar em cada termo.

    Returns:
        Os dados brutos de todos os termos, com a coluna termo_busca, e o registro da coleta.
    """
    partes = []
    registros = []
    for termo in termos:
        print(f"Coletando {termo!r}")
        dados, registro = coletar_termo(termo, paginas)
        print(f"  {registro['situacao']}: {registro['registros']} registros")
        partes.append(dados)
        registros.append(registro)
    bruto = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()
    return bruto, pd.DataFrame(registros)


# 2. Limpeza -----------------------------------------------------------------------------

def converter_data(texto: str) -> tuple[int | None, int | None]:
    """Extrai ano e mês de uma data do IPEA, nos formatos descritos junto de MESES.

    Args:
        texto: Data como o IPEA publica, por exemplo "Mai-2025", "2019" ou "-2004".

    Returns:
        Ano e mês. Cada um vira None quando não aparece no texto.

    Examples:
        >>> converter_data("Mai-2025")
        (2025, 5)
        >>> converter_data("-2004")
        (2004, None)
    """
    achado_ano = PADRAO_ANO.search(texto)
    achado_mes = PADRAO_MES.search(texto)
    ano = int(achado_ano.group()) if achado_ano else None
    mes = MESES[achado_mes.group(1).lower()] if achado_mes else None
    return ano, mes


def separar_temas(texto: str) -> str:
    """Transforma a coluna assuntos do IPEA numa lista de temas sem repetição.

    O IPEA publica os temas como "Temas:" seguido de nomes separados por vírgula, com
    quebras de linha e o mesmo tema repetido mais de uma vez.

    Args:
        texto: Conteúdo da coluna assuntos.

    Returns:
        Temas separados por "; ", na ordem em que aparecem pela primeira vez.
    """
    sem_rotulo = re.sub(r"^\s*Temas:\s*", "", texto)
    temas = [" ".join(parte.split()) for parte in sem_rotulo.split(",")]
    # dict.fromkeys tira as repetições e mantém a ordem da primeira aparição.
    return "; ".join(dict.fromkeys(tema for tema in temas if tema))


def limpar(bruto: pd.DataFrame) -> pd.DataFrame:
    """Limpa os dados brutos do IPEA.

    Normaliza espaços, converte a data em ano e mês, organiza os temas e junta numa
    linha só a publicação que apareceu em mais de um termo.

    Args:
        bruto: Saída de coletar().

    Returns:
        Uma linha por publicação, com as colunas titulo, link, autores, data, ano, mes,
        temas e termos.
    """
    colunas = ["titulo", "link", "autores", "data", "assuntos", "termo_busca"]
    dados = bruto.reindex(columns=colunas).fillna("").astype(str)
    dados = dados.assign(
        titulo=dados["titulo"].str.split().str.join(" "),
        autores=dados["autores"].str.split().str.join(" "),
        data=dados["data"].str.strip(),
        temas=dados["assuntos"].map(separar_temas),
    )
    # Sem link não há como conferir a publicação nem tirar repetidas.
    dados = dados[dados["link"].str.len() > 0]

    datas = dados["data"].map(converter_data)
    dados = dados.assign(
        ano=pd.array([ano for ano, _ in datas], dtype="Int64"),
        mes=pd.array([mes for _, mes in datas], dtype="Int64"),
    )

    # A mesma publicação volta uma vez para cada termo que a encontra. O agrupamento por
    # link deixa uma linha por publicação e guarda, em termos, todos os termos que a acharam.
    termos = dados.groupby("link", sort=False)["termo_busca"].agg(lambda valores: "; ".join(dict.fromkeys(valores)))
    limpo = dados.drop_duplicates(subset="link").set_index("link")
    limpo = limpo.assign(termos=termos).reset_index()
    return limpo[["titulo", "link", "autores", "data", "ano", "mes", "temas", "termos"]]


# 3. Análise -----------------------------------------------------------------------------

def analisar(limpo: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Produz as tabelas descritivas.

    Args:
        limpo: Saída de limpar().

    Returns:
        Dicionário com as tabelas por_ano, por_termo e temas.
    """
    por_ano = limpo["ano"].value_counts(dropna=False).sort_index().rename_axis("ano").reset_index(name="publicacoes")

    # Uma publicação achada pelos dois termos conta uma vez em cada termo.
    por_termo = (
        limpo["termos"].str.split("; ").explode().value_counts()
        .rename_axis("termo").reset_index(name="publicacoes")
    )

    temas = limpo["temas"].str.split("; ").explode()
    temas = temas[temas.str.len() > 0]
    por_tema = temas.value_counts().head(10).rename_axis("tema").reset_index(name="publicacoes")

    return {"por_ano": por_ano, "por_termo": por_termo, "temas": por_tema}


# 4. Exportação --------------------------------------------------------------------------

def exportar(tabelas: dict[str, pd.DataFrame], pasta: Path, prefixo: str = "04_ipea_") -> list[Path]:
    """Salva cada tabela num CSV em UTF-8 com BOM, que o Excel abre com os acentos certos.

    Args:
        tabelas: Nome da tabela e o DataFrame correspondente.
        pasta: Pasta de destino, criada se não existir.
        prefixo: Início do nome de cada arquivo.

    Returns:
        Caminhos dos arquivos salvos.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    for nome, tabela in tabelas.items():
        caminho = pasta / f"{prefixo}{nome}.csv"
        tabela.to_csv(caminho, index=False, encoding="utf-8-sig")
        caminhos.append(caminho)
    return caminhos


def main() -> int:
    """Roda as quatro etapas e devolve o código de saída do processo."""
    print("1. Coleta")
    bruto, registro = coletar(TERMOS)
    # Os brutos vão para o disco antes de qualquer limpeza.
    for caminho in exportar({"bruto": bruto, "registro_da_coleta": registro}, PASTA_DADOS):
        print(f"  Salvo: {caminho.relative_to(PASTA_EXEMPLOS.parent)}")
    if bruto.empty:
        print("Nenhum termo voltou com dados; veja o registro da coleta.")
        return 1

    print("\n2. Limpeza")
    limpo = limpar(bruto)
    print(f"  {len(bruto)} linhas brutas viraram {len(limpo)} publicações.")
    sem_ano = limpo["ano"].isna().sum()
    print(f"  Publicações sem ano legível: {sem_ano}.")

    print("\n3. Análise")
    tabelas = analisar(limpo)
    for nome, tabela in tabelas.items():
        print(f"\n{nome}:\n{tabela.to_string(index=False)}")

    print("\n4. Exportação")
    for caminho in exportar({"publicacoes": limpo, **tabelas}, PASTA_DADOS):
        print(f"  Salvo: {caminho.relative_to(PASTA_EXEMPLOS.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
