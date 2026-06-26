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
