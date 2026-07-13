# Padrão de Design — Orizon (v2)

> ⛔ **Paleta SUPERADA (2026-07-12).** Este doc descreve o tema **petróleo + dourado Dalmóbile** (antigo).
> A identidade atual é **cobre** (accent) unificado nos dois temas, **areia** no claro e **carvão** no
> escuro — fonte única em **`design-system/orizon-tokens.css` (v1.5)** e marca em
> `design-system/marca/REGRAS_MARCA.md` (glifo da bússola; dourado só em marketing, fora do produto).
> As regras de layout/componentes abaixo seguem válidas; só as **cores** estão desatualizadas.

> Fonte: `Padrao_Design_Orizon_v2.docx` (extraído automaticamente). **Especificação oficial de front-end.**

Padrão de Design — Orizon Studio
v2 — perfil + escala de botões consolidada 2026-07-08 · base técnica: design-tokens.md
## 1. Perfil de design
Tema dual, selecionável pelo usuário — claro e escuro, mesma paleta semântica, luminosidade invertida
Accent primário: petróleo — ação, foco, navegação ativa, links
Accent secundário de marca: dourado Dalmóbile — reservado a badge "Fechado", logo, cabeçalhos de documentos gerados (contrato, orçamento). Não usar em botões de ação.
Tipografia: uma única família sans em todo o app — hierarquia por peso/tamanho, não por troca de fonte
Mono (IBM Plex Mono): exceção funcional só para alinhamento de valores monetários/numéricos em tabela
Estética: clean, espaçoso, hierarquia por peso e espaço — não por saturação de cor (linha NetSuite/Zoho)
## 2. Tokens de cor
## 2.1 Superfícies e texto
## 2.2 Accent e marca
## 2.3 Semânticas de sistema
## 2.4 Status de negócio (badges)
Semântica de negócio já existe no código (_PROJ_STATUS_LABEL) — aqui só tokenizamos a cor.
## 3. Tipografia
Família única: Inter (ou system-ui como fallback). Mono reservado a números em tabela.
## 4. Componentes
## Botões — variante (cor/função)
Primário — bg --accent, texto branco. 1 por tela.
Secundário — transparente, borda --border, texto --muted; hover: borda + texto --accent
Perigo — transparente, borda/texto --err; hover: bg tint de --err
## Botões — escala de tamanho
## Botões — regra de dimensão (sem exceção)
Altura é fixa por tamanho — nunca cresce para caber o texto
Largura: conteúdo + padding, com max-width por contexto (ex. botão de tabela ≤140px); texto que excede trunca com reticências (…), nunca estica o botão
Radius: sempre o da escala do tamanho — nunca 0, nunca valor customizado ad-hoc. Nenhuma exceção "especial".
Rótulo: 1–3 palavras. Ação com texto mais longo vira link ou item de menu, não botão.
## Badge de status
Inline-flex, padding 3px 9px, radius 10px, 11px/500, ícone outline (Tabler) + texto — nunca emoji
## Navegação lateral
Agrupada por faixa de titularidade (Comercial · Logística · Pós-venda), não lista plana
Item ativo: bg --surface-2 + borda --border + texto --accent, peso 500
Item inativo: texto --muted, sem fundo
## Escala de raio e espaçamento (demais componentes)
Raios: 6px (inputs pequenos) · 8px (nav) · 10px (badges) · 12px (cards) — botões seguem a escala própria da seção 4
Espaçamento de conteúdo: 22px 26px · gaps de ação 10px · grids 16–20px
## 5. Backlog de migração
Ordem sugerida — cada item é independente, pode ser feito incrementalmente.
1. Substituir a paleta atual (dark-terminal verde-menta) pelos tokens claro/escuro acima
2. Remover a tinta laranja legada (rgba(232,97,26,…)) de hover/ativo — usar --accent-tint
3. Unificar login.html ao mesmo :root do app — hoje tem paleta própria e divergente
4. Tokenizar as cores de status hoje hardcoded (#f05a50, #d4a017, #c8a84b) para --st-*
5. Corrigir class="btn-primary" sem a base .btn (perde padding/fonte)
6. Unificar tipografia — remover Epilogue, migrar para família sans única + mono só em números
7. Implementar toggle de tema claro/escuro, persistido por usuário (não por preferência de SO)
8. Construir o hub de módulos agrupado por faixa (Comercial/Logística/Pós-venda) com os novos tokens
9. Mover Credenciais e Tokens para dentro de Admin, visibilidade condicionada à capability

### Tabela 1
| Token | Claro | Escuro | Papel |
|---|---|---|---|
| --bg | #FFFFFF | #171B1C | Fundo da página |
| --surface | #F7F7F5 | #1D2224 | Sidebar, topbar |
| --surface-2 | #FFFFFF | #20262A | Cards, inputs, dropdowns |
| --border | #E4E2DC | #2C3335 | Divisor padrão |
| --border-strong | #D3D1C7 | #3A4245 | Hover, ênfase |
| --text | #2A2A28 | #EDEFEE | Texto primário |
| --muted | #8A8880 | #8C979A | Texto secundário, labels |

### Tabela 2
| Token | Claro | Escuro | Papel |
|---|---|---|---|
| --accent | #1F4B4B | #4FA89E | Petróleo — ação primária, foco, nav ativo |
| --accent-tint | rgba(31,75,75,.10) | rgba(79,168,158,.14) | Fundo hover/ativo (substitui laranja legado) |
| --gold | #9C7A0C | #D4B348 | Dourado Dalmóbile — marca, "Fechado", documentos |
| --gold-tint | rgba(184,150,12,.14) | rgba(212,179,72,.16) | Fundo de badge dourado |

### Tabela 3
| Token | Claro | Escuro | Papel |
|---|---|---|---|
| --warn | #EF9F27 | #EF9F27 | Aviso do sistema (âmbar) |
| --err | #D64A3C | #E2876C | Erro, ação de perigo |
| --info | #2266A8 | #7DB3E8 | Informativo (mesma cor do status "frio") |

### Tabela 4
| Token | Claro | Escuro | Status |
|---|---|---|---|
| --st-quente | #B1452A | #E2876C | Lead quente |
| --st-morno | #B87A1E | #E8B458 | Lead morno |
| --st-frio | var(--info) | var(--info) | Lead frio |
| --st-convertido | var(--accent) | var(--accent) | Ganho |
| --st-fechado | var(--gold) | var(--gold) | Contrato fechado |
| --st-perdido | var(--muted) | var(--muted) | Perdido |

### Tabela 5
| Contexto | Tamanho | Peso | Extras |
|---|---|---|---|
| Título de página | 20px | 500 | — |
| Header de coluna | 11px | 500 | uppercase, letter-spacing .5px, --muted |
| Item de menu | 13px | 500 | — |
| Corpo / célula de tabela | 13px | 400 | — |
| Botão | 13px | 500 | — |
| Label de campo | 12px | 400 | --muted |
| Valor numérico/monetário | 13px | 400 | IBM Plex Mono, alinhado à direita |

### Tabela 6
| Tamanho | Altura fixa | Fonte | Radius | Uso típico |
|---|---|---|---|---|
| sm | 28px | 11px/500 | 6px | ação inline em linha de tabela (ex. "Abrir") |
| md (padrão) | 36px | 13px/500 | 8px | ação de tela (ex. "+ Novo projeto") |
| lg | 44px | 14px/500 | 8px | ação primária de destaque (ex. confirmar contrato) |
