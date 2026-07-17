import json
from datetime import datetime
import mod_comissao


# ── Task 1: modelo ───────────────────────────────────────────────────────────
def test_comissao_folha_tabela_existe(app_db):
    cols = {c.name for c in app_db.ComissaoFolha.__table__.columns}
    for c in ("funcionario_id", "competencia", "origem", "papel", "projeto_nome", "etapa_codigo",
              "base", "base_ajustada", "pct", "valor", "status", "ref_etapa"):
        assert c in cols


# ── Task 2: papel↔etapa e base por ambiente ──────────────────────────────────
def test_papel_da_etapa():
    assert mod_comissao.papel_da_etapa("10") == "medicao"
    assert mod_comissao.papel_da_etapa("11") == "projeto_executivo"
    assert mod_comissao.papel_da_etapa("11a") == "projeto_executivo"
    assert mod_comissao.papel_da_etapa("17") == "montagem"
    assert mod_comissao.papel_da_etapa("18") == "assistencia"
    assert mod_comissao.papel_da_etapa("13") is None   # produção não gera comissão de papel


def test_base_ambientes_projeto_inteiro(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Med", status="ativo"); db.add(f); db.flush()
    db.add(app_db.PoolAmbiente(projeto_id="PBase", nome="a", nome_exibicao="Cozinha",
                               xml_path="x", ambientes_json="[]", order_total=8000.0))
    db.add(app_db.PoolAmbiente(projeto_id="PBase", nome="b", nome_exibicao="Quarto",
                               xml_path="y", ambientes_json="[]", order_total=2000.0))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PBase", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    db.commit()
    base = mod_comissao.base_ambientes(db, "PBase", "medicao", f.id)
    assert base == 10000.0     # projeto inteiro = Σ order_total
    db.close()


def test_base_ambientes_por_ambiente(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Med2", status="ativo"); db.add(f); db.flush()
    p1 = app_db.PoolAmbiente(projeto_id="PBase2", nome="a", nome_exibicao="Cozinha",
                             xml_path="x", ambientes_json="[]", order_total=8000.0)
    p2 = app_db.PoolAmbiente(projeto_id="PBase2", nome="b", nome_exibicao="Quarto",
                             xml_path="y", ambientes_json="[]", order_total=2000.0)
    db.add(p1); db.add(p2); db.flush()
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PBase2", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=p1.id))   # só a cozinha
    db.commit()
    base = mod_comissao.base_ambientes(db, "PBase2", "medicao", f.id)
    assert base == 8000.0
    db.close()


# ── Task 3: preparar_comissao_etapa ──────────────────────────────────────────
def test_preparar_comissao_etapa_cria_item(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    com = {"por_meta": False, "pct": 3.0}
    fn = app_db.Funcao(loja_id=loja, nome="Medidor", usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Med", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    db.add(app_db.PoolAmbiente(projeto_id="PComis", nome="a", nome_exibicao="Cozinha",
                               xml_path="x", ambientes_json="[]", order_total=10000.0))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PComis", papel="medicao",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    et = app_db.CicloEtapa(projeto_nome="PComis", etapa_codigo="10", status="concluido",
                           concluido_em=datetime(2026, 7, 15), funcao_responsavel_id=fn.id,
                           responsavel_funcionario_id=f.id)
    db.add(et); db.commit()
    item = mod_comissao.preparar_comissao_etapa(db, loja, et); db.commit()
    assert item is not None
    assert item.competencia == "2026-07"
    assert item.papel == "medicao"
    assert item.base == 10000.0
    assert item.pct == 3.0
    assert item.valor == 300.0
    assert item.status == "previsto"
    mod_comissao.preparar_comissao_etapa(db, loja, et); db.commit()   # idempotente
    n = db.query(app_db.ComissaoFolha).filter_by(projeto_nome="PComis", etapa_codigo="10").count()
    assert n == 1
    db.close()


def test_preparar_comissao_etapa_sem_comissao_nao_cria(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Semcom", usa_comissao_vendas=0, status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="X", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    et = app_db.CicloEtapa(projeto_nome="PSem", etapa_codigo="10", status="concluido",
                           concluido_em=datetime(2026, 7, 1), funcao_responsavel_id=fn.id,
                           responsavel_funcionario_id=f.id)
    db.add(et); db.commit()
    assert mod_comissao.preparar_comissao_etapa(db, loja, et) is None
    db.close()


def test_set_etapa_status_dispara_comissao(seed, app_db):
    import main
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Montador", usa_comissao_vendas=0,
                       comissao_json=json.dumps({"por_meta": False, "pct": 2.0}), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Mnt", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    db.add(app_db.Projeto(nome_safe="PHook", loja_id=loja, status="fechado"))
    db.add(app_db.PoolAmbiente(projeto_id="PHook", nome="a", nome_exibicao="Sala",
                               xml_path="x", ambientes_json="[]", order_total=5000.0))
    db.add(app_db.AtribuicaoAmbiente(loja_id=loja, projeto_nome="PHook", papel="montagem",
                                     funcionario_id=f.id, pool_ambiente_id=None))
    db.add(app_db.CicloEtapa(projeto_nome="PHook", etapa_codigo="17", status="em_andamento",
                             funcao_responsavel_id=fn.id, responsavel_funcionario_id=f.id))
    db.commit()
    main._set_etapa_status(db, "PHook", "17", "concluido", None); db.commit()
    item = db.query(app_db.ComissaoFolha).filter_by(projeto_nome="PHook", etapa_codigo="17").first()
    assert item is not None and item.valor == 100.0   # 5000 × 2%
    assert item.competencia is not None
    db.close()


def test_gerar_folha_soma_itens_de_comissao(seed, app_db):
    import mod_folha, mod_provisoes
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Montador", salario_fixo=1000.0, usa_comissao_vendas=0, status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Mnt", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    for i, v in enumerate((150.0, 250.0)):
        db.add(app_db.ComissaoFolha(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
               origem="papel", papel="montagem", projeto_nome="P%d" % i, etapa_codigo="17",
               base=0.0, pct=0.0, valor=v, status="previsto", ref_etapa="P%d:17:%d" % (i, f.id)))
    db.commit()
    cfg = mod_provisoes.config_financeira_default()
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    assert reg.parte_variavel == 400.0        # 150 + 250
    assert reg.total == 1400.0                # fixa 1000 + 400
    # item cancelado não soma
    db.query(app_db.ComissaoFolha).filter_by(ref_etapa="P0:17:%d" % f.id).first().status = "cancelado"
    db.commit()
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    db.refresh(reg)
    assert reg.parte_variavel == 250.0
    db.close()


def test_gerar_folha_consultor_vira_item_venda(seed, app_db):
    import mod_folha, mod_provisoes
    from datetime import datetime
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()
    loja = u.loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Consultor de Vendas", salario_fixo=2000.0,
                       usa_comissao_vendas=1, status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Vend", funcao_id=fn.id, usuario_id=u.id, status="ativo")
    db.add(f); db.flush()
    db.add(app_db.Projeto(nome_safe="PV", loja_id=loja, criado_por_id=u.id,
                          status="fechado", status_at=datetime(2026, 7, 10)))
    db.add(app_db.Orcamento(projeto_id="PV", nome="O", ordem=1, loja_id=loja, valor_liquido=10000.0))
    db.commit()
    cfg = mod_provisoes.config_financeira_default()
    cfg["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": None, "pct": 3.0}]
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    item = db.query(app_db.ComissaoFolha).filter_by(ref_etapa="venda:%d:2026-07" % f.id).first()
    assert item is not None and item.origem == "venda" and item.valor == 300.0
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    assert reg.parte_variavel == 300.0 and reg.total == 2300.0    # fixa 2000 + comissão 300
    db.close()


def test_cancelar_comissao_etapa(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    it = app_db.ComissaoFolha(loja_id=loja, funcionario_id=1, competencia="2026-07",
         origem="papel", papel="medicao", projeto_nome="PC", etapa_codigo="10",
         base=1000.0, pct=3.0, valor=30.0, status="previsto", ref_etapa="PC:10:1")
    db.add(it); db.commit()
    mod_comissao.cancelar_comissao_etapa(db, "PC", "10", 1); db.commit()
    assert db.query(app_db.ComissaoFolha).filter_by(ref_etapa="PC:10:1").first().status == "cancelado"
    db.close()
