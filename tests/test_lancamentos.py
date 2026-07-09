import pytest
import mod_contabil as mc

# app_db é module-scoped -> os lançamentos persistem entre os testes deste arquivo.
# Por isso cada teste usa contas ANALÍTICAS distintas (sem acúmulo cruzado).


def _q(db):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=1, codigo=cod).first().id


def test_lancar_entre_analiticas(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); c = _q(db)
    lan = mc.lancar(db, "loja", 1, conta_debito_id=c("1.1.01"), conta_credito_id=c("4.1.01"),
                    valor=100.0, projeto_id="Proj_X", historico="venda")
    assert lan["id"] and lan["valor"] == 100.0 and lan["projeto_id"] == "Proj_X"
    db.close()


def test_lancar_rejeita_sintetica_e_invalidos(app_db):
    # só levanta exceções (não persiste) -> pode reusar contas
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); c = _q(db)
    with pytest.raises(ValueError):   # conta "5" é sintética
        mc.lancar(db, "loja", 1, conta_debito_id=c("5"), conta_credito_id=c("1.1.02"), valor=10)
    with pytest.raises(ValueError):   # valor <= 0
        mc.lancar(db, "loja", 1, conta_debito_id=c("1.1.02"), conta_credito_id=c("4.1.02"), valor=0)
    with pytest.raises(ValueError):   # débito == crédito
        mc.lancar(db, "loja", 1, conta_debito_id=c("1.1.02"), conta_credito_id=c("1.1.02"), valor=10)
    db.close()


def test_tem_lancamentos_impede_apagar(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); c = _q(db)
    estoques = c("1.1.03")   # conta própria deste teste
    mc.lancar(db, "loja", 1, conta_debito_id=estoques, conta_credito_id=c("2.1.01"), valor=50)
    r = mc.remover_conta(db, "loja", 1, estoques)   # tem lançamento -> inativa (não apaga)
    assert r["acao"] == "inativada"
    db.close()


def test_saldo_conta_por_natureza(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); c = _q(db)
    dev = c("1.1.04")   # Adiantamentos (ativo, devedora) — conta própria
    cred = c("4.2.01")  # Receita de Serviços (credora)
    mc.lancar(db, "loja", 1, conta_debito_id=dev, conta_credito_id=cred, valor=100)
    mc.lancar(db, "loja", 1, conta_debito_id=dev, conta_credito_id=cred, valor=30)
    assert mc.saldo_conta(db, "loja", 1, dev) == 130.0    # devedora, debitada 2x
    assert mc.saldo_conta(db, "loja", 1, cred) == 130.0   # credora, creditada 2x
    db.close()


def test_razao_e_cross_owner(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 1); c = _q(db)
    dev = c("1.2.1.01")  # Itens de Informática (ativo, devedora) — conta própria
    mc.lancar(db, "loja", 1, conta_debito_id=dev, conta_credito_id=c("4.4.01"), valor=100)
    raz = mc.razao(db, "loja", 1, dev)
    assert len(raz["linhas"]) == 1 and raz["saldo_final"] == 100.0 and raz["linhas"][0]["dc"] == "D"
    with pytest.raises(PermissionError):
        mc.lancar(db, "loja", 999, conta_debito_id=dev, conta_credito_id=c("4.4.01"), valor=1)
    db.close()
