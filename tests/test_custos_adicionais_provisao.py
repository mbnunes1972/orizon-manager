"""Fatia A (resultado da venda) — os custos adicionais viram PROVISÃO.

Antes: com_arq/pro_fid/cust_via/brinde eram só deduzidos do Val_Liq (fora do razão).
Agora: constituídos no contrato como ativo diferido (1.1.06.15-18) × provisão (2.1.04.15-18),
sem tocar a DRE (padrão FASE D2); reconhecidos como despesa comercial na NF-e (baixa do ativo,
a provisão sobrevive); e ajustáveis na AF via ajustar_provisao_delta (#11).
Custo Especial (5º da família): par 1.1.06.20 × 2.1.04.20, despesa 5.3.17.
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


_PARES = [("1.1.06.15", "2.1.04.15", "com_arq", 300.0),
          ("1.1.06.16", "2.1.04.16", "pro_fid", 150.0),
          ("1.1.06.17", "2.1.04.17", "cust_via", 200.0),
          ("1.1.06.18", "2.1.04.18", "brinde", 80.0),
          ("1.1.06.20", "2.1.04.20", "cust_esp", 120.0)]


def test_constituem_ativo_e_provisao_sem_tocar_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 950; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P",
        {r: v for _, _, r, v in _PARES}, ref_base="pf:P")
    for ativo, prov, _r, v in _PARES:
        assert _s(db, ot, oid, ativo) == v      # ativo diferido constituído
        assert _s(db, ot, oid, prov) == v       # provisão constituída
    for desp in ("5.3.15", "5.3.04", "5.3.14", "5.3.12", "5.3.17"):
        assert _s(db, ot, oid, desp) == 0.0     # DRE intacta no contrato
    db.close()


def test_matching_na_nfe_reconhece_despesa_e_baixa_ativo(app_db):
    db = app_db.get_session(); ot, oid = "loja", 951; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"com_arq": 300.0, "brinde": 80.0}, ref_base="pf:P")
    mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    assert _s(db, ot, oid, "5.3.15") == 300.0    # Comissão de Arquiteto → despesa comercial
    assert _s(db, ot, oid, "5.3.12") == 80.0     # Brinde → despesa comercial
    assert _s(db, ot, oid, "1.1.06.15") == 0.0   # ativo diferido baixado
    assert _s(db, ot, oid, "1.1.06.18") == 0.0
    assert _s(db, ot, oid, "2.1.04.15") == 300.0 # provisão SOBREVIVE (paga/reconciliada depois)
    assert _s(db, ot, oid, "2.1.04.18") == 80.0
    db.close()


def test_ajuste_delta_af_funciona_para_os_novos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 952; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"com_arq": 300.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "com_arq", 300.0, 380.0, ref="af:P:1:com_arq:rev1")
    assert _s(db, ot, oid, "2.1.04.15") == 380.0   # +80
    assert _s(db, ot, oid, "1.1.06.15") == 380.0
    assert _s(db, ot, oid, "5.3.15") == 0.0        # ajuste NÃO toca a DRE (#11)
    db.close()


def test_cust_esp_matching_e_conciliacao(app_db):
    # Custo Especial percorre o ciclo completo: constituição no contrato → matching na NF-e
    # (despesa 5.3.17, provisão sobrevive) → conciliação final resolve o saldo (sobra → 4.4.02).
    db = app_db.get_session(); ot, oid = "loja", 953; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"cust_esp": 120.0}, ref_base="pf:P")
    mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    assert _s(db, ot, oid, "5.3.17") == 120.0    # despesa reconhecida na NF-e
    assert _s(db, ot, oid, "1.1.06.20") == 0.0   # ativo diferido baixado
    assert _s(db, ot, oid, "2.1.04.20") == 120.0 # provisão sobrevive
    out = mc.conciliar_final(db, ot, oid, "P", ref_base="cf:P")
    assert out.get("2.1.04.20") == 120.0         # sobra resolvida (nada foi efetivado)
    assert _s(db, ot, oid, "2.1.04.20") == 0.0
    db.close()
