def test_kanban_agrupa_por_etapa_em_andamento(http_client_factory, seed, app_db):
    # projeto da loja 1 com a etapa 13 (Produção) em andamento
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="13", status="em_andamento"))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/expedicao/kanban")
    assert st == 200 and d["ok"] is True
    cods = [col["codigo"] for col in d["colunas"]]
    assert cods == ["12", "13", "14", "15", "16"]
    prod = next(col for col in d["colunas"] if col["codigo"] == "13")
    assert any(card["nome_safe"] == seed["projeto_l1"] for card in prod["cards"])


def test_kanban_ignora_etapa_nao_expedicao(http_client_factory, seed, app_db):
    # etapa 7 (Contrato) em andamento NÃO aparece no kanban de expedição
    db = app_db.get_session()
    db.add(app_db.CicloEtapa(projeto_nome=seed["projeto_l2"], etapa_codigo="7", status="em_andamento"))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, d = c.get("/api/expedicao/kanban")
    assert st == 200
    todos = [card["nome_safe"] for col in d["colunas"] for card in col["cards"]]
    assert seed["projeto_l2"] not in todos
