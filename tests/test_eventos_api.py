def test_post_evento_faturamento(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, r = c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 1200, "projeto_id": "Proj_L1"})
    assert st == 201 and r["lancamento"]["origem"] == "faturamento"
    # aparece na lista do projeto
    _, d = c.get("/api/financeiro/lancamentos?projeto=Proj_L1")
    assert any(l["origem"] == "faturamento" and l["valor"] == 1200 for l in d["lancamentos"])


def test_post_evento_desconhecido_400(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/financeiro/eventos", {"tipo": "xpto", "valor": 10})
    assert st == 400
