# Workflow de Medição (Sub-projeto 4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o fluxo de medição — etapa 9 (upload da solicitação + senha do medidor) e etapa 10 "Medição" (parecer Aprovado/Reprovado/Parcial + planta promob; Reprovado em 2 passos com documento do cliente + senha gerencial), com armazenamento de arquivos e auditoria.

**Architecture:** Capacidades novas em `perfis.py`; validação pura em `mod_medicao.py`; modelo `Medicao` (1 por projeto) em `database.py`; endpoints dedicados em `main.py` (upload multipart binário + gate por credenciais + conclusão das etapas do ciclo) com um parser multipart binário próprio; cards dedicados no frontend.

**Tech Stack:** Python (pytest p/ funções puras), stdlib http.server + email (multipart), SQLAlchemy; HTML/JS vanilla (FormData). Endpoints verificados via API real (curl), no estilo do projeto.

---

## File Structure

- **Modificar** `perfis.py` — flags `registrar_medicao` e `aprovar_medicao_reprovada`.
- **Criar** `mod_medicao.py` — `PARECERES` + `validar_parecer`.
- **Modificar** `database.py` — modelo `Medicao`.
- **Modificar** `mod_ciclo.py` — renomear etapa 10 → "Medição".
- **Modificar** `main.py` — `_parse_multipart_arquivos`, `_usuario_com_capacidade`, endpoints de medição, guard no PATCH `/ciclo/9|10`.
- **Modificar** `static/index.html` — renomear etapa 10 + cards de medição (9 e 10) + JS.

> Backend puro = TDD (pytest). Endpoints/frontend = implementar → verificar via API real (curl multipart)/inspeção. Rodar `python -m pytest -q` ao fim de cada tarefa de backend.

---

## Task 1: `perfis.py` — capacidades de medição

**Files:** Modify `perfis.py`; Test `tests/test_perfis.py`

- [ ] **Step 1: Teste (TDD)** — acrescentar a `tests/test_perfis.py`:

```python
def test_capacidades_medicao():
    assert perfis.pode("medidor", "registrar_medicao") is True
    assert perfis.pode("diretor", "registrar_medicao") is True
    assert perfis.pode("gerente_vendas", "registrar_medicao") is False
    assert perfis.pode("consultor", "registrar_medicao") is False
    # exceção do reprovado: vendas + adm_fin + diretor
    assert perfis.pode("gerente_vendas", "aprovar_medicao_reprovada") is True
    assert perfis.pode("gerente_adm_fin", "aprovar_medicao_reprovada") is True
    assert perfis.pode("diretor", "aprovar_medicao_reprovada") is True
    assert perfis.pode("medidor", "aprovar_medicao_reprovada") is False
    assert perfis.pode("consultor", "aprovar_medicao_reprovada") is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_perfis.py::test_capacidades_medicao -v` → FAIL.

- [ ] **Step 3: Implementar** — em `perfis.py`, adicionar as duas flags a cada perfil e ao `_DEFAULT`:
- `registrar_medicao`: True só em `medidor` e `diretor`.
- `aprovar_medicao_reprovada`: True só em `gerente_vendas`, `gerente_adm_fin`, `diretor`.
- `_DEFAULT`: ambas `False`.

Exemplo (linhas relevantes):
```python
    "diretor":          {..., "aprovar_financeiro": True,  "registrar_medicao": True,  "aprovar_medicao_reprovada": True},
    "gerente_vendas":   {..., "aprovar_financeiro": False, "registrar_medicao": False, "aprovar_medicao_reprovada": True},
    "gerente_adm_fin":  {..., "aprovar_financeiro": True,  "registrar_medicao": False, "aprovar_medicao_reprovada": True},
    "medidor":          {..., "aprovar_financeiro": False, "registrar_medicao": True,  "aprovar_medicao_reprovada": False},
```
(Para os demais perfis — consultor, assistente_logistico, conferente, supervisor_montagem, assistente_administrativo, projetista_executivo — adicionar `"registrar_medicao": False, "aprovar_medicao_reprovada": False`.) E `_DEFAULT` recebe `"registrar_medicao": False, "aprovar_medicao_reprovada": False`.

- [ ] **Step 4: Testes** — `python -m pytest tests/test_perfis.py -q` → PASS; `python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add perfis.py tests/test_perfis.py
git commit -m "feat(perfis): capacidades registrar_medicao e aprovar_medicao_reprovada"
```

---

## Task 2: `mod_medicao.py` — validação de parecer

**Files:** Create `mod_medicao.py`; Test `tests/test_medicao.py`

- [ ] **Step 1: Teste (TDD)** — criar `tests/test_medicao.py`:

```python
import mod_medicao as mm


def test_pareceres():
    assert mm.PARECERES == {"aprovado", "reprovado", "parcial"}


def test_validar_parecer_ok():
    assert mm.validar_parecer("aprovado", "") == []
    assert mm.validar_parecer("reprovado", "") == []
    assert mm.validar_parecer("parcial", "Cozinha, Dormitório") == []


def test_validar_parecer_invalido():
    erros = mm.validar_parecer("talvez", "")
    assert any("parecer" in e.lower() for e in erros)


def test_validar_parcial_exige_ambientes():
    erros = mm.validar_parecer("parcial", "   ")
    assert any("ambiente" in e.lower() for e in erros)
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_medicao.py -v` → FAIL (`No module named 'mod_medicao'`).

- [ ] **Step 3: Implementar** — criar `mod_medicao.py`:

```python
# -*- coding: utf-8 -*-
"""mod_medicao.py — Validações (puras) do parecer de medição."""

PARECERES = {"aprovado", "reprovado", "parcial"}


def validar_parecer(parecer, ambientes_aprovados):
    """Lista de erros (vazia se ok). 'parcial' exige ambientes_aprovados não vazio."""
    erros = []
    p = (parecer or "").strip().lower()
    if p not in PARECERES:
        erros.append("Parecer inválido (use aprovado, reprovado ou parcial).")
    if p == "parcial" and not (ambientes_aprovados or "").strip():
        erros.append("Informe os ambientes aprovados para parecer parcial.")
    return erros
```

- [ ] **Step 4: Testes** — `python -m pytest tests/test_medicao.py -q` → PASS; `python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add mod_medicao.py tests/test_medicao.py
git commit -m "feat(medicao): validador puro de parecer"
```

---

## Task 3: `database.py` modelo `Medicao` + renomear etapa 10

**Files:** Modify `database.py`, `mod_ciclo.py`; Test `tests/test_medicao.py`, `tests/test_ciclo.py`

- [ ] **Step 1: Testes (TDD)** — acrescentar a `tests/test_medicao.py`:

```python
def test_modelo_medicao_campos():
    from database import Medicao
    m = Medicao(projeto_nome="p", parecer="aprovado")
    assert m.projeto_nome == "p"
    assert m.parecer == "aprovado"
    # campos existem (default None até persistir)
    for c in ["solicitacao_arquivo", "planta_arquivo", "doc_cliente_arquivo",
              "ambientes_aprovados", "medidor_id", "excecao_por", "solicitacao_por"]:
        assert hasattr(m, c)
```
E a `tests/test_ciclo.py`:
```python
def test_etapa10_renomeada_medicao():
    assert mc.ETAPA_NOME["10"] == "Medição"
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_medicao.py::test_modelo_medicao_campos tests/test_ciclo.py::test_etapa10_renomeada_medicao -v` → FAIL.

- [ ] **Step 3: Modelo `Medicao`** — em `database.py`, adicionar (perto dos outros modelos, depois de `CicloEtapa`/`Contrato`):

```python
class Medicao(Base):
    """Dados de medição por projeto (etapas 9 e 10 do ciclo)."""
    __tablename__ = "medicoes"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    projeto_nome        = Column(String(200), nullable=False, unique=True)
    # Etapa 9 — solicitação
    solicitacao_arquivo = Column(String(255), nullable=True)
    solicitacao_por     = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    solicitacao_em      = Column(DateTime, nullable=True)
    # Etapa 10 — parecer + planta
    parecer             = Column(String(20), nullable=True)   # aprovado|reprovado|parcial
    ambientes_aprovados = Column(Text, nullable=True)
    planta_arquivo      = Column(String(255), nullable=True)
    medidor_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    medicao_em          = Column(DateTime, nullable=True)
    # Reprovado — decisão comercial
    doc_cliente_arquivo = Column(String(255), nullable=True)
    excecao_por         = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    excecao_em          = Column(DateTime, nullable=True)
```
(O `init_db`/`create_all` cria a tabela nova automaticamente; sem migração de dados.)

- [ ] **Step 4: Renomear etapa 10** — em `mod_ciclo.py`, no dict `ETAPA_NOME`, trocar `"10": "Planta de pontos medidos"` por `"10": "Medição"`.

- [ ] **Step 5: Testes** — `python -m pytest tests/test_medicao.py tests/test_ciclo.py -q` → PASS; `python -m pytest -q` → PASS.

- [ ] **Step 6: Commit**
```bash
git add database.py mod_ciclo.py tests/test_medicao.py tests/test_ciclo.py
git commit -m "feat(medicao): modelo Medicao + renomeia etapa 10 para Medicao"
```

---

## Task 4: `main.py` — helpers, GET /medicao e guard do PATCH 9/10

**Files:** Modify `main.py`

> Verificação via API na Task 7. Já importados em `main.py`: `perfis`, `mod_ciclo`, `Usuario`, `CicloEtapa`, `LogAcaoGerencial`, `get_session`, `get_usuario_sessao`, `datetime`, `re`/`_re`, `json`, `unquote`, `os`, `storage_salvar_binario`, `storage_ler_binario`, `_projeto_path`. Adicionar `import mod_medicao` e `from database import Medicao` (no bloco de imports do database).

- [ ] **Step 1: Parser multipart binário + helper de credencial+capacidade**

Adicionar em `main.py` (perto de `_parse_multipart`):

```python
def _parse_multipart_arquivos(body, ct):
    """Multipart binário: retorna (arquivos, campos) onde arquivos[name] = (filename, bytes)
    e campos[name] = texto. Diferente de _parse_multipart (que é específico p/ XML texto)."""
    raw = b"Content-Type: " + ct.encode() + b"\r\n\r\n" + body
    msg = email.message_from_bytes(raw, policy=_email_policy.compat32)
    arquivos, campos = {}, {}
    for part in msg.walk():
        cd = part.get("Content-Disposition", "")
        if not cd:
            continue
        params = {}
        for seg in cd.split(";"):
            seg = seg.strip()
            if "=" in seg:
                k, v = seg.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        nome = params.get("name", "")
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        if params.get("filename"):
            arquivos[nome] = (params["filename"], payload)
        elif nome:
            campos[nome] = payload.decode("utf-8", "ignore").strip()
    return arquivos, campos


def _usuario_com_capacidade(db, login, senha, capacidade):
    """Usuario ativo com senha correta e a capacidade dada (perfis), ou None."""
    u = db.query(Usuario).filter_by(login=(login or "").strip()).first()
    if not u or not u.ativo or not u.check_senha(senha or ""):
        return None
    if not perfis.pode(u.nivel, capacidade):
        return None
    return u
```

> NOTA: substituir o `_aprovador_financeiro` por `_usuario_com_capacidade(db, login, senha, "aprovar_financeiro")` é opcional (fora de escopo); deixe `_aprovador_financeiro` como está.

- [ ] **Step 2: Guard no PATCH `/ciclo/<codigo>` para 9/10**

Localizar o handler `^/api/projetos/([^/]+)/ciclo/([^/]+)$`. Logo após obter `novo_status` (e antes do bloco de gating), inserir:

```python
                    if novo_status in mod_ciclo.STATUS_CONCLUSIVOS and etapa_cod in ("9", "10"):
                        self.send_json({"ok": False, "erro": "Use o fluxo de Medição para concluir esta etapa."}, code=400)
                        return
```

- [ ] **Step 3: GET /api/projetos/<nome>/medicao**

No `do_GET`, adicionar (perto das rotas `/api/projetos/.../ciclo`):

```python
            m = _re.match(r'^/api/projetos/([^/]+)/medicao$', path)
            if m:
                nome_safe = unquote(m.group(1))
                if not get_usuario_sessao(self):
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    if not md:
                        self.send_json({"ok": True, "medicao": None}); return
                    self.send_json({"ok": True, "medicao": {
                        "parecer": md.parecer, "ambientes_aprovados": md.ambientes_aprovados or "",
                        "tem_solicitacao": bool(md.solicitacao_arquivo),
                        "tem_planta": bool(md.planta_arquivo),
                        "tem_doc_cliente": bool(md.doc_cliente_arquivo),
                    }})
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Sanity**

Run: `python -c "import main; print('main OK')"` → `main OK`.
Run: `python -m pytest -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add main.py
git commit -m "feat(medicao): parser multipart binario, helper de capacidade, GET /medicao e guard PATCH 9/10"
```

---

## Task 5: `main.py` — endpoints POST de medição + servir arquivos

**Files:** Modify `main.py`

- [ ] **Step 1: Helper para concluir/atualizar etapa do ciclo**

Adicionar em `main.py` (perto de `_usuario_com_capacidade`):

```python
def _set_etapa_status(db, nome_safe, codigo, status, responsavel_id):
    etapa = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe, etapa_codigo=codigo).first()
    if not etapa:
        etapa = CicloEtapa(projeto_nome=nome_safe, etapa_codigo=codigo)
        db.add(etapa)
    if etapa.status == "pendente" and status != "pendente":
        etapa.iniciado_em = datetime.utcnow()
    etapa.status = status
    if status in mod_ciclo.STATUS_CONCLUSIVOS:
        etapa.concluido_em = datetime.utcnow()
        etapa.responsavel_id = responsavel_id
    return etapa


def _get_or_create_medicao(db, nome_safe):
    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
    if not md:
        md = Medicao(projeto_nome=nome_safe)
        db.add(md)
    return md
```

- [ ] **Step 2: POST /medicao/solicitacao (etapa 9)**

No `do_POST`, adicionar:

```python
        m = _re.match(r'^/api/projetos/([^/]+)/medicao/solicitacao$', path)
        if m:
            nome_safe = unquote(m.group(1))
            if not get_usuario_sessao(self):
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
            db = get_session()
            try:
                u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao")
                if not u:
                    self.send_json({"ok": False, "erro": "Confirmação exige login+senha do Medidor (ou Diretor)."}, code=403); return
                if "arquivo" not in arquivos:
                    self.send_json({"ok": False, "erro": "Anexe o arquivo de solicitação de medição."}); return
                fname, data = arquivos["arquivo"]
                destino = os.path.join(_projeto_path(nome_safe), "medicao", "solicitacao_" + os.path.basename(fname))
                storage_salvar_binario(destino, data)
                md = _get_or_create_medicao(db, nome_safe)
                md.solicitacao_arquivo = os.path.basename(destino)
                md.solicitacao_por = u.id
                md.solicitacao_em = datetime.utcnow()
                _set_etapa_status(db, nome_safe, "9", "concluido", u.id)
                db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                        acao="medicao_solicitacao", projeto_nome=nome_safe, etapa_alvo="9"))
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return
```

- [ ] **Step 3: POST /medicao/parecer (etapa 10)**

```python
        m = _re.match(r'^/api/projetos/([^/]+)/medicao/parecer$', path)
        if m:
            nome_safe = unquote(m.group(1))
            if not get_usuario_sessao(self):
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
            parecer = (campos.get("parecer","") or "").strip().lower()
            ambientes = campos.get("ambientes_aprovados","")
            erros = mod_medicao.validar_parecer(parecer, ambientes)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)}); return
            db = get_session()
            try:
                u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "registrar_medicao")
                if not u:
                    self.send_json({"ok": False, "erro": "Registro exige login+senha do Medidor (ou Diretor)."}, code=403); return
                if "planta" not in arquivos:
                    self.send_json({"ok": False, "erro": "Anexe o arquivo promob da Planta de Pontos Medidos."}); return
                fname, data = arquivos["planta"]
                destino = os.path.join(_projeto_path(nome_safe), "medicao", "planta_" + os.path.basename(fname))
                storage_salvar_binario(destino, data)
                md = _get_or_create_medicao(db, nome_safe)
                md.planta_arquivo = os.path.basename(destino)
                md.parecer = parecer
                md.ambientes_aprovados = ambientes.strip() if parecer == "parcial" else None
                md.medidor_id = u.id
                md.medicao_em = datetime.utcnow()
                if parecer in ("aprovado", "parcial"):
                    _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                else:  # reprovado → aguardando decisão comercial
                    _set_etapa_status(db, nome_safe, "10", "em_andamento", u.id)
                db.add(LogAcaoGerencial(solicitante_id=u.id, autorizador_id=u.id,
                        acao="medicao_parecer_" + parecer, projeto_nome=nome_safe, etapa_alvo="10"))
                db.commit()
                self.send_json({"ok": True, "parecer": parecer})
            finally:
                db.close()
            return
```

- [ ] **Step 4: POST /medicao/decisao-reprovado (2º passo do reprovado)**

```python
        m = _re.match(r'^/api/projetos/([^/]+)/medicao/decisao-reprovado$', path)
        if m:
            nome_safe = unquote(m.group(1))
            solicitante = get_usuario_sessao(self)
            if not solicitante:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
            db = get_session()
            try:
                md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                if not md or md.parecer != "reprovado":
                    self.send_json({"ok": False, "erro": "Só aplicável a uma medição com parecer Reprovado."}); return
                u = _usuario_com_capacidade(db, campos.get("login",""), campos.get("senha",""), "aprovar_medicao_reprovada")
                if not u:
                    self.send_json({"ok": False, "erro": "Liberação exige login+senha de Gerente de Vendas, Gerente Adm/Financeiro ou Diretor."}, code=403); return
                if "doc_cliente" not in arquivos:
                    self.send_json({"ok": False, "erro": "Anexe o documento de aprovação do cliente."}); return
                fname, data = arquivos["doc_cliente"]
                destino = os.path.join(_projeto_path(nome_safe), "medicao", "doc_cliente_" + os.path.basename(fname))
                storage_salvar_binario(destino, data)
                md.doc_cliente_arquivo = os.path.basename(destino)
                md.excecao_por = u.id
                md.excecao_em = datetime.utcnow()
                _set_etapa_status(db, nome_safe, "10", "concluido", u.id)
                db.add(LogAcaoGerencial(solicitante_id=solicitante["id"], autorizador_id=u.id,
                        acao="medicao_excecao_reprovado", projeto_nome=nome_safe, etapa_alvo="10"))
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return
```

- [ ] **Step 5: GET servir arquivo de medição**

No `do_GET`, adicionar:
```python
            m = _re.match(r'^/api/projetos/([^/]+)/medicao/arquivo/(solicitacao|planta|doc_cliente)$', path)
            if m:
                nome_safe = unquote(m.group(1)); tipo = m.group(2)
                if not get_usuario_sessao(self):
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    md = db.query(Medicao).filter_by(projeto_nome=nome_safe).first()
                    fname = md and getattr(md, tipo + "_arquivo", None)
                finally:
                    db.close()
                if not fname:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                caminho = os.path.join(_projeto_path(nome_safe), "medicao", fname)
                try:
                    data = storage_ler_binario(caminho)
                except Exception:
                    self.send_json({"ok": False, "erro": "Arquivo não encontrado"}, code=404); return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", len(data))
                self.send_header("Content-Disposition", 'attachment; filename="%s"' % fname)
                self.end_headers()
                self.wfile.write(data)
                return
```

- [ ] **Step 6: Sanity** — `python -c "import main; print('main OK')"` → OK; `python -m pytest -q` → PASS.

- [ ] **Step 7: Commit**
```bash
git add main.py
git commit -m "feat(medicao): endpoints solicitacao/parecer/decisao-reprovado + servir arquivos"
```

---

## Task 6: Frontend — cards de medição (etapas 9 e 10)

**Files:** Modify `static/index.html`

- [ ] **Step 1: Renomear etapa 10 no ETAPAS_CICLO**

Grep `codigo: "10"`. Trocar `nome: "Planta de pontos medidos"` por `nome: "Medição"`.

- [ ] **Step 2: Dispatch dos cards 9 e 10**

No dispatch do corpo do card (onde hoje há `etapa.acao === 'contrato' ? ... : (etapa.codigo === '8' || etapa.codigo === '11d') ? _renderCardAprovacaoFinanceira(...) : _renderCardGenerico(...)`), adicionar antes do genérico:
```javascript
            : etapa.codigo === '9'
              ? _renderCardSolicitacaoMedicao(dados, bloqueada)
            : etapa.codigo === '10'
              ? _renderCardMedicao(dados, bloqueada)
```
(encadear mantendo a estrutura ternária existente; o `_renderCardGenerico(...)` continua sendo o último ramo).

- [ ] **Step 3: Funções de render + ações (JS)**

Adicionar (perto de `concluirAprovacaoFinanceira`):

```javascript
let _medicaoCache = null;
async function _carregarMedicao() {
  try {
    const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/medicao`, {credentials:'same-origin'});
    const d = await r.json();
    _medicaoCache = d.ok ? d.medicao : null;
  } catch(e) { _medicaoCache = null; }
}

function _renderCardSolicitacaoMedicao(dados, bloqueada) {
  if (dados.status === 'concluido')
    return `<p style="color:var(--ok);margin:0">&#x2713; Solicitação de medição confirmada.</p>`;
  if (bloqueada)
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior.</p>`;
  return `
    <p style="color:var(--muted);font-size:.85rem;margin:0 0 10px">Anexe o arquivo de solicitação e confirme com a senha do medidor.</p>
    <input type="file" id="med-solic-file" style="font-size:.82rem;margin-bottom:10px"><br>
    <button onclick="enviarSolicitacaoMedicao()" style="background:#b8960c;color:#000;border:none;border-radius:6px;padding:8px 18px;font-weight:700;cursor:pointer">&#x2713; Confirmar (medidor)</button>`;
}

async function enviarSolicitacaoMedicao() {
  const f = document.getElementById('med-solic-file')?.files[0];
  if (!f) { await avisoPopup('Selecione o arquivo de solicitação.', {titulo:'Medição'}); return; }
  const cred = await pedirCredenciaisGerente({titulo:'Solicitação de Medição', mensagem:'Login e senha do Medidor (ou Diretor).'});
  if (!cred) return;
  const fd = new FormData();
  fd.append('arquivo', f); fd.append('login', cred.login); fd.append('senha', cred.senha);
  const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/medicao/solicitacao`, {method:'POST', credentials:'same-origin', body: fd});
  const d = await r.json();
  if (!d.ok) { await avisoPopup(d.erro || 'Falha', {titulo:'Medição'}); return; }
  showToast('Solicitação de medição confirmada!', false);
  await carregarCiclo();
}

function _renderCardMedicao(dados, bloqueada) {
  if (dados.status === 'concluido')
    return `<p style="color:var(--ok);margin:0 0 10px">&#x2713; Medição concluída${_medicaoCache?.parecer ? ' (' + _medicaoCache.parecer + ')' : ''}.</p>
      <button onclick="abrirModalReabrir('10')" style="border:1px solid var(--muted);color:var(--muted);background:none;border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer">🔓 Reabrir (gerente)</button>`;
  if (bloqueada)
    return `<p style="color:var(--muted);font-size:.85rem;margin:0">🔒 Conclua a etapa anterior.</p>`;
  // Reprovado aguardando decisão comercial (2º passo)
  if (_medicaoCache && _medicaoCache.parecer === 'reprovado') {
    return `
      <p style="color:var(--warn,#c8a84b);margin:0 0 10px">Medição <strong>Reprovada</strong> — aguardando decisão comercial.</p>
      <p style="color:var(--muted);font-size:.82rem;margin:0 0 8px">Anexe o documento de aprovação do cliente e libere com senha de Gerente de Vendas/Adm-Fin/Diretor.</p>
      <input type="file" id="med-doc-file" style="font-size:.82rem;margin-bottom:10px"><br>
      <button onclick="enviarDecisaoReprovado()" style="background:#b8960c;color:#000;border:none;border-radius:6px;padding:8px 18px;font-weight:700;cursor:pointer">Liberar (decisão comercial)</button>`;
  }
  return `
    <p style="color:var(--muted);font-size:.85rem;margin:0 0 8px">Registre o parecer da medição, anexe a planta promob e confirme com a senha do medidor.</p>
    <label style="font-size:.82rem">Parecer:
      <select id="med-parecer" onchange="document.getElementById('med-ambientes-wrap').style.display = this.value==='parcial' ? 'block':'none'">
        <option value="aprovado">Aprovado</option>
        <option value="reprovado">Reprovado</option>
        <option value="parcial">Aprovado Parcialmente</option>
      </select></label>
    <div id="med-ambientes-wrap" style="display:none;margin-top:8px">
      <textarea id="med-ambientes" placeholder="Ambientes aprovados..." style="width:100%;box-sizing:border-box;font-size:.82rem;min-height:48px"></textarea>
    </div>
    <div style="margin-top:8px"><input type="file" id="med-planta-file" style="font-size:.82rem"></div>
    <button onclick="enviarParecerMedicao()" style="margin-top:10px;background:#b8960c;color:#000;border:none;border-radius:6px;padding:8px 18px;font-weight:700;cursor:pointer">Registrar parecer (medidor)</button>`;
}

async function enviarParecerMedicao() {
  const parecer = document.getElementById('med-parecer')?.value;
  const ambientes = document.getElementById('med-ambientes')?.value || '';
  const f = document.getElementById('med-planta-file')?.files[0];
  if (!f) { await avisoPopup('Anexe a planta promob.', {titulo:'Medição'}); return; }
  const cred = await pedirCredenciaisGerente({titulo:'Parecer da Medição', mensagem:'Login e senha do Medidor (ou Diretor).'});
  if (!cred) return;
  const fd = new FormData();
  fd.append('planta', f); fd.append('parecer', parecer); fd.append('ambientes_aprovados', ambientes);
  fd.append('login', cred.login); fd.append('senha', cred.senha);
  const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/medicao/parecer`, {method:'POST', credentials:'same-origin', body: fd});
  const d = await r.json();
  if (!d.ok) { await avisoPopup(d.erro || 'Falha', {titulo:'Medição'}); return; }
  showToast(d.parecer === 'reprovado' ? 'Parecer registrado: Reprovado (aguardando decisão).' : 'Medição registrada!', false);
  await carregarCiclo();
}

async function enviarDecisaoReprovado() {
  const f = document.getElementById('med-doc-file')?.files[0];
  if (!f) { await avisoPopup('Anexe o documento de aprovação do cliente.', {titulo:'Medição'}); return; }
  const cred = await pedirCredenciaisGerente({titulo:'Decisão Comercial', mensagem:'Login e senha de Gerente de Vendas, Adm/Financeiro ou Diretor.'});
  if (!cred) return;
  const fd = new FormData();
  fd.append('doc_cliente', f); fd.append('login', cred.login); fd.append('senha', cred.senha);
  const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/medicao/decisao-reprovado`, {method:'POST', credentials:'same-origin', body: fd});
  const d = await r.json();
  if (!d.ok) { await avisoPopup(d.erro || 'Falha', {titulo:'Medição'}); return; }
  showToast('Medição liberada (decisão comercial registrada).', false);
  await carregarCiclo();
}
```

- [ ] **Step 4: Carregar a medição ao renderizar o ciclo**

Em `renderCiclo()` (ou em `carregarCiclo`, antes de `renderCiclo`), garantir que `_carregarMedicao()` é chamado quando o projeto está nas etapas 9/10. Forma simples: em `carregarCiclo`, após `_fetchCiclo()` e antes de `renderCiclo()`, adicionar `await _carregarMedicao();`. (Localize `async function carregarCiclo()` e insira a chamada.)

- [ ] **Step 5: Sanity**

Run: `python -c "h=open('static/index.html',encoding='utf-8').read(); print('cards:', h.count('function _renderCardMedicao'), h.count('function _renderCardSolicitacaoMedicao')); print('Medição rename:', 'nome: \"Medição\"' in h or 'Medição' in h); print('acoes:', all(fn in h for fn in ['enviarSolicitacaoMedicao','enviarParecerMedicao','enviarDecisaoReprovado','_carregarMedicao']))"`
Expect: `1 1`, `True`, `True`. Ler ~6 linhas em torno do dispatch e do `carregarCiclo` para confirmar JS válido.

- [ ] **Step 6: Commit**
```bash
git add static/index.html
git commit -m "feat(medicao-front): cards de solicitacao e medicao (upload + parecer + 2 passos reprovado)"
```

---

## Task 7: Verificação integrada (API real) + DEV_LOG

**Files:** nenhuma alteração de código; corrigir inline se algo falhar.

- [ ] **Step 1: Suíte completa** — `python -m pytest -q` → PASS.

- [ ] **Step 2: Setup do ciclo de teste** — para um projeto `zz_med` com etapas 1–8 concluídas (para a 9 liberar):
```bash
python -c "
from database import get_session, CicloEtapa, Medicao
from datetime import datetime
db=get_session()
db.query(CicloEtapa).filter_by(projeto_nome='zz_med').delete()
db.query(Medicao).filter_by(projeto_nome='zz_med').delete()
for c in ['1','2','3','4','5','6','7','8']:
    db.add(CicloEtapa(projeto_nome='zz_med', etapa_codigo=c, status='concluido', concluido_em=datetime.utcnow()))
db.commit(); db.close(); print('setup ok')
"
```

- [ ] **Step 3: Verificação via curl (multipart)** — subir o servidor, logar (ex.: `pdm2026`), e:
  1. **Etapa 9:** `POST /medicao/solicitacao` com um arquivo + `login=med2026&senha=teste012` (medidor) → ok; etapa 9 concluída. Com `login=mds2026` (consultor) → 403.
  2. **Etapa 10 aprovado:** `POST /medicao/parecer` com planta + `parecer=aprovado` + medidor → ok; etapa 10 concluída.
  3. **Parcial sem ambientes:** `parecer=parcial` sem `ambientes_aprovados` → erro de validação.
  4. **Reprovado (2 passos):** resetar a medição/etapa 10; `parecer=reprovado` + medidor → ok, etapa 10 `em_andamento`; `POST /medicao/decisao-reprovado` com doc + `login=lds2026` (vendas) → ok, etapa 10 concluída; com medidor (`med2026`) → 403.
  5. **Guard:** `PATCH /ciclo/9 {status:'concluido'}` (sem fluxo de medição) → 400.
  6. **Auditoria:** conferir `log_acoes_gerenciais` com `acao` começando por `medicao_`.
  (Exemplo de curl multipart: `curl -s -b CK -F "arquivo=@arquivo.txt" -F "login=med2026" -F "senha=teste012" URL`.)

- [ ] **Step 4: Cleanup** — remover etapas/medição/logs do `zz_med` e a pasta `PROJETOS/zz_med/`.

- [ ] **Step 5: DEV_LOG.md** — adicionar a entrada do sub-projeto 4 (workflow de medição).

- [ ] **Step 6: Commit**
```bash
git add DEV_LOG.md
git commit -m "docs: atualiza DEV_LOG (sub-projeto 4 — workflow de medicao)"
```

---

## Self-Review (cobertura do spec)

- **Capacidades `registrar_medicao` e `aprovar_medicao_reprovada`** → Task 1. ✓
- **Validador de parecer (parcial exige ambientes)** → Task 2. ✓
- **Modelo `Medicao` + renomear etapa 10 "Medição"** → Task 3. ✓
- **Parser multipart binário, helper de capacidade, GET /medicao, guard PATCH 9/10** → Task 4. ✓
- **Endpoints solicitação/parecer/decisão-reprovado + servir arquivos + auditoria** → Task 5. ✓
- **Frontend: cards 9 e 10, upload, parecer, ambientes (parcial), 2 passos do reprovado** → Task 6. ✓
- **Verificação pytest + API real + DEV_LOG** → Task 7. ✓
- **Consistência de nomes:** `registrar_medicao`, `aprovar_medicao_reprovada`, `validar_parecer`, `Medicao`, `_parse_multipart_arquivos`, `_usuario_com_capacidade`, `_set_etapa_status`, `_get_or_create_medicao`, endpoints `/medicao/{solicitacao,parecer,decisao-reprovado,arquivo/<tipo>}`, `_renderCardSolicitacaoMedicao`/`_renderCardMedicao`, `enviarSolicitacaoMedicao`/`enviarParecerMedicao`/`enviarDecisaoReprovado`/`_carregarMedicao` — idênticos entre tarefas.
- **Sem placeholders.** Reprovado em 2 passos (parecer → em_andamento; decisao-reprovado → concluido).
