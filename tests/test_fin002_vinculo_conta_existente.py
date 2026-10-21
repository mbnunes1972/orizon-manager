"""FIN-002 (19/10/2026): Funcionário com acesso + e-mail de uma conta que JÁ existe.

Antes: "Já existe uma conta com este e-mail." — não havia como dar Função (cargo) a quem foi
criado por Admin › Usuários. Caso real em produção: Jaime (Master, acessa INS e VQ-M5) trabalha
nas duas lojas → um Funcionário em CADA loja, os dois ligados à MESMA conta.

Regra: liga (Funcionario.usuario_id) quando a conta é de loja, tem acesso à loja do Funcionário
e ainda não tem Funcionário nesta loja. Ligar NÃO mexe na conta (perfil/lojas/senha continuam de
Admin › Usuários) — só a conta que NASCEU do Funcionário (Usuario.funcionario_id) segue o fluxo
antigo. A ponte conta→Funcionário e a Função passam a olhar a loja.
"""
import random
import uuid


def _cpf():
    """CPF válido aleatório — o banco de teste é do módulo e CPF repetido na loja dá 409."""
    d = [random.randint(0, 9) for _ in range(9)]
    for n in (10, 11):
        r = sum(x * w for x, w in zip(d, range(n, 1, -1))) * 10 % 11
        d.append(0 if r == 10 else r)
    s = "".join(map(str, d))
    return "%s.%s.%s-%s" % (s[:3], s[3:6], s[6:9], s[9:])


def _conta_multiloja(http_client_factory, seed, lojas, nivel="master"):
    """Cria, como super_admin, uma conta de loja com acesso a `lojas` (como em produção)."""
    login = "multi_%s@loja.com" % uuid.uuid4().hex[:8]
    s = http_client_factory(); s.login("super", "senha123")
    st, d = s.post("/api/admin/usuarios", {"nome": "Conta Multi", "login": login,
        "senha": "senhaMulti1", "nivel": nivel, "loja_ids": lojas})
    assert st in (200, 201) and d["ok"], d
    return login


def _conta(app_db, login):
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login=login).first()
        return {"id": u.id, "nivel": u.nivel, "loja_id": u.loja_id, "ativo": u.ativo,
                "funcionario_id": u.funcionario_id,
                "lojas": sorted(r[0] for r in db.query(app_db.UsuarioLoja.loja_id)
                                .filter_by(usuario_id=u.id).all())}
    finally:
        db.close()


def _func(app_db, fid):
    db = app_db.get_session()
    try:
        f = db.get(app_db.Funcionario, fid)
        return {"usuario_id": f.usuario_id, "loja_id": f.loja_id}
    finally:
        db.close()


def _novo_func(c, login, cpf, perfil="operador", nome="Pessoa Multi"):
    return c.post("/api/funcionarios", {"nome": nome, "cpf": cpf,
        "acesso": {"tem_acesso": True, "email": login, "perfil": perfil}})


def test_funcionario_liga_conta_existente_sem_mexer_na_conta(http_client_factory, seed, app_db):
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    antes = _conta(app_db, login)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # perfil "operador" no formulário NÃO pode rebaixar o Master que já existe
    st, d = _novo_func(c, login, "529.982.247-25")
    assert st == 201, d
    assert _func(app_db, d["id"])["usuario_id"] == antes["id"]
    depois = _conta(app_db, login)
    assert depois["nivel"] == "master"
    assert depois["loja_id"] == antes["loja_id"]
    assert depois["lojas"] == sorted([l1, l2])
    assert depois["funcionario_id"] is None          # conta não "nasceu" deste Funcionário
    # a senha da conta continua a mesma (não vira dígitos do CPF)
    st2, d2 = http_client_factory().post("/api/auth/login",
                                         {"login": login, "senha": "senhaMulti1"})
    assert st2 == 200 and d2["ok"] is True, d2


def test_mesma_conta_um_funcionario_em_cada_loja(http_client_factory, seed, app_db):
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    uid = _conta(app_db, login)["id"]
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st1, d1 = _novo_func(c1, login, "111.444.777-35", nome="Jaime L1")
    st2, d2 = _novo_func(c2, login, "111.444.777-35", nome="Jaime L2")   # mesmo CPF, outra loja
    assert st1 == 201 and st2 == 201, (d1, d2)
    assert _func(app_db, d1["id"])["usuario_id"] == uid
    assert _func(app_db, d2["id"])["usuario_id"] == uid
    # um 2º Funcionário da MESMA loja para a mesma conta continua barrado
    st3, d3 = _novo_func(c1, login, "390.533.447-05", nome="Jaime L1 bis")
    assert st3 == 400 and "nesta loja" in d3["erro"], d3


def test_conta_sem_acesso_a_loja_do_funcionario_recusa(http_client_factory, seed, app_db):
    login = _conta_multiloja(http_client_factory, seed, [seed["loja2_id"]])
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _novo_func(c, login, "714.602.380-01")
    assert st == 400 and "acesso a esta loja" in d["erro"], d


def test_conta_administrativa_nao_vira_funcionario(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _novo_func(c, "super", "868.051.350-44")
    assert st == 400, d
    assert _conta(app_db, "super")["nivel"] == "super_admin"


def test_tirar_acesso_numa_loja_nao_desativa_conta_ligada(http_client_factory, seed, app_db):
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    _, d1 = _novo_func(c1, login, "286.155.410-00", nome="Dupla L1")
    _, d2 = _novo_func(c2, login, "286.155.410-00", nome="Dupla L2")
    st, d = c1.post("/api/funcionarios/%d" % d1["id"], {"acesso": {"tem_acesso": False}})
    assert st == 200, d
    assert _conta(app_db, login)["ativo"] == 1                  # login segue valendo na loja 2
    assert _func(app_db, d1["id"])["usuario_id"] is None        # só o vínculo da loja 1 saiu
    assert _func(app_db, d2["id"])["usuario_id"] == _conta(app_db, login)["id"]


def test_ponte_conta_funcionario_olha_a_loja(http_client_factory, seed, app_db):
    import main
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    _, d1 = _novo_func(c1, login, "153.509.460-56", nome="Ponte L1")
    _, d2 = _novo_func(c2, login, "153.509.460-56", nome="Ponte L2")
    uid = _conta(app_db, login)["id"]
    db = app_db.get_session()
    try:
        assert main._funcionario_do_usuario(db, uid, l1) == d1["id"]
        assert main._funcionario_do_usuario(db, uid, l2) == d2["id"]
    finally:
        db.close()


def test_funcao_da_conta_e_a_do_funcionario_da_loja(http_client_factory, seed, app_db):
    from auth.auth import _funcao_do_usuario
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    _, f1 = c1.post("/api/funcoes", {"nome": "Cargo L1 %s" % uuid.uuid4().hex[:4]})
    _, f2 = c2.post("/api/funcoes", {"nome": "Cargo L2 %s" % uuid.uuid4().hex[:4]})
    c1.post("/api/funcionarios", {"nome": "Func L1", "cpf": "046.454.286-32", "funcao_id": f1["id"],
        "acesso": {"tem_acesso": True, "email": login}})
    c2.post("/api/funcionarios", {"nome": "Func L2", "cpf": "046.454.286-32", "funcao_id": f2["id"],
        "acesso": {"tem_acesso": True, "email": login}})
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login=login).first()
        assert _funcao_do_usuario(u, l1)[0] == f1["item"]["nome"]
        assert _funcao_do_usuario(u, l2)[0] == f2["item"]["nome"]
    finally:
        db.close()
    # a coluna Função de Admin › Usuários mostra a função DAQUELA loja
    s = http_client_factory(); s.login("super", "senha123")
    for lid, fn in ((l1, f1), (l2, f2)):
        _, lst = s.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % lid)
        row = [x for x in lst["usuarios"] if x["login"] == login]
        assert row and row[0]["funcao_nome"] == fn["item"]["nome"], (lid, row)


def test_lista_da_loja_mostra_quem_tem_acesso_mesmo_sem_ser_a_principal(http_client_factory, seed, app_db):
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])   # principal = l1
    assert _conta(app_db, login)["loja_id"] == l1
    s = http_client_factory(); s.login("super", "senha123")
    _, lst = s.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % l2)
    assert any(x["login"] == login for x in lst["usuarios"])
    d2 = http_client_factory(); d2.login("dir_l2", "senha123")    # o Master da loja 2 também vê
    _, lst2 = d2.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % l2)
    assert any(x["login"] == login for x in lst2["usuarios"])


def test_responsabilidades_juntam_as_etapas_de_todas_as_lojas_da_pessoa(http_client_factory, seed, app_db):
    """/api/me/ciclo/responsabilidades lista etapas de TODAS as lojas acessíveis — com um
    Funcionário por loja, precisa olhar os dois (antes: um só, o da loja 2 sumia)."""
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    cpf = _cpf()
    _, d1 = _novo_func(c1, login, cpf, nome="Resp L1")
    _, d2 = _novo_func(c2, login, cpf, nome="Resp L2")
    db = app_db.get_session()
    try:
        for proj, fid, cod in ((seed["projeto_l1"], d1["id"], "91"),
                               (seed["projeto_l2"], d2["id"], "92")):
            db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=cod, status="pendente",
                                     responsavel_funcionario_id=fid))
        db.commit()
    finally:
        db.close()
    eu = http_client_factory(); eu.login(login, "senhaMulti1")
    st, d = eu.get("/api/me/ciclo/responsabilidades")
    assert st == 200, d
    vistos = {(i["projeto_nome"], i["etapa_codigo"]) for i in d["itens"]}
    assert (seed["projeto_l1"], "91") in vistos and (seed["projeto_l2"], "92") in vistos, d


def test_lista_de_outra_loja_nao_mostra_funcao_da_loja_principal(http_client_factory, seed, app_db):
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    _, fn = c1.post("/api/funcoes", {"nome": "So L1 %s" % uuid.uuid4().hex[:4]})
    c1.post("/api/funcionarios", {"nome": "So na L1", "cpf": _cpf(), "funcao_id": fn["id"],
        "acesso": {"tem_acesso": True, "email": login}})
    s = http_client_factory(); s.login("super", "senha123")
    _, lst = s.get("/api/admin/usuarios?escopo=loja&loja_id=%d" % l2)
    row = [x for x in lst["usuarios"] if x["login"] == login]
    assert row and row[0]["funcao_nome"] == "", row     # na loja 2 ele não tem cargo


def test_ponte_sem_funcionario_na_loja_cai_no_de_sempre(http_client_factory, seed, app_db):
    """Diretor da loja-mãe opera o PDV sem ter Funcionário lá (acesso DERIVADO): a ponte não pode
    passar a devolver None no PDV — sem Funcionário na loja pedida, vale o comportamento antigo."""
    import main
    from auth.auth import _funcao_do_usuario
    l1, l2 = seed["loja1_id"], seed["loja2_id"]
    login = _conta_multiloja(http_client_factory, seed, [l1, l2])
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    _, fn = c1.post("/api/funcoes", {"nome": "Mae %s" % uuid.uuid4().hex[:4]})
    _, d1 = c1.post("/api/funcionarios", {"nome": "Só na mãe", "cpf": _cpf(), "funcao_id": fn["id"],
        "acesso": {"tem_acesso": True, "email": login}})
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login=login).first()
        assert main._funcionario_do_usuario(db, u.id, l2) == d1["id"]
        assert _funcao_do_usuario(u, l2)[0] == fn["item"]["nome"]
    finally:
        db.close()
