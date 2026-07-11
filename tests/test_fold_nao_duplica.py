"""FASE 2 — prova de NÃO-DUPLICAÇÃO: foldar Montagem/Garantia na Marg_Cont (visão, mod_provisoes)
não altera DRE/Balanço nem cria lançamentos. mod_contabil é o único que escreve no razão."""
import mod_contabil as mc
import mod_provisoes as mp


def _cfg():
    return {"provisoes_contabeis": {"montagem_pct": 8.0, "garantia_pct": 0.5},
            "provisoes": {"assist_pct": 0.0}}


def test_fold_nao_altera_dre_nem_balanco(app_db):
    """DRE/Balanço fotografados antes e depois de rodar o fold (puro) são idênticos; nº de
    lançamentos inalterado. mod_provisoes não recebe db — não pode tocar o razão."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 80)
    V = 10000.0
    mc.registrar_evento(db, "loja", 80, "faturamento", V, projeto_id="PZ")           # receita
    mc.constituir_provisoes_venda(db, "loja", 80, "PZ", V, _cfg(), ref_base="p:1")    # 800 + 50
    db.commit()
    dre_antes = mc.dre(db, "loja", 80)
    bal_antes = mc.balanco(db, "loja", 80)
    n_antes = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=80).count()

    # roda TODO o caminho de visão do fold
    r = mp.provisoes_orcamento({"CFO": 3000.0, "Val_Liq": 6000.0, "VAVO": 7000.0,
                                "Prov_Imp": 0.0, "Val_Cont": V}, _cfg())
    mp.cust_var_marg_cont(3000.0, 6000.0, mp.itens_provisao(r))

    dre_depois = mc.dre(db, "loja", 80)
    bal_depois = mc.balanco(db, "loja", 80)
    n_depois = db.query(mc.Lancamento).filter_by(owner_tipo="loja", owner_id=80).count()
    db.close()
    assert dre_antes == dre_depois
    assert bal_antes == bal_depois
    assert n_antes == n_depois


def test_dre_ja_continha_montagem_garantia_e_fold_bate(app_db):
    """O fold não adiciona custo ao mundo: montagem+garantia já estão no DRE (const. de provisões),
    e o valor exibido na visão (Prov_Mont+Prov_Gar) é exatamente o constituído no razão."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 81)
    V = 10000.0
    mc.constituir_provisoes_venda(db, "loja", 81, "PY", V, _cfg(), ref_base="p:1")    # 800/50, assist 0
    db.commit()
    dre = mc.dre(db, "loja", 81)
    r = mp.provisoes_orcamento({"CFO": 0.0, "Val_Liq": 1.0, "VAVO": 0.0, "Prov_Imp": 0.0,
                                "Val_Cont": V}, _cfg())
    db.close()
    assert r["Prov_Mont"] == 800.0 and r["Prov_Gar"] == 50.0
    assert dre["constituicao_provisoes"] == r["Prov_Mont"] + r["Prov_Gar"]            # 850, assist 0
