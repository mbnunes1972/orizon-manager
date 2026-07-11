import mod_contabil as mc


def test_contas_provisao_do_plano_data_driven(app_db):
    """Enumera, data-driven, as contas analíticas do grupo de provisões (2.1.04.%),
    excluindo Comissão (.01) e Devolução (.04) por tratamento próprio."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 62)
    contas = mc.contas_provisao_do_plano(db, "loja", 62)
    cods = {c["codigo"] for c in contas}
    assert cods == {"2.1.04.02", "2.1.04.03", "2.1.04.05"}   # as 3 da venda
    assert "2.1.04.01" not in cods and "2.1.04.04" not in cods
    assert all({"codigo", "nome", "sub", "saldo_em_aberto"} <= set(c) for c in contas)
    db.close()


def test_contas_provisao_saldo_reflete_lancamento(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 63)
    cfg = {"provisoes_contabeis": {"montagem_pct": 5.0}}
    mc.constituir_provisoes_venda(db, "loja", 63, "PX", 10000.0, cfg, ref_base="p:1")  # montagem = 500
    contas = {c["codigo"]: c for c in mc.contas_provisao_do_plano(db, "loja", 63)}
    assert contas["2.1.04.02"]["saldo_em_aberto"] == 500.0
    db.close()


def test_conta_nova_no_grupo_aparece(app_db):
    """Provar o data-driven: uma conta nova em 2.1.04 aparece sem tocar no painel."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 64)
    db.add(mc.Conta(owner_tipo="loja", owner_id=64, codigo="2.1.04.06", nome="Provisão de Frete",
                    grupo=2, tipo="analitica", natureza=mc._natureza(2), ativa=1, ordem=999))
    db.commit()
    cods = {c["codigo"] for c in mc.contas_provisao_do_plano(db, "loja", 64)}
    assert "2.1.04.06" in cods
    db.close()


def test_dashboard_usa_o_helper(app_db):
    """O dashboard reflete exatamente o helper (mesmas contas) — garante que a extração não mudou nada."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 65)
    dash = mc.dashboard_financeiro(db, "loja", 65)
    helper = mc.contas_provisao_do_plano(db, "loja", 65)
    assert {p["codigo"] for p in dash["provisoes"]} == {c["codigo"] for c in helper}
    assert dash["total_provisoes_abertas"] == round(sum(c["saldo_em_aberto"] for c in helper), 2)
    db.close()
