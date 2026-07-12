"""FASE D2 · Fase 3 — matching pleno na NF-e: reconhecer_despesas_nfe reconhece TODAS as despesas
planejadas (10 rubricas) de uma vez, debitando 5.6.0X (ou 5.1.01 p/ fábrica) × baixa do ativo diferido
1.1.06.0X. A Provisão (2.1.04.0X) SOBREVIVE à NF-e. Idempotente. Impostos NÃO entram (têm rota própria)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


# rubrica -> (ativo diferido 1.1.06, provisão 2.1.04, despesa reconhecida na NF-e)
RUBRICAS = {
    "montagem":            ("1.1.06.02", "2.1.04.02", "5.6.02"),
    "garantia":            ("1.1.06.03", "2.1.04.03", "5.6.01"),
    "assistencia":         ("1.1.06.05", "2.1.04.05", "5.6.03"),
    "custo_fabrica":       ("1.1.06.06", "2.1.04.06", "5.1.01"),
    "frete_fabrica":       ("1.1.06.07", "2.1.04.07", "5.6.04"),
    "frete_local":         ("1.1.06.08", "2.1.04.08", "5.6.05"),
    "insumos":             ("1.1.06.09", "2.1.04.09", "5.6.06"),
    "com_medidor":         ("1.1.06.10", "2.1.04.10", "5.6.07"),
    "com_proj_exec":       ("1.1.06.11", "2.1.04.11", "5.6.08"),
    "retencao_com_vendas": ("1.1.06.12", "2.1.04.12", "5.6.09"),
}
VALORES = {"montagem": 1000.0, "garantia": 200.0, "assistencia": 300.0, "custo_fabrica": 60000.0,
           "frete_fabrica": 400.0, "frete_local": 150.0, "insumos": 100.0, "com_medidor": 250.0,
           "com_proj_exec": 350.0, "retencao_com_vendas": 500.0}


def _contrato(db, ot, oid, proj):
    mc.constituir_provisoes_fechamento(db, ot, oid, proj, dict(VALORES, impostos=5000.0), ref_base="pf:" + proj)


def test_matching_reconhece_todas_as_despesas_uma_vez(app_db):
    db = app_db.get_session(); ot, oid = "loja", 720; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    # antes da NF-e: nada de despesa no resultado
    d0 = mc.dre(db, ot, oid)
    assert d0["cmv_csp"] == 0.0 and d0["constituicao_provisoes"] == 0.0
    out = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    assert out == VALORES
    for chave, (ativo, prov, desp) in RUBRICAS.items():
        assert _s(db, ot, oid, desp) == VALORES[chave]                       # despesa reconhecida (5.6.0X ou 5.1.01)
        assert _s(db, ot, oid, ativo) == 0.0                                 # ativo diferido baixado
        assert _s(db, ot, oid, prov) == VALORES[chave]                       # PROVISÃO sobrevive
    # 5.1.01 é o CMV da fábrica (pode somar outras origens; aqui só a fábrica)
    assert _s(db, ot, oid, "5.1.01") == 60000.0
    # DRE agora reflete os custos, cada um UMA vez
    d = mc.dre(db, ot, oid)
    assert d["cmv_csp"] == 60000.0                                           # 5.1.01 fábrica
    assert d["constituicao_provisoes"] == 3250.0                            # soma das 9 rubricas 5.6.x
    assert d["deducoes"] == 0.0                                              # impostos NÃO entram no matching
    assert _s(db, ot, oid, "1.1.05") == 5000.0 and _s(db, ot, oid, "2.1.04.13") == 5000.0
    db.close()


def test_matching_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 721; mc.seed_plano(db, ot, oid)
    _contrato(db, ot, oid, "P")
    mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")
    out2 = mc.reconhecer_despesas_nfe(db, ot, oid, "P", ref_base="match:P")   # 2ª vez (reproc. NF-e)
    assert out2 == {}                                                        # nada a reconhecer de novo
    assert _s(db, ot, oid, "5.1.01") == 60000.0                              # não duplicou o CMV
    assert _s(db, ot, oid, "5.6.02") == 1000.0                               # nem a montagem
    db.close()


def test_faturamento_cmv_foi_retirado():
    """O evento antigo faturamento_cmv (5.1.01 × 2.1.04.06) foi substituído pelo matching (× 1.1.06.06)."""
    assert "faturamento_cmv" not in mc.EVENTOS
    assert mc.EVENTOS["reconhecimento_despesa_custo_fabrica"][:2] == ("5.1.01", "1.1.06.06")
