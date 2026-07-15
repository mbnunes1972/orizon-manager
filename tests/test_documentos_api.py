# -*- coding: utf-8 -*-
"""tests/test_documentos_api.py — Task 8: os 5 endpoints HTTP do registro de modelos de
documento por loja (miolo já pronto/testado em mod_documentos.py / mod_marcadores.py /
mod_documentos_import.py).

Sobe o servidor real (fixtures `servidor`/`seed`/`http_client_factory` de conftest.py) e bate
via HTTP — a Task 6 aprendeu que teste unitário não prova a composição (login+escopo+multipart+
resposta), então aqui é E2E de propósito, não chamada direta aos módulos.

`HttpClient` (conftest.py) só fala JSON. Os endpoints desta frente precisam de multipart
(importar) e de resposta binária/PDF (preview) — os dois helpers abaixo (`_post_multipart`,
`_post_json_raw`) resolvem isso com urllib puro, no mesmo estilo de
tests/test_qualidade_upload_e2e.py.

NENHUM teste sobe .docx/.odt de verdade — só .md/.txt (leitura direta, sem LibreOffice) — e o
teste de "falha de conversão" monkeypatcha mod_documentos_import.normalizar em vez de forçar o
LibreOffice a falhar.
"""
import os
import json as _json
import urllib.request as _urllib_req

import pytest


# ── Helpers HTTP (o HttpClient de conftest.py só fala JSON) ────────────────────

def _post_multipart(client, path, campos, arquivo=None):
    """arquivo: (nome_campo, filename, bytes) ou None. Devolve (status, dict|bytes)."""
    boundary = b"----DocApiTestBoundary"
    partes = []
    for k, v in (campos or {}).items():
        partes.append(
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="' + k.encode() + b'"\r\n\r\n'
            + str(v).encode("utf-8") + b"\r\n"
        )
    if arquivo:
        nome_campo, filename, dados = arquivo
        partes.append(
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="' + nome_campo.encode() +
            b'"; filename="' + filename.encode() + b'"\r\n'
            b"Content-Type: application/octet-stream\r\n\r\n"
            + dados + b"\r\n"
        )
    partes.append(b"--" + boundary + b"--\r\n")
    body = b"".join(partes)

    req = _urllib_req.Request(client.base + path, data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary.decode())
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=10)
        status, raw = resp.status, resp.read()
    except _urllib_req.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        data = _json.loads(raw) if raw else None
    except Exception:
        data = raw
    return status, data


def _post_json_raw(client, path, payload):
    """POST JSON devolvendo a resposta CRUA (status, bytes, headers) — usado no preview,
    que devolve application/pdf, não JSON."""
    data = _json.dumps(payload).encode("utf-8")
    req = _urllib_req.Request(client.base + path, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=15)
        return resp.status, resp.read(), dict(resp.headers)
    except _urllib_req.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def _login(factory, who):
    c = factory()
    status, body = c.login(who, "senha123")
    assert status == 200, body
    return c


CORPO_OK = "CLAUSULA PRIMEIRA\n1.1. [NOME_CLIENTE], CPF [CPF_CLIENTE], texto de teste.\n"
CORPO_DESCONHECIDO = "CLAUSULA PRIMEIRA\n1.1. [MARCADOR_QUE_NAO_EXISTE] no meio do texto.\n"


# ── GET /api/documentos/marcadores ──────────────────────────────────────────────

def test_marcadores_sem_sessao_401(http_client_factory):
    c = http_client_factory()
    status, body = c.get("/api/documentos/marcadores")
    assert status == 401, body


def test_marcadores_com_sessao_devolve_catalogo(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.get("/api/documentos/marcadores")
    assert status == 200, body
    assert body["ok"] is True
    assert "NOME_CLIENTE" in body["catalogo"]
    assert body["catalogo"]["NOME_CLIENTE"]["escopo"] == "cliente"


# ── GET /api/documentos/modelos — escopo por loja + pode_gerir ─────────────────

def test_modelos_get_escopado_e_pode_gerir_reflete_perfil(http_client_factory):
    master = _login(http_client_factory, "dir_l1")
    status, body = master.get("/api/documentos/modelos")
    assert status == 200, body
    assert body["ok"] is True
    assert body["pode_gerir"] is True   # master: gerir_documentos = True

    operador = _login(http_client_factory, "cons_l1")
    status, body = operador.get("/api/documentos/modelos")
    assert status == 200, body
    assert body["pode_gerir"] is False  # operador: gerir_documentos = False


def test_tenancy_loja_a_nao_ve_modelo_da_loja_b(app_db, seed, http_client_factory):
    import mod_documentos
    db = app_db.get_session()
    try:
        v = mod_documentos.criar_versao(
            db, seed["loja2_id"], "contrato",
            "CLAUSULA PRIMEIRA\n1.1. Modelo exclusivo da Loja 2.\n", "l2.md", 1)
        mod_documentos.ativar(db, v.id)
        v_id = v.id
    finally:
        db.close()

    c1 = _login(http_client_factory, "dir_l1")
    status, body = c1.get("/api/documentos/modelos")
    assert status == 200, body
    ids_l1 = {m["id"] for m in body["modelos"]}
    assert v_id not in ids_l1, "loja A não pode enxergar modelo da loja B"

    c2 = _login(http_client_factory, "dir_l2")
    status, body = c2.get("/api/documentos/modelos")
    assert status == 200, body
    ids_l2 = {m["id"] for m in body["modelos"]}
    assert v_id in ids_l2


# ── POST /api/documentos/modelos/importar ───────────────────────────────────────

def test_importar_sem_capacidade_403(http_client_factory):
    c = _login(http_client_factory, "cons_l1")   # operador: sem gerir_documentos
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.md", CORPO_OK.encode("utf-8")))
    assert status == 403, body


def test_importar_pdf_400_com_mensagem_acionavel(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.pdf", b"%PDF-1.4 conteudo qualquer"))
    assert status == 400, body
    assert "PDF" in body["erro"] and "Word" in body["erro"]


def test_importar_md_valido_devolve_corpo_e_nao_cria_versao(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo_valido.md", CORPO_OK.encode("utf-8")))
    assert status == 200, body
    assert body["ok"] is True
    assert body["corpo_md"].strip()
    assert body["origem_nome"] == "modelo_valido.md"
    assert body["tipo"] == "contrato"
    assert body["staging"] == os.path.basename(body["staging"]), "staging deve ser só o basename"
    assert "/" not in body["staging"] and "\\" not in body["staging"]
    assert body["analise"]["bloqueia_ativacao"] is False
    assert "NOME_CLIENTE" in body["analise"]["conhecidos_usados"]

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "importar NUNCA cria versão — só converte e analisa"


def test_importar_falha_de_conversao_remove_o_staging(seed, http_client_factory, monkeypatch, tmp_path):
    """normalizar() falhando (não FormatoNaoSuportado) tem que limpar o staging."""
    import mod_documentos, mod_documentos_import
    docs_dir = str(tmp_path / "docs_falha")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)
    monkeypatch.setattr(mod_documentos_import, "normalizar",
                        lambda path: (_ for _ in ()).throw(RuntimeError("conversão simulada falhou")))

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "modelo.docx", b"binario irrelevante, normalizar esta mockado"))
    assert status == 400, body
    assert "Falha ao converter" in body["erro"]

    staging_dir = os.path.join(docs_dir, str(seed["loja1_id"]), "contrato", "_staging")
    restantes = os.listdir(staging_dir) if os.path.exists(staging_dir) else []
    assert restantes == [], "staging não foi limpo após falha de conversão: %r" % restantes


def test_importar_corpo_vazio_remove_o_staging(seed, http_client_factory, monkeypatch, tmp_path):
    import mod_documentos
    docs_dir = str(tmp_path / "docs_vazio")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)

    c = _login(http_client_factory, "dir_l1")
    status, body = _post_multipart(
        c, "/api/documentos/modelos/importar", {"tipo": "contrato"},
        arquivo=("arquivo", "vazio.txt", b"   \n\n   \n"))
    assert status == 400, body
    assert "conte" in body["erro"].lower() or "vazio" in body["erro"].lower()

    staging_dir = os.path.join(docs_dir, str(seed["loja1_id"]), "contrato", "_staging")
    restantes = os.listdir(staging_dir) if os.path.exists(staging_dir) else []
    assert restantes == [], "staging não foi limpo após corpo vazio: %r" % restantes


# ── POST /api/documentos/modelos/preview ────────────────────────────────────────

def test_preview_sem_capacidade_403(http_client_factory):
    c = _login(http_client_factory, "cons_l1")
    status, body, _headers = _post_json_raw(
        c, "/api/documentos/modelos/preview", {"corpo_md": CORPO_OK})
    assert status == 403
    assert _json.loads(body)["ok"] is False


def test_preview_gera_pdf_e_nao_salva_nada(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, dados, headers = _post_json_raw(
        c, "/api/documentos/modelos/preview", {"corpo_md": CORPO_OK})
    assert status == 200, dados[:300]
    assert headers.get("Content-Type") == "application/pdf"
    assert dados[:4] == b"%PDF"

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "preview não pode persistir nada"


# ── POST /api/documentos/modelos — cria + ativa ─────────────────────────────────

def test_modelos_post_sem_capacidade_403(http_client_factory):
    c = _login(http_client_factory, "cons_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_OK, "origem_nome": "m.md",
        "cravados_aprovados": [],
    })
    assert status == 403, body


def test_modelos_post_marcador_desconhecido_400_nada_criado(app_db, seed, http_client_factory):
    db = app_db.get_session()
    antes = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()

    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_DESCONHECIDO, "origem_nome": "m.md",
        "cravados_aprovados": [],
    })
    assert status == 400, body
    assert body["ok"] is False
    assert "MARCADOR_QUE_NAO_EXISTE" in body["erro"]

    db = app_db.get_session()
    depois = db.query(app_db.DocumentoModelo).filter_by(loja_id=seed["loja1_id"]).count()
    db.close()
    assert depois == antes, "marcador desconhecido não pode criar versão nenhuma"


def test_modelos_post_feliz_cria_ativa_e_aparece_no_get(http_client_factory):
    c = _login(http_client_factory, "dir_l1")
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "proposta", "corpo_md": CORPO_OK, "origem_nome": "proposta_nova.md",
        "cravados_aprovados": [],
    })
    assert status == 200, body
    assert body["ok"] is True
    modelo = body["modelo"]
    assert modelo["tipo"] == "proposta"
    assert modelo["ativo"] is True

    status, body = c.get("/api/documentos/modelos")
    assert status == 200, body
    achados = [m for m in body["modelos"] if m["id"] == modelo["id"]]
    assert len(achados) == 1
    assert achados[0]["ativo"] is True


# ── Path traversal ───────────────────────────────────────────────────────────────

def test_staging_path_traversal_nao_escapa_da_loja(app_db, seed, http_client_factory, monkeypatch, tmp_path):
    """'staging' vindo do cliente com componentes de diretório não pode fazer o servidor
    promover um arquivo de fora do _staging/ da loja da sessão (nem de outra loja)."""
    import mod_documentos
    docs_dir = str(tmp_path / "docs_traversal")
    monkeypatch.setattr(mod_documentos, "DOCS_LOJA_DIR", docs_dir)

    # Arquivo "secreto" no _staging de verdade da Loja 2, mesmo nome que será tentado.
    outro_dir = os.path.join(docs_dir, str(seed["loja2_id"]), "contrato", "_staging")
    os.makedirs(outro_dir, exist_ok=True)
    secreto = os.path.join(outro_dir, "traversal_alvo.docx")
    with open(secreto, "wb") as fh:
        fh.write(b"CONTEUDO DA LOJA 2 - NAO PODE VAZAR")

    c = _login(http_client_factory, "dir_l1")   # sessão da Loja 1
    status, body = c.post("/api/documentos/modelos", {
        "tipo": "contrato", "corpo_md": CORPO_OK, "origem_nome": "modelo.md",
        "staging": "../../%s/contrato/_staging/traversal_alvo.docx" % seed["loja2_id"],
        "cravados_aprovados": [],
    })
    assert status == 200, body   # não existindo no destino recomposto, segue sem origem_path
    assert body["ok"] is True

    db = app_db.get_session()
    try:
        m = db.get(app_db.DocumentoModelo, body["modelo"]["id"])
        assert m.loja_id == seed["loja1_id"]
        assert m.origem_path is None, (
            "path traversal NÃO pode ter promovido o arquivo da Loja 2: origem_path=%r" % m.origem_path
        )
    finally:
        db.close()
    # o arquivo "secreto" da Loja 2 continua onde estava — não foi movido/consumido
    assert os.path.exists(secreto)
