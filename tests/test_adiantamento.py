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


def test_gerar_folha_cria_oficial_e_liquido(seed, app_db):
    import mod_folha, mod_provisoes
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Reg", salario_fixo=2000.0,
                       regime_contratacao="registrado", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="R", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    cfg = mod_provisoes.config_financeira_default()
    cfg["folha"]["adiantamento_oficial_ativo"] = True
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    d = mod_folha.serialize(db, reg)
    assert d["total"] == 2000.0
    assert d["abatimentos"] == 800.0
    assert d["liquido_pagar"] == 1200.0
    assert d["saldo_debito"] == 800.0
    assert any(a["tipo"] == "oficial" and a["valor"] == 800.0 for a in d["adiantamentos"])
    db.close()


def test_pagar_quita_adiantamentos_da_competencia(seed, app_db):
    import mod_folha
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="P", status="ativo", pix="p@x"); db.add(f); db.flush()
    ad = app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="adiantamento",
         competencia="2026-07", valor=300.0, abater=1, competencia_abate="2026-07", quitado=0)
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
         parte_fixa=1000.0, total=1000.0, status="aprovada")
    db.add(ad); db.add(reg); db.flush()
    mod_folha.pagar(db, "loja", 99, reg)
    assert reg.status == "paga"
    db.refresh(ad); assert ad.quitado == 1
    db.close()


def test_adiantamento_crud_endpoint(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="CrudFunc", status="ativo"); db.add(f); db.commit(); fid = f.id; db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/adiantamentos", {"funcionario_id": fid, "tipo": "emprestimo",
        "competencia": "2026-07", "valor": 500.0, "abater": True, "competencia_abate": "2026-08"})
    assert st in (200, 201), d
    aid = d["id"]
    st2, d2 = c.patch("/api/adiantamentos/%d" % aid, {"abater": False})
    assert st2 == 200 and d2["abater"] is False
    st3, d3 = c.patch("/api/adiantamentos/%d" % aid, {"remover": True})
    assert st3 == 200 and d3.get("removido") is True
    db2 = app_db.get_session()
    assert db2.query(app_db.AdiantamentoFuncionario).filter_by(id=aid).first() is None
    db2.close()


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
