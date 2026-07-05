import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json, uuid as _uuid
import urllib.request, urllib.error


def _post_multipart(base, cookie, path, fields, file_field=None, filename=None, filedata=b""):
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
        parts.append(filedata); parts.append(b"\r\n")
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


def _reset_etapas(app_db, proj, codigos):
    """Zera CicloDocumento + CicloEtapa das etapas dadas. Necessário porque `seed`/
    `app_db` são module-scoped → o estado vaza entre testes do mesmo arquivo."""
    db = app_db.get_session()
    for cod in codigos:
        db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo=cod).delete()
        db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=cod).delete()
    db.commit(); db.close()


def _marcar_concluida(app_db, proj, codigo):
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo=codigo).first()
    if et:
        et.status = "concluido"
    else:
        db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=codigo, status="concluido"))
    db.commit(); db.close()


def test_upload_xml_append_only_e_listagem(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12"])
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="pedido1.xml", filedata=b"<xml>1</xml>")
    assert st == 200 and body.get("ok") is True, body
    st2, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="pedido2.xml", filedata=b"<xml>2</xml>")
    assert st2 == 200
    st3, lst = c.get(f"/api/projetos/{proj}/ciclo/12/pedido-xml")
    assert st3 == 200 and lst["ok"] is True
    assert len(lst["documentos"]) == 2, "append-only deve manter os dois XMLs"


def test_upload_xml_sem_arquivo_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {})
    assert st == 400


def test_upload_xml_etapa_sem_upload_400(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/13/pedido-xml", {},
        file_field="arquivo", filename="x.xml", filedata=b"x")
    assert st == 400


def test_upload_xml_nao_autenticado_401(http_client_factory, seed, projetos_dir):
    c = http_client_factory()   # sem login
    proj = seed["projeto_l2"]
    st, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="x.xml", filedata=b"x")
    assert st == 401


def test_upload_xml_cycle_gated_consultor_ok(http_client_factory, seed, projetos_dir):
    # consultor NÃO tem executar_pe, mas AQUI é cycle-gated → deve conseguir (200)
    c = _login(http_client_factory, "cons_l1")
    proj = seed["projeto_l1"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
        file_field="arquivo", filename="p.xml", filedata=b"<xml/>")
    assert st == 200 and body.get("ok") is True, body
