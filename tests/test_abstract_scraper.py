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
from pydantic import Field

from raspe.abstract_scraper import AbstractScraper, _HandlerRaspe
from raspe.exceptions import ScraperError, ValidationError
from raspe.schemas.base import OutputBase, PesquisaObrigatoriaMixin
from raspe.schemas.documentacao import descobrir_raspadores


class _DummyScraper(AbstractScraper):
    """Subclasse concreta mínima para testes."""

    @property
    def type(self) -> Literal['HTML']:
        return 'HTML'

    def _parse_page(self, path: str) -> pd.DataFrame:
        # Lê o arquivo e devolve um DataFrame com o conteúdo
        with open(path, "r", encoding="utf-8") as f:
            return pd.DataFrame({"path": [path], "content": [f.read()]})

    def _raspar(self, **kwargs) -> pd.DataFrame:
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
        assert s.logger.name == "raspe.logger_test"
        assert s.logger.logger.parent is logging.getLogger("raspe")
        assert s.logger.level == logging.DEBUG

    def test_logger_em_modo_info_quando_debug_off(self):
        s = _DummyScraper("logger_info", debug=False)
        assert s.logger.level == logging.INFO

    def test_logger_nao_propaga(self):
        """Para evitar duplicação de logs com o root logger."""
        assert logging.getLogger("raspe").propagate is False

    def test_logger_nao_empilha_handler_por_instancia(self, capsys):
        """Instâncias com o mesmo nome compartilham o logger; cada mensagem sai uma vez só."""
        primeiro = _DummyScraper("handler_unico", debug=False)
        segundo = _DummyScraper("handler_unico", debug=True)
        assert primeiro.logger.logger is segundo.logger.logger
        assert sum(isinstance(h, _HandlerRaspe) for h in logging.getLogger("raspe").handlers) == 1
        segundo.logger.warning("aviso único")
        assert capsys.readouterr().err.count("aviso único") == 1

    def test_nivel_e_de_cada_instancia(self, capsys):
        """Criar uma instância com debug=True não liga o DEBUG da anterior, e vice-versa."""
        silenciosa = _DummyScraper("nivel_proprio", debug=False)
        detalhada = _DummyScraper("nivel_proprio", debug=True)
        silenciosa.logger.debug("debug da silenciosa")
        detalhada.logger.debug("debug da detalhada")
        err = capsys.readouterr().err
        assert "debug da silenciosa" not in err
        assert "debug da detalhada" in err

        detalhada.logger.setLevel("WARNING")
        detalhada.logger.info("info depois do setLevel")
        silenciosa.logger.info("info da silenciosa")
        err = capsys.readouterr().err
        assert "info depois do setLevel" not in err
        assert "info da silenciosa" in err

    def test_set_level_valida_o_nome_e_get_effective_level_reflete_a_instancia(self):
        s = _DummyScraper("nivel_invalido", debug=False)
        assert s.logger.getEffectiveLevel() == logging.INFO
        with pytest.raises(ValueError, match="warning"):
            s.logger.setLevel("warning")
        s.logger.setLevel(logging.ERROR)
        assert s.logger.getEffectiveLevel() == logging.ERROR

    def test_api_de_logger_vai_para_o_logger_da_fonte(self):
        """Quem usava ``raspador.logger.addHandler`` continua funcionando."""
        s = _DummyScraper("api_logger")
        extra = logging.NullHandler()
        s.logger.addHandler(extra)
        try:
            assert extra in s.logger.handlers
            assert extra in logging.getLogger("raspe.api_logger").handlers
        finally:
            s.logger.removeHandler(extra)

    def test_nova_instancia_nao_desfaz_configuracao_do_usuario(self):
        """O raspe configura o logger ``raspe`` uma vez; criar raspadores não sobrescreve o propagate do usuário."""
        raiz = logging.getLogger("raspe")
        try:
            raiz.propagate = True
            _DummyScraper("propagate_usuario")
            assert raiz.propagate is True
            assert sum(isinstance(h, _HandlerRaspe) for h in raiz.handlers) == 1
        finally:
            raiz.propagate = False

    def test_nivel_do_logger_raspe_vale_para_todas_as_fontes(self, capsys):
        """O usuário silencia o raspe inteiro pelo logger pai, e novas instâncias respeitam isso."""
        raiz = logging.getLogger("raspe")
        nivel_antigo = raiz.level
        try:
            raiz.setLevel(logging.WARNING)
            s = _DummyScraper("silenciado", debug=True)
            s.logger.info("info escondido")
            s.logger.warning("aviso visível")
            err = capsys.readouterr().err
            assert "info escondido" not in err
            assert "aviso visível" in err
        finally:
            raiz.setLevel(nivel_antigo)


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
    def test_cria_diretorio_dentro_da_pasta_do_buscador(self):
        s = _DummyScraper("dl")
        path = s._create_download_dir()
        assert os.path.isdir(path)
        assert os.path.dirname(path) == os.path.join(s.download_path, s.nome_buscador)

    def test_chamadas_no_mesmo_segundo_geram_paths_diferentes(self, mocker):
        """Relógio parado: o timestamp repete e o sufixo aleatório desempata."""
        from datetime import datetime as real_datetime

        s = _DummyScraper("dl2")
        mock_dt = mocker.patch("raspe.abstract_scraper.datetime")
        mock_dt.now.return_value = real_datetime(2024, 1, 1, 12, 0, 0)

        p1 = s._create_download_dir()
        p2 = s._create_download_dir()

        assert p1 != p2
        for path in (p1, p2):
            assert os.path.isdir(path)
            assert os.path.basename(path).startswith("20240101120000_")


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

    def test_diretorio_vazio_traz_as_colunas_do_scraper(self, tmp_path):
        """Busca sem resultados devolve as colunas esperadas, não um DataFrame sem colunas."""
        s = _DummyScraper("pd2b")
        s.colunas = ["path", "content"]
        df = s._parse_data(str(tmp_path))
        assert df.empty
        assert list(df.columns) == ["path", "content"]

    def test_erro_em_arquivo_isolado_nao_aborta_e_avisa(self, tmp_path, mocker):
        """Se _parse_page levantar, os demais arquivos entram e o resultado vem com aviso."""
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

        with pytest.warns(UserWarning, match=r"1 de 2 páginas .*broken\.html \(ValueError: simulated parse error\)"):
            df = s._parse_data(str(tmp_path))
        assert len(df) == 1
        assert df.iloc[0]["content"] == "ok"

    def test_pagina_sem_linhas_avisa(self, tmp_path, mocker):
        """Página baixada que não rende linhas (bloqueio, layout novo) não some em silêncio."""
        s = _DummyScraper("pd4")
        (tmp_path / "a.html").write_text("ok", encoding="utf-8")
        (tmp_path / "b.html").write_text("", encoding="utf-8")
        original_parse = s._parse_page
        mocker.patch.object(
            s, "_parse_page",
            side_effect=lambda p: pd.DataFrame(columns=["content"]) if p.endswith("b.html") else original_parse(p),
        )
        with pytest.warns(UserWarning, match=r"1 de 2 páginas .*b\.html") as avisos:
            df = s._parse_data(str(tmp_path))
        assert len(df) == 1
        assert avisos[0].filename == __file__

    def test_nenhuma_pagina_lida_levanta_erro(self, tmp_path, mocker):
        """Se todas as páginas falham no _parse_page, o resultado não pode parecer busca vazia."""
        s = _DummyScraper("pd5")
        (tmp_path / "a.html").write_text("x", encoding="utf-8")
        (tmp_path / "b.html").write_text("y", encoding="utf-8")
        mocker.patch.object(s, "_parse_page", side_effect=ValueError("layout novo"))
        with pytest.raises(ScraperError, match=r"nenhuma das 2 páginas.*a\.html \(ValueError: layout novo\)") as erro:
            s._parse_data(str(tmp_path))
        assert isinstance(erro.value.__cause__, ValueError)

    def test_mensagem_lista_ate_cinco_paginas(self, tmp_path, mocker):
        """Numa busca longa, a lista de páginas com erro não afoga o traceback."""
        s = _DummyScraper("pd6")
        for i in range(8):
            (tmp_path / f"p{i}.html").write_text("x", encoding="utf-8")
        mocker.patch.object(s, "_parse_page", side_effect=ValueError("layout novo"))
        with pytest.raises(ScraperError, match=r"p4\.html \(ValueError: layout novo\); e mais 3\.") as erro:
            s._parse_data(str(tmp_path))
        assert "p5.html" not in str(erro.value)


class TestPaginasPara:
    @pytest.mark.parametrize("total, paginas", [(0, 0), (1, 1), (10, 1), (11, 2), (101, 11)])
    def test_arredonda_para_cima(self, total, paginas):
        assert _DummyScraper("pp1")._paginas_para(total, 10) == paginas

    def test_total_zero_com_zero_por_pagina_da_zero(self):
        """A contagem "Mostrando 0 a 0 de 0" dá tamanho de página 0, e a conta não pode dividir por ele."""
        assert _DummyScraper("pp4")._paginas_para(0, 0, 0) == 0

    def test_no_teto_corta_e_avisa(self):
        with pytest.warns(UserWarning, match="PP2: a busca deu 1,500 resultados, mas o limite é 1,000") as avisos:
            assert _DummyScraper("PP2")._paginas_para(1500, 10, 1000) == 100
        assert avisos[0].filename == __file__

    def test_no_teto_exato_nao_avisa(self):
        """Com a contagem exata (Câmara, NYT), chegar ao teto ainda é o resultado completo."""
        assert _DummyScraper("pp3")._paginas_para(1000, 10, 1000) == 100


class TestScrapeAlias:
    def test_scrape_chama_raspar(self, mocker):
        s = _DummyScraper("alias")
        mock_raspar = mocker.patch.object(s, "raspar", return_value=pd.DataFrame({"x": [1]}))
        result = s.scrape(termo="x")
        mock_raspar.assert_called_once_with(termo="x")
        assert len(result) == 1


class _InputDummy(PesquisaObrigatoriaMixin):
    """Entrada mínima para exercitar o ``raspar()`` da base."""


class _OutputDummy(OutputBase):
    """Saída mínima: uma coluna da fonte, mais ``termo_busca``."""

    valor: str = Field(description="Valor.", examples=["x"])


class _DummyComSchema(_DummyScraper):
    schema_entrada = _InputDummy
    schema_saida = _OutputDummy


class TestRasparUnico:
    """``AbstractScraper.raspar`` valida, chama ``_raspar`` e confere a saída, para todo raspador."""

    def test_parametro_invalido_levanta_sem_chamar_raspar(self, mocker):
        s = _DummyComSchema("unico_invalido")
        coleta = mocker.patch.object(s, "_raspar")
        with pytest.raises(ValidationError, match="'desconhecido': parâmetro desconhecido"):
            s.raspar(pesquisa="x", desconhecido=1)
        coleta.assert_not_called()

    def test_raspar_recebe_os_parametros_validados_e_a_saida_e_conferida(self, mocker):
        s = _DummyComSchema("unico_conferido")
        coleta = mocker.patch.object(
            s, "_raspar", return_value=pd.DataFrame({"termo_busca": ["x"], "valor": ["v"]})
        )
        df = s.raspar(pesquisa="x")
        coleta.assert_called_once_with(pesquisa="x")
        assert list(df.columns) == ["valor", "termo_busca"]

    def test_saida_vazia_ganha_as_colunas_do_schema(self, mocker):
        s = _DummyComSchema("unico_vazio")
        mocker.patch.object(s, "_raspar", return_value=pd.DataFrame())
        assert list(s.raspar(pesquisa="x").columns) == ["valor", "termo_busca"]

    def test_sem_schema_devolve_o_resultado_como_veio(self, mocker):
        s = _DummyScraper("unico_sem_schema")
        esperado = pd.DataFrame({"qualquer": [1]})
        mocker.patch.object(s, "_raspar", return_value=esperado)
        assert s.raspar(termo="x") is esperado

    @pytest.mark.parametrize("classe", descobrir_raspadores(), ids=lambda classe: classe.__name__)
    def test_nenhum_raspador_sobrescreve_raspar(self, classe):
        """Sobrescrever ``raspar`` pularia a validação ou a conferência; o ponto de extensão é ``_raspar``."""
        assert classe.raspar is AbstractScraper.raspar
