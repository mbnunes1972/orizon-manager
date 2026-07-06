# Lista de Projetos — Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir os cards de projeto por uma tabela com status de pipeline, filtros de texto e multi-seleção por status, e enriquecer a API com CPF do cliente e valor do último orçamento.

**Architecture:** Três camadas de mudança independentes: (1) `database.py` — novo modelo `Projeto` com status/datas; (2) `main.py` + `mod_omie.py` — enriquecer listagem com status e valor, nova rota PATCH, setar "convertido" ao bloquear; (3) `static/index.html` — redesign da page-00 em tabela com filtros e dropdown inline de status.

**Tech Stack:** Python/SQLAlchemy/SQLite, HTML/CSS/JS vanilla, padrões existentes do projeto (SPA de arquivo único).

---

## Mapa de arquivos

| Arquivo | Mudanças |
|---------|----------|
| `database.py` | Novo modelo `Projeto`; função `_upsert_projeto_status` |
| `main.py` | `_enriquecer_projetos_com_status` após listar; rota `PATCH /api/projetos/<nome>/status`; setar "convertido" após bloquear |
| `mod_omie.py` | `_listar_projetos` passa a incluir `cliente_cpf` |
| `static/index.html` | CSS tabela; HTML page-00 com status filter; JS renderização em linhas + dropdown inline |

---

## Task 1: database.py — modelo Projeto + _upsert_projeto_status

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\database.py`

- [ ] **Step 1: Adicionar modelo Projeto**

Após o modelo `Parceiro` (antes de `# ── EP-07`), inserir:

```python
class Projeto(Base):
    """Metadados de pipeline por projeto. nome_safe é a chave natural (nome da pasta)."""
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,   primary_key=True)
    status     = Column(String(20), nullable=True)   # quente | morno | frio | convertido | perdido
    status_at  = Column(DateTime,   nullable=True)
    perdido_em = Column(DateTime,   nullable=True)
```

- [ ] **Step 2: Adicionar _upsert_projeto_status ao database.py**

Após a função `get_session()`, no final do arquivo:

```python
def upsert_projeto_status(nome_safe: str, status: str, perdido_em=None):
    """Cria ou atualiza o registro de status do projeto. Thread-safe via sessão própria."""
    from datetime import datetime as _dt
    db = get_session()
    try:
        p = db.get(Projeto, nome_safe)
        if not p:
            p = Projeto(nome_safe=nome_safe)
            db.add(p)
        antigo_status = p.status
        p.status    = status
        p.status_at = _dt.utcnow()
        if status == "perdido":
            p.perdido_em = perdido_em or _dt.utcnow()
        elif antigo_status == "perdido" and status != "perdido":
            p.perdido_em = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

- [ ] **Step 3: Testar criação da tabela**

```
python -c "from database import init_db, Projeto; init_db(); print('OK')"
```

Esperado: `OK`

Verificar tabela criada:
```
python -c "
import sqlite3
c = sqlite3.connect('omie.db')
tables = [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('projetos_meta' in tables)
"
```
Esperado: `True`

- [ ] **Step 4: Testar upsert_projeto_status**

```
python -c "
from database import upsert_projeto_status, get_session, Projeto
upsert_projeto_status('proj_teste', 'quente')
db = get_session()
p = db.get(Projeto, 'proj_teste')
print(p.status, p.status_at is not None)
db.close()
"
```
Esperado: `quente True`

- [ ] **Step 5: Commit**

```
git add database.py
git commit -m "feat: modelo Projeto com status pipeline + upsert_projeto_status"
```

---

## Task 2: mod_omie.py — _listar_projetos inclui cliente_cpf

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\mod_omie.py`

O campo `cliente_cpf` já é referenciado em `_buscar_projetos` mas não é populado por `_listar_projetos`. Corrigir isso.

- [ ] **Step 1: Atualizar _listar_projetos para incluir cliente_cpf**

Localizar `_listar_projetos` (~linha 132). No dict que é adicionado ao `resultado`, adicionar após `'cliente_id': proj.get('cliente_id'),`:

```python
'cliente_cpf': cli.get('cpf', '') if isinstance(cli, dict) else '',
```

O resultado do dict completo fica:
```python
resultado.append({
    'nome_safe':      nome_safe,
    'nome_projeto':   proj.get('nome_projeto', proj.get('cliente', '')),
    'cliente_nome':   cliente_nome,
    'cliente_id':     proj.get('cliente_id'),
    'cliente_cpf':    cli.get('cpf', '') if isinstance(cli, dict) else '',
    'parceiro_id':    proj.get('parceiro_id'),
    'atualizado_em':  proj.get('atualizado_em', ''),
    'n_ambientes':    len(proj.get('ambientes', [])),
    'n_selecionados': sum(1 for a in proj.get('ambientes', []) if a.get('selecionado')),
})
```

- [ ] **Step 2: Verificar**

```
python -c "
from mod_omie import _listar_projetos
ps = _listar_projetos()
if ps:
    print('cliente_cpf' in ps[0])
else:
    print('sem projetos — ok')
"
```
Esperado: `True` ou `sem projetos — ok`

- [ ] **Step 3: Commit**

```
git add mod_omie.py
git commit -m "feat: _listar_projetos inclui cliente_cpf"
```

---

## Task 3: main.py — enriquecer projetos com status e último orçamento

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\main.py`

- [ ] **Step 1: Adicionar função _enriquecer_projetos_com_status**

Após a função `_enriquecer_projetos_com_pool` (~linha 40), adicionar:

```python
def _enriquecer_projetos_com_status(projetos):
    """Adiciona status e ultimo_orcamento_valor a cada projeto da lista."""
    if not projetos:
        return
    from sqlalchemy import func
    nomes = [p['nome_safe'] for p in projetos if p.get('nome_safe')]
    if not nomes:
        return
    db = get_session()
    try:
        # Status pipeline
        metas = db.query(Projeto).filter(Projeto.nome_safe.in_(nomes)).all()
        meta_map = {m.nome_safe: m for m in metas}

        # Último orçamento: valor_total do registro com updated_at mais recente
        subq = (
            db.query(
                Orcamento.projeto_id,
                func.max(Orcamento.updated_at).label("max_at")
            )
            .filter(Orcamento.projeto_id.in_(nomes))
            .group_by(Orcamento.projeto_id)
            .subquery()
        )
        orc_rows = (
            db.query(Orcamento)
            .join(subq, (Orcamento.projeto_id == subq.c.projeto_id) &
                        (Orcamento.updated_at == subq.c.max_at))
            .all()
        )
        orc_map = {o.projeto_id: o.valor_total for o in orc_rows}

        for p in projetos:
            ns = p.get('nome_safe')
            if not ns:
                continue
            meta = meta_map.get(ns)
            p['status']                  = meta.status     if meta else None
            p['status_at']               = meta.status_at.isoformat() if meta and meta.status_at else None
            p['perdido_em']              = meta.perdido_em.isoformat() if meta and meta.perdido_em else None
            p['ultimo_orcamento_valor']  = orc_map.get(ns)
    finally:
        db.close()
```

Garantir que `Projeto` e `Orcamento` estão importados de `database`. Localizar a linha de import de `database` (~linha 1) e adicionar `Projeto` e `Orcamento` se ainda não estiverem:

```python
from database import (get_session, init_db, Usuario, Sessao, LogAutorizacao,
                      Cliente, Parceiro, PoolAmbiente, Orcamento, OrcamentoAmbiente,
                      Projeto, upsert_projeto_status)
```

- [ ] **Step 2: Chamar _enriquecer_projetos_com_status nas rotas GET /projetos e GET /projetos/buscar**

Na rota `GET /projetos` (~linha 190), após `_enriquecer_projetos_com_pool(projetos)` adicionar:
```python
_enriquecer_projetos_com_status(projetos)
```

Na rota `GET /projetos/buscar` (~linha 194), após `_enriquecer_projetos_com_pool(locais)` adicionar:
```python
_enriquecer_projetos_com_status(locais)
```

- [ ] **Step 3: Verificar sintaxe**

```
python -c "import main; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```
git add main.py
git commit -m "feat: projetos enriquecidos com status pipeline e valor do último orçamento"
```

---

## Task 4: main.py — PATCH /api/projetos/<nome_safe>/status + "convertido" automático

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\main.py`

- [ ] **Step 1: Adicionar rota PATCH /api/projetos/<nome_safe>/status**

No bloco de rotas que trata métodos não-GET/POST (ou adicionar um bloco `do_PATCH` se não existir).

Verificar se o servidor tem `do_PATCH`. Buscar com:
```
grep -n "def do_PATCH\|def do_PUT\|def do_" main.py | head -10
```

Se não existir `do_PATCH`, adicionar após `do_POST`:

```python
def do_PATCH(self):
    try:
        import re as _re
        path = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b'{}'

        m = _re.match(r'^/api/projetos/([^/]+)/status$', path)
        if m:
            from urllib.parse import unquote
            nome_safe = unquote(m.group(1))
            req = json.loads(body)
            novo_status = (req.get('status') or '').strip().lower()
            VALIDOS = {'quente', 'morno', 'frio', 'perdido'}
            if novo_status not in VALIDOS:
                self.send_json({"ok": False, "erro": f"Status inválido. Use: {', '.join(sorted(VALIDOS))}"})
                return
            upsert_projeto_status(nome_safe, novo_status)
            self.send_json({"ok": True, "status": novo_status})
            return

        self.send_json({"ok": False, "erro": "Rota não encontrada"}, 404)
    except Exception as e:
        self.send_json({"ok": False, "erro": str(e)}, 500)

def send_json(self, data, code=200):
    body = json.dumps(data, ensure_ascii=False).encode()
    self.send_response(code)
    self.send_header('Content-Type', 'application/json')
    self.send_header('Content-Length', len(body))
    self.end_headers()
    self.wfile.write(body)
```

> **Atenção:** se `send_json` já existir no arquivo (muito provável), NÃO redefinir — remover o bloco duplicado. Verificar com `grep -n "def send_json" main.py`. Incluir apenas o `do_PATCH` com o bloco `send_json` **removido**.

- [ ] **Step 2: Setar "convertido" automaticamente ao bloquear projeto**

Na rota POST `/exportar` (~linha 517), após `bloquear_projeto(nome_safe_para_bloquear)` e o log correspondente:

```python
try:
    bloquear_projeto(nome_safe_para_bloquear)
    log_cb("Projeto bloqueado — XMLs travados com hash SHA-256.", "ok")
    session_set("projeto_bloqueado", True)
    # Seta status "convertido" automaticamente
    try:
        upsert_projeto_status(nome_safe_para_bloquear, "convertido")
    except Exception as e_status:
        log_cb(f"Aviso: status convertido não pôde ser salvo: {e_status}", "warn")
except Exception as e_lock:
    log_cb("Aviso: nao foi possivel bloquear o projeto: %s" % e_lock, "warn")
```

- [ ] **Step 3: Verificar sintaxe**

```
python -c "import main; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```
git add main.py
git commit -m "feat: PATCH status projeto + convertido automático ao aprovar"
```

---

## Task 5: index.html — CSS + HTML page-00 redesign

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\static\index.html`

- [ ] **Step 1: Adicionar CSS da tabela de projetos**

Localizar o bloco de CSS das classes de projeto (`.proj-card-item`, `.proj-card-nome`, etc., ~linhas 75-80). Após esse bloco, adicionar:

```css
/* Tabela de projetos */
.proj-table{width:100%;border-collapse:collapse;font-size:13px}
.proj-table th{text-align:left;padding:7px 12px;font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--muted);border-bottom:1px solid var(--border);font-weight:600}
.proj-table td{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:middle}
.proj-table tr.proj-row:hover td{background:rgba(232,97,26,.04);cursor:pointer}
.proj-table tr.proj-row td.cell-status{cursor:default}
.proj-status-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700;letter-spacing:.3px;white-space:nowrap}
.proj-status-badge.quente{background:rgba(240,90,80,.12);color:#f05a50}
.proj-status-badge.morno{background:rgba(251,191,36,.12);color:#d4a017}
.proj-status-badge.frio{background:rgba(96,165,250,.12);color:var(--section)}
.proj-status-badge.convertido{background:rgba(25,201,160,.12);color:var(--ok)}
.proj-status-badge.perdido{background:rgba(120,120,120,.12);color:var(--muted)}
.proj-status-badge.sem{background:transparent;color:var(--muted)}
.proj-status-dd{position:absolute;top:100%;left:0;z-index:300;background:var(--card);border:1px solid var(--border2);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.4);min-width:140px;overflow:hidden;display:none}
.proj-status-dd.open{display:block}
.proj-status-dd-item{padding:8px 14px;font-size:12px;cursor:pointer;display:flex;align-items:center;gap:8px}
.proj-status-dd-item:hover{background:var(--surface)}
/* Filtro multi-select status */
.proj-status-filter-wrap{position:relative;display:inline-block}
.proj-status-filter-dd{position:absolute;top:100%;right:0;z-index:300;background:var(--card);border:1px solid var(--border2);border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.4);min-width:160px;padding:6px 0;display:none;margin-top:4px}
.proj-status-filter-dd.open{display:block}
.proj-status-filter-item{display:flex;align-items:center;gap:8px;padding:6px 14px;font-size:12px;cursor:pointer}
.proj-status-filter-item:hover{background:var(--surface)}
```

- [ ] **Step 2: Substituir HTML da page-00**

Localizar a `<div class="page active" id="page-00">` (~linha 490) e substituir seu conteúdo interno (do título até `</div>` que fecha `proj-resultados`) por:

```html
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px">
  <div class="page-title" style="margin:0">Projetos</div>
  <button class="btn btn-primary btn-sm" onclick="mostrarFormNovoProjeto()">+ Novo Projeto</button>
</div>

<div id="form-novo-projeto" class="p00-form" style="display:none">
  <!-- [manter formulário existente intacto — não alterar] -->
</div>

<div style="display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap">
  <div style="flex:1;position:relative;min-width:200px">
    <input type="text" id="proj-search" placeholder="Filtrar por nome, cliente ou CPF..."
           oninput="projAplicarFiltros()" class="inp" style="width:100%;box-sizing:border-box;padding-right:32px">
    <div class="search-spinner" id="proj-spinner" style="position:absolute;right:8px;top:50%;transform:translateY(-50%)"><div class="spinner"></div></div>
  </div>
  <div class="proj-status-filter-wrap">
    <button class="btn btn-ghost btn-sm" id="proj-status-filter-btn"
            onclick="projToggleStatusFilter(event)" style="font-size:11px;white-space:nowrap">
      Status &#9660;
    </button>
    <div class="proj-status-filter-dd" id="proj-status-filter-dd">
      <label class="proj-status-filter-item"><input type="checkbox" value="quente"    checked onchange="projAplicarFiltros()"> 🔥 Quente</label>
      <label class="proj-status-filter-item"><input type="checkbox" value="morno"     checked onchange="projAplicarFiltros()"> ● Morno</label>
      <label class="proj-status-filter-item"><input type="checkbox" value="frio"      checked onchange="projAplicarFiltros()"> ❄ Frio</label>
      <label class="proj-status-filter-item"><input type="checkbox" value="convertido" checked onchange="projAplicarFiltros()"> ✓ Convertido</label>
      <label class="proj-status-filter-item"><input type="checkbox" value="perdido"   checked onchange="projAplicarFiltros()"> ✗ Perdido</label>
      <label class="proj-status-filter-item"><input type="checkbox" value="sem"       checked onchange="projAplicarFiltros()"> — Sem status</label>
    </div>
  </div>
</div>
<div id="proj-search-hint" style="font-size:11px;color:var(--muted);height:16px;margin-bottom:8px"></div>
<div id="proj-resultados"></div>
```

> **Atenção:** ao substituir, preservar o bloco `<div id="form-novo-projeto"...>` com todo o seu conteúdo original (não alterá-lo).

- [ ] **Step 3: Commit**

```
git add static/index.html
git commit -m "feat: page-00 redesign HTML/CSS — tabela projetos com filtro status"
```

---

## Task 6: index.html — JS renderização em tabela + filtros + dropdown status inline

**Files:**
- Modify: `E:\2026\estudo_de_ia\omie_v3\static\index.html`

- [ ] **Step 1: Substituir renderProjResultados por versão tabela**

Localizar a função `renderProjResultados` (~linha 1934) e substituí-la inteiramente por:

```javascript
const _PROJ_STATUS_LABEL = {
  quente:     { label: '🔥 Quente',     cls: 'quente'    },
  morno:      { label: '● Morno',       cls: 'morno'     },
  frio:       { label: '❄ Frio',        cls: 'frio'      },
  convertido: { label: '✓ Convertido',  cls: 'convertido'},
  perdido:    { label: '✗ Perdido',     cls: 'perdido'   },
};

function _projStatusBadge(p){
  const s = p.status;
  if(!s) return `<span class="proj-status-badge sem" data-nome="${esc(p.nome_safe||'')}">—</span>`;
  if(s === 'convertido') return `<span class="proj-status-badge convertido">✓ Convertido</span>`;
  const info = _PROJ_STATUS_LABEL[s] || {label:s, cls:'sem'};
  return `<span class="proj-status-badge ${info.cls}" style="cursor:pointer"
               onclick="projStatusClick(event,'${esc(p.nome_safe||'')}')">${esc(info.label)}</span>`;
}

function renderProjResultados(lista){
  const el = document.getElementById('proj-resultados');
  if(!lista.length){
    el.innerHTML='<div style="text-align:center;padding:32px;color:var(--muted);font-size:13px">Nenhum projeto encontrado.</div>';
    return;
  }
  const fmt = v => v != null ? 'R$ '+Number(v).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}) : '—';
  const fmtData = s => s ? s.substring(0,10).split('-').reverse().join('/') : '—';
  el.innerHTML = `
    <table class="proj-table">
      <thead><tr>
        <th style="width:130px">Status</th>
        <th style="width:100px">Data</th>
        <th>Projeto</th>
        <th>Cliente</th>
        <th style="width:140px;text-align:right">Último Orçamento</th>
      </tr></thead>
      <tbody>
        ${lista.map(p=>`
        <tr class="proj-row" data-nome="${esc(p.nome_safe||'')}">
          <td class="cell-status" style="position:relative">
            ${_projStatusBadge(p)}
            <div class="proj-status-dd" id="proj-dd-${esc(p.nome_safe||'')}">
              ${['quente','morno','frio','perdido'].map(s=>`
                <div class="proj-status-dd-item" onclick="projStatusSet('${esc(p.nome_safe||'')}','${s}')">
                  ${esc(_PROJ_STATUS_LABEL[s].label)}
                </div>`).join('')}
            </div>
          </td>
          <td onclick="abrirProjeto('${esc(p.nome_safe||'')}')">${fmtData(p.atualizado_em||p.criado_em||'')}</td>
          <td onclick="abrirProjeto('${esc(p.nome_safe||'')}')" style="font-weight:600">${esc(p.nome_projeto||'—')}</td>
          <td onclick="abrirProjeto('${esc(p.nome_safe||'')}')" style="color:var(--muted)">${esc(p.cliente_nome||'—')}</td>
          <td onclick="abrirProjeto('${esc(p.nome_safe||'')}')" style="text-align:right;font-family:'IBM Plex Mono',monospace;font-size:12px">${fmt(p.ultimo_orcamento_valor)}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;

  // Click fora fecha dropdowns
  document.querySelectorAll('.proj-row').forEach(row=>{
    row.addEventListener('click', e=>{
      if(!e.target.closest('.cell-status')) return;
    });
  });
}
```

- [ ] **Step 2: Adicionar funções de status inline e filtros**

Após `renderProjResultados`, adicionar:

```javascript
function projStatusClick(e, nomeSafe){
  e.stopPropagation();
  // Fecha outros dropdowns abertos
  document.querySelectorAll('.proj-status-dd.open').forEach(d=>{
    if(d.id !== 'proj-dd-'+nomeSafe) d.classList.remove('open');
  });
  const dd = document.getElementById('proj-dd-'+nomeSafe);
  if(dd) dd.classList.toggle('open');
}

async function projStatusSet(nomeSafe, novoStatus){
  // Fecha dropdown
  const dd = document.getElementById('proj-dd-'+nomeSafe);
  if(dd) dd.classList.remove('open');

  try{
    const r = await fetch('/api/projetos/'+encodeURIComponent(nomeSafe)+'/status', {
      method:'PATCH', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({status: novoStatus})
    });
    const d = await r.json();
    if(!d.ok){ showToast('Erro: '+(d.erro||'falha'), true); return; }
    // Atualiza localmente sem re-fetch
    const p = _projListaBase.find(x=>x.nome_safe===nomeSafe);
    if(p){ p.status = novoStatus; p.status_at = new Date().toISOString(); }
    projAplicarFiltros();
  }catch(e){ showToast('Erro: '+e, true); }
}

function projToggleStatusFilter(e){
  e.stopPropagation();
  document.getElementById('proj-status-filter-dd').classList.toggle('open');
}

// Fechar dropdowns ao clicar fora
document.addEventListener('click', ()=>{
  document.querySelectorAll('.proj-status-dd.open, .proj-status-filter-dd.open')
    .forEach(d=>d.classList.remove('open'));
});

function projAplicarFiltros(){
  const txt = (document.getElementById('proj-search')?.value || '').trim().toLowerCase();
  const checks = [...document.querySelectorAll('#proj-status-filter-dd input[type=checkbox]')];
  const ativos = new Set(checks.filter(c=>c.checked).map(c=>c.value));

  let lista = [..._projListaBase];

  // Filtro de texto (nome projeto + cliente nome + CPF)
  if(txt.length >= 2){
    lista = lista.filter(p=>
      (p.nome_projeto||'').toLowerCase().includes(txt) ||
      (p.cliente_nome||'').toLowerCase().includes(txt) ||
      (p.cliente_cpf||'').replace(/\D/g,'').includes(txt.replace(/\D/g,''))
    );
  }

  // Filtro de status (OR lógico)
  const todosAtivos = checks.every(c=>c.checked) || checks.every(c=>!c.checked);
  if(!todosAtivos){
    lista = lista.filter(p=>{
      const s = p.status || 'sem';
      return ativos.has(s);
    });
  }

  // Atualiza hint
  const hint = document.getElementById('proj-search-hint');
  if(hint) hint.textContent = lista.length ? `${lista.length} projeto(s)` : 'Nenhum resultado';

  // Ordena por data decrescente
  lista.sort((a,b)=>{
    const da = a.atualizado_em||a.criado_em||'';
    const db2 = b.atualizado_em||b.criado_em||'';
    return db2.localeCompare(da);
  });

  renderProjResultados(lista);

  // Atualiza label do botão de filtro
  const btn = document.getElementById('proj-status-filter-btn');
  if(btn){
    const n = checks.filter(c=>c.checked).length;
    btn.textContent = todosAtivos ? 'Status ▾' : `Status (${n}) ▾`;
  }
}
```

- [ ] **Step 3: Atualizar projCarregar e remover projToggleOrdem / projFiltrar / executarBuscaProjeto**

Localizar `projCarregar` (~linha 5165) e substituir por:

```javascript
async function projCarregar(){
  try {
    const r = await fetch('/projetos');
    const d = await r.json();
    if(!d.ok) return;
    _projListaBase = d.projetos || [];
    projAplicarFiltros();
  } catch(e){}
}
```

Localizar e **remover** as funções:
- `projRenderOrdenado()` — substituída por `projAplicarFiltros`
- `projToggleOrdem()` — botão de ordem foi removido
- `projFiltrar()` — substituída por `projAplicarFiltros`
- `executarBuscaProjeto()` — o filtro agora é client-side

Verificar se `projToggleOrdem` ou `projToggleOrdem` são referenciados em algum botão HTML restante. O botão `&#x21C5;` com `onclick="projToggleOrdem()"` foi removido no redesign de HTML (Task 5), então não haverá referências órfãs.

- [ ] **Step 4: Verificar que goPage(0) ainda chama projCarregar**

Confirmar que na função `goPage` existe:
```javascript
if(n===0) projCarregar();
```
Se não existir, adicionar.

- [ ] **Step 5: Commit**

```
git add static/index.html
git commit -m "feat: lista de projetos em tabela com status inline e filtros"
```

---

## Self-Review

**Spec coverage:**
- ✅ Tabela com Status | Data | Projeto | Cliente | Último Orçamento → Tasks 5, 6
- ✅ Filtro texto (nome/cliente/CPF) → Task 6 `projAplicarFiltros`
- ✅ Filtro multi-seleção de status → Tasks 5, 6
- ✅ Status inline dropdown (quente/morno/frio/perdido) → Task 6 `projStatusClick` + `projStatusSet`
- ✅ "Convertido" não editável via dropdown → Task 6 `_projStatusBadge` (sem click handler)
- ✅ "Perdido" grava `perdido_em` → Task 1 `upsert_projeto_status`
- ✅ `ultimo_orcamento_valor` do orçamento mais recente → Task 3
- ✅ `cliente_cpf` na listagem → Task 2
- ✅ Status "convertido" automático ao aprovar → Task 4
- ✅ PATCH /api/projetos/<nome>/status → Task 4
- ✅ Novo projeto já navega para page-02 → **JÁ IMPLEMENTADO** (linha 2317 do index.html)

**Placeholders:** Nenhum.

**Type consistency:**
- `upsert_projeto_status(nome_safe, status)` definida em Task 1, usada em Tasks 3 e 4 ✅
- `projAplicarFiltros()` definida em Task 6, chamada em HTML da Task 5 (`onchange`, `oninput`) ✅
- `projStatusSet(nomeSafe, status)` definida em Task 6, chamada em HTML gerado por `renderProjResultados` ✅
- `projStatusClick(e, nomeSafe)` definida em Task 6, chamada em `_projStatusBadge` ✅
- `_projListaBase` usada em Tasks 6 (lida) e `projCarregar` (escrita) ✅
