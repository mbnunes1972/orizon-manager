# tests/test_liberar_impostos.py
# Task 1 — endpoint POST /api/auth/liberar_impostos


def _mk(app_db, login, nivel):
    db = app_db.get_session()
    u = app_db.Usuario(nome=login, login=login, nivel=nivel, ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()


def _post(http_client_factory, login, senha):
    c = http_client_factory()
    return c.post("/api/auth/liberar_impostos",
                  {"login_autorizador": login, "senha_autorizador": senha})


def test_diretor_libera(http_client_factory, seed):
    st, body = _post(http_client_factory, "dir_l1", "senha123")
    assert st == 200 and body["ok"] and body["autorizador"]["nome"]


def test_gerente_adm_fin_libera(http_client_factory, seed, app_db):
    _mk(app_db, "gaf", "gerente_adm_fin")
    st, body = _post(http_client_factory, "gaf", "senha123")
    assert st == 200 and body["ok"]


def test_gerente_vendas_403(http_client_factory, seed, app_db):
    _mk(app_db, "gv", "gerente_vendas")
    st, body = _post(http_client_factory, "gv", "senha123")
    assert st == 403 and body["ok"] is False


def test_senha_errada_401(http_client_factory, seed):
    st, body = _post(http_client_factory, "dir_l1", "errada")
    assert st == 401 and body["ok"] is False
