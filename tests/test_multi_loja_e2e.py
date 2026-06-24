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
