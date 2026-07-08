# Passo 2 (migração visual) — Itens 1–2: paleta claro/escuro + aposentar tinta laranja

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Migrar a paleta do app (`static/index.html`) do **dark-terminal verde-menta** para os **tokens
claro/escuro** do `Padrao_Design_Orizon_v2.docx` (accent **petróleo**, dourado como accent secundário de marca),
e **aposentar a tinta laranja legada** (`rgba(232,97,26,…)`) usando `--accent-tint`. Corresponde aos **itens 1 e 2
da seção 5** do padrão (checklist derivado em `docs/design/backlog-migracao-design.md`; **fonte de verdade = o
`.docx`**).

**Architecture:** Reescrever o `:root` com os tokens novos (**escuro = padrão**, `:root[data-theme="light"]` =
claro, pronto para o toggle do item 7) e **aliasar os nomes antigos** (`--card`, `--border2`, `--ok`, `--section`,
`--dalm-gold`, `--dalm-gold-light`) aos novos — assim as **~250 referências `var(--…)` existentes herdam a paleta
nova sem tocar cada uma**. Depois, trocar as 8 ocorrências da tinta laranja por `--accent-tint`.

**Tech Stack:** `static/index.html` (CSS/HTML/JS inline — **sem teste JS/visual**; `node --check`/balanço +
**verificação manual no navegador**). Backend **intocado** (suíte segue 681). Branch: `feat/design-paleta`.

**Escopo desta frente = SÓ itens 1–2.** NÃO faz: item 3 (unificar `login.html`), item 4 (tokenizar status
hardcoded `#f05a50/#d4a017/#c8a84b`), item 5 (`btn-primary` sem `.btn`), item 6 (tipografia única), item 7 (toggle).
Esses ficam para as próximas frentes — cores hardcoded remanescentes (status, teal/amber/coral) **continuam como
estão** por ora.

**Ler antes:** `docs/design/padrao-design-orizon-v2.md` (Tabelas 1–4 = os valores) · `docs/design-tokens.md`
(estado atual) · `static/index.html` L9–25 (`:root` atual) e as 8 linhas com `rgba(232,97,26` (grep). **Baseline
681 passed.** `git add` só `static/index.html`.

---

## Task 1: Reescrever o `:root` — tokens claro/escuro + aliases (item 1)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Substituir o bloco `:root{…}` atual (L9–25) por:**
```css
/* Tokens de design — Padrao_Design_Orizon_v2 (fonte: .docx). Tema dual; PADRÃO = escuro.
   Os "aliases dos tokens antigos" mantêm as ~250 referências var(--…) existentes funcionando com a paleta nova. */
:root{
  /* superfícies e texto (escuro) */
  --bg:#171B1C; --surface:#1D2224; --surface-2:#20262A;
  --border:#2C3335; --border-strong:#3A4245;
  --text:#EDEFEE; --muted:#8C979A;
  /* accent (petróleo) e marca (dourado) — escuro */
  --accent:#4FA89E; --accent-tint:rgba(79,168,158,.14);
  --gold:#D4B348; --gold-tint:rgba(212,179,72,.16);
  /* semânticas de sistema — escuro */
  --warn:#EF9F27; --err:#E2876C; --info:#7DB3E8;
  /* status de negócio — escuro (aplicados aos badges no item 4; definidos aqui já como parte da paleta) */
  --st-quente:#E2876C; --st-morno:#E8B458; --st-frio:var(--info);
  --st-convertido:var(--accent); --st-fechado:var(--gold); --st-perdido:var(--muted);
  /* ── ALIASES dos tokens antigos (NÃO remover — o CSS existente depende deles) ── */
  --card:var(--surface-2); --border2:var(--border-strong); --ok:var(--accent);
  --section:var(--info); --dalm-gold:var(--gold); --dalm-gold-light:var(--gold);
  --sb-bg:var(--surface);
  /* Cartões teal/amber/coral — NÃO cobertos pela paleta v2; mantidos p/ frente futura */
  --teal-bg:#04342C; --teal-brd:#0F6E56; --teal-text:#9FE1CB; --teal-lbl:#5DCAA5;
  --amber-bg:#412402; --amber-brd:#854F0B; --amber-text:#FAC775; --amber-lbl:#EF9F27;
  --coral-bg:#4A1B0C; --coral-brd:#993C1D; --coral-text:#F5C4B3; --coral-lbl:#F0997B;
}
:root[data-theme="light"]{
  --bg:#FFFFFF; --surface:#F7F7F5; --surface-2:#FFFFFF;
  --border:#E4E2DC; --border-strong:#D3D1C7;
  --text:#2A2A28; --muted:#8A8880;
  --accent:#1F4B4B; --accent-tint:rgba(31,75,75,.10);
  --gold:#9C7A0C; --gold-tint:rgba(184,150,12,.14);
  --warn:#EF9F27; --err:#D64A3C; --info:#2266A8;
  --st-quente:#B1452A; --st-morno:#B87A1E; --st-frio:var(--info);
  --st-convertido:var(--accent); --st-fechado:var(--gold); --st-perdido:var(--muted);
}
```
> **Por que aliases:** `--card`(50×), `--border2`(30×), `--ok`(85×), `--section`(4×), `--dalm-gold`(64×),
> `--dalm-gold-light`(11×) aparecem em todo o CSS. Aliasando (`--card:var(--surface-2)` etc.) eles seguem a paleta
> nova automaticamente, sem editar 250 linhas. Os aliases usam `var()`, então mudam sozinhos com o tema.
> **Padrão = escuro** (sem atributo `data-theme`); o claro só entra quando o item 7 (toggle) setar `data-theme="light"`.

- [ ] **Step 2: Verificação de sintaxe/render.**
  - `node --check` do `<script>` (não muda JS, mas confirma que nada quebrou); ou balanço net 0.
  - `grep -c "rgba(232,97,26" static/index.html` → ainda 8 (a Task 2 troca).
  - `python3 -m pytest -q` → **681** (backend intocado).
  - **Verificação manual (essencial — não há teste visual):** Ctrl+F5 e olhar as telas principais: fundo passa a
    **dark petróleo** (não verde-terminal), texto quase-branco, accent petróleo em título/menu ativo/botões, valores
    (banner/orçamento) em petróleo (eram verde). Confirmar que **nada some/fica ilegível** (contraste). Anotar telas
    que ficaram estranhas para ajuste (mas NÃO tokenizar status/teal aqui — é item futuro).

- [ ] **Step 3: Commit.**
```bash
git add static/index.html
git commit -m "feat(design): item 1 — paleta claro/escuro (petroleo/dourado) via :root + aliases; padrao escuro"
```

---

## Task 2: Aposentar a tinta laranja legada (item 2)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Trocar as 8 ocorrências de `rgba(232,97,26,…)`** por `var(--accent-tint)` (fundos) — os fundos de
hover/ativo perdem a variação de alpha (viram o tint único do accent, como o padrão manda):
  - L47 `.nav-item:hover` bg → `var(--accent-tint)`
  - L48 `.nav-item.active` bg → `var(--accent-tint)`
  - L88 `.proj-card-item:hover` bg → `var(--accent-tint)`
  - L97 `.proj-table tr.proj-row:hover td` bg → `var(--accent-tint)`
  - L137 `.drop-zone:hover,.drop-zone.drag` bg → `var(--accent-tint)`
  - L165 `.fb-row` bg → `var(--accent-tint)`
  - L2298 (inline JS, `key===ativo` bg) → `var(--accent-tint)`
  - L1554 (card destacado): `background:rgba(232,97,26,.04)` → `var(--accent-tint)` **e** `border-color:rgba(232,97,26,.2)` → `var(--accent)`
Use `grep -nE "rgba\(232,97,26" static/index.html` para localizar cada uma (os números de linha mudam após a Task 1).

- [ ] **Step 2: Verificação.**
  - `grep -c "rgba(232,97,26" static/index.html` → **0**.
  - `node --check`/balanço; `python3 -m pytest -q` → 681.
  - **Manual:** hover/ativo do menu, hover de card/linha de tabela e drop-zone agora com **tint petróleo** (não mais laranja).

- [ ] **Step 3: Commit.**
```bash
git add static/index.html
git commit -m "feat(design): item 2 — aposenta tinta laranja legada (rgba 232,97,26) -> --accent-tint"
```

---

## Task 3: Docs — checklist + DEV_LOG

**Files:** Modify `docs/design/backlog-migracao-design.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Em `backlog-migracao-design.md`, marcar **itens 1 e 2 como CONCLUÍDOS** (`[x]` ou nota "✅ feito
2026-07-08"), mantendo o aviso de que é checklist derivado (fonte = `.docx`). Registrar o que ficou de fato
(paleta dual definida, padrão escuro; aliases; status/teal/amber ainda hardcoded = itens 4/futuro; toggle = item 7).
- [ ] **Step 2:** `DEV_LOG.md` — nota do passo 2 itens 1–2 (paleta petróleo/dourado dual, tinta laranja aposentada).
**Step 3: Commit.**
```bash
git add docs/design/backlog-migracao-design.md DEV_LOG.md
git commit -m "docs(design): itens 1-2 do backlog concluidos (paleta claro/escuro + fim da tinta laranja)"
```

---

## Self-review do plano
- **Cobertura:** item 1 (paleta claro/escuro via `:root` + aliases, padrão escuro) = T1 · item 2 (tinta laranja →
  `--accent-tint`) = T2 · checklist/DEV_LOG + nota "derivado do .docx" = T3. Escopo restrito a 1–2 (3–7 fora, declarado).
- **Sem placeholders:** `:root` completo (dark+light+aliases+st), as 8 substituições listadas com seletor.
- **Consistência:** aliases (`--card→--surface-2`, `--ok→--accent`, `--dalm-gold→--gold`, `--border2→--border-strong`,
  `--section→--info`) cobrem exatamente os tokens antigos com uso (>0). `--accent-tint` definido em ambos os temas e
  usado na T2. `--st-*` definidos (aplicação nos badges = item 4).
- **Risco (alto, visual):** mudança transversal sem teste visual → `node --check` + **verificação manual obrigatória**
  em T1/T2. Aliases evitam churn e regressão de sintaxe. Cores hardcoded remanescentes (status, teal/amber, `#fff`
  em botões) **persistem de propósito** (itens 4/6). Se algo ficar ilegível no dark novo, anotar — ajuste pontual,
  não reverter a paleta.
- **Fora de escopo:** itens 3–7; templates de diagramação (passo 3).
