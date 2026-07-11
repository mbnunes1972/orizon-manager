# tests/test_perfis_api_e2e.py
# Task 7 — CRUD /api/admin/perfis (Master) + perfis-matriz por loja


def _login(factory, who):
    c = factory(); c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_master_lista_cria_edita(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get("/api/admin/perfis")
    assert st == 200 and body["ok"]
    slugs = {p["slug"] for p in body["perfis"]}
    assert {"master", "gerencial", "operador"} <= slugs
    assert "caps_selecionaveis" in body
    op = next(p for p in body["perfis"] if p["slug"] == "operador")
    assert op["capacidades"]["aprovar_financeiro"] is False
    # cria custom com módulos E override de capacidade fina
    st, body = c.post("/api/admin/perfis", {"nome": "Vendas Jr", "base": "operador",
                       "modulos": ["cadastro", "comercial", "fiscal"],
                       "capacidades": {"aprovar_financeiro": True}})
    assert st == 201 and body["ok"], body
    novo = body["perfil"]["slug"]
    # edita
    st, body = c.patch(f"/api/admin/perfis/{novo}", {"modulos": ["cadastro", "comercial"],
                        "capacidades": {"aprovar_financeiro": True, "autorizar": True}})
    assert st == 200 and body["ok"]


def test_sistema_nao_edita(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.patch("/api/admin/perfis/master", {"modulos": []})
    assert st == 403 or not body.get("ok")


def test_operador_nao_gerencia(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/admin/perfis", {"nome": "X", "base": "operador", "modulos": []})
    assert st == 403
