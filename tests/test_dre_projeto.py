import mod_contabil as mc


def _q(db, oid):
    return lambda cod: db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first().id


def test_margem_projeto(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 20); c = _q(db, 20)
    # Projeto A: receita 1000, custo produto 400, comissão 100, provisão 30
    mc.registrar_evento(db, "loja", 20, "faturamento", 1000.0, projeto_id="A")
    mc.lancar(db, "loja", 20, conta_debito_id=c("5.1.01"), conta_credito_id=c("2.1.01"), valor=400.0, projeto_id="A")
    mc.lancar(db, "loja", 20, conta_debito_id=c("5.3.01"), conta_credito_id=c("1.1.01"), valor=100.0, projeto_id="A")
    mc.registrar_evento(db, "loja", 20, "fechamento_venda", 30.0, projeto_id="A")
    r = mc.margem_projeto(db, "loja", 20, "A")
    db.close()
    assert r["receita"] == 1000.0 and r["custo_produto"] == 400.0
    assert r["comercial"] == 100.0 and r["provisao_garantia"] == 30.0
    assert r["margem_contribuicao"] == 470.0     # 1000-400-0-100-30


def test_margem_isola_por_projeto(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 21)
    mc.registrar_evento(db, "loja", 21, "faturamento", 500.0, projeto_id="X")
    mc.registrar_evento(db, "loja", 21, "faturamento", 200.0, projeto_id="Y")
    rx = mc.margem_projeto(db, "loja", 21, "X")
    ry = mc.margem_projeto(db, "loja", 21, "Y")
    todos = mc.margem_todos_projetos(db, "loja", 21)
    db.close()
    assert rx["receita"] == 500.0 and ry["receita"] == 200.0
    assert [t["projeto_id"] for t in todos] == ["X", "Y"]   # ordenado por margem desc
    assert mc.projetos_com_lancamento.__name__            # existe
