# Navegação Orizon v1 — Cadastro em abas + Sidebar (Módulos/Atalhos/Admin) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Aplicar as **ações imediatas de navegação** do `Diagramacao_e_Navegacao_Orizon_v1.docx` (§2.4/§2.5):
(1) **Clientes e Parceiros saem da sidebar** e passam a viver como **abas dentro de um módulo Cadastro**
(Clientes · Fornecedores · Parceiros · Funcionários · Terceiros); (2) a sidebar ganha uma **seção "Atalhos"**
(separada visualmente) com **Projetos** como único item (máx. 2); (3) o **agrupamento por faixa do hub permanece**
(Vendas / Execução do Projeto / Logística-Expedição / Pós-venda-Montagem / Financeiro — mais fiel ao
ARQUITETURA-MODULOS.md que a versão simplificada "Comercial/Logística/Pós-venda" do doc de design).

**Architecture:** Modelo de navegação de **3 níveis** (Hub → Sidebar → Abas do módulo), profundidade máxima 3.
Frontend puro (`static/index.html`), sem backend. O conteúdo atual de Clientes (`page-05`) e Parceiros (`page-06`)
é **movido** para painéis-aba de um novo `page-10` (Cadastro), **preservando os IDs internos** (`#cli-*`/`#par-*`)
para que `cliCarregar`/`parCarregar` e os modais sigam funcionando sem alteração.

**Tech Stack:** `static/index.html` (HTML+CSS+JS inline). **Sem teste JS** → verificação: `node --check`/balanço do
`<script>` + `python3 -m pytest -q` verde (backend intocado) + roteiro manual. Branch: `feat/nav-cadastro-sidebar`.

**Baseline 680 passed.** `git add` só os arquivos da mudança. **Não** é a migração de design (tokens claro/escuro,
seção 5 do Padrao_v2) — essa é backlog paralelo (Task 3 registra, não implementa).

**Ler antes (âncoras reais):**
- Sidebar `<nav class="sb-nav">` L398–405: `sb-nav-title` "Menu", `nav-08` (Módulos→Hub), `nav-00` (Projetos),
  `nav-05` (Clientes), `nav-06` (Parceiros), `nav-07` (Admin, `display:none` até capability).
- `page-05` (Clientes) L1100–1132 e `page-06` (Parceiros) L1134–1162 — cada uma: `page-title`, busca `#cli-busca`/
  `#par-busca`, tabela `#cli-tbody`/`#par-tbody`, hint `#cli-hint`/`#par-hint`.
- `goPage(n)` L2288 (padrão `page-0${n}`/`nav-0${n}` + lazy-loads: `if(n===5) cliCarregar()`, `if(n===6) parCarregar()`).
- `_HUB_DESTINO` L2305 (`cadastro: ()=>goPage(5)`).
- `_aterrissarPorPapel` L2062 (super_admin esconde `nav-00/05/06`).
- `_aplicarModulosNoMenu` L2010–2015 (esconde `nav-05/06` se `cadastro` off).
- Padrão de aba já existente: `adminLojaTab`/`.home-tab` (admin da loja) — reusar o mesmo estilo de aba.

**Refs a `goPage(5)/goPage(6)`:** só 3 no arquivo (nav-05, nav-06, `_HUB_DESTINO`) — todas tratadas aqui.

---

## Task 1: Módulo Cadastro com abas (`page-10`)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Criar `page-10` (Cadastro) com barra de abas + painéis, movendo o conteúdo existente.**
No lugar de `page-05` e `page-06` (ou logo após `page-06`), criar:
```html
  <!-- PAGE 10: Cadastro (módulo com abas) -->
  <div class="page" id="page-10">
    <div class="page-title">Cadastro</div>
    <div class="home-tabs" style="display:flex;gap:6px;margin:12px 0 18px;flex-wrap:wrap">
      <button class="home-tab active" data-cadtab="clientes"     onclick="cadTab('clientes')">Clientes</button>
      <button class="home-tab"        data-cadtab="fornecedores" onclick="cadTab('fornecedores')">Fornecedores</button>
      <button class="home-tab"        data-cadtab="parceiros"    onclick="cadTab('parceiros')">Parceiros</button>
      <button class="home-tab"        data-cadtab="funcionarios" onclick="cadTab('funcionarios')">Funcionários</button>
      <button class="home-tab"        data-cadtab="terceiros"    onclick="cadTab('terceiros')">Terceiros</button>
    </div>
    <div id="cad-panel-clientes"><!-- MOVER AQUI o conteúdo interno de page-05 (busca + tabela + hint) --></div>
    <div id="cad-panel-parceiros" style="display:none"><!-- MOVER AQUI o conteúdo interno de page-06 --></div>
    <div id="cad-panel-fornecedores" style="display:none"><p style="color:var(--muted)">Fornecedores — em breve.</p></div>
    <div id="cad-panel-funcionarios" style="display:none"><p style="color:var(--muted)">Funcionários — em breve.</p></div>
    <div id="cad-panel-terceiros"    style="display:none"><p style="color:var(--muted)">Terceiros — em breve.</p></div>
  </div>
```
**IMPORTANTE:** mova o **conteúdo interno** de `page-05` (tudo dentro dela EXCETO o `page-title` "Clientes" e o
header com botão "+ Novo Cliente" — mantenha o botão de ação junto da busca, como hoje) para `#cad-panel-clientes`,
e o de `page-06` para `#cad-panel-parceiros`. **Preserve todos os IDs internos** (`cli-busca`, `cli-tbody`,
`cli-hint`, `par-busca`, `par-tbody`, `par-hint`, e o botão "+ Novo Cliente"/"+ Novo Parceiro"). Depois **remova as
`<div class="page" id="page-05">` e `id="page-06">`** (agora vazias). Se `page-05`/`page-06` tinham um header com o
botão primário no topo, leve esse header para dentro do painel correspondente (a ação primária pode ficar acima da
busca do painel).

- [ ] **Step 2: JS — `cadTab` + `cadRender`** (perto de `hubRender`/`goPage`):
```javascript
function cadTab(qual){
  document.querySelectorAll('#page-10 .home-tab').forEach(b =>
    b.classList.toggle('active', b.getAttribute('data-cadtab') === qual));
  ['clientes','parceiros','fornecedores','funcionarios','terceiros'].forEach(k => {
    const p = document.getElementById('cad-panel-'+k);
    if(p) p.style.display = (k === qual) ? 'block' : 'none';
  });
  if(qual === 'clientes')  cliCarregar();
  if(qual === 'parceiros') parCarregar();
}

function cadRender(){ cadTab('clientes'); }   // aba padrão = Clientes
```

- [ ] **Step 3: Rotear `page-10` no `goPage`.** Em `goPage(n)`, adicionar `if(n===10) cadRender();`. **Remover** (ou
deixar inertes) os antigos `if(n===5) cliCarregar();` / `if(n===6) parCarregar();` — as pages 05/06 não existem mais;
o carregamento agora vem de `cadTab`. `goPage(10)` resolve `page-10`/`nav-10` pelo padrão (não haverá `nav-10`, tudo
bem — `goPage` só ativa o que existe).

- [ ] **Step 4: Hub Cadastro → Cadastro.** Em `_HUB_DESTINO`, trocar `cadastro: () => goPage(5)` por
`cadastro: () => goPage(10)`.

- [ ] **Step 5: Verificação.** `node --check` do `<script>` (ou balanço net 0 do diff). `python3 -m pytest -q` verde.
**Roteiro manual:** Hub → card **Cadastro** → abre em **Cadastro** com abas; **Clientes** lista os clientes (busca/
tabela/"+ Novo Cliente" funcionam); **Parceiros** lista os parceiros; Fornecedores/Funcionários/Terceiros = "em breve".
**Commit:**
```bash
git add static/index.html
git commit -m "feat(nav): modulo Cadastro com abas (Clientes/Parceiros + stubs); hub Cadastro abre aqui"
```

---

## Task 2: Sidebar — seções Módulos / Atalhos / Admin

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Reestruturar a `<nav class="sb-nav">` (L398–405).** Substituir por (Tabela 2 do doc de navegação):
```html
  <nav class="sb-nav">
    <div class="sb-nav-title">Módulos</div>
    <div class="nav-item" id="nav-08" onclick="goPage(8)">&#x1F3E0; Módulos</div>

    <div class="sb-secao">
      <div class="sb-nav-title">Atalhos</div>
      <div class="nav-item" id="nav-00" onclick="goPage(0)">&#x25C8; Projetos</div>
    </div>

    <div class="sb-secao">
      <div class="sb-nav-title">Admin</div>
      <div class="nav-item" id="nav-07" onclick="goPage(7)" style="display:none">&#x2699;&#xFE0F; Admin</div>
    </div>
  </nav>
```
Ou seja: **removidos** `nav-05` (Clientes) e `nav-06` (Parceiros); **Projetos** (`nav-00`) movido para a seção
**Atalhos**; **Admin** por último. `nav-08` (Módulos) no topo.

- [ ] **Step 2: CSS do divisor de seção** (perto de `.sb-nav-title`, ~L43):
```css
.sb-secao{margin-top:14px;padding-top:12px;border-top:1px solid var(--border)}
```

- [ ] **Step 3: Limpar `_aplicarModulosNoMenu`.** Em L2010–2015, **remover** as linhas que escondem `nav-05`/`nav-06`
(esses elementos não existem mais). O gating de Cadastro por módulo agora é feito no Hub (o card some via
`hub_layout`, que já filtra por `modulos_ativos`). A função pode ficar sem corpo útil — se ela só fazia isso,
mantenha-a como no-op (ou remova a chamada); **não** deixe `getElementById('nav-05')` dando erro (retorna null, mas
o `setNav` já protege — só remova as duas linhas para não confundir).

- [ ] **Step 4: `_aterrissarPorPapel` (super_admin).** Confirmar o bloco que esconde `['nav-00','nav-05','nav-06']`
para super_admin: **remover** `'nav-05'`/`'nav-06'` da lista (não existem); manter `'nav-00'` (Projetos segue
escondido para super_admin, que não é operacional).

- [ ] **Step 5: Verificação.** `node --check`/balanço; `python3 -m pytest -q` verde. **Roteiro manual:** sidebar
mostra **Módulos** (topo) · **Atalhos → Projetos** (com divisor) · **Admin** (último, só quem tem capability).
Clientes/Parceiros **não** aparecem mais na sidebar — só via Hub → Cadastro. Item ativo destaca certo ao navegar.
**Commit:**
```bash
git add static/index.html
git commit -m "feat(nav): sidebar em secoes (Modulos/Atalhos/Admin); remove Clientes/Parceiros do menu"
```

---

## Task 3: Docs — spec oficial + confirmação de faixa + backlog de design

**Files:** Create `docs/design/navegacao-orizon-v1.md`, `docs/design/padrao-design-orizon-v2.md`; Modify
`docs/ARQUITETURA-MODULOS.md`, `DEV_LOG.md`.

- [ ] **Step 1: Versionar as duas specs como markdown** (extrair dos `.docx` que estão na raiz do repo):
```bash
python3 - <<'PY'
import docx
for src,dst in [("Diagramacao_e_Navegacao_Orizon_v1.docx","docs/design/navegacao-orizon-v1.md"),
                ("Padrao_Design_Orizon_v2.docx","docs/design/padrao-design-orizon-v2.md")]:
    d=docx.Document(src); out=[f"> Fonte: `{src}` (extraído automaticamente). Spec oficial de front-end.\n"]
    for p in d.paragraphs:
        t=(p.text or "").rstrip()
        if t: out.append(("## " if p.style and "Heading" in (p.style.name or "") else "")+t)
    for i,tb in enumerate(d.tables):
        out.append(f"\n### Tabela {i+1}")
        rows=[[ (c.text or '').strip() for c in r.cells] for r in tb.rows]
        if rows:
            out.append("| "+" | ".join(rows[0])+" |"); out.append("|"+"---|"*len(rows[0]))
            for r in rows[1:]: out.append("| "+" | ".join(r)+" |")
    import os; os.makedirs("docs/design",exist_ok=True)
    open(dst,"w",encoding="utf-8").write("\n".join(out))
    print("escrito",dst)
PY
```

- [ ] **Step 2: Confirmar a faixa no `ARQUITETURA-MODULOS.md`.** Na seção "🖥️ Hub de módulos …", acrescentar uma
nota: **o agrupamento por faixa implementado (Vendas / Execução do Projeto / Logística-Expedição / Pós-venda-Montagem
/ Financeiro) é a versão autoritativa**, alinhada a `mod_ciclo.FAIXA_POR_ETAPA`; a versão simplificada
"Comercial/Logística/Pós-venda" do `padrao-design-orizon-v2` está **superada** (o próprio doc de navegação confirma).
E registrar a nova navegação: Clientes/Parceiros viraram abas do módulo **Cadastro**; sidebar em seções
**Módulos / Atalhos (Projetos) / Admin**.

- [ ] **Step 3: Backlog de design (paralelo, não implementado agora).** Criar `docs/design/backlog-migracao-design.md`
com os 9 itens da seção 5 do `padrao-design-orizon-v2` (tema claro/escuro, aposentar tinta laranja legada, unificar
`login.html`, tokenizar status, `class="btn-primary"` sem `.btn`, tipografia única, toggle de tema, etc.), marcando
que **não bloqueiam** a navegação e são incrementais. Referenciar `docs/design-tokens.md` (extração do estado atual).

- [ ] **Step 4:** `DEV_LOG.md` — nota da frente (Cadastro em abas + sidebar em seções + specs versionadas + backlog
de design). **Commit:**
```bash
git add docs/design/ docs/ARQUITETURA-MODULOS.md DEV_LOG.md
git commit -m "docs(design): versiona specs Orizon (navegacao v1 + design v2) + backlog + confirma faixa"
```

---

## Self-review do plano
- **Cobertura das ações imediatas (doc navegação §2.4/§2.5):** Clientes/Parceiros viram abas de Cadastro (T1) ·
  removidos da sidebar (T2) · seção Atalhos com Projetos, separada por divisor, ≤2 itens (T2) · faixa do hub
  confirmada/permanece (T3 §2, sem código) · specs oficiais versionadas + backlog de design paralelo (T3).
- **Sem placeholders:** HTML do `page-10`/painéis, `cadTab`/`cadRender`, sidebar reestruturada, CSS do divisor,
  scripts de extração — completos. "Mover o conteúdo interno de page-05/06 preservando IDs" é instrução precisa
  (os IDs a preservar estão listados).
- **Consistência:** `page-10`/`cad-panel-*`/`cadTab`/`cadRender` (T1) ↔ `goPage(10)` e `_HUB_DESTINO.cadastro`
  (T1) ↔ sidebar sem nav-05/06 (T2). IDs internos de clientes/parceiros inalterados → `cliCarregar`/`parCarregar`/
  modais seguem funcionando. Refs a `goPage(5/6)` (3) todas tratadas.
- **Risco frontend:** sem teste JS → `node --check` + roteiro manual; o maior risco é o *move* dos blocos HTML —
  mitigado por preservar IDs e por só 3 refs a goPage(5/6). Backend intocado (suíte segue 680).
- **Fora de escopo (proposital):** migração de tokens de design (tema claro/escuro etc.) — backlog paralelo (T3),
  não bloqueia.
