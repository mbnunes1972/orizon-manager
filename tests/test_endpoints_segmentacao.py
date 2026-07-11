"""FASE B1 — endpoints da segmentação Mercadoria × Serviço.

Default da loja: PATCH /api/admin/lojas/<id> (gate editar_dados_loja, valida soma=100).
Override por projeto: POST /api/projetos/<nome>/parametros (gate aprovar_financeiro — Diretor)."""


def test_dados_loja_salva_segmentacao(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    lid = seed["loja1_id"]
    st, d = c.patch(f"/api/admin/lojas/{lid}", {"pct_mercadoria": 70.0, "pct_servico": 30.0})
    assert st == 200 and d["ok"] is True
    assert d["loja"]["pct_mercadoria"] == 70.0 and d["loja"]["pct_servico"] == 30.0


def test_dados_loja_rejeita_soma_diferente_de_100(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    lid = seed["loja1_id"]
    st, d = c.patch(f"/api/admin/lojas/{lid}", {"pct_mercadoria": 70.0, "pct_servico": 25.0})
    assert st == 400 and d["ok"] is False


def test_dados_loja_gate_editar(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: sem editar_dados_loja
    lid = seed["loja1_id"]
    st, d = c.patch(f"/api/admin/lojas/{lid}", {"pct_mercadoria": 70.0, "pct_servico": 30.0})
    assert st == 403 and d["ok"] is False


def test_override_projeto_persistido(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")   # master: tem aprovar_financeiro
    proj = seed["projeto_l1"]
    st, d = c.post(f"/api/projetos/{proj}/parametros", {"pct_mercadoria": 80.0, "pct_servico": 20.0})
    assert st == 200 and d["ok"] is True
    assert d["parametros"]["pct_mercadoria"] == 80.0 and d["parametros"]["pct_servico"] == 20.0


def test_override_gate_aprovar_financeiro(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: sem aprovar_financeiro
    proj = seed["projeto_l1"]
    st, d = c.post(f"/api/projetos/{proj}/parametros", {"pct_mercadoria": 80.0, "pct_servico": 20.0})
    assert st == 403 and d["ok"] is False


def test_override_rejeita_soma_diferente(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post(f"/api/projetos/{proj}/parametros", {"pct_mercadoria": 80.0, "pct_servico": 30.0})
    assert st == 400 and d["ok"] is False


def test_override_sobrevive_a_salvamento_de_outros_parametros(http_client_factory, seed):
    """Salvar parâmetros normais (sem pct_*) NÃO pode apagar o override de segmentação já gravado."""
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post(f"/api/projetos/{proj}/parametros", {"pct_mercadoria": 80.0, "pct_servico": 20.0})
    assert st == 200 and d["ok"] is True
    # salvamento normal de OUTRO parâmetro, sem enviar pct_* (fluxo do auto-save geral)
    st, d = c.post(f"/api/projetos/{proj}/parametros", {"carga_trib": 9.0})
    assert st == 200 and d["ok"] is True
    assert d["parametros"]["pct_mercadoria"] == 80.0 and d["parametros"]["pct_servico"] == 20.0
    assert d["parametros"]["carga_trib"] == 9.0
