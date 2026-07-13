# Design Tokens — Orizon Manager | Dalmóbile

> ⛔ **SUPERADO (2026-07-12).** A fonte única da paleta agora é **`design-system/orizon-tokens.css`
> (v1.5)** — identidade **cobre** unificada nos dois temas (accent cobre), com **areia** no claro e
> **carvão quente** no escuro; sem mais divergência entre temas. A marca vive em
> `design-system/marca/` (glifo da bússola; `REGRAS_MARCA.md`). As tabelas abaixo (navy/azul/ciano §2.0
> e verde-menta/dourado §2.1+) são **registro histórico** do estado anterior — mantidas para referência,
> não são mais canônicas. Ver DEV_LOG Sessão 72/73.

> **Extração fiel do estado atual do código** (2026-07-08), base para o documento de padronização.
> Fonte: `static/index.html` (único `<style>` inline; paleta em `:root`, L9–25). **Não é uma proposta** — é o
> que está no código hoje. As lacunas/divergências estão sinalizadas em §5; uma proposta de consolidação está no
> Apêndice A (claramente marcada como sugestão).

## 1. Onde está definido hoje

| Local | O quê | Situação |
|---|---|---|
| `static/index.html` L9–25 (`:root`) | **Paleta de cor** do app | Única parte tokenizada |
| `static/index.html` (resto do `<style>`) | Tipografia, espaçamento, raios, cores de status | **Inline, hardcoded** — não tokenizado |
| `static/login.html` L12–20 (`:root` próprio) | Paleta da tela de login | **Divergente** do app (ver §5.6) |
| `contrato_template/contrato.css` | Estilo do **PDF do contrato** (WeasyPrint) | Superfície separada — não é o app |
| — | `theme.css` / `tailwind.config` / `design-tokens.json` | **Não existem** |

**Conclusão:** existe um núcleo de tokens (só cor), mas tipografia/espaçamento/raios e várias cores de status
estão espalhados. É o principal alvo da padronização.

## 2. Cores

### 2.0 Paleta navy/azul/ciano (logo antiga) · 2026-07-10 ⛔ SUPERADA (v1.5 → cobre/areia/carvão)
> Alinhada à logo **Orizon Manager**. **Substitui** o verde-menta + dourado das tabelas §2.1–2.4 abaixo
> (que refletem o tema antigo). O **dourado (`--gold`/`--dalm-gold`) foi REMOVIDO** — sem vínculo de marca
> (Dalmóbile é licenciamento, não marca própria). O **laranja legado de hover (`#E8611A`, §2.4) sai** →
> usar `--accent-tint`/`--surface-2`. Âmbar segue só para avisos; coral/vermelho para erro.
>
> Paleta-base da logo: navy `#0B1D3A` · azul elétrico `#0066FF` · ciano `#00B8C9` · cinza `#8A96A3` · claro `#E6EBF1`.

| Token | Dark | Light | Papel |
|---|---|---|---|
| `--bg` | `#081120` | `#FFFFFF` | Fundo principal (página) |
| `--surface` | `#0B1D3A` | `#F4F7FB` | Sidebar, input, cards de lista (navy no dark) |
| `--surface-2` / `--card` | `#12294A` | `#FFFFFF` | Cards, dropdowns, modais (elevado) |
| `--border` | `#1C3459` | `#DCE3EC` | Borda/divisor |
| `--border-strong` / `--border2` | `#2A4A73` | `#C6CFDB` | Borda secundária/hover |
| `--accent` | `#00B8C9` | `#0E7C8C` | Ciano de ação — menu ativo, logo, foco, valores |
| `--accent-tint` | `rgba(0,184,201,.16)` | `rgba(14,124,140,.10)` | Fundo de estado (ativo/hover) |
| `--primary` (btn/ação/link) | `#0066FF` | `#0066FF` | Azul elétrico — botão primário, links |
| `--ok` | `#00B8C9` | `#0E7C8C` | Sucesso/valores (= accent) |
| `--text` | `#E6EBF1` | `#0B1D3A` | Texto primário |
| `--muted` | `#8A96A3` | `#5A6572` | Texto secundário/esmaecido |
| `--info` / status "frio"/"fechado" | `#5B9BFF` | `#0066FF` | Azul de metadados (substitui o dourado no "fechado") |
| `--warn` | `#EF9F27` | `#EF9F27` | Aviso (âmbar) — mantido |
| `--err` | `#E2876C` | `#D64A3C` | Erro/perigo (coral/vermelho) — mantido |

> **Removidos:** `--gold`, `--dalm-gold`, `--dalm-gold-light`. O status **`fechado`** deixa de ser dourado e
> passa a azul (`--info`). Contrastes finais (WCAG) a validar na aplicação, nos dois temas.

### 2.1 Tokens do `:root` (app — index.html L10–24)
| Token | Hex | Papel |
|---|---|---|
| `--bg` | `#111d11` | **Fundo principal (dark)** |
| `--surface` | `#0e180e` | Sidebar, fundo de input, cards de lista |
| `--card` | `#162016` | Cards, dropdowns, modais |
| `--sb-bg` | `#0d160d` | Declarado; a sidebar na prática usa `--surface` |
| `--border` | `#1e2e1e` | **Borda/divisor** padrão |
| `--border2` | `#2a3a2a` | Borda secundária (ghost, dashed, dropdowns) |
| `--accent` | `#5DCAA5` | **Verde-menta de ação** — menu ativo, logo, `btn-primary`, foco, nome do app |
| `--ok` | `#5DCAA5` | Sucesso/valores (**mesmo hex de `--accent`**) |
| `--text` | `#9FE1CB` | **Texto primário** |
| `--muted` | `#4d7a4d` | **Texto secundário/esmaecido** (labels de coluna, subtítulos, placeholders) |
| `--warn` | `#EF9F27` | Aviso (âmbar) |
| `--err` | `#F0997B` | Erro/perigo (coral) |
| `--create` | `#a78bfa` | Roxo (criação — uso pontual) |
| `--section` | `#60a5fa` | Azul (metadados, status "frio") |
| `--dalm-gold` / `--dalm-gold-light` | `#b8960c` / `#c4a234` | Dourado Orizon/Dalmóbile |

### 2.2 Conjuntos de cartão (bg / borda / texto / label)
| Cartão | `bg` | `brd` | `text` | `lbl` |
|---|---|---|---|---|
| teal | `#04342C` | `#0F6E56` | `#9FE1CB` | `#5DCAA5` |
| amber | `#412402` | `#854F0B` | `#FAC775` | `#EF9F27` |
| coral | `#4A1B0C` | `#993C1D` | `#F5C4B3` | `#F0997B` |

### 2.3 Badges de status — **há semântica** (`_PROJ_STATUS_LABEL`, JS L2360 + CSS L89–96)
| Status (valor) | Rótulo | Cor do texto | Fundo | Semântica |
|---|---|---|---|---|
| `quente` | 🔥 Quente | `#f05a50` | `rgba(240,90,80,.12)` | Lead quente |
| `morno` | ● Morno | `#d4a017` | `rgba(251,191,36,.12)` | Lead morno |
| `frio` | ❄ Frio | `--section` `#60a5fa` | `rgba(96,165,250,.12)` | Lead frio |
| `convertido` | ✓ Convertido | `--ok` `#5DCAA5` | `rgba(25,201,160,.12)` | Ganho |
| `fechado` | 🔒 Fechado | `#c8a84b` | `rgba(180,140,40,.16)` | Contrato fechado |
| `perdido` | ✗ Perdido | `--muted` `#4d7a4d` | `rgba(120,120,120,.12)` | Perdido |
| *(sem status)* | — Definir | `--muted` | `transparent` | Placeholder de ação |

> A **lógica semântica existe** (mapa `status → {rótulo, classe}`), mas as **cores dos badges não são tokens**
> (`#f05a50`, `#d4a017`, `#c8a84b` + `rgba(...)` crus). O fundo do `convertido` usa `rgba(25,201,160,…)` =
> `#19C9A0`, um **verde diferente** do `--ok`/`--accent` (`#5DCAA5`).

### 2.4 Tinta de estado (hover/ativo) — **laranja legado** ⚠️
Os fundos de hover/ativo do menu, cards e drop-zone usam `rgba(232,97,26,α)` — que é **laranja `#E8611A`**,
resíduo de um tema antigo. Ex.: `.nav-item.active` → texto/borda em `--accent` (verde), mas o **fundo** é um
laranja fraco. Ver §5.2.

## 3. Tipografia

Carregadas via Google Fonts (index.html L7):
- **`IBM Plex Mono`** (400, 500) — monoespaçada; `font-family` do `body`: corpo, inputs, tabelas, valores.
- **`Epilogue`** (400, 600, 700, 900) — sans-serif display: títulos, nav, botões, labels de seção.

| Contexto | Fonte | Tamanho | Peso | Extras |
|---|---|---|---|---|
| Título de página `.page-title` | Epilogue | 22px | 900 | letter-spacing −.5px |
| Cabeçalho de projeto `.proj-header-nome` | Epilogue | 20px | 900 | |
| Nome do app `.sb-app-name` | Epilogue | 15px | 900 | ls −.3px |
| Header de coluna `.proj-table th` | (mono) | 10px | 600 | UPPERCASE, ls .6px, `--muted` |
| Título de card `.card-title` | Epilogue | 11px | 700 | UPPERCASE, ls 1.5px, `--muted` |
| Item de menu `.nav-item` | Epilogue | 12px | 600 | |
| Corpo / célula de tabela | IBM Plex Mono | 12–13px | 400 | |
| Botão `.btn` | Epilogue | 13px | 700 | ls .2px (`.btn-sm` → 11px) |
| Label de campo `.field-label` | (mono) | 10px | — | `--muted`, ls .5px |
| Subtítulo/hints `.page-sub`/`.hint` | (mono) | 10–11px | — | `--muted` |

## 4. Componentes recorrentes

### Botões
| Variante | Classe | Especificação |
|---|---|---|
| **Primário** | `.btn.btn-primary` | bg `--accent`, texto `#fff`, Epilogue 700/13px, padding `10px 22px`, radius `8px`; hover `opacity .88`; disabled `opacity .35`. Ex.: **"+ Novo Projeto"** (`btn btn-primary btn-sm`) |
| **Secundário** | `.btn.btn-ghost` | transparente, borda `1px --border2`, cor `--muted`; hover borda+cor → `--accent`. Ex.: **"Abrir", "Parâmetros"** (`btn btn-ghost btn-sm`) |
| **Perigo** | `.btn.btn-danger` | transparente, borda/cor `--err`, hover bg `rgba(248,113,113,.1)` |
| **Pequeno** | `.btn-sm` | padding `6px 13px`, 11px (modificador) |

### Badge de status `.proj-status-badge`
inline-flex · padding `2px 8px` · radius `10px` · 10px/700 · ls .3px · gap 4px · cor/bg por classe (§2.3).
Badge de origem `.badge-origem`: 9px, padding `2px 7px`, radius 10px, 700.

### Item de menu lateral `.nav-item`
Epilogue 600/12px, cor `--muted`, padding `9px 10px`, radius 8px, "bolinha" `::before` (6px, `--border2`).
- **inativo:** cor `--muted`, dot `--border2`
- **hover:** bg `rgba(232,97,26,.06)` *(laranja legado)*, cor → `--text`
- **ativo:** bg `rgba(232,97,26,.1)` *(laranja legado)*, cor → `--accent`, `border-left:2px --accent`, dot → `--accent`
- **done:** dot → `--ok`, cor → `--text` · **locked:** `opacity .35`

### Espaçamento e raios
- Card de lista `.proj-card-item`: padding `14px 18px`, margin-bottom `8px`, radius `10px`
- Tabela: `th` `7px 12px`, `td` `10px 12px`, linhas `border-bottom:1px --border`
- Card: padding `24px`, margin-bottom `16px`, radius `12px`
- Conteúdo `.content`: padding `28px 32px`
- Gaps: ações `10px`, grids `16–20px`
- **Escala de raio:** `6px` (inputs pequenos) · `8px` (botões/inputs/nav) · `10px` (cards de lista/badges) · `12px` (cards)

## 5. Lacunas / dívidas de padronização (a resolver)

1. **Só a cor é tokenizada.** Tipografia (tamanhos/pesos), espaçamento e raios estão repetidos inline, sem escala nomeada.
2. **Tinta laranja legada** `rgba(232,97,26,…)` (`#E8611A`) em hover/ativo do menu, cards e drop-zone — sobra de tema antigo; conflita com o accent verde.
3. **Verde sem fonte única:** `--accent` e `--ok` são iguais (`#5DCAA5`), mas o fundo do badge `convertido` usa outro verde (`#19C9A0`).
4. **Vermelho sem fonte única:** `btn-danger` hover usa `rgba(248,113,113)` ≠ `--err` (`#F0997B`); e o vermelho do `quente` (`#f05a50`) é outro ainda.
5. **Cores de status fora do `:root`** (`#f05a50`, `#d4a017`, `#c8a84b` + rgba de fundo).
6. **`login.html` tem paleta própria e divergente** (drift real):
   | Token | login.html | app | Diverge? |
   |---|---|---|---|
   | `--bg` | `#0d160d` | `#111d11` | sim |
   | `--card` | `#111d11` | `#162016` | sim |
   | `--accent` | `#9FE1CB` | `#5DCAA5` | **sim** (o accent do login é o `--text` do app) |
   | `--text` | `#c8d8c8` | `#9FE1CB` | sim |
   | `--muted` | `#6a8a6a` | `#4d7a4d` | sim |
   | `--err` | `#e05c5c` | `#F0997B` | sim |
   | fonte | só Epilogue | Epilogue + IBM Plex Mono | sim |
7. **Inconsistência de classe:** "+ Novo Cliente" (L675) usa `class="btn-primary"` **sem a base `.btn`** → perde padding/fonte.

---

## Apêndice A — Proposta de `:root` consolidado (SUGESTÃO, não é o estado atual)

Recomendação para a padronização: trazer status, raios e escala para tokens nomeados, unificar o verde/vermelho
numa fonte só, e aposentar a tinta laranja legada (substituindo por um tint do accent). **Não aplicar sem
revisão visual** — é ponto de partida do documento de padrão.

```css
:root{
  /* superfícies */
  --bg:#111d11; --surface:#0e180e; --card:#162016;
  --border:#1e2e1e; --border2:#2a3a2a;
  /* marca / ação (fonte única do verde) */
  --accent:#5DCAA5; --accent-tint:rgba(93,202,165,.10);   /* substitui rgba(232,97,26,…) laranja */
  --ok:var(--accent);
  /* texto */
  --text:#9FE1CB; --muted:#4d7a4d;
  /* semânticas */
  --warn:#EF9F27; --err:#F0997B; --section:#60a5fa; --create:#a78bfa;
  --dalm-gold:#b8960c; --dalm-gold-light:#c4a234;
  /* status (tokenizar as cores hoje hardcoded) */
  --st-quente:#f05a50; --st-morno:#d4a017; --st-frio:var(--section);
  --st-convertido:var(--ok); --st-fechado:#c8a84b; --st-perdido:var(--muted);
  /* raios */
  --r-sm:6px; --r-md:8px; --r-lg:10px; --r-xl:12px;
  /* espaçamento base */
  --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-6:24px; --sp-8:32px;
  /* tipografia */
  --font-mono:'IBM Plex Mono',monospace; --font-display:'Epilogue',sans-serif;
}
```

**Ações de padronização sugeridas (backlog):** (a) mover cores de status para `--st-*`; (b) substituir toda
`rgba(232,97,26,…)` por `--accent-tint`; (c) unificar o verde do `convertido` e o vermelho do `btn-danger`/`quente`;
(d) alinhar `login.html` ao mesmo `:root` (ou importar); (e) corrigir `class="btn-primary"` → `class="btn btn-primary"`.
