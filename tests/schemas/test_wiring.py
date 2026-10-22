"""Wiring dos schemas em ``raspar()``: mensagens de erro, aliases e conferência de saída.

Os contratos por raspador cobrem o caminho feliz de cada um. Aqui ficam os
casos que valem para todos e que nenhum contrato exercita: cada tipo de erro
de validação vira uma linha legível, o alias avisa de dentro de ``scrape()`` e
dos raspadores com navegador, e a saída divergente do schema avisa sem jogar
fora os dados.
"""

import tempfile
from datetime import date
from typing import Literal
from unittest.mock import AsyncMock

import pandas as pd
import pytest
import responses

from raspe.exceptions import ScraperError, ValidationError
from raspe.schemas import InputPresidencia, OutputPresidencia, conferir_saida, descrever_tipo, validar_entrada
from raspe.scrapers.ans import ScraperANS
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.saudelegis import ScraperSaudeLegis
from tests._helpers import load_sample_bytes

URL_PRESIDENCIA = "https://legislacao.presidencia.gov.br/pesquisa/ajax/resultado_pesquisa_legislacao.php"


class TestMensagensDeErro:
    """Toda recusa sai antes de qualquer requisição; ``responses`` ativo sem rota prova isso."""

    @responses.activate
    def test_erro_de_validacao_herda_de_scraper_error(self):
        with pytest.raises(ScraperError):
            ScraperPresidencia().raspar(pesquisa="x", desconhecido=1)

    @responses.activate
    def test_pesquisa_ausente(self):
        with pytest.raises(ValidationError, match="'pesquisa': parâmetro obrigatório ausente"):
            ScraperPresidencia().raspar()

    @responses.activate
    def test_tipo_errado_descreve_o_tipo_esperado(self):
        with pytest.raises(ValidationError, match="valor 3 inválido; esperado texto ou lista de textos"):
            ScraperPresidencia().raspar(pesquisa=3)

    @responses.activate
    def test_valor_fora_da_lista_mostra_os_permitidos(self):
        with pytest.raises(ValidationError, match="esperado um de 'todos', 'online', 'jornal'"):
            ScraperFolha().raspar(pesquisa="x", site="impresso")

    @responses.activate
    def test_paginas_em_lista_pede_range(self):
        with pytest.raises(ValidationError, match=r"'paginas': valor \[1, 2\] inválido; esperado range ou nulo"):
            ScraperPresidencia().raspar(pesquisa="x", paginas=[1, 2])

    @pytest.mark.parametrize(
        ("paginas", "mensagem"),
        [
            (range(3, 0, -1), "não aceita range decrescente"),
            (range(3, 1), "não pode ser uma seleção vazia"),
            (range(0, 2), "começa em 1"),
        ],
    )
    @responses.activate
    def test_paginas_invalidas(self, paginas, mensagem):
        with pytest.raises(ValidationError, match=f"'paginas': 'paginas' {mensagem}"):
            ScraperPresidencia().raspar(pesquisa="x", paginas=paginas)

    def test_paginas_none_explicito_baixa_todas(self):
        parametros = validar_entrada(InputPresidencia, {"pesquisa": "x", "paginas": None}, metodo="m()")
        assert parametros == {"pesquisa": "x", "paginas": None}

    @responses.activate
    def test_varios_erros_saem_um_por_linha_com_os_aceitos(self):
        with pytest.raises(ValidationError) as erro:
            ScraperPresidencia().raspar(pesquisa=3, pagina=range(1, 2))
        assert str(erro.value).splitlines() == [
            "ScraperPresidencia.raspar() recebeu parâmetros inválidos:",
            "  - 'pesquisa': valor 3 inválido; esperado texto ou lista de textos",
            "  - 'pagina': parâmetro desconhecido (você quis dizer 'paginas'?)",
            "Parâmetros aceitos: pesquisa, paginas.",
        ]


class TestDescreverTipo:
    @pytest.mark.parametrize(
        ("anotacao", "descricao"),
        [
            (str, "texto"),
            (int | None, "inteiro ou nulo"),
            (bool, "booleano"),
            (str | date | None, "texto ou data ou nulo"),
            (list[str], "lista de textos"),
            (Literal["a", "b"], "um de 'a', 'b'"),
        ],
    )
    def test_tipos_conhecidos(self, anotacao, descricao):
        assert descrever_tipo(anotacao) == descricao

    def test_tipo_desconhecido_cai_na_representacao_do_python(self):
        assert descrever_tipo(float) == str(float)


class TestAliasDeprecado:
    def test_scrape_atribui_o_aviso_a_quem_chamou(self, mocker):
        """``scrape()`` acrescenta um frame do pacote; o aviso continua apontando para cá."""
        baixar = mocker.patch.object(ScraperCFM, "_download_data", return_value="inexistente")
        mocker.patch.object(ScraperCFM, "_parse_data", return_value=pd.DataFrame())
        with pytest.warns(DeprecationWarning, match="'texto'") as avisos:
            ScraperCFM().scrape(texto="x")
        assert avisos[0].filename == __file__
        assert baixar.call_args.kwargs["pesquisa"] == "x"


class TestNavegador:
    """Raspadores Playwright validam antes de abrir o navegador."""

    def test_alias_avisa_e_chega_canonico_ao_navegador(self, mocker):
        navegador = mocker.patch.object(ScraperSaudeLegis, "_raspar_async", new=AsyncMock(return_value=pd.DataFrame()))
        with pytest.warns(DeprecationWarning, match="'assunto'.*'pesquisa'") as avisos:
            df = ScraperSaudeLegis().raspar(assunto="doença rara")
        assert avisos[0].filename == __file__
        navegador.assert_awaited_once_with(pesquisa="doença rara")
        assert df.empty
        assert list(df.columns) == ScraperSaudeLegis.schema_saida.colunas()  # type: ignore[union-attr]

    @pytest.mark.parametrize(
        ("kwargs", "mensagem"),
        [
            ({"pesquisa": "x", "paginas": range(1, 3)}, "'paginas': parâmetro desconhecido"),
            ({"pesquisa": ["a", "b"]}, r"'pesquisa': valor \['a', 'b'\] inválido; esperado texto"),
        ],
    )
    def test_parametro_que_o_navegador_ignorava_agora_levanta(self, mocker, kwargs, mensagem):
        navegador = mocker.patch.object(ScraperANS, "_raspar_async", new=AsyncMock())
        with pytest.raises(ValidationError, match=mensagem):
            ScraperANS().raspar(**kwargs)
        navegador.assert_not_awaited()


class TestListaDePesquisa:
    @responses.activate
    def test_cada_item_da_lista_vira_termo_busca(self, mocker, tmp_path):
        mocker.patch("time.sleep")
        # O diretório de download leva o horário em segundos; sem a pausa real
        # entre requisições, os dois itens cairiam no mesmo diretório.
        mocker.patch.object(
            ScraperPresidencia, "_create_download_dir", side_effect=lambda: tempfile.mkdtemp(dir=tmp_path)
        )
        responses.add(
            responses.POST, URL_PRESIDENCIA,
            body=load_sample_bytes("presidencia", "raspar/single_page.html"),
            status=200,
            content_type="text/html; charset=utf-8",
        )
        df = ScraperPresidencia().raspar(pesquisa=["meio ambiente", "saúde"])
        assert list(df.columns) == OutputPresidencia.colunas()
        assert set(df["termo_busca"]) == {"meio ambiente", "saúde"}


class TestConferirSaida:
    def _df(self, **colunas):
        return pd.DataFrame({coluna: ["valor"] for coluna in colunas})

    def test_reordena_para_a_ordem_do_schema(self):
        colunas = OutputPresidencia.colunas()
        df = self._df(**{coluna: None for coluna in reversed(colunas)})
        assert list(conferir_saida(df, OutputPresidencia, metodo="m()").columns) == colunas

    def test_sem_linhas_devolve_as_colunas_do_schema(self):
        df = conferir_saida(pd.DataFrame(), OutputPresidencia, metodo="m()")
        assert df.empty
        assert list(df.columns) == OutputPresidencia.colunas()

    def test_colunas_divergentes_avisam_e_mantem_os_dados(self):
        colunas = [coluna for coluna in OutputPresidencia.colunas() if coluna != "link"] + ["extra"]
        df = self._df(**{coluna: None for coluna in colunas})
        with pytest.warns(UserWarning, match=r"faltando: \['link'\]; sobrando: \['extra'\]") as avisos:
            devolvido = conferir_saida(df, OutputPresidencia, metodo="ScraperPresidencia.raspar()")
        assert devolvido is df
        assert avisos[0].filename == __file__
