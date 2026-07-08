import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_tenancy as mt
from types import SimpleNamespace


def _loja(modulos_ativos=None):
    return SimpleNamespace(id=1, modulos_ativos=modulos_ativos)


def test_default_tudo_ligado():
    loja = _loja(None)
    assert mt.modulo_ativo(loja, "fiscal") is True
    assert mt.modulo_ativo(loja, "comercial") is True


def test_nucleo_sempre_ativo():
    loja = _loja(json.dumps(["comercial"]))
    assert mt.modulo_ativo(loja, "auth") is True
    assert mt.modulo_ativo(loja, "tenancy") is True


def test_dominio_desligado():
    loja = _loja(json.dumps(["cadastro", "comercial", "financeiro"]))
    assert mt.modulo_ativo(loja, "fiscal") is False
    assert mt.modulo_ativo(loja, "comercial") is True


def test_lista_ativa_resolve():
    loja = _loja(json.dumps(["cadastro"]))
    assert "cadastro" in mt.modulos_ativos_da_loja(loja)
    assert "fiscal" not in mt.modulos_ativos_da_loja(loja)


def test_get_put_modulos_da_loja(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert st == 200 and "fiscal" in d["ativos"]
    st2, d2 = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial"]})
    assert st2 == 200
    st3, d3 = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert "fiscal" not in d3["ativos"] and "comercial" in d3["ativos"]


def test_guard_bloqueia_modulo_desligado(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "producao", "financeiro"]})
    dc = http_client_factory(); dc.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st == 403 and "módulo" in (d.get("erro", "")).lower()
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})
    st2, _ = dc.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 in (200, 404)
