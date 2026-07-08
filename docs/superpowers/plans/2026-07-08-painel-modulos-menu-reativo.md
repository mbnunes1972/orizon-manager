# Painel de Módulos + Menu Reativo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou
> superpowers:executing-plans para executar tarefa-a-tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Dar **cara visível** à modularização (Fase 1): um **painel no Admin da loja** para ligar/desligar os
domínios por loja, e um **menu que reage** — o menu lateral esconde Clientes/Parceiros quando Cadastro está
desligado, e o Admin da loja esconde as abas Fiscal/Financeiro conforme o módulo. Usa a topologia backend que já
existe (`GET/POST /api/admin/lojas/<id>/modulos`, motor `modulos_ativos_da_loja`, default tudo-ligado).

**Architecture:** Backend expõe rótulos/ordem/dependências dos domínios (`modulos.py`) + injeta os módulos ativos
da loja do usuário no bootstrap `/api/auth/me` + valida topologia coerente (fecho de dependência) no POST.
Frontend: nova aba **Módulos** no admin da loja (espelha o padrão da aba Fiscal: GET estado + salvar via POST) +
`_aplicarModulosNoMenu()` que esconde itens de menu/abas conforme o conjunto ativo. Default **tudo-ligado** →
lojas sem config seguem idênticas.

**Tech Stack:** Python `http.server` + SQLAlchemy/SQLite (backend testável com pytest); `static/index.html`
(HTML+CSS+JS inline — **sem teste JS**, verificação por `node --check` do `<script>` extraído + navegador).

**Ler antes:**
- Backend já pronto (Fase 1): `modulos.py` (`MODULOS`, `DOMINIOS`, `modulo_do_path`), `mod_tenancy.modulos_ativos_da_loja/modulo_ativo`, `main.py` `GET/POST /api/admin/lojas/<id>/modulos` (~L1537 e ~L4315), `_bloqueio_modulo` (~L5502).
- Bootstrap: `auth_routes.py` `/api/auth/me` (L65-88, injeta `usuario["lojas"]`/`loja_ativa_id`); `auth.py._usuario_dict` (L167-182).
- Frontend (âncoras do mapa): menu lateral `static/index.html` L408-414 (`nav-00/05/06/07`), gating por flag em `carregarUsuario` L1996-1999, `goPage` L2277-2295; admin da loja `adminRenderLoja` L6957-6977 (5 abas), troca `adminLojaTab` L6979-6989, aba Fiscal `adminFiscalCarregar` L7070 / `adminFiscalSalvar` L7140, id da loja em `_adminNav.loja?.id`.
- **Baseline 670 passed.** Teste: `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança. Branch: `feat/painel-modulos`.

**Regra de ouro:** default tudo-ligado é inviolável — loja com `modulos_ativos=NULL` vê tudo, igual a hoje.

---

## Mapa módulo → rótulo → efeito no menu (referência das tarefas)

| Domínio | Rótulo | Item de menu / aba que reage |
|---|---|---|
| `cadastro` | Cadastro | menu lateral **Clientes (nav-05)** + **Parceiros (nav-06)** |
| `comercial` | Comercial (Vendas) | — (vive dentro de Projetos; não esconde nesta frente) |
| `producao` | Produção / Projetos | — (dentro do ciclo) |
| `fiscal` | Fiscal (NF-e/NFS-e) | aba **Fiscal** do admin da loja |
| `financeiro` | Financeiro | aba **Financeiro** do admin da loja |
| `estoque` | Estoque | — (stub, sem tela — toggle inerte visualmente) |
| `posvenda` | Pós-venda | — (stub) |
| `expedicao` | Expedição / Logística | — (stub) |

---

## Task 1: `modulos.py` — rótulos, ordem e validação de dependência

**Files:** Modify `modulos.py`; Test: `tests/test_modulos.py` (adicionar).

- [ ] **Step 1: Teste primeiro** — adicionar a `tests/test_modulos.py`:
```python
def test_rotulo_e_ordem_dos_dominios():
    ordem = m.dominios_com_rotulo()
    ids = [d["id"] for d in ordem]
    # todos os domínios aparecem, cada um com rótulo humano
    assert set(ids) == set(m.DOMINIOS)
    assert all(d["rotulo"] for d in ordem)
    # ordem estável e conhecida (cadastro primeiro)
    assert ids[0] == "cadastro"


def test_topologia_valida_fecho_de_dependencia():
    # comercial depende de cadastro: comercial ON sem cadastro -> inválido
    ok, _ = m.topologia_valida(["comercial"])
    assert ok is False
    ok2, _ = m.topologia_valida(["cadastro", "comercial"])
    assert ok2 is True
    # tudo ligado é válido
    ok3, _ = m.topologia_valida(list(m.DOMINIOS))
    assert ok3 is True
    # conjunto vazio é válido (nada ativo, nada quebra)
    ok4, _ = m.topologia_valida([])
    assert ok4 is True
```

- [ ] **Step 2: Rodar → falha** (`AttributeError: dominios_com_rotulo`).

- [ ] **Step 3: Implementar em `modulos.py`.** Adicionar `"rotulo"` a cada módulo de domínio no dict `MODULOS`
(sem tocar nos núcleo, sem quebrar os testes existentes que não checam rótulo):
```python
    # nos domínios, acrescente a chave "rotulo": ex. no cadastro -> "rotulo": "Cadastro", etc.
    # cadastro:"Cadastro"  comercial:"Comercial (Vendas)"  producao:"Produção / Projetos"
    # fiscal:"Fiscal (NF-e/NFS-e)"  financeiro:"Financeiro"  estoque:"Estoque"
    # posvenda:"Pós-venda"  expedicao:"Expedição / Logística"
```
E, ao fim do arquivo, a ordem estável + helpers:
```python
# Ordem estável dos domínios para a UI (DOMINIOS é frozenset, sem ordem).
DOMINIOS_ORDEM = ["cadastro", "comercial", "producao", "fiscal", "financeiro",
                  "estoque", "posvenda", "expedicao"]


def dominios_com_rotulo():
    """Lista ordenada dos domínios: [{'id','rotulo','depende_de'}]. Para o painel de módulos."""
    return [{"id": d, "rotulo": MODULOS[d].get("rotulo", d),
             "depende_de": list(MODULOS[d]["depende_de"])} for d in DOMINIOS_ORDEM]


def topologia_valida(ativos):
    """(True, "") se o conjunto `ativos` é coerente: todo módulo ativo tem seus depende_de (que são
    domínios) também ativos — senão (False, msg). Núcleo é sempre ativo (ignorado). Evita salvar uma
    topologia quebrada (ex.: Comercial ligado sem Cadastro)."""
    ativos = set(ativos)
    for mod in ativos:
        for dep in MODULOS.get(mod, {}).get("depende_de", []):
            if dep in DOMINIOS and dep not in ativos:
                return (False, "Módulo '%s' depende de '%s', que precisa estar ativo." % (mod, dep))
    return (True, "")
```
> **Cheque:** `DOMINIOS_ORDEM` deve conter exatamente os 8 domínios de `DOMINIOS` (o teste
> `test_rotulo_e_ordem_dos_dominios` compara os conjuntos). Se `DOMINIOS` mudar, ajuste a ordem.

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_modulos.py tests/test_arquitetura_modulos.py -q` → verde
(o teste de fronteira segue verde — só adicionamos dados/funções puras). Suíte inteira → verde. **Commit:**
```bash
git add modulos.py tests/test_modulos.py
git commit -m "feat(arq): rotulos + ordem + topologia_valida (fecho de dependencia) no manifesto"
```

---

## Task 2: `main.py` — GET enriquecido + POST valida dependência

**Files:** Modify `main.py`; Test: `tests/test_topologia_modulos.py` (adicionar e2e).

- [ ] **Step 1: Teste primeiro** — adicionar a `tests/test_topologia_modulos.py`:
```python
def test_get_modulos_lista_dominios_com_rotulo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    st, d = c.get(f"/api/admin/lojas/{lid}/modulos")
    assert st == 200
    ids = [x["id"] for x in d["dominios"]]
    assert "cadastro" in ids and "fiscal" in ids
    cad = next(x for x in d["dominios"] if x["id"] == "cadastro")
    assert cad["rotulo"] and cad["ativo"] is True     # default tudo-ligado


def test_post_modulos_rejeita_topologia_quebrada(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    lid = seed["loja1_id"]
    # comercial sem cadastro -> 400 (fecho de dependência)
    st, d = c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["comercial"]})
    assert st == 400 and "depende" in (d.get("erro", "")).lower()
    # religa tudo para não contaminar
    c.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})
```

- [ ] **Step 2: Rodar → falha** (GET ainda não devolve `dominios`; POST ainda não valida dependência).

- [ ] **Step 3a: `main.py` — GET `/api/admin/lojas/<id>/modulos`** (~L1537): enriquecer a resposta. Onde hoje faz
`self.send_json({"ok": True, "ativos": sorted(mod_tenancy.modulos_ativos_da_loja(loja))})`, trocar por:
```python
                    import modulos as _mod
                    ativos = mod_tenancy.modulos_ativos_da_loja(loja)
                    dominios = [{"id": x["id"], "rotulo": x["rotulo"], "depende_de": x["depende_de"],
                                 "ativo": x["id"] in ativos} for x in _mod.dominios_com_rotulo()]
                    self.send_json({"ok": True, "ativos": sorted(ativos), "dominios": dominios})
```

- [ ] **Step 3b: `main.py` — POST `/api/admin/lojas/<id>/modulos`** (~L4315): após validar que cada item ∈
`modulos.DOMINIOS` e ANTES de gravar, validar o fecho de dependência:
```python
                    # (após montar `ativos` como lista validada contra DOMINIOS)
                    import modulos as _mod
                    _ok, _msg = _mod.topologia_valida(ativos)
                    if not _ok:
                        self.send_json({"ok": False, "erro": _msg}, code=400); return
```
(Mantém o caminho `ativos is None` → religa tudo, sem validação.)

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_topologia_modulos.py -q` → verde; suíte inteira → verde.
**Reinicie o servidor** se for testar manualmente. **Commit:**
```bash
git add main.py tests/test_topologia_modulos.py
git commit -m "feat(topologia): GET lista dominios+rotulo+ativo; POST valida fecho de dependencia"
```

---

## Task 3: `auth_routes.py` — expor módulos ativos no bootstrap

**Files:** Modify `auth_routes.py`; Test: `tests/test_auth_me_modulos.py` (novo) ou adicionar a um e2e de auth existente.

- [ ] **Step 1: Teste primeiro** — criar `tests/test_auth_me_modulos.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_me_traz_modulos_ativos_default_tudo(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/auth/me")
    assert st == 200
    mods = d["usuario"]["modulos_ativos"]
    assert "cadastro" in mods and "fiscal" in mods      # loja sem config -> tudo ligado


def test_me_reflete_modulo_desligado(http_client_factory, seed, app_db):
    adm = http_client_factory(); adm.login("super", "senha123")
    lid = seed["loja1_id"]
    adm.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": ["cadastro", "comercial", "producao", "financeiro"]})
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/auth/me")
    assert "fiscal" not in d["usuario"]["modulos_ativos"]
    adm.post(f"/api/admin/lojas/{lid}/modulos", {"ativos": None})   # religa
```

- [ ] **Step 2: Rodar → falha** (`me` não tem `modulos_ativos`).

- [ ] **Step 3: `auth_routes.py`** — no handler `/api/auth/me` (L65-88), após montar `usuario` e resolver a loja
ativa, injetar os módulos ativos da loja ativa do usuário. Padrão (adapte aos nomes reais do handler):
```python
    # módulos ativos da loja ativa do usuário (topologia) — default tudo-ligado se sem loja/config
    import mod_tenancy, modulos as _mod
    _loja_ativa = db.get(Loja, usuario.get("loja_ativa_id")) if usuario.get("loja_ativa_id") else None
    usuario["modulos_ativos"] = sorted(mod_tenancy.modulos_ativos_da_loja(_loja_ativa)
                                       if _loja_ativa else _mod.DOMINIOS)
```
> **Cheque os imports/sessão do handler:** confirme como o handler acessa `db`/`Loja` (pode já importar de
> `database`); se o `me` não abrir sessão de DB, use a mesma forma dos outros handlers de `auth_routes.py`. Se
> `loja_ativa_id` não estiver setado ainda no ponto da injeção, use `usuario.get("loja_id")`.

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_auth_me_modulos.py -q` → verde; suíte inteira → verde.
**Commit:**
```bash
git add auth_routes.py tests/test_auth_me_modulos.py
git commit -m "feat(topologia): /api/auth/me expoe modulos_ativos da loja do usuario"
```

---

## Task 4: Frontend — painel "Módulos" no Admin da loja

**Files:** Modify `static/index.html`. **Sem teste JS** — verificar por `node --check` do `<script>` + navegador.

- [ ] **Step 1: Adicionar a aba "Módulos" à lista de abas da loja.** Em `adminRenderLoja` (~L6957-6977), onde as
5 abas são montadas (Dados/Usuários/Projetos/Financeiro/Fiscal), acrescentar uma aba **Módulos** (botão que chama
`adminLojaTab('modulos')`) e um contêiner `<div id="loja-panel-modulos">`. Espelhe o markup das outras abas.

- [ ] **Step 2: Rotear a aba em `adminLojaTab`** (~L6979-6989): adicionar `if (qual==='modulos') adminModulosCarregar();`
(lazy-load), no mesmo estilo do `if (qual==='fiscal') adminFiscalCarregar();`.

- [ ] **Step 3: Implementar `adminModulosCarregar` + `adminModulosSalvar`** (perto de `adminFiscalCarregar`,
~L7070). Espelha o padrão Fiscal, mas consome `.../modulos` (GET lista + **POST** salva):
```javascript
let _modsCfg = null;   // {dominios:[{id,rotulo,depende_de,ativo}], ativos:[...]}

async function adminModulosCarregar() {
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  const box = document.getElementById('loja-panel-modulos');
  if (!lid || !box) return;
  try {
    const r = await fetch(`/api/admin/lojas/${lid}/modulos`, { credentials: 'same-origin' });
    const d = await r.json();
    if (!d.ok) { box.innerHTML = `<p style="color:var(--muted)">${esc(d.erro || 'Sem acesso.')}</p>`; return; }
    _modsCfg = d;
    const linhas = d.dominios.map(m => `
      <label style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)">
        <input type="checkbox" data-mod="${esc(m.id)}" ${m.ativo ? 'checked' : ''} onchange="adminModulosMudou()">
        <span style="flex:1">${esc(m.rotulo)}</span>
        ${m.depende_de.length ? `<span style="color:var(--muted);font-size:.72rem">depende de: ${esc(m.depende_de.join(', '))}</span>` : ''}
      </label>`).join('');
    box.innerHTML = `
      <p style="color:var(--muted);font-size:.82rem;margin:0 0 8px">Ligue/desligue os módulos desta loja.
        Desligar um módulo esconde suas telas e bloqueia suas ações. O núcleo (login, ciclo) é sempre ativo.</p>
      ${linhas}
      <div id="mods-aviso" style="display:none;color:var(--err);font-size:.78rem;margin-top:8px"></div>
      <button class="btn btn-primary btn-sm" style="margin-top:10px" onclick="adminModulosSalvar()">Salvar módulos</button>`;
  } catch(e) { box.innerHTML = `<p style="color:var(--err)">Erro de rede: ${esc(e.message)}</p>`; }
}

function _modsSelecionados() {
  return Array.from(document.querySelectorAll('#loja-panel-modulos input[data-mod]:checked'))
              .map(i => i.getAttribute('data-mod'));
}

function adminModulosMudou() {
  // valida fecho de dependência no cliente (o backend também barra) — avisa e desabilita Salvar
  const ativos = new Set(_modsSelecionados());
  const aviso = document.getElementById('mods-aviso');
  for (const m of _modsCfg.dominios) {
    if (!ativos.has(m.id)) continue;
    const falta = m.depende_de.filter(dep => _modsCfg.dominios.some(x => x.id === dep) && !ativos.has(dep));
    if (falta.length) {
      aviso.textContent = `"${m.rotulo}" depende de: ${falta.join(', ')} — ligue esses módulos.`;
      aviso.style.display = 'block'; return;
    }
  }
  aviso.style.display = 'none';
}

async function adminModulosSalvar() {
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  const ativos = _modsSelecionados();
  try {
    const r = await fetch(`/api/admin/lojas/${lid}/modulos`, {
      method: 'POST', credentials: 'same-origin', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ ativos }) });
    const d = await r.json();
    if (!d.ok) { await avisoPopup(esc(d.erro || 'Falha ao salvar.'), {titulo:'Módulos'}); return; }
    showToast('Módulos atualizados!', false);
    // se editou a PRÓPRIA loja ativa, recarrega o usuário p/ o menu reagir na hora
    if (String(lid) === String(_usuarioAtual && _usuarioAtual.loja_id)) { await carregarUsuario(); }
    adminModulosCarregar();
  } catch(e) { await avisoPopup('Erro de rede: ' + esc(e.message), {titulo:'Módulos'}); }
}
```

- [ ] **Step 4: Balanceamento do `<script>` + syntax.** Extraia o `<script>` e rode `node --check` (se `node`
não existir no ambiente, cheque o balanço de `{}`/`()`/`` ` `` das LINHAS ADICIONADAS com um contador — não
piorar). `python3 -m pytest -q` (garante que o backend segue verde). **Commit:**
```bash
git add static/index.html
git commit -m "feat(admin): painel de modulos por loja (liga/desliga, com aviso de dependencia)"
```

---

## Task 5: Frontend — menu reativo (esconde itens/abas de módulo desligado)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Helper `_aplicarModulosNoMenu()`** — usa `_usuarioAtual.modulos_ativos` (que agora vem do
`/api/auth/me`). Adicionar perto do gating do `nav-07` (~L1996-1999):
```javascript
function _aplicarModulosNoMenu() {
  const mods = (_usuarioAtual && _usuarioAtual.modulos_ativos) || null;
  // sem info (null) -> não esconde nada (default tudo-ligado / compat)
  const ativo = (m) => !mods || mods.indexOf(m) !== -1;
  const setNav = (id, on) => { const el = document.getElementById(id); if (el) el.style.display = on ? '' : 'none'; };
  // Cadastro -> Clientes (nav-05) + Parceiros (nav-06)
  setNav('nav-05', ativo('cadastro'));
  setNav('nav-06', ativo('cadastro'));
}
```

- [ ] **Step 2: Chamar após carregar o usuário.** Em `carregarUsuario` (após setar `_usuarioAtual` e o gating do
`nav-07`, ~L1999), acrescentar `_aplicarModulosNoMenu();`. **Cuidado:** o `_aterrissarPorPapel` (L2051) também
mexe em `nav-05/06` para super_admin — garanta que `_aplicarModulosNoMenu()` roda DEPOIS ou que os dois não se
sobrescrevam de forma errada (super_admin já não é operacional; a interseção "esconder" está correta em ambos).

- [ ] **Step 3: Abas Fiscal/Financeiro do admin da loja reagem à loja administrada.** Em `adminRenderLoja`
(~L6957), ao montar as abas, esconder a aba **Fiscal** e **Financeiro** se o módulo estiver desligado **para a
loja sendo administrada**. Como o `adminRenderLoja` monta as abas de forma síncrona e a info de módulos vem por
fetch, o caminho mais simples: buscar os módulos da loja ao entrar no admin dela e guardar em
`_adminNav.loja.modulos` (num ponto como `adminEntrarLoja`), então no render:
```javascript
    // dentro do map/condição das abas:
    const modsLoja = (_adminNav.loja && _adminNav.loja.modulos) || null;   // null -> mostra tudo
    const abaAtiva = (m) => !modsLoja || modsLoja.indexOf(m) !== -1;
    // ... só inclui a aba Fiscal se abaAtiva('fiscal'); a aba Financeiro se abaAtiva('financeiro')
```
E em `adminEntrarLoja(id, nome)` (~L6810), antes de renderizar, popular `_adminNav.loja.modulos` via
`GET /api/admin/lojas/<id>/modulos` (reusa a resposta `ativos`). Se a chamada falhar, deixe `modulos=null`
(mostra tudo — nunca esconda por erro de rede).
> **Nota honesta:** os domínios sem tela dedicada (comercial/producao/estoque/posvenda/expedicao) não têm item de
> menu/aba nesta frente — o toggle deles fica **inerte visualmente** (só reage no backend, via `_bloqueio_modulo`).
> Isso é esperado; a superfície de menu cresce quando esses módulos ganharem tela.

- [ ] **Step 4: Verificação manual (roteiro no navegador)** — Ctrl+F5 e:
  1. Admin → loja → aba **Módulos**: desligar **Cadastro** e Salvar → **é barrado** (Comercial depende de Cadastro) com aviso.
  2. Desligar **Fiscal** (deixando o resto) e Salvar → a **aba Fiscal some** do admin daquela loja.
  3. Entrar com um usuário **operacional da própria loja** com **Cadastro desligado** (via admin, desligue os
     dependentes primeiro) → **Clientes/Parceiros somem** do menu lateral. Religar (Módulos → tudo) → voltam.
  4. Loja sem config (default) → menu e abas idênticos a antes (nada some).
- [ ] **Step 5:** `node --check` do `<script>` (ou balanço das linhas adicionadas) + `python3 -m pytest -q` verde.
**Commit:**
```bash
git add static/index.html
git commit -m "feat(nav): menu reativo — esconde Clientes/Parceiros (cadastro) e abas Fiscal/Financeiro por modulo"
```

---

## Task 6: Fechamento — docs

**Files:** Modify `docs/ARQUITETURA-MODULOS.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Em `ARQUITETURA-MODULOS.md`, na nota da Fase 1, acrescentar que a topologia agora tem **UI**:
painel de módulos por loja (Admin) + menu/abas reativos; `/api/auth/me` expõe `modulos_ativos`. **Step 2:**
`DEV_LOG.md` — nota da frente (painel + menu reativo), contagem da suíte, e a nota honesta de que domínios sem
tela ainda só reagem no backend. **Step 3:** commit.
```bash
git add docs/ARQUITETURA-MODULOS.md DEV_LOG.md
git commit -m "docs: painel de modulos + menu reativo (topologia agora com UI)"
```

---

## Self-review do plano
- **Cobertura do objetivo:** painel por loja (T4) · menu lateral reage — Cadastro→Clientes/Parceiros (T5) · abas
  Fiscal/Financeiro reagem (T5) · backend expõe módulos ao front (T3) · rótulos/ordem/validação de dependência
  (T1/T2) · default tudo-ligado preservado em todas (T2/T3/T5). Escopo "topo + abas do Admin" respeitado; efeito
  dentro do ciclo fica de fora (declarado como não-escopo/inerte).
- **Sem placeholders:** código completo para manifesto, endpoints, bootstrap e as funções JS (adminModulos*,
  _aplicarModulosNoMenu). Os "localize L####" vêm do mapa do frontend com o padrão exato a espelhar (aba Fiscal).
- **Consistência de nomes:** `dominios_com_rotulo`/`DOMINIOS_ORDEM`/`topologia_valida` (T1) usados em T2; resposta
  do GET `{ativos, dominios:[{id,rotulo,depende_de,ativo}]}` consumida igual em T4; `usuario.modulos_ativos` (T3)
  lido por `_aplicarModulosNoMenu` (T5). POST body `{ativos:[...]|null}` idêntico ao backend da Fase 1.
- **Risco frontend:** sem teste JS → `node --check` + roteiro manual (T5 Step 4). Default tudo-ligado garante que
  lojas sem config e o caminho `null` nunca escondem nada por engano.
