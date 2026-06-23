# tests/test_qualidade_xml.py
import os
import pytest
import mod_qualidade_xml as q

_LELEU_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PROJETOS", "LELEU", "xmls")
_skip_leleu = pytest.mark.skipif(not os.path.isdir(_LELEU_DIR), reason="XMLs LELEU nao versionados (PROJETOS/ no .gitignore)")

def test_acrescimo_zerado_bloqueia():
    itens = [{"order_total": 100.0, "budget_total": 100.0},   # markup 1.0
             {"order_total": 50.0,  "budget_total": 50.0}]
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "bloqueado"
    assert r["qa_pct_sem_acrescimo"] == 100.0

def test_markup_saudavel_ok():
    itens = [{"order_total": 100.0, "budget_total": 278.0},
             {"order_total": 50.0,  "budget_total": 139.0}]
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "ok" and r["qa_pct_sem_acrescimo"] == 0.0

def test_custo_sem_venda_bloqueia():
    itens = [{"order_total": 100.0, "budget_total": 300.0},   # bom
             {"order_total": 80.0,  "budget_total": 0.0}]     # paga e nao vende
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_custo_sem_venda"] == 1 and r["qa_selo"] == "bloqueado"

def test_acessorio_valor_zero_nao_acusa():
    itens = [{"order_total": 100.0, "budget_total": 300.0},
             {"order_total": 0.0,   "budget_total": 0.0}]     # acessorio inofensivo
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_custo_sem_venda"] == 0 and r["qa_selo"] == "ok"

def _itens_do_xml(nome):
    from promob_grupos import ler_xml
    amb = ler_xml(os.path.join("PROJETOS", "LELEU", "xmls", nome))
    return [it for g in amb.get("grupos", []) for it in g.get("itens", [])]

@_skip_leleu
def test_leleu_area_gourmet_bloqueia():
    r = q.avaliar_qualidade_xml(_itens_do_xml("Area Gourmet.xml"))
    assert r["qa_selo"] == "bloqueado"

@_skip_leleu
def test_leleu_banheiro_ok():
    r = q.avaliar_qualidade_xml(_itens_do_xml("Banheiro Social.xml"))
    assert r["qa_selo"] == "ok"
