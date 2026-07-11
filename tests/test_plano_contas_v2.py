"""FASE A (infra contábil): novas caixinhas no PLANO_PADRAO — Adiantamento de Clientes (passivo),
Provisão Custo Fábrica (2.1.04.06) e as provisões das demais rubricas monitoradas. Backfill idempotente."""
import mod_contabil as mc

_PROV_NOVAS = ("2.1.04.06", "2.1.04.07", "2.1.04.08", "2.1.04.09", "2.1.04.10", "2.1.04.11", "2.1.04.12")
_NOVAS = ("2.1.06",) + _PROV_NOVAS


def test_plano_tem_contas_novas(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 200)
    cods = {c.codigo for c in db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=200).all()}
    for cod in _NOVAS:
        assert cod in cods, cod
    db.close()


def test_adiantamento_e_custo_fabrica_natureza(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 201)
    q = lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=201, codigo=cod).first()
    adi = q("2.1.06")
    assert adi is not None and adi.grupo == 2 and adi.natureza == "credora"   # passivo credor
    fab = q("2.1.04.06")
    assert fab is not None and fab.natureza == "credora" and "F" in fab.nome   # provisão (passivo)
    db.close()


def test_seed_plano_backfill_contas_novas(app_db):
    """Backfill idempotente: um plano SEM as contas novas ganha-as ao re-seed (planos já existentes)."""
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 202)
    for cod in _NOVAS:                                  # simula plano "antigo": remove as novas
        c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=202, codigo=cod).first()
        if c:
            db.delete(c)
    db.commit()
    criadas = mc.seed_plano(db, "loja", 202)            # re-seed recria só as faltantes
    cods = {c.codigo for c in db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=202).all()}
    assert criadas == len(_NOVAS)
    assert all(cod in cods for cod in _NOVAS)
    assert mc.seed_plano(db, "loja", 202) == 0          # idempotente: 2ª vez não cria nada
    db.close()


def test_provisoes_novas_aparecem_no_painel(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 203)
    cods = {c["codigo"] for c in mc.contas_provisao_do_plano(db, "loja", 203)}
    assert set(_PROV_NOVAS) <= cods                     # as 7 novas aparecem (data-driven)
    assert {"2.1.04.02", "2.1.04.03", "2.1.04.05"} <= cods
    assert "2.1.04.01" not in cods and "2.1.04.04" not in cods   # comissão/devolução seguem excluídas
    db.close()
