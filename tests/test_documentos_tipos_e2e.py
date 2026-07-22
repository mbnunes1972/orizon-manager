# -*- coding: utf-8 -*-
"""Painel de Documentos — tipos customizados + preview por tipo + cabeçalho (spec
contrato-documentos/2026-07-22-cabecalho-aditivo-painel-documentos-design.md).

E2E HTTP: CRUD de documento_tipos (permissão/duplicado/slug), importar+ativar modelo de um
tipo customizado pelo fluxo REAL, e preview por tipo SEM corpo_md (modelo ativo/padrão do
sistema, contexto de exemplo no aditivo)."""
import json
import urllib.request as _urllib_req


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


def _post_multipart_md(c, tipo, nome_arq, texto):
    boundary = b"----DocTipoBoundary"
    body = (b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="arquivo"; filename="' + nome_arq.encode() + b'"\r\n'
            b"Content-Type: text/markdown\r\n\r\n" + texto.encode("utf-8") + b"\r\n"
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="tipo"\r\n\r\n' + tipo.encode() + b"\r\n"
            b"--" + boundary + b"--\r\n")
    req = _urllib_req.Request(c.base + "/api/documentos/modelos/importar", data=body, method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary=" + boundary.decode())
    req.add_header("Cookie", c.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=15)
        return resp.status, json.loads(resp.read())
    except _urllib_req.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _preview_raw(c, payload):
    data = json.dumps(payload).encode("utf-8")
    req = _urllib_req.Request(c.base + "/api/documentos/modelos/preview", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Cookie", c.cookie)
    try:
        resp = _urllib_req.urlopen(req, timeout=60)
        return resp.status, resp.read()
    except _urllib_req.HTTPError as e:
        return e.code, e.read()


def test_criar_listar_tipos_customizados(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")

    st, body = c.post("/api/documentos/tipos", {"nome": "Ficha de Montagem", "etapa_ciclo": "16"})
    assert st == 200 and body["ok"], body
    t = body["tipo"]
    assert t["slug"].startswith("doc_") and "ficha" in t["slug"]
    assert t["nome"] == "Ficha de Montagem" and t["etapa_ciclo"] == "16"

    st, body = c.get("/api/documentos/tipos")
    assert st == 200 and body["ok"], body
    assert any(x["slug"] == t["slug"] for x in body["tipos"])

    # duplicado → erro claro
    st, body = c.post("/api/documentos/tipos", {"nome": "Ficha de Montagem"})
    assert st == 400 and "existe" in (body.get("erro") or "").lower(), body

    # nome vazio → erro
    st, body = c.post("/api/documentos/tipos", {"nome": "  "})
    assert st == 400, body

    # sem gerir_documentos (operador) → 403
    c2 = _login(http_client_factory, "cons_l1")
    st, body = c2.post("/api/documentos/tipos", {"nome": "Doc do Consultor"})
    assert st == 403, body


def test_importar_ativar_e_preview_tipo_customizado(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/documentos/tipos", {"nome": "Checklist de Entrega", "etapa_ciclo": "17"})
    assert st == 200 and body["ok"], body
    slug = body["tipo"]["slug"]

    corpo = "# CHECKLIST DE ENTREGA\n1. Cliente: [NOME_CLIENTE]\n2. Loja: [NOME_EMPRESA]\n"
    st, body = _post_multipart_md(c, slug, "checklist.md", corpo)
    assert st == 200 and body["ok"], body
    st2, body2 = c.post("/api/documentos/modelos",
                        {"tipo": slug, "corpo_md": body["corpo_md"],
                         "origem_nome": body["origem_nome"], "staging": body["staging"],
                         "origem_sha256": body["origem_sha256"], "cravados_aprovados": []})
    assert st2 == 200 and body2["ok"], body2

    st, body = c.get("/api/documentos/modelos")
    assert any(m["tipo"] == slug and m["ativo"] for m in body["modelos"]), body

    # preview do modelo ATIVO (sem corpo_md) → PDF corpo-só com cabeçalho
    st, raw = _preview_raw(c, {"tipo": slug})
    assert st == 200 and raw[:4] == b"%PDF", (st, raw[:80])


def test_preview_sem_corpo_por_tipo_nativo(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    # contrato: cai no modelo global do sistema (capa+corpo)
    st, raw = _preview_raw(c, {"tipo": "contrato"})
    assert st == 200 and raw[:4] == b"%PDF", (st, raw[:80])
    # termo_aditivo: modelo padrão do sistema + contexto de EXEMPLO (ordinal, blocos)
    st, raw = _preview_raw(c, {"tipo": "termo_aditivo"})
    assert st == 200 and raw[:4] == b"%PDF", (st, raw[:80])
    # tipo desconhecido → erro JSON, não 500
    st, raw = _preview_raw(c, {"tipo": "doc_inexistente"})
    assert st == 400, (st, raw[:120])
