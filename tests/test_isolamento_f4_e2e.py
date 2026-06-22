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


# ── TASK 8: Escrita cross-loja → 404/403 e estado intacto ────────────────────

def test_status_cross_loja_nao_altera(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.patch(f"/api/projetos/{seed['projeto_l1']}/status", {"status": "perdido"})
    assert status in (403, 404)
    db = app_db.get_session()
    proj = db.get(app_db.Projeto, seed["projeto_l1"])
    estado = proj.status
    db.close()
    assert estado == "quente"


def test_briefing_cliente_cross_loja_bloqueado(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.post(f"/api/clientes/{seed['cliente_l1_id']}/briefing", {})
    assert status in (403, 404)


# ── TASK 9: Criação carimba loja_id do autor ─────────────────────────────────
# Response shape: {"ok": True, "cliente": {...}} — id at body["cliente"]["id"]
# Required fields: nome, email, telefone (validar_cadastro_minimo)

def test_criacao_de_cliente_carimba_loja_do_autor(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    # Required fields: nome, email, telefone (validar_cadastro_minimo); CPF optional
    novo = {"nome": "Cliente Novo L2", "cpf": "333.333.333-33",
            "email": "novol2@example.com", "telefone": "(12) 90000-0000"}
    status, body = c.post("/api/clientes", novo)
    assert status in (200, 201)
    db = app_db.get_session()
    cli = db.query(app_db.Cliente).filter_by(cpf="333.333.333-33").first()
    loja = cli.loja_id if cli else None
    db.close()
    assert cli is not None
    assert loja == seed["loja2_id"]


# ── TASK 10: Sem regressão (loja legítima) + colisão de CPF isolada ──────────
# CPF-collision contract: same-loja → 409 + {"cliente":...}; cross-loja → 409 no data

def test_diretor_l1_opera_normalmente(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l1")
    s1, _ = c.get(f"/api/clientes/{seed['cliente_l1_id']}")
    s2, _ = c.get(f"/projetos/{seed['projeto_l1']}")
    assert s1 == 200 and s2 == 200


def test_colisao_cpf_nao_vaza_cliente_de_outra_loja(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    # CPF "111.111.111-11" belongs to cliente_l1 (Loja 1).
    # Handler contract (F4 fix): cross-loja CPF collision → 409 with
    # {"ok": False, "erro": "CPF já cadastrado em outra unidade."} — no cliente data.
    status, body = c.post("/api/clientes",
                          {"nome": "Homonimo", "cpf": "111.111.111-11",
                           "email": "homonimo@example.com", "telefone": "(11) 90000-0000"})
    # Must be a rejection (409); NEVER a success that leaks Loja-1 data
    assert status == 409, (
        f"SECURITY FINDING: CPF collision with another loja's cliente returned {status} "
        f"instead of 409 — response: {body}"
    )
    # Body must NOT contain any cliente object (would expose Loja-1 data)
    if isinstance(body, dict):
        retornado_id = body.get("id") or (body.get("cliente") or {}).get("id")
        assert retornado_id != seed["cliente_l1_id"], (
            "SECURITY FINDING: cross-loja CPF collision returned the other loja's cliente id"
        )
        assert "cliente" not in body, (
            "SECURITY FINDING: cross-loja CPF collision body contains 'cliente' key — data leak"
        )
    # Invariant: the Loja-1 cliente still belongs to Loja 1
    db = app_db.get_session()
    original = db.get(app_db.Cliente, seed["cliente_l1_id"])
    loja_orig = original.loja_id
    db.close()
    assert loja_orig == seed["loja1_id"]


# ── Regressão: guard contra shadowing de `threading` em do_POST ───────────────
# Um `import threading` (ou `threading = ...`) dentro de do_POST torna `threading`
# uma variável LOCAL em toda a função, quebrando os usos anteriores com
# UnboundLocalError (ex.: o sync Omie em background no POST /api/clientes).
# Exposto pela suíte E2E e corrigido removendo o import redundante (main.py).

def test_do_post_nao_faz_shadowing_de_threading():
    import main
    assert "threading" not in main.Handler.do_POST.__code__.co_varnames, (
        "do_POST tem `threading` como variável local (import/atribuição interna) — "
        "isso causa UnboundLocalError nos usos de threading antes dessa linha. "
        "Use o threading importado no nível do módulo."
    )
