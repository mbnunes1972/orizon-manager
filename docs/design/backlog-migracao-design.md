# Backlog de migração de design — Orizon Studio

> ⚠️ **Este arquivo é um checklist operacional DERIVADO.** A **fonte de verdade** é o
> **`Padrao_Design_Orizon_v2.docx`** (seção 5). Se o backlog mudar, a alteração volta **primeiro para o .docx** e
> depois se reflete aqui — não editar este `.md` como se fosse a especificação.
>
> Da **seção 5** do `padrao-design-orizon-v2.md`. **Paralelo e não-bloqueante** — cada item é incremental e
> independente das mudanças de navegação (Cadastro em abas, sidebar, hub). Base do estado atual:
> `docs/design-tokens.md` (extração do que existe hoje). Alvo: `padrao-design-orizon-v2.md` (tokens claro/escuro,
> accent petróleo, dourado como accent secundário de marca, fonte única sans + mono só em números).

Ordem sugerida (independentes, incrementais):

1. ✅ **feito 2026-07-08** — **Substituir a paleta atual** (dark-terminal verde-menta) pelos **tokens
   claro/escuro** do padrão v2 (`--bg/--surface/--surface-2/--border/--text/--muted` + accent petróleo
   `#1F4B4B`/`#4FA89E`). Reescrito o `:root` com tema **dual** (padrão = escuro; `:root[data-theme="light"]`
   pronto p/ o toggle do item 7) e **aliases** dos tokens antigos (`--card→--surface-2`, `--ok→--accent`,
   `--dalm-gold→--gold`, `--border2→--border-strong`, `--section→--info`, `--sb-bg→--surface`, e
   `--fg→--text`/`--input→--surface` p/ inputs de modais) — as ~250 referências `var(--…)` herdam a paleta
   sem edição individual. **Ainda hardcoded de propósito** (itens futuros): status (`#f05a50`… → item 4) e
   cartões teal/amber/coral. Toggle = item 7.
2. ✅ **feito 2026-07-08** — **Aposentar a tinta laranja legada** `rgba(232,97,26,…)` de hover/ativo →
   usar `--accent-tint`. As 8 ocorrências foram trocadas (grep = 0); fundos de hover/ativo agora usam o tint
   único do accent petróleo (perdem a variação de alpha, como o padrão manda).
3. **Unificar `login.html`** ao mesmo `:root` do app (hoje tem paleta própria e divergente — ver §5.6 do design-tokens).
4. **Tokenizar as cores de status** hoje hardcoded (`#f05a50`, `#d4a017`, `#c8a84b`) para `--st-*`.
5. **Corrigir `class="btn-primary"` sem a base `.btn`** (perde padding/fonte — ex.: "+ Novo Cliente").
6. **Unificar tipografia** — remover Epilogue, migrar para família sans única (Inter/system-ui) + **mono só em
   números** (valores monetários/numéricos em tabela).
7. **Toggle de tema claro/escuro**, persistido **por usuário** (não por preferência do SO).
8. (Já feito na navegação) hub de módulos agrupado por faixa — **implementado** com a faixa autoritativa de 5
   grupos (Vendas/Execução/Logística-Expedição/Pós-venda/Financeiro), mais fiel que a versão simplificada do doc.
9. (Já feito) **Credenciais e Tokens** dentro de Admin, visibilidade por capability (super_admin).

**Componentes a padronizar junto** (seção 4 do padrão v2): escala de botões (sm 28px / md 36px / lg 44px, altura
fixa, radius da escala, rótulo 1–3 palavras, largura trunca com `…` nunca estica); badge sem emoji (ícone outline
Tabler + texto); largura máx. de conteúdo 960px em Detalhe/Formulário; ação primária sempre no header (canto
superior direito), nunca solta no corpo.

> Estes itens **não** entram na frente de navegação atual — são a migração visual, a ser feita quando priorizada.
