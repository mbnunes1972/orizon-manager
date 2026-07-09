def _find(nodes, cod):
    for n in nodes:
        if n["codigo"] == cod:
            return n
        r = _find(n["filhos"], cod)
        if r:
            return r
    return None


def test_get_arvore_seed_on_first_access(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/contas")
    assert st == 200 and d["ok"] is True
    cods = [n["codigo"] for n in d["contas"]]
    assert cods == ["1", "2", "3", "4", "5"]


def test_post_cria_e_put_renomeia(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    g54 = _find(d["contas"], "5.4")               # Despesas Administrativas
    st, nova = c.post("/api/financeiro/contas", {"pai_id": g54["id"], "nome": "Nova Despesa"})
    assert st == 201 and nova["conta"]["grupo"] == 5
    st2, r = c.put("/api/financeiro/contas/" + str(nova["conta"]["id"]), {"nome": "Renomeada"})
    assert st2 == 200 and r["conta"]["nome"] == "Renomeada"


def test_remover_folha(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/financeiro/contas")
    folha = _find(d["contas"], "5.6.01")           # Constituição de Provisão (folha)
    st, r = c.post("/api/financeiro/contas/" + str(folha["id"]) + "/remover", {})
    assert st == 200 and r["acao"] == "apagada"


def test_sem_capability_barra_mutacao(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # consultor: sem aprovar_financeiro/editar_dados_loja
    _, d = c.get("/api/financeiro/contas")                        # GET ok (autenticado)
    g = d["contas"][0]
    st, _ = c.post("/api/financeiro/contas", {"pai_id": g["id"], "nome": "X"})
    assert st == 403
