import json


def test_provisao_registro_persiste(app_db, seed):
    db = app_db.get_session()
    try:
        r = app_db.ProvisaoRegistro(
            orcamento_id=seed["orcamento_l1_id"], versao="venda",
            itens_json=json.dumps({"frete_fab": 100.0, "out_forn": 0.0}),
            cfo=4000.0, val_liq=9000.0, cust_var=4100.0, marg_cont=0.5444, decisao=None)
        db.add(r); db.commit()
        got = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").first()
        assert got is not None
        assert json.loads(got.itens_json)["frete_fab"] == 100.0
        assert got.cfo == 4000.0 and got.val_liq == 9000.0
    finally:
        db.close()


def test_registrar_venda(app_db, seed, projetos_dir):
    import main
    db = app_db.get_session()
    try:
        # ambiente com valor p/ o motor calcular
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Amb", versao=1,
                                 nome_exibicao="Amb", xml_path="", ambientes_json="[]",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
        r = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").first()
        assert r is not None and r.decisao is None
        import json as _j
        assert set(_j.loads(r.itens_json).keys()) >= {"frete_fab", "out_forn", "prov_imp"}
        assert r.cfo == 4000.0          # CFO = order_total
        # idempotente / re-snapshot: chamar de novo não duplica
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
        n = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").count()
        assert n == 1
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").delete()
        db.commit()
        db.close()


def test_get_provisoes(http_client_factory, app_db, seed, projetos_dir):
    import main, json as _j
    db = app_db.get_session()
    try:
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="A", versao=1,
                                 nome_exibicao="A", xml_path="", ambientes_json="[]",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        db.commit()
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")   # diretor tem aprovar_financeiro
    st, body = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert st == 200 and body["ok"] is True
    assert body["provisoes"]["venda"] is not None
    assert "frete_fab" in body["provisoes"]["atual"]["itens"]
    assert body["provisoes"]["desatualizado"] is False


def test_get_provisoes_outra_loja_404(http_client_factory, seed):
    # dir_l2 (loja2) nao pode ler provisoes de um orcamento da loja1
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert st in (403, 404)


def test_get_provisoes_sem_permission_403(http_client_factory, seed):
    # super_admin nao tem aprovar_financeiro
    c = http_client_factory(); c.login("super", "senha123")
    st, _ = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert st == 403
