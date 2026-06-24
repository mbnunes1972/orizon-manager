# Distribuição de Brinde e Custo Viagem (Fase 2) — Design

**Data:** 2026-06-23
**Status:** Em revisão (design)
**Base:** `docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md` (motor).
**Branch:** `feat/fase2-autosave-negociacao` (continuação da Fase 2). **Rollback:** tag `pre-refator-negociacao`.

## 1. Problema

Brinde e custo viagem são **recuperação de margem** (brinde do cliente + montagem fora de
sede). Eles devem se **distribuir pelos ambientes do projeto**, de modo que cada orçamento
recupere **a sua parte** — sem discrepância entre o somatório dos ambientes e o valor do
projeto.

Hoje (pós-faxina, com o parâmetro guardando o TOTAL): o motor dá o valor **cheio** ao orçamento,
independentemente de ele ser um subconjunto do projeto:
- `num_bri = bri / num_amb` (com `bri` = total) → somado nos `num_amb` ambientes do orçamento = **total cheio**.
- `num_via = cust_via × vbva / VBVO_orçamento` → somado = **cust_via cheio**.

Intenção correta (confirmada): projeto com 7 ambientes, cliente fecha 3 → o orçamento recupera
**3/7 do brinde** (distribuição **igual** por ambiente) e a viagem **proporcional ao valor** dos
ambientes contratados (`total_viagem × VBVO_orçamento / VBVO_projeto`).

## 2. Objetivo

Distribuir brinde e viagem por **todos os ambientes do pool do projeto**; cada orçamento
recupera a fração correspondente aos seus ambientes.

### Denominador (confirmado)
"Ambientes do projeto" = **todos os `PoolAmbiente` do projeto** (o pool), estejam ou não em
algum orçamento.

### Decisões confirmadas
- Parâmetro guarda o **TOTAL** (já é assim pós-faxina; o save manda o input cru do modal). **Sem
  mudança de semântica nem de schema.**
- Distribuição: **brinde igual** por ambiente; **viagem proporcional** ao `VBVA` do ambiente.
- **Fase 2-passo 2 (futuro, NÃO neste spec):** seletor de quais ambientes recebem cada item
  (default = todos do pool), com persistência em `parametros_json` (`brinde_ambientes`,
  `viagem_ambientes`) e a regra "conjunto efetivo = seleção ∩ pool atual; vazio → todos". O
  design abaixo é a **generalização com o conjunto = todos do pool** (o seletor só liga a seleção).

---

## 3. §1 — Motor (`mod_negociacao`)

Assinatura: `calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0, n_total_proj=None, vbvo_proj=None)`.

Por ambiente do orçamento:
- **brinde:** `num_bri = (bri / n_total_proj) if (tog_bri and n_total_proj) else <fallback>`.
- **viagem:** `num_via = (cust_via × vbva / vbvo_proj) if (tog_cvia and vbvo_proj) else <fallback>`.
- **Fallback** (args `None` — compatibilidade com chamadas/testes que não passam contexto):
  comportamento atual — `num_bri = bri / num_amb` e `num_via = cust_via × vbva / VBVO_orçamento`.

Resultado para um orçamento (subconjunto de `k` ambientes, de `n_total_proj` do projeto):
- brinde recuperado = `k × (total_brinde / n_total_proj)`.
- viagem recuperada = `total_viagem × (VBVO_orçamento / vbvo_proj)`.

As demais fórmulas (blindagem do desconto, comissão em cadeia, `Cust_Ad`, `Val_Liq`, etc.)
**não mudam** — só a origem de `num_bri`/`num_via`. O retorno (`Cust_Via`, `Bri`, `Cust_Ad`, …)
segue igual; `Cust_Via`/`Bri` no retorno passam a refletir o total **recuperado pelo orçamento**
(a fração), não o total do projeto.

## 4. §2 — Backend (`_negociacao_breakdown`)

Antes de chamar o motor, calcular o **contexto do projeto** a partir do pool:
- `n_total_proj` = nº de `PoolAmbiente` do projeto (`projeto_id` = `orc.projeto_id`).
- `vbvo_proj` = Σ `budget_total` dos `PoolAmbiente` do projeto.

Passar `n_total_proj`/`vbvo_proj` ao motor — **tanto no preview quanto no `_recalcular_orcamento`**
(o helper é compartilhado, então é um ponto só). Se o projeto não tiver pool (caso degenerado),
`n_total_proj`/`vbvo_proj` ficam `None` → motor cai no fallback (não quebra).

## 5. §3 — Frontend

Sem mudança de cálculo (o motor é a fonte). O modal já manda o **total** de brinde/viagem. O
painel de apoio (`mp-a-viagem`/`mp-a-brinde`) e a tela exibem `Cust_Via`/`Bri` do motor (a fração
recuperada pelo orçamento) — já vêm do breakdown. Confirmar que o texto/intenção do modal deixa
claro que o valor é o **total do projeto** (a ser distribuído).

## 6. §4 — Dados existentes

- Param já é o total (pós-faxina) → **sem migração de schema**.
- Projetos cujo brinde foi salvo **pré-faxina** (valor pré-dividido) ficam com número antigo →
  **re-entrar** o total no modal (são poucos) ou o **reset de teste** recalcula. Sinalizar na
  implementação (não há migração automática segura, pois o `n_total_proj` de então pode diferir).

## 7. §5 — Testes / re-validação

- `tests/test_negociacao.py`:
  - Atualizar a **âncora LELEU** se ela tiver brinde/viagem ativos (passar `n_total_proj`/`vbvo_proj`
    = os do próprio orçamento, p/ manter o número se LELEU = projeto inteiro; ou ajustar o esperado).
  - **Novo teste 3-de-7:** projeto com 7 ambientes (pool), orçamento com 3 → brinde recuperado =
    `3/7 × total_brinde`; viagem recuperada = `total_viagem × VBVO_3 / VBVO_7`.
  - Teste do **fallback** (sem `n_total_proj` → comportamento atual) para não quebrar chamadas legadas.
- **E2E:** o preview/breakdown de um orçamento subconjunto reflete a fração (com pool semeado).
- **Re-validação visual** pelo usuário (é mudança de cálculo).

## 8. Arquivos afetados

- `mod_negociacao.py` — args `n_total_proj`/`vbvo_proj`; `num_bri`/`num_via` com fallback.
- `main.py` — `_negociacao_breakdown` calcula `n_total_proj`/`vbvo_proj` do pool e passa ao motor.
- `tests/test_negociacao.py` — âncora + teste 3-de-7 + fallback; possivelmente `tests/test_cutover_e2e.py`.
- docs — esta spec (e a base spec §4, nota sobre a distribuição).
