"""FASE D2 — endpoints da reconciliação de provisões + contas a pagar."""


def test_reconciliacao_endpoint_ok(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")
    assert st == 200 and d["ok"] is True
    assert "provisoes" in d["reconciliacao"] and "totais" in d["reconciliacao"]


def test_efetivar_reconciliacao_pagar_fluxo(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # efetiva o custo real de uma provisão (competência → Fornecedores a Pagar)
    st, d = c.post("/api/financeiro/efetivar-provisao",
                   {"conta": "2.1.04.07", "valor": 900.0, "ref": "eftest1"})
    assert st == 200 and d["ok"] is True, d
    # reconciliação reflete o efetivado
    st, d = c.get("/api/financeiro/reconciliacao-provisoes")
    linhas = {l["codigo"]: l for l in d["reconciliacao"]["provisoes"]}
    assert linhas["2.1.04.07"]["efetivado"] == 900.0
    # contas a pagar mostra a obrigação
    st, d = c.get("/api/financeiro/contas-a-pagar")
    assert d["contas_a_pagar"]["total_em_aberto"] == 900.0
    # paga o fornecedor → zera
    st, d = c.post("/api/financeiro/pagar-fornecedor", {"valor": 900.0, "ref": "pgtest1"})
    assert st == 200 and d["ok"] is True, d
    st, d = c.get("/api/financeiro/contas-a-pagar")
    assert d["contas_a_pagar"]["total_em_aberto"] == 0.0


def test_resolver_saldo_endpoint(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # efetiva 900 numa provisão sem constituição → saldo negativo (falta) → resolver manda p/ despesa
    c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.08", "valor": 300.0, "ref": "ef8"})
    st, d = c.post("/api/financeiro/resolver-saldo-provisao", {"conta": "2.1.04.08"})
    assert st == 200 and d["ok"] is True, d
    # idempotente: 2ª resolução não faz nada (saldo já zero)
    st, d = c.post("/api/financeiro/resolver-saldo-provisao", {"conta": "2.1.04.08"})
    assert st == 200 and d["ok"] is True


def test_efetivar_gate_operador_403(http_client_factory, seed):
    c = http_client_factory(); c.login("cons_l1", "senha123")   # operador: sem acesso ao Financeiro
    st, d = c.post("/api/financeiro/efetivar-provisao", {"conta": "2.1.04.07", "valor": 900.0})
    assert st == 403 and d["ok"] is False
