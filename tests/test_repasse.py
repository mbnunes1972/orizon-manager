import mod_contabil as mc


def test_total_a_cobrar_fabrica_so_defeito(app_db):
    db = app_db.get_session()
    # 2 reparos por defeito de fábrica + 1 "outro" (não conta)
    mc.registrar_evento(db, "loja", 70, "execucao_reparo_garantia", 100.0, projeto_id="A", motivo="defeito_fabrica")
    mc.registrar_evento(db, "loja", 70, "execucao_reparo_garantia", 50.0, projeto_id="B", motivo="defeito_fabrica")
    mc.registrar_evento(db, "loja", 70, "execucao_reparo_garantia", 30.0, projeto_id="C", motivo="outro")
    rep = mc.total_a_cobrar_fabrica(db, "loja", 70)
    db.close()
    assert rep["total"] == 150.0 and rep["qtd"] == 2      # só os 2 de defeito de fábrica


def test_motivo_persiste_no_lancamento(app_db):
    db = app_db.get_session()
    lan = mc.registrar_evento(db, "loja", 71, "execucao_reparo_garantia", 40.0, motivo="defeito_fabrica")
    l = db.query(mc.Lancamento).get(lan["id"])
    assert l.motivo == "defeito_fabrica"
    db.close()


def test_endpoint_repasse(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "execucao_reparo_garantia", "valor": 200,
                                       "projeto_id": "Proj_L1", "motivo": "defeito_fabrica"})
    st, d = c.get("/api/financeiro/repasse-fabrica")
    assert st == 200 and d["repasse"]["total"] >= 200
