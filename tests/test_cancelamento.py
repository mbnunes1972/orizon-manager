"""Cancelamento de contrato (dentro do prazo, ANTES da NF-e): estorno TOTAL da constituição do contrato
— Receita a Realizar + provisões×ativos diferidos (reusa devolver_venda f=1.0) + juros a apropriar do
ramo loja (2.1.07 × 1.1.07). Origem/rótulo próprios no razão (distingue de devolução). O reembolso físico
de valores já recebidos fica p/ a Tesouraria (módulo futuro)."""
import mod_contabil as mc


def _s(db, ot, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, ot, oid, c.id)


def _montar_contrato(db, ot, oid, proj, com_juros=True):
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", 10000.0, projeto_id=proj, ref="v:" + proj)
    mc.constituir_provisoes_fechamento(db, ot, oid, proj,
                                       {"custo_fabrica": 4000.0, "impostos": 1000.0}, ref_base="pf:" + proj)
    if com_juros:   # ramo loja: juros a apropriar (1.1.07 × 2.1.07)
        mc.registrar_evento(db, ot, oid, "constituir_juros_direto", 600.0, projeto_id=proj, ref="j:" + proj)


def test_cancelar_contrato_estorna_diferido_e_juros(app_db):
    db = app_db.get_session(); ot, oid = "loja", 989
    _montar_contrato(db, ot, oid, "P")
    out = mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    # diferido zerado
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "1.1.02") == 0.0
    assert _s(db, ot, oid, "2.1.04.06") == 0.0 and _s(db, ot, oid, "1.1.06.06") == 0.0
    assert _s(db, ot, oid, "2.1.04.13") == 0.0 and _s(db, ot, oid, "1.1.05") == 0.0
    # juros a apropriar zerados (recebível 1.1.07 + passivo 2.1.07)
    assert _s(db, ot, oid, "1.1.07") == 0.0 and _s(db, ot, oid, "2.1.07") == 0.0
    assert out.get("1.1.07") == 600.0
    db.close()


def test_cancelar_contrato_idempotente(app_db):
    db = app_db.get_session(); ot, oid = "loja", 988
    _montar_contrato(db, ot, oid, "P", com_juros=False)
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")   # 2ª vez — não duplica
    assert _s(db, ot, oid, "2.1.06") == 0.0 and _s(db, ot, oid, "2.1.04.06") == 0.0
    db.close()


def test_cancelamento_endpoint_estorna_e_trava(http_client_factory, seed, app_db):
    # cobre o fluxo do BOTÃO com LANÇAMENTOS reais: 200 + estorno + status "cancelado". (NOTA: o lock
    # "database is locked" do SQLite em ARQUIVO — ordem commit×upsert — NÃO reproduz aqui, pois o app_db
    # de teste é em memória; este teste garante o contrato do endpoint, não a corrida de sessões.)
    db = app_db.get_session()
    ot, own = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, own)
    mc.registrar_evento(db, ot, own, "registro_venda_contrato", 10000.0, projeto_id="Proj_L1", ref="v:Proj_L1")
    mc.constituir_provisoes_fechamento(db, ot, own, "Proj_L1", {"custo_fabrica": 4000.0}, ref_base="pf:Proj_L1")
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    st, d = c.post("/api/orcamentos/%d/cancelamento" % oid, {"login": "dir_l1", "senha": "senha123"})
    assert st == 200, (st, d)
    assert d.get("ok") and d.get("status") == "cancelado", d
    assert d.get("revertido"), d   # estornou lançamentos de fato


def test_cancelar_contrato_deixa_recebivel_a_devolver_se_houve_recebimento(app_db):
    # se o cliente já pagou (recebimento_venda abate 1.1.02), o estorno da Receita a Realizar deixa
    # 1.1.02 CREDOR = valor a devolver (reembolso físico → Tesouraria, módulo futuro).
    db = app_db.get_session(); ot, oid = "loja", 987
    _montar_contrato(db, ot, oid, "P", com_juros=False)
    mc.registrar_evento(db, ot, oid, "recebimento_venda", 3000.0, projeto_id="P", ref="rec:P")  # cliente pagou 3000
    mc.cancelar_contrato(db, ot, oid, "P", ref_base="cancel:P")
    assert _s(db, ot, oid, "2.1.06") == 0.0        # receita a realizar zerada
    assert _s(db, ot, oid, "1.1.02") == -3000.0    # recebível credor = a devolver ao cliente
    db.close()
