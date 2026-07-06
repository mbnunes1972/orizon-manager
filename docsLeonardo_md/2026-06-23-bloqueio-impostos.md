# Bloqueio dos Campos de Impostos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ocultar a base tributária e a provisão de impostos da tela com um cadeado, revelando-as só por senha de Diretor ou Gerente Administrativo-Financeiro.

**Architecture:** O frontend continua calculando os impostos, mas mascara a exibição (🔒) até que um endpoint backend valide credenciais com a capacidade `aprovar_financeiro`. `_renderImpostosLock()` é o único ponto de exibição; `_impostosLiberados` (não persistido) controla mostrar valor × cadeado.

**Tech Stack:** Python 3 (stdlib http.server, SQLAlchemy/sqlite), frontend HTML/JS vanilla em `static/index.html`, pytest. No WSL é `python3` (não `python`).

## Global Constraints

- **Quem libera:** capacidade **`aprovar_financeiro`** (diretor + gerente_adm_fin). NÃO `autorizar`.
- **Campos mascarados:** `${p}-r-base-trib` e `${p}-r-impostos` para `p` em `ay/cc/vp/tf`.
- **Liberação não persistida:** `_impostosLiberados` é estado de JS (default `false`); recarregar re-bloqueia. Sem sessão/cookie/timer (tratamento futuro).
- **Bloqueio de apresentação:** os valores são calculados no frontend e ficam no cliente — não é sigilo criptográfico.
- **Distinção de erro:** credencial inválida → **401**; credencial válida sem `aprovar_financeiro` → **403**.
- Backend ~293 testes a manter verdes. Sem harness JS → frontend é validação manual. `git add` só dos arquivos da task.

---

### Task 1: Endpoint `POST /api/auth/liberar_impostos`

**Files:**
- Modify: `main.py` (novo handler no `do_POST`, junto aos handlers `/api/auth/...`)
- Test: `tests/test_liberar_impostos.py` (criar)

**Interfaces:**
- Consumes: `get_session()`, modelo `Usuario` (`.ativo`, `.check_senha(senha)`, `.nivel`, `.nome`), `perfis.pode(nivel, capacidade)`.
- Produces: `POST /api/auth/liberar_impostos` body `{login_autorizador, senha_autorizador}` → `{ok, autorizador:{nome}}` (200) | `{ok:False, erro}` (401/403).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_liberar_impostos.py
def _mk(app_db, login, nivel):
    db = app_db.get_session()
    u = app_db.Usuario(nome=login, login=login, nivel=nivel, ativo=1)
    u.set_senha("senha123"); db.add(u); db.commit(); db.close()

def _post(http_client_factory, login, senha):
    c = http_client_factory()
    return c.post("/api/auth/liberar_impostos",
                  {"login_autorizador": login, "senha_autorizador": senha})

def test_diretor_libera(http_client_factory, seed):
    st, body = _post(http_client_factory, "dir_l1", "senha123")
    assert st == 200 and body["ok"] and body["autorizador"]["nome"]

def test_gerente_adm_fin_libera(http_client_factory, seed, app_db):
    _mk(app_db, "gaf", "gerente_adm_fin")
    st, body = _post(http_client_factory, "gaf", "senha123")
    assert st == 200 and body["ok"]

def test_gerente_vendas_403(http_client_factory, seed, app_db):
    _mk(app_db, "gv", "gerente_vendas")
    st, body = _post(http_client_factory, "gv", "senha123")
    assert st == 403 and body["ok"] is False

def test_senha_errada_401(http_client_factory, seed):
    st, body = _post(http_client_factory, "dir_l1", "errada")
    assert st == 401 and body["ok"] is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_liberar_impostos.py -v`
Expected: FAIL (rota inexistente → provavelmente 404/erro).

- [ ] **Step 3: Implementar o handler**

Em `main.py`, no `do_POST`, junto aos outros handlers `/api/auth/`, adicionar (usar o alias de regex local — `re` ou `_re` — igual aos vizinhos):

```python
            if re.match(r'^/api/auth/liberar_impostos$', path):
                req = json.loads(body) if body else {}
                login = (req.get("login_autorizador") or "").strip()
                senha = req.get("senha_autorizador") or ""
                db = get_session()
                try:
                    u = db.query(Usuario).filter_by(login=login).first()
                    if not u or not u.ativo or not u.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Usuário ou senha inválidos."}, code=401)
                        return
                    if not perfis.pode(u.nivel, "aprovar_financeiro"):
                        self.send_json({"ok": False, "erro": "Perfil sem permissão para liberar impostos."}, code=403)
                        return
                    self.send_json({"ok": True, "autorizador": {"nome": u.nome}})
                finally:
                    db.close()
                return
```

- [ ] **Step 4: Rodar e ver passar + suíte**

Run: `python3 -m pytest tests/test_liberar_impostos.py -v && python3 -m pytest -q`
Expected: 4 passed; suíte total verde.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_liberar_impostos.py
git commit -m "feat(impostos): endpoint liberar_impostos (checa aprovar_financeiro)"
```

---

### Task 2: Frontend — máscara dos impostos (`_renderImpostosLock`)

**Files:**
- Modify: `static/index.html` (`_atualizarImpostos` ~3995; adicionar estado + `_renderImpostosLock`)

> Sem teste automatizado (sem harness JS) → validação manual no passo final.

- [ ] **Step 1: Estado + cache (perto de `_atualizarImpostos`)**

```javascript
let _impostosLiberados = false;          // não persistido: recarregar re-bloqueia
const _impostosValores = {};             // { prefix: { base, imp } }
const _IMPOSTOS_PREFIXOS = ['ay', 'cc', 'vp', 'tf'];
```

- [ ] **Step 2: `_atualizarImpostos` passa a cachear e delegar**

Substituir o corpo de `_atualizarImpostos(prefixo, valorBase)` por:

```javascript
function _atualizarImpostos(prefixo, valorBase) {
  const cargaPct = parseFloat(document.getElementById('mp-carga-trib')?.value) || 0;
  const impostos = Math.round(valorBase * cargaPct / 100 * 100) / 100;
  _impostosValores[prefixo] = { base: valorBase, imp: impostos };
  _renderImpostosLock();
}
```

- [ ] **Step 3: `_renderImpostosLock` (único exibidor)**

```javascript
function _renderImpostosLock() {
  _IMPOSTOS_PREFIXOS.forEach(p => {
    const v = _impostosValores[p];
    const elBase = document.getElementById(p + '-r-base-trib');
    const elImp  = document.getElementById(p + '-r-impostos');
    if (!v) return;
    if (_impostosLiberados) {
      if (elBase) elBase.textContent = 'R$ ' + fmt(v.base);
      if (elImp)  elImp.textContent  = 'R$ ' + fmt(v.imp);
    } else {
      const lock = '<span style="cursor:pointer" title="Liberar com senha de diretor/gerente adm-fin" onclick="abrirModalLiberarImpostos()">🔒</span>';
      if (elBase) elBase.innerHTML = lock;
      if (elImp)  elImp.innerHTML  = lock;
    }
  });
}
```

- [ ] **Step 4: Validação manual parcial**

Run: `python3 main.py` → hard refresh. Os campos de base/provisão nos painéis de pagamento devem aparecer com 🔒 (clicável). (O modal vem na Task 3.)

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(impostos): mascara base/provisao com cadeado (_renderImpostosLock)"
```

---

### Task 3: Frontend — modal de liberação + re-bloquear

**Files:**
- Modify: `static/index.html` (HTML do modal + funções)

- [ ] **Step 1: HTML do modal (espelha modal-autorizacao, perto dele)**

```html
<div id="modal-liberar-impostos" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:400;align-items:center;justify-content:center">
  <div style="background:var(--card);border:1px solid var(--border2);border-radius:14px;padding:24px;max-width:380px;width:92%">
    <div style="font-family:'Epilogue',sans-serif;font-weight:900;font-size:15px;margin-bottom:6px">Liberar impostos</div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:14px">Senha de Diretor ou Gerente Administrativo-Financeiro.</div>
    <input id="li-login" placeholder="Usuário" style="width:100%;margin-bottom:8px;padding:8px;background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text)">
    <input id="li-senha" type="password" placeholder="Senha" onkeydown="if(event.key==='Enter')confirmarLiberarImpostos()" style="width:100%;margin-bottom:8px;padding:8px;background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text)">
    <div id="li-erro" style="font-size:11px;color:var(--err);min-height:14px;margin-bottom:8px"></div>
    <div style="display:flex;gap:8px;justify-content:flex-end">
      <button onclick="fecharModalLiberarImpostos()" style="padding:7px 14px;background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer">Cancelar</button>
      <button onclick="confirmarLiberarImpostos()" style="padding:7px 14px;background:var(--accent);border:none;border-radius:6px;color:#fff;font-weight:700;cursor:pointer">Confirmar</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Funções do modal**

```javascript
function abrirModalLiberarImpostos() {
  document.getElementById('li-login').value = '';
  document.getElementById('li-senha').value = '';
  document.getElementById('li-erro').textContent = '';
  document.getElementById('modal-liberar-impostos').style.display = 'flex';
  setTimeout(() => document.getElementById('li-login').focus(), 80);
}
function fecharModalLiberarImpostos() {
  document.getElementById('modal-liberar-impostos').style.display = 'none';
}
async function confirmarLiberarImpostos() {
  const login = document.getElementById('li-login').value.trim();
  const senha = document.getElementById('li-senha').value;
  const erro  = document.getElementById('li-erro');
  erro.textContent = '';
  if (!login || !senha) { erro.textContent = 'Preencha usuário e senha.'; return; }
  try {
    const r = await fetch('/api/auth/liberar_impostos', {
      method: 'POST', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ login_autorizador: login, senha_autorizador: senha }),
    });
    const d = await r.json();
    if (d.ok) {
      _impostosLiberados = true; _renderImpostosLock();
      fecharModalLiberarImpostos();
      showToast('Impostos liberados por ' + d.autorizador.nome);
    } else {
      erro.textContent = d.erro || 'Não autorizado.';
    }
  } catch (e) { erro.textContent = 'Falha na liberação.'; }
}
```

- [ ] **Step 3: Re-bloquear manual (rótulo)**

Localizar o rótulo/cabeçalho da seção de impostos (texto fixo perto dos campos `-r-impostos`, ex.: "Provisão de impostos"). Tornar clicável: `onclick="if(_impostosLiberados){_impostosLiberados=false;_renderImpostosLock();}"` com `title="Clique para ocultar"`. Se não houver um rótulo único, adicionar um pequeno botão "🔓 ocultar" visível só quando `_impostosLiberados` (mostrado/escondido dentro de `_renderImpostosLock`).

- [ ] **Step 4: Validação manual completa**

Run: `python3 main.py` → hard refresh. (a) campos com 🔒; (b) clicar → modal; (c) senha de `dir_l1` → revela base+provisão + toast; (d) senha de um gerente de vendas → erro "sem permissão"; (e) re-bloquear → volta a 🔒; (f) recarregar → 🔒.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(impostos): modal de liberacao por senha + re-bloquear"
```

---

### Task 4: Tela do projeto fechado + DEV_LOG

**Files:**
- Inspecionar/Modify: `static/index.html`; Modify: `DEV_LOG.md`

- [ ] **Step 1: Verificar IDs na tela do projeto fechado**

Run: `grep -n "r-base-trib\|r-impostos\|painel-aymore\|painel-cartao" static/index.html`
Determinar: a tela do projeto fechado reusa os mesmos painéis de pagamento (IDs `-r-base-trib`/`-r-impostos`)? Se SIM, já está coberta por `_renderImpostosLock` (mesmos IDs) — confirmar que `_renderImpostosLock` roda quando essa tela renderiza (chamar `_renderImpostosLock()` ao montá-la, se necessário). Se usa IDs diferentes, acrescentar esses prefixos/IDs à lógica de `_renderImpostosLock`.

- [ ] **Step 2: Garantir o cadeado ao renderizar a tela do projeto fechado**

Se a tela do projeto fechado renderiza os impostos por um caminho que não passa por `_atualizarImpostos`, chamar `_renderImpostosLock()` no fim desse render (e popular `_impostosValores` se preciso). Edição mínima conforme o que o Step 1 achar.

- [ ] **Step 3: Validação manual + DEV_LOG**

Validar no browser que a tela do projeto fechado também mostra 🔒 e libera com senha. Acrescentar entrada ao `DEV_LOG.md`: bloqueio de impostos (cadeado + liberação por senha de diretor/gerente_adm_fin via `aprovar_financeiro`; liberação não persistida; bloqueio de apresentação).

- [ ] **Step 4: Commit**

```bash
git add static/index.html DEV_LOG.md
git commit -m "feat(impostos): cobre tela do projeto fechado + DEV_LOG"
```

---

## Self-Review (autor)

**Cobertura do spec:**
- §1 estado/render (cache + cadeado) → Task 2. ✔
- §2 modal de liberação → Task 3. ✔
- §3 re-bloquear → Task 3 Step 3. ✔
- §4 backend `liberar_impostos` (aprovar_financeiro; 401/403) → Task 1. ✔
- §5 projeto fechado → Task 4. ✔
- §6 testes (E2E diretor/adm-fin/vendas/senha-errada; manual frontend) → Task 1 + manuais. ✔

**Consistência de nomes:** `_impostosLiberados`, `_impostosValores`, `_IMPOSTOS_PREFIXOS`, `_renderImpostosLock()`, `abrirModalLiberarImpostos`/`confirmarLiberarImpostos`/`fecharModalLiberarImpostos`, endpoint `/api/auth/liberar_impostos`, `autorizador.nome` — usados igual entre tasks.

**Observações:** Tasks 2-4 (UI) sem teste automatizado (sem harness JS) → manuais; a autorização (a parte sensível) é coberta pelo E2E da Task 1. Task 4 Step 1 é investigação que pode reduzir a 0 a mudança (se os IDs forem os mesmos).
