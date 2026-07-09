import pytest
import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_rateio_proporcional_receita(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 30); c = _q(db, 30)
    # Projeto A receita 900, projeto B receita 300 (75%/25%)
    mc.registrar_evento(db, "loja", 30, "faturamento", 900.0, projeto_id="A")
    mc.registrar_evento(db, "loja", 30, "faturamento", 300.0, projeto_id="B")
    # Despesa fixa (5.4 Aluguel) 400 — sem projeto
    mc.lancar(db, "loja", 30, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=400.0)
    rec = mc.reconciliar(db, "loja", 30, metodologia="proporcional_receita")
    db.close()
    assert rec["despesas_fixas_periodo"] == 400.0
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["A"]["valor_rateado"] == 300.0    # 75% de 400
    assert aloc["B"]["valor_rateado"] == 100.0    # 25% de 400
    assert aloc["A"]["margem_plena"] == 600.0     # 900 margem - 300 rateio
    # divergência = resultado societário − soma margem plena
    assert rec["resultado_societario_oficial"] == 800.0   # 1200 receita - 400 desp adm
    assert rec["soma_margem_plena"] == 800.0              # (900-300)+(300-100)=800
    assert rec["divergencia_residual"] == 0.0             # nada não-alocado neste cenário


def test_rateio_linear_e_metodologia_invalida(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 31); c = _q(db, 31)
    mc.registrar_evento(db, "loja", 31, "faturamento", 100.0, projeto_id="X")
    mc.registrar_evento(db, "loja", 31, "faturamento", 900.0, projeto_id="Y")
    mc.lancar(db, "loja", 31, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=200.0)
    rec = mc.reconciliar(db, "loja", 31, metodologia="linear_por_projeto")
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["X"]["valor_rateado"] == 100.0 and aloc["Y"]["valor_rateado"] == 100.0   # 200/2 cada
    with pytest.raises(ValueError):
        mc.reconciliar(db, "loja", 31, metodologia="chute")
    db.close()


def test_fechar_periodo_persiste(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 32)
    mc.registrar_evento(db, "loja", 32, "faturamento", 500.0, projeto_id="Z")
    r = mc.fechar_periodo(db, "loja", 32, metodologia="proporcional_receita")
    assert r["id"]
    periodos = mc.listar_periodos(db, "loja", 32)
    db.close()
    assert len(periodos) == 1 and periodos[0]["status"] == "fechado"
    assert periodos[0]["resultado_societario"] == 500.0
