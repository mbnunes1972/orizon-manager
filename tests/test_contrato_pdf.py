import importlib.util
import pytest

_weasy_ausente = importlib.util.find_spec("weasyprint") is None
skip_sem_weasy = pytest.mark.skipif(_weasy_ausente, reason="weasyprint não instalado")


def test_markdown_disponivel():
    import markdown  # noqa: F401


def test_subst_marcadores_html_substitui_e_mantem_desconhecido():
    from mod_contrato import _substituir_marcadores_html
    html = "<p>Nome: [NOME_CLIENTE] — Falta: [NAO_EXISTE]</p>"
    out = _substituir_marcadores_html(html, {"NOME_CLIENTE": "Ana Paula"})
    assert "Ana Paula" in out
    assert "[NAO_EXISTE]" in out
    assert "[NOME_CLIENTE]" not in out


def test_subst_marcadores_html_case_e_duplo_colchete():
    from mod_contrato import _substituir_marcadores_html
    out = _substituir_marcadores_html("N:[Num_Contrato] D:[[Data_Contrato]",
                                      {"NUM_CONTRATO": "INS-1", "DATA_CONTRATO": "02/07/2026"})
    assert "INS-1" in out and "02/07/2026" in out and "[" not in out
