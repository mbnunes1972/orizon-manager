import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_lista_projetos_traz_parceiro_nome(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # cria um parceiro e associa a um projeto do seed
    st, dp = c.post("/api/parceiros", {"nome": "Arq Teste", "tipo": "arquiteto", "cpf_cnpj": "111.444.777-35"})
    assert st == 200, dp
    pid = dp["parceiro"]["id"]
    proj = seed["projeto_l1"]
    st2, _ = c.post(f"/api/projetos/{proj}/parceiro", {"parceiro_id": pid})
    assert st2 == 200
    st3, d = c.get("/projetos")
    assert st3 == 200
    alvo = next(p for p in d["projetos"] if p["nome_safe"] == proj)
    assert alvo["parceiro_id"] == pid
    assert alvo["parceiro_nome"] == "Arq Teste"
    # projeto sem parceiro -> parceiro_nome None/ausente, sem quebrar
    outros = [p for p in d["projetos"] if p["nome_safe"] != proj]
    assert all(p.get("parceiro_nome") in (None, "") for p in outros if not p.get("parceiro_id"))
