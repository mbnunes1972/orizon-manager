import mod_assistencias as ma
import mod_contabil as mc


# ── Mapeamento motivo -> tipo de custo (tabela do doc) ───────────────────────
def test_motivo_deriva_tipo_custo():
    assert ma.tipo_custo_de("alteracao_projeto") == "paga"
    assert ma.tipo_custo_de("complemento") == "paga"
    assert ma.tipo_custo_de("erro_projeto") == "loja"
    assert ma.tipo_custo_de("erro_montagem") == "loja"
    assert ma.tipo_custo_de("defeito_fabricacao") == "fabrica"
    assert ma.tipo_custo_de("empenamento") == "fabrica"
    assert ma.tipo_custo_de("xpto") is None


# ── Motor de lançamento: cada tipo de custo posta no razão certo (v7 §6) ─────
def _saldo(db, oid, cod):
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first()
    return mc.saldo_conta(db, "loja", oid, c.id) if c else 0.0


def test_realizar_loja_baixa_provisao_assistencia(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 70)
    caso = ma.criar_caso(db, 70, None, "montagem", "erro_montagem", "x", 300.0, 1)
    ok, err = ma.realizar_caso(db, "loja", 70, caso)
    assert ok, err
    # Débito 2.1.04.05 (baixa provisão assist. técnica) -> saldo do passivo cai 300
    assert _saldo(db, 70, "2.1.04.05") == -300.0
    assert caso.status == "realizado"
    db.close()


def test_realizar_fabrica_baixa_provisao_garantia(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 71)
    caso = ma.criar_caso(db, 71, None, "pos_conclusao", "defeito_fabricacao", "x", 500.0, 1)
    assert caso.tipo_custo == "fabrica"
    ma.realizar_caso(db, "loja", 71, caso)
    assert _saldo(db, 71, "2.1.04.03") == -500.0        # provisão de garantia baixada
    rel = ma.a_cobrar_fabrica(db, 71)
    assert rel["total"] == 500.0 and rel["qtd"] == 1     # entra no "a cobrar da fábrica"
    db.close()


def test_realizar_paga_gera_venda_sem_provisao(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 72)
    caso = ma.criar_caso(db, 72, None, "montagem", "complemento", "x", 250.0, 1)
    assert caso.tipo_custo == "paga"
    ma.realizar_caso(db, "loja", 72, caso)
    assert _saldo(db, 72, "1.1.02") == 250.0             # Contas a Receber
    assert _saldo(db, 72, "4.1.02") == 250.0             # Receita com Vendas de Assistência
    assert ma.a_cobrar_fabrica(db, 72)["total"] == 0.0   # Paga não entra no repasse da fábrica
    db.close()


def test_realizar_idempotente(app_db):
    db = app_db.get_session(); mc.seed_plano(db, "loja", 73)
    caso = ma.criar_caso(db, 73, None, "montagem", "erro_projeto", "x", 100.0, 1)
    ma.realizar_caso(db, "loja", 73, caso)
    ma.realizar_caso(db, "loja", 73, caso)               # 2ª vez não duplica
    assert _saldo(db, 73, "2.1.04.05") == -100.0
    db.close()


# ── HTTP: criar/listar/realizar via endpoints ────────────────────────────────
def test_endpoints_criar_listar_realizar(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "defeito_fabricacao",
                                               "descricao": "porta empenou", "valor": 400})
    assert st == 201 and d["tipo_custo"] == "fabrica", d
    cid = d["id"]
    st, lst = c.get("/api/assistencias/casos")
    assert st == 200
    assert any(x["id"] == cid and x["tipo_custo_label"] == "Fábrica" for x in lst["casos"])
    assert lst["a_cobrar_fabrica"]["total"] == 400
    assert {m["id"] for m in lst["meta"]["motivos"]} >= {"erro_montagem", "defeito_fabricacao"}
    st, _ = c.post("/api/assistencias/casos/%d/realizar" % cid, {})
    assert st == 200
    _, lst2 = c.get("/api/assistencias/casos?tipo=fabrica")
    assert next(x for x in lst2["casos"] if x["id"] == cid)["status"] == "realizado"


def test_caso_de_outra_loja_nao_realiza(http_client_factory, seed, app_db):
    c1 = http_client_factory(); c1.login("dir_l1", "senha123")
    _, d = c1.post("/api/assistencias/casos", {"sub_tipo": "montagem", "motivo": "erro_projeto", "valor": 50})
    c2 = http_client_factory(); c2.login("dir_l2", "senha123")
    st, _ = c2.post("/api/assistencias/casos/%d/realizar" % d["id"], {})
    assert st == 404
