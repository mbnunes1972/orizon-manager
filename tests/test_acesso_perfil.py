"""Perfil-4 (rev2 §2/§9): a matriz de acesso por módulo/painel é enforced no backend + refletida
no hub (auth/me). Consultor não abre Financeiro/Fiscal/Admin/Config; Suporte só Admin+Config."""


def _mk(app_db, login, nivel):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    u = app_db.Usuario(nome=login, login=login, nivel=nivel, loja_id=l1, ativo=1)
    u.set_senha("x"); db.add(u); db.commit(); db.close()


def _mods(c):
    _, me = c.get("/api/auth/me")
    return me["usuario"], set(me["usuario"]["modulos_ativos"])


def test_consultor_bloqueado_financeiro_e_folha(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")
    assert c.get("/api/financeiro/dashboard")[0] == 403
    assert c.get("/api/folha?competencia=2026-07")[0] == 403
    # Diretoria acessa (não é barrada pelo perfil)
    d = http_client_factory(); d.login("dir_l1", "senha123")
    assert d.get("/api/financeiro/dashboard")[0] != 403
    assert d.get("/api/folha?competencia=2026-07")[0] != 403


def test_auth_me_hub_reflete_matriz(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")
    u, mods = _mods(c)
    assert u["acessa_admin"] is False and u["acessa_config"] is False   # Consultor sem painéis
    assert "financeiro" not in mods and "fiscal" not in mods and "folha" not in mods
    assert "comercial" in mods and "cadastro" in mods                   # operacional ok
    d = http_client_factory(); d.login("dir_l1", "senha123")
    ud, modsd = _mods(d)
    assert ud["acessa_admin"] and ud["acessa_config"]
    assert {"financeiro", "fiscal", "folha", "comercial"} <= modsd       # Diretoria tudo


def test_suporte_so_paineis_sem_operacional(http_client_factory, seed, app_db):
    _mk(app_db, "sup2@loja.com", "suporte")
    s = http_client_factory(); s.login("sup2@loja.com", "x")
    assert s.get("/api/financeiro/dashboard")[0] == 403      # sem Financeiro
    u, mods = _mods(s)
    assert u["acessa_admin"] and u["acessa_config"]           # só painéis
    assert not ({"comercial", "cadastro", "financeiro", "fiscal"} & mods)   # nada operacional/fin/fiscal


def test_usuarios_loja_funcao_fallback_para_funcao_id(http_client_factory, seed, app_db):
    # Perfil-4: conta SÓ-login (sem Funcionário) mostra a Função via Usuario.funcao_id (cargo migrado);
    # Perfil segue sendo o nível de acesso.
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fc = app_db.Funcao(loja_id=l1, nome="Medidor"); db.add(fc); db.flush()
    u = app_db.Usuario(nome="Só Login", login="cl@loja.com", nivel="consultor",
                       loja_id=l1, ativo=1, funcao_id=fc.id)
    u.set_senha("x"); db.add(u); db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/admin/usuarios")
    cl = next(x for x in d["usuarios"] if x["login"] == "cl@loja.com")
    assert cl["funcao_nome"] == "Medidor"   # Função = cargo
    assert cl["nivel"] == "consultor"        # Perfil = acesso
