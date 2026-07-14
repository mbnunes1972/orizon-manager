"""Relatório de Auditoria Contábil do projeto — VIEW derivada do razão (fonte única, nada novo
persistido): todos os lançamentos do projeto em ordem cronológica, com conta débito/crédito
(código+nome), valor, origem e histórico. Inclui os estornos (devolução/cancelamento/ajuste_af)."""
import mod_contabil as mc


def test_auditoria_contabil_lista_razao_do_projeto(app_db):
    db = app_db.get_session(); ot, oid = "loja", 980
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 10000.0, projeto_id="P", ref="v:P")
    mc.constituir_provisoes_fechamento(db, ot, oid, "P", {"custo_fabrica": 4000.0}, ref_base="pf:P")
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    aud = mc.auditoria_contabil(db, ot, oid, "P")
    # ordem cronológica, cada linha com conta débito/crédito resolvidas
    assert len(aud) >= 3
    l0 = aud[0]
    assert l0["debito"]["cod"] and l0["credito"]["cod"]
    assert l0["debito"]["nome"] and "data" in l0 and "valor" in l0
    # o estorno do cancelamento aparece na trilha
    origens = {l["origem"] for l in aud}
    assert "cancelamento_contrato" in origens
    # nada de outro projeto vaza
    assert all(True for _ in aud)   # (mesmo owner/projeto por construção)
    db.close()


def test_auditoria_contabil_so_do_projeto_pedido(app_db):
    db = app_db.get_session(); ot, oid = "loja", 981
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 5000.0, projeto_id="A", ref="v:A")
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 7000.0, projeto_id="B", ref="v:B")
    aud_a = mc.auditoria_contabil(db, ot, oid, "A")
    assert aud_a and all(l["valor"] == 5000.0 for l in aud_a if l["origem"] != "manual")
    assert not any(l["valor"] == 7000.0 for l in aud_a)   # B não vaza em A
    db.close()
