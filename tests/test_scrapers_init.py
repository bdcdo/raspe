"""Testes da reexportação dos raspadores em ``raspe.scrapers``.

``raspe/scrapers/__init__.py`` reexporta as classes de raspador para permitir
``from raspe.scrapers import ScraperCFM`` e promete que esse import funciona sem
o extra ``browser``: o Playwright só é carregado quando o navegador abre.
"""

import importlib
import inspect
import os
import pkgutil
import subprocess
import sys
import textwrap

import raspe.scrapers
from raspe.abstract_scraper import AbstractScraper


def _raspadores_definidos() -> dict[str, type]:
    """Nomes públicos que apontam para raspadores nos módulos de ``raspe.scrapers``.

    Um nome entra quando aponta para uma subclasse de ``AbstractScraper``
    definida no próprio módulo. Guardar o nome, e não só a classe, faz o alias
    ``IpeaScraper`` entrar sem lista escrita aqui; o filtro por ``__module__``
    descarta a classe base que um módulo importa de outro (``ans.py`` importa
    ``ScraperDatalegis`` de ``datalegis.py``), que é contada só no módulo onde
    nasce.
    """
    definidos: dict[str, type] = {}
    for info in pkgutil.iter_modules(raspe.scrapers.__path__):
        modulo = importlib.import_module(f"raspe.scrapers.{info.name}")
        for nome, obj in inspect.getmembers(modulo, inspect.isclass):
            if nome.startswith("_") or obj.__module__ != modulo.__name__:
                continue
            if issubclass(obj, AbstractScraper):
                definidos[nome] = obj
    return definidos


class TestReexportacao:
    def test_all_cobre_os_raspadores_dos_modulos(self):
        """Raspador novo em ``raspe/scrapers/`` precisa entrar no ``__all__``, e o ``__all__`` não lista sobra."""
        assert set(raspe.scrapers.__all__) == set(_raspadores_definidos())

    def test_cada_nome_do_all_resolve_para_a_classe_do_modulo(self):
        """Nome no ``__all__`` sem o import correspondente quebra ``from raspe.scrapers import *``."""
        definidos = _raspadores_definidos()
        for nome in raspe.scrapers.__all__:
            assert getattr(raspe.scrapers, nome) is definidos[nome], nome


# Roda num interpretador novo porque o processo da suíte já pode ter o
# Playwright em sys.modules (ele está instalado no ambiente de desenvolvimento),
# e aí um import antecipado passaria despercebido. O bloqueador em sys.meta_path
# faz o pacote se comportar como ausente, como na instalação sem o extra.
_SEM_PLAYWRIGHT = textwrap.dedent(
    """
    import importlib.abc
    import sys


    class BloqueiaPlaywright(importlib.abc.MetaPathFinder):
        def find_spec(self, nome, caminho, alvo=None):
            if nome.split(".")[0] in {"playwright", "playwright_stealth"}:
                raise ModuleNotFoundError(f"No module named {nome!r}")
            return None


    sys.meta_path.insert(0, BloqueiaPlaywright())

    import raspe.scrapers
    from raspe.exceptions import DriverNotInstalledError
    from raspe.scraper_manager import scraper

    for nome in raspe.scrapers.__all__:
        getattr(raspe.scrapers, nome)
    instancias = [scraper(fonte) for fonte in ("saudelegis", "ans", "anvisa")]

    carregados = sorted(m for m in sys.modules if m.startswith("playwright"))
    assert not carregados, f"Playwright carregado no import: {carregados}"

    try:
        instancias[1].raspar(termo="doença rara")
    except DriverNotInstalledError:
        pass
    else:
        raise AssertionError("raspar() sem Playwright deveria levantar DriverNotInstalledError")
    """
)


def test_import_e_instancia_sem_o_extra_browser(tmp_path):
    """``raspe.scrapers`` e ``scraper()`` funcionam sem Playwright até o navegador abrir."""
    # TMPDIR aponta para tmp_path para que os diretórios de download criados
    # pelos raspadores fiquem dentro da pasta temporária do teste.
    ambiente = {**os.environ, "TMPDIR": str(tmp_path)}
    resultado = subprocess.run(
        [sys.executable, "-c", _SEM_PLAYWRIGHT],
        cwd=tmp_path,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
