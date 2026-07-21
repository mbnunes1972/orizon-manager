"""DRE/Balanço — período e completude das contas (pedido do usuário, 2026-07-22).

Bug real corrigido: `_mov`/`_detalhe_grupo` filtravam `tipo="analitica"` — mas o seed_plano
CONVERTE um pai em sintética quando ele ganha filho no backfill; lançamentos diretos anteriores
à conversão sumiam da DRE/Balanço (total E analítico). Agora TODA conta com lançamento no
período aparece; sem movimento, fora.
"""
from datetime import datetime
import mod_contabil as mc


def _lancar(db, ot, oid, cod_d, cod_c, valor, data):
    cd = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod_d).first()
    cc = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod_c).first()
    mc.lancar(db, ot, oid, cd.id, cc.id, valor, data=data, historico="t")


def test_conta_sintetica_com_lancamento_direto_aparece(app_db):
    db = app_db.get_session(); ot, oid = "loja", 980; mc.seed_plano(db, ot, oid)
    # lançamento numa despesa comum
    _lancar(db, ot, oid, "5.4.01", "1.1.01", 1000.0, datetime(2026, 7, 10))
    # simula o cenário do backfill: 5.4.01 vira SINTÉTICA depois de já ter lançamento direto
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.4.01").first()
    c.tipo = "sintetica"
    db.commit()
    d = mc.dre(db, ot, oid)
    assert d["despesas_administrativas"] == 1000.0          # total NÃO perde a conta
    codigos = [l["codigo"] for l in d["detalhe"]["despesas_administrativas"]]
    assert "5.4.01" in codigos                              # analítico também mostra
    db.close()


def test_dre_por_periodo_e_sem_movimento_fora(app_db):
    db = app_db.get_session(); ot, oid = "loja", 981; mc.seed_plano(db, ot, oid)
    _lancar(db, ot, oid, "5.4.01", "1.1.01", 500.0, datetime(2026, 6, 15))   # junho
    _lancar(db, ot, oid, "5.4.02", "1.1.01", 300.0, datetime(2026, 7, 15))   # julho
    d_jun = mc.dre(db, ot, oid, ini=datetime(2026, 6, 1), fim=datetime(2026, 6, 30))
    assert d_jun["despesas_administrativas"] == 500.0
    cods = [l["codigo"] for l in d_jun["detalhe"]["despesas_administrativas"]]
    assert cods == ["5.4.01"]                               # só a conta COM movimento no período
    d_jul = mc.dre(db, ot, oid, ini=datetime(2026, 7, 1), fim=datetime(2026, 7, 31))
    cods = [l["codigo"] for l in d_jul["detalhe"]["despesas_administrativas"]]
    assert cods == ["5.4.02"]
    db.close()


def test_conta_com_movimento_que_zera_aparece_com_zero(app_db):
    # teve lançamentos no período (débito == crédito) → aparece com 0,00; sem movimento → fora
    db = app_db.get_session(); ot, oid = "loja", 982; mc.seed_plano(db, ot, oid)
    _lancar(db, ot, oid, "5.4.03", "1.1.01", 200.0, datetime(2026, 7, 5))
    _lancar(db, ot, oid, "1.1.01", "5.4.03", 200.0, datetime(2026, 7, 6))   # estorno
    d = mc.dre(db, ot, oid)
    linhas = {l["codigo"]: l["valor"] for l in d["detalhe"]["despesas_administrativas"]}
    assert linhas.get("5.4.03") == 0.0                      # teve movimento → aparece zerada
    assert "5.4.04" not in linhas                           # sem movimento → fora
    db.close()


def test_balanco_data_corte(app_db):
    db = app_db.get_session(); ot, oid = "loja", 983; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "captacao_emprestimo", 10000.0, ref="b1",
                        data=datetime(2026, 6, 1))
    mc.registrar_evento(db, ot, oid, "pagamento_emprestimo", 4000.0, ref="b2",
                        data=datetime(2026, 7, 15))
    b_jun = mc.balanco(db, ot, oid, data_corte=datetime(2026, 6, 30))
    det = {l["codigo"]: l["valor"] for l in b_jun["detalhe"]["passivo_circulante"]}
    assert det.get("2.1.10") == 10000.0                     # posição em 30/06
    b_full = mc.balanco(db, ot, oid)
    det = {l["codigo"]: l["valor"] for l in b_full["detalhe"]["passivo_circulante"]}
    assert det.get("2.1.10") == 6000.0
    assert b_jun["confere"] and b_full["confere"]
    db.close()
