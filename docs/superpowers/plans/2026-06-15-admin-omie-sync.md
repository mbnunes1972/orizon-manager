# Admin Panel + Omie Auto-Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar role Admin, sincronização automática de clientes com Omie ao cadastrar, painel de monitoramento/reprocessamento de falhas, e limpeza da navegação lateral.

**Architecture:** Quatro áreas independentes mas relacionadas: (1) limpeza da UI (sidebar + barra de orçamentos), (2) suporte ao role `admin` no banco e frontend, (3) auto-sync de cliente com Omie ao criar (com fallback gracioso), (4) página admin com fila de pendentes/erros e retry. Todas as mudanças residem em `database.py`, `main.py` e `static/index.html`.

**Tech Stack:** Python (SQLite/SQLAlchemy), HTML/CSS/JS vanilla (SPA), Omie REST API via `mod_omie.py`.

---

## Mapa de arquivos

| Arquivo | O que muda |
|---|---|
| `database.py` | Novos campos em `Cliente` (`omie_sync_status`, `omie_sync_erro`, `omie_sync_at`); `admin` em `limite_desconto` e `pode_ver_parametros`; migração automática |
| `main.py` | `POST /api/clientes` tenta criar no Omie; novas rotas `GET /api/admin/omie-sync` e `POST /api/admin/omie-sync/<id>/retry`; `_cliente_dict` expõe campos sync |
| `static/index.html` | Remove nav-new-amb/nav-02/nav-03; barra de orçamentos com 3 botões; nav-07 Admin; page-07 admin panel; `_LIMITES_NIVEL` + labels com `admin`; goPage(7) |

---

## Task 1: database.py — novos campos + suporte admin

**Files:**
- Modify: `database.py`

- [ ] **Step 1: Adicionar campos de sync ao modelo Cliente**

Em `database.py`, após a linha `omie_codigo = Column(String(40), nullable=True)`:

```python
omie_sync_status = Column(String(20),  nullable=True)   # ok | erro | pendente
omie_sync_erro   = Column(Text,        nullable=True)
omie_sync_at     = Column(DateTime,    nullable=True)
```

- [ ] **Step 2: Adicionar 'admin' ao limite_desconto e pode_ver_parametros**

Atualizar as duas properties em `Usuario`:

```python
@property
def limite_desconto(self) -> float:
    limites = {"consultor": 10.0, "gerente": 20.0, "diretor": 50.0, "admin": 50.0}
    return limites.get(self.nivel, 0.0)

@property
def pode_ver_parametros(self) -> bool:
    return self.nivel in ("gerente", "diretor", "admin")
```

> Nota: `diretor` estava em 100.0 — corrigir para 50.0 (limite real do sistema).

- [ ] **Step 3: Adicionar migração automática dos novos campos**

Em `_migrar_colunas`, dentro do bloco `clientes`, adicionar ao array `novas`:

```python
("omie_sync_status", "VARCHAR(20)"),
("omie_sync_erro",   "TEXT"),
("omie_sync_at",     "DATETIME"),
```

- [ ] **Step 4: Testar migração**

```bash
python -c "from database import init_db; init_db(); print('OK')"
```

Esperado: `OK` sem erros. Verificar com:

```bash
python -c "
import sqlite3
c = sqlite3.connect('orizon.db')
cols = [r[1] for r in c.execute('PRAGMA table_info(clientes)').fetchall()]
print(cols)
"
```

Esperado: lista inclui `omie_sync_status`, `omie_sync_erro`, `omie_sync_at`.

- [ ] **Step 5: Commit**

```bash
git add database.py
git commit -m "feat: campos omie_sync em Cliente + role admin no modelo"
```

---

## Task 2: main.py — _cliente_dict + POST /api/clientes com auto-sync

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Atualizar `_cliente_dict` para expor campos de sync**

Localizar a função `_cliente_dict` (linha ~1502) e adicionar após `"omie_codigo": c.omie_codigo or ""`:

```python
"omie_sync_status": c.omie_sync_status or "",
"omie_sync_erro":   c.omie_sync_erro   or "",
"omie_sync_at":     c.omie_sync_at.isoformat() if c.omie_sync_at else "",
```

- [ ] **Step 2: Criar helper `_tentar_sync_omie(c, db)`**

Adicionar função auxiliar antes do bloco de rotas POST (cerca de linha 779). Esta função tenta registrar o cliente no Omie e atualiza os campos de sync no objeto `c` (já persistido):

```python
def _tentar_sync_omie(c, db):
    """Tenta criar cliente no Omie. Atualiza omie_sync_* em c e faz db.commit()."""
    from datetime import datetime as _dt
    if not c.cpf:
        c.omie_sync_status = "pendente"
        c.omie_sync_erro   = "CPF não informado — necessário para registro no Omie"
        c.omie_sync_at     = _dt.utcnow()
        db.commit()
        return

    cfg = config_carregar()
    key    = cfg.get("app_key", "")
    secret = cfg.get("app_secret", "")
    if not key or not secret:
        c.omie_sync_status = "pendente"
        c.omie_sync_erro   = "Credenciais Omie não configuradas"
        c.omie_sync_at     = _dt.utcnow()
        db.commit()
        return

    _set_credenciais(key, secret)
    logs = []
    try:
        codigo = criar_cliente(c.nome, c.cpf, lambda msg, tipo="info": logs.append(msg))
        c.omie_codigo      = str(codigo)
        c.omie_sync_status = "ok"
        c.omie_sync_erro   = None
        c.omie_sync_at     = _dt.utcnow()
    except Exception as e:
        c.omie_sync_status = "erro"
        c.omie_sync_erro   = str(e)
        c.omie_sync_at     = _dt.utcnow()
    db.commit()
```

- [ ] **Step 3: Chamar `_tentar_sync_omie` no POST /api/clientes**

Na rota POST `/api/clientes` (linha ~809), após `db.refresh(c)` e antes de `self.send_json(...)`:

```python
db.refresh(c)
_tentar_sync_omie(c, db)
self.send_json({"ok": True, "cliente": _cliente_dict(c)})
```

- [ ] **Step 4: Testar manualmente**

Iniciar o servidor e criar um cliente via interface. Verificar no log do terminal se houve tentativa de sync. Verificar no banco:

```bash
python -c "
import sqlite3
c = sqlite3.connect('orizon.db')
for row in c.execute('SELECT nome, omie_codigo, omie_sync_status, omie_sync_erro FROM clientes ORDER BY id DESC LIMIT 3').fetchall():
    print(row)
"
```

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: auto-sync cliente para Omie ao criar cadastro"
```

---

## Task 3: main.py — rotas admin (lista + retry)

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Adicionar GET /api/admin/omie-sync**

Adicionar no bloco de rotas GET (próximo às outras rotas `/api/`):

```python
elif path == "/api/admin/omie-sync":
    u = autenticar(self)
    if not u or u.nivel != "admin":
        self.send_json({"ok": False, "erro": "Acesso negado"}, 403)
        return
    db = get_session()
    try:
        clientes = db.query(Cliente).filter(
            Cliente.omie_sync_status.in_(["erro", "pendente"])
        ).order_by(Cliente.omie_sync_at.desc()).all()
        self.send_json({"ok": True, "clientes": [_cliente_dict(c) for c in clientes]})
    finally:
        db.close()
```

- [ ] **Step 2: Adicionar POST /api/admin/omie-sync/<id>/retry**

Adicionar no bloco de rotas POST:

```python
m_sync = re.match(r"^/api/admin/omie-sync/(\d+)/retry$", path)
if m_sync:
    u = autenticar(self)
    if not u or u.nivel != "admin":
        self.send_json({"ok": False, "erro": "Acesso negado"}, 403)
        return
    db = get_session()
    try:
        c = db.get(Cliente, int(m_sync.group(1)))
        if not c:
            self.send_json({"ok": False, "erro": "Cliente não encontrado"})
            return
        _tentar_sync_omie(c, db)
        self.send_json({"ok": True, "cliente": _cliente_dict(c)})
    finally:
        db.close()
```

- [ ] **Step 3: Verificar função `autenticar`**

Confirmar que `autenticar(self)` já existe no código e retorna o objeto `Usuario` ou `None`. Buscar com:

```bash
grep -n "def autenticar" main.py
```

Se não existir, usar o padrão já usado em outras rotas protegidas (buscar como o código valida a sessão do usuário e replicar o mesmo padrão).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat: rotas admin GET/POST omie-sync com controle de acesso"
```

---

## Task 4: index.html — sidebar cleanup + barra de orçamentos

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Limpar sidebar — remover itens de nav**

Localizar e remover as três linhas (~307-309):

```html
<!-- REMOVER estas três linhas: -->
<div class="nav-item locked" id="nav-new-amb" onclick="abrirModalNovoAmbiente()" style="color:var(--muted)">+ Novo ambiente</div>
<div class="nav-item locked" id="nav-02" onclick="goPage(2)">&#x25C6; Negociacao</div>
<div class="nav-item locked" id="nav-03" onclick="goPage(3)">&#x2191; Exportar</div>
```

Substituir por item Admin (oculto por padrão, mostrado via JS):

```html
<div class="nav-item" id="nav-07" onclick="goPage(7)" style="display:none">&#x2699;&#xFE0F; Admin</div>
```

- [ ] **Step 2: Limpar JS lock/unlock de nav-new-amb, nav-02, nav-03**

Localizar a função `goPage` (~linha 1808) e remover referências a `nav-new-amb`, `nav-02`, `nav-03`. Localizar `unlockNav` e remover o mesmo. Buscar com:

```
grep -n "nav-new-amb\|nav-02\|nav-03" static/index.html
```

Remover apenas os blocos que fazem lock/unlock desses ids (não remover os comentários de documentação se existirem em outro contexto).

- [ ] **Step 3: Atualizar barra de orçamentos (~linha 590)**

Substituir:

```html
<button class="btn btn-ghost btn-sm" onclick="abrirPainelPool()"
        style="font-size:11px;padding:4px 10px">Ambientes &#9660;</button>
<button class="btn btn-ghost btn-sm" onclick="abrirModalNovoOrc()"
        style="font-size:11px;padding:4px 10px;margin-left:4px">+ Novo</button>
```

Por:

```html
<button class="btn btn-ghost btn-sm" onclick="abrirPainelPool()"
        style="font-size:11px;padding:4px 10px">Ambientes</button>
<button class="btn btn-ghost btn-sm" onclick="abrirModalNovoAmbiente()"
        style="font-size:11px;padding:4px 10px;margin-left:4px">Novo Ambiente</button>
<button class="btn btn-ghost btn-sm" onclick="abrirModalNovoOrc()"
        style="font-size:11px;padding:4px 10px;margin-left:4px">Novo Orçamento</button>
```

- [ ] **Step 4: Confirmar que goPage(7) funciona**

A função `goPage` atual (~linha 1810) usa `'page-0'+n`, então `goPage(7)` busca `page-07`. Confirmar que a lógica cobre n=7 (não há exceção especial como há para n=9). Se houver, ajustar:

```javascript
function goPage(n){
  const pageId = n === 9 ? 'page-09' : 'page-0'+n;
  // ...resto igual
```

Para n=7 isso produz `'page-07'` — correto, sem mudança necessária.

- [ ] **Step 5: Commit parcial**

```bash
git add static/index.html
git commit -m "feat: sidebar cleanup + barra de orçamentos com 3 botões"
```

---

## Task 5: index.html — page-07 Admin Panel + JS

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Adicionar page-07 ao HTML**

Inserir após a `div#page-06` (Parceiros) e antes de `div#page-03`:

```html
<!-- PAGE 07: Admin -->
<div class="page" id="page-07">
  <div class="page-title">&#x2699;&#xFE0F; Painel Admin</div>
  <div class="page-sub">Monitoramento e sincronização Omie</div>

  <div class="card" style="margin-bottom:16px">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div style="font-family:'Epilogue',sans-serif;font-weight:700;font-size:14px">Fila Omie — Clientes pendentes / com erro</div>
      <button class="btn btn-ghost btn-sm" onclick="adminCarregar()" style="font-size:11px">&#x21BA; Atualizar</button>
    </div>
    <div id="admin-sync-lista">
      <div style="color:var(--muted);font-size:12px;text-align:center;padding:20px">Carregando...</div>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Adicionar JS — adminCarregar() e adminRetry(id)**

Inserir o bloco JS próximo às funções de clientes/parceiros (buscar `// ── Parceiros` e inserir após):

```javascript
// ── Admin Panel ───────────────────────────────────────────────────────────────

async function adminCarregar() {
  const lista = document.getElementById('admin-sync-lista');
  if (!lista) return;
  lista.innerHTML = '<div style="color:var(--muted);font-size:12px;text-align:center;padding:20px">Carregando...</div>';
  try {
    const r = await fetch('/api/admin/omie-sync');
    const d = await r.json();
    if (!d.ok) { lista.innerHTML = `<div style="color:var(--err);padding:12px">${esc(d.erro||'Erro')}</div>`; return; }
    if (!d.clientes.length) {
      lista.innerHTML = '<div style="color:var(--ok);font-size:12px;text-align:center;padding:20px">✓ Nenhum pendente — todos sincronizados.</div>';
      return;
    }
    lista.innerHTML = d.clientes.map(c => `
      <div style="display:flex;align-items:flex-start;justify-content:space-between;
                  padding:10px 0;border-bottom:1px solid var(--border);gap:12px" id="admin-row-${c.id}">
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;font-size:13px">${esc(c.nome)}</div>
          <div style="font-size:11px;color:var(--muted)">CPF: ${esc(c.cpf||'—')} &nbsp;|&nbsp; Status:
            <span style="color:${c.omie_sync_status==='erro'?'var(--err)':'var(--warn)'}">
              ${esc(c.omie_sync_status||'—')}
            </span>
          </div>
          ${c.omie_sync_erro ? `<div style="font-size:10px;color:var(--err);margin-top:2px;word-break:break-word">${esc(c.omie_sync_erro)}</div>` : ''}
          ${c.omie_sync_at  ? `<div style="font-size:10px;color:var(--muted)">${esc(c.omie_sync_at.substring(0,19).replace('T',' '))}</div>` : ''}
        </div>
        <button class="btn btn-ghost btn-sm" onclick="adminRetry(${c.id})"
                style="font-size:11px;white-space:nowrap" id="admin-btn-${c.id}">&#x21BA; Tentar</button>
      </div>`).join('');
  } catch(e) {
    lista.innerHTML = `<div style="color:var(--err);padding:12px">Erro de conexão: ${esc(String(e))}</div>`;
  }
}

async function adminRetry(id) {
  const btn = document.getElementById('admin-btn-'+id);
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  try {
    const r = await fetch('/api/admin/omie-sync/'+id+'/retry', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const d = await r.json();
    if (!d.ok) { showToast('Erro: '+(d.erro||'falha'), true); if(btn){btn.disabled=false;btn.textContent='↺ Tentar';} return; }
    if (d.cliente.omie_sync_status === 'ok') {
      const row = document.getElementById('admin-row-'+id);
      if (row) row.remove();
      showToast('Cliente sincronizado com Omie ✓');
      const lista = document.getElementById('admin-sync-lista');
      if (lista && !lista.querySelector('[id^="admin-row-"]')) {
        lista.innerHTML = '<div style="color:var(--ok);font-size:12px;text-align:center;padding:20px">✓ Nenhum pendente — todos sincronizados.</div>';
      }
    } else {
      showToast('Ainda com erro: '+(d.cliente.omie_sync_erro||'—'), true);
      if (btn) { btn.disabled=false; btn.textContent='↺ Tentar'; }
      adminCarregar();
    }
  } catch(e) {
    showToast('Erro: '+e, true);
    if (btn) { btn.disabled=false; btn.textContent='↺ Tentar'; }
  }
}
```

- [ ] **Step 3: Carregar admin panel ao entrar na page-07**

Na função `goPage` (~linha 1808), adicionar ao bloco de carregamento por página (onde estão `if(n===5) cliCarregar()`, `if(n===6) parCarregar()`):

```javascript
if (n === 7) adminCarregar();
```

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: page-07 painel admin com fila Omie e retry"
```

---

## Task 6: index.html — suporte ao role admin no frontend

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Atualizar `_LIMITES_NIVEL`**

Localizar (~linha 1559):

```javascript
const _LIMITES_NIVEL = { consultor: 10, gerente: 20, diretor: 50 };
```

Substituir por:

```javascript
const _LIMITES_NIVEL = { consultor: 10, gerente: 20, diretor: 50, admin: 50 };
```

- [ ] **Step 2: Atualizar labels de nível nos modais de autorização**

Há dois objetos `nivelLabel` no código (~linhas 4101 e 4480). Adicionar `admin` em ambos:

```javascript
const nivelLabel = { consultor: 'Consultor', gerente: 'Gerente', diretor: 'Diretor', admin: 'Admin' }[nivel] || nivel;
```

- [ ] **Step 3: Mostrar nav-07 para role admin**

Na função que carrega o usuário após login (buscar onde `_usuarioAtual = d.usuario` e `atualizarSidebarUsuario()` são chamados), adicionar após setar `_usuarioAtual`:

```javascript
const navAdmin = document.getElementById('nav-07');
if (navAdmin) navAdmin.style.display = _usuarioAtual?.nivel === 'admin' ? '' : 'none';
```

- [ ] **Step 4: Exibir "Admin" no display de nível na sidebar e modal**

Na sidebar há `id="sb-user-nivel"` que mostra o nível. O texto já vem do objeto `u.nivel`. Adicionar no mesmo bloco a exibição correta para admin (já funciona pois exibe o valor bruto do campo).

Na modal de parâmetros há `id="mp-nivel-display"` com texto "Limite de desconto: X%". Verificar se o texto exibe corretamente para admin com o `_LIMITES_NIVEL` atualizado — deve funcionar sem mudança adicional.

- [ ] **Step 5: Criar usuário admin de teste no banco**

```bash
python -c "
from database import get_session, Usuario
db = get_session()
u = Usuario(nome='Administrador', login='admin2026', nivel='admin')
u.set_senha('admin123')
db.add(u)
db.commit()
print('Admin criado — login: admin2026 / senha: admin123')
db.close()
"
```

> Alterar senha antes de ir para produção.

- [ ] **Step 6: Testar fluxo completo**

1. Login como `admin2026`
2. Verificar que nav-07 ⚙️ Admin aparece na sidebar
3. Clicar em Admin → painel carrega
4. Criar um cliente sem CPF → verificar que aparece como `pendente` no painel admin
5. Criar cliente com CPF e credenciais Omie configuradas → verificar `ok` ou `erro` no banco
6. No painel admin, clicar "↺ Tentar" num cliente com erro → verificar resultado

- [ ] **Step 7: Commit final**

```bash
git add static/index.html database.py main.py
git commit -m "feat: role admin completo — painel, nav, limites e labels"
```

---

## Self-Review

**Spec coverage:**
- ✅ Remove sidebar: nav-new-amb, nav-02, nav-03 → Task 4
- ✅ Barra orçamentos: Ambientes | Novo Ambiente | Novo Orçamento → Task 4
- ✅ Role admin com acesso a vendas → Tasks 1, 6
- ✅ Auto-sync cliente→Omie ao criar → Task 2
- ✅ Painel admin com fila de erros/pendentes → Tasks 3, 5
- ✅ Retry de sync pelo painel → Tasks 3, 5
- ✅ Sem registro manual no Omie (sistema gerencia) → Tasks 2, 3

**Placeholder scan:** Nenhum TBD/TODO — todos os passos têm código completo.

**Type consistency:**
- `_tentar_sync_omie(c, db)` definida em Task 2, usada em Tasks 2 e 3 ✅
- `_cliente_dict` atualizada em Task 2, retornada em Tasks 2 e 3 ✅
- `adminCarregar()` definida em Task 5, chamada em Task 5 (goPage) ✅
- `adminRetry(id)` definida em Task 5, chamada no HTML de Task 5 ✅
- `nav-07` / `page-07` consistentes entre Tasks 4, 5 e 6 ✅
