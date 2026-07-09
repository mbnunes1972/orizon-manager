import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_sugere_por_nome_da_conta(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 80); c = _q(db, 80)
    s = mc.sugerir_conta(db, "loja", 80, "pagamento do aluguel da loja")
    db.close()
    assert s and s["codigo"] == "5.4.01" and s["nome"] == "Aluguel"   # bate por 'aluguel'


def test_sugere_por_historico(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 81); c = _q(db, 81)
    # histórico: um lançamento em Energia Elétrica com um termo idiossincrático
    mc.lancar(db, "loja", 81, conta_debito_id=c("5.4.02"), conta_credito_id=c("1.1.01"),
              valor=100.0, historico="conta de luz cpfl unidade central")
    s = mc.sugerir_conta(db, "loja", 81, "conta de luz cpfl")   # não bate o nome, bate o histórico
    db.close()
    assert s and s["codigo"] == "5.4.02"


def test_sugere_none_sem_match(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 82)
    assert mc.sugerir_conta(db, "loja", 82, "zzz") is None
    db.close()


def test_endpoint_sugerir_e_registra_ia(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/financeiro/sugerir-conta", {"texto": "aluguel da loja"})
    assert st == 200 and d["sugestao"]["codigo"] == "5.4.01"
