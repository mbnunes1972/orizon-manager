# Passo 1 — Corrigir escopo do Admin (Núcleo) + telas Fiscal/Financeiro no Hub

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Corrigir a divergência de escopo do **módulo Admin (Núcleo/Plataforma)**: o Admin da **loja** deve ter
só **Dados · Usuários · Módulos** — **Projetos, Fiscal e Provisões (ex-"Financeiro") saem** (são domínios, não
sub-telas administrativas). Para não deixar a config órfã (decisão do usuário), os **cards Fiscal e Financeiro do
Hub deixam de ser "em breve"** e passam a abrir exatamente esses painéis de config (reaproveitados). **Credenciais
e Tokens** permanece na **Plataforma** (super_admin, global) — não vira aba de loja.

**Ref (precedência):** `ARQUITETURA-MODULOS.md` (Núcleo = Auth/Tenancy/Auditoria/Ciclo/Integrações; Admin
administra conta/loja, **não** domínios) · `docs/design/navegacao-orizon-v1.md` (3 níveis; Admin por último) ·
`docs/design/padrao-design-orizon-v2.md`. *(Nota: `Modulos_Orizon.docx` não está no repo — quando entrar, revalidar.)*

**Architecture:** Frontend puro (`static/index.html`). Os endpoints de config **já existem** e são gateados por
`pode_editar_dados_loja` (`/api/admin/lojas/<id>/perfil-fiscal`, `/api/admin/lojas/<id>/config-financeira`) — quem
não tem a capability recebe 403 e o painel mostra "Sem acesso" (é a **permissão-dentro-do-módulo** que o usuário
pediu, não aba no Admin). As funções `adminFiscalCarregar`/`adminFinanceiroCarregar` já usam
`_adminNav.loja?.id || _usuarioAtual.loja_id` — no Hub, usam a **loja do próprio usuário**.

**Tech Stack:** `static/index.html` (HTML+CSS+JS inline — **sem teste JS**; `node --check`/balanço + navegador).
Branch: `feat/escopo-admin`. **Baseline 681 passed.** Backend **intocado** (suíte deve seguir 681).

**Ler antes (âncoras reais):**
- `adminRenderLoja` L7066–7096: monta as 6 abas + 6 painéis (`loja-panel-*`) e chama `adminLojaCarregarDados`/
  `adminUsuariosCarregar`. `adminLojaTab` L7098–7109 roteia (`financeiro`→`adminFinanceiroCarregar`,
  `fiscal`→`adminFiscalCarregar`, `projetos`→`adminLojaProjetosCarregar`, `modulos`→`adminModulosCarregar`).
- `adminFiscalCarregar` (~L7150) injeta em `#loja-panel-fiscal`; `adminFinanceiroCarregar` (~L7116) em
  `#loja-panel-financeiro`; ambos usam `lid = _adminNav.loja?.id || _usuarioAtual.loja_id` e tratam 403 ("Sem acesso").
- `goPage(n)` L2288 (padrão `page-0N`/`nav-0N`; `n>=10` → `page-N`; lazy-loads `if(n===...)`).
- `_HUB_DESTINO` L2353–2355 (`comercial`→goPage(0), `cadastro`→goPage(10)); `hubRender` marca "Em breve" quando o
  módulo não tem destino.
- `_adminNav` L6859: `let _adminNav = { nivel:1, rede:null, loja:null, projeto:null }` (objeto global).
- `page-08` (Hub) L717; `page-10` (Cadastro).

---

## Task 1: Admin da loja reduzido + telas Fiscal/Financeiro no Hub

**Files:** Modify `static/index.html`.

- [ ] **Step 1: `adminRenderLoja` — só Dados/Usuários/Módulos.** Substituir o corpo de `adminRenderLoja` (L7066–7096)
removendo as abas/painéis de **Projetos, Provisões(financeiro) e Fiscal** e a lógica `abaAtiva`/`modsLoja` (que só
servia para gatear essas abas):
```javascript
async function adminRenderLoja(box){
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  box.innerHTML = `
    <div style="display:flex;gap:0;border-bottom:2px solid var(--dalm-gold);margin-bottom:12px">
      <button class="home-tab ativo" id="loja-tab-dados" onclick="adminLojaTab('dados')">Dados da loja</button>
      <button class="home-tab" id="loja-tab-usuarios" onclick="adminLojaTab('usuarios')">Usuários da loja</button>
      <button class="home-tab" id="loja-tab-modulos" onclick="adminLojaTab('modulos')">Módulos</button>
    </div>
    <div id="loja-panel-dados"></div>
    <div id="loja-panel-usuarios" style="display:none">
      <button class="btn btn-ghost btn-sm" onclick="abrirModalUsuario({modo:'novo', escopo:'loja', loja_id:(_adminNav.loja&&_adminNav.loja.id)||(_usuarioAtual&&_usuarioAtual.loja_id), onSaved:adminUsuariosCarregar})" style="font-size:11px">+ Novo usuário</button>
      <div id="admin-usuarios-lista" style="margin-top:10px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
    </div>
    <div id="loja-panel-modulos" style="display:none"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>`;
  adminLojaCarregarDados(lid);
  adminUsuariosCarregar();
}
```

- [ ] **Step 2: `adminLojaTab` — só 3 abas.** Reduzir o array e o roteamento (remove projetos/financeiro/fiscal):
```javascript
function adminLojaTab(qual){
  ['dados','usuarios','modulos'].forEach(q => {
    const tab   = document.getElementById('loja-tab-'+q);
    const panel = document.getElementById('loja-panel-'+q);
    if (tab)   tab.classList.toggle('ativo', q===qual);
    if (panel) panel.style.display = q===qual ? '' : 'none';
  });
  if (qual==='modulos') adminModulosCarregar();
}
```
> `adminLojaProjetosCarregar`, `adminFinanceiroCarregar`, `adminFiscalCarregar` **continuam existindo** — as duas
> últimas serão chamadas pelo Hub (Steps 3–4). `adminLojaProjetosCarregar` fica órfã (dead code aceitável).

- [ ] **Step 3: Novas páginas do Hub — Fiscal e Financeiro (config).** Adicionar junto das outras `.page` (ex.:
após `page-10`), com os contêineres que as funções de config já usam (`#loja-panel-fiscal`/`#loja-panel-financeiro`):
```html
  <!-- PAGE 11: Fiscal (config do módulo — Emitente/NF-e) -->
  <div class="page" id="page-11">
    <div class="page-title">Fiscal</div>
    <div class="page-sub">Configuração fiscal da sua loja (Emitente, tokens, NF-e/NFS-e).</div>
    <div id="loja-panel-fiscal" style="margin-top:12px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
  </div>
  <!-- PAGE 12: Financeiro (config — Provisões/custos-padrão) -->
  <div class="page" id="page-12">
    <div class="page-title">Financeiro</div>
    <div class="page-sub">Provisões e custos-padrão da sua loja (alimentam o orçamento).</div>
    <div id="loja-panel-financeiro" style="margin-top:12px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
  </div>
```
> Os IDs `loja-panel-fiscal`/`loja-panel-financeiro` **saíram** do `adminRenderLoja` (Step 1) e agora vivem **só**
> aqui — sem ID duplicado. As funções `adminFiscalCarregar`/`adminFinanceiroCarregar` injetam nesses contêineres.

- [ ] **Step 4: `goPage` + `_HUB_DESTINO` — abrir as telas com a loja do usuário.**
Em `goPage(n)` adicionar (antes de chamar, zerar `_adminNav.loja` para usar a loja do próprio usuário):
```javascript
  if(n===11){ if(_adminNav) _adminNav.loja = null; adminFiscalCarregar(); }
  if(n===12){ if(_adminNav) _adminNav.loja = null; adminFinanceiroCarregar(); }
```
Em `_HUB_DESTINO` acrescentar:
```javascript
  fiscal:     () => goPage(11),
  financeiro: () => goPage(12),
```
Assim os cards **Fiscal** e **Financeiro** do Hub deixam de ser "Em breve" (o `hubRender` já mostra "Abrir →"
quando há destino).

- [ ] **Step 5: Verificação.** `node --check` do `<script>` (via WSL, se houver) ou balanço net 0 do diff.
`python3 -m pytest -q` → **681** (backend intocado). **Roteiro manual:**
  1. **Admin → (loja) →** abas: só **Dados · Usuários · Módulos** (Projetos/Provisões/Fiscal sumiram).
  2. **Hub → card Fiscal** → abre a **config fiscal** da sua loja (Emitente/tokens); quem não tem capability vê
     "Sem acesso" (permissão-dentro-do-módulo).
  3. **Hub → card Financeiro** → abre **Provisões** (custos-padrão) da sua loja.
  4. **Credenciais e Tokens** segue em **Admin → Plataforma** (super_admin), inalterado.
**Commit:**
```bash
git add static/index.html
git commit -m "fix(admin): escopo Nucleo — Admin da loja = Dados/Usuarios/Modulos; Fiscal/Financeiro viram tela no Hub"
```

---

## Task 2: Docs — escopo do Admin + confirmação por escrito

**Files:** Modify `docs/ARQUITETURA-MODULOS.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Em `ARQUITETURA-MODULOS.md` (nota "🖥️ Hub…"/"UI da topologia"), registrar:
  - **Admin (Núcleo) tem escopo de conta/loja:** abas **Dados · Usuários · Módulos**; **Credenciais e Tokens** na
    Plataforma (super_admin, global). **Projetos, Fiscal e Provisões saíram do Admin** — são domínios com tela própria.
  - **Fiscal e Financeiro ganharam tela no Hub** (config: Emitente/NF-e e provisões/custos-padrão da loja),
    gateadas por `pode_editar_dados_loja` **dentro do módulo** (não como aba do Admin) — evita o erro de fronteira
    (módulo absorvendo escopo alheio, como o risco já mapeado da Expedição). Visão administrativa de rede é
    **permissão elevada dentro do módulo**, tarefa futura.
- [ ] **Step 2:** `DEV_LOG.md` — nota do passo 1 (escopo do Admin corrigido; Fiscal/Financeiro no Hub). **Step 3:**
commit.
```bash
git add docs/ARQUITETURA-MODULOS.md DEV_LOG.md
git commit -m "docs(arq): Admin=Nucleo (Dados/Usuarios/Modulos); Fiscal/Financeiro com tela propria no Hub"
```

---

## Self-review do plano
- **Cobertura do pedido (passo 1):** Admin da loja reduzido a Dados/Usuários/Módulos (T1 Step 1–2) · Projetos/Fiscal/
  Provisões removidos (T1) · config Fiscal/Provisões **não fica órfã** → cards Fiscal/Financeiro do Hub abrem os
  painéis (T1 Step 3–4) · Credenciais na Plataforma, intocado (decisão 2) · confirmação por escrito referenciando o
  doc (T2 + relatório final).
- **Sem placeholders:** corpo completo de `adminRenderLoja`/`adminLojaTab`, HTML das páginas 11/12, `goPage` e
  `_HUB_DESTINO`. As funções de config são reaproveitadas sem alteração (targetam os IDs movidos).
- **Consistência:** `loja-panel-fiscal`/`loja-panel-financeiro` movem do Admin (removidos) para page-11/page-12
  (sem ID duplicado); `adminFiscalCarregar`/`adminFinanceiroCarregar` inalteradas; `_HUB_DESTINO.fiscal/financeiro`
  → goPage(11/12) → zera `_adminNav.loja` → usa `_usuarioAtual.loja_id`.
- **Risco:** frontend sem teste JS → `node --check` + roteiro manual; ID duplicado é o principal risco (mitigado:
  os panels saem do Admin no mesmo commit em que entram nas pages). Backend intocado (681).
- **Fora de escopo (proposital):** migração visual (doc 3 §5) = passo 2; templates de diagramação = passo 3;
  visão administrativa de rede dos módulos = futuro (permissão dentro do módulo).
