import json


def test_breakdown_inclui_margem_real(app_db, seed, projetos_dir):
    import main, mod_provisoes
    db = app_db.get_session()
    try:
        # configura a loja 1 com frete fábrica 10% e injeta ambientes no orçamento L1
        loja = db.get(app_db.Loja, seed["loja1_id"])
        cfg = mod_provisoes.config_financeira_default()
        cfg["provisoes"]["frete_fab_pct"] = 10.0
        loja.config_financeira_json = json.dumps(cfg)
        # pool ambiente + vínculo no orçamento L1 (VBVA/CFA não-nulos)
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha",
                                 nome_exibicao="Cozinha", xml_path="cozinha.xml",
                                 ambientes_json="{}",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        d = main._negociacao_breakdown(orc, db)
    finally:
        db.close()
    assert "Cust_Var" in d and "Marg_Cont" in d
    assert d["Frete_Fab_Orc"] == round(0.10 * d["CFO"], 2)
    # Cust_Var >= CFO (custo de fábrica sempre entra)
    assert d["Cust_Var"] >= d["CFO"]


def test_get_put_config_financeira(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")   # diretor: editar_dados_loja
    st, body = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    assert st == 200 and "config" in body
    cfg = body["config"]; cfg["provisoes"]["com_adm_pct"] = 7.0
    st2, body2 = c.put("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"], cfg)
    assert st2 == 200 and body2["ok"] is True
    st3, body3 = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    assert body3["config"]["provisoes"]["com_adm_pct"] == 7.0


def test_put_config_rejeita_invalido(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, body = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    cfg = body["config"]; cfg["provisoes"]["frete_fab_pct"] = -5.0
    st, b = c.put("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"], cfg)
    assert b["ok"] is False


def test_breakdown_usa_carga_trib_da_loja_quando_projeto_sem_params(app_db, seed, projetos_dir):
    import main, mod_provisoes, json as _json
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, seed["loja1_id"])
        cfg = mod_provisoes.config_financeira_default()
        cfg["defaults_negociacao"]["carga_trib_pct"] = 10.0
        loja.config_financeira_json = _json.dumps(cfg)
        # projeto SEM parametros_json
        proj = db.get(app_db.Projeto, seed["projeto_l1"])
        proj.parametros_json = None
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Amb", versao=1,
                                 nome_exibicao="Amb", xml_path="", ambientes_json="[]",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        d = main._negociacao_breakdown(orc, db)
    finally:
        db.close()
    # carga_trib 10% da loja deve refletir em Prov_Imp (> 0), pois o projeto nao tem params proprios
    assert d["Prov_Imp"] > 0


def test_put_out_forn(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.put("/api/orcamentos/%d/out-forn" % seed["orcamento_l1_id"], {"out_forn": 777})
    assert st == 200 and body["ok"] is True
    assert body["sombra"]["Out_Forn"] == 777
    # persistiu: nova previa reflete
    st2, b2 = c.post("/api/orcamentos/%d/negociacao-preview" % seed["orcamento_l1_id"], {})
    assert b2["sombra"]["Out_Forn"] == 777


def test_out_forn_fora_de_escopo_403(http_client_factory, seed):
    # dir_l2 (loja2) nao pode editar out_forn de um orcamento da loja1
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = c.put("/api/orcamentos/%d/out-forn" % seed["orcamento_l1_id"], {"out_forn": 100})
    assert st in (403, 404)


def test_out_forn_clamp_negativo(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.put("/api/orcamentos/%d/out-forn" % seed["orcamento_l1_id"], {"out_forn": -500})
    assert st == 200 and body["ok"] is True
    assert body["sombra"]["Out_Forn"] == 0   # clampado
