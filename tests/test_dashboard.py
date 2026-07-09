import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_dashboard_provisoes_dre_cobertura(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 60); c = _q(db, 60)
    cfg = {"provisoes": {"assist_pct": 3.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 2.0}}
    mc.constituir_provisoes_venda(db, "loja", 60, "PV", 10000.0, cfg, ref_base="prov:1")   # 500/300/200
    mc.registrar_evento(db, "loja", 60, "faturamento", 1000.0, projeto_id="PV")             # receita
    mc.registrar_evento(db, "loja", 60, "recebimento", 700.0, projeto_id="PV")              # caixa 700
    dash = mc.dashboard_financeiro(db, "loja", 60)
    db.close()
    saldos = {p["nome"]: p["saldo_em_aberto"] for p in dash["provisoes"]}
    assert saldos["Provisão de Montagem"] == 500.0
    assert saldos["Provisão de Assistência Técnica"] == 300.0
    assert saldos["Provisão de Garantia"] == 200.0
    assert dash["total_provisoes_abertas"] == 1000.0
    assert dash["dre_resumo"]["receita_liquida"] == 1000.0
    # cobertura: caixa 700 / provisões 1000 = 0.70
    assert dash["cobertura_caixa"]["caixa"] == 700.0
    assert dash["cobertura_caixa"]["indice"] == 0.7


def test_dashboard_endpoint(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/dashboard")
    assert st == 200 and d["ok"] is True
    assert len(d["dashboard"]["provisoes"]) == 3
