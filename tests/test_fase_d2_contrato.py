"""FASE D2 · Fase 2 — constituir as 10 rubricas no CONTRATO em Passivo (via ativo diferido 1.1.06),
SEM tocar a DRE; registrar a venda cheia em 2.1.06 "Receita a Realizar"; recebimento abate 1.1.02.
Nada de resultado é reconhecido no contrato (isso só ocorre na NF-e — Fase 3)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


# rubrica -> (subconta 1.1.06 do ativo diferido, conta 2.1.04 da provisão)
RUBRICAS = {
    "montagem":            ("1.1.06.02", "2.1.04.02"),
    "garantia":            ("1.1.06.03", "2.1.04.03"),
    "assistencia":         ("1.1.06.05", "2.1.04.05"),
    "custo_fabrica":       ("1.1.06.06", "2.1.04.06"),
    "frete_fabrica":       ("1.1.06.07", "2.1.04.07"),
    "frete_local":         ("1.1.06.08", "2.1.04.08"),
    "insumos":             ("1.1.06.09", "2.1.04.09"),
    "com_medidor":         ("1.1.06.10", "2.1.04.10"),
    "com_proj_exec":       ("1.1.06.11", "2.1.04.11"),
    "retencao_com_vendas": ("1.1.06.12", "2.1.04.12"),
}


def test_prov_fechamento_inclui_custo_fabrica():
    assert "custo_fabrica" in mc._PROV_FECHAMENTO
    assert mc.EVENTOS["fechamento_venda_custo_fabrica"][:2] == ("1.1.06.06", "2.1.04.06")
    # as 9 de sempre agora debitam o ativo diferido 1.1.06.0X (não mais 5.6.0X)
    assert mc.EVENTOS["fechamento_venda_montagem"][0] == "1.1.06.02"
    assert mc.EVENTOS["fechamento_venda_retencao_com_vendas"][0] == "1.1.06.12"


def test_constituir_10_rubricas_nao_toca_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 710; mc.seed_plano(db, ot, oid)
    valores = {
        "montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
        "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
        "com_proj_exec": 350.0, "retencao_com_vendas": 500.0, "impostos": 5000.0,
    }
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", valores, ref_base="pf:P")
    # cada rubrica das 10: ativo diferido debitado × provisão creditada, mesmo valor
    for chave, (ativo, prov) in RUBRICAS.items():
        assert _s(db, ot, oid, ativo) == valores[chave], "ativo %s" % ativo
        assert _s(db, ot, oid, prov) == valores[chave], "provisão %s" % prov
    # impostos seguem no ativo diferido próprio (1.1.05 × 2.1.04.13), não em 1.1.06
    assert _s(db, ot, oid, "1.1.05") == 5000.0 and _s(db, ot, oid, "2.1.04.13") == 5000.0
    # NADA toca a DRE no contrato
    d = mc.dre(db, ot, oid)
    assert d["constituicao_provisoes"] == 0.0 and d["cmv_csp"] == 0.0
    assert d["deducoes"] == 0.0 and d["receita_bruta"] == 0.0 and d["lucro_liquido"] == 0.0
    db.close()


def test_registro_venda_contrato_receita_a_realizar(app_db):
    db = app_db.get_session(); ot, oid = "loja", 711; mc.seed_plano(db, ot, oid)
    assert mc.EVENTOS["registro_venda_contrato"][:2] == ("1.1.02", "2.1.06")
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 236826.82, projeto_id="P", ref="venda:P")
    assert _s(db, ot, oid, "1.1.02") == 236826.82     # Contas a Receber (ativo)
    assert _s(db, ot, oid, "2.1.06") == 236826.82     # Receita a Realizar (passivo)
    assert mc.dre(db, ot, oid)["receita_bruta"] == 0.0   # receita só na NF-e
    db.close()


def test_recebimento_venda_abate_contas_a_receber(app_db):
    db = app_db.get_session(); ot, oid = "loja", 712; mc.seed_plano(db, ot, oid)
    assert mc.EVENTOS["recebimento_venda"][:2] == ("1.1.01", "1.1.02")
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 100000.0, projeto_id="P", ref="venda:P")
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 20000.0, projeto_id="P", ref="rcb:P:1")
    assert _s(db, ot, oid, "1.1.01") == 20000.0        # Caixa entra
    assert _s(db, ot, oid, "1.1.02") == 80000.0        # Contas a Receber abatido
    assert _s(db, ot, oid, "2.1.06") == 100000.0       # Receita a Realizar intocada
    db.close()
