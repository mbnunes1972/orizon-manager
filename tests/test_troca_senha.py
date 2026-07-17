"""Senha provisória: usuário criado com senha_provisoria=1 é sinalizado no login e troca a senha."""


def test_login_sinaliza_e_troca(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    u = app_db.Usuario(nome="Novo Dir", login="novodir@l1.com", nivel="master",
                       loja_id=l1, ativo=1, senha_provisoria=1)
    u.set_senha("provisoria123"); db.add(u); db.commit(); db.close()

    c = http_client_factory()
    st, out = c.login("novodir@l1.com", "provisoria123")
    assert st == 200 and out.get("precisa_trocar_senha") is True, out

    st2, o2 = c.post("/api/auth/trocar-senha", {"nova_senha": "definitiva456"})
    assert st2 == 200 and o2["ok"], (st2, o2)

    # relogar com a nova senha, sem o flag
    c2 = http_client_factory()
    st3, o3 = c2.login("novodir@l1.com", "definitiva456")
    assert st3 == 200 and not o3.get("precisa_trocar_senha"), o3
