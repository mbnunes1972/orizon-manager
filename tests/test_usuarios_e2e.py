# tests/test_usuarios_e2e.py
# Task 4 — endpoint GET /api/admin/usuarios/perfis-permitidos
# (base para tasks 5-7 também)


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_perfis_permitidos_loja_para_diretor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200 and body["ok"]
    slugs = {p["slug"] for p in body["perfis"]}
    assert "consultor" in slugs and "super_admin" not in slugs and "admin_rede" not in slugs


def test_perfis_permitidos_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st == 200 and [p["slug"] for p in body["perfis"]] == ["super_admin"]
    c2 = _login(http_client_factory, "dir_l1")
    st2, body2 = c2.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st2 == 200 and body2["perfis"] == []


# Task 5 — filtros de escopo + campos de contato na lista de usuários

def test_lista_escopo_loja_so_da_loja(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200
    logins = {u["login"] for u in body["usuarios"]}
    assert "dir_l1" in logins and "dir_l2" not in logins and "super" not in logins


def test_lista_escopo_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios?escopo=plataforma")
    assert st == 200
    niveis = {u["nivel"] for u in body["usuarios"]}
    assert niveis == {"super_admin"}


def test_lista_inclui_campos_contato(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    u = body["usuarios"][0]
    assert "email" in u and "cpf" in u and "whatsapp" in u
