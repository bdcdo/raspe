"""O erro de leitura de uma página, ou dos itens dela, chega a quem chamou.

Cada ``_parse_page`` deixa a exceção da página subir, e o ``_parse_data`` a põe na
mensagem do ``ScraperError`` (todas as páginas falharam) ou do aviso (parte delas).
O erro de um item, que o ``_parse_page`` pula para não perder os demais, sobe por
``_conferir_itens``: ``ScraperError`` se nenhum item da página foi lido, aviso se parte foi.
"""

import ast
import inspect
import textwrap
from collections.abc import Callable

import pytest
from bs4 import BeautifulSoup, Tag
from pytest_mock import MockerFixture

from raspe.abstract_scraper import AbstractScraper
from raspe.exceptions import ScraperError
from raspe.schemas.documentacao import descobrir_raspadores, fabricas_por_raspador
from raspe.scrapers.camara import ScraperCamaraDeputados
from raspe.scrapers.capes import ScraperCapes
from raspe.scrapers.cfm import ScraperCFM
from raspe.scrapers.folha import ScraperFolha
from raspe.scrapers.ipea import ScraperIpea
from raspe.scrapers.nyt import ScraperNYT
from raspe.scrapers.presidencia import ScraperPresidencia
from raspe.scrapers.senado import ScraperSenadoFederal
from tests._helpers import load_sample

# Todo raspador com fábrica pública, inclusive os que herdam o _parse_page (ANS e ANVISA, do
# ScraperDatalegis), para um raspador novo não ficar fora.
RASPADORES = [classe for classe in descobrir_raspadores() if classe.__name__ in fabricas_por_raspador()]

TODOS = 10**6


def _construir(classe: type[AbstractScraper], mocker: MockerFixture) -> AbstractScraper:
    """Cria o raspador sem rede (o construtor da Câmara visita o portal)."""
    mocker.patch.object(ScraperCamaraDeputados, "_prep_scrape", return_value={})
    return classe(api_key="x") if classe is ScraperNYT else classe()


@pytest.mark.parametrize("classe", RASPADORES, ids=lambda c: c.__name__)
def test_pagina_ilegivel_leva_o_erro_original_ao_scraper_error(classe: type[AbstractScraper], mocker, tmp_path):
    raspador = _construir(classe, mocker)
    # Bytes que não são UTF-8: a leitura do arquivo falha com UnicodeDecodeError.
    (tmp_path / f"pagina_00001.{raspador.type.lower()}").write_bytes(b"\xff\xfe\x00 quebrado")
    with pytest.raises(ScraperError, match=r"pagina_00001\.\w+ \(UnicodeDecodeError: ") as erro:
        raspador._parse_data(str(tmp_path))
    assert isinstance(erro.value.__cause__, UnicodeDecodeError)


def test_ans_e_anvisa_estao_na_lista():
    """Os dois herdam o _parse_page do ScraperDatalegis; a lista não pode depender de quem o define."""
    assert {"ScraperANS", "ScraperANVISA"} <= {classe.__name__ for classe in RASPADORES}


class TestConferirItens:
    """``AbstractScraper._conferir_itens``, o caminho do erro de item até quem chamou."""

    def test_sem_erro_nao_faz_nada(self):
        ScraperPresidencia()._conferir_itens("p.html", [], 0)

    def test_todos_os_itens_com_erro_levanta_com_a_causa(self):
        causa = KeyError("href")
        with pytest.raises(ScraperError, match=r"^2 de 2 itens não puderam ser lidos \(o primeiro: KeyError") as e:
            ScraperPresidencia()._conferir_itens("/x/p.html", [causa, ValueError()], 0)
        assert e.value.__cause__ is causa

    def test_parte_dos_itens_com_erro_avisa_quem_chamou(self):
        padrao = r"PRESIDENCIA: em p\.html, 1 de 10 itens não puderam ser lidos .* fora do resultado"
        with pytest.warns(UserWarning, match=padrao) as avisos:
            ScraperPresidencia()._conferir_itens("/x/p.html", [KeyError("href")], 9)
        assert avisos[0].filename == __file__


Quebrar = Callable[[MockerFixture, int, str], None]


def _quebrar_tag(metodo: str, e_item: Callable[[Tag], bool]) -> Quebrar:
    """Faz ``Tag.<metodo>`` levantar ``RuntimeError`` nas ``vezes`` primeiras chamadas sobre um item.

    Como a exceção interrompe o item, ``vezes=1`` quebra só o primeiro item da página.
    """

    def quebrar(mocker: MockerFixture, vezes: int, _caminho: str) -> None:
        original = getattr(Tag, metodo)
        chamadas = 0

        def quebrado(self, *args, **kwargs):
            nonlocal chamadas
            if e_item(self) and chamadas < vezes:
                chamadas += 1
                raise RuntimeError("item quebrado")
            return original(self, *args, **kwargs)

        mocker.patch.object(Tag, metodo, quebrado)

    return quebrar


def _quebrar_metodo(classe: type, metodo: str) -> Quebrar:
    """Quebra um método do raspador chamado uma vez por item (``_parse_card``, ``_parse_article``)."""

    def quebrar(mocker: MockerFixture, vezes: int, _caminho: str) -> None:
        original = getattr(classe, metodo)
        chamadas = 0

        def quebrado(self, item):
            nonlocal chamadas
            chamadas += 1
            if chamadas <= vezes:
                raise RuntimeError("item quebrado")
            return original(self, item)

        mocker.patch.object(classe, metodo, quebrado)

    return quebrar


def _senado_sem_h3(_mocker: MockerFixture, vezes: int, caminho: str) -> None:
    """Troca o ``<h3>`` dos ``vezes`` primeiros itens do Senado por ``<h4>``, e eles levantam ``ValueError``.

    Quebrar ``Tag`` não serve aqui: o ``except`` do Senado relê o item para o diagnóstico.
    """
    with open(caminho, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
    for item in soup.select("div.sf-busca-resultados-item")[:vezes]:
        item.h3.name = "h4"  # type: ignore[union-attr]
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(str(soup))


def _e_li(tag: Tag) -> bool:
    return tag.name == "li"


# Raspador -> (pasta dos samples, como quebrar os itens da página típica).
ITENS: dict[type[AbstractScraper], tuple[str, Quebrar]] = {
    ScraperCamaraDeputados: ("camara", _quebrar_tag("find", _e_li)),
    ScraperCapes: ("capes", _quebrar_metodo(ScraperCapes, "_parse_card")),
    ScraperCFM: ("cfm", _quebrar_metodo(ScraperCFM, "_parse_article")),
    ScraperFolha: ("folha", _quebrar_tag("find", _e_li)),
    ScraperIpea: ("ipea", _quebrar_tag("find", lambda t: "row" in (t.get("class") or []))),
    ScraperPresidencia: ("presidencia", _quebrar_tag("select_one", lambda t: t.name == "div")),
    ScraperSenadoFederal: ("senado", _senado_sem_h3),
}


def _pula_item(classe: type) -> bool:
    """Reconhece laços com ``except`` no parser ou em um método dele da mesma classe."""
    metodo = classe._parse_page
    nomes = {"_parse_page"}
    arvore = ast.parse(textwrap.dedent(inspect.getsource(metodo)))
    nomes.update(
        chamada.func.attr
        for chamada in ast.walk(arvore)
        if isinstance(chamada, ast.Call)
        and isinstance(chamada.func, ast.Attribute)
        and isinstance(chamada.func.value, ast.Name)
        and chamada.func.value.id == "self"
        and chamada.func.attr in classe.__dict__
    )
    for nome in nomes:
        candidato = getattr(classe, nome)
        codigo = ast.parse(textwrap.dedent(inspect.getsource(candidato)))
        for no in ast.walk(codigo):
            if isinstance(no, (ast.For, ast.AsyncFor)) and any(
                isinstance(filho, ast.Try) and filho.handlers for filho in ast.walk(no)
            ):
                return True
    return False


def test_todo_raspador_que_pula_item_esta_em_itens():
    """Quem trata exceção por item entra em ``ITENS``, que cobra ``_conferir_itens``."""
    com_except = {classe for classe in RASPADORES if _pula_item(classe)}
    assert com_except == set(ITENS)


def test_guarda_reconhece_except_estreito_e_helper():
    class ExcecaoEstreita:
        def _parse_page(self):
            for item in []:
                try:
                    print(item)
                except ValueError:
                    continue

    class LacoNoHelper:
        def _parse_page(self):
            return self._ler_itens()

        def _ler_itens(self):
            for item in []:
                try:
                    print(item)
                except ValueError:
                    continue

    class ZeroLegitimo:
        def _parse_page(self):
            for item in []:
                print(item)

    assert _pula_item(ExcecaoEstreita)
    assert _pula_item(LacoNoHelper)
    assert not _pula_item(ZeroLegitimo)


def test_senado_diagnostico_quebrado_preserva_erro_e_linhas(mocker, tmp_path):
    caminho = _pagina(tmp_path, "senado")
    original = Tag.find
    chamadas = 0

    def encontrar(self, name=None, *args, **kwargs):
        nonlocal chamadas
        if (name == "h3" and "sf-busca-resultados-item" in self.get("class", [])
                and "Norma 1" in self.get_text()):
            chamadas += 1
            if chamadas == 1:
                raise ValueError("erro original")
            if chamadas == 2:
                raise RuntimeError("diagnóstico quebrado")
        return original(self, name, *args, **kwargs)

    mocker.patch.object(Tag, "find", encontrar)
    with pytest.warns(UserWarning, match=r"1 de 2 itens.*ValueError: erro original"):
        df = ScraperSenadoFederal()._parse_page(caminho)
    assert not df.empty
    assert chamadas == 1


def _pagina(tmp_path, pasta: str) -> str:
    caminho = tmp_path / "pagina_00001.html"
    caminho.write_text(load_sample(pasta, "raspar/page_01.html"), encoding="utf-8")
    return str(caminho)


@pytest.mark.parametrize("classe", list(ITENS), ids=lambda c: c.__name__)
class TestErroDeItem:
    def test_todos_os_itens_quebrados_levam_a_causa_ao_scraper_error(self, classe, mocker, tmp_path):
        raspador = _construir(classe, mocker)
        pasta, quebrar = ITENS[classe]
        quebrar(mocker, TODOS, _pagina(tmp_path, pasta))
        padrao = r"pagina_00001\.html \(ScraperError: \d+ de \d+ itens não puderam ser lidos \(o primeiro: "
        with pytest.raises(ScraperError, match=padrao) as e:
            raspador._parse_data(str(tmp_path))
        assert isinstance(e.value.__cause__, ScraperError)
        assert isinstance(e.value.__cause__.__cause__, (RuntimeError, ValueError))

    def test_um_item_quebrado_avisa_e_mantem_os_demais(self, classe, mocker, tmp_path):
        raspador = _construir(classe, mocker)
        pasta, quebrar = ITENS[classe]
        caminho = _pagina(tmp_path, pasta)
        inteira = len(raspador._parse_page(caminho))
        quebrar(mocker, 1, caminho)
        with pytest.warns(UserWarning, match=r"em pagina_00001\.html, 1 de \d+ itens não puderam ser lidos"):
            df = raspador._parse_page(caminho)
        assert len(df) == inteira - 1
