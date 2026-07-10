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


# ── v12: funcionário responsável filtrado pela função exigida pela fase ──────────
def test_responsavel_funcionario_restrito_a_funcao(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fmed = app_db.Funcao(loja_id=loja, nome="Medidor")
    fmont = app_db.Funcao(loja_id=loja, nome="Montador")
    db.add_all([fmed, fmont]); db.flush()
    medidor = app_db.Funcionario(loja_id=loja, nome="Ana Medidora", funcao_id=fmed.id, status="ativo")
    montador = app_db.Funcionario(loja_id=loja, nome="Beto Montador", funcao_id=fmont.id, status="ativo")
    db.add_all([medidor, montador])
    et = app_db.CicloEtapa(projeto_nome="Proj_L1", etapa_codigo="10", funcao_responsavel_id=fmed.id)
    db.add(et); db.commit()
    fmed_id, med_id, mont_id = fmed.id, medidor.id, montador.id
    db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    # função errada (Montador numa fase de Medidor) → barrado
    st, d = c.post("/api/projetos/Proj_L1/ciclo/10/responsavel", {"funcionario_id": mont_id})
    assert st == 400 and d.get("ok") is False, d
    # função certa → aceito
    st2, d2 = c.post("/api/projetos/Proj_L1/ciclo/10/responsavel", {"funcionario_id": med_id})
    assert st2 == 200 and d2.get("ok") is True, d2
    # o /ciclo passa a expor a função exigida e o funcionário escolhido
    _, cic = c.get("/api/projetos/Proj_L1/ciclo")
    e10 = next(x for x in cic["ciclo"] if x["etapa_codigo"] == "10")
    assert e10["funcao_responsavel_nome"] == "Medidor"
    assert e10["responsavel_funcionario_nome"] == "Ana Medidora"
    # dropdown filtrado por função lista só o medidor
    _, lst = c.get("/api/funcionarios?funcao_id=%d" % fmed_id)
    nomes = {x["nome"] for x in lst["itens"]}
    assert "Ana Medidora" in nomes and "Beto Montador" not in nomes


def test_usuarios_loja_expoe_funcao_do_funcionario(http_client_factory, seed, projetos_dir, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fcon = app_db.Funcao(loja_id=loja, nome="Consultor de Vendas"); db.add(fcon); db.flush()
    func = app_db.Funcionario(loja_id=loja, nome="Carla Vendas", funcao_id=fcon.id, status="ativo")
    db.add(func); db.flush()
    u = app_db.Usuario(nome="Carla Vendas", login="carla@loja.com", nivel="consultor",
                       loja_id=loja, ativo=1, funcionario_id=func.id)
    u.set_senha("x"); db.add(u); db.commit()
    db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.get("/api/admin/usuarios")
    carla = next(x for x in d["usuarios"] if x["login"] == "carla@loja.com")
    assert carla["funcao_nome"] == "Consultor de Vendas"   # Função herdada do Funcionário
    assert carla["nivel"] == "consultor"                   # Perfil (acesso) inalterado


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
        {"codigo": "9", "prazo_dias": "5", "funcao_id": "7"},   # strings viram int
        {"codigo": "", "prazo_dias": 3},      # sem código → ignorado
        {"codigo": "10", "prazo_dias": -4},   # negativo → 0; sem funcao_id → None
    ]))
    by = {f["codigo"]: f for f in fases}
    assert by["9"] == {"codigo": "9", "prazo_dias": 5, "funcao_id": 7}
    assert by["10"] == {"codigo": "10", "prazo_dias": 0, "funcao_id": None}
    assert all(f["codigo"] for f in fases)


def test_gerar_cronograma_herda_funcao_responsavel(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1)
    cfg = _cfg([{"codigo": "10", "prazo_dias": 10, "funcao_id": 42}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjFn", cfg, d0); db.commit()
    e10 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjFn", etapa_codigo="10").first()
    assert e10.funcao_responsavel_id == 42               # função herdada do padrão no D0
    assert e10.responsavel_funcionario_id is None         # funcionário nasce vazio
    db.close()


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
