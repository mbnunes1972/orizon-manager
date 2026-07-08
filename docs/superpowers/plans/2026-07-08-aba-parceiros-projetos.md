# Aba "Parceiros" na página Projetos (parceiro → projetos relacionados) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** A página **Projetos** (page-00) hoje tem abas **Projetos | Clientes** (`home-tabs`). Adicionar uma 3ª aba
**Parceiros** que lista os parceiros da loja e, para cada um, os **projetos relacionados** (via
`parceiro_id` de cada projeto) — nomes clicáveis que abrem o projeto. Espelha o padrão da aba Clientes.

**Architecture:** A relação projeto→parceiro já existe: cada projeto guarda `parceiro_id` no seu JSON
(`_carregar_projeto`/`_salvar_projeto`), e a lista `GET` de projetos (`_listar_projetos()` + enrichers em
`main.py`) já carrega `parceiro_id` por item. Backend: um enricher resolve `parceiro_nome` na lista. Frontend:
nova aba + painel que **agrupa os projetos por `parceiro_id`** e cruza com a lista de parceiros (`/api/parceiros`).

**Tech Stack:** Python (`http.server`/SQLAlchemy) + pytest (backend testável); `static/index.html` (HTML+CSS+JS
inline — **sem teste JS**; verificação `node --check`/balanço + navegador). Branch: `feat/aba-parceiros`.

**Ler antes:**
- Lista de projetos: `main.py` ~L339 (`projetos = _listar_projetos()` → `_filtrar_projetos_por_loja` →
  `_enriquecer_projetos_com_pool` → `_enriquecer_projetos_com_status` → `send_json({"projetos": projetos})`).
  Os enrichers em `main.py` L58–90. **Cada item já tem `parceiro_id`** (vem do JSON do projeto) — confirmar.
- Parceiro: `POST /api/projetos/<nome>/parceiro` (L3609) grava `proj["parceiro_id"]`; `GET /api/parceiros`
  (~L500) lista parceiros da loja (`_parceiro_dict`); `Parceiro` model (`database.py`).
- Frontend: `home-tabs` L663–667 (Projetos|Clientes) + `homeMostrarTab` L10303; painel Clientes
  `#home-clientes-panel` L668–688 + `cliHomeCarregar` L10311; painel Projetos `#home-projetos-panel` L689–714;
  render das linhas de projeto (`projAplicarFiltros` L2564 / `#proj-resultados`) — como abrir um projeto ao clicar.
- **Baseline 680 passed.** Teste: `python3 -m pytest -q` (fallback
  `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

---

## Task 1: Backend — `parceiro_nome` na lista de projetos

**Files:** Modify `main.py`; Test: `tests/test_projetos_parceiro_lista_e2e.py` (novo) ou um e2e de projetos existente.

- [ ] **Step 1: Verificar o estado atual.** Confirme que cada item de `GET /api/projetos` (a rota que usa
`_listar_projetos()` em `main.py:339`) já traz `parceiro_id`. Rode:
```bash
grep -nE "parceiro_id" main.py | head
```
e, se necessário, leia `_listar_projetos`/`_carregar_projeto` (import em `main.py:38`) para confirmar que
`parceiro_id` está no dict. Se **já vem** `parceiro_id`, ótimo (não precisa adicioná-lo); esta task só acrescenta
`parceiro_nome`. Se **não vier**, adicione-o no enricher abaixo (lendo do JSON via `_carregar_projeto` já não é
ideal em loop — melhor pegar do dict que `_listar_projetos` devolve).

- [ ] **Step 2: Teste primeiro** — `tests/test_projetos_parceiro_lista_e2e.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_lista_projetos_traz_parceiro_nome(http_client_factory, seed, app_db, projetos_dir):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # cria um parceiro e associa a um projeto do seed
    st, dp = c.post("/api/parceiros", {"nome": "Arq Teste", "tipo": "arquiteto", "cpf_cnpj": "111.444.777-35"})
    assert st == 200, dp
    pid = dp["parceiro"]["id"]
    proj = seed["projeto_l1"]
    st2, _ = c.post(f"/api/projetos/{proj}/parceiro", {"parceiro_id": pid})
    assert st2 == 200
    st3, d = c.get("/api/projetos")
    assert st3 == 200
    alvo = next(p for p in d["projetos"] if p["nome_safe"] == proj)
    assert alvo["parceiro_id"] == pid
    assert alvo["parceiro_nome"] == "Arq Teste"
    # projeto sem parceiro -> parceiro_nome None/ausente, sem quebrar
    outros = [p for p in d["projetos"] if p["nome_safe"] != proj]
    assert all(p.get("parceiro_nome") in (None, "") for p in outros if not p.get("parceiro_id"))
```
> Confirme no `conftest.py` os nomes reais: login `dir_l1`, `seed["projeto_l1"]`, e a assinatura de `POST
> /api/parceiros` (o e2e de validação `tests/test_validacao_cadastro_e2e.py` já cria parceiro assim). Ajuste se
> divergir. Rode → **falha** (`parceiro_nome` ausente).

- [ ] **Step 3: `main.py` — enricher `_enriquecer_projetos_com_parceiro`.** Junto dos outros enrichers (L58–90):
```python
def _enriquecer_projetos_com_parceiro(projetos):
    """Resolve o nome do parceiro (arquiteto) de cada projeto a partir do parceiro_id já presente no item."""
    if not projetos:
        return
    ids = {p.get("parceiro_id") for p in projetos if p.get("parceiro_id")}
    if not ids:
        return
    db = get_session()
    try:
        nomes = {pr.id: pr.nome for pr in db.query(Parceiro).filter(Parceiro.id.in_(ids)).all()}
        for p in projetos:
            pid = p.get("parceiro_id")
            p["parceiro_nome"] = nomes.get(pid) if pid else None
    finally:
        db.close()
```
E chamá-lo no handler da lista (após `_enriquecer_projetos_com_status(projetos)`, ~L342):
```python
                    _enriquecer_projetos_com_parceiro(projetos)
```
Faça o mesmo na 2ª chamada de enrichers (a de `locais`, ~L366-367) para consistência, se existir.

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_projetos_parceiro_lista_e2e.py -q` → verde; suíte inteira →
verde (680 + novo). **Commit:**
```bash
git add main.py tests/test_projetos_parceiro_lista_e2e.py
git commit -m "feat(projetos): lista traz parceiro_nome (resolve do parceiro_id) para a aba Parceiros"
```

---

## Task 2: Frontend — aba "Parceiros" na página Projetos

**Files:** Modify `static/index.html`. **Sem teste JS** — `node --check`/balanço + navegador.

- [ ] **Step 1: Adicionar o botão da aba** em `#home-tabs` (L663–667), após o de Clientes:
```html
      <button id="tab-btn-parceiros" class="home-tab" onclick="homeMostrarTab('parceiros')">Parceiros</button>
```

- [ ] **Step 2: Adicionar o painel** `#home-parceiros-panel` (após `#home-clientes-panel`, ~L688), espelhando o de
Clientes (busca + "+ Novo Parceiro" + tabela). A tabela tem coluna **"Projetos relacionados"**:
```html
    <div id="home-parceiros-panel" style="display:none;">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;">
        <input id="par-busca-home" type="text" placeholder="Buscar parceiro por nome ou CPF/CNPJ..."
               style="flex:1;padding:8px 12px;border:1px solid var(--dalm-gold);border-radius:6px;background:var(--card);color:var(--text);"
               oninput="parHomeCarregar()">
        <button class="btn-primary" onclick="parAbrirModalNovo && parAbrirModalNovo()">+ Novo Parceiro</button>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        <thead>
          <tr style="border-bottom:2px solid var(--dalm-gold);">
            <th style="text-align:left;padding:8px;color:var(--dalm-gold-light);">Parceiro</th>
            <th style="text-align:left;padding:8px;color:var(--dalm-gold-light);">CPF/CNPJ</th>
            <th style="text-align:left;padding:8px;color:var(--dalm-gold-light);">Tipo</th>
            <th style="text-align:left;padding:8px;color:var(--dalm-gold-light);">Projetos relacionados</th>
          </tr>
        </thead>
        <tbody id="par-home-tbody"></tbody>
      </table>
    </div>
```
> Confirme o nome real da função de novo parceiro (o botão "+ Cadastrar novo parceiro" do fluxo de projeto usa
> `npAbrirCadastroParceiro`; a aba de Cadastro usa `parAbrirModal`). Use a que abre o modal de novo parceiro; se
> não houver uma "Novo" dedicada, use `parAbrirModal()`.

- [ ] **Step 3: `homeMostrarTab` — tratar 'parceiros'.** Em `homeMostrarTab(tab)` (L10303), adicionar o 3º painel/
botão ao padrão existente (mostrar `#home-parceiros-panel` + marcar `#tab-btn-parceiros` ativo quando
`tab==='parceiros'`, escondendo os outros dois) e, ao entrar, chamar `parHomeCarregar()`. Siga EXATAMENTE o padrão
que a função já usa para 'projetos'/'clientes' (classes `ativo`/`home-tab`, `style.display`).

- [ ] **Step 4: `parHomeCarregar()`** — busca parceiros + projetos, agrupa e renderiza. Adicionar perto de
`cliHomeCarregar` (L10311):
```javascript
async function parHomeCarregar(){
  const tb = document.getElementById('par-home-tbody');
  if(!tb) return;
  try {
    const [rp, rj] = await Promise.all([
      fetch('/api/parceiros', {credentials:'same-origin'}).then(r=>r.json()),
      fetch('/api/projetos',  {credentials:'same-origin'}).then(r=>r.json()),
    ]);
    const parceiros = (rp.parceiros || []);
    const projetos  = (rj.projetos  || []);
    // agrupa projetos por parceiro_id
    const porParceiro = {};
    projetos.forEach(p => { if(p.parceiro_id){ (porParceiro[p.parceiro_id] = porParceiro[p.parceiro_id] || []).push(p); } });
    const q = (document.getElementById('par-busca-home')?.value || '').toLowerCase().trim();
    const filtrados = parceiros.filter(pc =>
      !q || (pc.nome||'').toLowerCase().includes(q) || (pc.cpf_cnpj||'').toLowerCase().includes(q));
    tb.innerHTML = filtrados.map(pc => {
      const projs = porParceiro[pc.id] || [];
      const projHtml = projs.length
        ? projs.map(p => `<a onclick="projAbrir('${esc(p.nome_safe)}')" style="color:var(--accent);cursor:pointer;text-decoration:underline;margin-right:8px">${esc(p.nome_safe)}</a>`).join('')
          + `<span style="color:var(--muted);font-size:11px">(${projs.length})</span>`
        : '<span style="color:var(--muted)">—</span>';
      return `<tr style="border-bottom:1px solid var(--border)">
        <td style="padding:8px">${esc(pc.nome||'')}</td>
        <td style="padding:8px">${esc(pc.cpf_cnpj||'')}</td>
        <td style="padding:8px">${esc(pc.tipo||'')}</td>
        <td style="padding:8px">${projHtml}</td>
      </tr>`;
    }).join('') || `<tr><td colspan="4" style="padding:12px;color:var(--muted)">Nenhum parceiro.</td></tr>`;
  } catch(e){ tb.innerHTML = `<tr><td colspan="4" style="padding:12px;color:var(--err)">Erro ao carregar: ${esc(e.message)}</td></tr>`; }
}
```
> **Confirme o nome da função que abre um projeto** ao clicar (o plano usa `projAbrir(nome_safe)`; o real pode ser
> `projAbrirProjeto`/`abrirProjeto`/`projSelecionar` — veja como a linha da tabela de Projetos faz o clique em
> `#proj-resultados`/`projAplicarFiltros` e use a MESMA função). Ajuste `projAbrir` para o nome real. Confirme
> também as chaves reais do parceiro no `_parceiro_dict` (`nome`, `cpf_cnpj`, `tipo`).

- [ ] **Step 5: Verificação.** `node --check` do `<script>` (ou balanço net 0). `python3 -m pytest -q` verde
(backend intocado por esta task). **Roteiro manual:** página Projetos → aba **Parceiros** → lista os parceiros;
um parceiro com projeto mostra os nomes dos projetos (clicáveis, abrem o projeto) + contagem; parceiro sem projeto
mostra "—"; a busca filtra. **Commit:**
```bash
git add static/index.html
git commit -m "feat(projetos): aba Parceiros (parceiro -> projetos relacionados) na pagina Projetos"
```

---

## Task 3: Docs

**Files:** Modify `DEV_LOG.md`.

- [ ] **Step 1:** Nota no `DEV_LOG.md`: aba Parceiros na página Projetos (parceiro→projetos via `parceiro_id`);
lista de projetos passou a expor `parceiro_nome`. **Commit:**
```bash
git add DEV_LOG.md
git commit -m "docs: aba Parceiros na pagina Projetos (parceiro -> projetos relacionados)"
```

---

## Self-review do plano
- **Cobertura do pedido:** aba Parceiros ao lado de Projetos/Clientes (T2) · relação parceiro↔projetos exibida
  (agrupa por `parceiro_id`, nomes clicáveis) (T2) · backend traz `parceiro_nome` para render limpo (T1).
- **Sem placeholders:** enricher completo (T1), HTML do painel + `parHomeCarregar` + integração no `homeMostrarTab`
  (T2). As "confirme o nome real de X" são verificações com a função/campo a espelhar (projAbrir, parAbrirModal,
  chaves do parceiro), não TODOs.
- **Consistência:** `parceiro_id`/`parceiro_nome` (T1) ↔ `porParceiro`/`p.parceiro_id`/`pc.id` (T2);
  `home-parceiros-panel`/`tab-btn-parceiros`/`par-home-tbody`/`parHomeCarregar` coerentes entre HTML e JS.
- **Risco:** frontend sem teste JS → `node --check` + roteiro manual; maior incerteza = nomes reais de
  `projAbrir`/`parAbrirModal`/chaves do parceiro (mitigado por instruir a confirmar). Backend com e2e.
- **Escopo:** só a página Projetos; não mexe no módulo Cadastro (que tem o CRUD de parceiros) — aqui é a **visão
  operacional** parceiro→projetos, complementar.
