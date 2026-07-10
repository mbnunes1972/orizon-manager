from datetime import datetime, timedelta
import mod_cronograma
import mod_provisoes


# ── HTTP: editar data_prevista com reautenticação + auditoria (Gerente+) ─────────
def test_data_prevista_reauth_gerente_edita_e_audita(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/Proj_L1/ciclo/9/data-prevista",
                   {"login": "dir_l1", "senha": "senha123", "data_prevista": "2026-08-15"})
    assert st == 200 and d.get("ok") is True, d
    db = app_db.get_session()
    try:
        e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="Proj_L1", etapa_codigo="9").first()
        assert e9 and e9.data_prevista_conclusao == datetime(2026, 8, 15)
        log = (db.query(app_db.LogAcaoGerencial)
               .filter_by(projeto_nome="Proj_L1", acao="editar_data_prevista", etapa_alvo="9").first())
        assert log is not None                    # auditado (quem/quando/old→new)
        assert '"valor_novo"' in (log.contexto or "")
    finally:
        db.close()


def test_data_prevista_consultor_barrado(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # autorizador é consultor (sem 'autorizar') → 403, mesmo com senha correta
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/data-prevista",
                   {"login": "cons_l1", "senha": "senha123", "data_prevista": "2026-08-20"})
    assert st == 403 and d.get("ok") is False


def test_data_prevista_senha_errada_barrada(http_client_factory, seed, projetos_dir, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/data-prevista",
                   {"login": "dir_l1", "senha": "errada", "data_prevista": "2026-08-20"})
    assert st == 403 and d.get("ok") is False


def _cfg(fases):
    cfg = mod_provisoes.config_financeira_default()
    cfg["cronograma_padrao"] = fases
    return cfg


def test_config_default_inclui_cronograma():
    cfg = mod_provisoes.config_financeira_default()
    assert "cronograma_padrao" in cfg
    assert any(f["codigo"] == "8" for f in cfg["cronograma_padrao"])


def test_cronograma_padrao_normaliza_e_ignora_invalido():
    fases = mod_cronograma.cronograma_padrao(_cfg([
        {"codigo": "9", "prazo_dias": "5"},   # string vira int
        {"codigo": "", "prazo_dias": 3},      # sem código → ignorado
        {"codigo": "10", "prazo_dias": -4},   # negativo → 0
    ]))
    assert {"codigo": "9", "prazo_dias": 5} in fases
    assert {"codigo": "10", "prazo_dias": 0} in fases
    assert all(f["codigo"] for f in fases)


def test_gerar_cronograma_define_data_prevista(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1, 12, 0, 0)
    cfg = _cfg([{"codigo": "9", "prazo_dias": 5}, {"codigo": "13", "prazo_dias": 45}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjX", cfg, d0); db.commit()
    e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="9").first()
    e13 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="13").first()
    assert e9.data_prevista_conclusao == d0 + timedelta(days=5)
    assert e13.data_prevista_conclusao == d0 + timedelta(days=45)
    assert e9.concluido_em is None   # data_conclusao nasce vazia
    db.close()


def test_gerar_cronograma_idempotente_e_preserva_conclusao(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1)
    cfg = _cfg([{"codigo": "9", "prazo_dias": 5}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjY", cfg, d0); db.commit()
    # etapa concluída manualmente (data_conclusao preenchida)
    e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjY", etapa_codigo="9").first()
    e9.status = "concluido"; e9.concluido_em = datetime(2026, 7, 3); db.commit()
    # reexecuta o cronograma → recomputa data_prevista, NÃO duplica nem apaga a conclusão
    mod_cronograma.gerar_cronograma_projeto(db, "ProjY", cfg, d0 + timedelta(days=1)); db.commit()
    regs = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjY", etapa_codigo="9").all()
    assert len(regs) == 1
    assert regs[0].data_prevista_conclusao == d0 + timedelta(days=6)   # recomputado do novo D0
    assert regs[0].concluido_em == datetime(2026, 7, 3)                # conclusão preservada
    db.close()
