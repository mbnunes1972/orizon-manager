"""FASE B2 — eventos de dupla-partida: Adiantamento de Clientes → receita segmentada
(Mercadoria 4.1.01 / Serviço 4.2.01) → CMV=CFO (5.1.01×2.1.04.06) → pagamento fábrica.
Núcleo do razão (sem HTTP). Design do Fable 5 (2026-07-11)."""
import mod_contabil as mc


def _saldo(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


_EVENTOS_B2 = {
    "recebimento_venda":                ("1.1.01", "2.1.06"),
    "faturamento_mercadoria_adiantado": ("2.1.06", "4.1.01"),
    "faturamento_mercadoria_a_receber": ("1.1.02", "4.1.01"),
    "faturamento_servico_adiantado":    ("2.1.06", "4.2.01"),
    "faturamento_servico_a_receber":    ("1.1.02", "4.2.01"),
    "faturamento_cmv":                  ("5.1.01", "2.1.04.06"),
    "pagamento_fabrica":                ("2.1.04.06", "1.1.01"),
}


def test_eventos_b2_existem_com_par_correto():
    for ev, (d, c) in _EVENTOS_B2.items():
        assert ev in mc.EVENTOS, ev
        assert mc.EVENTOS[ev][0] == d and mc.EVENTOS[ev][1] == c, ev


def test_recebimento_venda_credita_adiantamento(app_db):
    db = app_db.get_session(); ot, oid = "loja", 300; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    assert _saldo(db, ot, oid, "2.1.06") == 100000.0   # passivo
    assert _saldo(db, ot, oid, "1.1.01") == 100000.0   # caixa
    db.close()


def test_faturar_segmento_pool_cheio_so_adiantado(app_db):
    db = app_db.get_session(); ot, oid = "loja", 301; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0
    assert _saldo(db, ot, oid, "2.1.06") == 35000.0
    assert _saldo(db, ot, oid, "1.1.02") == 0.0        # nada a receber (tudo adiantado)
    db.close()


def test_faturar_segmento_split_parcial(app_db):
    db = app_db.get_session(); ot, oid = "loja", 302; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 40000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    assert _saldo(db, ot, oid, "2.1.06") == 0.0        # pool esgotado
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0
    assert _saldo(db, ot, oid, "1.1.02") == 25000.0    # resto a receber
    db.close()


def test_faturar_segmento_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 303; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")   # 2ª vez
    assert _saldo(db, ot, oid, "4.1.01") == 65000.0    # não duplica
    db.close()


def test_adiantamento_nunca_negativo_dois_segmentos(app_db):
    db = app_db.get_session(); ot, oid = "loja", 304; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "servico", 35000.0, ref_base="fat:NFSE-P-1")
    assert mc.saldo_adiantamento_projeto(db, ot, oid, "P") == 0.0
    assert _saldo(db, ot, oid, "2.1.06") == 0.0
    db.close()


def test_faturamento_cmv_uma_vez_por_projeto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 305; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "faturamento_cmv", 40000.0, projeto_id="P", ref="cmv:P")
    mc.registrar_evento(db, ot, oid, "faturamento_cmv", 40000.0, projeto_id="P", ref="cmv:P")  # reproc.
    assert _saldo(db, ot, oid, "5.1.01") == 40000.0       # 1× no resultado
    assert _saldo(db, ot, oid, "2.1.04.06") == 40000.0    # passivo com a fábrica
    db.close()


def test_fluxo_completo_balanco_fecha_e_dre(app_db):
    """Cenário A do design: Val_Cont 100k (65/35), CFO 40k, recebimento total."""
    db = app_db.get_session(); ot, oid = "loja", 306; mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 100000.0, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", 65000.0, ref_base="fat:NFE-P-9")
    mc.registrar_evento(db, ot, oid, "faturamento_cmv", 40000.0, projeto_id="P", ref="cmv:P")
    mc.faturar_segmento(db, ot, oid, "P", "servico", 35000.0, ref_base="fat:NFSE-P-1")
    mc.registrar_evento(db, ot, oid, "pagamento_fabrica", 40000.0, projeto_id="P", ref="pgf:P:1")
    assert mc.balanco(db, ot, oid)["confere"] is True
    assert _saldo(db, ot, oid, "1.1.01") == 60000.0       # 100k − 40k fábrica
    assert _saldo(db, ot, oid, "2.1.06") == 0.0           # adiantamento zerou ao faturar
    assert _saldo(db, ot, oid, "2.1.04.06") == 0.0        # provisão fábrica baixada
    d = mc.dre(db, ot, oid)
    assert d["receita_bruta"] == 100000.0                 # 65k + 35k, sem duplicar
    assert d["cmv_csp"] == 40000.0                        # CFO 1× (deixa de ser 0)
    assert d["lucro_bruto"] == 60000.0
    db.close()


def test_soma_receitas_igual_val_cont_via_orquestrador(app_db):
    """Σ(4.1.01 + 4.2.01) == Val_Cont exato, com segmentação que gera dízima."""
    from mod_orcamento_params import segmentar
    db = app_db.get_session(); ot, oid = "loja", 307; mc.seed_plano(db, ot, oid)
    val_cont = 100000.01
    merc, serv = segmentar(val_cont, 65.0)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", val_cont, projeto_id="P", ref="rcb:P:1")
    mc.faturar_segmento(db, ot, oid, "P", "mercadoria", merc, ref_base="fat:NFE-P-9")
    mc.faturar_segmento(db, ot, oid, "P", "servico", serv, ref_base="fat:NFSE-P-1")
    assert round(_saldo(db, ot, oid, "4.1.01") + _saldo(db, ot, oid, "4.2.01"), 2) == round(val_cont, 2)
    db.close()


# ── Congelamento da segmentação na assinatura (A6) ────────────────────────────────────────────
def test_congelar_segmentacao_grava_default_da_loja(app_db):
    import json as _j, main
    from database import Loja, Projeto
    db = app_db.get_session()
    lj = Loja(nome="Loja Cong 1", pct_mercadoria=65.0, pct_servico=35.0)
    db.add(lj); db.flush()
    db.add(Projeto(nome_safe="Proj_Cong_1", loja_id=lj.id, status="quente")); db.commit()
    seg = main._congelar_segmentacao_no_projeto(db, lj.id, "Proj_Cong_1")
    db.commit()
    assert seg == {"pct_mercadoria": 65.0, "pct_servico": 35.0}
    par = _j.loads(db.query(Projeto).filter_by(nome_safe="Proj_Cong_1").first().parametros_json)
    assert par["pct_mercadoria"] == 65.0 and par["pct_servico"] == 35.0
    db.close()


def test_congelar_segmentacao_override_vence_e_preserva_params(app_db):
    import json as _j, main
    from database import Loja, Projeto
    db = app_db.get_session()
    lj = Loja(nome="Loja Cong 2", pct_mercadoria=65.0, pct_servico=35.0)
    db.add(lj); db.flush()
    db.add(Projeto(nome_safe="Proj_Cong_2", loja_id=lj.id, status="quente",
                   parametros_json=_j.dumps({"pct_mercadoria": 80.0, "pct_servico": 20.0, "carga_trib": 9.0})))
    db.commit()
    seg = main._congelar_segmentacao_no_projeto(db, lj.id, "Proj_Cong_2")
    db.commit()
    assert seg == {"pct_mercadoria": 80.0, "pct_servico": 20.0}   # override do projeto vence a loja
    par = _j.loads(db.query(Projeto).filter_by(nome_safe="Proj_Cong_2").first().parametros_json)
    assert par["carga_trib"] == 9.0                               # não apaga os demais parâmetros
    db.close()


# ── B2.2: margem_projeto expõe custo_servico → destrava reconciliar(proporcional_custo_direto) ──
def test_margem_projeto_expoe_custo_servico(app_db):
    db = app_db.get_session(); ot, oid = "loja", 322; mc.seed_plano(db, ot, oid)
    cfg = {"provisoes": {"assist_pct": 3.0}, "provisoes_contabeis": {"montagem_pct": 5.0, "garantia_pct": 2.0}}
    mc.constituir_provisoes_venda(db, ot, oid, "P", 10000.0, cfg, ref_base="prov:P")   # 500/300/200
    m = mc.margem_projeto(db, ot, oid, "P")
    assert m["custo_servico"] == 1000.0     # 500 montagem + 300 assistência + 200 garantia (5.6.x do projeto)
    # expor custo_servico NÃO altera a margem (as provisões já são subtraídas individualmente)
    assert m["margem_contribuicao"] == -1000.0
    db.close()


def test_reconciliar_proporcional_custo_direto_nao_quebra(app_db):
    db = app_db.get_session(); ot, oid = "loja", 323; mc.seed_plano(db, ot, oid)
    c = lambda cod: db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first().id
    # custo direto (CMV 5.1): A=900, B=300 → 75%/25%
    mc.registrar_evento(db, ot, oid, "faturamento_cmv", 900.0, projeto_id="A", ref="cmv:A")
    mc.registrar_evento(db, ot, oid, "faturamento_cmv", 300.0, projeto_id="B", ref="cmv:B")
    mc.lancar(db, ot, oid, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=400.0)
    rec = mc.reconciliar(db, ot, oid, metodologia="proporcional_custo_direto")   # antes: KeyError
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["A"]["valor_rateado"] == 300.0    # 75% de 400
    assert aloc["B"]["valor_rateado"] == 100.0    # 25% de 400
    db.close()
