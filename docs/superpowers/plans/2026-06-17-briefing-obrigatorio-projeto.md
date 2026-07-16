# Briefing Obrigatório Por-Projeto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o briefing por-projeto e obrigatório: depois de criar o projeto, o consultor preenche o briefing daquele projeto antes de negociar; o backend bloqueia negociação (orcamentos/pool) sem os campos obrigatórios.

**Architecture:** A tabela `Briefing` já tem a coluna `projeto_nome` (modelo + DB dev); adiciona-se um safety-net de migração. Novos endpoints `GET/POST /api/projetos/<nome>/briefing` operam por-projeto e marcam a etapa 3 só daquele projeto; o endpoint de cliente deixa de marcar etapa 3. Um helper `_briefing_projeto_completo` alimenta o gate em orcamentos/pool. O frontend cria o projeto, abre o briefing do projeto (obrigatório) e só então vai à negociação.

**Tech Stack:** Python 3 `http.server` + SQLAlchemy + sqlite3 (migração raw); pytest; frontend HTML/CSS/JS vanilla (`static/index.html`, sem harness JS → verificação manual/Playwright).

**Spec:** `docs/superpowers/specs/ciclo/2026-06-17-briefing-obrigatorio-projeto-design.md`
**Branch:** `feat/briefing-obrigatorio-projeto` (já criada).

**Campos obrigatórios do briefing** (`_BRIEFING_OBRIGATORIOS`, main.py:2396): `tipo_imovel`, `budget_declarado`, `categoria_proposta`, `data_entrega_desejada`, `flexibilidade_prazo`. "Briefing OK" = os 5 preenchidos (`_briefing_dict(b)["completo"]`).

---

## File Structure

| Arquivo | Mudança |
|---|---|
| `database.py` | safety-net de migração: `projeto_nome` em `briefings` (idempotente) |
| `main.py` | `_briefing_projeto_completo`; `GET/POST /api/projetos/<nome>/briefing`; remove etapa-3 do endpoint de cliente; gate em `orcamentos`/`pool` |
| `static/index.html` | `criarProjeto` sem checagem prévia → abre briefing do projeto; `_bfProjetoNome` + `abrirBriefingProjeto`; `bfSalvar` por-projeto; aprovação usa briefing do projeto |
| `tests/test_briefing.py` | testes de `_briefing_projeto_completo` |

---

## Task 1: Backend — helper `_briefing_projeto_completo` + safety-net de migração

**Files:**
- Modify: `database.py` (`_migrar_colunas`, ~após o bloco `orcamentos` na linha ~377)
- Modify: `main.py` (novo helper após `_briefing_dict`, ~linha 2440)
- Test: `tests/test_briefing.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_briefing.py`:

```python
def test_briefing_projeto_completo_helper():
    import main
    from database import Briefing
    from datetime import datetime

    def mk(**kw):
        base = dict(cliente_id=1, projeto_nome="P", data_atendimento=datetime.utcnow(),
                    tipo_imovel="apto", budget_declarado=1000.0, categoria_proposta="x",
                    data_entrega_desejada="2026-12-01", flexibilidade_prazo="alta")
        base.update(kw)
        return Briefing(**base)

    class _Q:
        def __init__(self, r): self._r = r
        def filter_by(self, **k): return self
        def order_by(self, *a): return self
        def first(self): return self._r
    class _DB:
        def __init__(self, r): self._r = r
        def query(self, *a): return _Q(self._r)

    # com briefing completo -> True
    assert main._briefing_projeto_completo("P", _DB(mk())) is True
    # sem briefing (None) -> False
    assert main._briefing_projeto_completo("P", _DB(None)) is False
    # briefing com obrigatório faltando -> False
    assert main._briefing_projeto_completo("P", _DB(mk(budget_declarado=0.0))) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_briefing.py::test_briefing_projeto_completo_helper -v`
Expected: FAIL with `AttributeError: module 'main' has no attribute '_briefing_projeto_completo'`

- [ ] **Step 3: Implement the helper in `main.py`**

Add this function immediately AFTER `def _briefing_dict(b) -> dict:` (which ends at `return d`, ~line 2440):

```python
def _briefing_projeto_completo(nome_safe, db) -> bool:
    """True se o projeto tem um briefing POR-PROJETO com todos os obrigatórios
    preenchidos. Briefings legados (projeto_nome NULL) não são considerados."""
    b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
          .order_by(Briefing.id.desc()).first()
    if not b:
        return False
    return _briefing_dict(b)["completo"]
```

- [ ] **Step 4: Add the migration safety-net in `database.py`**

In `_migrar_colunas()`, after the `orcamentos` block (which ends ~line 377 with the `for col, tipo in [...]` loop and `if col not in orc_cols`), add a `briefings` block before `conn.commit()`:

```python
        # ── briefings ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(briefings)")
        bf_cols = {row[1] for row in cur.fetchall()}
        if "projeto_nome" not in bf_cols:
            cur.execute("ALTER TABLE briefings ADD COLUMN projeto_nome TEXT")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -X utf8 -m pytest tests/test_briefing.py -v`
Expected: PASS (existing + the new helper test)
Run: `python -c "import database; database.init_db(); import main; print('ok')"` → `ok`
Run: `python -X utf8 -m pytest tests/ -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add database.py main.py tests/test_briefing.py
git commit -m "feat(briefing): helper _briefing_projeto_completo + migracao projeto_nome (safety-net)"
```

---

## Task 2: Backend — endpoints por-projeto + remove etapa-3 do endpoint de cliente

**Files:**
- Modify: `main.py` — GET handler (~após linha 262, perto do GET de cliente); POST handler (~após o bloco do POST de cliente, linha ~1178); remoção em `main.py:1171-1172`

- [ ] **Step 1: Add `GET /api/projetos/<nome>/briefing`**

In `main.py`, in the GET dispatch (`do_GET`), immediately AFTER the client-briefing GET block (which ends with its `return` at ~line 262), add:

```python
        m = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m:
            nome_safe = unquote(m.group(1))
            db = get_session()
            try:
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return
```

- [ ] **Step 2: Add `POST /api/projetos/<nome>/briefing`**

In `main.py`, in the POST dispatch (`do_POST`), immediately AFTER the client-briefing POST block (the `m_bf = re.match(r"^/api/clientes/(\d+)/briefing$", ...)` handler that ends with its `finally: db.close()` at ~line 1178), add:

```python
        m_bp = re.match(r"^/api/projetos/([^/]+)/briefing$", path)
        if m_bp:
            nome_safe = unquote(m_bp.group(1))
            usuario   = get_usuario_sessao(self)
            req       = json.loads(body) if body else {}
            db        = get_session()
            try:
                p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                cliente_id = p_meta.cliente_id if p_meta else None
                if not cliente_id:
                    self.send_json({"ok": False, "erro": "Projeto sem cliente vinculado"})
                    return
                b = db.query(Briefing).filter_by(projeto_nome=nome_safe)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        projeto_nome=nome_safe,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                if bd["completo"]:
                    # Marca a etapa 3 (Briefing) SÓ deste projeto.
                    etapa3 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="3"
                    ).first()
                    if not etapa3:
                        etapa3 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="3")
                        db.add(etapa3)
                    etapa3.status        = "concluido"
                    etapa3.concluido_em  = datetime.utcnow()
                    etapa3.responsavel_id = usuario["id"] if usuario else None
                    db.commit()
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return
```

- [ ] **Step 3: Remove the etapa-3 marking from the client endpoint**

In `main.py`, in the client-briefing POST handler, find (currently ~lines 1170-1172):

```python
                bd = _briefing_dict(b)
                if bd["completo"]:
                    _marcar_etapa_cliente(cliente_id, "3", db, usuario)
                self.send_json({"ok": True, "briefing": bd})
```

Replace with (etapa 3 agora é por-projeto, não mais marcada por cliente):

```python
                bd = _briefing_dict(b)
                self.send_json({"ok": True, "briefing": bd})
```

- [ ] **Step 4: Verify**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax ok')"` → syntax ok
Run: `python -c "import main; print('import ok')"` → import ok
Run: `python -X utf8 -m pytest tests/ -q` → all pass.
Grep check: `re.match(r"^/api/projetos/([^/]+)/briefing$"` should appear twice (one GET in do_GET, one POST in do_POST). `_marcar_etapa_cliente(cliente_id, "3"` should have ZERO occurrences now.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(briefing): endpoints GET/POST /api/projetos/<nome>/briefing; etapa 3 por-projeto"
```

---

## Task 3: Backend — gate de negociação (orcamentos + pool)

**Files:**
- Modify: `main.py` — `POST /projetos/<nome>/orcamentos` (~1273); `POST /projetos/<nome>/pool` (~1314)

- [ ] **Step 1: Gate em `POST /projetos/<nome>/orcamentos`**

In `main.py`, find the orcamentos handler body (currently ~lines 1273-1276):

```python
            if m_novo_orc:
                nome_safe = m_novo_orc.group(1)
                db = get_session()
                _orc_dict = None
                try:
```

Insert the briefing gate right after `db = get_session()` and before `_orc_dict = None`:

```python
            if m_novo_orc:
                nome_safe = m_novo_orc.group(1)
                db = get_session()
                if not _briefing_projeto_completo(nome_safe, db):
                    db.close()
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de iniciar a negociação."},
                                   code=400)
                    return
                _orc_dict = None
                try:
```

- [ ] **Step 2: Gate em `POST /projetos/<nome>/pool`**

In `main.py`, find the pool handler start (currently ~lines 1313-1320):

```python
            if m_pool:
                nome_safe = m_pool.group(1)
                ct = self.headers.get("Content-Type", "")
                arquivos, _ = _parse_multipart(body, ct)
                if not arquivos:
                    self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                    return
```

Insert the briefing gate right after `nome_safe = m_pool.group(1)`:

```python
            if m_pool:
                nome_safe = m_pool.group(1)
                _db_bf = get_session()
                try:
                    _bf_ok = _briefing_projeto_completo(nome_safe, _db_bf)
                finally:
                    _db_bf.close()
                if not _bf_ok:
                    self.send_json({"ok": False,
                                    "erro": "Preencha o briefing do projeto antes de subir XML."},
                                   code=400)
                    return
                ct = self.headers.get("Content-Type", "")
                arquivos, _ = _parse_multipart(body, ct)
                if not arquivos:
                    self.send_json({"ok": False, "erro": "Nenhum XML recebido"})
                    return
```

- [ ] **Step 3: Verify**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax ok')"` → syntax ok
Run: `python -X utf8 -m pytest tests/ -q` → all pass.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(briefing): bloqueia orcamentos/pool sem briefing do projeto (400)"
```

---

## Task 4: Frontend — criar projeto → briefing do projeto → negociação

**Files:**
- Modify: `static/index.html` — `criarProjeto` (~2657); briefing modal funcs (`_bfClienteId`/`bfSalvar`/`bfFechar` ~7274-7379); aprovação (`abrirAprovacaoComDados` ~6813)

- [ ] **Step 1: `criarProjeto` — remover checagem prévia e abrir o briefing do projeto após criar**

In `static/index.html`, in `criarProjeto()`, REMOVE the pre-creation briefing check (currently lines 2668-2680):

```javascript
  // Verificar briefing do cliente
  try {
    const rb = await fetch('/api/clientes/' + clienteId + '/briefing', {credentials:'same-origin'});
    const db_ = await rb.json();
    if (!db_.ok || !db_.briefing || !db_.briefing.completo) {
      st.innerHTML = 'Briefing incompleto. <button onclick="npAbrirBriefingCliente()" ' +
        'style="background:none;border:1px solid var(--dalm-gold);color:var(--dalm-gold);' +
        'border-radius:4px;padding:2px 10px;font-size:.8rem;cursor:pointer;margin-left:6px">' +
        '✎ Preencher Briefing</button>';
      st.style.color = 'var(--err)';
      return;
    }
  } catch(e) { /* ignora erro de rede */ }
```

(Delete that whole block. The `st.textContent = 'Criando...'` line right after it stays.)

Then, at the END of the success path, REPLACE the final negotiation navigation. Currently:

```javascript
    await carregarOrcamentos();
    goPage(2);
  }catch(e){ st.textContent = 'Erro: '+e; st.style.color = 'var(--err)'; }
}
```

with (abre o briefing do projeto recém-criado; ao concluir, segue para a negociação):

```javascript
    await carregarOrcamentos();
    // Briefing obrigatório por-projeto: abre o briefing deste projeto antes de negociar.
    abrirBriefingProjeto(projetoAtivo.nome_safe, (projetoAtivo.cliente||{}).nome || projetoAtivo.nome_projeto || '');
  }catch(e){ st.textContent = 'Erro: '+e; st.style.color = 'var(--err)'; }
}
```

- [ ] **Step 2: Adicionar `_bfProjetoNome` + `abrirBriefingProjeto` e tornar `bfSalvar` por-projeto**

In `static/index.html`, find `let _bfClienteId = null;` (line 7274) and replace with:

```javascript
let _bfClienteId = null;
let _bfProjetoNome = null;   // quando setado, o briefing é por-projeto

async function abrirBriefingProjeto(nomeSafe, clienteNome) {
  _bfProjetoNome = nomeSafe;
  _bfClienteId = null;
  document.getElementById('bf-cliente-nome').textContent = clienteNome || '';
  document.getElementById('bf-data').value = new Date().toISOString().split('T')[0];
  const nomeEl = document.getElementById('usuario-nome') || document.querySelector('[data-usuario-nome]');
  document.getElementById('bf-consultor').value = nomeEl?.textContent || '';
  ['bf-tipo-imovel','bf-condicao','bf-decisor','bf-experiencia','bf-categoria','bf-flexibilidade',
   'bf-metragem','bf-num-ambientes','bf-budget','bf-data-entrega',
   'bf-amb-prioritarios','bf-end-emp','bf-nao-abre-mao','bf-restricoes','bf-obs-livres']
    .forEach(id => { const el = document.getElementById(id); if(el) el.value = ''; });
  try {
    const r = await fetch('/api/projetos/' + encodeURIComponent(nomeSafe) + '/briefing', {credentials:'same-origin'});
    const d = await r.json();
    if (d.ok && d.briefing) _bfPreencherForm(d.briefing);
  } catch(e) {}
  document.getElementById('modal-briefing').style.display = 'flex';
}
```

Then, in `bfSalvar()`, change the SAVE fetch (currently lines 7358-7366):

```javascript
  try {
    const r = await fetch('/api/clientes/' + _bfClienteId + '/briefing',
      {method:'POST', credentials:'same-origin',
       headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const d = await r.json();
    if (d.ok) {
      if (typeof showToast === 'function') showToast('Briefing salvo!');
      bfFechar();
      if (typeof cliHomeCarregar === 'function') cliHomeCarregar();
    } else {
      if (typeof showToast === 'function') showToast(d.erro || 'Erro ao salvar briefing', true);
    }
  } catch(e) {
    if (typeof showToast === 'function') showToast('Erro de conexão', true);
  }
```

to (rota por-projeto quando `_bfProjetoNome`; após salvar no fluxo de projeto vai à negociação):

```javascript
  const url = _bfProjetoNome
    ? '/api/projetos/' + encodeURIComponent(_bfProjetoNome) + '/briefing'
    : '/api/clientes/' + _bfClienteId + '/briefing';
  try {
    const r = await fetch(url,
      {method:'POST', credentials:'same-origin',
       headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const d = await r.json();
    if (d.ok) {
      if (typeof showToast === 'function') showToast('Briefing salvo!');
      const eraProjeto = !!_bfProjetoNome;
      bfFechar();
      if (eraProjeto) {
        if (typeof carregarCicloSilencioso === 'function') carregarCicloSilencioso();
        goPage(2);   // segue para a negociação
      } else if (typeof cliHomeCarregar === 'function') {
        cliHomeCarregar();
      }
    } else {
      if (typeof showToast === 'function') showToast(d.erro || 'Erro ao salvar briefing', true);
    }
  } catch(e) {
    if (typeof showToast === 'function') showToast('Erro de conexão', true);
  }
```

And in `bfFechar()` (lines 7375-7379), also clear `_bfProjetoNome`:

```javascript
function bfFechar() {
  const modal = document.getElementById('modal-briefing');
  if (modal) modal.style.display = 'none';
  _bfClienteId = null;
  _bfProjetoNome = null;
}
```

- [ ] **Step 3: Aprovação usa o briefing do projeto**

In `static/index.html`, in `abrirAprovacaoComDados()` (~line 6813), find the briefing check that fetches `/api/clientes/<id>/briefing`:

```javascript
  const rb = await fetch('/api/clientes/' + clienteParaBriefing.id + '/briefing');
```

Replace that fetch URL with the per-project one (the project is active: `projetoAtivo.nome_safe`):

```javascript
  const rb = await fetch('/api/projetos/' + encodeURIComponent(projetoAtivo.nome_safe) + '/briefing');
```

(Leave the rest of that check — `const db_ = await rb.json(); if (!db_.ok || !db_.briefing || !db_.briefing.completo) { mostrarErroComAcao(...) }` — intact. The "Abrir Briefing" action in that popup should also open the project briefing; if it currently calls `cliAbrirBriefing(...)`, change that call to `abrirBriefingProjeto(projetoAtivo.nome_safe, (projetoAtivo.cliente||{}).nome || '')`. Read the popup callback and update it accordingly.)

- [ ] **Step 4: Verify (static integrity)**

- Grep: in `criarProjeto`, no more fetch to `/api/clientes/...briefing` for the pre-check.
- Grep: `abrirBriefingProjeto` defined and called (from `criarProjeto` and the approval popup).
- Confirm one `<script>`/`</script>` pair; even backtick parity.
- Run `python -X utf8 -m pytest tests/ -q` → all pass (Python unaffected).

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(briefing): criar projeto -> briefing do projeto obrigatorio -> negociacao"
```

---

## Final verification (fase /verify ao fim)

- [ ] **Run full suite:** `python -X utf8 -m pytest tests/ -q` → all pass.
- [ ] **Runtime drive (API):** start one fresh `python main.py` (mate instâncias antigas antes!); login; criar um projeto novo p/ um cliente; `POST /projetos/<novo>/orcamentos` e `/pool` → **400** ("Preencha o briefing…"); `POST /api/projetos/<novo>/briefing` com os 5 obrigatórios → `GET /ciclo` mostra etapa 3 concluída; `POST /orcamentos` agora passa. Confirmar que a etapa 3 de OUTRO projeto do mesmo cliente NÃO foi marcada (leitura direta de `orizon.db`).
- [ ] **GUI drive (Playwright):** criar projeto → o briefing abre automaticamente → preencher os 5 obrigatórios + salvar → cai na negociação (page-02). Limpar dados de teste; parar o servidor.

---

## Notas de escopo (fora deste plano)
- UI de briefing por-cliente na aba Clientes (legado, não removida).
- `_briefing_locked` (por-cliente, não usado) — alinhamento futuro.
- Mover criação do "Orçamento 1" para depois do briefing.
