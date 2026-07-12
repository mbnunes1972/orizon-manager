import mod_contabil as mc

# app_db module-scoped -> uso owner distinto por teste para isolar os lançamentos.


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_dre_estrutura_e_sinais(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 10); c = _q(db, 10)
    # Receita bruta 1000 (faturamento)
    mc.registrar_evento(db, "loja", 10, "faturamento", 1000.0, projeto_id="P1")
    # Dedução 80 (Simples Nacional s/ Vendas: D 4.3.01 / C Caixa)
    mc.lancar(db, "loja", 10, conta_debito_id=c("4.3.01"), conta_credito_id=c("1.1.01"), valor=80.0)
    # Despesa administrativa 200 (Aluguel: D 5.4.01 / C Caixa)
    mc.lancar(db, "loja", 10, conta_debito_id=c("5.4.01"), conta_credito_id=c("1.1.01"), valor=200.0)
    d = mc.dre(db, "loja", 10)
    db.close()
    assert d["receita_bruta"] == 1000.0
    assert d["deducoes"] == 80.0                 # dedução com sinal certo (D−C positivo, subtraído)
    assert d["receita_liquida"] == 920.0
    assert d["despesas_administrativas"] == 200.0
    assert d["ebitda"] == 720.0
    assert d["lucro_liquido"] == 720.0


def test_dre_com_cmv_e_provisao(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 11); c = _q(db, 11)
    mc.registrar_evento(db, "loja", 11, "faturamento", 500.0, projeto_id="P2")   # receita 500
    mc.lancar(db, "loja", 11, conta_debito_id=c("5.1.01"), conta_credito_id=c("2.1.01"), valor=150.0)  # CMV 150
    mc.registrar_evento(db, "loja", 11, "fechamento_venda_garantia", 30.0, projeto_id="P2")  # FASE D2: constituição DIFERIDA (1.1.06), não toca DRE
    d = mc.dre(db, "loja", 11)
    db.close()
    assert d["receita_liquida"] == 500.0
    assert d["cmv_csp"] == 150.0
    assert d["lucro_bruto"] == 350.0
    assert d["constituicao_provisoes"] == 0.0   # FASE D2: despesa da provisão só entra na DRE na NF-e (matching pleno)
    assert d["ebitda"] == 350.0 and d["lucro_liquido"] == 350.0


def test_dre_vazio_zerado(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 12)
    d = mc.dre(db, "loja", 12)
    db.close()
    assert d["receita_bruta"] == 0.0 and d["lucro_liquido"] == 0.0
