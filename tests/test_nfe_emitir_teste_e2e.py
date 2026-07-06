import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
import nfe_emissao
from emissor_fiscal import resultado_de_focus


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH999",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def baixar(self, caminho): return b"BYTES"


class FakeEmissor:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota): return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})


def _post_multipart(base, cookie, path, fields, filename, filedata):
    boundary = "----t" + _uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--"+boundary+"\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{k}"\r\n\r\n').encode())
        parts.append((str(v)+"\r\n").encode())
    parts.append(("--"+boundary+"\r\n").encode())
    parts.append((f'Content-Disposition: form-data; name="arquivo"; filename="{filename}"\r\n').encode())
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(filedata); parts.append(b"\r\n")
    parts.append(("--"+boundary+"--\r\n").encode())
    req = urllib.request.Request(base+path, data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    if cookie: req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.add(app_db.PerfilFiscal(loja_id=loja_id, ambiente_ativo="homologacao", razao_social="LOJA X",
                               csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102"))
    db.commit(); db.close()


def test_emitir_teste_ok(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": proj, "markup_pct": "30"}, "fabrica.xml", _fixture_xml())
    assert st == 200 and b.get("ok") is True, b
    assert b["status"] == "autorizado" and b["chave"] == "CH999" and b["xml_doc_id"]


def test_emitir_teste_sem_perfil_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    db = app_db.get_session(); db.query(app_db.PerfilFiscal).filter_by(loja_id=seed["loja2_id"]).delete(); db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": seed["projeto_l2"], "markup_pct": "30"}, "f.xml", _fixture_xml())
    assert st == 400


def test_emitir_teste_perm_403(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "cons_l1")
    st, _ = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja1_id']}/nfe/emitir-teste",
                            {"projeto_nome": seed["projeto_l1"], "markup_pct": "30"}, "f.xml", _fixture_xml())
    assert st == 403


def test_emitir_teste_projeto_de_outra_loja_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")   # diretor loja2, mas projeto é da loja1
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": seed["projeto_l1"], "markup_pct": "30"}, "f.xml", _fixture_xml())
    assert st == 400 and "não pertence" in b.get("erro", "").lower()
