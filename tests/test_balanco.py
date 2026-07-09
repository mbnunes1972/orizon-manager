import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_balanco_fecha_por_partida_dobrada(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 50); c = _q(db, 50)
    # Faturamento 1000 (D Contas a Receber / C Receita)
    mc.registrar_evento(db, "loja", 50, "faturamento", 1000.0, projeto_id="P")
    # Recebimento 600 (D Caixa / C Contas a Receber)
    mc.registrar_evento(db, "loja", 50, "recebimento", 600.0, projeto_id="P")
    # Despesa administrativa 200 (D Aluguel / C Caixa)
    mc.lancar(db, "loja", 50, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=200.0)
    b = mc.balanco(db, "loja", 50)
    db.close()
    # Ativo: Caixa 400 (600-200) + Contas a Receber 400 (1000-600) = 800 circulante
    assert b["ativo"]["circulante"] == 800.0 and b["ativo"]["total"] == 800.0
    # PL: resultado do exercício = receita 1000 - despesa 200 = 800
    assert b["patrimonio_liquido"]["resultado_exercicio"] == 800.0
    assert b["total_passivo_mais_pl"] == 800.0
    assert b["confere"] is True             # Ativo (800) = Passivo (0) + PL (800)


def test_balanco_vazio_zerado_e_confere(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 51)
    b = mc.balanco(db, "loja", 51)
    db.close()
    assert b["ativo"]["total"] == 0.0 and b["total_passivo_mais_pl"] == 0.0 and b["confere"] is True
