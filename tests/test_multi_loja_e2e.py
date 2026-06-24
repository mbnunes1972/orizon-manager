import json as _json, urllib.request, urllib.error
import pytest


def _get_h(client, path, headers=None):
    """GET reaproveitando o cookie do HttpClient, com headers extras (ex.: X-Loja-Ativa)."""
    req = urllib.request.Request(client.base + path, method="GET")
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        out = _json.loads(raw) if raw else None
    except Exception:
        out = raw
    return status, out


@pytest.fixture(scope="module")
def dir_l1_multiloja(app_db, seed):
    """Torna dir_l1 (default loja1) membro também da loja2."""
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
        db.add_all([
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja1_id"]),
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja2_id"]),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def _put_h(client, path, body, headers=None):
    """PUT com cookie do HttpClient, corpo JSON e headers extras (ex.: X-Loja-Ativa)."""
    data = _json.dumps(body).encode()
    req = urllib.request.Request(client.base + path, data=data, method="PUT")
    req.add_header("Content-Type", "application/json")
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        out = _json.loads(raw) if raw else None
    except Exception:
        out = raw
    return status, out


def _clientes_nomes(body):
    return {c["nome"] for c in (body.get("clientes") or [])}


def test_sem_header_usa_loja_default(http_client_factory, dir_l1_multiloja):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = _get_h(c, "/api/clientes?q=")
    assert st == 200
    assert "Cliente L1" in _clientes_nomes(body)
    assert "Cliente L2" not in _clientes_nomes(body)


def test_header_loja2_muda_contexto(http_client_factory, dir_l1_multiloja, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = _get_h(c, "/api/clientes?q=", {"X-Loja-Ativa": str(seed["loja2_id"])})
    assert st == 200
    assert "Cliente L2" in _clientes_nomes(body)
    assert "Cliente L1" not in _clientes_nomes(body)


def test_header_loja_nao_membro_da_403(http_client_factory, seed):
    # dir_l2 tem loja_id=loja2 e sem membership; default (loja2) é sempre acessível.
    # Header loja1 (não-membro) não está em {loja2} -> resolver None -> 403.
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = _get_h(c, "/api/clientes?q=", {"X-Loja-Ativa": str(seed["loja1_id"])})
    assert st == 403


def test_put_orcamento_loja_ativa_nao_usa_contexto_obsoleto(
        http_client_factory, dir_l1_multiloja, seed):
    """Reproduz o bug de staleness em do_PUT.

    Sequência:
    1. GET com X-Loja-Ativa=loja2  → seta global do servidor para loja2.
    2. PUT renomear orçamento de loja1 com X-Loja-Ativa=loja1.
       Antes do fix: global ainda é loja2 → _obj_da_loja não acha o orçamento → 404.
       Depois do fix: do_PUT lê o header → loja1 → encontra o orçamento → 200.
    """
    c = http_client_factory(); c.login("dir_l1", "senha123")

    # Passo 1: contamina o global do servidor com loja2
    _get_h(c, "/api/clientes?q=", {"X-Loja-Ativa": str(seed["loja2_id"])})

    # Passo 2: PUT na loja1 — deve funcionar
    oid  = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    st, body = _put_h(
        c,
        f"/projetos/{nome}/orcamentos/{oid}",
        {"nome": "Renomeado ML"},
        {"X-Loja-Ativa": str(seed["loja1_id"])},
    )
    assert st == 200, f"Esperado 200, obtido {st}: {body}"
    assert body and body.get("ok"), f"Resposta não-ok: {body}"


def test_auth_me_expoe_lojas_acessiveis(http_client_factory, dir_l1_multiloja, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.get("/api/auth/me")
    assert st == 200
    u = body["usuario"]
    ids = {l["id"] for l in u["lojas"]}
    assert ids == {seed["loja1_id"], seed["loja2_id"]}
    assert u["loja_ativa_id"] == seed["loja1_id"]
    assert all("nome" in l and "codigo" in l for l in u["lojas"])


def test_admin_rede_cria_usuario_multiloja_na_propria_rede(http_client_factory, seed):
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Novo Diretor", "login": "novodir", "senha": "senha123",
        "nivel": "diretor", "loja_ids": [seed["loja1_id"], seed["loja2_id"]],
    })
    assert st == 200 and body["ok"] is True
    # confere que as memberships foram gravadas via /api/auth/me do novo usuário
    c2 = http_client_factory(); c2.login("novodir", "senha123")
    _, me = c2.get("/api/auth/me")
    ids = {l["id"] for l in me["usuario"]["lojas"]}
    assert ids == {seed["loja1_id"], seed["loja2_id"]}


def test_admin_rede_barrado_em_loja_de_outra_rede(http_client_factory, app_db, seed):
    # cria uma loja em outra rede
    db = app_db.get_session()
    try:
        rb = app_db.Rede(nome="Rede C"); db.add(rb); db.flush()
        lb = app_db.Loja(nome="Loja C", rede_id=rb.id, codigo="LJC"); db.add(lb); db.commit()
        loja_c = lb.id
    finally:
        db.close()
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Invasor", "login": "invasor", "senha": "senha123",
        "nivel": "diretor", "loja_ids": [seed["loja1_id"], loja_c],
    })
    assert body["ok"] is False  # loja_c fora do escopo da rede do adm_rede


def test_diretor_edit_nao_revoga_memberships_fora_do_escopo(http_client_factory, seed):
    """Regressão Finding 1: diretor que edita usuário multi-loja não pode revogar
    memberships de lojas fora do seu escopo (loja2 não deve ser removida)."""
    # Passo 1: adm_rede cria usuário multi-loja em loja1 e loja2
    cadm = http_client_factory(); cadm.login("adm_rede", "senha123")
    st, body = cadm.post("/api/admin/usuarios", {
        "nome": "Multi Diretor 2", "login": "multidir2", "senha": "senha123",
        "nivel": "diretor",
        "loja_ids": [seed["loja1_id"], seed["loja2_id"]],
    })
    assert st == 200 and body["ok"] is True, f"Criação falhou: {body}"

    # Obtém o id do novo usuário via /api/auth/me
    cnovo = http_client_factory(); cnovo.login("multidir2", "senha123")
    st_me, me = cnovo.get("/api/auth/me")
    assert st_me == 200
    novo_id = me["usuario"]["id"]
    ids_apos_criacao = {l["id"] for l in me["usuario"]["lojas"]}
    assert ids_apos_criacao == {seed["loja1_id"], seed["loja2_id"]}, \
        f"Criação deveria ter atribuído loja1+loja2; obteve: {ids_apos_criacao}"

    # Passo 2: dir_l1 (diretor da loja1) edita o telefone, mas envia loja_ids=[loja1]
    # — simula o modal que só exibe a loja do próprio ator
    cdir = http_client_factory(); cdir.login("dir_l1", "senha123")
    st_patch, patch_body = cdir.patch(f"/api/admin/usuarios/{novo_id}", {
        "telefone": "9999",
        "loja_ids": [seed["loja1_id"]],
    })
    assert st_patch == 200 and patch_body.get("ok") is True, \
        f"Edição pelo diretor falhou: st={st_patch} body={patch_body}"

    # Passo 3: memberships devem continuar sendo {loja1, loja2}
    cnovo2 = http_client_factory(); cnovo2.login("multidir2", "senha123")
    st_me2, me2 = cnovo2.get("/api/auth/me")
    assert st_me2 == 200
    ids_apos_patch = {l["id"] for l in me2["usuario"]["lojas"]}
    assert ids_apos_patch == {seed["loja1_id"], seed["loja2_id"]}, \
        f"Memberships foram alteradas pelo diretor! Esperado: {{loja1, loja2}}, Obtido: {ids_apos_patch}"
