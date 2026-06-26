import json


def test_loja_guarda_config_financeira_json(app_db, seed):
    db = app_db.get_session()
    try:
        l = db.get(app_db.Loja, seed["loja1_id"])
        l.config_financeira_json = json.dumps({"provisoes": {"frete_fab_pct": 5.0}})
        db.commit()
        l2 = db.get(app_db.Loja, seed["loja1_id"])
        assert json.loads(l2.config_financeira_json)["provisoes"]["frete_fab_pct"] == 5.0
    finally:
        db.close()


def test_orcamento_tem_out_forn_default_zero(app_db, seed):
    db = app_db.get_session()
    try:
        o = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        assert (o.out_forn or 0.0) == 0.0
        o.out_forn = 1234.5
        db.commit()
        assert db.get(app_db.Orcamento, seed["orcamento_l1_id"]).out_forn == 1234.5
    finally:
        db.close()
