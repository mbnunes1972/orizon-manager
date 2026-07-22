"""DRE/Balanço — período e completude das contas (pedido do usuário, 2026-07-22; requisito
REVISADO no mesmo dia: o analítico mostra TODAS as contas analíticas ativas do grupo, com ou
sem movimento — sem movimento sai 0,00. Supera o "sem movimento → fora" da 1ª versão).

Bug real corrigido (mantido): `_mov`/`_detalhe_grupo` filtravam `tipo="analitica"` — mas o
seed_plano CONVERTE um pai em sintética quando ele ganha filho no backfill; lançamentos
diretos anteriores à conversão sumiam da DRE/Balanço (total E analítico). Conta com
lançamento — mesmo sintética ou inativa — SEMPRE aparece.
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


def test_dre_por_periodo_com_todas_as_contas(app_db):
    """Período filtra o VALOR; a LISTA traz o plano inteiro do grupo (requisito revisado)."""
    db = app_db.get_session(); ot, oid = "loja", 981; mc.seed_plano(db, ot, oid)
    _lancar(db, ot, oid, "5.4.01", "1.1.01", 500.0, datetime(2026, 6, 15))   # junho
    _lancar(db, ot, oid, "5.4.02", "1.1.01", 300.0, datetime(2026, 7, 15))   # julho
    d_jun = mc.dre(db, ot, oid, ini=datetime(2026, 6, 1), fim=datetime(2026, 6, 30))
    assert d_jun["despesas_administrativas"] == 500.0
    linhas = {l["codigo"]: l["valor"] for l in d_jun["detalhe"]["despesas_administrativas"]}
    assert linhas["5.4.01"] == 500.0                        # movimento do período
    assert linhas["5.4.02"] == 0.0                          # fora do período → 0,00 (mas LISTADA)
    assert "5.4.04" in linhas and linhas["5.4.04"] == 0.0   # sem movimento nenhum → 0,00, listada
    d_jul = mc.dre(db, ot, oid, ini=datetime(2026, 7, 1), fim=datetime(2026, 7, 31))
    linhas = {l["codigo"]: l["valor"] for l in d_jul["detalhe"]["despesas_administrativas"]}
    assert linhas["5.4.02"] == 300.0 and linhas["5.4.01"] == 0.0
    db.close()


def test_analitico_mostra_o_plano_inteiro_do_grupo(app_db):
    """Requisito 2026-07-22 (2ª revisão): a DRE analítica mostra TODAS as contas de receita e
    despesa; o balanço analítico, TODAS as de ativo e passivo — com ou sem movimento."""
    db = app_db.get_session(); ot, oid = "loja", 982; mc.seed_plano(db, ot, oid)
    _lancar(db, ot, oid, "5.4.03", "1.1.01", 200.0, datetime(2026, 7, 5))
    _lancar(db, ot, oid, "1.1.01", "5.4.03", 200.0, datetime(2026, 7, 6))   # estorno
    d = mc.dre(db, ot, oid)
    linhas = {l["codigo"]: l["valor"] for l in d["detalhe"]["despesas_administrativas"]}
    assert linhas.get("5.4.03") == 0.0                      # movimento que zera → 0,00
    assert "5.4.04" in linhas                               # sem movimento → LISTADA (0,00)
    todas_54 = {c.codigo for c in db.query(mc.Conta)
                .filter_by(owner_tipo=ot, owner_id=oid, tipo="analitica")
                .filter(mc.Conta.codigo.like("5.4.%"), mc.Conta.ativa == 1).all()}
    assert todas_54 <= set(linhas)                          # o grupo INTEIRO está lá
    # balanço analítico idem: todas as analíticas de ativo/passivo
    b = mc.balanco(db, ot, oid)
    cods_ativo = {l["codigo"] for l in b["detalhe"]["ativo_circulante"]}
    todas_11 = {c.codigo for c in db.query(mc.Conta)
                .filter_by(owner_tipo=ot, owner_id=oid, tipo="analitica")
                .filter(mc.Conta.codigo.like("1.1.%"), mc.Conta.ativa == 1).all()}
    assert todas_11 <= cods_ativo
    # conta INATIVA sem movimento não polui; inativa COM movimento continua aparecendo
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo="5.4.05").first()
    c.ativa = 0
    db.commit()
    d2 = mc.dre(db, ot, oid)
    assert "5.4.05" not in {l["codigo"] for l in d2["detalhe"]["despesas_administrativas"]}
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
