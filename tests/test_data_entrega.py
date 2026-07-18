"""Passo 1 (cronograma): POST /api/projetos/<nome>/data-entrega — define a data de entrega esperada e
valida contra o Cronograma Padrão (folga). Base do regressivo + do gate 'cronograma próprio'."""
from database import Projeto


def test_data_entrega_folgada_cabe_e_persiste(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj, {"data_entrega": "2028-01-01"})   # bem à frente
    assert st == 200, (st, d)
    assert d["ok"] and d.get("cabe") is True and d.get("folga_min") is not None
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is not None and p.data_inicio is not None   # âncoras persistidas
    db.close()


def test_data_entrega_apertada_nao_cabe(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {"data_entrega": "2026-07-20"})
    assert st == 200 and d["ok"]
    assert d["cabe"] is False and d["folga_min"] < 0   # não cabe no Cronograma Padrão


def test_data_entrega_invalida_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {})
    assert st == 400


def test_data_entrega_persiste_e_volta_no_contrato(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj, {"data_entrega": "2028-01-01"})
    assert st == 200 and d["ok"], (st, d)
    # o GET do contrato deve devolver a data gravada (hoje não devolve → o card relê vazio)
    st2, d2 = c.get("/api/projetos/%s/contrato" % proj)
    assert st2 == 200 and d2["contrato"] is not None, (st2, d2)
    assert (d2["contrato"].get("data_entrega") or "").startswith("2028-01-01"), d2["contrato"]
