import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_me_traz_modulos_ativos_default_tudo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/auth/me")
    assert st == 200
    mods = d["usuario"]["modulos_ativos"]
    assert "cadastro" in mods and "fiscal" in mods


def test_me_reflete_modulo_desligado(http_client_factory, seed, app_db):
    adm = http_client_factory(); adm.login("super", "senha123")
    lid = seed["loja1_id"]
    adm.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "producao", "financeiro"]})
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/auth/me")
    assert "fiscal" not in d["usuario"]["modulos_ativos"]
    adm.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})   # religa
