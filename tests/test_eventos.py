import pytest
import mod_contabil as mc


def _q(db):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo=cod).first().id


def test_evento_faturamento_gera_lancamento_correto(app_db):
    db = app_db.get_session(); c = _q(db)
    lan = mc.registrar_evento(db, "loja", 1, "faturamento", 1000.0, projeto_id="Proj_A")
    assert lan["conta_debito_id"] == c("1.1.02")    # Contas a Receber
    assert lan["conta_credito_id"] == c("4.1.01")   # Receita com Vendas
    assert lan["origem"] == "faturamento" and lan["projeto_id"] == "Proj_A" and lan["valor"] == 1000.0
    db.close()


def test_evento_recebimento(app_db):
    db = app_db.get_session(); c = _q(db)
    lan = mc.registrar_evento(db, "loja", 1, "recebimento", 400.0, projeto_id="Proj_B")
    assert lan["conta_debito_id"] == c("1.1.01") and lan["conta_credito_id"] == c("1.1.02")
    db.close()


def test_evento_fechamento_venda_constitui_provisao(app_db):
    db = app_db.get_session(); c = _q(db)
    lan = mc.registrar_evento(db, "loja", 1, "fechamento_venda", 90.0, projeto_id="Proj_C")
    assert lan["conta_debito_id"] == c("5.6.01")       # Constituição de Provisão (despesa)
    assert lan["conta_credito_id"] == c("2.1.04.03")   # Provisão de Garantia Técnica
    db.close()


def test_evento_comissao_e_assistencia(app_db):
    db = app_db.get_session(); c = _q(db)
    l1 = mc.registrar_evento(db, "loja", 1, "pagamento_comissao", 50.0, projeto_id="Proj_D")
    assert l1["conta_debito_id"] == c("2.1.04.01") and l1["conta_credito_id"] == c("1.1.01")
    l2 = mc.registrar_evento(db, "loja", 1, "execucao_assistencia", 20.0, projeto_id="Proj_D")
    assert l2["conta_debito_id"] == c("2.1.04.03") and l2["conta_credito_id"] == c("1.1.01")
    db.close()


def test_evento_desconhecido_rejeitado(app_db):
    db = app_db.get_session()
    with pytest.raises(ValueError):
        mc.registrar_evento(db, "loja", 1, "evento_inexistente", 10.0)
    db.close()
