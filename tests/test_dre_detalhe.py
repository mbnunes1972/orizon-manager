import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_dre_detalhe_nivel3(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 60); c = _q(db, 60)
    # 2 despesas administrativas: Aluguel 300 (5.4.01), Energia 120 (5.4.02)
    mc.lancar(db, "loja", 60, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=300.0)
    mc.lancar(db, "loja", 60, conta_debito_id=c("5.4.02"), conta_credito_id=c("1.1.01"), valor=120.0)
    d = mc.dre(db, "loja", 60)
    db.close()
    assert d["despesas_administrativas"] == 420.0            # total nível 2 (Resumido)
    det = d["detalhe"]["despesas_administrativas"]           # composição nível 3 (Analítico)
    por_cod = {x["codigo"]: x["valor"] for x in det}
    assert por_cod.get("5.4.01") == 300.0 and por_cod.get("5.4.02") == 120.0
    # requisito revisado 2026-07-22: o analítico lista o grupo INTEIRO — sem movimento sai 0,00
    assert por_cod.get("5.4.03") == 0.0
    assert sum(x["valor"] for x in det) == 420.0            # zeradas não alteram o total
