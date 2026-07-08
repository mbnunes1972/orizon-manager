# Hub de Módulos (aterrissagem) + Credenciais no Admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans. Passos usam checkbox (`- [ ]`).

**Goal:** A aterrissagem pós-login do usuário operacional passa a ser um **hub de módulos** (cards de domínio
**agrupados por faixa de titularidade do ciclo**), em vez da lista de Projetos direta; e **Credenciais** sai do
menu lateral para dentro do **Admin** ("Credenciais e Tokens"), **de fato invisível** para quem não é
Administrador do Sistema (super_admin). Camada de apresentação sobre o que a Fase 1 já expõe — reativo ao
`modulos_ativos` da loja (via `/api/auth/me`).

**Architecture:** `modulos.py` ganha `faixa` por domínio + `FAIXAS` (ordem/rótulos) + `hub_layout(ativos)`.
`/api/auth/me` passa a incluir `usuario["hub"]` (layout agrupado já filtrado pela topologia da loja) — **sem novo
endpoint**. O frontend renderiza o hub a partir de `_usuarioAtual.hub` + um mapa `id→destino` (goPage); domínios
sem tela viram cards **"em breve"**. Credenciais vira uma seção no `adminRenderPlataforma`, gated por super_admin.

**Tech Stack:** Python (`http.server`, SQLAlchemy) + pytest (backend testável); `static/index.html`
(HTML+CSS+JS inline — **sem teste JS**; verificação por `node --check`/balanço + navegador).

**Decisões (fechadas com o usuário):**
- **Credenciais e Tokens:** visível **só para super_admin** (Administrador do Sistema). Diretor **deixa** de ver.
- **Hub:** mostra **todos os domínios ativos** da loja; os sem tela dedicada → **"em breve"** (desabilitado).
- **Agrupamento = faixa de titularidade do ciclo** (Governança / `mod_ciclo.FAIXA_POR_ETAPA`):

| Grupo (faixa) | Domínios | Destino (tela) |
|---|---|---|
| **Vendas** | `cadastro`, `comercial` | Cadastro→Clientes (`goPage(5)`) · Comercial→Projetos (`goPage(0)`) |
| **Execução do Projeto** | `producao` | — (em breve) |
| **Logística / Expedição** | `fiscal`, `estoque`, `expedicao` | — (em breve; Fiscal vive no ciclo/admin) |
| **Pós-venda / Montagem** | `posvenda` | — (em breve) |
| **Financeiro** (transversal) | `financeiro` | — (em breve; Financeiro vive no orçamento) |

**Ler antes:** `modulos.py` (`MODULOS`, `DOMINIOS`, `DOMINIOS_ORDEM`, `dominios_com_rotulo`); `mod_ciclo.py`
(`FAIXA_POR_ETAPA` — nomes de faixa: vendas/execucao_projeto/expedicao/montagem); `auth_routes.py` `/api/auth/me`
(já injeta `usuario["modulos_ativos"]`); `static/index.html` — sidebar creds `#sb-creds-block` (L388–405), nav
(L408–414), `goPage` (L2288), `_aterrissarPorPapel` (L2062), gating antigo de creds (L2171–2177),
`adminRenderPlataforma` (~L6832+). **Baseline 676 passed.** Teste: `python3 -m pytest -q` (fallback
`C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da
mudança. Branch: `feat/hub-modulos`.

**Regra de ouro:** default tudo-ligado intocado — loja sem config vê todos os domínios no hub; `hub` ausente/vazio
no `/me` → o frontend cai no comportamento antigo (Projetos), nunca tela em branco.

---

## Task 1: `modulos.py` — faixas + `hub_layout`

**Files:** Modify `modulos.py`; Test: `tests/test_modulos.py` (adicionar).

- [ ] **Step 1: Teste primeiro** — adicionar a `tests/test_modulos.py`:
```python
def test_faixa_por_dominio():
    # cada domínio tem faixa; Fiscal fica na Logística/Expedição (não em Vendas)
    assert m.MODULOS["fiscal"]["faixa"] == "expedicao"
    assert m.MODULOS["comercial"]["faixa"] == "vendas"
    assert m.MODULOS["financeiro"]["faixa"] == "financeiro"
    for d in m.DOMINIOS:
        assert m.MODULOS[d].get("faixa"), f"{d} sem faixa"


def test_hub_layout_agrupa_por_faixa():
    g = m.hub_layout(list(m.DOMINIOS))
    faixas = [x["faixa"] for x in g]
    assert faixas == ["vendas", "execucao_projeto", "expedicao", "montagem", "financeiro"]
    vendas = next(x for x in g if x["faixa"] == "vendas")
    ids = [mm["id"] for mm in vendas["modulos"]]
    assert ids == ["cadastro", "comercial"] and vendas["rotulo"] == "Vendas"


def test_hub_layout_so_ativos_e_sem_faixa_vazia():
    g = m.hub_layout(["cadastro", "comercial"])   # só Vendas ativa
    assert [x["faixa"] for x in g] == ["vendas"]
    assert m.hub_layout([]) == []
```

- [ ] **Step 2: Rodar → falha** (`KeyError: 'faixa'` / `AttributeError: hub_layout`).

- [ ] **Step 3: `modulos.py`.** (a) Adicionar `"faixa"` a cada domínio no `MODULOS`:
`cadastro`→`"vendas"`, `comercial`→`"vendas"`, `producao`→`"execucao_projeto"`, `fiscal`→`"expedicao"`,
`estoque`→`"expedicao"`, `expedicao`→`"expedicao"`, `posvenda`→`"montagem"`, `financeiro`→`"financeiro"`.
(b) Ao fim do arquivo:
```python
# Faixas de titularidade para o hub de módulos (ordem de exibição). As 4 primeiras espelham
# mod_ciclo.FAIXA_POR_ETAPA (Governança do Ciclo); "financeiro" é transversal (dono dos gates 8/11d).
FAIXAS = [
    ("vendas",           "Vendas"),
    ("execucao_projeto", "Execução do Projeto"),
    ("expedicao",        "Logística / Expedição"),
    ("montagem",         "Pós-venda / Montagem"),
    ("financeiro",       "Financeiro"),
]


def hub_layout(ativos):
    """Layout do hub: domínios ATIVOS agrupados por faixa, na ordem de FAIXAS/DOMINIOS_ORDEM.
    Só inclui faixas com ≥1 domínio ativo. [{'faixa','rotulo','modulos':[{'id','rotulo'}]}]."""
    ativos = set(ativos)
    grupos = []
    for fid, frot in FAIXAS:
        mods = [{"id": d, "rotulo": MODULOS[d]["rotulo"]}
                for d in DOMINIOS_ORDEM
                if d in ativos and MODULOS[d].get("faixa") == fid]
        if mods:
            grupos.append({"faixa": fid, "rotulo": frot, "modulos": mods})
    return grupos
```

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_modulos.py tests/test_arquitetura_modulos.py -q` → verde
(fronteira segue verde — só dados/funções puras). Suíte inteira → verde. **Commit:**
```bash
git add modulos.py tests/test_modulos.py
git commit -m "feat(arq): faixa por dominio + hub_layout (agrupamento por titularidade)"
```

---

## Task 2: `/api/auth/me` inclui `usuario["hub"]`

**Files:** Modify `auth_routes.py`; Test: `tests/test_auth_me_modulos.py` (adicionar).

- [ ] **Step 1: Teste primeiro** — adicionar a `tests/test_auth_me_modulos.py`:
```python
def test_me_traz_hub_agrupado(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/auth/me")
    assert st == 200
    hub = d["usuario"]["hub"]
    faixas = [g["faixa"] for g in hub]
    assert "vendas" in faixas                       # loja default -> tudo ativo -> todas as faixas
    vendas = next(g for g in hub if g["faixa"] == "vendas")
    assert any(mm["id"] == "comercial" for mm in vendas["modulos"])
```

- [ ] **Step 2: Rodar → falha** (`me` não tem `hub`).

- [ ] **Step 3: `auth_routes.py`** — no `/api/auth/me`, LOGO APÓS a linha que já monta
`usuario["modulos_ativos"] = sorted(...)` (frente anterior), acrescentar:
```python
    usuario["hub"] = _mod.hub_layout(usuario["modulos_ativos"])
```
(`_mod` já é o `import modulos as _mod` do bloco de `modulos_ativos`; se o import tiver outro alias, use o real.)

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_auth_me_modulos.py -q` → verde; suíte inteira → verde.
**Commit:**
```bash
git add auth_routes.py tests/test_auth_me_modulos.py
git commit -m "feat(hub): /api/auth/me inclui hub (modulos por faixa)"
```

---

## Task 3: Frontend — página Hub + aterrissagem + item de menu

**Files:** Modify `static/index.html`. **Sem teste JS** — `node --check`/balanço + navegador.

- [ ] **Step 1: HTML — página do hub + item de menu.**
(a) Adicionar um item de menu no topo da `<nav class="sb-nav">` (L408–414), ANTES de Projetos:
```html
    <div class="nav-item" id="nav-08" onclick="goPage(8)">&#x1F3E0; Módulos</div>
```
(b) Adicionar a página do hub junto das outras `.page` (ex.: depois de `page-00`):
```html
  <div class="page" id="page-08">
    <div class="page-title">Módulos</div>
    <div class="page-sub" id="hub-sub">Selecione um módulo para começar.</div>
    <div id="hub-grupos"></div>
  </div>
```
(c) CSS do card do hub (junto do bloco `<style>`, perto de `.card`):
```css
.hub-faixa{margin-bottom:22px}
.hub-faixa-title{font-family:'Epilogue',sans-serif;font-weight:700;font-size:11px;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin-bottom:10px}
.hub-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}
.hub-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px 18px;cursor:pointer;transition:.15s;display:flex;flex-direction:column;gap:6px}
.hub-card:hover{border-color:var(--accent)}
.hub-card.soon{opacity:.5;cursor:default}
.hub-card.soon:hover{border-color:var(--border)}
.hub-card-nome{font-family:'Epilogue',sans-serif;font-weight:700;font-size:14px;color:var(--text)}
.hub-card-tag{font-size:9px;letter-spacing:.5px;color:var(--muted);text-transform:uppercase}
```

- [ ] **Step 2: JS — render do hub** (perto das funções de página, ex.: após `goPage`). O destino de cada módulo
é frontend; só `cadastro`/`comercial` têm tela hoje:
```javascript
// módulo -> ação de navegação (só os que têm tela real); ausentes = "em breve"
const _HUB_DESTINO = {
  comercial: () => goPage(0),   // Projetos
  cadastro:  () => goPage(5),   // Clientes
};

function hubRender(){
  const box = document.getElementById('hub-grupos');
  if(!box) return;
  const grupos = (_usuarioAtual && _usuarioAtual.hub) || null;
  if(!grupos){ box.innerHTML = ''; return; }   // sem info -> não renderiza (compat)
  box.innerHTML = grupos.map(g => `
    <div class="hub-faixa">
      <div class="hub-faixa-title">${esc(g.rotulo)}</div>
      <div class="hub-cards">
        ${g.modulos.map(m => {
          const tem = !!_HUB_DESTINO[m.id];
          return `<div class="hub-card${tem?'':' soon'}" ${tem?`onclick="_hubIr('${esc(m.id)}')"`:''}>
            <span class="hub-card-nome">${esc(m.rotulo)}</span>
            <span class="hub-card-tag">${tem?'Abrir →':'Em breve'}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`).join('');
}

function _hubIr(id){ const f = _HUB_DESTINO[id]; if(f) f(); }
```

- [ ] **Step 3: Rotear no `goPage`** — em `goPage(n)` (L2288), adicionar o lazy-load:
```javascript
  if(n===8) hubRender();
```
(`goPage(8)` já resolve `nav-08`/`page-08` pelo padrão `'nav-0'+n`/`'page-0'+n`.)

- [ ] **Step 4: Aterrissagem** — em `_aterrissarPorPapel` (L2062), o usuário **operacional** (não super_admin,
não admin_rede) passa a cair no hub. No fim da função, adicionar:
```javascript
  const ehAdmin = u.pode_gerir_redes || u.nivel === 'admin_rede';
  if(!ehAdmin) goPage(8);   // operacional aterrissa no Hub de Módulos
```
(super_admin/admin_rede continuam com `goPage(7)` como já está.) O `page-00`/`nav-00` nascem com `active` no HTML,
mas `goPage(8)` troca a página ativa corretamente. **Não** remova Projetos/Clientes/Parceiros do menu — o hub é a
aterrissagem; a sidebar segue para acesso rápido (e reativa ao módulo, como a frente anterior já faz).

- [ ] **Step 5: Verificação** — `node --check` do `<script>` (ou balanço das linhas do diff, net 0);
`python3 -m pytest -q` verde (backend intocado). **Roteiro manual:** login como `dir_l1` (operacional) → cai no
**Hub** com grupos Vendas/Execução/Logística/Pós-venda/Financeiro; card **Comercial**→Projetos, **Cadastro**→
Clientes; os demais "Em breve" (não clicáveis). Desligar Fiscal na loja (aba Módulos) → some do grupo Logística.
**Commit:**
```bash
git add static/index.html
git commit -m "feat(hub): pagina Hub de Modulos (cards por faixa) como aterrissagem operacional"
```

---

## Task 4: Frontend — Credenciais e Tokens dentro do Admin (super_admin)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Remover o bloco de credenciais da sidebar.** Apagar o `<!-- Credenciais -->` +
`<div class="sb-creds" id="sb-creds-block">…</div>` (L388–405). Guardar mentalmente os campos e a função:
inputs `#app_key`, `#app_secret`, `#intervalo`, botão `onclick="saveConfig()"`, hint `#save-hint`.

- [ ] **Step 2: Limpar o gating antigo.** Em `carregarConfig`/onde estava (L2171–2177), remover as referências a
`sb-creds-fields`/`sb-creds-oculto`/`sb-creds-lock` (agora inexistentes) para não dar erro de `null`.

- [ ] **Step 3: Adicionar "Credenciais e Tokens" no Admin Plataforma.** Em `adminRenderPlataforma(box)` (~L6832+),
**somente para super_admin**, injetar a seção (mova os inputs Omie para cá):
```javascript
  // Credenciais e Tokens — Núcleo/Plataforma; só Administrador do Sistema (super_admin) enxerga.
  if (_usuarioAtual && _usuarioAtual.pode_gerir_redes) {
    html += `
      <div class="card" style="margin-top:16px">
        <div class="card-title">Credenciais e Tokens</div>
        <div style="max-width:420px">
          <label class="field-label">Omie — App Key</label>
          <input type="text" id="app_key" placeholder="App Key">
          <label class="field-label" style="margin-top:10px">Omie — App Secret</label>
          <input type="password" id="app_secret" placeholder="App Secret">
          <label class="field-label" style="margin-top:10px">Intervalo (s)</label>
          <input type="number" id="intervalo" min="0.3" max="10" step="0.1" value="0.5">
          <div class="actions"><button class="btn btn-primary btn-sm" onclick="saveConfig()">Salvar credenciais</button></div>
          <div class="sb-save-hint" id="save-hint" style="text-align:left"></div>
        </div>
      </div>`;
  }
```
> **Confirme** como `adminRenderPlataforma` monta o conteúdo (variável `html`/`box.innerHTML`). Se ele monta uma
> string `html` e faz `box.innerHTML = html`, concatene a seção ANTES do `box.innerHTML =`. Se injeta direto,
> adapte para o padrão real. E confirme se `carregarConfig()` (que preenche os inputs) é chamado ao entrar na
> Plataforma — se não, chame-o após render quando super_admin (para carregar os valores salvos nos inputs novos).

- [ ] **Step 4: `_aterrissarPorPapel` não esconde mais nada relativo a creds.** Conferir que nenhuma outra função
tenta ler `#sb-creds-*`. `grep -n "sb-creds" static/index.html` deve retornar **só o CSS** (as regras `.sb-creds`
podem ficar, inertes) — nenhuma referência de JS/HTML a `sb-creds-block/fields/oculto/lock`.

- [ ] **Step 5: Verificação** — `node --check`/balanço; `python3 -m pytest -q` verde. **Roteiro manual:** (1)
usuário comum/Diretor → **não** vê Credenciais em lugar nenhum (nem sidebar, nem Admin); (2) super_admin → Admin
(Plataforma) mostra **"Credenciais e Tokens"** com os campos Omie e salva. **Commit:**
```bash
git add static/index.html
git commit -m "feat(admin): Credenciais e Tokens no Admin (so super_admin); remove do menu lateral"
```

---

## Task 5: Docs — "UI da topologia" do ARQUITETURA-MODULOS + DEV_LOG

**Files:** Modify `docs/ARQUITETURA-MODULOS.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Na seção **"🖥️ UI da topologia"** do `ARQUITETURA-MODULOS.md`, registrar as duas decisões:
  1. **Aterrissagem = hub de módulos** agrupados por **faixa de titularidade** (Vendas / Execução do Projeto /
     Logística-Expedição / Pós-venda-Montagem / Financeiro transversal), consistente com a Governança do Ciclo —
     em vez de abrir direto na lista de Projetos. Reativo ao `modulos_ativos`; domínios sem tela = "em breve".
  2. **Credenciais e Tokens** migrou do menu lateral para dentro do **Admin (Plataforma)**, com visibilidade
     condicionada à capability de **Administrador do Sistema (super_admin)** — **não aparece** (não é só bloqueio)
     para quem não tem. Diretor deixou de ver.
- [ ] **Step 2:** `DEV_LOG.md` — nota da frente (hub + credenciais), contagem da suíte, nota honesta de que só
  Comercial/Cadastro têm destino hoje. **Step 3:** commit.
```bash
git add docs/ARQUITETURA-MODULOS.md DEV_LOG.md
git commit -m "docs(arq): UI da topologia — hub de modulos por faixa + Credenciais no Admin (super_admin)"
```

---

## Self-review do plano
- **Cobertura do pedido:** aterrissagem vira hub (T3) · agrupamento por faixa de titularidade, consistente com a
  Governança (T1 define faixa por domínio = `FAIXA_POR_ETAPA`; Fiscal→Logística; Financeiro transversal) ·
  Credenciais sai do menu e vira "Credenciais e Tokens" no Admin, **invisível** para não-super_admin (T4) ·
  reativo ao `modulos_ativos`/`/api/auth/me` (T2 injeta `hub`; T3 lê `_usuarioAtual.hub`) · docs (T5).
- **Sem placeholders:** código completo do `hub_layout`, do `/me`, do render do hub, do card CSS e da seção de
  credenciais. Os "confirme como adminRenderPlataforma monta" são verificações com o padrão a espelhar, não TODOs.
- **Consistência de nomes:** `MODULOS[d]["faixa"]`/`FAIXAS`/`hub_layout` (T1) → `usuario["hub"]` (T2) →
  `_usuarioAtual.hub`/`_HUB_DESTINO`/`hubRender`/`page-08`/`nav-08` (T3); `pode_gerir_redes` (super_admin) gate em
  T4. Faixas idênticas a `mod_ciclo.FAIXA_POR_ETAPA` (vendas/execucao_projeto/expedicao/montagem) + `financeiro`.
- **Default tudo-ligado:** `hub` ausente no `/me` → hub não renderiza (compat); loja sem config → todas as faixas.
  Nada esconde por erro. Credenciais: renderizada só sob `pode_gerir_redes` (verdadeiramente ausente do DOM senão).
- **Risco frontend:** sem teste JS → `node --check` + roteiro manual em T3/T4.
