def test_reconciliar_e_fechar_periodo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 1000, "projeto_id": "PA"})
    c.post("/api/financeiro/eventos", {"tipo": "faturamento", "valor": 1000, "projeto_id": "PB"})
    # despesa fixa 5.4 (Aluguel) 400 sem projeto
    _, contas = c.get("/api/financeiro/contas")

    def find(nodes, cod):
        for n in nodes:
            if n["codigo"] == cod:
                return n
            r = find(n["filhos"], cod)
            if r:
                return r
    aluguel = find(contas["contas"], "5.4.01")["id"]
    caixa = find(contas["contas"], "1.1.01")["id"]
    c.post("/api/financeiro/lancamentos", {"conta_debito_id": aluguel, "conta_credito_id": caixa, "valor": 400})

    st, d = c.post("/api/financeiro/reconciliar", {"metodologia": "proporcional_receita"})
    assert st == 200 and d["ok"] is True
    rec = d["reconciliacao"]
    aloc = {a["projeto_id"]: a for a in rec["alocacao_por_projeto"]}
    assert aloc["PA"]["valor_rateado"] == 200.0 and aloc["PB"]["valor_rateado"] == 200.0  # 50/50
    assert rec["divergencia_residual"] == 0.0

    st2, d2 = c.post("/api/financeiro/periodos", {"metodologia": "proporcional_receita"})
    assert st2 == 201 and d2["periodo"]["id"]
    st3, d3 = c.get("/api/financeiro/periodos")
    assert st3 == 200 and len(d3["periodos"]) == 1


def test_reconciliar_metodologia_invalida_400(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/financeiro/reconciliar", {"metodologia": "xyz"})
    assert st == 400
