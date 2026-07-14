"""Fatia B (resultado da venda) — RESULTADO FINANCEIRO, ramo FINANCEIRA.

Quando o financiamento corre por uma financeira (Aymoré/Cartão), o Cust_Fin é DESPESA
financeira (taxa/deságio absorvido). Tratada como rubrica provisionada:
- constituída no contrato (ativo diferido 1.1.06.19 × provisão 2.1.04.19), sem tocar a DRE;
- reconhecida por rota PRÓPRIA (5.5.04 Custo Financeiro × baixa do ativo) — NÃO entra no matching
  operacional da NF-e (como impostos);
- ajustável na AF via ajustar_provisao_delta (#11).

(O ramo LOJA — receita financeira a apropriar por parcela — vem na etapa seguinte.)
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_custo_financeiro_constitui_provisao_sem_tocar_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 960; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    assert _s(db, ot, oid, "1.1.06.19") == 500.0
    assert _s(db, ot, oid, "2.1.04.19") == 500.0
    assert _s(db, ot, oid, "5.5.04") == 0.0     # despesa financeira NÃO reconhecida no contrato
    db.close()


def test_custo_financeiro_fica_fora_do_matching_operacional(app_db):
    db = app_db.get_session(); ot, oid = "loja", 961; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")   # matching OPERACIONAL
    assert _s(db, ot, oid, "1.1.06.19") == 500.0   # ativo intacto — não é baixado pelo matching operacional
    assert _s(db, ot, oid, "5.5.04") == 0.0
    db.close()


def test_custo_financeiro_reconhecimento_por_rota_propria(app_db):
    db = app_db.get_session(); ot, oid = "loja", 962; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    mc.registrar_evento(db, ot, oid, "reconhecimento_despesa_custo_financeiro", 500.0, projeto_id="P", ref="rf:P")
    assert _s(db, ot, oid, "5.5.04") == 500.0      # despesa financeira reconhecida (resultado financeiro)
    assert _s(db, ot, oid, "1.1.06.19") == 0.0     # ativo diferido baixado
    assert _s(db, ot, oid, "2.1.04.19") == 500.0   # provisão sobrevive (paga à financeira depois)
    db.close()


def test_custo_financeiro_ajuste_delta_af(app_db):
    db = app_db.get_session(); ot, oid = "loja", 963; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_financeiro": 500.0}, ref_base="pf:P")
    mc.ajustar_provisao_delta(db, ot, oid, "P", "custo_financeiro", 500.0, 620.0, ref="af:P:1:custo_financeiro:rev1")
    assert _s(db, ot, oid, "2.1.04.19") == 620.0   # +120
    assert _s(db, ot, oid, "1.1.06.19") == 620.0
    assert _s(db, ot, oid, "5.5.04") == 0.0        # ajuste NÃO toca a DRE (#11)
    db.close()


# ── Ramo LOJA (financiamento direto) — recebíveis com juros a apropriar, SEM despesa ──

def test_financiamento_direto_juros_a_apropriar_no_contrato(app_db):
    db = app_db.get_session(); ot, oid = "loja", 964; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    assert _s(db, ot, oid, "1.1.07") == 300.0    # recebível dos juros (só juros; VAVO fica no 1.1.02)
    assert _s(db, ot, oid, "2.1.07") == 300.0    # receita financeira a apropriar (diferida)
    assert _s(db, ot, oid, "4.4.03") == 0.0      # ainda não realizada
    db.close()


def test_financiamento_direto_recebe_e_apropria_por_parcela(app_db):
    db = app_db.get_session(); ot, oid = "loja", 965; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    mc.registrar_evento(db, ot, oid, "receber_parcela_direto", 100.0, projeto_id="P", ref="rp:P:1")
    assert _s(db, ot, oid, "1.1.01") == 100.0    # caixa
    assert _s(db, ot, oid, "1.1.07") == 200.0    # recebível baixado
    mc.registrar_evento(db, ot, oid, "apropriar_receita_financeira", 100.0, projeto_id="P", ref="ap:P:1")
    assert _s(db, ot, oid, "2.1.07") == 200.0    # a apropriar reduz na competência
    assert _s(db, ot, oid, "4.4.03") == 100.0    # receita financeira realizada
    db.close()


def test_financiamento_direto_ciclo_completo_fecha_sem_despesa(app_db):
    db = app_db.get_session(); ot, oid = "loja", 966; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 300.0, projeto_id="P", ref="jd:P")
    for i in (1, 2, 3):
        mc.registrar_evento(db, ot, oid, "receber_parcela_direto", 100.0, projeto_id="P", ref="rp:P:%d" % i)
        mc.registrar_evento(db, ot, oid, "apropriar_receita_financeira", 100.0, projeto_id="P", ref="ap:P:%d" % i)
    assert _s(db, ot, oid, "1.1.07") == 0.0      # recebível zerado
    assert _s(db, ot, oid, "2.1.07") == 0.0      # tudo apropriado
    assert _s(db, ot, oid, "4.4.03") == 300.0    # receita financeira total realizada
    assert _s(db, ot, oid, "1.1.01") == 300.0    # caixa recebido
    assert _s(db, ot, oid, "5.5.04") == 0.0      # ramo loja NÃO tem despesa financeira (capital próprio)
    db.close()
