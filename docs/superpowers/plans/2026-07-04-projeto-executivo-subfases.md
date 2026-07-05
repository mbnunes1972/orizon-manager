# Subfases do Projeto Executivo (etapa 11) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer as subfases do Projeto Executivo (etapa 11: 11a/11b/11c/11e) com upload de documentos (append-only), transições de fase nomeadas, revisão com reabertura em cascata e monitoramento local por projeto.

**Architecture:** Backend Python puro (`http.server`) + SQLAlchemy/SQLite. Duas tabelas novas (`ciclo_documentos`, `ciclo_revisoes`) chaveadas por `(projeto_nome, etapa_codigo)`; status/datas continuam no `CicloEtapa` existente. Lógica pura (guardas, cascade, versão) em `mod_ciclo.py` (testável sem HTTP); endpoints multipart em `main.py` espelhando o workflow de Medição. Frontend no único `static/index.html` (verificação manual).

**Tech Stack:** Python 3.12, SQLAlchemy, `http.server`, pytest; frontend HTML/CSS/JS inline.

**Spec:** `docs/superpowers/specs/2026-07-04-projeto-executivo-subfases-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `perfis.py` | Capabilities `executar_pe` e `revisar_pe` | Modificar |
| `database.py` | Modelos `CicloDocumento`, `CicloRevisao` | Modificar |
| `mod_ciclo.py` | Lógica pura de PE (subfases, guardas, versão) | Modificar |
| `main.py` | Endpoints (upload, concluir, revisão, GET, download) | Modificar |
| `static/index.html` | Painéis das subfases + botões + progresso | Modificar |
| `tests/test_ciclo.py` | Testes puros de `mod_ciclo` (PE) | Modificar |
| `tests/test_ciclo_pe_e2e.py` | Testes HTTP dos endpoints | Criar |
| `docs/USUARIOS.md`, `DEV_LOG.md` | Documentação | Modificar |

**Nota de decisão (ambiguidade resolvida):** o "reabrir em cascata" existente usa a capability
`autorizar`, que **exclui** o Gerente Adm/Financeiro. Como a revisão de PE deve incluí-lo (Vendas /
Adm-Fin / Diretor), este plano cria uma capability **dedicada `revisar_pe`** com exatamente esses três
perfis, em vez de reusar `autorizar`.

---

## Task 1: Capabilities `executar_pe` e `revisar_pe`

**Files:**
- Modify: `perfis.py:8-19` (dict `PERFIS`)
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao final de `tests/test_ciclo.py`:

```python
import perfis

def test_capability_executar_pe():
    for slug in ("projetista_executivo", "conferente", "gerente_vendas",
                 "gerente_adm_fin", "diretor"):
        assert perfis.pode(slug, "executar_pe") is True, slug
    for slug in ("consultor", "medidor", "assistente_logistico"):
        assert perfis.pode(slug, "executar_pe") is False, slug

def test_capability_revisar_pe():
    for slug in ("gerente_vendas", "gerente_adm_fin", "diretor"):
        assert perfis.pode(slug, "revisar_pe") is True, slug
    for slug in ("projetista_executivo", "conferente", "consultor"):
        assert perfis.pode(slug, "revisar_pe") is False, slug
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo.py::test_capability_executar_pe tests/test_ciclo.py::test_capability_revisar_pe -v`
Expected: FAIL (capabilities retornam False).

- [ ] **Step 3: Adicionar as chaves nos perfis**

Em `perfis.py`, adicionar `"executar_pe": True` e/ou `"revisar_pe": True` aos perfis:
- `diretor` → `"executar_pe": True, "revisar_pe": True`
- `gerente_vendas` → `"executar_pe": True, "revisar_pe": True`
- `gerente_adm_fin` → `"executar_pe": True, "revisar_pe": True`
- `conferente` → `"executar_pe": True`
- `projetista_executivo` → `"executar_pe": True`

Exemplo (linha do `conferente`):
```python
    "conferente":                {"rotulo": "Conferente",                        "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False, "executar_pe": True},
```

(`perfis.pode` já retorna `False` por padrão para perfis sem a chave — não precisa alterar `_DEFAULT`.)

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `python3 -m pytest tests/test_ciclo.py -k capability -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add perfis.py tests/test_ciclo.py
git commit -m "feat(pe): capabilities executar_pe e revisar_pe"
```

---

## Task 2: Modelos `CicloDocumento` e `CicloRevisao`

**Files:**
- Modify: `database.py` (antes de `def init_db()`, ~linha 469)
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_ciclo.py`:

```python
def test_modelos_ciclo_documento_e_revisao(tmp_path):
    import importlib, database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    dbf = str(tmp_path / "t.db")
    database.DB_PATH = dbf
    database.ENGINE = create_engine(f"sqlite:///{dbf}")
    database.Session = sessionmaker(bind=database.ENGINE)
    database.init_db()
    s = database.Session()
    d = database.CicloDocumento(projeto_nome="P", etapa_codigo="11a",
                                tipo="pe_planta_pontos", arquivo_path="ciclo/11a/x.pdf",
                                nome_original="x.pdf")
    s.add(d); s.commit()
    r = database.CicloRevisao(projeto_nome="P", etapa_codigo="11b", relatorio_doc_id=d.id)
    s.add(r); s.commit()
    assert s.query(database.CicloDocumento).count() == 1
    assert s.query(database.CicloRevisao).first().etapa_codigo == "11b"
    s.close()
```

- [ ] **Step 2: Rodar o teste e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo.py::test_modelos_ciclo_documento_e_revisao -v`
Expected: FAIL (`AttributeError: module 'database' has no attribute 'CicloDocumento'`).

- [ ] **Step 3: Adicionar os modelos**

Em `database.py`, logo antes de `# ── Inicialização ──` (linha ~469):

```python
class CicloDocumento(Base):
    """Documento carregado numa subfase do ciclo. Append-only: nunca sobrescreve."""
    __tablename__ = "ciclo_documentos"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome   = Column(Text,     nullable=False)   # nome_safe
    etapa_codigo   = Column(Text,     nullable=False)   # "11a","11b","11c","11e"
    tipo           = Column(Text,     nullable=False)   # pe_planta_pontos, ...
    arquivo_path   = Column(Text,     nullable=False)   # relativo a PROJETOS/<nome>/
    nome_original  = Column(Text,     nullable=False)
    enviado_por_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    enviado_em     = Column(DateTime, nullable=False, default=datetime.utcnow)

    enviado_por = relationship("Usuario", foreign_keys=[enviado_por_id])


class CicloRevisao(Base):
    """Revisão aberta numa subfase (reabertura em cascata)."""
    __tablename__ = "ciclo_revisoes"

    id               = Column(Integer,  primary_key=True, autoincrement=True)
    projeto_nome     = Column(Text,     nullable=False)
    etapa_codigo     = Column(Text,     nullable=False)
    aberta_por_id    = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    aberta_em        = Column(DateTime, nullable=False, default=datetime.utcnow)
    relatorio_doc_id = Column(Integer,  ForeignKey("ciclo_documentos.id"), nullable=True)
    motivo           = Column(Text,     nullable=True)

    aberta_por = relationship("Usuario", foreign_keys=[aberta_por_id])
```

`Base.metadata.create_all` (em `init_db`) cria as tabelas novas automaticamente — nenhuma migração de coluna necessária.

- [ ] **Step 4: Rodar o teste e confirmar que passa**

Run: `python3 -m pytest tests/test_ciclo.py::test_modelos_ciclo_documento_e_revisao -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_ciclo.py
git commit -m "feat(pe): modelos CicloDocumento e CicloRevisao (append-only)"
```

---

## Task 3: Lógica pura de PE em `mod_ciclo.py`

**Files:**
- Modify: `mod_ciclo.py` (após `STATUS_CONCLUSIVOS`, ~linha 42)
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar em `tests/test_ciclo.py`:

```python
import mod_ciclo as mc2

def test_tipo_doc_de():
    assert mc2.tipo_doc_de("11a") == "pe_planta_pontos"
    assert mc2.tipo_doc_de("11c") == "pe_projeto_executivo"
    assert mc2.tipo_doc_de("11d") is None   # 11d não é subfase enriquecida
    assert mc2.tipo_doc_de("99z") is None

def test_guarda_conclusao_exige_documento():
    ok, erro = mc2.guarda_conclusao("11a", set(), {})
    assert ok is False and "Carregue" in erro
    ok, erro = mc2.guarda_conclusao("11a", {"pe_planta_pontos"}, {})
    assert ok is True and erro == ""

def test_guarda_conclusao_11e_exige_anteriores():
    tipos = {"pe_pe_assinado"}
    # 11a-11c concluídas, 11d pendente → barra
    st = {"11a": "concluido", "11b": "concluido", "11c": "concluido", "11d": "pendente"}
    ok, erro = mc2.guarda_conclusao("11e", tipos, st)
    assert ok is False and "11d" in erro
    # todas concluídas → libera
    st["11d"] = "aprovado"
    ok, erro = mc2.guarda_conclusao("11e", tipos, st)
    assert ok is True

def test_versao_atual():
    from datetime import datetime
    docs = [
        {"tipo": "pe_projeto_executivo", "enviado_em": datetime(2026, 7, 10), "id": 1},
        {"tipo": "pe_projeto_executivo", "enviado_em": datetime(2026, 7, 12), "id": 2},
        {"tipo": "pe_planta_pontos",     "enviado_em": datetime(2026, 7, 9),  "id": 3},
    ]
    assert mc2.versao_atual(docs, "pe_projeto_executivo")["id"] == 2
    assert mc2.versao_atual(docs, "inexistente") is None
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo.py -k "tipo_doc or guarda or versao_atual" -v`
Expected: FAIL (`AttributeError` em `mod_ciclo`).

- [ ] **Step 3: Implementar a lógica pura**

Em `mod_ciclo.py`, após a definição de `STATUS_CONCLUSIVOS` (linha ~42):

```python
# ── Projeto Executivo (etapa 11) — subfases enriquecidas ──────────────────────
SUBFASES_PE = {
    "11a": {"nome": "Planta de pontos de PE",       "tipo_doc": "pe_planta_pontos",
            "doc_label": "arquivo de medição",       "botao": "Encaminhar para PE",       "revisavel": False},
    "11b": {"nome": "Reunião de alinhamento",        "tipo_doc": "pe_relatorio_alinhamento",
            "doc_label": "relatório da reunião",     "botao": "Projeto Alinhado",         "revisavel": True},
    "11c": {"nome": "Revisão de PE",                 "tipo_doc": "pe_projeto_executivo",
            "doc_label": "Projeto Executivo",        "botao": "Concluído",                "revisavel": True},
    "11e": {"nome": "Aprovação do PE pelo cliente",  "tipo_doc": "pe_pe_assinado",
            "doc_label": "Projeto Executivo Assinado","botao": "Concluir Projeto Executivo","revisavel": False},
}

# Subfases que precisam estar concluídas antes de concluir o PE (11e).
PE_SUBFASES_OBRIGATORIAS = ["11a", "11b", "11c", "11d"]


def tipo_doc_de(codigo):
    sf = SUBFASES_PE.get(codigo)
    return sf["tipo_doc"] if sf else None


def guarda_conclusao(codigo, tipos_presentes, status_por_codigo):
    """(ok, erro). tipos_presentes: set de tipos de documento já carregados na subfase.
    status_por_codigo: {codigo: status} — usado no 11e para exigir 11a-11d concluídas."""
    sf = SUBFASES_PE.get(codigo)
    if not sf:
        return (False, "Subfase de PE desconhecida.")
    if sf["tipo_doc"] not in tipos_presentes:
        return (False, f"Carregue o documento ({sf['doc_label']}) antes de '{sf['botao']}'.")
    if codigo == "11e":
        faltando = [c for c in PE_SUBFASES_OBRIGATORIAS
                    if status_por_codigo.get(c) not in STATUS_CONCLUSIVOS]
        if faltando:
            return (False, "Conclua as subfases anteriores do PE: " + ", ".join(faltando) + ".")
    return (True, "")


def versao_atual(documentos, tipo):
    """documentos: lista de dicts com 'tipo' e 'enviado_em'. Última versão do tipo, ou None."""
    do_tipo = [d for d in documentos if d.get("tipo") == tipo]
    if not do_tipo:
        return None
    return max(do_tipo, key=lambda d: d["enviado_em"])
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 -m pytest tests/test_ciclo.py -v`
Expected: PASS (todos, incluindo os antigos).

- [ ] **Step 5: Commit**

```bash
git add mod_ciclo.py tests/test_ciclo.py
git commit -m "feat(pe): logica pura de subfases (guardas, versao) em mod_ciclo"
```

---

## Task 4: Endpoint de upload de documento

**Files:**
- Modify: `main.py` — em `do_POST`, junto aos endpoints de medição (após o bloco `medicao/decisao-reprovado`, ~linha 3692). Garantir `import uuid` no topo de `main.py` (adicionar se ausente).
- Test: `tests/test_ciclo_pe_e2e.py`

- [ ] **Step 1: Criar o teste HTTP que falha**

Criar `tests/test_ciclo_pe_e2e.py` com o helper multipart e o primeiro teste:

```python
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
    # segundo upload do mesmo tipo → nova versão (append-only)
    st2, _ = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
        {"login": "dir_l2", "senha": "senha123"},
        file_field="arquivo", filename="planta_v2.pdf", filedata=b"%PDF-fake2")
    assert st2 == 200
    st3, docs = c.get(f"/api/projetos/{proj}/ciclo/pe")
    assert st3 == 200
    versoes = [d for d in docs["documentos"] if d["tipo"] == "pe_planta_pontos"]
    assert len(versoes) == 2, "append-only deve manter as duas versões"
```

(O `HttpClient` do `conftest.py` expõe `.base` e `.cookie`.)

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py::test_upload_pe_cria_documento -v`
Expected: FAIL (rota inexistente → 404).

- [ ] **Step 3: Implementar o endpoint de upload**

Garantir no topo de `main.py`: `import uuid`. Adicionar em `do_POST` após o bloco de medição (~linha 3692, antes do `else:` final de `do_POST`):

```python
            # POST /api/projetos/<nome>/ciclo/<codigo>/documento — upload append-only (PE)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/documento$', path)
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
                    tipo_esperado = mod_ciclo.tipo_doc_de(codigo)
                    if not tipo_esperado:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "executar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o arquivo."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo=tipo_esperado,
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc)
                    et = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
                    if not et or et.status == "pendente":
                        _set_etapa_status(db, nome_safe, codigo, "em_andamento", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_documento_" + tipo_esperado, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    # arquivo em disco SOMENTE após commit (padrão EP-07)
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "documento_id": doc.id})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

O endpoint GET `/ciclo/pe` (usado pelo teste) é criado na Task 7 — este teste só passa após a Task 7. Marque este teste como dependente ou rode a Task 7 na sequência. Para validar isoladamente agora, cheque via banco (opcional).

- [ ] **Step 4: Implementar a Task 7 (GET) e então rodar**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py::test_upload_pe_cria_documento -v`
Expected: PASS (após Task 7).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_ciclo_pe_e2e.py
git commit -m "feat(pe): endpoint de upload de documento (append-only)"
```

---

## Task 5: Endpoint de conclusão de subfase

**Files:**
- Modify: `main.py` (em `do_POST`, após o endpoint de documento)
- Test: `tests/test_ciclo_pe_e2e.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_ciclo_pe_e2e.py`:

```python
def test_concluir_11a_barra_sem_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    # sem documento carregado numa subfase nova → 400
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11c/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 400 and "Carregue" in body["erro"]


def test_concluir_11a_com_documento(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    _post_multipart(c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11a/documento",
                    {"login": "dir_l2", "senha": "senha123"},
                    file_field="arquivo", filename="p.pdf", filedata=b"x")
    st, body = c.post(f"/api/projetos/{proj}/ciclo/11a/concluir",
                      {"login": "dir_l2", "senha": "senha123"})
    assert st == 200 and body.get("ok") is True
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py -k concluir -v`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Implementar o endpoint de conclusão**

Em `do_POST`, após o endpoint de documento:

```python
            # POST /api/projetos/<nome>/ciclo/<codigo>/concluir — fecha a subfase de PE
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/concluir$', path)
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
                    if codigo not in mod_ciclo.SUBFASES_PE:
                        self.send_json({"ok": False, "erro": "Subfase de PE inválida."}, code=400); return
                    req = json.loads(body or b'{}')
                    u = _usuario_com_capacidade(db, req.get("login", ""), req.get("senha", ""), "executar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Ação exige login+senha de Projetista Executivo, Conferente, Gerente ou Diretor."}, code=403); return
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).all()
                    tipos_presentes = {d.tipo for d in docs}
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    status_por = {e.etapa_codigo: e.status for e in todas}
                    ok, erro = mod_ciclo.guarda_conclusao(codigo, tipos_presentes, status_por)
                    if not ok:
                        self.send_json({"ok": False, "erro": erro}, code=400); return
                    _set_etapa_status(db, nome_safe, codigo, "concluido", u.id)
                    if codigo == "11e":
                        _set_etapa_status(db, nome_safe, "11", "concluido", u.id)
                    db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                            acao="pe_concluir_" + codigo, projeto_nome=nome_safe, etapa_alvo=codigo))
                    db.commit()
                    self.send_json({"ok": True})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py -k concluir -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_ciclo_pe_e2e.py
git commit -m "feat(pe): endpoint de conclusao de subfase com guardas"
```

---

## Task 6: Endpoint de revisão (reabertura em cascata)

**Files:**
- Modify: `main.py` (em `do_POST`, após o endpoint de conclusão)
- Test: `tests/test_ciclo_pe_e2e.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_ciclo_pe_e2e.py`:

```python
def test_revisao_reabre_em_cascata(http_client_factory, seed, projetos_dir, app_db):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    # marca 11e concluída direto no banco para provar que a revisão de 11b a reabre
    db = app_db.get_session()
    for cod in ("11b", "11c", "11d", "11e"):
        db.add(app_db.CicloEtapa(projeto_nome=proj, etapa_codigo=cod, status="concluido"))
    db.commit(); db.close()
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l2", "senha": "senha123", "motivo": "ajuste"},
        file_field="arquivo", filename="relatorio.pdf", filedata=b"rel")
    assert st == 200 and "11e" in body["resetadas"], body
    db = app_db.get_session()
    e11e = db.query(app_db.CicloEtapa).filter_by(projeto_nome=proj, etapa_codigo="11e").first()
    assert e11e.status == "pendente"
    db.close()


def test_revisao_exige_gerente(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "cons_l1")   # consultor não pode revisar
    proj = seed["projeto_l1"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "cons_l1", "senha": "senha123"},
        file_field="arquivo", filename="r.pdf", filedata=b"r")
    assert st == 403


def test_revisao_exige_relatorio(http_client_factory, seed, projetos_dir):
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, body = _post_multipart(
        c.base, c.cookie, f"/api/projetos/{proj}/ciclo/11b/revisao",
        {"login": "dir_l2", "senha": "senha123"})   # sem arquivo
    assert st == 400 and "relatório" in body["erro"].lower()
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py -k revisao -v`
Expected: FAIL.

- [ ] **Step 3: Implementar o endpoint de revisão**

Em `do_POST`, após o endpoint de conclusão:

```python
            # POST /api/projetos/<nome>/ciclo/<codigo>/revisao — revisão + reabertura em cascata
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/revisao$', path)
            if m:
                nome_safe = unquote(m.group(1)); codigo = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, solicitante)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    if _projeto_da_loja(db, nome_safe, loja_id) is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    sf = mod_ciclo.SUBFASES_PE.get(codigo)
                    if not sf or not sf["revisavel"]:
                        self.send_json({"ok": False, "erro": "Esta subfase não permite revisão."}, code=400); return
                    u = _usuario_com_capacidade(db, campos.get("login", ""), campos.get("senha", ""), "revisar_pe")
                    if not u:
                        self.send_json({"ok": False, "erro": "Revisão exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o relatório complementar (obrigatório)."}, code=400); return
                    fname, data = arquivos["arquivo"]
                    base_nome = os.path.basename(fname)
                    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base_nome
                    rel = os.path.join("ciclo", codigo, unico)
                    doc = CicloDocumento(projeto_nome=nome_safe, etapa_codigo=codigo, tipo="pe_relatorio_complementar",
                                         arquivo_path=rel, nome_original=base_nome, enviado_por_id=u.id)
                    db.add(doc); db.flush()   # doc.id para a revisão
                    todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos = [e.etapa_codigo for e in todas]
                    resetar = mod_ciclo.codigos_a_resetar(codigo, codigos)
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe).order_by(Contrato.id.desc()).first()
                    cstatus = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False, "erro": "Contrato já assinado — não é possível revisar esta etapa"}, code=400); return
                    resetar_set = set(resetar)
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status = "pendente"; e.iniciado_em = None; e.concluido_em = None; e.responsavel_id = None
                    # a etapa-mãe 11 volta a "em andamento" (PE deixou de estar concluído)
                    _set_etapa_status(db, nome_safe, "11", "em_andamento", u.id)
                    rev = CicloRevisao(projeto_nome=nome_safe, etapa_codigo=codigo, aberta_por_id=u.id,
                                       relatorio_doc_id=doc.id, motivo=(campos.get("motivo") or None))
                    db.add(rev)
                    db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                            acao="pe_revisao", projeto_nome=nome_safe, etapa_alvo=codigo,
                            contexto=json.dumps({"resetadas": sorted(resetar_set)})))
                    db.commit()
                    storage_salvar_binario(os.path.join(_projeto_path(nome_safe), rel), data)
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py -k revisao -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_ciclo_pe_e2e.py
git commit -m "feat(pe): endpoint de revisao com reabertura em cascata"
```

---

## Task 7: Endpoints GET (`/ciclo/pe`) e download de documento

**Files:**
- Modify: `main.py` — em `do_GET`, junto ao GET de medição (`/medicao`, ~linha 1213) e ao GET de arquivo (`/medicao/arquivo/...`, ~linha 1178)
- Test: `tests/test_ciclo_pe_e2e.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar em `tests/test_ciclo_pe_e2e.py`:

```python
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
    # o diretório de medição NÃO deve ter sido tocado pelo fluxo de PE
    med = os.path.join(projetos_dir, proj, "medicao")
    assert not os.path.exists(med) or os.listdir(med) == []
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py::test_get_pe_lista_documentos_e_medicao_intocada -v`
Expected: FAIL (rota GET inexistente).

- [ ] **Step 3: Implementar os GET**

Em `do_GET`, junto aos GET de medição:

```python
            # GET /api/projetos/<nome>/ciclo/pe — documentos + revisões + status das subfases
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/pe$', path)
            if m:
                nome_safe = unquote(m.group(1))
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
                    docs = db.query(CicloDocumento).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloDocumento.enviado_em.desc()).all()
                    revs = db.query(CicloRevisao).filter_by(projeto_nome=nome_safe)\
                             .order_by(CicloRevisao.aberta_em.desc()).all()
                    etapas = db.query(CicloEtapa).filter(CicloEtapa.projeto_nome == nome_safe,
                                                         CicloEtapa.etapa_codigo.like("11%")).all()
                    subfases = {e.etapa_codigo: {"status": e.status,
                                                 "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None}
                                for e in etapas}
                    self.send_json({"ok": True,
                        "subfases": subfases,
                        "documentos": [{"id": d.id, "etapa_codigo": d.etapa_codigo, "tipo": d.tipo,
                                        "nome_original": d.nome_original,
                                        "enviado_em": d.enviado_em.isoformat() if d.enviado_em else None,
                                        "enviado_por_id": d.enviado_por_id} for d in docs],
                        "revisoes": [{"id": r.id, "etapa_codigo": r.etapa_codigo,
                                      "aberta_por_id": r.aberta_por_id,
                                      "aberta_em": r.aberta_em.isoformat() if r.aberta_em else None,
                                      "relatorio_doc_id": r.relatorio_doc_id, "motivo": r.motivo} for r in revs]})
                finally:
                    db.close()
                return

            # GET /api/projetos/<nome>/ciclo/documento/<id> — baixa um documento (read-only)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/documento/(\d+)$', path)
            if m:
                nome_safe = unquote(m.group(1)); doc_id = int(m.group(2))
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
                    doc = db.query(CicloDocumento).filter_by(id=doc_id, projeto_nome=nome_safe).first()
                    if not doc:
                        self.send_response(404); self.end_headers(); return
                    caminho = os.path.join(_projeto_path(nome_safe), doc.arquivo_path)
                    if not os.path.exists(caminho):
                        self.send_response(404); self.end_headers(); return
                    with open(caminho, "rb") as f:
                        conteudo = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Disposition", f'inline; filename="{doc.nome_original}"')
                    self.send_header("Content-Length", str(len(conteudo)))
                    self.end_headers()
                    self.wfile.write(conteudo)
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Rodar toda a suíte de PE**

Run: `python3 -m pytest tests/test_ciclo_pe_e2e.py tests/test_ciclo.py -v`
Expected: PASS (todos os testes de PE, incluindo o de upload da Task 4).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_ciclo_pe_e2e.py
git commit -m "feat(pe): GET /ciclo/pe e download de documento"
```

---

## Task 8: Frontend — leitura e render dos painéis das subfases

**Files:**
- Modify: `static/index.html` — `ETAPAS_CICLO` (linha ~7503) e a função que renderiza o painel de ciclo (loop `for (const etapa of ETAPAS_CICLO)`, ~linha 7720)

> Frontend não tem teste automatizado. Verificação: **manual no navegador** + `node --check` no `<script>` extraído.

- [ ] **Step 1: Buscar os dados de PE ao abrir o Ciclo**

Adicionar uma função JS que consome o GET novo e guarda em estado de página:

```javascript
let _pePayload = { subfases:{}, documentos:[], revisoes:[] };
async function peCarregar(nomeSafe){
  try{
    const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafe)}/ciclo/pe`);
    const j = await r.json();
    if(j && j.ok){ _pePayload = j; }
  }catch(e){ /* silencioso: painel mostra vazio */ }
}
```

Chamar `await peCarregar(nomeSafeAtual)` no mesmo ponto em que o painel de Ciclo é (re)renderizado.

- [ ] **Step 2: Render dos documentos/versões por subfase**

Adicionar helper que, para um `codigo` de subfase, lista as versões (mais recente primeiro) com link de download:

```javascript
function peDocsHtml(codigo, tipo){
  const docs = _pePayload.documentos
      .filter(d => d.etapa_codigo === codigo && d.tipo === tipo)
      .sort((a,b) => (b.enviado_em||'').localeCompare(a.enviado_em||''));
  if(!docs.length) return '<div class="pe-vazio">Nenhum documento carregado.</div>';
  return docs.map((d,i) =>
    `<div class="pe-doc">📎 <a href="/api/projetos/${encodeURIComponent(nomeSafeAtual)}/ciclo/documento/${d.id}" target="_blank">${d.nome_original}</a>`
    + ` · ${(d.enviado_em||'').slice(0,16).replace('T',' ')}${i===0?' <span class="pe-atual">(atual)</span>':''}</div>`
  ).join('');
}
```

- [ ] **Step 3: Injetar os botões conforme capability**

No loop que renderiza cada `etapa` do ciclo, quando `etapa.codigo` estiver em `["11a","11b","11c","11e"]`, renderizar o cartão com: os documentos (`peDocsHtml`), o botão "Carregar …", o botão de fechar (nome vindo de um mapa), e — se `11b`/`11c` — o botão "Revisão". Usar a permissão do usuário logado (já disponível no front, ex.: `usuarioAtual.pode('executar_pe')` / `('revisar_pe')` — seguir o mecanismo de capability já usado no front para `aprovar_financeiro`).

Mapa de rótulos (espelha `SUBFASES_PE` do backend):
```javascript
const PE_SUBFASES = {
  "11a": {carregar:"Carregar arquivo de medição", fechar:"Encaminhar para PE",        tipo:"pe_planta_pontos",        revisavel:false},
  "11b": {carregar:"Carregar relatório da reunião", fechar:"Projeto Alinhado",          tipo:"pe_relatorio_alinhamento",revisavel:true},
  "11c": {carregar:"Carregar Projeto Executivo",   fechar:"Concluído",                 tipo:"pe_projeto_executivo",    revisavel:true},
  "11e": {carregar:"Carregar PE Assinado",         fechar:"Concluir Projeto Executivo",tipo:"pe_pe_assinado",          revisavel:false},
};
```

- [ ] **Step 4: Indicador de progresso na etapa 11**

No cabeçalho da etapa 11, calcular `concluidas = ["11a","11b","11c","11e"].filter(c => (_pePayload.subfases[c]||{}).status === 'concluido' || ...conclusivos).length` e exibir `Projeto Executivo — {concluidas}/4 subfases concluídas` + uma barra. Em `11a`, exibir link read-only para a planta da Medição (etapa 10), reusando o GET de arquivo de medição já existente.

- [ ] **Step 5: Checar sintaxe e verificação manual**

Run (sintaxe): extrair o `<script>` de `static/index.html` para `/tmp/app.js` e `node --check /tmp/app.js`.
Manual: abrir o projeto → aba Ciclo → etapa 11; confirmar que os cartões e botões aparecem conforme o perfil logado.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(pe): paineis das subfases + progresso no frontend"
```

---

## Task 9: Frontend — ações (upload, concluir, revisão)

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Handler de upload**

```javascript
async function peUpload(codigo, inputFile){
  const f = inputFile.files[0];
  if(!f){ avisoPopup("Selecione um arquivo."); return; }
  const cred = await pedirCredenciaisGerente();   // reusa o modal de login+senha existente
  if(!cred) return;
  const fd = new FormData();
  fd.append("arquivo", f); fd.append("login", cred.login); fd.append("senha", cred.senha);
  const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafeAtual)}/ciclo/${codigo}/documento`, {method:"POST", body:fd});
  const j = await r.json();
  if(!j.ok){ avisoPopup(j.erro || "Falha ao carregar."); return; }
  await peCarregar(nomeSafeAtual); cicloRerender();
}
```

- [ ] **Step 2: Handler de conclusão**

```javascript
async function peConcluir(codigo){
  const cred = await pedirCredenciaisGerente();
  if(!cred) return;
  const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafeAtual)}/ciclo/${codigo}/concluir`,
    {method:"POST", headers:{"Content-Type":"application/json"},
     body: JSON.stringify({login:cred.login, senha:cred.senha})});
  const j = await r.json();
  if(!j.ok){ avisoPopup(j.erro || "Não foi possível concluir."); return; }
  await peCarregar(nomeSafeAtual); cicloRerender();
}
```

- [ ] **Step 3: Handler de revisão (com relatório obrigatório)**

```javascript
async function peRevisao(codigo, inputRelatorio){
  const f = inputRelatorio.files[0];
  if(!f){ avisoPopup("Anexe o relatório complementar (obrigatório)."); return; }
  if(!await confirmarPopup("A revisão reabre esta e as fases seguintes do PE. Continuar?")) return;
  const cred = await pedirCredenciaisGerente();   // senha gerencial
  if(!cred) return;
  const fd = new FormData();
  fd.append("arquivo", f); fd.append("login", cred.login); fd.append("senha", cred.senha);
  const r = await fetch(`/api/projetos/${encodeURIComponent(nomeSafeAtual)}/ciclo/${codigo}/revisao`, {method:"POST", body:fd});
  const j = await r.json();
  if(!j.ok){ avisoPopup(j.erro || "Falha na revisão."); return; }
  avisoPopup("Revisão registrada. Fases reabertas: " + (j.resetadas||[]).join(", "));
  await peCarregar(nomeSafeAtual); cicloRerender();
}
```

(`pedirCredenciaisGerente`, `avisoPopup`, `confirmarPopup` já existem no front — reusar. `cicloRerender` = a função que redesenha o painel de Ciclo; usar o nome real do projeto.)

- [ ] **Step 2..4: Verificação manual + sintaxe**

Run: `node --check` no script extraído.
Manual, por perfil: Projetista/Conferente carregam e concluem; consultor não vê os botões de ação; Gerente abre revisão e vê as fases reabrirem; downloads abrem as versões corretas.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(pe): acoes de upload, conclusao e revisao no frontend"
```

---

## Task 10: Documentação

**Files:**
- Modify: `docs/USUARIOS.md` (novas capabilities `executar_pe`/`revisar_pe`), `DEV_LOG.md` (nova sessão), spec (marcar como implementado)

- [ ] **Step 1: `docs/USUARIOS.md`** — documentar que `executar_pe` (Projetista Executivo, Conferente, Gerente de Vendas, Gerente Adm/Financeiro, Diretor) e `revisar_pe` (Gerente de Vendas, Gerente Adm/Financeiro, Diretor) passam a existir.

- [ ] **Step 2: `DEV_LOG.md`** — adicionar `## Sessão N — Subfases do Projeto Executivo` com [ESTADO]/[DECIDIDO]/[ARQUIVOS], e atualizar o `RESUMO ATUAL`/`ESTADO ATUAL`.

- [ ] **Step 3: Spec** — no cabeçalho de `docs/superpowers/specs/2026-07-04-projeto-executivo-subfases-design.md`, trocar o status para **implementado (Sessão N)**.

- [ ] **Step 4: Suíte verde + commit**

Run: `python3 -m pytest -q`
Expected: tudo verde.

```bash
git add docs/USUARIOS.md DEV_LOG.md docs/superpowers/specs/2026-07-04-projeto-executivo-subfases-design.md
git commit -m "docs: subfases do Projeto Executivo (capabilities, DEV_LOG, spec)"
```

- [ ] **Step 5: Re-ingestão do grafo MCP** (ritual de fechar frente)

Após mergear na `main` e `git push`, re-ingerir: tool `ingerir` com `fonte: "all"`.

---

## Self-Review (feito pelo autor do plano)

**Cobertura do spec:**
- Modelo B (2 tabelas + status no CicloEtapa) → Tasks 2, 7. ✔
- Capabilities executar_pe/revisar_pe → Task 1 (resolve a ambiguidade `autorizar` vs adm_fin). ✔
- Upload append-only → Tasks 4, 7 (teste de 2 versões). ✔
- Guardas de conclusão + 11e conclui etapa 11 → Tasks 3, 5. ✔
- Revisão cascata + relatório obrigatório + senha gerencial → Task 6. ✔
- Medição inviolável → Task 7 (asserção de diretório intocado). ✔
- Monitoramento/progresso → Tasks 7, 8. ✔
- Erros (400/401/403/404) → cobertos nos endpoints e testes. ✔

**Placeholders:** nenhum — todo passo tem código/comando concretos. Pontos que dependem de nomes reais do
front (`pedirCredenciaisGerente`, `cicloRerender`, `usuarioAtual.pode`, `nomeSafeAtual`) estão marcados
para o implementador confirmar contra `static/index.html`.

**Consistência de tipos:** `tipo_doc_de`, `guarda_conclusao`, `versao_atual`, `SUBFASES_PE`,
`CicloDocumento`, `CicloRevisao`, `CicloEtapa` usados com os mesmos nomes/assinaturas em todas as tasks.
