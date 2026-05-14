"""Testes unitários para AbstractScraper.

Usa uma subclasse mínima ``_DummyScraper`` para exercitar os métodos
concretos da classe abstrata (validação de parâmetros, logger,
``_create_download_dir``, ``_parse_data``, alias ``scrape``).
"""

import logging
import os
from typing import Literal

import pandas as pd
import pytest

from raspe.abstract_scraper import AbstractScraper
from raspe.exceptions import ValidationError


class _DummyScraper(AbstractScraper):
    """Subclasse concreta mínima para testes."""

    @property
    def type(self) -> Literal['HTML']:
        return 'HTML'

    def _parse_page(self, path: str) -> pd.DataFrame:
        # Lê o arquivo e devolve um DataFrame com o conteúdo
        with open(path, "r", encoding="utf-8") as f:
            return pd.DataFrame({"path": [path], "content": [f.read()]})

    def raspar(self, **kwargs) -> pd.DataFrame:
        # Implementação trivial para satisfazer o ABC
        return pd.DataFrame()


class TestInit:
    def test_atributos_basicos(self):
        s = _DummyScraper("test_scraper", debug=False)
        assert s.nome_buscador == "test_scraper"
        assert s.debug is False
        assert s.exclude_cols_from_dedup == []
        assert os.path.isdir(s.download_path)

    def test_logger_configurado(self):
        s = _DummyScraper("logger_test", debug=True)
        assert isinstance(s.logger, logging.Logger)
        assert s.logger.name == "logger_test"
        assert s.logger.level == logging.DEBUG

    def test_logger_em_modo_info_quando_debug_off(self):
        s = _DummyScraper("logger_info", debug=False)
        assert s.logger.level == logging.INFO

    def test_logger_nao_propaga(self):
        """Para evitar duplicação de logs com o root logger."""
        s = _DummyScraper("propagate_test")
        assert s.logger.propagate is False


class TestValidarParametros:
    def test_passa_kwargs_sem_datas(self):
        s = _DummyScraper("v1")
        params = s._validar_parametros(pesquisa="termo", ano=2024)
        assert params == {"pesquisa": "termo", "ano": 2024}

    def test_normaliza_data_inicio_e_fim(self):
        s = _DummyScraper("v2")
        params = s._validar_parametros(data_inicio="01/01/2024", data_fim="31/12/2024")
        assert params["data_inicio"] == "2024-01-01"
        assert params["data_fim"] == "2024-12-31"

    def test_aliases_begin_end_date(self):
        s = _DummyScraper("v3")
        params = s._validar_parametros(begin_date="20240101", end_date="20241231")
        assert params["begin_date"] == "2024-01-01"
        assert params["end_date"] == "2024-12-31"

    def test_aliases_inicio_fim(self):
        s = _DummyScraper("v4")
        params = s._validar_parametros(inicio="01/01/2024", fim="31/12/2024")
        assert params["inicio"] == "2024-01-01"
        assert params["fim"] == "2024-12-31"

    def test_apenas_data_inicio_sem_fim(self):
        s = _DummyScraper("v5")
        params = s._validar_parametros(data_inicio="2024-01-01")
        assert params["data_inicio"] == "2024-01-01"

    def test_data_invalida_propaga_validation_error(self):
        s = _DummyScraper("v6")
        with pytest.raises(ValidationError):
            s._validar_parametros(data_inicio="abc", data_fim="2024-12-31")

    def test_ordem_invertida_propaga_validation_error(self):
        s = _DummyScraper("v7")
        with pytest.raises(ValidationError, match="não pode ser posterior"):
            s._validar_parametros(data_inicio="2024-12-31", data_fim="2024-01-01")


class TestCreateDownloadDir:
    def test_cria_diretorio(self):
        s = _DummyScraper("dl")
        path = s._create_download_dir()
        assert os.path.isdir(path)
        assert s.nome_buscador in path

    def test_chamadas_sequenciais_geram_paths_diferentes(self, mocker):
        """Mock datetime para garantir timestamps distintos."""
        s = _DummyScraper("dl2")
        fake_dates = iter(["20240101120000", "20240101120001"])

        def fake_now():
            class _F:
                @staticmethod
                def strftime(_fmt):
                    return next(fake_dates)
            return _F()

        mocker.patch("raspe.abstract_scraper.datetime", **{"now": fake_now})
        p1 = s._create_download_dir()
        p2 = s._create_download_dir()
        assert p1 != p2


class TestParseData:
    def test_consolida_arquivos_html(self, tmp_path):
        s = _DummyScraper("pd1")
        f1 = tmp_path / "a.html"
        f2 = tmp_path / "b.html"
        f1.write_text("conteudo A", encoding="utf-8")
        f2.write_text("conteudo B", encoding="utf-8")

        df = s._parse_data(str(tmp_path))
        assert len(df) == 2
        assert {"conteudo A", "conteudo B"} <= set(df["content"])

    def test_diretorio_vazio_retorna_df_vazio(self, tmp_path):
        s = _DummyScraper("pd2")
        df = s._parse_data(str(tmp_path))
        assert df.empty

    def test_erro_em_arquivo_isolado_nao_aborta(self, tmp_path, mocker):
        """Se _parse_page levantar, o arquivo é ignorado mas os demais entram."""
        s = _DummyScraper("pd3")
        f1 = tmp_path / "ok.html"
        f2 = tmp_path / "broken.html"
        f1.write_text("ok", encoding="utf-8")
        f2.write_text("broken", encoding="utf-8")

        original_parse = s._parse_page

        def maybe_fail(path):
            if "broken" in path:
                raise ValueError("simulated parse error")
            return original_parse(path)

        mocker.patch.object(s, "_parse_page", side_effect=maybe_fail)

        df = s._parse_data(str(tmp_path))
        assert len(df) == 1
        assert df.iloc[0]["content"] == "ok"


class TestScrapeAlias:
    def test_scrape_chama_raspar(self, mocker):
        s = _DummyScraper("alias")
        mock_raspar = mocker.patch.object(s, "raspar", return_value=pd.DataFrame({"x": [1]}))
        result = s.scrape(termo="x")
        mock_raspar.assert_called_once_with(termo="x")
        assert len(result) == 1
