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
    assert "operador" in slugs and "super_admin" not in slugs and "admin_rede" not in slugs


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


# Task 6 — POST /api/admin/usuarios grava contato e admin_rede cria par

def test_diretor_cria_usuario_loja_com_contato(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Nova Pessoa", "login": "nova1", "senha": "s1", "nivel": "operador",
        "telefone": "1", "whatsapp": "2", "email": "n@p.com", "cpf": "390.533.447-05",
        "loja_id": seed["loja1_id"]})
    assert st == 200 and body["ok"]
    st2, lst = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    novo = next(u for u in lst["usuarios"] if u["login"] == "nova1")
    assert novo["email"] == "n@p.com" and novo["whatsapp"] == "2"


def test_admin_rede_cria_par(http_client_factory, seed):
    c = _login(http_client_factory, "adm_rede")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Outro Adm", "login": "adm2", "senha": "s1", "nivel": "admin_rede"})
    assert st == 200 and body["ok"]


def test_diretor_nao_cria_super(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "X", "login": "x9", "senha": "s", "nivel": "super_admin",
        "loja_id": seed["loja1_id"]})
    assert body["ok"] is False


# Task 7 — PATCH: contato, escalonamento admin_rede e anti-lockout

def test_admin_rede_edita_par(http_client_factory, seed, app_db):
    # cria um par admin_rede para editar
    c = _login(http_client_factory, "adm_rede")
    c.post("/api/admin/usuarios", {"nome": "Par", "login": "par1", "senha": "s", "nivel": "admin_rede"})
    db = app_db.get_session()
    pid = db.query(app_db.Usuario).filter_by(login="par1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{pid}", {"telefone": "55", "email": "p@p.com"})
    assert st == 200 and body["ok"]


def test_nao_inativa_a_si_mesmo(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"ativo": False})
    assert body["ok"] is False


def test_nao_rebaixa_proprio_perfil(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"nivel": "consultor"})
    assert body["ok"] is False


def test_diretor_nao_promove_para_admin_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="dir_l2").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{alvo}", {"nivel": "admin_rede"})
    assert body["ok"] is False


def test_admin_rede_nao_promove_para_super(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "adm_rede")
    db = app_db.get_session()
    id_dir_l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{id_dir_l1}", {"nivel": "super_admin"})
    assert body["ok"] is False


def test_edita_proprio_contato_permitido(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"telefone": "1199", "email": "eu@loja.com"})
    assert body["ok"] is True


def test_perfis_permitidos_super_admin_honra_loja_id(http_client_factory, seed, app_db):
    """Bug 2026-07-22: super_admin (sem loja própria) criando usuário na gestão geral — o
    endpoint deve honrar o loja_id do request e devolver os perfis DAQUELA loja, inclusive
    os customizados (antes ignorava e caía no fallback genérico master/gerencial/operador)."""
    from auth import perfil_store
    db = app_db.get_session()
    perfil_store.seed_perfis_loja(db, seed["loja2_id"])
    p, err = perfil_store.criar_perfil(db, seed["loja2_id"], "Diretor", "master", ["comercial"])
    assert p is not None, err
    db.close()
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja2_id']}")
    assert st == 200 and body["ok"], body
    rotulos = {x["rotulo"] for x in body["perfis"]}
    assert "Diretor" in rotulos, rotulos            # perfil customizado da loja aparece
    slugs = {x["slug"] for x in body["perfis"]}
    assert {"master", "gerencial", "operador"} <= slugs


def test_perfis_permitidos_nao_vaza_loja_fora_do_escopo(http_client_factory, seed, app_db):
    """dir_l1 pedindo os perfis da loja 2 NÃO recebe os customizados de lá — o loja_id só é
    honrado dentro do escopo do ator (super/admin_rede da rede/a própria loja)."""
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja2_id']}")
    assert st == 200 and body["ok"], body
    rotulos = {x["rotulo"] for x in body["perfis"]}
    assert "Diretor" not in rotulos                  # criado no teste anterior, loja 2


def test_super_admin_cria_outro_super_admin(http_client_factory, seed):
    """Pedido 2026-07-22: o Super Admin pode criar outros usuários Super Admin (o botão
    '+ Novo gestor' do Painel Orizon usa escopo=plataforma)."""
    c = _login(http_client_factory, "super")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Segundo Gestor", "login": "super2", "senha": "s1", "nivel": "super_admin"})
    assert st == 200 and body["ok"], body
    st, lst = c.get("/api/admin/usuarios?escopo=plataforma")
    assert any(u["login"] == "super2" for u in lst["usuarios"])
