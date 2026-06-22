import sqlite3

def test_usuarios_tem_colunas_contato(app_db):
    conn = sqlite3.connect(app_db.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(usuarios)")}
    conn.close()
    assert {"email", "cpf", "whatsapp"} <= cols

def test_usuario_persiste_contato(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Contato", login="ctt", nivel="consultor",
                       email="a@b.com", cpf="123", whatsapp="9999")
    u.set_senha("x")
    db.add(u); db.commit()
    uid = u.id; db.close()
    db2 = app_db.get_session()
    lido = db2.get(app_db.Usuario, uid); db2.close()
    assert lido.email == "a@b.com" and lido.cpf == "123" and lido.whatsapp == "9999"
