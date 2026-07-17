import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest


def test_canary_banco_isolado(app_db):
    # SQLite: garante que não é o arquivo de produção. Postgres (DB_PATH é None por desenho, ver
    # conftest.py): a mesma garantia é o nome do banco de teste nunca ser o de produção ("orizon").
    if app_db.DB_PATH is not None:
        assert "orizon.db" not in app_db.DB_PATH
    else:
        assert app_db.ENGINE.url.database != "orizon"
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
    novo = {"nome": "Cliente Novo L2", "cpf": "529.982.247-25",
            "email": "novol2@example.com", "telefone": "(12) 90000-0000"}
    status, body = c.post("/api/clientes", novo)
    assert status in (200, 201)
    db = app_db.get_session()
    cli = db.query(app_db.Cliente).filter_by(cpf="529.982.247-25").first()
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
    # CPF "111.444.777-35" belongs to cliente_l1 (Loja 1). CPF válido (passa na
    # validação de DV) para exercitar a checagem de unicidade cross-loja, não a validação.
    # Handler contract (F4 fix): cross-loja CPF collision → 409 with
    # {"ok": False, "erro": "CPF já cadastrado em outra unidade."} — no cliente data.
    status, body = c.post("/api/clientes",
                          {"nome": "Homonimo", "cpf": "111.444.777-35",
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


# ── TASK 11: Orçamento cross-loja read → 404 ─────────────────────────────────
# Não há GET de um orçamento isolado (a rota ~3368 é PUT de rename). O isolamento
# de leitura é exercitado pela lista (TASK 13) via _projeto_da_loja; aqui cobrimos
# a escrita cross-loja: PUT /projetos/<nome>/orcamentos/<id> usa _obj_da_loja → 404.

def test_orcamento_rename_cross_loja_da_404(http_client_factory, seed):
    """PUT renomear orçamento de Proj_L1 como dir_l2 → 404 (_obj_da_loja filtra por loja)."""
    c = _login(http_client_factory, "dir_l2")
    oid = seed["orcamento_l1_id"]
    status, body = c.put(f"/projetos/{seed['projeto_l1']}/orcamentos/{oid}", {"nome": "Hack"})
    assert status == 404, (
        f"SECURITY FINDING: dir_l2 conseguiu renomear orçamento de loja 1 — "
        f"status {status}, resposta: {body}"
    )


# ── TASK 12: Contrato cross-loja read → 404 ──────────────────────────────────

def test_contrato_de_outra_loja_da_404(http_client_factory, seed):
    """GET /api/projetos/Proj_L1/contrato como dir_l2 → 404."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get(f"/api/projetos/{seed['projeto_l1']}/contrato")
    assert status == 404, (
        f"SECURITY FINDING: dir_l2 leu contrato de loja 1 e recebeu {status} "
        f"em vez de 404 — resposta: {body}"
    )


# ── TASK 13: Escopo da listagem de orçamentos ─────────────────────────────────

def test_orcamentos_lista_scope_negativo_404(http_client_factory, seed):
    """dir_l2 não pode listar orçamentos de um projeto de outra loja (→ 404)."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get(f"/projetos/{seed['projeto_l1']}/orcamentos")
    assert status == 404, (
        f"SECURITY FINDING: dir_l2 listou orçamentos do projeto de loja 1 — "
        f"status {status}, resposta: {body}"
    )


def test_orcamentos_lista_scope_positivo_200(http_client_factory, seed):
    """dir_l2 lista orçamentos de Proj_L2 → 200 e o orçamento seedado está presente."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get(f"/projetos/{seed['projeto_l2']}/orcamentos")
    assert status == 200, (
        f"dir_l2 não conseguiu listar orçamentos do próprio projeto — "
        f"status {status}, resposta: {body}"
    )
    orcamentos = body.get("orcamentos", []) if isinstance(body, dict) else []
    ids = {o.get("id") for o in orcamentos}
    assert seed["orcamento_l2_id"] in ids, (
        f"Orçamento seedado (id={seed['orcamento_l2_id']}) não apareceu na lista de "
        f"Proj_L2 para dir_l2 — ids retornados: {ids}"
    )


# ── TASK 14: Ambientes exige autenticação (401) ───────────────────────────────

def test_ambientes_atualizar_sem_auth_401(http_client_factory, seed):
    """POST /projetos/<nome>/ambientes/atualizar sem login → 401."""
    c = http_client_factory()   # sem login
    status, body = c.post(f"/projetos/{seed['projeto_l1']}/ambientes/atualizar", {})
    assert status == 401, (
        f"SECURITY FINDING: endpoint de ambientes aceitou requisição anônima — "
        f"status {status}, resposta: {body}"
    )


# ── TASK 15: Projeto create carimba loja_id do autor ─────────────────────────

def test_projeto_create_carimba_loja_id(http_client_factory, seed, app_db, projetos_dir):
    """POST /projetos/novo como dir_l2 → projeto criado tem loja_id = loja2."""
    c = _login(http_client_factory, "dir_l2")
    body_req = {"nome_projeto": "Proj_Stamp_L2", "cliente_id": seed["cliente_l2_id"]}
    status, body = c.post("/projetos/novo", body_req)
    assert status == 200, (
        f"Criação de projeto falhou — status {status}, resposta: {body}"
    )
    assert isinstance(body, dict) and body.get("ok") is True, (
        f"Resposta inesperada ao criar projeto: {body}"
    )
    nome_safe = body.get("projeto", {}).get("nome_safe")
    assert nome_safe, f"Resposta não contém nome_safe: {body}"

    db = app_db.get_session()
    proj = db.get(app_db.Projeto, nome_safe)
    loja = proj.loja_id if proj else None
    db.close()
    assert proj is not None, f"Projeto '{nome_safe}' não encontrado no banco"
    assert loja == seed["loja2_id"], (
        f"SECURITY FINDING: projeto criado por dir_l2 tem loja_id={loja!r} "
        f"em vez de {seed['loja2_id']!r}"
    )


# ── TASK 16: Orçamento create carimba loja_id do autor ───────────────────────
# Pré-condição: briefing completo para Proj_L2 já seedado em conftest.py.
# O endpoint POST /projetos/<nome>/orcamentos exige {"nome": "..."} e rejeita
# body sem "nome" com 400. Também exige _briefing_projeto_completo (→ 400 se ausente).

def test_orcamento_create_carimba_loja_id(http_client_factory, seed, app_db):
    """POST /projetos/Proj_L2/orcamentos como dir_l2 → orçamento criado tem loja_id = loja2."""
    c = _login(http_client_factory, "dir_l2")
    status, body = c.post(f"/projetos/{seed['projeto_l2']}/orcamentos",
                          {"nome": "Orc Stamp L2"})
    assert status == 200, (
        f"Criação de orçamento falhou — status {status}, resposta: {body}"
    )
    assert isinstance(body, dict) and body.get("ok") is True, (
        f"Resposta inesperada ao criar orçamento: {body}"
    )
    orc_id = body.get("orcamento", {}).get("id")
    assert orc_id, f"Resposta não contém orcamento.id: {body}"

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, orc_id)
    loja = orc.loja_id if orc else None
    db.close()
    assert orc is not None, f"Orçamento id={orc_id} não encontrado no banco"
    assert loja == seed["loja2_id"], (
        f"SECURITY FINDING: orçamento criado por dir_l2 tem loja_id={loja!r} "
        f"em vez de {seed['loja2_id']!r}"
    )
