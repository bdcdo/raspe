"""Testes unitários para raspe.utils.

Cobre as funções públicas exportadas em ``raspe.utils``:

* ``expand`` — converte expressão de busca em lista de combinações
* ``remove_duplicates`` — dedup por coluna ``link`` agregando ``termo_busca``
* ``start_session`` — cria ``requests.Session`` com headers padrão
* ``extract`` — coleta texto de cada URL em uma coluna do DataFrame
* ``check`` — conta ocorrências de cada termo em ``link_content``
* ``validar_data`` — normaliza string de data para ISO 8601
* ``validar_intervalo_datas`` — valida par (início, fim) com ordem
"""

import re

import pandas as pd
import pytest
import requests
import responses

from raspe.exceptions import ValidationError
from raspe.utils import check, expand, extract, remove_duplicates, start_session, validar_data, validar_intervalo_datas


class TestExpand:
    """Testes para a função expand() que converte expressões de busca complexas."""

    def test_simple_or_expression(self):
        """Testa expressão simples com operador OU."""
        expr = "termo1 OU termo2"
        result = expand(expr)
        assert result == ["termo1", "termo2"]

    def test_simple_and_expression(self):
        """Testa expressão simples com operador E."""
        expr = "termo1 E termo2"
        result = expand(expr)
        assert result == ["termo1 termo2"]

    def test_complex_expression(self):
        """Testa expressão complexa com operadores aninhados."""
        expr = "(doença OU doenças) E (rara OU raras)"
        result = expand(expr)
        assert sorted(result) == sorted([
            "doença rara",
            "doença raras",
            "doenças rara",
            "doenças raras"
        ])

    def test_nested_expression(self):
        """Testa expressão com múltiplos níveis de aninhamento."""
        expr = "((termo1 OU termo2) E termo3) OU (termo4 E termo5)"
        result = expand(expr)
        assert sorted(result) == sorted([
            "termo1 termo3",
            "termo2 termo3",
            "termo4 termo5"
        ])

    def test_example_from_docstring(self):
        """Testa o exemplo do docstring."""
        expr = "(((doença OU doenças) E (rara OU raras)) OU ((medicamento) E (órfão)))"
        result = expand(expr)
        expected = ['doença rara', 'doença raras', 'doenças rara', 'doenças raras', 'medicamento órfão']
        assert sorted(result) == sorted(expected)

    def test_complex_multiline_expression(self):
        """Testa expressão complexa com múltiplas linhas e termos."""
        expr = """
        (
        ((doença OU síndrome OU patologia) E (rara OU ultrarrara)) OU
        ((doenças OU síndromes OU patologias) E ((raras OU ultrarraras))) OU
        (medicamento E órfão) OU
        (medicamentos E órfãos) OU
        (terapia E órfã) OU
        (terapias E órfãs)
        )
        """
        result = expand(expr)

        expected = [
            'doença rara', 'doença ultrarrara',
            'síndrome rara', 'síndrome ultrarrara',
            'patologia rara', 'patologia ultrarrara',
            'doenças raras', 'doenças ultrarraras',
            'síndromes raras', 'síndromes ultrarraras',
            'patologias raras', 'patologias ultrarraras',
            'medicamento órfão',
            'medicamentos órfãos',
            'terapia órfã',
            'terapias órfãs'
        ]

        assert sorted(result) == sorted(expected)

    def test_unbalanced_parentheses(self):
        """Testa se a função detecta parênteses desequilibrados."""
        expr = "(termo1 E termo2"
        with pytest.raises(ValueError, match="Parênteses desequilibrados"):
            expand(expr)

    def test_empty_parentheses(self):
        """Testa se a função detecta parênteses vazios."""
        expr = "termo1 E () E termo2"
        with pytest.raises(ValueError, match="Parênteses vazios"):
            expand(expr)


class TestRemoveDuplicates:
    """Testes para a função remove_duplicates() que deduplica por 'link'."""

    def test_sem_duplicatas_preserva_dataframe(self):
        """Sem duplicatas, todas as linhas permanecem (em qualquer ordem)."""
        df = pd.DataFrame({
            "link": ["http://a", "http://b", "http://c"],
            "titulo": ["A", "B", "C"],
            "termo_busca": ["x", "y", "z"],
        })
        result = remove_duplicates(df)
        assert len(result) == 3
        assert set(result["link"]) == {"http://a", "http://b", "http://c"}

    def test_duplicatas_simples_agregam_termo_busca(self):
        """Duas linhas com mesmo link → uma linha com termo_busca concatenado."""
        df = pd.DataFrame({
            "link": ["http://a", "http://a", "http://b"],
            "titulo": ["A", "A", "B"],
            "termo_busca": ["termo1", "termo2", "termo3"],
        })
        result = remove_duplicates(df)
        assert len(result) == 2
        row_a = result[result["link"] == "http://a"].iloc[0]
        assert "termo1" in row_a["termo_busca"]
        assert "termo2" in row_a["termo_busca"]

    def test_colunas_extras_usam_first(self):
        """Colunas além de link/termo_busca usam agregação 'first'."""
        df = pd.DataFrame({
            "link": ["http://a", "http://a"],
            "titulo": ["Primeiro", "Segundo"],
            "termo_busca": ["t1", "t2"],
            "data": ["2024-01-01", "2024-01-02"],
        })
        result = remove_duplicates(df)
        assert len(result) == 1
        row = result.iloc[0]
        assert row["titulo"] == "Primeiro"
        assert row["data"] == "2024-01-01"

    def test_dataframe_vazio(self):
        """DataFrame vazio retorna vazio sem levantar exceção."""
        df = pd.DataFrame({"link": [], "titulo": [], "termo_busca": []})
        result = remove_duplicates(df)
        assert len(result) == 0


class TestStartSession:
    """Testes para start_session() que cria requests.Session padronizada."""

    def test_retorna_requests_session(self):
        """A função retorna uma instância de requests.Session."""
        session = start_session()
        assert isinstance(session, requests.Session)

    def test_headers_obrigatorios_configurados(self):
        """Headers padrão estão configurados."""
        session = start_session()
        headers = session.headers
        assert "User-Agent" in headers
        assert "Mozilla" in headers["User-Agent"]
        assert "Accept-Language" in headers
        assert "pt-BR" in headers["Accept-Language"]
        assert "Accept-Encoding" in headers
        assert headers["Connection"] == "keep-alive"

    def test_sessoes_independentes(self):
        """Cada chamada retorna uma session independente."""
        s1 = start_session()
        s2 = start_session()
        assert s1 is not s2


@pytest.mark.filterwarnings("ignore::bs4.MarkupResemblesLocatorWarning")
@pytest.mark.filterwarnings("ignore::bs4.GuessedAtParserWarning")
class TestExtract:
    """Testes para extract() que coleta conteúdo HTML de uma coluna de URLs.

    Markers ``filterwarnings`` silenciam dois warnings do BeautifulSoup que
    aparecem nesses cenários e seriam transformados em erro pelo
    ``filterwarnings = ["error"]`` global:

    * ``MarkupResemblesLocatorWarning`` — corpo curto em alguns testes.
    * ``GuessedAtParserWarning`` — ``raspe.utils.extract`` chama
      ``BeautifulSoup`` sem ``features=...`` explícito. Suprimimos só os dois
      warnings concretos, sem afrouxar a regra global.
    """

    @responses.activate
    def test_extract_baixa_e_extrai_texto(self, mocker):
        """extract() faz GET em cada link e adiciona coluna {col}_content."""
        mocker.patch("time.sleep")

        responses.add(
            responses.GET,
            "http://example.com/a",
            body="<html><body>Conteúdo A</body></html>",
            status=200,
            content_type="text/html; charset=utf-8",
        )
        responses.add(
            responses.GET,
            "http://example.com/b",
            body="<html><body>Conteúdo B</body></html>",
            status=200,
            content_type="text/html; charset=utf-8",
        )

        df = pd.DataFrame({"link": ["http://example.com/a", "http://example.com/b"]})
        result = extract(df, "link")

        assert "link_content" in result.columns
        assert "Conteúdo A" in result["link_content"].iloc[0]
        assert "Conteúdo B" in result["link_content"].iloc[1]

    def test_extract_file_url_eh_pulado(self, mocker):
        """Links file:// são pulados e geram string vazia (sem requisição)."""
        mocker.patch("time.sleep")
        df = pd.DataFrame({"link": ["file:///tmp/local.html"]})
        result = extract(df, "link")
        assert result["link_content"].iloc[0] == ""

    @responses.activate
    def test_extract_erro_de_requisicao_resulta_em_string_vazia(self, mocker):
        """Quando GET falha, a linha recebe string vazia ao invés de propagar."""
        mocker.patch("time.sleep")
        responses.add(
            responses.GET,
            "http://example.com/broken",
            body=ConnectionError("falha de rede"),
        )
        df = pd.DataFrame({"link": ["http://example.com/broken"]})
        result = extract(df, "link")
        assert result["link_content"].iloc[0] == ""


class TestCheck:
    """Testes para check() que conta termos de busca em link_content."""

    def test_count_simples(self):
        """check() adiciona uma coluna por palavra única em termo_busca."""
        df = pd.DataFrame({
            "termo_busca": ["medicamento órfão"],
            "link_content": ["O medicamento órfão é raro. O medicamento custa caro."],
        })
        result = check(df)
        assert "medicamento" in result.columns
        assert "órfão" in result.columns
        assert result["medicamento"].iloc[0] == 2
        assert result["órfão"].iloc[0] == 1

    def test_count_palavra_completa(self):
        """check() conta apenas ocorrências como palavra completa."""
        df = pd.DataFrame({
            "termo_busca": ["rara"],
            "link_content": ["doença rara, raras, ultrararas, rara."],
        })
        result = check(df)
        # 'rara' aparece 2x como palavra isolada; 'raras' e 'ultrararas' não contam
        assert result["rara"].iloc[0] == 2


class TestValidarData:
    """Testes para validar_data() que normaliza strings de data."""

    def test_formato_iso(self):
        assert validar_data("2024-01-15") == "2024-01-15"

    def test_formato_brasileiro(self):
        assert validar_data("15/01/2024") == "2024-01-15"

    def test_formato_compacto(self):
        assert validar_data("20240115") == "2024-01-15"

    def test_none_retorna_none(self):
        assert validar_data(None) is None

    def test_string_vazia_retorna_none(self):
        assert validar_data("") is None

    def test_string_com_espacos_retorna_none(self):
        assert validar_data("   ") is None

    def test_formato_invalido_levanta_validation_error(self):
        with pytest.raises(ValidationError, match="formato inválido"):
            validar_data("15-01-2024")

    def test_data_impossivel_levanta_validation_error(self):
        """29/02/2023 não existe (2023 não é bissexto)."""
        with pytest.raises(ValidationError, match="data impossível"):
            validar_data("29/02/2023")

    def test_mes_invalido_levanta_validation_error(self):
        with pytest.raises(ValidationError, match="data impossível"):
            validar_data("15/13/2024")

    def test_nome_param_aparece_na_mensagem(self):
        with pytest.raises(ValidationError, match="data_inicio"):
            validar_data("abc", nome_param="data_inicio")


class TestValidarIntervaloDatas:
    """Testes para validar_intervalo_datas() que valida par (início, fim)."""

    def test_ambos_none(self):
        assert validar_intervalo_datas(None, None) == (None, None)

    def test_apenas_inicio(self):
        result = validar_intervalo_datas("2024-01-01", None)
        assert result == ("2024-01-01", None)

    def test_apenas_fim(self):
        result = validar_intervalo_datas(None, "2024-12-31")
        assert result == (None, "2024-12-31")

    def test_ordem_correta_normaliza_cross_formato(self):
        result = validar_intervalo_datas("01/01/2024", "20241231")
        assert result == ("2024-01-01", "2024-12-31")

    def test_ordem_invertida_levanta_validation_error(self):
        with pytest.raises(ValidationError, match="não pode ser posterior"):
            validar_intervalo_datas("2024-12-31", "2024-01-01")

    def test_nomes_personalizados_aparecem_na_mensagem(self):
        with pytest.raises(ValidationError, match="inicio_custom"):
            validar_intervalo_datas(
                "2024-12-31", "2024-01-01",
                nome_inicio="inicio_custom",
                nome_fim="fim_custom",
            )

    def test_propaga_validation_error_de_validar_data(self):
        with pytest.raises(ValidationError, match="formato inválido"):
            validar_intervalo_datas("invalida", "2024-12-31")
