# Auditoria de migração de design — Padrão Orizon v4

Estado de cada rota/tela quanto à migração para `Padrao_Design_Orizon_v4` (tokens `var(--…)`,
depth via `--shadow`, accent teal `--accent`, sem verde-terminal/dourado fixo, theme-aware claro/escuro).
Data: 2026-07-10 · substitui a descoberta tela-a-tela por captura.

Legenda: ✅ Migrada · 🟡 Parcial · 🔴 Não migrada · ⚪ Stub/N-A

| Rota / Tela | id | Estado | Observação |
|---|---|---|---|
| **Login** (entrada) | `static/login.html` | ✅ | Página nova do usuário (v4). O card de login é token-based; a seção "marketing" tem cores próprias por design. |
| **Orçamentos** (atalho) | page-00 | ✅ | Migrada na frente v6 (tokens, filtros, sem abas duplicadas). |
| **Negociação/Orçamento** | page-02 | 🟡 | **Corrigida agora**: cards de resumo, Seletor de Status (Fechado), botão "Etapas do Projeto" e linhas do plano de pagamento passaram a tokens. Painéis das modalidades (Aymoré/Cartão/VP/Total Flex) já eram token-based. **Resta**: painel **Etapas do Projeto (Ciclo)** — badges `.badge-pendente/.badge-em_andamento/...` com cores escuras fixas (§CSS 384–397). |
| **Em Construção** (genérica) | page-08 | ✅ | Construída com tokens. |
| **Config** (Provisões/Comissão/Documentos) | page-09 | ✅ | Construída com tokens (frente v8). |
| **Cadastro** (Clientes/Parceiros/…) | page-10 | 🟡 | Token-based, mas estética **dourada antiga** (tabelas com `--dalm-gold-light`, sublinhado de aba `--dalm-gold`) em vez do accent teal v4. |
| **Fiscal** (Emitente/NF-e) | page-11 | 🟡 | Renderizada por `adminFiscalCarregar` no padrão do console Admin (dourado). Poucos hex fixos. |
| **Financeiro** (Dashboard/DRE/Balanço/…) | page-12 | ✅ | Construído com tokens. |
| **Expedição** (Kanban CicloLogistico) | page-13 | ✅ | Construída com tokens. |
| **Assistências** (casos + a-cobrar-fábrica) | page-14 | ✅ | Construída com tokens. |
| **Admin** (Dados/Usuários/Perfis/Módulos/Credenciais) | page-07 | 🟡 | Token-based, mas **estética dourada antiga**: abas com `border-bottom:2px solid var(--dalm-gold)`, títulos `--dalm-gold`, ~4 hex fixos no JS. Não é o look teal v4. |
| **Exportar** | page-03 | ⚪ | Stub "em breve". |
| **(dummy)** | page-01 | ⚪ | Oculta, só p/ `unlockNav`. |

## Modais / componentes transversais
| Componente | Estado | Observação |
|---|---|---|
| Editar projeto, Novo pedido (Expedição), Detalhe (Expedição), Novo caso (Assistências) | ✅ | Construídos com tokens. |
| Comissão de vendas (`modal-comissao`), Parâmetros (`modal-params`), Novo ambiente, Parceiro (`modal-parceiro`), Briefing | 🟡 | Mistura tokens + alguns hex/dourado fixos. |
| **Ciclo / Etapas do Projeto** (badges de etapa) | 🔴 | `.badge-*` com fundos escuros fixos (`#2a2a1a`, `#1a2a2a`…) — quebram no tema claro. |
| Contrato/Proposta (PDF) | — | `contrato_template/contrato.css` é o **PDF** (WeasyPrint), fora do escopo do design da app. |

## Prioridade sugerida das próximas correções
1. **Ciclo / Etapas do Projeto** (badges `.badge-*`) — 🔴, quebra no claro, e é aberto direto da Negociação.
2. **Admin** (page-07) — 🟡, migrar do dourado para o accent teal v4 (abas, títulos).
3. **Cadastro** (page-10) e **Fiscal** (page-11) — 🟡, mesma estética dourada do Admin.
4. Modais 🟡 (Comissão, Parâmetros, Parceiro, Briefing) — varredura de hex/dourado residual.

> Método: `var(--…)` em vez de hex fixo; fundo `--surface-2` + `--shadow` (não borda dourada);
> labels `--muted`, valores `--text`; cor semântica via token `--st-*`/`--warn`/`--err`/`--accent`
> (tint theme-aware com `color-mix(in srgb, var(--x) N%, transparent)`).
