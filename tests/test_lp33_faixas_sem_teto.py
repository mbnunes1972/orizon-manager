# -*- coding: utf-8 -*-
"""LP-33 (docs/db/TAREFA_LOTE_ACEITE6.md, Tarefa 3) — a faixa sem teto e o rótulo que mente.

Decisão do Marcelo (16/09):
- 3a: a comparação `<` já cobre venda acima de todas as faixas (aplica `faixas[-1]`, sem buraco
  de comissão) — o que faltava era a GARANTIA de que a última faixa é declaradamente sem teto
  (`venda_ate=None`), não uma faixa qualquer. `mod_provisoes.validar_faixas_comissao` (nova,
  compartilhada) e o configurador da tela passam a exigir isso.
- 3b: o código está certo (`<`, estritamente menor — "abaixo de", não "até"); só o rótulo mudou
  na tela. Nenhuma mudança em `resolver_comissao_venda`/`_resolver_pct_funcao`.
- 3c: os dois modelos de comissão (motor da loja × comissão própria de função) são configuradores
  DIFERENTES de propósito (não se unificam) mas compartilham a FORMA do dado — o conserto vale
  para os dois: `mod_provisoes.resolver_comissao_venda` (motor da loja) e
  `mod_folha._resolver_pct_funcao` (função não-consultor) têm o MESMO defeito de validação
  (`mod_cadastro.funcao_aplicar` gravava `comissao.faixas` sem checar nada) — cobertos os dois.

Tarefa 3d, o trio pedido, para os dois lados."""
import mod_provisoes
import mod_folha


def _cfg_com_faixas(*faixas):
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = list(faixas)
    return c


# ── Motor da loja (mod_provisoes.resolver_comissao_venda) ───────────────────────────────────

def test_motor_loja_venda_acima_de_todas_as_faixas_usa_a_ultima():
    c = _cfg_com_faixas({"venda_ate": 100000.0, "pct": 3.0}, {"venda_ate": None, "pct": 6.0})
    assert mod_provisoes.resolver_comissao_venda(c, 400000.0, 0.0) == 6.0


def test_motor_loja_venda_exatamente_no_limite_sobe_de_faixa():
    """Semântica 'abaixo de', deliberada (16/09): atingir o valor promove, não fica na faixa."""
    c = _cfg_com_faixas({"venda_ate": 100000.0, "pct": 3.0}, {"venda_ate": None, "pct": 6.0})
    assert mod_provisoes.resolver_comissao_venda(c, 100000.0, 0.0) == 6.0   # == 100000 → sobe
    assert mod_provisoes.resolver_comissao_venda(c, 99999.99, 0.0) == 3.0   # < 100000 → fica


def test_motor_loja_validar_recusa_ultima_faixa_com_teto():
    c = _cfg_com_faixas({"venda_ate": 100000.0, "pct": 3.0}, {"venda_ate": 300000.0, "pct": 6.0})
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros and any("sem teto" in e.lower() for e in erros)


def test_motor_loja_validar_aceita_ultima_faixa_sem_teto():
    c = _cfg_com_faixas({"venda_ate": 100000.0, "pct": 3.0}, {"venda_ate": None, "pct": 6.0})
    assert mod_provisoes.validar_config_financeira(c) == []


# ── Comissão própria de função (mod_folha._resolver_pct_funcao) ─────────────────────────────

def test_funcao_propria_venda_acima_de_todas_as_faixas_usa_a_ultima():
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    assert mod_folha._resolver_pct_funcao(com, 400000.0) == 1.0


def test_funcao_propria_venda_exatamente_no_limite_sobe_de_faixa():
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    assert mod_folha._resolver_pct_funcao(com, 100000.0) == 1.0     # == 100000 → sobe
    assert mod_folha._resolver_pct_funcao(com, 99999.99) == 0.5     # < 100000 → fica


# ── validar_faixas_comissao — a função nova compartilhada pelos dois lados (3c) ──────────────

def test_validar_faixas_comissao_recusa_ultima_com_teto():
    erros = mod_provisoes.validar_faixas_comissao(
        [{"venda_ate": 100000.0, "pct": 0.5}, {"venda_ate": 300000.0, "pct": 1.0}])
    assert erros and any("sem teto" in e.lower() for e in erros)


def test_validar_faixas_comissao_aceita_ultima_sem_teto():
    assert mod_provisoes.validar_faixas_comissao(
        [{"venda_ate": 100000.0, "pct": 0.5}, {"venda_ate": None, "pct": 1.0}]) == []


def test_validar_faixas_comissao_recusa_faixa_sem_pct():
    erros = mod_provisoes.validar_faixas_comissao([{"venda_ate": None}])
    assert erros


def test_validar_faixas_comissao_lista_vazia_exigida_por_padrao():
    assert mod_provisoes.validar_faixas_comissao([]) != []


def test_validar_faixas_comissao_lista_vazia_pode_ser_permitida():
    assert mod_provisoes.validar_faixas_comissao([], exigir_faixas=False) == []


# ── Ponta a ponta HTTP: o lado da função ganhou o gate que não tinha (3c) ────────────────────

def _fid(app_db):
    db = app_db.get_session()
    lid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcao(loja_id=lid, nome="Medidor LP33", status="ativo"); db.add(f); db.commit()
    fid = f.id; db.close(); return fid


def test_api_funcoes_recusa_ultima_faixa_com_teto(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {"comissao": {
        "por_meta": True, "base": "liquido",
        "faixas": [{"venda_ate": 50000.0, "pct": 1.0}, {"venda_ate": 150000.0, "pct": 2.0}],
    }})
    assert st == 400 and out.get("ok") is False, out
    assert "sem teto" in (out.get("erro") or "").lower()


def test_api_funcoes_aceita_ultima_faixa_sem_teto(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {"comissao": {
        "por_meta": True, "base": "liquido",
        "faixas": [{"venda_ate": 50000.0, "pct": 1.0}, {"venda_ate": None, "pct": 2.0}],
    }})
    assert st == 200 and out.get("ok") is True, out


def test_api_funcoes_pct_fixo_nao_passa_pelo_gate_de_faixas(http_client_factory, seed, app_db):
    """Comissão simples (não por_meta) não tem faixa nenhuma — o gate novo não pode bloquear
    quem nem usa faixas."""
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {"comissao": {"por_meta": False, "base": "liquido", "pct": 5.0}})
    assert st == 200 and out.get("ok") is True, out
