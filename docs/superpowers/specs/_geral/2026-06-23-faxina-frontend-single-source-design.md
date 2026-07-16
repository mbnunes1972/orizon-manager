# Faxina Fase 1 — Frontend Single-Source (motor é a única fonte) — Design

**Data:** 2026-06-23
**Status:** Em revisão (design)
**Base:** `docs/superpowers/specs/negociacao/2026-06-23-cutover-negociacao-design.md` (cutover Fase B) e
`docs/superpowers/specs/negociacao/2026-06-22-mecanismo-negociacao-design.md` (motor).
**Branch:** `feat/cutover-negociacao`. **Rollback:** tag `pre-refator-negociacao`.

## 1. Problema

Mesmo com o motor (`mod_negociacao` + `mod_fin`) validado e o backend do cutover sólido (288
testes), a UI ainda carrega um **cálculo legado** paralelo que disputa os mesmos campos de
display. Há **fonte dupla**: dois inputs de desconto (`neg-desconto` × `mp-desconto`) e dois
leitores de parâmetros (`lerMargensModal` × `lerMargensNegociacao`), mantidos em sincronia por
código frágil (`negSyncModal`/`negSyncSidebar`). A consequência foi uma sequência de bugs de
divergência (ex.: "valor bruto" diferente entre a tela de negociação e o modal de parâmetros) —
cada correção pontual revelava outra. A causa-raiz é **arquitetural**, não um bug isolado.

## 2. Objetivo

O **backend (motor) é a ÚNICA fonte de verdade** de todos os números de negociação. O frontend
vira **visor + editor**: os inputs escrevem no backend; as telas exibem **apenas** a saída do
motor. Eliminar todo cálculo/estado de parâmetros do frontend e toda sincronização DOM↔DOM.

### Não-escopo (Fase 2 — spec/plano próprios)
- Apagar colunas/JSON legados (`custo_financeiro_pct` do `mod_margens`, bloco `margens`
  duplicado, semântica legada de `valor_liquido`, etc.) e reorganizar tabelas. Esta fase é
  **não-destrutiva** em schema: só muda frontend + acrescenta 2 campos ao retorno do motor.

### Decisões confirmadas
- **Arquitetura "backend é a fonte" (Opção 1):** inputs → auto-save (debounced) → backend
  recalcula pelo motor → a **resposta do save traz o breakdown** → frontend exibe. Sem override
  de params vindo do frontend.
- **Desconto: um input só** (`neg-desconto` na tela de negociação + descontos por ambiente). No
  modal o desconto é **read-only** (mostra o valor vindo da negociação, só para o apoio calcular).
- **`mod_fin` reusado como está**; params do projeto vêm sempre do `parametros_json`.

---

## 3. §1 — Backend: motor devolve tudo; leitura só dos salvos

### 3.1 Motor devolve viagem e brinde
`mod_negociacao.calcular_orcamento(...)` passa a incluir no dict de retorno:
- `Cust_Via` — viagem total considerada (soma de `num_via` dos ambientes).
- `Bri` — brinde total considerado (soma de `num_bri` dos ambientes).

Assim o painel de apoio tem 100% dos números do motor (a cadeia
`VAVO − Com_Arq − Pro_Fid − Cust_Via − Bri = Val_Liq` fecha com valores do motor).

### 3.2 Breakdown lê só os salvos (sem overrides)
`_negociacao_breakdown(orc, db)` deixa de aceitar `params`/`desc_orc`/`descontos_amb`: lê sempre
do banco — `Projeto.parametros_json`, `orc.desconto_pct`, `OrcamentoAmbiente.desconto_individual_pct`.
`_recalcular_orcamento` continua usando-o (mesmo cálculo, persistindo).

### 3.3 Endpoints de save retornam o breakdown
Todo endpoint que altera um **insumo de cálculo** recalcula pelo motor e devolve o **breakdown
completo** na resposta. Insumos: desconto global (`orc.desconto_pct`), desconto por ambiente,
parâmetros do projeto (`parametros_json`). Forma de pagamento (já existente) idem.

**Shape do breakdown na resposta** (`"sombra"` + extras), com as **siglas do motor em
maiúsculas** — IDÊNTICO ao que o preview devolve, para o frontend consumir os dois de forma
uniforme (`_aplicarPreviewNaTela` lê `s.VBNO`, `s.VAVO`, ...):
`{ VBVO, CFO, VBNO, VAVO, Com_Arq, Pro_Fid, Cust_Via, Bri, Cust_Ad, Val_Liq, Desc_Tot, Markup,
   Cust_Fin, Val_Cont, Prov_Imp, ambientes:[{id, VBVA, CFA, VBNA, VAVA}] }`.
Os saves devolvem o dict do motor vindo de `_negociacao_breakdown` (não o `_sombra_dict` legado,
de chaves minúsculas). Convergir o `/margens` para esse mesmo shape.

### 3.4 Preview endpoint
`POST /api/orcamentos/<id>/negociacao-preview` permanece para **leitura pura** (carga inicial),
agora **sem corpo** (lê só os salvos). Devolve o mesmo breakdown.

## 4. §2 — Frontend: um único escritor

`_aplicarPreviewNaTela(s)` é a **única** função que escreve os campos de display, a partir do
breakdown `s`:
- **Apoio (modal):** `mp-a-bruto`←VBNO, `mp-a-desc`←VBNO−VAVO, `mp-a-avista`←VAVO,
  `mp-a-arq`←Com_Arq, `mp-a-fid`←Pro_Fid, `mp-a-viagem`←Cust_Via, `mp-a-brinde`←Bri,
  `mp-a-liq`←Val_Liq, `mp-a-margem`←Desc_Tot, impostos/retenção←base Prov_Imp/VAVO.
- **Tela de negociação:** `neg-subtotal`←VBNO, `neg-desc-val`←VBNO−VAVO, `neg-avista`←VAVO,
  `neg-total`←Val_Cont.
- **Células por ambiente:** `VAVA` casado pelo `id` do pool (`data-ep07-id`).

## 5. §3 — Faxina das funções legadas

**Apagar (cálculo/estado/sync legado):**
`lerMargensModal`, a parte legada de `lerMargensNegociacao`, `negAtualizarDescontoEfetivo`,
`calcularValorBrutoCliente`, `mpRecalcularEstruturalModal`, `_ep07DistribuirFinanciado`,
`negSyncModal`, `negSyncSidebar`, e a **parte de cálculo** de `mpAtualizarApoio` /
`renderTabelaNeg` / `executarCalculo`.

**Manter (estrutura, sem cálculo de valor):**
`renderTabelaNeg` constrói as **linhas** da tabela (inputs de desconto por ambiente, com
`data-ep07-id`) — mas **não calcula** os valores das células; o motor os preenche via
`_aplicarPreviewNaTela`.

**Verificar antes de apagar:** se o **path legado não-EP07** (`renderTabelaNeg`/`executarCalculo`
para projetos antigos sem orçamento) ainda é exercido. Se não for, entra na faxina; se for,
preservar isolado.

## 6. §4 — Desconto (input único)

- **Editor único:** `neg-desconto` (global) + inputs de desconto por ambiente, na tela de
  negociação. `oninput` → valida limite → **auto-save** (debounced) do `orc.desconto_pct` /
  desconto-por-ambiente → a resposta traz o breakdown → `_aplicarPreviewNaTela` exibe.
- **No modal:** o campo de desconto fica **read-only** (exibe o valor atual vindo da negociação,
  para o apoio refletir o cálculo). Remover `mp-desconto` como editor e remover `negSyncModal`/
  `negSyncSidebar`.
- **Limite 35%:** checado contra o `Desc_Tot` do breakdown do motor (já implementado).

## 7. §5 — Fluxo edição→exibição

1. Usuário edita um insumo (desconto na tela; parâmetro no modal).
2. Handler valida e dispara **auto-save debounced** ao endpoint correspondente.
3. Backend recalcula pelo motor e **retorna o breakdown**.
4. `_aplicarPreviewNaTela(resposta.sombra)` atualiza todos os campos.

Carga inicial / abertura de tela: chama o preview (leitura) e aplica.
Params do modal: edição **auto-salva** (debounced); o botão "Salvar" do modal vira salvar-e-fechar
(idempotente). Sem estado de rascunho no frontend.

## 8. §6 — Segurança e testes

- **Não-destrutivo:** nenhuma coluna/JSON removida nesta fase (Fase 2 cuida disso).
- **Golden-master:** os números não mudam (mesmo motor) — só a fonte de exibição. Comparar
  `valor_total`/`valor_liquido`/breakdown antes×depois para garantir estabilidade.
- **Testes backend:** manter os 288 verdes; E2E novos: (a) `_negociacao_breakdown` lê só dos
  salvos (sem overrides); (b) cada endpoint de save devolve o breakdown com `Cust_Via`/`Bri`;
  (c) o motor inclui `Cust_Via`/`Bri` e fecham a cadeia.
- **Frontend:** sem harness JS → validação manual no browser (roteiro: editar desconto na tela e
  param no modal; conferir que apoio e tela batem e mudam juntos; cadeia do apoio fecha).
- **Rollback:** branch atual; tag `pre-refator-negociacao`.

## 9. Arquivos afetados

- `mod_negociacao.py` — incluir `Cust_Via`/`Bri` no retorno.
- `main.py` — `_negociacao_breakdown` sem overrides; endpoints de save (desconto global, desconto
  por ambiente, parâmetros) recalculam e retornam o breakdown; preview sem corpo.
- `static/index.html` — `_aplicarPreviewNaTela` único escritor (incl. viagem/brinde); apagar as
  funções de cálculo/sync legadas; desconto único (modal read-only); auto-save dispara exibição.
- `tests/` — E2E dos saves retornando breakdown e do motor com `Cust_Via`/`Bri`.
- docs — esta spec.
