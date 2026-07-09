def test_projetos_dre_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 600, "projeto_id": "ProjMarg"})
    st, d = c.get("/api/financeiro/projetos-dre")
    assert st == 200 and d["ok"] is True
    p = next((x for x in d["projetos"] if x["projeto_id"] == "ProjMarg"), None)
    assert p is not None and p["receita"] == 600.0 and p["margem_contribuicao"] == 600.0
