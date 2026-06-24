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
