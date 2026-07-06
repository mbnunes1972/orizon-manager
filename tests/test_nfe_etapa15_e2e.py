import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
import nfe_emissao
from emissor_fiscal import resultado_de_focus


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH-15",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def baixar(self, caminho): return b"BYTES"


class FakeEmissor:
    def __init__(self): self.client = FakeClient(); self.nota_recebida = None
    def emitir_nfe_produto(self, nota):
        self.nota_recebida = nota
        return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH-15",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    """Garante que a loja tem um Emitente próprio (o do seed) com o ambiente pedido e tokens,
    e que loja.emitente_id aponta para ele. A emissão resolve o Emitente (não o PerfilFiscal)."""
    import fiscal_cripto
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    em = db.get(app_db.Emitente, loja.emitente_id) if loja.emitente_id else None
    if em is None:
        em = app_db.Emitente(cnpj="90000000000%02d" % loja_id, razao_social="LOJA X",
                             regime_tributario="simples", csosn_padrao="102",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                             cidade="Sao Paulo", logradouro="Rua A", numero="1",
                             bairro="Centro", cep="01000-000")
        db.add(em); db.flush()
        loja.emitente_id = em.id
    em.ambiente_ativo = ambiente
    em.focus_token_homolog_enc = fiscal_cripto.encrypt("tok-homolog")
    em.focus_token_prod_enc = fiscal_cripto.encrypt("tok-prod")
    db.commit(); db.close()


def _sem_emitente(app_db, loja_id):
    """Remove qualquer emitente resolvível para a loja (self, override de loja, default de rede)
    → resolver_emitente lança ValueError e o endpoint responde 400."""
    db = app_db.get_session()
    loja = db.get(app_db.Loja, loja_id)
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="loja", owner_id=loja_id).delete()
    if loja.rede_id is not None:
        db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=loja.rede_id).delete()
    loja.emitente_id = None
    db.commit(); db.close()


def _reset15(app_db, proj):
    db = app_db.get_session()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.query(app_db.DocumentoFiscal).filter_by(projeto_nome=proj).delete()
    db.commit(); db.close()


def _upload_xml(c, proj, data):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             (f'Content-Disposition: form-data; name="arquivo"; filename="fabrica.xml"\r\n').encode(),
             b"Content-Type: application/octet-stream\r\n\r\n", data, b"\r\n",
             ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def test_upload_nfe_fabrica_e_estado(http_client_factory, seed, app_db, projetos_dir):
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    st, b = _upload_xml(c, proj, _fixture_xml())
    assert st == 200 and b.get("documento_id"), b
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert st2 == 200 and g["ok"] is True
    assert len(g["fabrica_xmls"]) == 1 and g["fabrica_xmls"][0]["emissao"] is None


def test_upload_nfe_fabrica_perm_403(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "cons_l1")     # sem editar_dados_loja
    st, _ = _upload_xml(c, seed["projeto_l1"], _fixture_xml())
    assert st == 403


def test_get_nfe_nao_autenticado_401(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory()
    st, _ = c.get(f"/api/projetos/{seed['projeto_l2']}/ciclo/15/nfe")
    assert st == 401


def _upload_sem_arquivo(c, proj):
    boundary = "----t" + _uuid.uuid4().hex
    parts = [("--"+boundary+"\r\n").encode(),
             (f'Content-Disposition: form-data; name="dummy"\r\n\r\n').encode(),
             b"x\r\n", ("--"+boundary+"--\r\n").encode()]
    req = urllib.request.Request(c.base + f"/api/projetos/{proj}/ciclo/15/nfe-fabrica",
                                 data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def test_upload_sem_arquivo_400(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    st, _ = _upload_sem_arquivo(c, seed["projeto_l2"])
    assert st == 400


def test_upload_projeto_de_outra_loja_404(http_client_factory, seed, app_db, projetos_dir):
    # diretor da loja2 (tem editar_dados_loja) tentando a etapa 15 de um projeto da loja1
    c = _login(http_client_factory, "dir_l2")
    st, _ = _upload_xml(c, seed["projeto_l1"], _fixture_xml())
    assert st == 404


def _post(c, path, body):
    import urllib.request, urllib.error, json as J
    req = urllib.request.Request(c.base + path, data=J.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if c.cookie: req.add_header("Cookie", c.cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, J.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, J.loads(e.read() or b"{}")


def test_emitir_etapa15_autoriza_conclui(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    doc_id = up["documento_id"]
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado" and b["chave"] == "CH-15", b
    assert b["ref"] == f"NFE-{proj}-{doc_id}" and b["xml_doc_id"]
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status == "emitida"
    db.close()
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert g["fabrica_xmls"][0]["emissao"]["status"] == "autorizado"
    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st3 == 200 and b3["ref"] == b["ref"]


def test_emitir_etapa15_sem_emitente_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj)
    _sem_emitente(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    dbx = app_db.get_session()
    d = app_db.CicloDocumento(projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml",
                              arquivo_path="ciclo/15/x.xml", nome_original="x.xml")
    dbx.add(d); dbx.commit(); did = d.id; dbx.close()
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": did, "markup_pct": 30})
    assert st == 400 and "emitente" in b.get("erro", "").lower()
    # restaura o emitente da loja para não afetar testes seguintes do módulo
    _perfil(app_db, seed["loja2_id"])


def test_consultar_e_cancelar_etapa15(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    ref = f"NFE-{proj}-{up['documento_id']}"
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/consultar", {"ref": ref})
    assert st == 200 and b["status"] == "autorizado"
    st2, b2 = _post(c, f"/api/projetos/{proj}/ciclo/15/nfe/cancelar", {"ref": ref, "justificativa": "cancelamento teste homologacao"})
    assert st2 == 200 and b2["status"] == "cancelado"
    # nota cancelada → etapa 15 deixa de ser conclusiva
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status != "emitida"
    db.close()


def test_consultar_cancelar_cross_tenant_via_ref_404(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    # dir_l2 opera sobre o SEU projeto na URL, mas envia um ref de uma NF-e da loja1 no body → 404, sem tocar a nota alheia
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj2 = seed["projeto_l2"]; proj1 = seed["projeto_l1"]
    _reset15(app_db, proj2); _reset15(app_db, proj1); _perfil(app_db, seed["loja2_id"])
    db = app_db.get_session()
    db.add(app_db.DocumentoFiscal(ref="NFE-ALHEIA-1", projeto_nome=proj1, loja_id=seed["loja1_id"], status="autorizado"))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, _ = _post(c, f"/api/projetos/{proj2}/ciclo/15/nfe/consultar", {"ref": "NFE-ALHEIA-1"})
    assert st == 404
    st2, _ = _post(c, f"/api/projetos/{proj2}/ciclo/15/nfe/cancelar", {"ref": "NFE-ALHEIA-1", "justificativa": "tentativa cross tenant xyz"})
    assert st2 == 404
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref="NFE-ALHEIA-1").first()
    assert reg.status == "autorizado"   # a NF-e da loja1 permanece intocada
    db.close()


class FakeEmissorRejeita:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        return resultado_de_focus({"ref": nota["ref"], "status": "erro_autorizacao",
                                   "erros": [{"codigo": "999", "mensagem": "rejeitado"}]})


def test_emitir_rejeitada_nao_conclui_etapa(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissorRejeita())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj); _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] != "autorizado"
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status != "emitida"
    db.close()


class FakeEmissorCaptura:
    """Captura a nota emitida (para inspecionar o CNPJ do emitente no payload)."""
    _ultima = {}
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota):
        FakeEmissorCaptura._ultima["nota"] = nota
        return resultado_de_focus({"ref": nota["ref"], "status": "autorizado", "chave_nfe": "CH-MC",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})


def test_emitir_produto_sob_emitente_central_da_rede(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    """Multi-CNPJ: loja com Emitente próprio (self) + PerfilEmissao(owner=rede, produto)→central.
    A emissão de produto deve sair sob o CNPJ da CENTRAL (não o self da loja):
    DocumentoFiscal.emitente_id == central e o payload capturado tem o CNPJ da central."""
    import fiscal_cripto
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissorCaptura())
    FakeEmissorCaptura._ultima.clear()
    proj = seed["projeto_l2"]
    _reset15(app_db, proj)
    _perfil(app_db, seed["loja2_id"])   # garante o self-emitente da loja + tokens

    # cria o Emitente CENTRAL da rede e o PerfilEmissao(rede, produto)→central
    db = app_db.get_session()
    loja = db.get(app_db.Loja, seed["loja2_id"])
    self_eid = loja.emitente_id
    rede_id = loja.rede_id
    central = app_db.Emitente(cnpj="77777777000177", razao_social="CENTRAL DA REDE LTDA",
                              regime_tributario="simples", csosn_padrao="101",
                              cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                              cidade="Sao Paulo", logradouro="Av Central", numero="1000",
                              bairro="Centro", cep="01000-000", ambiente_ativo="homologacao",
                              focus_token_homolog_enc=fiscal_cripto.encrypt("tok-central"))
    db.add(central); db.flush()
    central_id = central.id
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=rede_id,
                                             tipo_doc="produto").delete()
    db.add(app_db.PerfilEmissao(owner_tipo="rede", owner_id=rede_id, tipo_doc="produto",
                                emitente_id=central_id))
    db.commit(); db.close()
    assert central_id != self_eid

    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml())
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe",
                  {"fabrica_doc_id": up["documento_id"], "markup_pct": 30})
    assert st == 200 and b["status"] == "autorizado", b

    # DocumentoFiscal gravado sob o emitente CENTRAL (≠ self da loja)
    db = app_db.get_session()
    reg = db.query(app_db.DocumentoFiscal).filter_by(ref=b["ref"]).first()
    assert reg.emitente_id == central_id and reg.emitente_id != self_eid
    db.close()
    # o payload que foi ao emissor tem o CNPJ da central no bloco emitente
    assert FakeEmissorCaptura._ultima["nota"]["emitente"]["doc"] == "77777777000177"

    # GET nfe expõe o emitente da emissão (central)
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    emissao = g["fabrica_xmls"][0]["emissao"]
    assert emissao["emitente_cnpj"] == "77777777000177"
    assert emissao["emitente_razao"] == "CENTRAL DA REDE LTDA"

    # limpa o PerfilEmissao de rede para não afetar testes seguintes do módulo
    db = app_db.get_session()
    db.query(app_db.PerfilEmissao).filter_by(owner_tipo="rede", owner_id=rede_id,
                                             tipo_doc="produto").delete()
    db.commit(); db.close()
