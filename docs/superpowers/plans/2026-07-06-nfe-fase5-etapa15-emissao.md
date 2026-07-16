# NF-e Fase 5 — Etapa 15 (Emissão da NF-e do cliente) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operar a emissão da NF-e da loja na **etapa 15** por projeto: upload da NF-e da fábrica → preview+markup → emitir (Focus, homologação) → acompanhar → baixar XML/DANFE, com painel dedicado no ciclo.

**Architecture:** Reusa todo o pipeline (Fases 1-4). Adiciona `NfeEmissao.fabrica_doc_id` (liga emissão↔XML da fábrica), ajusta `nfe_emissao.emitir` (param + regra de homologação), 5 endpoints por projeto em `/api/projetos/<nome>/ciclo/15/…` (gated por `editar_dados_loja`+escopo do projeto) e um painel dedicado na etapa 15. Backend e2e-testável (emissor mockado); painel por verificação manual.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML+JS inline. Reusa `mod_nfe`/`mapa_fiscal`/`nfe_emissao`/`emissor_fiscal`/`PerfilFiscal`/`CicloDocumento`.

**Base para ler antes:** spec `docs/superpowers/specs/fiscal/2026-07-06-nfe-fase5-etapa15-emissao-design.md`. Padrão de upload append-only por projeto: o handler `POST …/ciclo/12/pedido-xml` em `main.py` (usa `get_usuario_sessao`, `_parse_multipart_arquivos`, `_ator_dict`, `mod_tenancy.escopo_operacional(ator)`, `_projeto_da_loja(db, nome, loja_id)`, `CicloDocumento`, `_set_etapa_status`, `storage_salvar_binario`, `_projeto_path`). Leitura de doc: handler `GET …/ciclo/documento/<id>` (`storage_ler_binario(os.path.join(_projeto_path(nome_safe), doc.arquivo_path))`). Migração de coluna: `database._run_migracoes` (padrão `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`, ex. clientes/usuarios). Serviço: `nfe_emissao.emitir(db, loja_id, projeto_nome, nota, permitir_producao=False, emissor=None)` (Fase 4). Frontend: painéis das etapas 12/13/14 (`_renderCardImplantacao` etc., roteados em `renderCiclo`), helper `esc`, `showToast`, `avisoPopup`, `pedirCredenciaisGerente`. Capacidade `editar_dados_loja` em `perfis.pode(nivel, "editar_dados_loja")`.

**Lembrete de ambiente:** modelos/endpoints Python → **restart** para verificação manual; a suíte e2e sobe o próprio servidor. Baseline **519 passed**. `python3` do Bash pode ser o stub WindowsApps (usar o interpretador real; ver DEV_LOG). Frontend é lido do disco a cada request (Ctrl+F5). `node` indisponível → checagem estrutural do script.

---

## File Structure

- **Modify** `database.py` — coluna `NfeEmissao.fabrica_doc_id` + migração idempotente em `_run_migracoes`.
- **Modify** `nfe_emissao.py` — `emitir(..., fabrica_doc_id=None)` + regra de nome SEFAZ do destinatário em homologação.
- **Modify** `main.py` — 5 endpoints `/api/projetos/<nome>/ciclo/15/…`.
- **Modify** `static/index.html` — painel dedicado da etapa 15 + handlers + roteamento.
- **Modify** `tests/test_nfe_emissao_model.py`, `tests/test_nfe_emissao.py`; **Create** `tests/test_nfe_etapa15_e2e.py`.

---

## Task 1: `NfeEmissao.fabrica_doc_id` + migração + `emitir` (param + regra homologação)

**Files:**
- Modify: `database.py`, `nfe_emissao.py`
- Modify: `tests/test_nfe_emissao_model.py`, `tests/test_nfe_emissao.py`

- [ ] **Step 1: Write the failing tests**

Em `tests/test_nfe_emissao_model.py`, no `test_modelo_nfe_emissao`, adicionar `fabrica_doc_id=7` na criação e assertir:

```python
    e = database.NfeEmissao(ref="TESTE-1", projeto_nome="Proj_L2", loja_id=1, fabrica_doc_id=7,
                            status="autorizado", chave_nfe="CH", numero="10", serie="1")
```
e após reler:
```python
    assert lido.fabrica_doc_id == 7
```

Em `tests/test_nfe_emissao.py`, alterar a `FakeEmissor` para capturar a nota (adicionar no `__init__`:
`self.nota_recebida = None` e em `emitir_nfe_produto`: `self.nota_recebida = nota` na 1ª linha). Depois
adicionar dois testes ao final:

```python
def test_emitir_grava_fabrica_doc_id(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F1", proj); _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F1"), emissor=FakeEmissor(), fabrica_doc_id=99)
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-F1").first()
    assert reg.fabrica_doc_id == 99
    db.close()


def test_emitir_homologacao_forca_nome_dest_sefaz(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-F2", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-F2"), emissor=fake)
    assert fake.nota_recebida["destinatario"]["nome"] == \
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    db.close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_emissao_model.py tests/test_nfe_emissao.py -q -k "fabrica or homologacao_forca"`
Expected: FAIL (`fabrica_doc_id` não existe no modelo; nome do dest não é forçado).

- [ ] **Step 3: Add the column + migration to `database.py`**

No modelo `NfeEmissao`, adicionar (após `danfe_doc_id`):
```python
    fabrica_doc_id = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
```

Em `_run_migracoes(conn)` (junto das outras migrações `PRAGMA table_info`/`ALTER TABLE`), adicionar:
```python
        cur.execute("PRAGMA table_info(nfe_emissao)")
        nfe_cols = [r[1] for r in cur.fetchall()]
        if nfe_cols and "fabrica_doc_id" not in nfe_cols:
            cur.execute("ALTER TABLE nfe_emissao ADD COLUMN fabrica_doc_id INTEGER")
```
(O `if nfe_cols` garante que a tabela existe — em banco novo o `create_all` já criou a coluna, então a
migração é no-op; em banco antigo ela adiciona.)

- [ ] **Step 4: Update `nfe_emissao.emitir`**

Adicionar a constante (topo do módulo, junto dos `_TIPO_*`):
```python
_NOME_DEST_HOMOLOG = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
```

Trocar a assinatura e adicionar a regra de homologação + o `fabrica_doc_id` no upsert:
```python
def emitir(db, loja_id, projeto_nome, nota, permitir_producao=False, emissor=None, fabrica_doc_id=None):
    """Emite (ou devolve idempotente), acompanha até o status final e guarda XML/DANFE."""
    ref = nota["ref"]
    reg = db.query(NfeEmissao).filter_by(ref=ref).first()
    if reg and reg.status == "autorizado":
        return _resultado_de_registro(reg)
    pf = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
    ambiente = (pf.ambiente_ativo if pf else "homologacao") or "homologacao"
    if ambiente == "producao" and not permitir_producao:
        raise ValueError("Emissão em produção bloqueada (use permitir_producao=True).")
    if ambiente == "homologacao":
        nota["destinatario"]["nome"] = _NOME_DEST_HOMOLOG   # regra SEFAZ homologação
    if emissor is None:
        emissor = _emissor_para(db, loja_id)
    res = emissor.emitir_nfe_produto(nota)
    if res.status == StatusNota.PROCESSANDO:
        res = resultado_de_focus(emissor.client.aguardar_processamento(ref))
    if not reg:
        reg = NfeEmissao(ref=ref, projeto_nome=projeto_nome, loja_id=loja_id, etapa_codigo="15",
                         fabrica_doc_id=fabrica_doc_id)
        db.add(reg)
    _aplicar_resultado(reg, res)
    if res.status == StatusNota.AUTORIZADO:
        _guardar_docs_autorizado(db, reg, res, emissor.client)
    db.commit()
    return res
```

- [ ] **Step 5: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_emissao_model.py tests/test_nfe_emissao.py -q`
Expected: PASS (model + os 9 do serviço, incl. os 2 novos). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 6: Commit**

```bash
git add database.py nfe_emissao.py tests/test_nfe_emissao_model.py tests/test_nfe_emissao.py
git commit -m "feat(nfe): NfeEmissao.fabrica_doc_id + emitir(fabrica_doc_id) + nome SEFAZ homologacao"
```

---

## Task 2: endpoints `nfe-fabrica` (upload) + `GET nfe` (estado)

**Files:**
- Modify: `main.py` (do_POST: upload; do_GET: estado)
- Test: `tests/test_nfe_etapa15_e2e.py` (novo)

- [ ] **Step 1: Create the e2e test (upload + GET)**

Criar `tests/test_nfe_etapa15_e2e.py`:

```python
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
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.add(app_db.PerfilFiscal(loja_id=loja_id, ambiente_ativo=ambiente, razao_social="LOJA X",
                               csosn_padrao="102", cfop_dentro_uf="5102", cfop_fora_uf="6102"))
    db.commit(); db.close()


def _reset15(app_db, proj):
    db = app_db.get_session()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.query(app_db.NfeEmissao).filter_by(projeto_nome=proj).delete()
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
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_etapa15_e2e.py -q -k "upload or estado or 401"`
Expected: FAIL (rotas 404).

- [ ] **Step 3: Add the upload endpoint in `do_POST`**

Inserir (usar `_re` como os blocos vizinhos; espelha o `pedido-xml` da etapa 12, **com** o gate fiscal):

```python
            # POST /api/projetos/<nome>/ciclo/15/nfe-fabrica — upload da NF-e da fábrica (append-only)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe-fabrica$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da NF-e da fábrica."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", "15", unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=usuario["id"])
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo="15").first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, "15", "em_andamento", usuario["id"])
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Add the GET estado endpoint in `do_GET`**

Inserir (antes do fallback 404 do do_GET; usar `_re`). Import `NfeEmissao` no topo do main se ainda não
estiver na linha `from database import (...)`:

```python
            # GET /api/projetos/<nome>/ciclo/15/nfe — estado da etapa 15 (XMLs da fábrica + emissões)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    docs = (db.query(CicloDocumento)
                              .filter_by(projeto_nome=nome_safe, etapa_codigo="15", tipo="nfe_fabrica_xml")
                              .order_by(CicloDocumento.enviado_em.desc()).all())
                    emissoes = {e.fabrica_doc_id: e for e in
                                db.query(NfeEmissao).filter_by(projeto_nome=nome_safe).all()
                                if e.fabrica_doc_id is not None}
                    out = []
                    for d in docs:
                        e = emissoes.get(d.id)
                        emissao = None if not e else {
                            "ref": e.ref, "status": e.status, "chave": e.chave_nfe, "numero": e.numero,
                            "serie": e.serie, "mensagem_sefaz": e.mensagem_sefaz,
                            "erros": json.loads(e.erros_json) if e.erros_json else [],
                            "xml_doc_id": e.xml_doc_id, "danfe_doc_id": e.danfe_doc_id}
                        out.append({"id": d.id, "nome_original": d.nome_original,
                                    "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                    "emissao": emissao})
                    self.send_json({"ok": True, "fabrica_xmls": out})
                finally:
                    db.close()
                return
```

- [ ] **Step 5: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_etapa15_e2e.py -q -k "upload or estado or 401"`
Expected: PASS (3). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_nfe_etapa15_e2e.py
git commit -m "feat(nfe): etapa 15 upload da NF-e da fabrica + GET estado (gated fiscal)"
```

---

## Task 3: endpoints `emitir-nfe` + `consultar` + `cancelar`

**Files:**
- Modify: `main.py` (do_POST)
- Test: `tests/test_nfe_etapa15_e2e.py` (adicionar)

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_nfe_etapa15_e2e.py`:

```python
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
    # etapa 15 concluída (emitida)
    db = app_db.get_session()
    et = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="15").first()
    assert et.status == "emitida"
    # GET nfe agora mostra a emissão
    db.close()
    st2, g = c.get(f"/api/projetos/{proj}/ciclo/15/nfe")
    assert g["fabrica_xmls"][0]["emissao"]["status"] == "autorizado"
    # idempotência: reemitir devolve a mesma (não muda)
    st3, b3 = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc_id, "markup_pct": 30})
    assert st3 == 200 and b3["ref"] == b["ref"]


def test_emitir_etapa15_sem_perfil_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    proj = seed["projeto_l2"]
    _reset15(app_db, proj)
    db = app_db.get_session(); db.query(app_db.PerfilFiscal).filter_by(loja_id=seed["loja2_id"]).delete(); db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    _, up = _upload_xml(c, proj, _fixture_xml()) if False else (None, {"documento_id": 0})
    # cria um doc de fábrica direto p/ isolar o 400 do perfil
    dbx = app_db.get_session()
    d = app_db.CicloDocumento(projeto_nome=proj, etapa_codigo="15", tipo="nfe_fabrica_xml",
                              arquivo_path="ciclo/15/x.xml", nome_original="x.xml")
    dbx.add(d); dbx.commit(); did = d.id; dbx.close()
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": did, "markup_pct": 30})
    assert st == 400 and "perfil" in b.get("erro", "").lower()


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
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_etapa15_e2e.py -q -k "emitir_etapa15 or consultar_e_cancelar"`
Expected: FAIL (rotas 404).

- [ ] **Step 3: Add the three endpoints in `do_POST`**

Inserir (usar `_re`; garantir `mod_nfe`, `mapa_fiscal`, `nfe_emissao` importados no bloco):

```python
            # POST /api/projetos/<nome>/ciclo/15/emitir-nfe — emite a NF-e da loja
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/emitir-nfe$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import mod_nfe, mapa_fiscal, nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    projeto = _projeto_da_loja(db, nome_safe, loja_id)
                    if projeto is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    loja = db.get(Loja, loja_id)
                    perfil = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
                    if not perfil:
                        self.send_json({"ok": False, "erro": "Configure o Perfil Fiscal da loja antes de emitir."}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    doc_id = req.get("fabrica_doc_id")
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe,
                                                             etapa_codigo="15", tipo="nfe_fabrica_xml").first() if doc_id else None
                    if not doc:
                        self.send_json({"ok": False, "erro": "XML da fábrica inválido."}, code=400); return
                    try:
                        markup = float(req.get("markup_pct") or 0)
                    except (TypeError, ValueError):
                        markup = 0.0
                    xml_bytes = storage_ler_binario(os.path.join(_projeto_path(nome_safe), doc.arquivo_path))
                    preview = mod_nfe.preview(xml_bytes, markup)
                    ref = "NFE-" + nome_safe + "-" + str(doc.id)
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(perfil, loja, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, fabrica_doc_id=doc.id)
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                    reg = db.query(NfeEmissao).filter_by(ref=ref).first()
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value, "chave": res.chave, "numero": res.numero,
                                    "serie": res.serie, "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": reg.xml_doc_id if reg else None,
                                    "danfe_doc_id": reg.danfe_doc_id if reg else None})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/consultar — reconsulta status
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/consultar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.consultar(db, req.get("ref"))
                    if res.status.value == "autorizado":
                        _set_etapa_status(db, nome_safe, "15", "emitida", usuario["id"]); db.commit()
                    self.send_json({"ok": True, "status": res.status.value, "chave": res.chave,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return

            # POST /api/projetos/<nome>/ciclo/15/nfe/cancelar — cancela a NF-e
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/15/nfe/cancelar$', path)
            if m:
                nome_safe = unquote(m.group(1))
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                if not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                import nfe_emissao
                try:
                    req = json.loads(body) if body else {}
                except Exception:
                    self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    res = nfe_emissao.cancelar(db, req.get("ref"), req.get("justificativa") or "")
                    self.send_json({"ok": True, "status": res.status.value, "mensagem_sefaz": res.mensagem_sefaz})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha: " + str(e)}, code=500)
                finally:
                    db.close()
                return
```

Confirmar que `Loja`, `Cliente`, `PerfilFiscal`, `NfeEmissao`, `CicloDocumento`, `CicloEtapa` estão
importados no topo do `main.py` (`from database import (...)`); adicionar os que faltarem.
`cancelar_nfe` do FocusClient exige justificativa 15-255 chars — o teste usa uma frase longa; a UI deve
validar. `nfe_emissao.cancelar` repassa direto.

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_etapa15_e2e.py -q`
Expected: PASS (6). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_nfe_etapa15_e2e.py
git commit -m "feat(nfe): etapa 15 emitir-nfe + consultar + cancelar (conclui em emitida, idempotente)"
```

---

## Task 4: painel da etapa 15 no frontend

**Files:**
- Modify: `static/index.html`

Sem teste JS → checagem estrutural (extrair `<script>` e balancear chaves/parênteses/backticks) + verificação manual.

- [ ] **Step 1: Rotear a etapa 15 para um painel dedicado**

No bloco de escolha do card (onde `etapa.codigo === '14' ? _renderCardEntrega(...)`), adicionar antes do
fallback genérico:
```javascript
          : etapa.codigo === '15'
            ? _renderCardEmissaoNfe(dados, bloqueada)
```

- [ ] **Step 2: Estado + loader (junto dos loaders do ciclo, ex. após `pedidosXmlCarregar`)**

```javascript
let _nfe15 = { fabrica_xmls: [] };
async function nfe15Carregar(nomeSafe) {
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafe)}/ciclo/15/nfe`, { credentials: 'same-origin' });
    const j = await r.json();
    _nfe15 = (j && j.ok) ? j : { fabrica_xmls: [] };
  } catch(e) { _nfe15 = { fabrica_xmls: [] }; }
}
```
E no `carregarCiclo`, após os outros loaders: `if (projetoAtivo) await nfe15Carregar(projetoAtivo.nome_safe);`

- [ ] **Step 3: Render + handlers (junto dos handlers das etapas operacionais)**

```javascript
const _NFE_NIVEIS_EMITE = new Set(["diretor","gerente_adm_fin","admin_rede","super_admin"]);
function _podeEmitirNfe() {
  return _NFE_NIVEIS_EMITE.has((_usuarioAtual && _usuarioAtual.nivel) || '');
}

function _renderCardEmissaoNfe(dados, bloqueada) {
  const concluido = dados.status === 'emitida' || dados.status === 'concluido';
  if (bloqueada) {
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior para liberar esta etapa.</p>`;
  }
  const podeEmitir = _podeEmitirNfe();
  const linhas = (_nfe15.fabrica_xmls || []).map(x => {
    const e = x.emissao;
    const proj = projetoAtivo ? projetoAtivo.nome_safe : '';
    if (e) {
      const cor = e.status === 'autorizado' ? 'var(--ok)' : e.status === 'erro' ? 'var(--warn)' : e.status === 'cancelado' ? 'var(--muted)' : 'var(--dalm-gold)';
      const dl = id => id ? `<a class="btn-ciclo" style="font-size:.75rem;text-decoration:none" target="_blank" rel="noopener" href="/api/projetos/${encodeURIComponent(proj)}/ciclo/documento/${id}">Baixar</a>` : '';
      return `<div style="border:1px solid var(--border);border-radius:6px;padding:8px;margin-bottom:6px;font-size:.82rem">
        <div>📄 ${esc(x.nome_original)} — <span style="color:${cor};font-weight:700">${esc(e.status)}</span>${e.chave ? ' · ' + esc(e.chave) : ''}</div>
        ${e.mensagem_sefaz ? `<div style="color:var(--muted);font-size:.75rem">${esc(e.mensagem_sefaz)}</div>` : ''}
        <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">
          ${e.xml_doc_id ? 'XML: ' + dl(e.xml_doc_id) : ''} ${e.danfe_doc_id ? 'DANFE: ' + dl(e.danfe_doc_id) : ''}
          ${podeEmitir ? `<button class="btn-ciclo" style="font-size:.75rem" onclick="consultarNfeLoja('${esc(e.ref)}')">Consultar</button>` : ''}
          ${podeEmitir && e.status === 'autorizado' ? `<button class="btn-ciclo" style="font-size:.75rem" onclick="cancelarNfeLoja('${esc(e.ref)}')">Cancelar</button>` : ''}
        </div></div>`;
    }
    return `<div style="display:flex;gap:8px;align-items:center;margin-bottom:6px;font-size:.82rem;flex-wrap:wrap">
        <span style="flex:1">📄 ${esc(x.nome_original)}</span>
        ${podeEmitir ? `<input id="nfe-markup-${x.id}" type="number" step="0.01" value="30" title="Markup %" style="width:70px;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:5px 8px;color:var(--text);font-size:.8rem">
          <button class="btn-ciclo" style="font-size:.8rem" onclick="emitirNfeLoja(${x.id})">Emitir NF-e da Loja</button>` : '<span style="color:var(--muted);font-size:.75rem">sem permissão para emitir</span>'}
      </div>`;
  }).join('') || `<p style="color:var(--muted);font-size:.82rem;margin:0 0 8px">Nenhuma NF-e da fábrica carregada.</p>`;
  const upload = podeEmitir ? `<label class="btn-ciclo" style="font-size:.82rem;cursor:pointer">
       📎 Carregar NF-e da Fábrica
       <input type="file" accept=".xml" style="display:none" onchange="enviarNfeFabrica(this)"></label>` : '';
  return `<div style="margin-bottom:10px">${linhas}</div>${upload}
    ${concluido ? '<p style="color:var(--ok);margin:8px 0 0">✓ NF-e emitida.</p>' : ''}`;
}

async function enviarNfeFabrica(inputFile) {
  if (!projetoAtivo) return;
  const f = inputFile.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('arquivo', f);
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/15/nfe-fabrica`,
      { method: 'POST', credentials: 'same-origin', body: fd });
    const j = await r.json();
    if (!j.ok) { await avisoPopup(j.erro || 'Falha ao carregar.', {titulo:'NF-e — Fábrica'}); return; }
    showToast('NF-e da fábrica carregada!', false); await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'NF-e — Fábrica'}); }
}

async function emitirNfeLoja(docId) {
  if (!projetoAtivo) return;
  const mk = parseFloat((document.getElementById('nfe-markup-' + docId) || {}).value || '0') || 0;
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/15/emitir-nfe`,
      { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ fabrica_doc_id: docId, markup_pct: mk }) });
    const j = await r.json();
    if (!j.ok) { await avisoPopup(j.erro || 'Falha na emissão.', {titulo:'Emitir NF-e'}); return; }
    showToast('Emissão: ' + j.status, false); await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Emitir NF-e'}); }
}

async function consultarNfeLoja(ref) {
  if (!projetoAtivo) return;
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/15/nfe/consultar`,
      { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ref }) });
    const j = await r.json();
    if (!j.ok) { await avisoPopup(j.erro || 'Falha.', {titulo:'Consultar NF-e'}); return; }
    showToast('Status: ' + j.status, false); await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Consultar NF-e'}); }
}

async function cancelarNfeLoja(ref) {
  if (!projetoAtivo) return;
  const just = await promptPopup ? null : null;   // ver Step 3b
  const j2 = window.prompt('Justificativa do cancelamento (15 a 255 caracteres):', '');
  if (!j2 || j2.length < 15) { await avisoPopup('Justificativa deve ter ao menos 15 caracteres.', {titulo:'Cancelar NF-e'}); return; }
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/15/nfe/cancelar`,
      { method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ ref, justificativa: j2 }) });
    const j = await r.json();
    if (!j.ok) { await avisoPopup(j.erro || 'Falha.', {titulo:'Cancelar NF-e'}); return; }
    showToast('Cancelamento: ' + j.status, false); await carregarCiclo();
  } catch(e) { await avisoPopup('Erro de rede: ' + e.message, {titulo:'Cancelar NF-e'}); }
}
```

Nota: remover a linha `const just = await promptPopup ? null : null;` (é resíduo) — usar direto o
`window.prompt`. Manter o resto.

- [ ] **Step 4: Checagem estrutural + suíte**

Extrair o maior `<script>` e conferir balanceamento (chaves/parênteses/backticks; o desbalanço de -1
parêntese é pré-existente do arquivo). Rodar `python3 -m pytest -q` (o frontend não afeta o backend →
segue verde).

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(nfe): painel da etapa 15 (carregar NF-e fabrica, emitir, status, baixar, consultar/cancelar)"
```

---

## Task 5: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/fiscal/2026-07-06-nfe-fase5-etapa15-emissao-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q` → verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar `> Status: **APROVADO (brainstorming)** — a implementar. Última peça...` por
`> Status: **IMPLEMENTADO (Sessão N)** — etapa 15 (upload NF-e fábrica → emitir → acompanhar → baixar) com e2e; painel manual pendente; smoke real quando o certificado A1 estiver na Focus.`

- [ ] **Step 3: DEV_LOG — marcar Fase 5 ✅ na tabela do módulo fiscal**

Na tabela do `⏸️ ESTADO ATUAL` (🧾 Módulo Fiscal), trocar a linha da **Fase 5** para ✅ (etapa 15:
upload da NF-e da fábrica + emitir/consultar/cancelar + painel; conclui em `emitida`). Registrar: a
integração NF-e fica **completa em código**; só falta o **certificado A1 na Focus** para o smoke real +
a **verificação manual do painel** (etapa 15 e Painel Fiscal II).

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/fiscal/2026-07-06-nfe-fase5-etapa15-emissao-design.md
git commit -m "docs(nfe): DEV_LOG + spec Fase 5 como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §3 modelo+migração (Task 1), §4.1 `emitir` (Task 1), §4.2 upload+GET (Task 2) e
  emitir/consultar/cancelar (Task 3), §5 painel (Task 4), §6 testes distribuídos. §7 fora de escopo
  respeitado (produção bloqueada; sem consolidação; regimes extras adiados).
- **Consistência de nomes:** `fabrica_doc_id`, `nfe_fabrica_xml`, `ref="NFE-<projeto>-<doc_id>"`, status
  `emitida`, `_emissor_para` (monkeypatch), `perfis.pode(nivel,"editar_dados_loja")`, os campos do `GET
  nfe` (`fabrica_xmls[].emissao.{status,chave,...}`) e as respostas dos endpoints idênticos entre
  backend, testes e frontend. `res.status.value` usado nos endpoints (StatusNota é str-enum).
- **Sem placeholders:** todo passo com código completo; a linha-resíduo do `cancelarNfeLoja` está
  sinalizada para remoção. `Sessão N` = número corrente do DEV_LOG.
```
