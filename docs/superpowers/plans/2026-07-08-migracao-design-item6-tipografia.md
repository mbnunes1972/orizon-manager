# Passo 2 (migração visual) — Item 6: tipografia única (Inter) + mono só em números

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou
> executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Unificar a tipografia do app numa **família sans única (Inter)** — hierarquia por peso/tamanho, não por
troca de fonte — **aposentando a Epilogue**, e manter **IBM Plex Mono só em números** (valores monetários/numéricos).
Corresponde ao **item 6 da seção 5** do padrão (`docs/design/backlog-migracao-design.md`; **fonte de verdade = o
`.docx`**, tabela de tipografia em `docs/design/padrao-design-orizon-v2.md` §3).

**Architecture:** Hoje o estado está **invertido** em relação à spec: `body` usa **`IBM Plex Mono` como default**
(`static/index.html:46`) → corpo/inputs/labels/tabelas herdam mono; a **Epilogue** é aplicada **explicitamente** a
títulos/nav/botões (65 declarações uniformes `font-family:'Epilogue',sans-serif`). O **mono explícito** (41 declarações
`font-family:'IBM Plex Mono',monospace`) está **só em números** — 13 campos de valor `mp-a-*`, 9 `<td>` numéricas
alinhadas à direita, e demais inputs/spans de valor (auditados: nenhum é texto). A migração: (1) **tokenizar** as fontes
(`--font-sans`/`--font-mono` no `:root`), (2) **virar o default do `body` para sans**, (3) **substituir as 65 Epilogue
por `var(--font-sans)`** (os pesos/tamanhos já dão a hierarquia) e **as 41 mono por `var(--font-mono)`** (seguem mono),
(4) **trocar o link do Google Fonts** (Epilogue→Inter, mantendo IBM Plex Mono), (5) mesmo para `login.html`. Como todo
mono explícito é numérico e o default vira sans, a regra "mono só em números" fica satisfeita **sem auditoria adicional**
— resta **verificação visual** (não há teste de front).

**Tech Stack:** `static/index.html` + `static/login.html` (CSS/HTML/JS inline — **sem teste JS/visual**; `node` não
está disponível neste ambiente → validação por **balanço/grep + verificação manual no navegador**). Backend **intocado**
(suíte segue **681**). Branch: `feat/design-tipografia`.

**Escopo = SÓ item 6.** NÃO faz o item 7 (toggle de tema). NÃO renomeia o `<title>`/logo "Promob → Omie" (copy de marca
obsoleta em `index.html:6` e `login.html` — **sinalizado à parte**, decisão do usuário). NÃO mexe em pesos/tamanhos
(só a **família**). Os `#c8a84b` decorativos (~L829/831) seguem fora (follow-up de marca já registrado).

**Ler antes:** `docs/design/padrao-design-orizon-v2.md` §3 (tabela de tipografia) · `docs/design-tokens.md` §3 (estado
atual, confirma `body` mono) · `static/index.html:6-8` (link + início do `<style>`/`:root`) e `:46` (`body`).
**Baseline 681 passed.** `git add` só `static/index.html` e `static/login.html`.

---

## Task 1: Tokenizar fontes + virar o default do `body` para sans (index.html)

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Trocar o link do Google Fonts (L7)** — dropar Epilogue, adicionar **Inter** (com os pesos que o app
  usa: 400/500 já eram do mono; 600/700/900 eram da Epilogue), **mantendo IBM Plex Mono**:
```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600;700;900&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Adicionar os tokens de fonte no `:root`** (logo após a linha `--sb-bg:var(--surface);`, junto dos
  aliases — são theme-independent, definidos uma vez só; o `:root[data-theme="light"]` **não** precisa redefinir):
```css
  /* Tipografia — família sans única (Inter) + mono reservado a números (Padrao_Design_Orizon_v2 §3) */
  --font-sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --font-mono:'IBM Plex Mono',ui-monospace,'SFMono-Regular',Menlo,monospace;
```

- [ ] **Step 3: Virar o default do `body` para sans (L46).** Trocar **só** o `font-family` (mantendo o resto da regra):
  - De:  `body{background:var(--bg);color:var(--text);font-family:'IBM Plex Mono',monospace;height:100vh;display:flex;overflow:hidden}`
  - Para: `body{background:var(--bg);color:var(--text);font-family:var(--font-sans);height:100vh;display:flex;overflow:hidden}`
  > Edite esta linha **antes** do Step 5 (ela contém a string `font-family:'IBM Plex Mono',monospace` que o Step 5 troca
  > em massa; fazendo o `body` primeiro, o replace-all do Step 5 não a afeta e o `body` fica sans, não mono).

- [ ] **Step 4: Substituir as 65 Epilogue → `var(--font-sans)`** (string uniforme; usar replace-all):
  - Trocar todas as ocorrências de `font-family:'Epilogue',sans-serif` por `font-family:var(--font-sans)`.
  - Verificar: `grep -c "Epilogue" static/index.html` → **0** (a única que restava fora do `font-family` era o link do
    Step 1, já removido).

- [ ] **Step 5: Substituir as 41 mono → `var(--font-mono)`** (string uniforme; replace-all). Após o Step 3, a linha do
  `body` já não casa mais, então só sobram as 41 declarações de valor/`<td>`:
  - Trocar todas as ocorrências de `font-family:'IBM Plex Mono',monospace` por `font-family:var(--font-mono)`.
  - Verificar: `grep -c "font-family:'IBM Plex Mono',monospace" static/index.html` → **0**;
    `grep -c "var(--font-mono)" static/index.html` → **41**.

- [ ] **Step 6: Verificação.**
  - `grep -c "Epilogue" static/index.html` → **0**; `grep -c "'IBM Plex Mono'" static/index.html` → **1** (só o token
    `--font-mono` no `:root`).
  - `grep -c "var(--font-sans)" static/index.html` → **66** (65 ex-Epilogue + o `body`).
  - `python3 -m pytest -q` → **681** (backend intocado).
  - **Verificação manual (essencial — não há teste visual):** Ctrl+F5 e olhar: (a) **títulos/nav/botões/labels/corpo**
    agora em **Inter** (não Epilogue nem mono); a hierarquia (peso/tamanho) permanece. (b) **valores monetários** — o
    banner de negociação, os campos `mp-a-*` (bruto/desconto/à vista/margem/líquido…) e as **colunas numéricas das
    tabelas** (orçamento, ambientes) seguem em **mono**, alinhadas. (c) nada ilegível/estourado. Anotar telas estranhas.

- [ ] **Step 7: Commit.**
```bash
git add static/index.html
git commit -m "feat(design): item 6 — tipografia sans unica (Inter) + mono so em numeros (index.html)"
```

---

## Task 2: login.html — mesma sans única (Inter)

**Files:** Modify `static/login.html`.

- [ ] **Step 1: Trocar o `@import` (L8)** de Epilogue para Inter:
  - De:  `@import url('https://fonts.googleapis.com/css2?family=Epilogue:wght@400;600;700&display=swap');`
  - Para: `@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');`

- [ ] **Step 2: Substituir as 3 declarações `font-family: 'Epilogue', sans-serif`** (com espaços, no `body`, `input`,
  `.btn`) pela mesma stack sans do app (login é standalone, não herda o `:root` do index → usar a stack literal):
  - Trocar todas as ocorrências de `font-family: 'Epilogue', sans-serif` por
    `font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif`.
  - Verificar: `grep -c "Epilogue" static/login.html` → **0**.

- [ ] **Step 3: Verificação.**
  - `grep -c "Epilogue" static/login.html` → **0**; `grep -c "Inter" static/login.html` → **≥4** (import + 3 stacks).
  - **Manual:** Ctrl+F5 na tela de login → texto em **Inter**, layout intacto (login não tem números → sem mono).

- [ ] **Step 4: Commit.**
```bash
git add static/login.html
git commit -m "feat(design): item 6 — login.html na sans unica (Inter)"
```

---

## Task 3: Docs — checklist + DEV_LOG

**Files:** Modify `docs/design/backlog-migracao-design.md`, `DEV_LOG.md`.

- [ ] **Step 1:** Em `backlog-migracao-design.md`, marcar **item 6 como CONCLUÍDO** (`✅ feito 2026-07-08`), registrando:
  família sans única = **Inter** (system-ui fallback); **Epilogue aposentada**; **mono (IBM Plex Mono) mantido só em
  números** (o default do `body` virou sans; o mono explícito das 41 declarações — campos `mp-a-*` + `<td>` numéricas —
  já era 100% numérico, então a regra fica satisfeita); fontes **tokenizadas** (`--font-sans`/`--font-mono`). Manter o
  aviso "checklist derivado, fonte = `.docx`".
- [ ] **Step 2:** `DEV_LOG.md` — nota do passo 2 item 6 (Inter, fim da Epilogue, mono só números, tokens de fonte;
  frontend puro/suíte 681; **verificação visual com o usuário**; **pendente do passo 2 = só o item 7**). Re-sinalizar o
  copy obsoleto **"Promob → Omie"** — agora confirmado **também no `<title>` do `index.html:6`**, além do login.
- [ ] **Step 3: Commit.**
```bash
git add docs/design/backlog-migracao-design.md DEV_LOG.md
git commit -m "docs(design): item 6 do backlog concluido (tipografia unica Inter + mono so numeros)"
```

---

## Self-review do plano
- **Cobertura:** item 6 (sans única + mono só números) = T1 (index: link, tokens, body→sans, 65 Epilogue→sans, 41
  mono→mono-token) + T2 (login). Checklist/DEV_LOG + nota "derivado do `.docx`" = T3. Escopo restrito ao item 6 (7 fora).
- **Sem placeholders:** strings exatas para o link, os tokens, a linha do `body`, e os dois replace-all (com contagens
  esperadas). Ordem body-primeiro-depois-replace declarada para não colidir.
- **Consistência:** `--font-sans`/`--font-mono` definidos no `:root` e referenciados em T1; login usa a **stack literal**
  (não herda o `:root`). Contagens: Epilogue 65→0, mono 41→`var(--font-mono)` 41, `var(--font-sans)` 66 (65+body),
  `'IBM Plex Mono'` restante = 1 (o token).
- **Risco (alto, visual):** mudança transversal de fonte sem teste visual → **verificação manual obrigatória** em T1/T2.
  O default vira sans e o mono explícito (numérico) é preservado → "mono só em números" satisfeito por construção; a
  auditoria mostrou 0 mono em texto. Se algum número perder o mono (dependia do default), é ajuste pontual (adicionar
  `font-family:var(--font-mono)`), não reverter. Pesos/tamanhos intocados (só família) → hierarquia preservada; o link
  do Inter inclui 400/500/600/700/900 (todos os pesos usados por Epilogue/mono).
- **Fora de escopo:** item 7 (toggle); copy "Promob → Omie" (`<title>` + login); `#c8a84b` decorativo.
