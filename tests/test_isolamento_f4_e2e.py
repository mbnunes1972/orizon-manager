import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_canary_banco_isolado(app_db):
    assert "omie.db" not in app_db.DB_PATH
    db = app_db.get_session()
    loja = app_db.Loja(nome="Canary")
    db.add(loja); db.commit()
    lid = loja.id
    db.close()
    db2 = app_db.get_session()
    lido = db2.query(app_db.Loja).filter_by(id=lid).first()
    db2.close()
    assert lido is not None and lido.nome == "Canary"


def test_canary_login_via_http(http_client_factory):
    c = http_client_factory()
    status, body = c.login("dir_l1", "senha123")
    assert status == 200 and body.get("ok") is True
    assert c.cookie and c.cookie.startswith("omie_session=")
    status, _ = c.get("/api/clientes")
    assert status == 200
