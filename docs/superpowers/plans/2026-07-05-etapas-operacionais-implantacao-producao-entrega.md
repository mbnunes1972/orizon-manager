# Etapas operacionais 12/13/14 (Implantação · Produção · Entrega) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ações concretas às etapas principais 12 (Implantação do pedido), 13 (Produção) e 14 (Entrega no depósito) do ciclo — upload de XMLs, números dos pedidos e relatório de entrega — reusando o `PATCH /ciclo` existente e sem nova tabela/capability.

**Architecture:** Abordagem C do spec. Guardas puras em `mod_ciclo.py`; um endpoint novo de upload append-only (`POST /ciclo/<codigo>/pedido-xml`, cycle-gated) reusando `CicloDocumento`; listagem via `GET` novo; conclusão e salvar-texto reusam o `PATCH /ciclo/<codigo>` já existente (números/relatório em `CicloEtapa.observacoes`), com uma guarda operacional inserida antes de concluir. Frontend com 3 painéis dedicados. PE intocado.

**Tech Stack:** Python `http.server` + SQLAlchemy/SQLite (backend), `static/index.html` (HTML+JS inline), pytest.

**Base para ler antes:** spec `docs/superpowers/specs/ciclo/2026-07-05-etapas-operacionais-implantacao-producao-entrega-design.md`. Padrões existentes a espelhar: PE upload em `main.py:3765-3810`, PATCH ciclo em `main.py:4183-4260`, GET `/ciclo/pe` em `main.py:1348-1386`, guardas puras em `mod_ciclo.py:66-93`, testes puros em `tests/test_ciclo.py`, e2e em `tests/test_ciclo_pe_e2e.py`, fixtures em `tests/conftest.py`.

**Lembrete de ambiente:** mudança em Python (`main.py`/`mod_ciclo.py`) **exige restart** do servidor para verificação manual; os testes e2e sobem o próprio servidor (fixture `http_client_factory`), então `pytest` pega o código novo sem restart. Frontend (`index.html`) é lido do disco a cada request → só **Ctrl+F5**.

---

## File Structure

- **Modify** `mod_ciclo.py` — adiciona `ETAPAS_OPERACIONAIS`, `tipo_doc_operacional`, `guarda_conclusao_operacional` (lógica pura, sem I/O).
- **Modify** `main.py` — 2 endpoints novos (`POST`/`GET .../ciclo/<codigo>/pedido-xml`) + guarda operacional dentro do `PATCH /ciclo/<codigo>`.
- **Modify** `static/index.html` — loader de estado dos XMLs, roteamento das etapas 12/13/14 para painéis dedicados, 3 funções de render e seus handlers.
- **Modify** `tests/test_ciclo.py` — testes puros das guardas.
- **Create** `tests/test_ciclo_operacional_e2e.py` — testes e2e HTTP.

---

## Task 1: Lógica pura em `mod_ciclo.py` (guardas operacionais)

**Files:**
- Modify: `mod_ciclo.py` (adicionar após o bloco do PE, perto da linha 97 `ETAPAS_APROVACAO_FINANCEIRA`)
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Write the failing tests**

Adicionar ao final de `tests/test_ciclo.py`:

```python
def test_tipo_doc_operacional():
    assert mc.tipo_doc_operacional("12") == "implantacao_pedido_xml"
    assert mc.tipo_doc_operacional("13") is None   # 13 não aceita upload
    assert mc.tipo_doc_operacional("14") is None
    assert mc.tipo_doc_operacional("11a") is None


def test_guarda_operacional_12_exige_xml():
    ok, erro = mc.guarda_conclusao_operacional("12", False, None, None)
    assert ok is False and "XML" in erro
    ok, erro = mc.guarda_conclusao_operacional("12", True, None, None)
    assert ok is True and erro == ""


def test_guarda_operacional_13_exige_numeros():
    ok, erro = mc.guarda_conclusao_operacional("13", False, "   \n  ", None)
    assert ok is False and "número" in erro.lower()
    ok, erro = mc.guarda_conclusao_operacional("13", False, "P-1001\nP-1002", None)
    assert ok is True and erro == ""


def test_guarda_operacional_14_exige_relatorio():
    ok, erro = mc.guarda_conclusao_operacional("14", False, None, "   ")
    assert ok is False and "Relatório" in erro
    ok, erro = mc.guarda_conclusao_operacional("14", False, None, "1 porta avariada")
    assert ok is True and erro == ""


def test_guarda_operacional_codigo_desconhecido():
    ok, erro = mc.guarda_conclusao_operacional("99", False, None, None)
    assert ok is False and "desconhecida" in erro.lower()


def test_etapas_operacionais_registradas():
    assert set(mc.ETAPAS_OPERACIONAIS) == {"12", "13", "14"}
    # nomes em sincronia com ETAPA_NOME (fonte canônica)
    for cod in mc.ETAPAS_OPERACIONAIS:
        assert mc.ETAPAS_OPERACIONAIS[cod]["nome"] == mc.ETAPA_NOME[cod]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ciclo.py -q -k "operacional"`
Expected: FAIL com `AttributeError: module 'mod_ciclo' has no attribute 'tipo_doc_operacional'`.

- [ ] **Step 3: Write the implementation**

Adicionar em `mod_ciclo.py` logo antes do bloco `# Etapas que exigem autorização financeira` (linha ~96):

```python
# ── Etapas operacionais (12/13/14) — ações e guardas de conclusão ─────────────
# Etapas principais pós-PE com ações próprias no frontend. Cycle-gated (sem
# capability dedicada): quem já pode avançar o ciclo executa. Só a 12 aceita
# upload (XMLs dos pedidos); 13/14 guardam texto em CicloEtapa.observacoes.
ETAPAS_OPERACIONAIS = {
    "12": {"nome": "Implantação do pedido", "exige": "xml",
           "tipo_doc": "implantacao_pedido_xml", "botao": "Encaminhar Pedidos à Fábrica"},
    "13": {"nome": "Produção",              "exige": "numeros",
           "botao": "Produção Concluída"},
    "14": {"nome": "Entrega no depósito",   "exige": "relatorio",
           "botao": "Concluir Relatório de Entrega"},
}


def tipo_doc_operacional(codigo):
    """tipo_doc da etapa operacional que aceita upload (só a 12), ou None."""
    op = ETAPAS_OPERACIONAIS.get(codigo)
    return op.get("tipo_doc") if op else None


def _tem_linha_nao_vazia(texto):
    return any(linha.strip() for linha in (texto or "").splitlines())


def guarda_conclusao_operacional(codigo, tem_xml, numeros_txt, relatorio_txt):
    """(ok, erro) para concluir uma etapa operacional (12/13/14).
    tem_xml: bool (existe ao menos um XML na etapa 12).
    numeros_txt / relatorio_txt: texto de observacoes da etapa 13 / 14."""
    op = ETAPAS_OPERACIONAIS.get(codigo)
    if not op:
        return (False, "Etapa operacional desconhecida.")
    exige = op["exige"]
    if exige == "xml" and not tem_xml:
        return (False, "Carregue pelo menos um pedido (XML) antes de encaminhar à fábrica.")
    if exige == "numeros" and not _tem_linha_nao_vazia(numeros_txt):
        return (False, "Informe os números dos pedidos antes de concluir a produção.")
    if exige == "relatorio" and not (relatorio_txt or "").strip():
        return (False, "Preencha o Relatório de Entrega antes de concluí-lo.")
    return (True, "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ciclo.py -q -k "operacional"`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_ciclo.py tests/test_ciclo.py
git commit -m "feat(ciclo): guardas puras das etapas operacionais 12/13/14 em mod_ciclo"
```

---

## Task 2: Endpoint de upload dos XMLs (etapa 12) + listagem

**Files:**
- Modify: `main.py` — POST em `do_POST` (após o bloco do `documento` do PE, ~linha 3810); GET em `do_GET` (após o bloco `GET /ciclo/pe`, ~linha 1386)
- Test: `tests/test_ciclo_operacional_e2e.py` (novo)

- [ ] **Step 1: Write the failing test**

Criar `tests/test_ciclo_operacional_e2e.py`:

```python
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
    `app_db` são module-scoped → o estado vaza entre testes do mesmo arquivo; cada
    teste que asserta estado deve montar exatamente o seu."""
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
    # etapa 13 não aceita upload de pedido (tipo_doc_operacional -> None)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ciclo_operacional_e2e.py -q -k "upload"`
Expected: FAIL (rotas ainda não existem → 404, asserts quebram).

- [ ] **Step 3: Write the POST endpoint**

Em `main.py`, no método `do_POST`, logo **após** o bloco `POST .../ciclo/<codigo>/documento` (termina em `return` na ~linha 3810), inserir:

```python
            # POST /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — upload XML da etapa
            # operacional (12), append-only, CYCLE-GATED (sem capability de PE).
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo_esperado = mod_ciclo.tipo_doc_operacional(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Esta etapa não aceita upload de pedidos."}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo XML."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", usuario["id"])
                    db.add(LogAcaoGerencial(solicitante_id=usuario["id"], autorizador_id=usuario["id"],
                            acao="ciclo_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Write the GET listing endpoint**

Em `main.py`, no método `do_GET`, logo **após** o bloco `GET .../ciclo/documento/<id>` (~linha 1386, antes do próximo `m = ...`), inserir:

```python
            # GET /api/projetos/<nome>/ciclo/<codigo>/pedido-xml — lista os XMLs da etapa operacional (12)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/pedido-xml$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    tipo = mod_ciclo.tipo_doc_operacional(codigo)
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo)
                              .order_by(CicloDocumento.enviado_em.desc()).all()) if tipo else []
                    out = [{"id": d.id, "nome_original": d.nome_original,
                            "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None} for d in docs]
                    self.send_json({"ok": True, "documentos": out})
                finally:
                    db.close()
                return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ciclo_operacional_e2e.py -q -k "upload"`
Expected: PASS (5 testes).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_ciclo_operacional_e2e.py
git commit -m "feat(ciclo): endpoint de upload/listagem de XML da etapa 12 (cycle-gated, append-only)"
```

---

## Task 3: Guarda operacional no `PATCH /ciclo/<codigo>`

**Files:**
- Modify: `main.py:4225` — inserir guarda antes do bloco `# Aprovação financeira (8/11d)`
- Test: `tests/test_ciclo_operacional_e2e.py` (adicionar)

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_ciclo_operacional_e2e.py` (os helpers `_reset_etapas`/`_marcar_concluida` já
foram definidos no bloco do Task 2). **Cada teste reseta as etapas que toca**, porque `seed`/`app_db`
são module-scoped e o estado vaza entre testes do mesmo arquivo:

```python
def test_12_nao_conclui_sem_xml_e_conclui_com_xml(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["11", "12"])
    _marcar_concluida(app_db, proj, "11")   # libera o gating sequencial da 12
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/12", {"status": "concluido"})
    assert st == 400 and "XML" in body["erro"], body
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/12/pedido-xml", {},
                    file_field="arquivo", filename="p.xml", filedata=b"<xml/>")
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/12", {"status": "concluido"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_13_nao_conclui_sem_numeros_e_conclui_com_numeros(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])
    _marcar_concluida(app_db, proj, "12")   # libera a 13
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13", {"status": "concluido"})
    assert st == 400 and "número" in body["erro"].lower(), body
    # salva números via PATCH observacoes (sem status)
    st_s, _ = c.patch(f"/api/projetos/{proj}/ciclo/13", {"observacoes": "P-1001\nP-1002"})
    assert st_s == 200
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/13", {"status": "concluido"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_13_conclui_com_numeros_no_mesmo_patch(http_client_factory, seed, projetos_dir, app_db):
    # números enviados JUNTO com o status devem satisfazer a guarda
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])
    _marcar_concluida(app_db, proj, "12")
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13",
                       {"status": "concluido", "observacoes": "P-9"})
    assert st == 200 and body.get("ok") is True, body


def test_14_nao_conclui_sem_relatorio_e_conclui_com_relatorio(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["13", "14"])
    _marcar_concluida(app_db, proj, "13")   # libera a 14
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/14", {"status": "concluido", "observacoes": "   "})
    assert st == 400 and "Relatório" in body["erro"], body
    st2, body2 = c.patch(f"/api/projetos/{proj}/ciclo/14",
                         {"status": "concluido", "observacoes": "1 gaveta avariada"})
    assert st2 == 200 and body2.get("ok") is True, body2


def test_gating_sequencial_preservado_13_sem_12(http_client_factory, seed, projetos_dir, app_db):
    # sem concluir a 12, a 13 não avança (gating sequencial existente, mensagem da etapa anterior)
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["12", "13"])   # garante 12 NÃO concluída
    st, body = c.patch(f"/api/projetos/{proj}/ciclo/13",
                       {"status": "concluido", "observacoes": "P-1"})
    assert st == 400 and "anterior" in body["erro"].lower(), body


def test_pe_intocado_smoke(http_client_factory, seed, projetos_dir, app_db):
    # a guarda operacional não afeta o PE: upload+concluir 11a segue funcionando
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _reset_etapas(app_db, proj, ["11a"])
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="p.pdf", filedata=b"x")
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11a/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 200 and body.get("ok") is True, body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_ciclo_operacional_e2e.py -q -k "conclui or gating or intocado"`
Expected: FAIL nos testes `12/13/14` (hoje a etapa conclui sem guarda → o teste de "não conclui" recebe 200 em vez de 400). `gating_sequencial` e `pe_intocado` já devem passar (comportamento existente).

- [ ] **Step 3: Write the guard in the PATCH handler**

Em `main.py`, dentro do bloco `PATCH /ciclo/<codigo>` (após o bloco de gating sequencial que termina na ~linha 4224, e **antes** do comentário `# Aprovação financeira (8/11d): ...` na ~linha 4225), inserir:

```python
                    # Guarda das etapas operacionais (12/13/14): exige XML / números /
                    # relatório antes de concluir. Usa o obs recebido no request (se veio
                    # junto do status) ou o persistido na etapa.
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in mod_ciclo.ETAPAS_OPERACIONAIS:
                        tem_xml = db.query(CicloDocumento).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="12",
                            tipo=mod_ciclo.tipo_doc_operacional("12")).first() is not None
                        obs_efetivo   = obs if obs is not None else etapa.observacoes
                        numeros_txt   = obs_efetivo if etapa_cod == "13" else None
                        relatorio_txt = obs_efetivo if etapa_cod == "14" else None
                        ok_op, erro_op = mod_ciclo.guarda_conclusao_operacional(
                            etapa_cod, tem_xml, numeros_txt, relatorio_txt)
                        if not ok_op:
                            self.send_json({"ok": False, "erro": erro_op}, code=400)
                            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_ciclo_operacional_e2e.py -q`
Expected: PASS (todos, incl. Task 2).

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest -q`
Expected: verde (baseline 414 + os novos). A falha pré-existente do weasyprint pode aparecer só se o ambiente não tiver a lib; ignorar se for exatamente essa.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_ciclo_operacional_e2e.py
git commit -m "feat(ciclo): guarda operacional na conclusao das etapas 12/13/14 (PATCH /ciclo)"
```

---

## Task 4: Frontend — painéis das etapas 12/13/14

**Files:**
- Modify: `static/index.html` — estado `_pedidosXml` + loader (~linha 7556-7564, junto do PE); carregamento no `carregarCiclo` (~linha 7617); roteamento (~linha 7790-7792); 3 funções de render + handlers (junto das funções `_renderCardPE`/`peUpload`, ~linha 8470+).

Sem teste JS → verificação por `node --check` + manual no navegador.

- [ ] **Step 1: Add state + loader (junto do bloco do PE, após `peCarregar`, ~linha 7564)**

```javascript
// ── Etapas operacionais (12 Implantação) — lista de XMLs carregados ────────
let _pedidosXml = [];   // [{id, nome_original, enviado_em}]

async function pedidosXmlCarregar(nomeSafe) {
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafe)}/ciclo/12/pedido-xml`,
                          { credentials: 'same-origin' });
    const j = await r.json();
    _pedidosXml = (j && j.ok) ? (j.documentos || []) : [];
  } catch(e) { _pedidosXml = []; }
}
```

- [ ] **Step 2: Load it in `carregarCiclo` (após `await peCarregar(...)`, ~linha 7617)**

Trocar a linha:

```javascript
    if (projetoAtivo) await peCarregar(projetoAtivo.nome_safe);
```

por:

```javascript
    if (projetoAtivo) await peCarregar(projetoAtivo.nome_safe);
    if (projetoAtivo) await pedidosXmlCarregar(projetoAtivo.nome_safe);
```

- [ ] **Step 3: Route stages 12/13/14 to dedicated panels (bloco de escolha do card, ~linha 7790)**

Trocar:

```javascript
          : PE_SUBFASES[etapa.codigo]
            ? _renderCardPE(etapa.codigo, dados, bloqueada)
            : _renderCardGenerico(etapa, dados, bloqueada)}
```

por:

```javascript
          : PE_SUBFASES[etapa.codigo]
            ? _renderCardPE(etapa.codigo, dados, bloqueada)
          : etapa.codigo === '12'
            ? _renderCardImplantacao(dados, bloqueada)
          : etapa.codigo === '13'
            ? _renderCardProducao(dados, bloqueada)
          : etapa.codigo === '14'
            ? _renderCardEntrega(dados, bloqueada)
            : _renderCardGenerico(etapa, dados, bloqueada)}
```

- [ ] **Step 4: Add the 3 render functions + handlers (junto de `peUpload`, ~linha 8470)**

```javascript
// ── Etapa 12 — Implantação do pedido ───────────────────────────────────────
function _renderCardImplantacao(dados, bloqueada) {
  const concluido = dados.status === 'concluido';
  const dt = dados.concluido_em ? new Date(dados.concluido_em).toLocaleDateString('pt-BR') : '';
  if (bloqueada) {
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior para liberar esta etapa.</p>`;
  }
  const lista = (_pedidosXml && _pedidosXml.length)
    ? _pedidosXml.map(d => `
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px;font-size:.82rem">
          <span style="flex:1">📄 ${esc(d.nome_original)}</span>
          <a class="btn-ciclo" style="font-size:.78rem;text-decoration:none" target="_blank" rel="noopener"
             href="/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/documento/${d.id}">Baixar</a>
        </div>`).join('')
    : `<p style="color:var(--muted);font-size:.82rem;margin:0 0 8px">Nenhum pedido (XML) carregado.</p>`;
  const btnReabrir = concluido
    ? `<button onclick="abrirModalReabrir('12')" style="border:1px solid var(--muted);color:var(--muted);background:none;border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer">🔓 Reabrir (gerente)</button>`
    : '';
  return `
    <div style="margin-bottom:10px">${lista}</div>
    ${concluido
      ? `<p style="color:var(--ok);margin:0 0 10px">✓ Pedidos encaminhados à fábrica${dt ? ' em ' + dt : ''}.</p>${btnReabrir}`
      : `<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
           <label class="btn-ciclo" style="font-size:.82rem;cursor:pointer">
             📎 Carregar Pedidos
             <input type="file" accept=".xml" multiple style="display:none" onchange="enviarPedidosXml(this)">
           </label>
           <button onclick="encaminharPedidosFabrica()" ${_pedidosXml.length ? '' : 'disabled'}
             style="background:${_pedidosXml.length ? 'var(--dalm-gold)' : 'var(--muted)'};color:#1a1200;border:none;font-weight:700;border-radius:5px;padding:7px 16px;font-size:.82rem;cursor:${_pedidosXml.length ? 'pointer' : 'not-allowed'}">
             Encaminhar Pedidos à Fábrica</button>
         </div>`}`;
}

async function enviarPedidosXml(inputFile) {
  if (!projetoAtivo) return;
  const files = Array.from(inputFile.files || []);
  if (!files.length) return;
  try {
    for (const f of files) {
      const fd = new FormData();
      fd.append('arquivo', f);
      const r = await fetch(
        `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/12/pedido-xml`,
        { method: 'POST', credentials: 'same-origin', body: fd });
      const j = await r.json();
      if (!j.ok) { await avisoPopup(j.erro || 'Falha ao carregar.', {titulo:'Implantação — Upload'}); break; }
    }
    showToast('Pedido(s) carregado(s)!', false);
    await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Implantação — Upload'}); }
}

async function encaminharPedidosFabrica() {
  if (!projetoAtivo) return;
  try {
    const r = await fetch(
      `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/12`,
      { method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'concluido' }) });
    const d = await r.json();
    if (!d.ok) { await avisoPopup(d.erro || 'Falha ao encaminhar.', {titulo:'Implantação'}); return; }
    showToast('Pedidos encaminhados à fábrica!', false);
    await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Implantação'}); }
}

// ── Etapa 13 — Produção ────────────────────────────────────────────────────
function _renderCardProducao(dados, bloqueada) {
  const concluido = dados.status === 'concluido';
  const dt = dados.concluido_em ? new Date(dados.concluido_em).toLocaleDateString('pt-BR') : '';
  if (bloqueada) {
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior para liberar esta etapa.</p>`;
  }
  const btnReabrir = concluido
    ? `<button onclick="abrirModalReabrir('13')" style="border:1px solid var(--muted);color:var(--muted);background:none;border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer;margin-left:8px">🔓 Reabrir (gerente)</button>`
    : '';
  return `
    <p style="color:var(--muted);font-size:.82rem;margin:0 0 6px">Números dos pedidos (um por linha) — resultado da implantação na fábrica.</p>
    <textarea id="numeros-etapa-13" ${concluido ? 'disabled' : ''}
      placeholder="Ex.: P-1001&#10;P-1002"
      style="width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text);font-size:.82rem;resize:vertical;min-height:64px">${esc(dados.observacoes || '')}</textarea>
    ${concluido
      ? `<p style="color:var(--ok);margin:8px 0 0">✓ Produção concluída${dt ? ' em ' + dt : ''}.${btnReabrir}</p>`
      : `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
           <button onclick="salvarNumerosPedidos()" class="btn-ciclo" style="font-size:.82rem">💾 Salvar Números dos Pedidos</button>
           <button onclick="producaoConcluida()"
             style="background:var(--dalm-gold);color:#1a1200;border:none;font-weight:700;border-radius:5px;padding:7px 16px;font-size:.82rem;cursor:pointer">Produção Concluída</button>
         </div>`}`;
}

async function _patchEtapa(codigo, payload, okMsg, titulo) {
  if (!projetoAtivo) return false;
  try {
    const r = await fetch(
      `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/${encodeURIComponent(codigo)}`,
      { method: 'PATCH', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload) });
    const d = await r.json();
    if (!d.ok) { await avisoPopup(d.erro || 'Falha.', {titulo}); return false; }
    showToast(okMsg, false);
    await carregarCiclo();
    return true;
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo}); return false; }
}

async function salvarNumerosPedidos() {
  const txt = document.getElementById('numeros-etapa-13')?.value || '';
  await _patchEtapa('13', { observacoes: txt }, 'Números salvos.', 'Produção');
}

async function producaoConcluida() {
  const txt = document.getElementById('numeros-etapa-13')?.value || '';
  await _patchEtapa('13', { status: 'concluido', observacoes: txt }, 'Produção concluída!', 'Produção');
}

// ── Etapa 14 — Entrega no depósito ─────────────────────────────────────────
function _renderCardEntrega(dados, bloqueada) {
  const concluido = dados.status === 'concluido';
  const dt = dados.concluido_em ? new Date(dados.concluido_em).toLocaleDateString('pt-BR') : '';
  if (bloqueada) {
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior para liberar esta etapa.</p>`;
  }
  const btnReabrir = concluido
    ? `<button onclick="abrirModalReabrir('14')" style="border:1px solid var(--muted);color:var(--muted);background:none;border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer;margin-left:8px">🔓 Reabrir (gerente)</button>`
    : '';
  return `
    <p style="color:var(--muted);font-size:.82rem;margin:0 0 6px">Relatório de Entrega — descreva faltas e avarias.</p>
    <textarea id="relatorio-etapa-14" ${concluido ? 'disabled' : ''}
      placeholder="Ex.: 1 gaveta avariada; falta 1 puxador…"
      style="width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text);font-size:.82rem;resize:vertical;min-height:80px">${esc(dados.observacoes || '')}</textarea>
    ${concluido
      ? `<p style="color:var(--ok);margin:8px 0 0">✓ Relatório de Entrega concluído${dt ? ' em ' + dt : ''}.${btnReabrir}</p>`
      : `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
           <button onclick="salvarRelatorioEntrega()" class="btn-ciclo" style="font-size:.82rem">💾 Salvar Relatório de Entrega</button>
           <button onclick="concluirRelatorioEntrega()"
             style="background:var(--dalm-gold);color:#1a1200;border:none;font-weight:700;border-radius:5px;padding:7px 16px;font-size:.82rem;cursor:pointer">Concluir Relatório de Entrega</button>
         </div>`}`;
}

async function salvarRelatorioEntrega() {
  const txt = document.getElementById('relatorio-etapa-14')?.value || '';
  await _patchEtapa('14', { observacoes: txt }, 'Relatório salvo.', 'Entrega no depósito');
}

async function concluirRelatorioEntrega() {
  const txt = document.getElementById('relatorio-etapa-14')?.value || '';
  await _patchEtapa('14', { status: 'concluido', observacoes: txt }, 'Relatório de Entrega concluído!', 'Entrega no depósito');
}
```

- [ ] **Step 5: Remove the `toggleavel` from stage 14 (evita botão genérico duplicado)**

Em `ETAPAS_CICLO` (~linha 7520), trocar:

```javascript
  { codigo: "14",  nome: "Entrega no depósito",                sub: false, toggleavel: true },
```

por:

```javascript
  { codigo: "14",  nome: "Entrega no depósito",                sub: false },
```

(O roteamento já manda a 14 para `_renderCardEntrega`; remover `toggleavel` evita qualquer resíduo do card genérico.)

- [ ] **Step 6: Syntax-check the inline script**

Extrair o `<script>` e rodar `node --check`:

```bash
python3 - <<'PY'
import re
html = open('static/index.html', encoding='utf-8').read()
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
big = max(scripts, key=len)
open('/tmp/_orizon_check.js','w',encoding='utf-8').write(big)
print('script extraído:', len(big), 'chars')
PY
node --check /tmp/_orizon_check.js && echo "OK sintaxe"
```

Expected: `OK sintaxe`.

- [ ] **Step 7: Commit**

```bash
git add static/index.html
git commit -m "feat(ciclo): paineis das etapas 12/13/14 no frontend (Implantacao/Producao/Entrega)"
```

---

## Task 5: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md` — nova `## Sessão N` + atualizar `⏸️ ESTADO ATUAL`
- Modify: `docs/superpowers/specs/ciclo/2026-07-05-etapas-operacionais-implantacao-producao-entrega-design.md` — cabeçalho `Status: IMPLEMENTADO`

- [ ] **Step 1: Run the full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Update spec header**

Trocar a linha `> Status: **APROVADO (brainstorming)** — a implementar.` por
`> Status: **IMPLEMENTADO (Sessão N)** — backend com testes; frontend com verificação manual pendente no navegador.`
(usar o número real da próxima sessão).

- [ ] **Step 3: Add DEV_LOG session + update ESTADO ATUAL**

Adicionar `## Sessão N — Etapas operacionais 12/13/14 (branch feat/etapas-operacionais)` com: escopo (upload de XML append-only na 12; números da fábrica na 13; relatório de faltas/avarias na 14), decisões (abordagem C, sem tabela/capability nova, cycle-gated), endpoints (`POST/GET .../ciclo/<codigo>/pedido-xml`; guarda no `PATCH /ciclo`), testes (`test_ciclo.py` + `test_ciclo_operacional_e2e.py`), e o pendente (verificação manual + merge/push/re-ingestão). Atualizar a seção `⏸️ ESTADO ATUAL`.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/ciclo/2026-07-05-etapas-operacionais-implantacao-producao-entrega-design.md
git commit -m "docs(ciclo): DEV_LOG sessao N + spec das etapas operacionais como implementado"
```

- [ ] **Step 5: Verificação manual no navegador (antes do merge)**

Restart do servidor (`python3 main.py`) + Ctrl+F5. Num projeto com a etapa 11 concluída:
- **12:** "Carregar Pedidos" aceita `.xml` (múltiplos), lista aparece com "Baixar"; "Encaminhar à Fábrica" desabilitado sem XML, habilita com XML e fecha a etapa.
- **13:** textarea de números; "Produção Concluída" barra sem números e conclui com números; números persistem ao reabrir o card.
- **14:** textarea do relatório; "Concluir Relatório de Entrega" barra vazio e conclui com texto.
- **Reabrir (gerente)** volta cada etapa; gating sequencial (13 exige 12; 14 exige 13) respeitado.

Depois: fechar a frente (finishing-a-development-branch) → merge/push/re-ingestão.

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §3 dados (Task 1 tipos + Task 2 CicloDocumento + observacoes via PATCH), §4.1 mod_ciclo (Task 1), §4.2 endpoints (Task 2) + guarda no PATCH (Task 3), §5 frontend (Task 4), §6 testes (Tasks 1-3), §7 fora de escopo (respeitado — sem parsing de XML, sem capability nova, texto livre).
- **Consistência de tipos:** `tipo_doc_operacional`, `guarda_conclusao_operacional`, `ETAPAS_OPERACIONAIS` usados com a mesma assinatura em mod_ciclo, main.py e testes. Campo `tipo="implantacao_pedido_xml"` idêntico no POST, no GET e no filtro da guarda. Funções de front (`_renderCardImplantacao/Producao/Entrega`, `enviarPedidosXml`, `encaminharPedidosFabrica`, `salvarNumerosPedidos`, `producaoConcluida`, `salvarRelatorioEntrega`, `concluirRelatorioEntrega`, `_patchEtapa`, `pedidosXmlCarregar`, estado `_pedidosXml`) referenciadas de forma consistente entre render e handlers.
- **Sem placeholders:** todo passo com código tem o código completo.
```
