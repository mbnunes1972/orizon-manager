# Navegação Consistente: Painel Admin uniforme + Painel Orizon + seletor de empresa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Uniformizar as telas de configuração — o **Painel Admin** vira um conjunto plano de 4 abas (Dados da empresa, Usuários, Perfis de Usuário, Módulos) igual para todo perfil, escopado por um **seletor de empresa** compartilhado com o Config; a administração **do sistema** (redes/lojas/gestores) sai para um novo **Painel Orizon** (só super_admin); e, na Fase 2, abas sem permissão aparecem **trancadas** (cadeado + step-up).

**Architecture:** Backend Python puro (`http.server` + SQLAlchemy/SQLite). O escopo por empresa reaproveita o mecanismo do god-mode (Sessão 80): o seletor arma o header `X-Loja-Ativa` → `_ator_dict`/`_loja_admin_alvo`/`escopo_operacional` já resolvem a loja ativa (inclusive para super_admin). Só há **dois** endpoints novos/ampliados: `GET /api/admin/empresas` (alimenta o seletor) e as flags de capacidade de aba no `/auth/me` (para o cadeado). Todo o resto é reorganização de frontend (`static/index.html`): um novo `page-orizon`, o Admin deixando de ser drill-down, o seletor compartilhado, e as travas por aba.

**Tech Stack:** Python 3 (`python3 -m pytest`, SQLite por padrão); frontend em `static/index.html` (sem teste JS → `node --check` via WSL + verificação manual no navegador).

**Base:** branch `feat/navegacao-consistente` (a partir da `main`, que já contém o god-mode da Sessão 80). Spec: `docs/superpowers/specs/2026-07-16-navegacao-consistente-painel-orizon-design.md`.

---

## File Structure

- **`main.py`** (Modify) — novo `GET /api/admin/empresas`; `/auth/me` (via `auth_routes`) passa a expor as caps de aba.
- **`auth/auth.py`** (Modify) — `_usuario_dict` ganha `pode_gerir_documentos` e `pode_ver_parametros` **derivado de `perfis.pode`** (não da coluna) para o cadeado respeitar o god-mode.
- **`static/index.html`** (Modify) — `nav-orizon` + `page-orizon` (Redes/Lojas/Gestores); Admin plano (reescrita de `adminCarregarConsole`/`adminRender`); seletor de empresa (Admin+Config); Fase 2: cadeado/step-up por aba + nav Admin/Config sempre visível; renomeações.
- **`tests/test_admin_empresas.py`** (Create) — cobre `GET /api/admin/empresas` por perfil.
- **`tests/test_auth_me_caps.py`** (Create) — cobre as caps de aba no `/auth/me`.
- **`DEV_LOG.md`** (Modify) — nova sessão.

---

# FASE 1 — Estrutura (Orizon + Admin plano + seletor)

## Task 1: Backend — `GET /api/admin/empresas` (alimenta o seletor)

**Files:**
- Modify: `main.py` (novo ramo em `do_GET`, junto dos demais `/api/admin/*`)
- Test: `tests/test_admin_empresas.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_admin_empresas.py`:

```python
"""GET /api/admin/empresas — lojas que o ator pode administrar, p/ o seletor de empresa
(topo de Admin/Config). super_admin: todas; admin_rede: da sua rede; loja: a própria; 401 sem login."""


def _logins(c, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    l2 = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    db.close()
    return l1, l2


def test_super_admin_ve_todas_as_empresas(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"], (st, out)
    ids = {e["loja_id"] for e in out["empresas"]}
    assert {l1, l2} <= ids
    # cada item traz nome da loja e da rede (grupo) p/ o agrupamento visual
    assert all("nome" in e and "rede_nome" in e for e in out["empresas"])


def test_usuario_de_loja_ve_so_a_propria(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"]
    ids = {e["loja_id"] for e in out["empresas"]}
    assert ids == {l1}


def test_admin_rede_ve_so_lojas_da_rede(http_client_factory, seed, app_db):
    l1, l2 = _logins(None, seed, app_db)
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"]
    ids = {e["loja_id"] for e in out["empresas"]}
    assert {l1, l2} <= ids     # no seed, l1 e l2 estão na mesma rede do adm_rede


def test_sem_login_401(http_client_factory, seed):
    c = http_client_factory()
    st, out = c.get("/api/admin/empresas")
    assert st == 401
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_admin_empresas.py -q`
Expected: FAIL (rota inexistente → provavelmente 404/HTML; o assert de `out["ok"]` quebra).

- [ ] **Step 3: Implementar o endpoint**

Em `main.py`, no `do_GET`, junto dos outros ramos `/api/admin/*` (perto do `elif path == "/api/admin/perfis":`), adicionar:

```python
        elif path == "/api/admin/empresas":
            # Lojas que o ator pode administrar — alimenta o seletor de empresa (topo de Admin/Config).
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                redes = {r.id: r.nome for r in db.query(Rede).all()}
                empresas = []
                for lo in db.query(Loja).order_by(Loja.nome.asc()).all():
                    if not mod_tenancy.pode_ver_loja(ator, {"id": lo.id, "rede_id": lo.rede_id}):
                        continue
                    empresas.append({"loja_id": lo.id, "nome": lo.nome,
                                     "rede_id": lo.rede_id,
                                     "rede_nome": redes.get(lo.rede_id, "") if lo.rede_id else ""})
                self.send_json({"ok": True, "empresas": empresas})
            finally:
                db.close()
            return
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_admin_empresas.py -q`
Expected: 4 passed. (Nota: `pode_ver_loja` já dá super_admin=todas, admin_rede=da rede, loja=a própria.)

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_admin_empresas.py
git commit -m "feat(admin): GET /api/admin/empresas — lojas administráveis p/ o seletor de empresa

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Backend — caps de aba no `/auth/me` (para o cadeado)

**Files:**
- Modify: `auth/auth.py` (`_usuario_dict`)
- Test: `tests/test_auth_me_caps.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_auth_me_caps.py`:

```python
"""/auth/me expõe as capacidades de aba (p/ o cadeado de Admin/Config) derivadas de perfis.pode —
respeitando o god-mode do super_admin. master libera admin; operador não; super_admin tudo."""


def _me(c):
    _, out = c.get("/api/auth/me")
    return out["usuario"]


def test_caps_de_aba_por_perfil(http_client_factory, seed):
    m = _me(_login(http_client_factory, "dir_l1"))          # master
    assert m["pode_gerir_usuarios"] and m["pode_gerir_perfis"]
    assert m["pode_gerir_documentos"] and m["pode_ver_parametros"]

    o = _me(_login(http_client_factory, "cons_l1"))          # operador
    assert o["pode_gerir_usuarios"] is False and o["pode_gerir_perfis"] is False
    assert o["pode_gerir_documentos"] is False and o["pode_ver_parametros"] is False

    s = _me(_login(http_client_factory, "super"))            # super_admin (god-mode)
    assert s["pode_gerir_usuarios"] and s["pode_gerir_perfis"]
    assert s["pode_gerir_documentos"] and s["pode_ver_parametros"]


def _login(f, who):
    c = f(); c.login(who, "senha123"); return c
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_auth_me_caps.py -q`
Expected: FAIL — hoje `_usuario_dict` não expõe `pode_gerir_documentos`, e `pode_ver_parametros` vem da coluna `u.pode_ver_parametros` (não reflete o god-mode do super_admin).

- [ ] **Step 3: Implementar**

Em `auth/auth.py`, `_usuario_dict`, trocar a linha
`        "pode_ver_parametros": u.pode_ver_parametros,`
por (derivar da matriz de perfil, coerente com o god-mode; e acrescentar documentos):
```python
        "pode_ver_parametros": perfis.pode(u.nivel, "ver_parametros"),
        "pode_gerir_documentos": perfis.pode(u.nivel, "gerir_documentos"),
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_auth_me_caps.py -q`
Expected: PASS.

- [ ] **Step 5: Regressão — nada que lia `pode_ver_parametros` quebrou**

Run: `python3 -m pytest tests/test_acesso_perfil.py tests/test_perfis.py -q`
Expected: PASS. (Se algum teste dependia do valor de COLUNA de `pode_ver_parametros`, ajustar aqui — a fonte passa a ser `perfis.pode`.)

- [ ] **Step 6: Commit**

```bash
git add auth/auth.py tests/test_auth_me_caps.py
git commit -m "feat(auth): /auth/me expõe caps de aba (gerir_documentos, ver_parametros via perfis.pode)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Frontend — Painel Orizon (novo `page-orizon` + `nav-orizon`), extrai plataforma/rede

**Files:**
- Modify: `static/index.html` (sidebar ~551; roteamento `goPage`; novas funções `orizon*`; move o conteúdo de `adminRenderPlataforma`/`adminRenderRede`)

- [ ] **Step 1: Adicionar o item de sidebar `nav-orizon`**

Em `static/index.html` (após `nav-cfg`, linha ~552):
```html
      <div class="nav-item" id="nav-orizon" onclick="goPageOrizon()" style="display:none"><i class="ti ti-building-cog"></i>Painel Orizon</div>
```

- [ ] **Step 2: Criar a `page-orizon`**

Após o fechamento de `page-09` (linha ~1857, após `</div>` que fecha `id="page-09"`), inserir:
```html
  <div class="page" id="page-orizon">
    <div class="page-title" style="margin:0">Painel Orizon</div>
    <div class="page-sub">Administração do sistema — redes, lojas e gestores.</div>
    <div style="display:flex;gap:0;border-bottom:1px solid var(--border);margin:12px 0 16px;flex-wrap:wrap">
      <button class="home-tab ativo" id="orz-tab-redes"    onclick="orizonTab('redes')">Redes</button>
      <button class="home-tab"       id="orz-tab-lojas"    onclick="orizonTab('lojas')">Lojas</button>
      <button class="home-tab"       id="orz-tab-gestores" onclick="orizonTab('gestores')">Gestores gerais</button>
    </div>
    <div id="orz-panel-redes"></div>
    <div id="orz-panel-lojas" style="display:none"></div>
    <div id="orz-panel-gestores" style="display:none"></div>
  </div>
```

- [ ] **Step 3: Gating do `nav-orizon` por `pode_gerir_redes`**

Na função que mostra Admin/Config por perfil (linhas ~2564-2567), acrescentar:
```javascript
    const _navOrizon = document.getElementById('nav-orizon');
    if (_navOrizon) _navOrizon.style.display = (_usuarioAtual && _usuarioAtual.pode_gerir_redes) ? '' : 'none';
```

- [ ] **Step 4: Roteamento — `goPageOrizon()` mostra a page e carrega**

Adicionar (perto das funções de navegação de página; a `goPage` já esconde as demais `.page`):
```javascript
function goPageOrizon(){
  document.querySelectorAll('.page').forEach(p => p.classList.remove('ativa'));
  document.getElementById('page-orizon').classList.add('ativa');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('ativo'));
  document.getElementById('nav-orizon').classList.add('ativo');
  orizonTab('redes');
}
function orizonTab(qual){
  ['redes','lojas','gestores'].forEach(q => {
    const t = document.getElementById('orz-tab-'+q), p = document.getElementById('orz-panel-'+q);
    if (t) t.classList.toggle('ativo', q===qual);
    if (p) p.style.display = q===qual ? '' : 'none';
  });
  if (qual==='redes')    orizonRedesCarregar();
  if (qual==='lojas')    orizonLojasCarregar();
  if (qual==='gestores') orizonGestoresCarregar();
}
```
_(Confirmar no arquivo a classe/rotina exata que `goPage` usa para (des)ativar `.page`/`.nav-item` — casar o padrão. Se `goPage` usa `style.display` em vez de classe `ativa`, espelhar isso aqui.)_

- [ ] **Step 5: Implementar `orizonRedesCarregar`/`orizonLojasCarregar`/`orizonGestoresCarregar`**

Reaproveitar o markup e as chamadas que hoje vivem em `adminRenderPlataforma` (redes + lojas avulsas), `adminRenderRede` (lojas da rede) e o card "Gestores gerais". Redes: `GET/POST /api/admin/redes` + `adminRedeNova`. Lojas: `GET/POST /api/admin/lojas` (avulsas e por rede) + `adminLojaNova`. Gestores: `GET /api/admin/usuarios?escopo=plataforma` + `abrirModalUsuario({escopo:'plataforma'})`. **Mover** (não duplicar) essas funções para o namespace `orizon*`; remover o card "Credenciais e Tokens (Omie)" do fluxo (não recriar — é da Frente 2). Escopo por `pode_ver_loja` no backend já garante que admin_rede (se algum dia vir aqui) só veja a própria rede, mas o `nav-orizon` já é gateado a super_admin.

- [ ] **Step 6: `node --check` (sintaxe do app)**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
python3 - <<'PY'
import re
html=open("static/index.html",encoding="utf-8").read()
open("_syntax_check.js","w",encoding="utf-8").write(max(re.findall(r"<script>(.*?)</script>",html,re.S),key=len))
PY
wsl.exe -e bash -lc "cd \"$(wslpath -a "$(git rev-parse --show-toplevel)")\" && node --check _syntax_check.js && echo JS_OK"
rm -f _syntax_check.js
```
Expected: `JS_OK`.

- [ ] **Step 7: Verificação manual + Commit**

Logar como super_admin → **Painel Orizon** aparece na sidebar → abre → abas Redes/Lojas/Gestores funcionam (criar rede, criar loja, criar gestor). Logar como master → `nav-orizon` **não** aparece.
```bash
git add static/index.html
git commit -m "feat(orizon-ui): Painel Orizon (redes/lojas/gestores) — extrai a administração de sistema do Admin

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Frontend — Painel Admin vira plano de 4 abas + renomeações

**Files:**
- Modify: `static/index.html` (`adminCarregarConsole` ~8896, `adminRender` ~8941, `adminRenderLoja` ~9102, legendas)

- [ ] **Step 1: `adminCarregarConsole` sempre renderiza o painel plano**

Substituir o corpo que decide nível por papel (linhas ~8896-8904) por:
```javascript
function adminCarregarConsole(){
  const u = _usuarioAtual || {};
  // Admin é SEMPRE o painel plano de 4 abas, escopado pela empresa selecionada (seletor no topo).
  _adminNav = { loja: null };   // drill-down aposentado (plataforma/rede foram p/ o Painel Orizon)
  adminRender();
}
```

- [ ] **Step 2: `adminRender` chama só o painel de loja (plano)**

Substituir `adminRender` (linhas ~8941-8947) por:
```javascript
function adminRender(){
  const box = document.getElementById('admin-console');
  adminRenderLoja(box);         // painel plano; a empresa vem do seletor (Task 5)
}
```
Remover/neutralizar `adminRenderPlataforma`, `adminRenderRede`, `adminRenderProjeto`, `adminEntrarRede`, `adminEntrarLoja`, `adminEntrarProjeto`, `adminIrNivel`, `adminBreadcrumb` **do fluxo do Admin** (o conteúdo útil de plataforma/rede já foi para `orizon*` na Task 3). Se alguma dessas ainda for referenciada, deixar um stub inócuo ou remover a referência.

- [ ] **Step 3: Renomear as legendas das abas**

Em `adminRenderLoja` (linhas ~9106-9109):
- `>Dados da loja<` → `>Dados da empresa<`
- `>Usuários da loja<` → `>Usuários<`
(mantendo os `id` `loja-tab-dados`/`loja-tab-usuarios` — só o texto muda.)

- [ ] **Step 4: `lid` do painel vem da empresa ativa**

Em `adminRenderLoja` a linha `const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);` passa a considerar a loja ativa (o seletor da Task 5 arma `_lojaAtiva`):
```javascript
  const lid = _lojaAtiva || (_usuarioAtual && _usuarioAtual.loja_id);
```
(A Task 5 introduz o helper `_empresaAtivaId()` e refatora esta linha para usá-lo — mesma semântica.)

- [ ] **Step 5: `node --check`** (mesmo bloco da Task 3 Step 6). Expected: `JS_OK`.

- [ ] **Step 6: Verificação manual + Commit**

Master → Admin abre direto nas 4 abas (Dados da empresa, Usuários, Perfis de Usuário, Módulos) e funciona na própria loja. super_admin → Admin abre no painel plano (empresa ativa; sem seletor ainda pode cair na 1ª empresa — a Task 5 fecha isso).
```bash
git add static/index.html
git commit -m "feat(admin-ui): Painel Admin vira plano de 4 abas (Dados da empresa/Usuários/Perfis/Módulos)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Frontend — Seletor de empresa compartilhado (topo de Admin e Config)

**Files:**
- Modify: `static/index.html` (barra do seletor no topo de `page-07`/console Admin e `page-09` Config; estado `_empresaAtiva`; carga via `/api/admin/empresas`)

- [ ] **Step 1: Estado + carga das empresas**

Adicionar (perto de `_lojaAtiva`, ~2351):
```javascript
let _empresas = null;              // cache [{loja_id,nome,rede_id,rede_nome}]
function _empresaAtivaId(){ return _lojaAtiva || (_usuarioAtual && _usuarioAtual.loja_id) || null; }
async function empresasCarregar(){
  if (_empresas) return _empresas;
  try { const r = await fetch('/api/admin/empresas', {credentials:'same-origin'});
        const d = await r.json(); _empresas = d.ok ? d.empresas : []; }
  catch(e){ _empresas = []; }
  return _empresas;
}
function empresaTrocar(id){
  _lojaAtiva = id ? parseInt(id,10) : null;
  if (_lojaAtiva) localStorage.setItem('loja_ativa', String(_lojaAtiva));
  // re-renderiza a tela ativa (Admin ou Config) com a nova empresa
  if (document.getElementById('page-07')?.classList.contains('ativa')) adminRender();
  if (document.getElementById('page-09')?.classList.contains('ativa') && typeof cfgReload==='function') cfgReload();
}
```
_(Ajustar `cfgReload` ao nome real da rotina que recarrega o Config; se não houver, chamar `cfgTab(_cfgAtual)` da aba corrente.)_

- [ ] **Step 2: Render do seletor (componente reutilizável)**

```javascript
async function empresaSeletorHTML(){
  const emps = await empresasCarregar();
  const cur = _empresaAtivaId();
  if (emps.length <= 1){
    const nome = emps[0]?.nome || (_usuarioAtual && _usuarioAtual.rotulo) || 'Minha empresa';
    return `<div class="emp-seletor"><span class="emp-lbl">Empresa:</span> <strong>${esc(nome)}</strong></div>`;
  }
  // agrupa por rede (grupo)
  const grupos = {};
  emps.forEach(e => { (grupos[e.rede_nome||'Sem grupo'] ||= []).push(e); });
  const opts = Object.keys(grupos).sort().map(g =>
    `<optgroup label="${esc(g)}">`+grupos[g].map(e =>
      `<option value="${e.loja_id}" ${e.loja_id==cur?'selected':''}>${esc(e.nome)}</option>`).join('')+`</optgroup>`).join('');
  return `<div class="emp-seletor"><span class="emp-lbl">Empresa:</span>
    <select onchange="empresaTrocar(this.value)"><option value="">— escolher —</option>${opts}</select></div>`;
}
```

- [ ] **Step 3: Injetar o seletor no topo de Admin e Config**

- Admin: em `adminRenderLoja`, antes da barra de abas, inserir um contêiner `#admin-emp-seletor` e preenchê-lo: `empresaSeletorHTML().then(h => { const el=document.getElementById('admin-emp-seletor'); if(el) el.innerHTML=h; })`.
- Config: no `page-09`, logo abaixo do `page-sub`, inserir `<div id="cfg-emp-seletor"></div>` e, na rotina que abre o Config (a que roda em `goPage(9)`/`n===9`), preenchê-lo com `empresaSeletorHTML()`.
- CSS mínimo (reusar tokens; sem cor literal) para `.emp-seletor`/`.emp-lbl` (alinhamento + espaçamento).

- [ ] **Step 4: `node --check`** (bloco da Task 3 Step 6). Expected: `JS_OK`.

- [ ] **Step 5: Verificação manual + Commit**

super_admin → Admin e Config mostram o **seletor** com todas as empresas agrupadas por rede; trocar a empresa recarrega a tela no escopo dela (criar usuário/perfil, editar dados, ver provisões da empresa escolhida). master (1 loja) → seletor aparece como rótulo fixo. Confirmar que o `X-Loja-Ativa` acompanha (Perfis/Usuários da empresa certa).
```bash
git add static/index.html
git commit -m "feat(admin-ui): seletor de empresa (empresa/grupo) no topo de Admin e Config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

# FASE 2 — Travas (abas trancadas + step-up, iguais para todos os perfis)

## Task 6: Frontend — Admin/Config sempre visíveis; abas trancadas com cadeado + step-up

**Files:**
- Modify: `static/index.html` (nav Admin/Config sempre visível ~2564-2567; cadeado nas abas de `adminRenderLoja`/`cfgTab`; clique → step-up)

- [ ] **Step 1: Admin/Config sempre na sidebar**

Nas linhas ~2564-2567, remover o esconde-por-`acessa_admin`/`acessa_config` (as telas passam a aparecer para todo usuário autenticado; a fronteira vira a trava por aba). Manter `nav-orizon` gateado por `pode_gerir_redes`.
```javascript
    const _navAdmin = document.getElementById('nav-07'); if (_navAdmin) _navAdmin.style.display = '';
    const _navCfg   = document.getElementById('nav-cfg'); if (_navCfg)   _navCfg.style.display = '';
```

- [ ] **Step 2: Mapa aba → capacidade**

Adicionar:
```javascript
const _ABA_CAP = {
  // Admin
  'loja-tab-dados': 'pode_editar_dados_loja', 'loja-tab-usuarios': 'pode_gerir_usuarios',
  'loja-tab-perfis': 'pode_gerir_perfis',     'loja-tab-modulos': 'pode_editar_dados_loja',
  // Config
  'cfg-tab-provisoes':'pode_ver_parametros','cfg-tab-comissao':'pode_ver_parametros',
  'cfg-tab-cronograma':'pode_ver_parametros','cfg-tab-funcoes':'pode_gerir_usuarios',
  'cfg-tab-documentos':'pode_gerir_documentos',
};
function _abaLiberada(tabId){
  const cap = _ABA_CAP[tabId]; if(!cap) return true;
  return !!(_usuarioAtual && _usuarioAtual[cap]);   // super_admin: todas true (god-mode)
}
```

- [ ] **Step 3: Renderizar cadeado + interceptar o clique**

Após montar as abas de Admin (`adminRenderLoja`) e Config (`page-09`), aplicar:
```javascript
function _aplicarCadeados(prefixIds){
  prefixIds.forEach(id => {
    const tab = document.getElementById(id); if(!tab) return;
    if (_abaLiberada(id)) { tab.classList.remove('trancada'); return; }
    tab.classList.add('trancada');
    if (!tab.querySelector('.lock')) tab.insertAdjacentHTML('beforeend', ' <i class="ti ti-lock lock"></i>');
  });
}
```
E no handler de clique de aba (`adminLojaTab`/`cfgTab`), no topo:
```javascript
  if (!_abaLiberada('loja-tab-'+qual)) {   // (cfg-tab-<qual> no cfgTab)
    abrirModalStepUp({ recurso: _ABA_CAP['loja-tab-'+qual], motivo: 'Abrir esta aba' })
      .then(ok => { if (ok) { /* reabre a aba já liberada */ } });
    return;
  }
```
_(Reusar `abrirModalStepUp` da Sessão 62. O contrato exato do step-up — payload e retorno — deve ser confirmado no arquivo; casar com o fluxo já existente para módulos bloqueados.)_

- [ ] **Step 4: CSS `.home-tab.trancada`** — aparência de trancada (opacidade/ícone), theme-aware, tokens (sem cor literal).

- [ ] **Step 5: `node --check`** (bloco da Task 3 Step 6). Expected: `JS_OK`.

- [ ] **Step 6: Verificação manual + Commit**

operador → Admin e Config aparecem na sidebar; abas sem permissão vêm com **cadeado**; clicar pede step-up (senha de quem tem) e libera. master → abas de Admin liberadas, Config conforme caps. super_admin → nenhuma trava.
```bash
git add static/index.html
git commit -m "feat(ui): abas de Admin/Config uniformes p/ todo perfil — cadeado + step-up (Sessão 62)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Verificação final + DEV_LOG

**Files:**
- Modify: `DEV_LOG.md`

- [ ] **Step 1: Suíte completa verde**

Run: `python3 -m pytest -q`
Expected: verde (com os novos `test_admin_empresas.py` e `test_auth_me_caps.py`).

- [ ] **Step 2: Verificação manual por perfil (navegador)**

Checklist (Ctrl+F5): (a) **super_admin** — Painel Orizon (cria rede/loja/gestor); Admin plano com seletor de todas as empresas; Config idem; sem cadeados. (b) **master** — sem Painel Orizon; Admin/Config na própria loja (seletor fixo); Perfis/Usuários/Módulos ok. (c) **operador** — Admin/Config visíveis com abas trancadas; step-up libera. (d) **admin_rede** — sem Painel Orizon; seletor lista só as lojas da sua rede.

- [ ] **Step 3: Atualizar DEV_LOG**

Nova `## Sessão N` no topo das sessões (acima da última), resumindo as duas fases, as decisões (super_admin técnico × gestor de rede negócios = dashboard futuro; admin_rede sem criar loja; seletor reaproveita X-Loja-Ativa do god-mode; travas por step-up) e a nova contagem da suíte. Atualizar `## ⏸️ ESTADO ATUAL`.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — navegação consistente (Painel Orizon + Admin plano + seletor + travas)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notas / decisões

- **super_admin técnico × gestor de rede (negócios):** Painel Orizon é do super_admin (cap. `gerir_redes`, exclusiva). O `admin_rede` **não** vê o Orizon; sua tela plena (dashboard consolidado) é **frente futura**.
- **admin_rede interino:** usa Admin/Config padrão com o seletor limitado à sua rede; **não** cria lojas/redes (função técnica do super_admin). Se for regressão indesejada, o usuário decide dar um "criar loja na minha rede" escopado — fora do default.
- **Escopo por empresa reusa o god-mode (Sessão 80):** o seletor só arma `X-Loja-Ativa`; nenhum backend novo de escopo.
- **Omie:** o card de chaves **não** é recriado no Painel Orizon; a remoção total do Omie é a Frente 2, com plano próprio.
- **Sem teste JS (convenção do projeto):** o frontend é verificado por `node --check` (sintaxe) + navegador. O peso de correção fica nos testes de backend (endpoint + caps) e na checklist manual por perfil.
