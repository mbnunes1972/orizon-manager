"""#11 — ajuste (delta) de provisão na Aprovação Financeira (Fatia 2).

Ao confirmar AF1/AF2 (ou a conferência #13), quando a estimativa mudou, lança um delta
SÓ entre o ativo diferido (1.1.06.0X / 1.1.05 impostos) e a provisão (2.1.04.0X) — NUNCA
toca a DRE (isso é a NF-e, #12). Aumento constitui mais; redução reverte, capada ao saldo
do ativo em aberto (padrão do espelho do reclassificar_provisao). Idempotente por ref.
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_aumento_constitui_ativo_e_provisao_sem_tocar_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 900; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    lan = mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 1200.0, ref="af:P:1:custo_fabrica:rev1")
    assert lan is not None
    assert _s(db, ot, oid, "2.1.04.06") == 1200.0    # provisão subiu +200
    assert _s(db, ot, oid, "1.1.06.06") == 1200.0    # ativo diferido subiu +200
    assert _s(db, ot, oid, "5.6.06") == 0.0          # DRE intacta
    assert _s(db, ot, oid, "5.1.01") == 0.0          # CMV/fábrica intacto
    db.close()


def test_reducao_reverte_com_ativo_cheio(app_db):
    db = app_db.get_session(); ot, oid = "loja", 901; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 700.0, ref="af:P:1:custo_fabrica:rev1")
    assert _s(db, ot, oid, "2.1.04.06") == 700.0     # reverteu -300
    assert _s(db, ot, oid, "1.1.06.06") == 700.0
    assert _s(db, ot, oid, "5.6.06") == 0.0
    db.close()


def test_reducao_capada_quando_ativo_ja_baixado_na_nfe(app_db):
    db = app_db.get_session(); ot, oid = "loja", 902; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    # NF-e baixou 600 do ativo (matching pleno) → ativo em aberto = 400
    mc.registrar_evento(db, ot, oid, "reconhecimento_despesa_custo_fabrica", 600.0, projeto_id="P", ref="nfe:P:cf")
    assert _s(db, ot, oid, "1.1.06.06") == 400.0
    # redução de 500 pedida, mas só 400 de ativo em aberto → reverte no máximo 400 (cap)
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 500.0, ref="af:P:1:custo_fabrica:rev2")
    assert _s(db, ot, oid, "1.1.06.06") == 0.0        # ativo zerado (não fica negativo)
    assert _s(db, ot, oid, "2.1.04.06") == 600.0      # provisão reduzida só pelo cap (1000-400); resto p/ conciliação
    db.close()


def test_delta_zero_nao_lanca(app_db):
    db = app_db.get_session(); ot, oid = "loja", 903; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    out = mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 1000.0, ref="af:P:1:custo_fabrica:rev1")
    assert out is None
    assert _s(db, ot, oid, "2.1.04.06") == 1000.0     # inalterado
    db.close()


def test_idempotente_por_ref(app_db):
    db = app_db.get_session(); ot, oid = "loja", 904; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 1000.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 1200.0, ref="af:P:1:custo_fabrica:rev1")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_fabrica", 1000.0, 1200.0, ref="af:P:1:custo_fabrica:rev1")  # 2ª vez
    assert _s(db, ot, oid, "2.1.04.06") == 1200.0     # não duplicou
    assert _s(db, ot, oid, "1.1.06.06") == 1200.0
    db.close()


def test_impostos_usa_ativo_1_1_05(app_db):
    # impostos vivem em 1.1.05 (não 1.1.06.13) — o delta deve usar o par do evento (generic)
    db = app_db.get_session(); ot, oid = "loja", 905; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"impostos": 5000.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "impostos", 5000.0, 5200.0, ref="af:P:1:impostos:rev1")
    assert _s(db, ot, oid, "2.1.04.13") == 5200.0
    assert _s(db, ot, oid, "1.1.05") == 5200.0
    db.close()
