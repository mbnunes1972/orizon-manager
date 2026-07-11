"""FASE C1 — painel de Provisões agrupado por TIPO A/B/C/D (data-driven).
A: comissões/pessoas · B: custos futuros · C: aquisição/fábrica · D: fiscal · O: outros (não mapeada)."""
import mod_contabil as mc


def test_contas_provisao_tem_tipo(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 500)
    contas = {c["codigo"]: c for c in mc.contas_provisao_do_plano(db, "loja", 500)}
    assert contas["2.1.04.10"]["tipo"] == "A" and contas["2.1.04.12"]["tipo"] == "A"
    assert contas["2.1.04.02"]["tipo"] == "B" and contas["2.1.04.05"]["tipo"] == "B"
    assert contas["2.1.04.06"]["tipo"] == "C" and contas["2.1.04.09"]["tipo"] == "C"
    assert contas["2.1.04.13"]["tipo"] == "D"
    db.close()


def test_dashboard_agrupa_por_tipo_com_subtotal(app_db):
    db = app_db.get_session(); ot, oid = "loja", 501; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P",
        {"com_medidor": 100.0, "montagem": 200.0, "frete_fabrica": 50.0, "impostos": 80.0},
        ref_base="pf:P")
    dash = mc.dashboard_financeiro(db, ot, oid)
    grupos = {g["tipo"]: g for g in dash["provisoes_por_tipo"]}
    assert grupos["A"]["rotulo"] == "Comissões / Pessoas" and grupos["A"]["subtotal"] == 100.0
    assert grupos["B"]["subtotal"] == 200.0
    assert grupos["C"]["subtotal"] == 50.0     # frete_fabrica 50 + custo_fabrica 0
    assert grupos["D"]["subtotal"] == 80.0
    # ordem A,B,C,D e total geral = soma dos subtotais
    assert [g["tipo"] for g in dash["provisoes_por_tipo"] if g["tipo"] in "ABCD"] == ["A", "B", "C", "D"]
    assert round(sum(g["subtotal"] for g in dash["provisoes_por_tipo"]), 2) == dash["total_provisoes_abertas"]
    db.close()


def test_conta_nova_sem_tipo_cai_em_outros(app_db):
    db = app_db.get_session(); ot, oid = "loja", 502; mc.seed_plano(db, ot, oid)
    db.add(mc.Conta(owner_tipo=ot, owner_id=oid, codigo="2.1.04.99", nome="Provisão Ad Hoc",
                    grupo=2, tipo="analitica", natureza=mc._natureza(2), ativa=1, ordem=999))
    db.commit()
    contas = {c["codigo"]: c for c in mc.contas_provisao_do_plano(db, ot, oid)}
    assert contas["2.1.04.99"]["tipo"] == "O"
    dash = mc.dashboard_financeiro(db, ot, oid)
    assert any(g["tipo"] == "O" and g["rotulo"] == "Outros" for g in dash["provisoes_por_tipo"])
    db.close()
