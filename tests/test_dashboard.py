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


def test_dashboard_provisoes_data_driven(app_db):
    """O painel é um loop sobre o Plano de Contas, não 3 componentes fixos: hoje mostra as 3
    provisões da venda (comissão e devolução ficam de fora); criar uma provisão nova no plano
    faz surgir um 4º card automaticamente, sem tocar no código do painel (Diagramacao_v4 §1.3)."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 61)
    dash = mc.dashboard_financeiro(db, "loja", 61)
    cods = {p["codigo"] for p in dash["provisoes"]}
    assert cods == {"2.1.04.02", "2.1.04.03", "2.1.04.05"}       # as 3 da venda
    assert "2.1.04.01" not in cods and "2.1.04.04" not in cods   # comissão/devolução: tratamento próprio
    # nova provisão CRIADA no Plano de Contas -> novo card, sem alterar a tela
    db.add(mc.Conta(owner_tipo="loja", owner_id=61, codigo="2.1.04.06", nome="Provisão de Frete",
                    grupo=2, tipo="analitica", natureza=mc._natureza(2), ativa=1, ordem=999))
    db.commit()
    dash2 = mc.dashboard_financeiro(db, "loja", 61)
    db.close()
    novo = {p["codigo"]: p for p in dash2["provisoes"]}.get("2.1.04.06")
    assert novo is not None
    assert novo["nome"] == "Provisão de Frete"        # nome vem do plano, não hardcoded
    assert novo["saldo_em_aberto"] == 0.0
    assert novo["sub"] == "Saldo provisionado em aberto"   # descrição genérica (não estava no mapa)
