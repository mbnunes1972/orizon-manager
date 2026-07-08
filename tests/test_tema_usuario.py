import sqlite3
import auth

def test_usuarios_tem_coluna_tema(app_db):
    conn = sqlite3.connect(app_db.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(usuarios)")}
    conn.close()
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
