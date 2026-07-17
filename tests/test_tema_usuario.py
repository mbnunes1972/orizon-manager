from sqlalchemy import inspect
from auth import auth

def test_usuarios_tem_coluna_tema(app_db):
    # introspecção via SQLAlchemy — funciona nos dois dialetos (DB_PATH é None em Postgres)
    cols = {c["name"] for c in inspect(app_db.ENGINE).get_columns("usuarios")}
    assert "tema" in cols

def test_usuario_dict_inclui_tema_default_escuro(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Tema", login="tema1", nivel="consultor")
    u.set_senha("x"); db.add(u); db.commit(); uid = u.id; db.close()
    db2 = app_db.get_session()
    lido = db2.get(app_db.Usuario, uid); db2.close()
    d = auth._usuario_dict(lido)
    assert d["tema"] == "escuro"

def test_set_tema_atualiza_e_valida(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Tema2", login="tema2", nivel="consultor")
    u.set_senha("x"); db.add(u); db.commit(); uid = u.id; db.close()
    assert auth.set_tema(uid, "claro") is True
    db2 = app_db.get_session()
    assert db2.get(app_db.Usuario, uid).tema == "claro"
    db2.close()
    assert auth.set_tema(uid, "roxo") is False
    db3 = app_db.get_session()
    assert db3.get(app_db.Usuario, uid).tema == "claro"
    db3.close()
    assert auth.set_tema(999999, "escuro") is False


def test_endpoint_preferencias_persiste_e_reflete_no_me(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/auth/preferencias", {"tema": "claro"})
    assert st == 200 and d["ok"] is True and d["tema"] == "claro"
    # round-trip: /api/auth/me reflete a preferência gravada
    st2, me = c.get("/api/auth/me")
    assert st2 == 200 and me["usuario"]["tema"] == "claro"

def test_endpoint_preferencias_rejeita_tema_invalido(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/auth/preferencias", {"tema": "roxo"})
    assert st == 400 and d["ok"] is False

def test_endpoint_preferencias_exige_autenticacao(http_client_factory, seed, app_db):
    c = http_client_factory()   # sem login
    st, d = c.post("/api/auth/preferencias", {"tema": "claro"})
    assert st == 401
