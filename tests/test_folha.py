import json
from datetime import datetime
import mod_folha
import mod_contabil as mc
import mod_provisoes


def _cfg_pct(pct):
    cfg = mod_provisoes.config_financeira_default()
    cfg["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": None, "pct": pct}]
    return cfg


# ── Fase 3: modelo e plano de contas ─────────────────────────────────────────
def test_folha_pagamento_tem_colunas_base_e_beneficios(app_db):
    cols = {c.name for c in app_db.FolhaPagamento.__table__.columns}
    assert "base_comissao" in cols
    assert "beneficios" in cols


def test_evento_folha_beneficios_mapeia_5316():
    deb, cred, _desc = mc.EVENTOS["folha_beneficios"]
    assert deb == "5.3.16"
    assert cred == "1.1.01"
    assert "5.3.16" in {cod for cod, _nome in mc.PLANO_PADRAO}


# ── Motor calculando pela Função ─────────────────────────────────────────────
def test_calcular_folha_consultor_fixa_mais_variavel(seed, app_db):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()   # consultor loja1
    loja = u.loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Consultor de Vendas", salario_fixo=2000.0,
                       usa_comissao_vendas=1, status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Vend", funcao_id=fn.id, usuario_id=u.id, status="ativo")
    db.add(f); db.flush()
    # venda fechada no período, atribuída ao consultor, com orçamento (valor líquido)
    db.add(app_db.Projeto(nome_safe="PFolha", loja_id=loja, criado_por_id=u.id,
                          status="fechado", status_at=datetime(2026, 7, 15)))
    db.add(app_db.Orcamento(projeto_id="PFolha", nome="O", ordem=1, loja_id=loja, valor_liquido=10000.0))
    db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", _cfg_pct(3.0))
    assert c["parte_fixa"] == 2000.0
    assert c["base_comissao"] == 10000.0     # consultor: base = vendas líquidas
    assert c["faixa_pct"] == 3.0
    assert c["parte_variavel"] == 300.0       # 10000 × 3%
    assert c["beneficios"] == 0.0
    assert c["total"] == 2300.0
    # venda de OUTRO mês não conta
    c2 = mod_folha.calcular_folha(db, loja, f, "2026-08", _cfg_pct(3.0))
    assert c2["base_comissao"] == 0.0 and c2["parte_variavel"] == 0.0 and c2["total"] == 2000.0
    db.close()


def test_calcular_folha_soma_beneficios_da_funcao(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    ben = {"at": {"on": True, "valor": 200.0}, "va": {"on": True, "valor": 500.0},
           "ps": {"on": False, "valor": 300.0}}
    fn = app_db.Funcao(loja_id=loja, nome="Montador", salario_fixo=1800.0,
                       usa_comissao_vendas=0, beneficios_json=json.dumps(ben), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="M", funcao_id=fn.id, status="ativo")
    db.add(f); db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", _cfg_pct(0.0))
    assert c["parte_fixa"] == 1800.0
    assert c["beneficios"] == 700.0           # AT 200 + VA 500 (PS off)
    assert c["parte_variavel"] == 0.0         # base editável inicia 0
    assert c["total"] == 2500.0               # 1800 + 0 + 700
    db.close()


def test_resolver_pct_funcao_por_meta():
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    assert mod_folha._resolver_pct_funcao(com, 50000.0) == 0.5    # até 100k → 0,5%
    assert mod_folha._resolver_pct_funcao(com, 150000.0) == 1.0   # acima → 1,0%


def test_resolver_pct_funcao_flat():
    com = {"por_meta": False, "pct": 2.0}
    assert mod_folha._resolver_pct_funcao(com, 999.0) == 2.0


# ── Base de comissão editável ────────────────────────────────────────────────
def test_editar_base_recalcula_variavel(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    fn = app_db.Funcao(loja_id=loja, nome="CFO", salario_fixo=0.0, usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="X", funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07")
    db.add(reg); db.flush()
    ok, err = mod_folha.editar_base(db, loja, reg, 150000.0, _cfg_pct(0.0))
    assert ok and err is None
    assert reg.base_comissao == 150000.0
    assert reg.faixa_pct == 1.0               # acima de 100k
    assert reg.parte_variavel == 1500.0       # 150000 × 1%
    assert reg.total == (reg.parte_fixa or 0.0) + 1500.0 + (reg.beneficios or 0.0)
    # folha paga não é reeditável
    reg.status = "paga"
    ok2, err2 = mod_folha.editar_base(db, loja, reg, 999.0, _cfg_pct(0.0))
    assert ok2 is False and err2
    db.close()


# ── Pagamento posta nas contas 5.3 (fixa, variável, benefícios) ──────────────
def test_pagar_posta_nas_contas_5_3(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 91)
    loja = app_db.Loja(nome="Loja Folha Pagar")
    db.add(loja); db.flush()
    f = app_db.Funcionario(loja_id=loja.id, nome="X", status="ativo", pix="x@pix")
    db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja.id, funcionario_id=f.id, competencia="2026-07",
                                parte_fixa=2000.0, parte_variavel=300.0, beneficios=700.0,
                                total=3000.0, status="aberta")
    db.add(reg); db.flush()
    mod_folha.pagar(db, "loja", 91, reg)

    def saldo(cod):
        c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=91, codigo=cod).first()
        return mc.saldo_conta(db, "loja", 91, c.id) if c else 0.0
    assert saldo("5.3.06") == 2000.0    # Salários de Vendas (parte fixa)
    assert saldo("5.3.01") == 300.0     # Comissão de Vendedor (parte variável)
    assert saldo("5.3.16") == 700.0     # Benefícios a Funcionários
    assert reg.status == "paga"
    mod_folha.pagar(db, "loja", 91, reg)   # idempotente
    assert saldo("5.3.16") == 700.0
    assert mod_folha.serialize(db, reg)["pagamento"] == "PIX: x@pix"   # usa PIX cadastrado
    db.close()


# ── Geração idempotente (parte fixa vem da Função) ───────────────────────────
def test_gerar_folha_um_por_funcionario_ativo_idempotente(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id   # loja2: isolada
    fn = app_db.Funcao(loja_id=loja, nome="Fixo1500", salario_fixo=1500.0, usa_comissao_vendas=0, status="ativo")
    db.add(fn); db.flush()
    fa = app_db.Funcionario(loja_id=loja, nome="A", funcao_id=fn.id, status="ativo")
    fb = app_db.Funcionario(loja_id=loja, nome="B", funcao_id=fn.id, status="inativo")
    db.add(fa); db.add(fb); db.commit()
    mod_folha.gerar_folha(db, loja, "2026-07", _cfg_pct(0.0)); db.commit()
    regs = {r.funcionario_id: r for r in
            db.query(app_db.FolhaPagamento).filter_by(loja_id=loja, competencia="2026-07").all()}
    assert fa.id in regs and regs[fa.id].parte_fixa == 1500.0        # ativo entra, fixa da Função
    assert fb.id not in regs                                          # inativo não entra
    mod_folha.gerar_folha(db, loja, "2026-07", _cfg_pct(0.0)); db.commit()
    n = db.query(app_db.FolhaPagamento).filter_by(loja_id=loja, competencia="2026-07", funcionario_id=fa.id).count()
    assert n == 1  # idempotente
    db.close()


# ── serialize/listar expõem base e benefícios ────────────────────────────────
def test_serialize_e_listar_expoem_base_e_beneficios(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Z", status="ativo"); db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-09",
                                parte_fixa=1000.0, base_comissao=5000.0, parte_variavel=50.0,
                                beneficios=200.0, total=1250.0, status="aberta")
    db.add(reg); db.commit()
    d = mod_folha.serialize(db, reg)
    assert d["base_comissao"] == 5000.0 and d["beneficios"] == 200.0
    out = mod_folha.listar(db, loja, "2026-09")
    assert out["total_beneficios"] == 200.0
    db.close()


# ── HTTP: geração/listagem via endpoints + PATCH da base ─────────────────────
def test_folha_endpoints(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="FixoEndpoint", salario_fixo=1800.0, usa_comissao_vendas=0, status="ativo")
    db.add(fn); db.flush()
    db.add(app_db.Funcionario(loja_id=loja, nome="Fixo", funcao_id=fn.id, status="ativo"))
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/folha/gerar", {"competencia": "2026-07"})
    assert st == 200, d
    item = next(x for x in d["folha"]["itens"] if x["funcionario"] == "Fixo")
    assert item["parte_fixa"] == 1800
    st2, d2 = c.get("/api/folha?competencia=2026-07")
    assert st2 == 200 and d2["folha"]["total_fixa"] >= 1800


def test_folha_patch_base_recalcula(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5}, {"venda_ate": None, "pct": 1.0}]}
    fn = app_db.Funcao(loja_id=loja, nome="CFOEndpoint", salario_fixo=0.0, usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="PatchBase", funcao_id=fn.id, status="ativo")
    db.add(f); db.commit(); fid = f.id; db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/folha/gerar", {"competencia": "2026-07"})
    st, d = c.get("/api/folha?competencia=2026-07")
    reg = next(x for x in d["folha"]["itens"] if x["funcionario"] == "PatchBase")
    st2, d2 = c.patch("/api/folha/%d" % reg["id"], {"base_comissao": 150000.0})
    assert st2 == 200, d2
    assert d2["base_comissao"] == 150000.0
    assert d2["faixa_pct"] == 1.0
    assert d2["parte_variavel"] == 1500.0
