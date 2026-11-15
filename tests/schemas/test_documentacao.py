"""``docs/colunas.md`` versionado tem de ser igual ao gerado pelos schemas."""

from pathlib import Path

import pytest

from raspe.schemas.documentacao import gerar_documento_colunas, main

DOCUMENTO = Path(__file__).resolve().parents[2] / "docs" / "colunas.md"


def test_documento_versionado_e_o_gerado():
    assert DOCUMENTO.read_text(encoding="utf-8") == gerar_documento_colunas(), (
        "docs/colunas.md diverge dos schemas. Regere com `python -m raspe.schemas.documentacao`."
    )


def test_main_grava_no_caminho_pedido(tmp_path):
    destino = tmp_path / "sub" / "colunas.md"
    main(["--saida", str(destino)])
    assert destino.read_text(encoding="utf-8") == gerar_documento_colunas()


def _repo(pasta, nome="raspe"):
    pasta.mkdir(parents=True)
    (pasta / "pyproject.toml").write_text(f'[project]\nname = "{nome}"\n', encoding="utf-8")
    return pasta


def test_main_sem_saida_grava_na_raiz_do_repo_de_qualquer_pasta(tmp_path, monkeypatch):
    """Rodado de uma subpasta, o padrão não cria um docs/colunas.md solto ali."""
    raiz = _repo(tmp_path / "raspe")
    subpasta = raiz / "src" / "raspe"
    subpasta.mkdir(parents=True)
    monkeypatch.chdir(subpasta)

    main([])

    assert (raiz / "docs" / "colunas.md").read_text(encoding="utf-8") == gerar_documento_colunas()
    assert not any(subpasta.iterdir())


def test_main_sem_saida_pula_o_pyproject_de_outro_projeto(tmp_path, monkeypatch):
    """Um projeto que vendoriza o raspe dentro do repo dele não vira destino por engano."""
    raiz = _repo(tmp_path / "raspe")
    _repo(raiz / "vendor" / "outro", nome="outro")
    monkeypatch.chdir(raiz / "vendor" / "outro")

    main([])

    assert (raiz / "docs" / "colunas.md").is_file()
    assert not (raiz / "vendor" / "outro" / "docs").exists()


def test_main_fora_do_repo_pede_saida(tmp_path, monkeypatch, capsys):
    """Fora do repo do raspe, não grava em lugar inesperado."""
    _repo(tmp_path / "outro", nome="outro")
    monkeypatch.chdir(tmp_path / "outro")
    with pytest.raises(SystemExit):
        main([])
    assert not (tmp_path / "outro" / "docs").exists()
    assert "passe --saida" in capsys.readouterr().err
