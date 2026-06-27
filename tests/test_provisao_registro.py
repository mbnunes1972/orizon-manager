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
