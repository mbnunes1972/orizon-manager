"""GET /api/admin/empresas — lojas que o ator pode administrar, p/ o seletor de empresa
(topo de Admin/Config). super_admin: todas; admin_rede: da sua rede; loja: a própria; 401 sem login."""


def _logins(c, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    l2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    db.close()
    return l1, l2


def test_super_admin_ve_todas_as_empresas(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"], (st, out)
    ids = {e["loja_id"] for e in out["empresas"]}
    assert {l1, l2} <= ids
    assert all("nome" in e and "rede_nome" in e for e in out["empresas"])


def test_usuario_de_loja_ve_so_a_propria(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"]
    ids = {e["loja_id"] for e in out["empresas"]}
    assert ids == {l1}


def test_admin_rede_ve_so_lojas_da_rede(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"]
    ids = {e["loja_id"] for e in out["empresas"]}
    assert {l1, l2} <= ids


def test_sem_login_401(http_client_factory, seed):
    c = http_client_factory()
    st, out = c.get("/api/admin/empresas")
    assert st == 401
