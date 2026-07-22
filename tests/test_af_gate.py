"""Fatia C — gate da Aprovação Financeira. disparar_deltas_af lança o ajuste (ativo × provisão, nunca
DRE) de cada rubrica que mudou entre versões, mapeando as chaves do painel → rubricas contábeis.
(O limite/step-up de Diretor é mod_parcelas.exige_aprovacao_diretor, já testado.)
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_disparar_delta_de_rubrica_alterada_sem_tocar_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 995; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"assistencia": 500.0, "impostos": 1000.0}, ref_base="pf:P")
    out = mc.disparar_deltas_af(db, ot, oid, "P", {"assist": 700.0, "prov_imp": 1000.0}, ref_base="af:P:rev1")
    assert out == {"assistencia": 200.0}    # só a assistência mudou (500→700); impostos igual
    assert _s(db, ot, oid, "2.1.04.05") == 700.0 and _s(db, ot, oid, "1.1.06.05") == 700.0  # provisão + ativo
    assert _s(db, ot, oid, "5.2.13") == 0.0   # DRE intacta (o delta não reconhece despesa)
    db.close()


def test_disparar_delta_custo_adicional_com_arq(app_db):
    # F0 (bug ①): os custos adicionais (com_arq/pro_fid/cust_via/brinde) passam a ser ajustáveis na AF.
    db = app_db.get_session(); ot, oid = "loja", 994; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"com_arq": 500.0}, ref_base="pf:P")
    out = mc.disparar_deltas_af(db, ot, oid, "P", {"com_arq": 800.0}, ref_base="af:P:rev1")
    assert out == {"com_arq": 300.0}
    assert _s(db, ot, oid, "2.1.04.15") == 800.0 and _s(db, ot, oid, "1.1.06.15") == 800.0
    assert _s(db, ot, oid, "5.3.15") == 0.0   # DRE intacta (o delta não reconhece despesa)
    db.close()


def test_disparar_sem_mudanca_nao_lanca(app_db):
    db = app_db.get_session(); ot, oid = "loja", 996; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"assistencia": 500.0}, ref_base="pf:P")
    out = mc.disparar_deltas_af(db, ot, oid, "P", {"assist": 500.0}, ref_base="af:P:rev1")
    assert out == {}
    assert _s(db, ot, oid, "2.1.04.05") == 500.0   # inalterado
    db.close()


def test_disparar_impostos_ajusta_1_1_05(app_db):
    db = app_db.get_session(); ot, oid = "loja", 997; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": 1000.0}, ref_base="pf:P")
    out = mc.disparar_deltas_af(db, ot, oid, "P", {"prov_imp": 1200.0}, ref_base="af:P:rev1")
    assert out == {"impostos": 200.0}
    assert _s(db, ot, oid, "2.1.04.13") == 1200.0 and _s(db, ot, oid, "1.1.05") == 1200.0
    db.close()


def test_disparar_converge_reaprovar_mesmo_alvo_nao_duplica(app_db):
    # idempotência por VALOR: ajustar do saldo atual p/ o alvo → re-aprovar o mesmo alvo com ref nova = no-op
    db = app_db.get_session(); ot, oid = "loja", 998; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"assistencia": 500.0}, ref_base="pf:P")
    mc.disparar_deltas_af(db, ot, oid, "P", {"assist": 700.0}, ref_base="af:P:rev1:1")
    out2 = mc.disparar_deltas_af(db, ot, oid, "P", {"assist": 700.0}, ref_base="af:P:rev1:2")  # ref nova, mesmo alvo
    assert out2 == {}                              # já está em 700 → nada a ajustar
    assert _s(db, ot, oid, "2.1.04.05") == 700.0   # não duplicou
    db.close()
