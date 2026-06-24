# Tela de Negociação — Fonte Única do Total e Colunas (Fase 2) — Design

**Data:** 2026-06-24
**Status:** ✅ Implementado e validado no navegador (2026-06-24).
**Base:** faxina single-source (cutover/Fase 1). **Branch:** `feat/fase2-autosave-negociacao`. **Rollback:** tag `pre-refator-negociacao`.

> **Nota de implementação (validação):** a validação no navegador revelou um bug de **persistência
> do plano de pagamento** não previsto neste design: ao dar *hard refresh*, o orçamento ativo
> **perdia o parcelamento** (mantinha a modalidade). Causa-raiz (confirmada por log): `carregarMargensSalvas`
> é re-disparado na navegação p/ a página 2 (e em add-ambiente/save-params) **sem `_negociacaoPendente`**;
> `carregarModalidades → onPagamentoChange(default)` zerava `neg-parcelas` e o auto-save salvava
> `n_parcelas=1`. Fix single-point: quando há orçamento ativo e nenhuma restauração pendente,
> `carregarMargensSalvas` captura a negociação atual da tela e a re-restaura após o reset. Também
> corrigidos: data da 1ª parcela do Aymoré (`ay-data-primeira`) na captura, e supressão do auto-save
> durante a carga (`_carregandoOrcamento`). Ver DEV_LOG Sessão 29.

## 1. Problema

Três sintomas na tabela por ambiente da tela de negociação, todos com a mesma raiz —
**múltiplas fontes para o mesmo número** (o vício a corrigir):

1. **Desconto por ambiente aparece zerado na 1ª entrada** (aparece na re-entrada). O input lê de
   `_descIndividual`, populado durante a carga com timing frágil.
2. **Falta a coluna "à vista" por ambiente** (hoje só há a coluna com custo financeiro).
3. **O Total (valor de contrato) é intermitente** — `neg-total`/`neg-total-final` têm **dois
   escritores que correm**: o motor (`_aplicarPreviewNaTela` → `Val_Cont`, ~250ms) e o fluxo de
   pagamento (`_ep07DistribuirFinanciado` → `total_cliente`, imediato). Quem escreve por último vence.

Fato confirmado: `Val_Cont = VAVO + Cust_Fin = total_cliente` — **o mesmo número** vindo do motor
(backend) e do `mod_fin` (frontend). Duplicidade.

## 2. Objetivo (Opção B — limpa)

O **motor (backend) é a fonte única** de todos os números da tabela, **inclusive o financiado**.
O `mod_fin` continua **calculando** o custo financeiro, mas o resultado entra pelo `total_cliente`
**salvo** → `Val_Cont`. O fluxo de pagamento deixa de escrever Total/células; fica só com o **plano
de parcelas**.

### Não-escopo (faxina futura)
- Eliminar o armazenamento duplicado `total_cliente` (em `forma_pagamento`) vs `Val_Cont`/`val_cont`
  (coluna): hoje convivem porque `total_cliente` é o input do `mod_fin`. Avaliar depois.
- Item 3 da Fase 2 (schema: `custo_financeiro_pct`, `margens` duplicado, `valor_liquido` legado).

---

## 3. §1 — Desconto por ambiente (display robusto)

`renderTabelaNeg` (EP-07) passa a ler o desconto do input **direto do dado do ambiente** que já
está iterando (`pa.desconto_individual_pct`, que vem no fetch `/orcamentos/<id>/ambientes`), usando
`_descIndividual['ep07_'+pa.id]` apenas como **override de edição em andamento**:
```
const k = 'ep07_'+pa.id;
const disc_i = (k in _descIndividual) ? _descIndividual[k] : (pa.desconto_individual_pct || 0);
```
Sem dependência de timing de população → mostra o desconto salvo já na 1ª entrada.

## 4. §2 — Duas colunas por ambiente (ambas do motor)

A tabela passa a ter **duas colunas de valor** por ambiente:
- **À vista:** `VAVA` (do motor, por ambiente).
- **Com custo financeiro:** `VAVA × Val_Cont/VAVO` (derivado do motor) — soma exatamente `Val_Cont`.

Ambas escritas por **`_aplicarPreviewNaTela`** (único escritor), casadas por `data-ep07-id`:
- `renderTabelaNeg` monta as duas `<td>` por linha (com `data-ep07-id` + um marcador de qual coluna,
  ex.: `data-col="avista"`/`data-col="fin"`), com placeholder.
- `_aplicarPreviewNaTela` preenche, por ambiente: avista ← `a.VAVA`; fin ← `a.VAVA × (Val_Cont/VAVO)`
  (guardando `VAVO`/`Val_Cont` do breakdown; se `VAVO=0`, fin = avista).

`_ep07DistribuirFinanciado` (o distribuidor legado das células/Total) é **aposentado** — o motor
passa a prover as duas colunas.

## 5. §3 — Total único (motor) + auto-save do pagamento

- **`neg-total`/`neg-total-final`** passam a ser escritos **só** por `_aplicarPreviewNaTela` =
  `Val_Cont` (o total de contrato financiado, do motor). O fluxo de pagamento **para de escrever**
  esses campos (remover as escritas em `_ep07DistribuirFinanciado` e afins).
- **Auto-save do pagamento (torna o `Val_Cont` vivo):** quando o plano de pagamento muda
  (`atualizarAymore`/`atualizarCartao`/`atualizarVP`/`atualizarTF` produzem `total_cliente`),
  dispara um **auto-save de `forma_pagamento`** (debounced) reusando `salvarValorNegociado`; a
  resposta traz o breakdown (com o novo `Val_Cont`) → `aplicarBreakdownResposta` exibe. Assim o
  Total e a coluna financiada refletem a modalidade atual, **sem corrida** (um escritor).
- **À vista (sem financiamento):** com modalidade "à vista" / sem custo financeiro, `total_cliente`
  = `VAVO` → `Val_Cont = VAVO` → Total = à vista. Coberto naturalmente.
- `neg-avista` (total à vista = `VAVO`) segue do motor (já é).

## 6. §4 — Testes

- **Backend:** os endpoints/motor já cobertos (Val_Cont, distribuição). Acrescentar, se faltar, um
  E2E de que salvar `forma_pagamento` com `total_cliente` faz `Val_Cont` refletir (já há base).
- **Frontend (manual, sem harness JS):** (a) desconto por ambiente aparece na 1ª entrada;
  (b) duas colunas (à vista × financiada) por ambiente, somando ao Total; (c) trocar a modalidade
  atualiza o Total e a coluna financiada de forma estável (sem "às vezes certo, às vezes errado").
- **Re-validação visual** pelo usuário (mudança de exibição/auto-save).

## 7. Arquivos afetados

- `static/index.html` — `renderTabelaNeg` (desconto do dado do ambiente; duas `<td>`);
  `_aplicarPreviewNaTela` (preenche as duas colunas; Total = Val_Cont; deriva a coluna financiada);
  remover escritas de Total/células de `_ep07DistribuirFinanciado` (aposentar); auto-save do
  pagamento nos `atualizar*` (debounced → `salvarValorNegociado` → `aplicarBreakdownResposta`).
- (Backend já provê `VAVA`/`Val_Cont`/`VAVO` no breakdown — sem mudança prevista; confirmar.)
- docs — esta spec.
