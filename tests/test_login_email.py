def test_login_aceita_email_e_login(http_client_factory, seed, app_db):
    # dá um e-mail (com maiúsculas) ao consultor do seed
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    u.email = "Consultor@Loja.com"
    db.commit(); db.close()

    # entra pelo e-mail (case-insensitive) — é o caminho da nova tela de entrada
    c = http_client_factory()
    st, d = c.post("/api/auth/login", {"login": "consultor@loja.com", "senha": "senha123"})
    assert st == 200 and d["ok"] is True

    # e o login tradicional continua funcionando (contas antigas)
    c2 = http_client_factory()
    st2, d2 = c2.post("/api/auth/login", {"login": "cons_l1", "senha": "senha123"})
    assert st2 == 200 and d2["ok"] is True

    # credencial errada segue barrada
    c3 = http_client_factory()
    st3, d3 = c3.post("/api/auth/login", {"login": "consultor@loja.com", "senha": "errada"})
    assert st3 == 401 and d3["ok"] is False
