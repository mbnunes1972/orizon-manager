"""POST /api/projetos/<nome>/data-entrega — persiste expectativa de entrega + previsão de medição +
venda programada e valida a FOLGA do trecho medição→entrega (bloqueio + override gerencial)."""
from database import Projeto


def test_data_entrega_folgada_cabe_e_persiste(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})
    assert st == 200, (st, d)
    assert d["ok"] and d.get("cabe") is True and d.get("folga_min") is not None
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is not None and p.previsao_medicao is not None and p.data_inicio is not None
    db.close()


def test_data_entrega_apertada_nao_cabe_nao_grava(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    # garante estado limpo — o `seed` é módulo-scoped e o teste anterior já pode ter persistido
    # data_entrega neste mesmo projeto; zera para que "não grava" seja uma checagem válida
    # independente da ordem de execução dos testes deste arquivo.
    db0 = app_db.get_session()
    db0.get(Projeto, proj).data_entrega = None
    db0.commit(); db0.close()
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2026-08-05", "previsao_medicao": "2026-08-01"})
    assert st == 200 and d["ok"]
    assert d["cabe"] is False and d["folga_min"] < 0 and d.get("requer_autorizacao") is True
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is None
    db.close()


def test_data_entrega_sem_folga_grava_com_autorizacao_gerencial(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2026-08-05", "previsao_medicao": "2026-08-01",
                    "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d["ok"] and d["cabe"] is False, (st, d)
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is not None
    log = (db.query(app_db.LogAcaoGerencial)
           .filter_by(projeto_nome=proj, acao="data_entrega_sem_folga").first())
    assert log is not None
    db.close()


def test_data_entrega_exige_previsao_medicao(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {"data_entrega": "2028-01-01"})
    assert st == 400 and "medição" in (d.get("erro", "").lower())


def test_data_entrega_invalida_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {})
    assert st == 400


def test_data_entrega_persiste_e_volta_no_contrato(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})
    assert st == 200 and d["ok"], (st, d)
    st2, d2 = c.get("/api/projetos/%s/contrato" % proj)
    assert st2 == 200 and d2["contrato"] is not None, (st2, d2)
    assert (d2["contrato"].get("data_entrega") or "").startswith("2028-01-01")
    assert (d2["contrato"].get("previsao_medicao") or "").startswith("2027-06-01")


def test_venda_programada_persiste_e_preserva(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01", "venda_programada": True})
    assert st == 200 and d["ok"] and d["cabe"], (st, d)
    db = app_db.get_session(); assert db.get(Projeto, proj).venda_programada == 1; db.close()
    # atualiza só as datas, sem reenviar venda_programada → PRESERVA
    st2, d2 = c.post("/api/projetos/%s/data-entrega" % proj,
                     {"data_entrega": "2028-02-01", "previsao_medicao": "2027-07-01"})
    assert st2 == 200 and d2["ok"], (st2, d2)
    db = app_db.get_session(); assert db.get(Projeto, proj).venda_programada == 1; db.close()


def test_data_entrega_sem_folga_credenciais_invalidas_403(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"],
                   {"data_entrega": "2026-08-05", "previsao_medicao": "2026-08-01",
                    "login": "dir_l1", "senha": "ERRADA"})
    assert st == 403 and "credenciais" in (d.get("erro", "").lower()), (st, d)
