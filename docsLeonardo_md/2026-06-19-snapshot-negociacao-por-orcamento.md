# Snapshot completo da negociação por orçamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir as entradas da negociação (modalidade, formas, nº de parcelas, entrada e datas manuais do Total Flex / Venda Programada) por orçamento no banco, reproduzi-las ao reabrir, e garantir o salvamento ao aprovar.

**Architecture:** Nova coluna JSON `orcamentos.negociacao_json` guarda um snapshot das ENTRADAS. O frontend captura essas entradas ao salvar/aprovar e as reinjeta ao reabrir (depois de `carregarModalidades`), recalculando o plano com as datas manuais preservadas. O salvamento ao aprovar passa a ser confiável (await + aborta a aprovação se falhar).

**Tech Stack:** Python stdlib http.server + SQLAlchemy/SQLite; SPA vanilla-JS em `static/index.html`; pytest; Playwright para verificação de UI.

**Convenção de testes deste repo:** funções puras/modelos → pytest; handlers HTTP e o SPA → verificados via API real + Playwright (ver `DEV_LOG.md`). Tasks 1 é TDD pytest; Tasks 2–5 são wiring verificado end-to-end na Task 6.

---

## File Structure

- `database.py` — coluna `negociacao_json` em `Orcamento` + migração em `_migrar_colunas`.
- `main.py` — `PATCH /orcamentos/<id>/valor` aceita `negociacao_json`; `GET /orcamentos/<id>/ambientes` devolve `negociacao_json`.
- `static/index.html` — `_capturarNegociacao()`, `_restaurarNegociacao(snap)`, constante `_NEG_CAMPOS_POR_MODALIDADE`, wiring em `salvarValorNegociado`/reabrir/aprovar.
- `tests/test_orcamento_negociacao.py` (novo) — coluna + round-trip.

---

## Task 1: Coluna `negociacao_json` em `orcamentos`

**Files:**
- Modify: `database.py` (classe `Orcamento` ~251-270; `_migrar_colunas` bloco `orcamentos` ~411-419)
- Test: `tests/test_orcamento_negociacao.py` (novo)

- [ ] **Step 1: Write the failing test** — create `tests/test_orcamento_negociacao.py`:

```python
import pytest, sys, os, json
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


def test_negociacao_json_persiste():
    from database import get_session, Orcamento
    snap = {"codigo": "total_flex", "n_parcelas": 10,
            "tf_datas": ["2026-07-18", "2026-08-17"]}
    db = get_session()
    o = Orcamento(projeto_id="Proj_N", nome="Orçamento 1", ordem=1,
                  negociacao_json=json.dumps(snap, ensure_ascii=False))
    db.add(o); db.commit(); db.refresh(o)
    lido = db.get(Orcamento, o.id)
    assert json.loads(lido.negociacao_json)["codigo"] == "total_flex"
    assert json.loads(lido.negociacao_json)["tf_datas"] == ["2026-07-18", "2026-08-17"]
    db.close()


def test_negociacao_json_default_none():
    from database import get_session, Orcamento
    db = get_session()
    o = Orcamento(projeto_id="Proj_N2", nome="Orçamento 1", ordem=1)
    db.add(o); db.commit(); db.refresh(o)
    assert db.get(Orcamento, o.id).negociacao_json is None
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orcamento_negociacao.py -v`
Expected: FAIL (`TypeError: 'negociacao_json' is an invalid keyword argument`).

- [ ] **Step 3: Add the column to the model**

In `database.py`, class `Orcamento`, after the `forma_pagamento = Column(...)` line, add:

```python
    negociacao_json = Column(Text,     nullable=True)   # snapshot das entradas da negociação (JSON)
```

(`Text` is already imported in database.py.)

- [ ] **Step 4: Add the column to `_migrar_colunas`**

In `database.py`, inside `_migrar_colunas`, in the `# ── orcamentos ──` block, add `negociacao_json` to the list of `(col, tipo)` pairs:

```python
            ("negociacao_json", "TEXT"),
```

(It joins the existing list alongside `valor_liquido`, `forma_pagamento`, `updated_at`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_orcamento_negociacao.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_orcamento_negociacao.py
git commit -m "feat(banco): coluna negociacao_json em orcamentos"
```

---

## Task 2: Backend — `PATCH /valor` aceita e `GET ambientes` devolve `negociacao_json`

**Files:**
- Modify: `main.py` (`PATCH /orcamentos/<id>/valor` ~2704-2728; `GET /orcamentos/<id>/ambientes` ~519-541)

- [ ] **Step 1: `PATCH /valor` grava `negociacao_json`**

In `main.py`, in the `^/orcamentos/(\d+)/valor$` handler, after the `if "forma_pagamento" in req:` block (before `orc.updated_at = datetime.utcnow()`), add:

```python
                    if "negociacao_json" in req:
                        orc.negociacao_json = req["negociacao_json"] or None
```

- [ ] **Step 2: `GET ambientes` devolve `negociacao_json`**

In `main.py`, in the `^/orcamentos/(\d+)/ambientes$` handler, the response currently is (from the previous sub-project):

```python
                    orc = db.get(Orcamento, oid)
                    margens = json.loads(orc.margens) if (orc and orc.margens) else {}
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "margens": margens, "ambientes": ambientes})
```

Replace it with (adds `negociacao` parsed from the orçamento; reuses the already-fetched `orc`):

```python
                    orc = db.get(Orcamento, oid)
                    margens = json.loads(orc.margens) if (orc and orc.margens) else {}
                    negociacao = json.loads(orc.negociacao_json) if (orc and orc.negociacao_json) else None
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "margens": margens, "negociacao": negociacao,
                                    "ambientes": ambientes})
```

- [ ] **Step 3: Smoke check**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Full suite (no regression)**

Run: `python -m pytest -q`
Expected: all green (previous count + 2 from Task 1).

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(api): /orcamentos/<id>/valor grava negociacao_json; GET ambientes devolve negociacao"
```

---

## Task 3: Frontend — captura das entradas (`_capturarNegociacao`)

**Files:**
- Modify: `static/index.html` (perto de `salvarValorNegociado` ~7350 e do bloco de variáveis de pagamento ~3106-3110)

Contexto de campos (ids reais por modalidade, já mapeados):
- `total_flex`: `tf-entrada`, `tf-prazo`, `tf-taxa-input`, `tf-data-contrato`; datas manuais em `_tfDatas`.
- `venda_programada`: `vp-entrada`, `vp-data-contrato`; datas manuais em `_vpDatas`.
- `aymore`: `ay-entrada`, `ay-data-contrato`, `ay-carencia`.
- `cartao_credito`: `cc-entrada`, `cc-data-contrato`, `cc-bandeira`.
- `a_vista`: `av-entrada-valor`, `av-entrada-data`, `av-entrada-forma`, `av-liq-data`, `av-liq-forma`.
- Comuns: modalidade em `_codigoPagAtivo` (select `neg-pagamento`), nº de parcelas em `neg-parcelas` (`_nParcelasSel`), formas em `_formaEntrada`/`_formaParcela`.

- [ ] **Step 1: Add the modalidade→campos map and the capture function**

In `static/index.html`, add near the payment-state globals (after the `let _formaParcela = 'boleto';` line, ~3109):

```javascript
// Snapshot da negociação — campos de input por modalidade (ids reais do DOM)
const _NEG_CAMPOS_POR_MODALIDADE = {
  total_flex:       ['tf-entrada','tf-prazo','tf-taxa-input','tf-data-contrato'],
  venda_programada: ['vp-entrada','vp-data-contrato'],
  aymore:           ['ay-entrada','ay-data-contrato','ay-carencia'],
  cartao_credito:   ['cc-entrada','cc-data-contrato','cc-bandeira'],
  a_vista:          ['av-entrada-valor','av-entrada-data','av-entrada-forma','av-liq-data','av-liq-forma'],
};

// Captura as ENTRADAS da negociação ativa (para reproduzir ao reabrir).
function _capturarNegociacao(){
  const codigo = _codigoPagAtivo || (document.getElementById('neg-pagamento')?.value) || 'a_vista';
  const campos = {};
  (_NEG_CAMPOS_POR_MODALIDADE[codigo] || []).forEach(id => {
    const el = document.getElementById(id);
    if (el) campos[id] = el.value;
  });
  const snap = {
    codigo,
    n_parcelas: parseInt(document.getElementById('neg-parcelas')?.value) || _nParcelasSel || 1,
    forma_entrada: _formaEntrada,
    forma_parcela: _formaParcela,
    campos,
  };
  if (codigo === 'total_flex') snap.tf_datas = Array.isArray(_tfDatas) ? _tfDatas.slice() : [];
  if (codigo === 'venda_programada') snap.vp_datas = Array.isArray(_vpDatas) ? _vpDatas.slice() : [];
  return snap;
}
```

- [ ] **Step 2: Send `negociacao_json` in `salvarValorNegociado`**

In `salvarValorNegociado` (~7361-7370), add `negociacao_json` to the PATCH body. Change the body object to include:

```javascript
        negociacao_json: JSON.stringify(_capturarNegociacao()),
```

(add it as a new line alongside `valor_total`, `valor_liquido`, `forma_pagamento`.)

- [ ] **Step 3: Smoke (load) — start app and confirm no JS console error**

Start the app (see `gui-verification-playwright`), open the SPA, open DevTools console: confirm no syntax/runtime error on load. (Full behaviour verified in Task 6.)

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(front): captura das entradas da negociacao (_capturarNegociacao) e envio no salvar"
```

---

## Task 4: Frontend — reprodução das entradas (`_restaurarNegociacao`)

**Files:**
- Modify: `static/index.html` (`carregarMargensSalvas` ~4922-4938; `_aplicarFiltroOrcamento` ~2513-2521)

A reprodução acontece ao ativar/reabrir um orçamento. O `negociacao` vem na resposta do GET de ambientes (Task 2). Guardamos em uma variável e restauramos depois de `carregarModalidades()`.

- [ ] **Step 1: Guardar `negociacao` ao receber os ambientes**

In `_aplicarFiltroOrcamento` (~2513), where the previous sub-project added the margens/desconto handling, add capture of `negociacao` into a module variable. Right after `if(projetoAtivo) projetoAtivo.margens = d.margens || {};` add:

```javascript
    _negociacaoPendente = d.negociacao || null;
```

And declare the variable near the payment globals (~3110):

```javascript
let _negociacaoPendente = null;  // snapshot da negociação a restaurar após carregarModalidades
```

- [ ] **Step 2: Write `_restaurarNegociacao`**

Add this function near `_capturarNegociacao` in `static/index.html`:

```javascript
// Reproduz as ENTRADAS salvas da negociação. Chamar APÓS carregarModalidades().
async function _restaurarNegociacao(snap){
  if (!snap || !snap.codigo) return;
  const sel = document.getElementById('neg-pagamento');
  if (sel) sel.value = snap.codigo;
  // renderiza o painel da modalidade e carrega faixas (assíncrono)
  if (typeof onPagamentoChange === 'function') await onPagamentoChange();
  // nº de parcelas (dispara onParcelasChange, que p/ TF/VP zera as datas — por isso vem antes das datas)
  const parc = document.getElementById('neg-parcelas');
  if (parc && snap.n_parcelas) {
    parc.value = String(snap.n_parcelas);
    if (typeof onParcelasChange === 'function') onParcelasChange();
  }
  // formas
  if (snap.forma_entrada) _formaEntrada = snap.forma_entrada;
  if (snap.forma_parcela) _formaParcela = snap.forma_parcela;
  const selFE = document.getElementById('neg-forma-entrada');
  const selFP = document.getElementById('neg-forma-parcela');
  if (selFE && snap.forma_entrada) selFE.value = snap.forma_entrada;
  if (selFP && snap.forma_parcela && !selFP.disabled) selFP.value = snap.forma_parcela;
  // campos de input da modalidade: escreve valor e dispara o handler nativo (input+change)
  const campos = snap.campos || {};
  Object.keys(campos).forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = campos[id];
    el.dispatchEvent(new Event('input',  { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  });
  // datas manuais: setar DEPOIS dos campos (cujos handlers podem ter zerado as listas) e re-renderizar
  if (snap.codigo === 'total_flex' && Array.isArray(snap.tf_datas)) {
    _tfDatas = snap.tf_datas.slice();
    if (typeof atualizarTF === 'function') atualizarTF();
  }
  if (snap.codigo === 'venda_programada' && Array.isArray(snap.vp_datas)) {
    _vpDatas = snap.vp_datas.slice();
    if (typeof atualizarVP === 'function') atualizarVP();
  }
  if (typeof agendarCalculo === 'function') agendarCalculo();
}
```

NOTE for the implementer: confirm the recompute function names by reading the panels — the TF recompute is `atualizarTF` (confirmed, ~4053); for VP confirm the equivalent (search `function atualizarVP` / the function that renders `vp-parc-body` and consumes `_vpDatas`); if the VP recompute has a different name, use that name. Also confirm the sidebar form selects ids (`neg-forma-entrada`/`neg-forma-parcela`) by reading `atualizarFormasPagamento` (~3120-3165); if different, use the real ids.

- [ ] **Step 3: Call `_restaurarNegociacao` after `carregarModalidades`**

In `carregarMargensSalvas` (~4937), the line `await carregarModalidades();` populates the dropdowns and triggers the default calc. Immediately AFTER it, add:

```javascript
  if (_negociacaoPendente) { await _restaurarNegociacao(_negociacaoPendente); _negociacaoPendente = null; }
```

- [ ] **Step 4: Smoke (load) — no console error on app load**

Start app, open SPA, confirm no JS error on load and that opening a project still renders the negotiation. (Behaviour verified in Task 6.)

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(front): reproduz entradas da negociacao ao reabrir orcamento (_restaurarNegociacao)"
```

---

## Task 5: Garantia de salvamento ao aprovar

**Files:**
- Modify: `static/index.html` (`salvarValorNegociado` ~7350-7373; `salvarOrcamento` ~6164-6196; `aprovarOrcamento` ~6224)

- [ ] **Step 1: `salvarValorNegociado` retorna sucesso/erro**

Rewrite `salvarValorNegociado` to RETURN a result instead of silently swallowing. Replace its body with:

```javascript
async function salvarValorNegociado() {
  if (!_orcamentoAtivoId) return { ok: false, erro: 'Nenhum orçamento ativo' };
  const elTotal   = document.getElementById('neg-total-final');
  const elAvista  = document.getElementById('neg-avista');
  const elPag     = document.getElementById('neg-pagamento');
  const rawTotal  = (elTotal?.value || '').replace(/\./g,'').replace(',','.').replace(/[^\d.]/g,'');
  const rawAvista = (elAvista?.textContent || '').replace(/[R$\s.]/g,'').replace(',','.');
  const valor        = parseFloat(rawTotal)  || 0;
  const valorLiquido = parseFloat(rawAvista) || 0;
  try {
    const r = await fetch(`/orcamentos/${_orcamentoAtivoId}/valor`, {
      method: 'PATCH', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        valor_total:     valor,
        valor_liquido:   valorLiquido,
        forma_pagamento: (typeof _capturarPagamento === 'function' && window._planoPagamento)
          ? JSON.stringify(_capturarPagamento(_formaEntrada, _formaParcela))
          : (elPag?.value || null),
        negociacao_json: JSON.stringify(_capturarNegociacao()),
      }),
    });
    const d = await r.json();
    return d && d.ok ? { ok: true } : { ok: false, erro: (d && d.erro) || 'Falha ao salvar' };
  } catch(e) {
    console.warn('salvarValorNegociado:', e);
    return { ok: false, erro: 'Erro de conexão ao salvar' };
  }
}
```

(NOTE: this removes the early `if (!valor) return;`. The save now always persists — including `negociacao_json` — and the caller decides what to do. The previous sub-project's frontend already changed this URL to per-orçamento; keep `/orcamentos/${_orcamentoAtivoId}/valor`.)

- [ ] **Step 2: `aprovarOrcamento` aborta se o salvamento falhar**

At the very top of `aprovarOrcamento` (~6224), before opening the export modal, add a guaranteed save:

```javascript
async function aprovarOrcamento() {
  const _sv = await salvarValorNegociado();
  if (!_sv.ok) {
    (typeof avisoPopup === 'function')
      ? avisoPopup('Não foi possível salvar o orçamento — aprovação cancelada. ' + (_sv.erro || ''))
      : showToast('Não foi possível salvar o orçamento — aprovação cancelada.', true);
    return;
  }
  const modal      = document.getElementById('modal-exportar');
  // ... resto da função permanece igual ...
```

(Keep the rest of the function body unchanged.)

- [ ] **Step 3: `salvarOrcamento` reflete o resultado do salvamento**

In `salvarOrcamento` (~6173-6175), the call `await salvarValorNegociado();` now returns a result. Use it: replace that line with:

```javascript
  // 1. Persiste valor negociado, valor líquido, forma de pagamento e entradas da negociação
  const _sv = await salvarValorNegociado();
  if (!_sv.ok) {
    showToast('Falha ao salvar o orçamento: ' + (_sv.erro || ''), true);
    return;
  }
```

(This sits before the etapa-4 marking; if the save fails, we don't mark the stage or show "salvo".)

- [ ] **Step 4: Check there are no OTHER callers relying on the old void return**

Run: `grep -n "salvarValorNegociado()" static/index.html`
For each call site, confirm it either awaits and ignores the result (fine) or handles `.ok`. The known sites are `salvarOrcamento` (handled), `aprovarOrcamento` (handled), and line ~7419 (inside another flow) — read that site and, if it just needs the save to happen, leaving `await salvarValorNegociado();` is acceptable (the result is simply unused). Report what you found.

- [ ] **Step 5: Smoke + commit**

Run: `python -c "print('syntax check is manual for JS')"` (no Python change). Start the app and confirm no console error on load.

```bash
git add static/index.html
git commit -m "feat(front): garante salvamento ao aprovar (aborta aprovacao se falhar)"
```

---

## Task 6: Verificação end-to-end

**Files:** nenhum (execução/verificação)

- [ ] **Step 1: Suíte pytest**

Run: `python -m pytest -q`
Expected: tudo verde (inclui os 2 testes da Task 1).

- [ ] **Step 2: Verificação por API real** (script `requests`, app rodando, login `pdm2026`/`teste123`)
- `PATCH /orcamentos/<id>/valor` com `negociacao_json` grava; `GET /orcamentos/<id>/ambientes` devolve `negociacao` igual ao salvo (round-trip do snapshot, incluindo `tf_datas`).

- [ ] **Step 3: Verificação Playwright (UI, dados reais)** — ver `gui-verification-playwright`
- **Total Flex:** abrir um projeto, escolher modalidade Total Flex, definir nº de parcelas e **editar datas manualmente**; Salvar Orçamento; trocar para outro orçamento e voltar (e também recarregar a página) → confirmar que a modalidade, o nº de parcelas, a entrada e as **datas manuais** foram reproduzidas e o plano recalculado bate.
- **Cartão / Aymoré / À vista:** salvar e reabrir → modalidade, formas, parcelas e entrada reproduzidas.
- **Aprovar:** aprovar um orçamento → reabrir → negociação preservada. Console sem erros.

- [ ] **Step 4: Atualizar DEV_LOG e finalizar a branch**
- Acrescentar seção de sessão no `DEV_LOG.md`.
- Seguir `superpowers:finishing-a-development-branch`.

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — snapshot da negociacao por orcamento"
```

---

## Self-Review (cobertura da spec)

- **Coluna JSON `negociacao_json`** → Task 1.
- **Salvar entradas (modalidade, formas, parcelas, entrada, datas TF/VP)** → Task 3 (`_capturarNegociacao` + map por modalidade).
- **Reproduzir ao reabrir (recalcular com datas manuais)** → Task 4 (`_restaurarNegociacao`, ordem: parcelas antes das datas; datas re-renderizadas por último).
- **Backend grava/serve o snapshot** → Task 2.
- **Garantia ao aprovar (bloqueia se falhar)** → Task 5.
- **forma_pagamento permanece (contrato)** → preservado em Task 5 (continua no body do PATCH).
- **Descontos já persistidos (sub-projeto anterior)** → não reimplementados.
- **Testes (round-trip + reprodução TF/datas + aprovar)** → Task 1 (pytest) + Task 6 (API/Playwright).
- **Consistência de nomes:** `negociacao_json` (coluna/campo), `_capturarNegociacao`, `_restaurarNegociacao`, `_negociacaoPendente`, `_NEG_CAMPOS_POR_MODALIDADE` — usados de forma idêntica entre as tasks.
