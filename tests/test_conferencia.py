"""Fatia 2 #13 — Conferência e Implantação do Pedido: dois lançamentos auditáveis (ajuste do Custo de
Fábrica pela diferença do PE + reclassificação p/ Outros Fornecedores), ambos ativo × provisão, nunca DRE.
"""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def test_conferencia_ajusta_fabrica_e_reclassifica_outros_sem_dre(app_db):
    db = app_db.get_session(); ot, oid = "loja", 985; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 4000.0}, ref_base="pf:P")
    out = mc.conferencia_pedido(db, ot, oid, "P", 4000.0, 4500.0, 1000.0, ref_base="conf:P")
    assert out == {"custo_fabrica_delta": 500.0, "outros_fornecedores": 1000.0}
    # (a) fábrica ajustada para 4500 e (b) 1000 reclassificado p/ Outros Fornecedores
    assert _s(db, ot, oid, "2.1.04.06") == 3500.0 and _s(db, ot, oid, "1.1.06.06") == 3500.0
    assert _s(db, ot, oid, "2.1.04.14") == 1000.0 and _s(db, ot, oid, "1.1.06.14") == 1000.0
    assert _s(db, ot, oid, "5.1.01") == 0.0   # DRE intacta (nada reconhecido — é a NF-e que reconhece)
    db.close()


def test_conferencia_so_ajuste_sem_migracao(app_db):
    db = app_db.get_session(); ot, oid = "loja", 986; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 4000.0}, ref_base="pf:P")
    out = mc.conferencia_pedido(db, ot, oid, "P", 4000.0, 4200.0, 0.0, ref_base="conf:P")
    assert out == {"custo_fabrica_delta": 200.0}
    assert _s(db, ot, oid, "2.1.04.06") == 4200.0
    assert _s(db, ot, oid, "2.1.04.14") == 0.0    # sem migração
    db.close()


def test_conferencia_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 987; mc.seed_plano(db, ot, oid)
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 4000.0}, ref_base="pf:P")
    mc.conferencia_pedido(db, ot, oid, "P", 4000.0, 4500.0, 1000.0, ref_base="conf:P")
    mc.conferencia_pedido(db, ot, oid, "P", 4000.0, 4500.0, 1000.0, ref_base="conf:P")  # 2ª vez
    assert _s(db, ot, oid, "2.1.04.06") == 3500.0 and _s(db, ot, oid, "2.1.04.14") == 1000.0  # não duplicou
    db.close()
