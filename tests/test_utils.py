import os
import re
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# Import functions from utils.py
from raspe.utils import expand


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
            # Combinações de singular + singular
            'doença rara', 'doença ultrarrara',
            'síndrome rara', 'síndrome ultrarrara',
            'patologia rara', 'patologia ultrarrara',

            # Combinações de plural + plural
            'doenças raras', 'doenças ultrarraras',
            'síndromes raras', 'síndromes ultrarraras',
            'patologias raras', 'patologias ultrarraras',

            # Outras combinações
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
