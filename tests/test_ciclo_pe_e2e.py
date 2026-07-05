import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json, uuid as _uuid
import urllib.request, urllib.error


def _post_multipart(base, cookie, path, fields, file_field=None, filename=None, filedata=b""):
    """POST multipart/form-data compatível com _parse_multipart_arquivos do main.py."""
    boundary = "----orizonTEST" + _uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--" + boundary + "\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{k}"\r\n\r\n').encode())
        parts.append((str(v) + "\r\n").encode())
    if file_field:
        parts.append(("--" + boundary + "\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n').encode())
        parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        parts.append(filedata)
        parts.append(b"\r\n")
    parts.append(("--" + boundary + "--\r\n").encode())
    body = b"".join(parts)
    req = urllib.request.Request(base + path, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_upload_pe_cria_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta.pdf", filedata=b"%PDF-fake")
    assert st == 200 and body.get("ok") is True, body
    st2, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta_v2.pdf", filedata=b"%PDF-fake2")
    assert st2 == 200
    st3, docs = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st3 == 200
    versoes = [d for d in docs["documentos"] if d["tipo"] == "pe_planta_pontos"]
    assert len(versoes) == 2, "append-only deve manter as duas versões"


def test_get_pe_lista_documentos_e_medicao_intocada(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11c/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="pe.pdf", filedata=b"PE")
    st, body = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st == 200 and body["ok"] is True
    assert any(d["tipo"] == "pe_projeto_executivo" for d in body["documentos"])
    assert "11c" in body["subfases"]
    med = os.path.join(projetos_dir, proj, "medicao")
    assert not os.path.exists(med) or os.listdir(med) == []
