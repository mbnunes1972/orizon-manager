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


def test_html_ambientes_linhas_par_e_impar():
    from mod_contrato import _html_ambientes_linhas, _TRACO
    html = _html_ambientes_linhas([("Cozinha", 20000.0), ("Sala", 12000.0), ("Closet", 6000.0)])
    assert html.count("<tr") == 2                      # ceil(3/2)=2 linhas
    assert "Cozinha" in html and "R$ 20.000,00" in html
    assert "Sala" in html and "Closet" in html
    # sobra ímpar: 2ª metade da última linha em traços
    assert html.count(_TRACO) == 2                     # nome+valor vazios


def test_html_ambientes_linhas_vazio():
    from mod_contrato import _html_ambientes_linhas, _TRACO
    html = _html_ambientes_linhas([])
    assert html.count("<tr") == 1 and html.count(_TRACO) == 4
