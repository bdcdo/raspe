"""Exemplo 1: busca básica em uma fonte.

Busca na base de legislação da Presidência da República as normas que mencionam
"doenças raras", mostra os primeiros resultados e salva a tabela em CSV e em Excel.

Como rodar, a partir da raiz do repositório:

    python examples/01_busca_basica.py

Faz até 4 requisições (uma para contar os resultados e uma por página) e leva menos de um minuto.
"""

import logging
from pathlib import Path

import raspe

# Entre aspas, o buscador da Presidência procura a expressão exata. Sem aspas, ele também
# devolve normas em que as duas palavras aparecem separadas, e a lista cresce muito (em
# outubro de 2026, de 3 para 14 páginas).
TERMO = '"doenças raras"'

# Cada página da Presidência tem 10 resultados. range(1, 4) pede as páginas 1, 2 e 3;
# se a busca tiver menos páginas, o raspe para na última que existe.
PAGINAS = range(1, 4)

PASTA_EXEMPLOS = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_EXEMPLOS / "datasets"


def main() -> None:
    """Executa a busca, mostra os primeiros resultados e salva os arquivos."""
    # Por padrão o raspador imprime cada passo da coleta e guarda as páginas baixadas numa
    # pasta temporária. Com debug=False ele apaga as páginas baixadas ao fim da busca, e a
    # linha seguinte deixa na tela só avisos e erros.
    raspador = raspe.presidencia(debug=False)
    raspador.logger.setLevel(logging.WARNING)

    normas = raspador.raspar(pesquisa=TERMO, paginas=PAGINAS)

    # Quando o site está fora do ar, ele responde com uma página de aviso e o raspador volta
    # vazio. Parar aqui evita um erro confuso adiante e não sobrescreve a tabela salva.
    if normas.empty:
        raise SystemExit(f"Nenhuma norma encontrada para {TERMO}. Se o termo está certo, o site pode "
                         "estar fora do ar; tente de novo mais tarde.")

    print(f"\n{len(normas)} normas encontradas para {TERMO}.\n")
    print(normas[["nome", "revogacao"]].head(10).to_string())

    PASTA_DADOS.mkdir(exist_ok=True)
    caminho_csv = PASTA_DADOS / "01_presidencia_doencas_raras.csv"
    caminho_excel = PASTA_DADOS / "01_presidencia_doencas_raras.xlsx"

    # O encoding utf-8-sig grava a marca BOM no começo do arquivo. Sem ela, o Excel no
    # Windows lê o CSV como Latin-1 e troca os acentos por símbolos.
    normas.to_csv(caminho_csv, index=False, encoding="utf-8-sig")
    normas.to_excel(caminho_excel, index=False)

    print(f"\nTabela salva em {caminho_csv.relative_to(PASTA_EXEMPLOS.parent)}")
    print(f"e em {caminho_excel.relative_to(PASTA_EXEMPLOS.parent)}")


if __name__ == "__main__":
    main()
