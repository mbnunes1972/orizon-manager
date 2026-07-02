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


def test_html_parcelas_linhas_elimina_vazias_e_tracos():
    from mod_contrato import _html_parcelas_linhas, _TRACO
    pag = {"tipo": "aymore", "num_parcelas_int": 4,
           "valores": ["R$ 4.000,00"] * 4 + [""] * 20,
           "datas": ["10/08/2026", "10/09/2026", "10/10/2026", "10/11/2026"] + [""] * 20}
    html = _html_parcelas_linhas(pag)
    assert html.count("<tr") == 2                       # 4 parcelas -> ceil(4/3)=2 linhas
    assert "R$ 4.000,00" in html and "10/08/2026" in html
    assert _TRACO in html                               # slots 5,6 vazios na 2a linha


def test_html_parcelas_linhas_cartao_sem_data():
    from mod_contrato import _html_parcelas_linhas
    pag = {"tipo": "cartao", "num_parcelas_int": 3,
           "valores": ["R$ 100,00"] * 3 + [""] * 21, "datas": [""] * 24}
    html = _html_parcelas_linhas(pag)
    assert html.count("<tr") == 1 and html.count("R$ 100,00") == 3


def test_nivel_clausula():
    from mod_contrato import _nivel_clausula
    assert _nivel_clausula("2. Após a assinatura...") == 1
    assert _nivel_clausula("2.3. A execução...") == 2
    assert _nivel_clausula("2.3.1. O Termo...") == 3
    assert _nivel_clausula("a) MEDIÇÃO: ...") == 4
    assert _nivel_clausula("Texto sem número") is None


def test_html_corpo_aplica_classe_por_nivel():
    from mod_contrato import _html_corpo
    md = "# CLÁUSULA PRIMEIRA\n\n1. Item um.\n\n1.1. Sub item.\n\na) alinea.\n"
    html = _html_corpo(md)
    assert "<h1" in html
    assert 'class="cl-1"' in html and "Item um" in html
    assert 'class="cl-2"' in html and "Sub item" in html
    assert 'class="cl-alinea"' in html and "alinea" in html
    assert "<li>" not in html and "<ol>" not in html   # não vira lista ordenada


def test_assets_template_existem():
    import os
    from mod_contrato import CONTRATO_TEMPLATE_DIR
    for f in ("contrato.css", "contrato.html", "logo_dalmobile.png"):
        assert os.path.exists(os.path.join(CONTRATO_TEMPLATE_DIR, f)), f
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"), encoding="utf-8").read()
    assert "<!--CAPA-->" in shell and "<!--CORPO-->" in shell


def test_montar_html_contrato_substitui_e_inclui_secoes():
    import json
    from mod_contrato import construir_contexto, _montar_html_contrato
    loja = {"nome": "L", "cnpj": "1", "codigo": "INS",
            "testemunha1_nome": "J", "testemunha1_cpf": "1",
            "testemunha2_nome": "F", "testemunha2_cpf": "2"}
    ctx = construir_contexto(
        {"nome": "Ana Paula", "cpf": "111.222.333-44", "email": "a@x.com",
         "telefone": "(12)9", "logradouro": "Rua A", "numero": "10", "complemento": "",
         "bairro": "Jardim Aquarius", "cidade": "SJC", "cep": "12000", "estado": "SP",
         "inst_mesmo_residencial": True},
        {"nome": "Z", "telefone": "(12)9", "email": "z@x.com"},
        json.dumps({"tipo": "aymore", "nome_forma": "Aymoré", "total_cliente": 26445.67,
                    "parcelas": [{"num": i + 1, "data": f"18/0{7+i}/2026", "valor": 4820.0}
                                 for i in range(3)]}),
        loja)
    ctx["num_contrato"] = "INS-1"
    ctx["adendo"] = "Acordo especial de entrega."
    ctx["_ambientes"] = [("Cozinha", 12345.67), ("Sala", 14100.0)]
    html = _montar_html_contrato(ctx)
    assert "Ana Paula" in html and "Jardim Aquarius" in html
    assert "Cozinha" in html and "R$ 12.345,67" in html
    assert "R$ 4.820,00" in html                     # parcela
    assert "[" not in html.split("contrato-corpo")[0] or "NOME_" not in html  # marcadores da capa consumidos
