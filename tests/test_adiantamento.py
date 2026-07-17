import mod_adiantamento


# ── Task 1: modelo ───────────────────────────────────────────────────────────
def test_adiantamento_tabela_existe(app_db):
    cols = {c.name for c in app_db.AdiantamentoFuncionario.__table__.columns}
    for c in ("funcionario_id", "tipo", "competencia", "valor", "abater",
              "competencia_abate", "quitado", "ref"):
        assert c in cols


# ── Task 2: config ───────────────────────────────────────────────────────────
def test_config_financeira_tem_folha_default():
    import mod_provisoes
    cfg = mod_provisoes.config_financeira_default()
    assert cfg["folha"]["adiantamento_oficial_ativo"] is False
    assert cfg["folha"]["adiantamento_oficial_pct"] == 40.0


# ── Task 3: saldo / abatimentos / oficial ────────────────────────────────────
def test_saldo_debito_soma_nao_quitados(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="D", status="ativo"); db.add(f); db.flush()
    db.add(app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="emprestimo",
           competencia="2026-07", valor=500.0, abater=1, competencia_abate="2026-08", quitado=0))
    db.add(app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="adiantamento",
           competencia="2026-07", valor=200.0, abater=1, competencia_abate="2026-07", quitado=1))
    db.commit()
    assert mod_adiantamento.saldo_debito(db, f.id) == 500.0
    assert mod_adiantamento.abatimentos_competencia(db, f.id, "2026-08") == 500.0
    assert mod_adiantamento.abatimentos_competencia(db, f.id, "2026-07") == 0.0
    db.close()


def test_upsert_oficial_40pct_carteira(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Registrado", salario_fixo=2000.0,
                       regime_contratacao="registrado", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="R", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    it = mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0); db.commit()
    assert it is not None and it.valor == 800.0 and it.tipo == "oficial"
    assert it.abater == 1 and it.competencia_abate == "2026-07"
    mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0); db.commit()
    n = db.query(app_db.AdiantamentoFuncionario).filter_by(funcionario_id=f.id, tipo="oficial").count()
    assert n == 1
    db.close()


def test_upsert_oficial_ignora_terceirizado(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Terc", salario_fixo=2000.0,
                       regime_contratacao="terceirizacao", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="T", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    assert mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0) is None
    db.close()


def test_quitar_da_competencia(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Q", status="ativo"); db.add(f); db.flush()
    db.add(app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="adiantamento",
           competencia="2026-07", valor=300.0, abater=1, competencia_abate="2026-07", quitado=0))
    db.commit()
    n = mod_adiantamento.quitar_da_competencia(db, f.id, "2026-07"); db.commit()
    assert n == 1
    assert mod_adiantamento.saldo_debito(db, f.id) == 0.0
    db.close()
