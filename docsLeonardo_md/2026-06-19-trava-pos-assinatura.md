# Trava total pós-assinatura + status "Fechado" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A partir da 1ª assinatura do contrato, travar (UI + backend 403) toda edição de orçamento/negociação/projeto; e, quando ambas as partes assinam, marcar o projeto com o novo status terminal "Fechado".

**Architecture:** Um helper backend `_contrato_assinado(nome_safe, db)` é a fonte única da verdade; ele é exposto no GET ciclo (consumido no load silencioso) e usado como guard (403) nos handlers de mutação. No frontend, `_contratoAssinado` (vindo do ciclo) esconde os botões de edição. O status "fechado" é setado por `upsert_projeto_status` quando o contrato fica totalmente assinado, e ganha rótulo/badge/filtro como os demais.

**Tech Stack:** Python stdlib http.server + SQLAlchemy/SQLite; SPA vanilla-JS em `static/index.html`; pytest; Playwright.

**Convenção de testes:** lógica pura/helpers → pytest; handlers HTTP + SPA → verificados via API real + Playwright (ver `DEV_LOG.md`). Task 1 é TDD pytest; Tasks 2–6 são wiring verificado na Task 7.

---

## File Structure

- `main.py` — helper `_contrato_assinado`; flag no GET ciclo; `upsert_projeto_status(..., "fechado")` na 2ª assinatura; guards 403 nos handlers de mutação.
- `static/index.html` — `_contratoAssinado` (de `_fetchCiclo`); esconder botões em `atualizarBotoesAprovacao`; ids nos botões da sidebar; status "fechado" (label/badge/CSS/filtro/dropdown).
- `tests/test_contrato_assinado.py` (novo) — helper `_contrato_assinado` + transição p/ "fechado".

---

## Task 1: Helper `_contrato_assinado` + status "fechado" na 2ª assinatura (backend)

**Files:**
- Modify: `main.py` (helper novo perto de `_projeto_esta_bloqueado`; handler de assinatura ~2276-2287)
- Test: `tests/test_contrato_assinado.py` (novo)

- [ ] **Step 1: Write the failing test** — create `tests/test_contrato_assinado.py`:

```python
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    import database
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=engine))
    database.init_db()
    yield


def _mk_contrato(db, status="rascunho", assinaturas=()):
    from database import Contrato, ContratoAssinatura, Orcamento
    from datetime import datetime
    o = Orcamento(projeto_id="Proj_A", nome="Orçamento 1", ordem=1)
    db.add(o); db.commit(); db.refresh(o)
    c = Contrato(projeto_nome="Proj_A", orcamento_id=o.id, status=status)
    db.add(c); db.commit(); db.refresh(c)
    for parte in assinaturas:
        db.add(ContratoAssinatura(contrato_id=c.id, parte=parte, nome="X", cpf="0",
                                  assinado_em=datetime.utcnow(), hash_sha256="h"))
    db.commit()
    return c


def test_assinado_false_sem_contrato():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    assert _contrato_assinado("Proj_Inexistente", db) is False
    db.close()


def test_assinado_false_rascunho():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="rascunho")
    assert _contrato_assinado("Proj_A", db) is False
    db.close()


def test_assinado_true_uma_assinatura():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="assinado_loja", assinaturas=("loja",))
    assert _contrato_assinado("Proj_A", db) is True
    db.close()


def test_assinado_true_status_vigente():
    from main import _contrato_assinado
    from database import get_session
    db = get_session()
    _mk_contrato(db, status="vigente")
    assert _contrato_assinado("Proj_A", db) is True
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contrato_assinado.py -v`
Expected: FAIL (`ImportError: cannot import name '_contrato_assinado'`).

- [ ] **Step 3: Add the helper** — In `main.py`, near `_projeto_esta_bloqueado` (search it), add:

```python
def _contrato_assinado(nome_safe, db) -> bool:
    """True se o último contrato do projeto tem qualquer assinatura (1ª assinatura)
    ou status já assinado. Fonte única da trava total pós-assinatura."""
    c = (db.query(Contrato)
           .filter_by(projeto_nome=nome_safe)
           .order_by(Contrato.id.desc())
           .first())
    if not c:
        return False
    if c.status in ("assinado_loja", "assinado_cliente", "assinado", "vigente"):
        return True
    return len(c.assinaturas) > 0
```

(`Contrato` is already imported in main.py.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contrato_assinado.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Set status "fechado" on full signature** — In `main.py`, in the assinar handler, inside the `if {"loja", "cliente"}.issubset(partes_assinadas):` block (where `contrato.status = "assinado"` ~line 2277 and etapa7 is closed, before the `db.commit()` at ~2287), add after `etapa7.responsavel_id = usuario["id"]`:

```python
                        try:
                            upsert_projeto_status(nome_safe, "fechado")
                        except Exception:
                            pass
```

(`upsert_projeto_status` is already imported in main.py — confirm with grep.)

- [ ] **Step 6: Smoke check**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_contrato_assinado.py
git commit -m "feat(contrato): helper _contrato_assinado + status Fechado na 2a assinatura"
```

---

## Task 2: Expor `contrato_assinado` no GET ciclo (backend)

**Files:**
- Modify: `main.py` (handler `GET /api/projetos/<nome>/ciclo` ~630-673)

- [ ] **Step 1: Add the flag to the response** — In `main.py`, in the GET ciclo handler, the response is currently:

```python
                    self.send_json({"ok": True, "ciclo": resultado})
```

Replace it with (computes the flag using the helper from Task 1, reusing the open `db`):

```python
                    assinado = _contrato_assinado(nome_safe, db)
                    self.send_json({"ok": True, "ciclo": resultado,
                                    "contrato_assinado": assinado})
```

- [ ] **Step 2: Smoke check**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 3: Full suite (no regression)**

Run: `python -m pytest -q`
Expected: green (previous count + 4 from Task 1).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(api): GET ciclo expoe contrato_assinado"
```

---

## Task 3: Guards 403 nos handlers de mutação (backend)

**Files:**
- Modify: `main.py` (handlers de novo orçamento, pool/sobrescrever/nova_versao/criar_forcado, ambiente add/remover, PATCH valor, margens, descontos, PATCH status, renomear orçamento)

Para cada handler abaixo, logo após obter a sessão `db` e o `nome_safe`/orçamento, e ANTES de qualquer escrita, inserir o guard. Use o `nome_safe` do projeto; quando o handler só tem `oid` (orçamento), obtenha o projeto via `orc.projeto_id`.

Padrão do guard (projeto conhecido por `nome_safe`):
```python
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
```
Padrão quando se tem `orc` (orçamento) primeiro:
```python
                if orc and _contrato_assinado(orc.projeto_id, db):
                    self.send_json({"ok": False,
                                    "erro": "Contrato assinado — alterações não permitidas."},
                                   code=403)
                    return
```

- [ ] **Step 1: Novo orçamento** — handler `POST /projetos/<nome>/orcamentos` (`m_novo_orc`, ~1498). Após abrir `db` e validar o briefing, antes de criar o `Orcamento`, inserir o guard (projeto = `nome_safe`).

- [ ] **Step 2: Pool (inserir XML/ambientes)** — handlers `POST /projetos/<nome>/pool` (~1543) e as variantes `pool/sobrescrever`, `pool/nova_versao`, `pool/criar_forcado`. Em cada um, após abrir `db` e ter `nome_safe`, inserir o guard. (Se compartilham um bloco de parse comum, inserir o guard em cada handler distinto.)

- [ ] **Step 3: Ambiente add/remover** — handlers `POST /orcamentos/<oid>/ambientes/<pid>` (~1908) e `.../remover` (~1869). Como têm `oid`, carregue o orçamento e use `orc.projeto_id`:
```python
                orc = db.get(Orcamento, oid)
                if orc and _contrato_assinado(orc.projeto_id, db):
                    self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
                    return
```
(Coloque o guard logo após obter `db`/`orc`, antes do recálculo/escrita. Se o handler já busca `orc` adiante, mova/duplique a obtenção mínima para o guard.)

- [ ] **Step 4: PATCH valor** — handler `^/orcamentos/(\d+)/valor$` (~2704). Após `orc = db.get(Orcamento, oid)` e o check de `not orc`, inserir o guard com `orc.projeto_id`.

- [ ] **Step 5: Margens e descontos** — handlers `POST /api/orcamentos/<id>/margens` e `PUT /api/orcamentos/<id>/descontos`. Já têm `orc` e checam `_projeto_esta_bloqueado`. Adicionar, junto ao check de bloqueio, o de assinatura:
```python
                    if _contrato_assinado(orc.projeto_id, db):
                        self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
                        return
```

- [ ] **Step 6: Renomear orçamento** — handler `do_PUT` `^/projetos/([^/]+)/orcamentos/(\d+)$` (~2651). Após obter `orc` e validar `orc.projeto_id == nome_safe`, inserir o guard (projeto = `nome_safe`).

- [ ] **Step 7: PATCH status do projeto** — handler `^/api/projetos/([^/]+)/status$` (~2730). Após validar `novo_status`, inserir o guard (projeto = `nome_safe`) antes de `upsert_projeto_status`.

- [ ] **Step 8: Smoke check**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 9: Full suite**

Run: `python -m pytest -q`
Expected: green (sem regressão).

- [ ] **Step 10: Commit**

```bash
git add main.py
git commit -m "feat(api): recusa (403) mutacoes de orcamento/projeto quando contrato assinado"
```

---

## Task 4: Frontend — `_contratoAssinado` e esconder botões de edição

**Files:**
- Modify: `static/index.html` (`_fetchCiclo` ~6567 area; `atualizarBotoesAprovacao` ~6613; botões da sidebar ~745/759/761/763)

- [ ] **Step 1: Capturar `_contratoAssinado` no `_fetchCiclo`** — `_fetchCiclo` atualmente:

```javascript
async function _fetchCiclo() {
  if (!projetoAtivo) return;
  const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo`,
                        { credentials: 'same-origin' });
  const d = await r.json();
  if (!d.ok) return;
  _cicloData = {};
  for (const e of (d.ciclo || [])) _cicloData[e.etapa_codigo] = e;
}
```

Add a global near the ciclo state (search `let _cicloData`): `let _contratoAssinado = false;`
And inside `_fetchCiclo`, after `if (!d.ok) return;`, add:
```javascript
  _contratoAssinado = !!d.contrato_assinado;
```

- [ ] **Step 2: Dar ids aos botões da sidebar** — In `static/index.html`:
  - Linha ~745 (Parâmetros): adicionar `id="btn-params"` ao `<button ... onclick="abrirModalParams()">`.
  - Linha ~759 (Ambientes): adicionar `id="btn-pool"` ao `<button ... onclick="abrirPainelPool()">`.
  - Linha ~761 (Novo Ambiente): adicionar `id="btn-novo-ambiente"` ao `<button ... onclick="abrirModalNovoAmbiente()">`.
  - Linha ~763 (Novo Orçamento): adicionar `id="btn-novo-orc"` ao `<button ... onclick="abrirModalNovoOrc()">`.

- [ ] **Step 3: Esconder na `atualizarBotoesAprovacao`** — In `atualizarBotoesAprovacao` (~6613), at the very top of the function (before `const aprovado = _orcamentoAprovado();`), add a block that, when signed, hides editing controls and skips the approval-button logic:

```javascript
  const assinado = (typeof _contratoAssinado !== 'undefined') && _contratoAssinado;
  ['btn-params','btn-pool','btn-novo-ambiente','btn-novo-orc'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = assinado ? 'none' : '';
  });
  if (assinado) {
    aplicarBloqueioNegociacao(true);                 // mantém inputs travados
    const actionRow = document.querySelector('#page-02 .action-row');
    if (actionRow) {
      const bs = actionRow.querySelector('.btn-ok');   if (bs) bs.style.display = 'none';
      const ba = actionRow.querySelector('.btn-amber'); if (ba) ba.style.display = 'none';
      const br = actionRow.querySelector('#btn-rever-orcamento'); if (br) br.remove();
      // garante o botão "Assinar Contrato" (a 2ª parte ainda pode assinar)
      if (!actionRow.querySelector('#btn-assinar-contrato')) {
        const btn = document.createElement('button');
        btn.id = 'btn-assinar-contrato';
        btn.className = 'btn btn-ghost';
        btn.style.cssText = 'border-color:var(--warn,#c8a84b);color:var(--warn,#c8a84b);font-size:.85rem;font-weight:600;padding:8px 16px;border-radius:4px;cursor:pointer';
        btn.innerHTML = '&#x270D; Assinar Contrato';
        btn.onclick = () => { abrirCiclo(); setTimeout(() => toggleCicloCard('7'), 300); };
        actionRow.appendChild(btn);
      }
    }
    return;   // não cair na lógica reversível de aprovação
  }
```

(The existing approval logic below stays for the not-signed case.)

- [ ] **Step 4: Smoke (load)** — Start the app, hard-refresh, open a project. Confirm no console error. (Full behaviour in Task 7.)

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(front): esconde edicao do orcamento quando contrato assinado (mantem Assinar Contrato)"
```

---

## Task 5: Frontend — status "Fechado" (label/badge/CSS/filtro/dropdown)

**Files:**
- Modify: `static/index.html` (CSS ~90-95; `_PROJ_STATUS_LABEL` ~2181; badge render ~2192; `negAtualizarStatusBtn` ~2278; `negStatusClick` ~2298; filtro de status ~702-706)

- [ ] **Step 1: CSS do badge** — After `.proj-status-badge.convertido{...}` (~line 93), add:

```css
.proj-status-badge.fechado{background:rgba(180,140,40,.16);color:#c8a84b}
```

- [ ] **Step 2: Label no `_PROJ_STATUS_LABEL`** — In the `_PROJ_STATUS_LABEL` object (~2181), add an entry:

```javascript
  fechado:    { label: '🔒 Fechado',  cls: 'fechado'    },
```

- [ ] **Step 3: Badge render** — Find the badge render that special-cases convertido (~2192: `if(s === 'convertido') return ...`). Add right after it:

```javascript
  if(s === 'fechado') return `<span class="proj-status-badge fechado">🔒 Fechado</span>`;
```

- [ ] **Step 4: Botão de status (label + cor + dropdown oculto)** — In `negAtualizarStatusBtn` (~2278):
  - In the `labels` object add `fechado:'🔒 Fechado'`.
  - In the color chain, before the trailing `: ''`, add `: s === 'fechado' ? '#c8a84b'`.
  - Change the dropdown-hide line:
    ```javascript
    if(dd) dd.style.display = (s === 'convertido' || s === 'fechado') ? 'none' : '';
    ```

- [ ] **Step 5: Bloquear abertura do dropdown** — In `negStatusClick` (~2298), change:
    ```javascript
    if(_projetoStatusAtual === 'convertido') return;
    ```
    to:
    ```javascript
    if(_projetoStatusAtual === 'convertido' || _projetoStatusAtual === 'fechado') return;
    ```

- [ ] **Step 6: Filtro na lista de projetos** — In the status filter checkboxes (~702-706), after the "Convertido" item, add:

```html
          <label class="proj-status-filter-item"><input type="checkbox" value="fechado" checked onchange="projAplicarFiltros()"> 🔒 Fechado</label>
```

- [ ] **Step 7: Smoke (load)** — Start app, hard-refresh; confirm no console error; the projects list still renders.

- [ ] **Step 8: Commit**

```bash
git add static/index.html
git commit -m "feat(front): status Fechado (label/badge/CSS/filtro/dropdown travado)"
```

---

## Task 6: Verificação cruzada de regressão (não quebrar o fluxo pré-assinatura)

**Files:** nenhum (revisão)

- [ ] **Step 1: Conferir o caminho não-assinado** — Ler `atualizarBotoesAprovacao` por inteiro e confirmar: quando `_contratoAssinado` é false, o comportamento é EXATAMENTE o anterior (Salvar/Aprovar visíveis quando não aprovado; pós-aprovação mostra Assinar + Rever). O bloco novo só age quando `assinado`.
- [ ] **Step 2: Confirmar `upsert_projeto_status` importado** — `grep -n "upsert_projeto_status" main.py` deve mostrar o import (linha ~13) e os usos (convertido + o novo fechado).
- [ ] **Step 3: Smoke + suite** — `python -m pytest -q` (verde) e `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`.

(Sem commit se nada mudou; se ajustes forem necessários, commitar com mensagem `fix(...)`.)

---

## Task 7: Verificação end-to-end

**Files:** nenhum (execução/verificação)

- [ ] **Step 1: pytest** — `python -m pytest -q` (tudo verde).

- [ ] **Step 2: API real** (app rodando, login `pdm2026`/`teste123`) — script `requests`:
  - Escolher um projeto **sem** contrato assinado: POST novo orçamento, POST pool, PATCH valor/status → **funcionam** (pré-assinatura).
  - Simular contrato assinado num projeto de teste (assinar loja+cliente via `POST /api/projetos/<nome>/contrato/assinar` nas duas partes) e confirmar: POST novo orçamento / pool / ambiente, PATCH valor/margens/descontos/status → **403**; e o projeto ficou com status **`fechado`** em `projetos_meta`.

- [ ] **Step 3: Playwright (UI, dados reais)** — ver `gui-verification-playwright`:
  - Projeto com contrato assinado: confirmar que **Salvar/Parâmetros/Ambientes/Novo Ambiente/Novo Orçamento/Rever** não aparecem, **"Assinar Contrato" aparece**, e o dropdown de status está travado.
  - Após as duas assinaturas, o badge do projeto (lista e cabeçalho) mostra **"🔒 Fechado"**.
  - Console sem erros.

- [ ] **Step 4: DEV_LOG + finalizar branch**
  - Acrescentar seção de sessão ao `DEV_LOG.md`.
  - Seguir `superpowers:finishing-a-development-branch`.

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — trava pos-assinatura + status Fechado"
```

---

## Self-Review (cobertura da spec)

- **Detecção (1ª assinatura) `_contrato_assinado`** → Task 1.
- **Exposto no GET ciclo / `_contratoAssinado`** → Task 2 (back) + Task 4 (front).
- **Esconder Salvar/Parâmetros/Ambientes/Novo Orçamento/Rever; manter Assinar Contrato** → Task 4.
- **Status do projeto travado (UI)** → Task 5 (dropdown) + (backend) Task 3 Step 7.
- **Backend 403 nas mutações** → Task 3.
- **Status "Fechado" automático na 2ª assinatura** → Task 1 Step 5.
- **Label/badge/CSS/filtro/dropdown do "Fechado"** → Task 5.
- **Testes (helper, transição, 403, UI)** → Task 1 (pytest) + Task 7 (API/Playwright).
- **Não quebrar o fluxo pré-assinatura** → Task 6.
- **Consistência de nomes:** `_contrato_assinado` (back), `_contratoAssinado` (front), `contrato_assinado` (JSON), `fechado` (status), ids `btn-params`/`btn-pool`/`btn-novo-ambiente`/`btn-novo-orc` — usados de forma idêntica entre as tasks.
