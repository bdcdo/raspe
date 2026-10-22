"""``docs/colunas.md`` versionado tem de ser igual ao gerado pelos schemas."""

from pathlib import Path

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
