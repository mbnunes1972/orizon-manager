import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


def test_canary_banco_isolado(app_db):
    assert "omie.db" not in app_db.DB_PATH
    db = app_db.get_session()
    loja = app_db.Loja(nome="Canary")
    db.add(loja); db.commit()
    lid = loja.id
    db.close()
    db2 = app_db.get_session()
    lido = db2.query(app_db.Loja).filter_by(id=lid).first()
    db2.close()
    assert lido is not None and lido.nome == "Canary"


def test_canary_login_via_http(http_client_factory):
    c = http_client_factory()
    status, body = c.login("dir_l1", "senha123")
    assert status == 200 and body.get("ok") is True
    assert c.cookie and c.cookie.startswith("omie_session=")
    status, _ = c.get("/api/clientes")
    assert status == 200


# ── TASK 4: Leitura cross-loja → 404 ─────────────────────────────────────────

def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who} (sem cookie de sessão)"
    return c


def test_cliente_de_outra_loja_da_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/api/clientes/{seed['cliente_l1_id']}")
    assert status == 404


def test_projeto_de_outra_loja_da_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/projetos/{seed['projeto_l1']}")
    assert status == 404


def test_cliente_da_propria_loja_abre(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/api/clientes/{seed['cliente_l2_id']}")
    assert status == 200


def test_projeto_da_propria_loja_abre(http_client_factory, seed, projetos_dir):
    # GET /projetos/<nome_safe> carrega projeto.json do disco via _carregar_projeto;
    # a fixture projetos_dir já escreveu o arquivo no diretório temporário isolado
    # (sem poluir o PROJETOS real).
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/projetos/{seed['projeto_l2']}")
    assert status == 200


# ── TASK 5: Escopo das listagens ──────────────────────────────────────────────

def test_lista_clientes_so_da_propria_loja(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get("/api/clientes")
    assert status == 200
    clientes = body["clientes"] if isinstance(body, dict) and "clientes" in body else body
    ids = {item.get("id") for item in clientes}
    assert seed["cliente_l2_id"] in ids
    assert seed["cliente_l1_id"] not in ids


def test_lista_projetos_so_da_propria_loja(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get("/projetos")
    assert status == 200
    projetos = body["projetos"] if isinstance(body, dict) and "projetos" in body else body
    nomes = {p.get("nome_safe") for p in projetos}
    # ambos existem em disco; o filtro por loja deve manter só o da loja 2
    assert seed["projeto_l2"] in nomes
    assert seed["projeto_l1"] not in nomes


# ── TASK 6: Perfis administrativos → 403 no operacional ──────────────────────

@pytest.mark.parametrize("who", ["super", "adm_rede"])
def test_admin_sem_acesso_operacional_lista_projetos(http_client_factory, who):
    c = _login(http_client_factory, who)
    status, _ = c.get("/projetos")
    assert status == 403


@pytest.mark.parametrize("who", ["super", "adm_rede"])
def test_admin_sem_acesso_operacional_lista_clientes(http_client_factory, who):
    c = _login(http_client_factory, who)
    status, _ = c.get("/api/clientes")
    assert status == 403


# ── TASK 7: Endpoints sem-auth corrigidos → 401 para anônimo ─────────────────

def test_status_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.patch(f"/api/projetos/{seed['projeto_l1']}/status", {"status": "morno"})
    assert status == 401


def test_descontos_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.put("/api/orcamentos/999/descontos", {"descontos": []})
    assert status == 401


def test_valor_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.patch("/orcamentos/999/valor", {"valor": 1000})
    assert status == 401


def test_parceiros_create_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.post("/api/parceiros", {"nome": "X"})
    assert status == 401


def test_parceiros_editar_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.post("/api/parceiros/999/editar", {"nome": "X"})
    assert status == 401


def test_briefing_projeto_get_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.get(f"/api/projetos/{seed['projeto_l1']}/briefing")
    assert status == 401


def test_briefing_cliente_post_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.post(f"/api/clientes/{seed['cliente_l1_id']}/briefing", {})
    assert status == 401


def test_briefing_projeto_post_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.post(f"/api/projetos/{seed['projeto_l1']}/briefing", {})
    assert status == 401
