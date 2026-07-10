from datetime import date
import mod_expedicao


# ── Lógica pura (mod_expedicao) ──────────────────────────────────────────────
def test_esta_atrasado(app_db):
    C = app_db.CicloLogistico
    atrasado = C(status_atual="Em Produção", prazo_producao=date(2020, 1, 1))
    assert mod_expedicao.esta_atrasado(atrasado, date(2026, 7, 9)) is True
    no_prazo = C(status_atual="Em Produção", prazo_producao=date(2999, 1, 1))
    assert mod_expedicao.esta_atrasado(no_prazo, date(2026, 7, 9)) is False
    entregue = C(status_atual="Entregue", prazo_entrega=date(2020, 1, 1))
    assert mod_expedicao.esta_atrasado(entregue, date(2026, 7, 9)) is False


# ── Kanban / ciclo de vida via HTTP ──────────────────────────────────────────
def test_kanban_colunas_por_status(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/expedicao/kanban")
    assert st == 200 and d["ok"] is True
    assert [col["status"] for col in d["colunas"]] == mod_expedicao.STATUS
    assert d["meta"]["status"][0] == "Pedido Enviado"


def test_criar_card_entra_em_pedido_enviado(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"],
                                            "numero_pedido": "PED-100",
                                            "prazos": {"prazo_producao": "2999-01-01"}})
    assert st == 201, d
    _, k = c.get("/api/expedicao/kanban")
    col = next(x for x in k["colunas"] if x["status"] == "Pedido Enviado")
    card = next(x for x in col["cards"] if x["id"] == d["id"])
    assert card["numero_pedido"] == "PED-100" and card["atrasado"] is False


def test_card_atrasado_quando_prazo_passou(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"],
                                            "prazos": {"prazo_producao": "2020-01-01"}})
    assert st == 201, d
    _, k = c.get("/api/expedicao/kanban")
    col = next(x for x in k["colunas"] if x["status"] == "Pedido Enviado")
    card = next(x for x in col["cards"] if x["id"] == d["id"])
    assert card["atrasado"] is True


def test_mover_captura_realizado_e_registra_historico(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]
    st, _ = c.post("/api/expedicao/cards/%d/mover" % cid,
                   {"novo_status": "Aguardando Recebimento",
                    "realizados": {"data_producao": "2026-07-09", "data_saida": "2026-07-09"}})
    assert st == 200
    _, det = c.get("/api/expedicao/cards/%d" % cid)
    card = det["card"]
    assert card["status_atual"] == "Aguardando Recebimento"
    assert card["realizados"]["data_producao"] == "2026-07-09"
    # histórico: criação (None -> Pedido Enviado) + a transição
    paras = [h["para"] for h in card["historico"]]
    assert paras == ["Pedido Enviado", "Aguardando Recebimento"]


def test_atualizar_detalhe_transporte(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, d = c.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]
    st, _ = c.post("/api/expedicao/cards/%d" % cid,
                   {"transportadora": "Transp X", "cte": "CTE-9", "rastreio": "BR123"})
    assert st == 200
    _, det = c.get("/api/expedicao/cards/%d" % cid)
    assert det["card"]["transporte"] == {"transportadora": "Transp X", "cte": "CTE-9", "rastreio": "BR123"}


def test_card_de_outra_loja_nao_vaza(http_client_factory, seed, app_db):
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    _, d = c1.post("/api/expedicao/cards", {"projeto_nome": seed["projeto_l1"]})
    cid = d["id"]
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st, _ = c2.get("/api/expedicao/cards/%d" % cid)
    assert st == 404
