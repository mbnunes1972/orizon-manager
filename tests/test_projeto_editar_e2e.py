import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _uid(app_db, login):
    db = app_db.get_session()
    try:
        return db.query(app_db.Usuario).filter_by(login=login).first().id
    finally:
        db.close()


def _cliente_id(app_db, nome):
    db = app_db.get_session()
    try:
        return db.query(app_db.Cliente).filter_by(nome=nome).first().id
    finally:
        db.close()


def test_consultores_endpoint_gerente_vs_consultor(http_client_factory, seed, app_db, projetos_dir):
    # `_usuarios_atribuiveis_da_loja` (main.py) agora filtra por FUNÇÃO (Consultor de Vendas /
    # Gerente de Vendas), não por perfil de acesso. Damos ao cons_l1 a função Consultor de Vendas;
    # o Diretor (dir_l1) pode ATRIBUIR (pode_atribuir), mas não aparece como consultor de vendas.
    db = app_db.get_session()
    cons = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    fc = app_db.Funcao(loja_id=cons.loja_id, nome="Consultor de Vendas", status="ativo")
    db.add(fc); db.flush()
    cons.funcao_id = fc.id
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/projetos/consultores")
    assert st == 200 and d["ok"] is True
    assert d["pode_atribuir"] is True
    nomes = {x["nome"] for x in d["consultores"]}
    assert "Consultor L1" in nomes           # tem função Consultor de Vendas
    assert "Diretor L1" not in nomes         # diretor não é consultor de vendas (regra por função)
    # consultor (escopo próprio) não pode atribuir
    c2 = http_client_factory(); c2.login("cons_l1", "senha123")
    _, d2 = c2.get("/api/projetos/consultores")
    assert d2["pode_atribuir"] is False


def test_criar_projeto_consultor_puxa_logado_ou_indicado(http_client_factory, seed, app_db, projetos_dir):
    cli = _cliente_id(app_db, "Cliente L1")
    cons_id = _uid(app_db, "cons_l1")
    dir_id = _uid(app_db, "dir_l1")
    # diretor cria e INDICA o consultor
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/projetos/novo", {"nome_projeto": "Proj Do Ger", "cliente_id": cli, "consultor_id": cons_id})
    assert st == 200, d
    _, dl = c.get("/projetos")
    alvo = next(p for p in dl["projetos"] if p.get("nome_projeto") == "Proj Do Ger")
    assert alvo["consultor_id"] == cons_id            # indicado pelo gerente/diretor
    # consultor cria: consultor = ele mesmo, ignora consultor_id de outra pessoa
    c2 = http_client_factory(); c2.login("cons_l1", "senha123")
    st2, d2 = c2.post("/projetos/novo", {"nome_projeto": "Proj Do Cons", "cliente_id": cli, "consultor_id": dir_id})
    assert st2 == 200, d2
    _, dl2 = c2.get("/projetos")
    alvo2 = next(p for p in dl2["projetos"] if p.get("nome_projeto") == "Proj Do Cons")
    assert alvo2["consultor_id"] == cons_id           # forçado ao próprio usuário logado


def test_editar_reatribui_consultor_por_diretor(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    cons_id = _uid(app_db, "cons_l1")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/editar" % proj, {"consultor_id": cons_id})
    assert st == 200, d
    _, dl = c.get("/projetos")
    alvo = next(p for p in dl["projetos"] if p["nome_safe"] == proj)
    assert alvo["consultor_id"] == cons_id
    assert alvo["consultor_nome"] == "Consultor L1"


def test_editar_consultor_negado_para_consultor(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("cons_l1", "senha123")
    dir_id = _uid(app_db, "dir_l1")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/editar" % proj, {"consultor_id": dir_id})
    assert st == 403


def test_editar_parceiro_e_nome_preserva_chave(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, dp = c.post("/api/parceiros", {"nome": "Esp Teste", "tipo": "arquiteto", "cpf_cnpj": "111.444.777-35"})
    assert st == 200, dp
    pid = dp["parceiro"]["id"]
    proj = seed["projeto_l1"]
    st2, d2 = c.post("/api/projetos/%s/editar" % proj,
                     {"parceiro_id": pid, "nome_projeto": "Projeto Renomeado"})
    assert st2 == 200, d2
    _, dl = c.get("/projetos")
    alvo = next(p for p in dl["projetos"] if p["nome_safe"] == proj)
    assert alvo["parceiro_nome"] == "Esp Teste"
    assert alvo["nome_projeto"] == "Projeto Renomeado"
    assert alvo["nome_safe"] == proj                  # a chave/identidade é preservada
