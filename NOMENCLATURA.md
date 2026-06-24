# NOMENCLATURA — siglas fechadas da negociação

> **Mecanismo para falarmos sempre a mesma língua.** Este é o **glossário canônico**. O
> **motor `mod_negociacao.calcular_orcamento` é a fonte única** de todos os números da negociação;
> toda exibição sai dele (via `_negociacao_breakdown` → preview/save). **Novos cálculos e telas
> devem usar EXATAMENTE estas siglas** — não inventar `saldo_*`, `margem_*`, etc. Ao acrescentar um
> número, ele deve **vir do motor** (ou de uma função pura testada que o motor exponha), nunca
> recalculado em paralelo no frontend.
>
> Base formal: `docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md` (§3/§4).

## 1. Fluxo (quem é dono do quê)

```
Entradas salvas (banco)  →  MOTOR (mod_negociacao)  →  siglas  →  exibição (frontend só mostra)
  parametros_json              calcular_orcamento         (abaixo)     _aplicarPreviewNaTela
  desconto_pct (orç)           _negociacao_breakdown
  desconto_individual_pct
  forma_pagamento (total_cliente)
```

## 2. Por AMBIENTE

| Sigla | Nome | Definição |
|-------|------|-----------|
| `VBVA` | Valor Bruto de Venda do Ambiente | do XML/Promob |
| `CFA`  | Custo de Fábrica do Ambiente | do XML/Omie |
| `VBNA` | Valor Bruto **Negociado** do Ambiente | com gross-up dos custos quando repassados (`Tog_Cadi`); senão `VBNA = VBVA` |
| `VAVA` | Valor **À Vista** do Ambiente | `VBNA × (1−%Desc_Orc) × (1−%Desc_Amb)` |
| `Com_Arq` (amb) | Comissão do Arquiteto do ambiente | `%Com_Arq × [VAVA − Pro_Fid_amb − base_custos]` (em cadeia: arq não ganha sobre a fidelidade) |
| `Pro_Fid` (amb) | Programa Fidelidade do ambiente | `%Pro_Fid × [VAVA − base_custos]` |
| `Cust_Via` (amb) | Custo Viagem rateado do ambiente | `Cust_Via × VBVA/vbvo_proj` (proporcional ao valor) |
| `Bri` (amb) | Brinde do ambiente | `Brinde / n_total_proj` (igual por ambiente) |
| `Val_Liq` (amb) | Valor Líquido do ambiente | `VAVA − Com_Arq − Pro_Fid − Cust_Via − Bri` |

`base_custos = (Tog_Cvia ? Cust_Via_amb : 0) + (Tog_Bri ? Bri_amb : 0)`.

## 3. Por ORÇAMENTO (Σ dos ambientes)

| Sigla | Nome | Definição |
|-------|------|-----------|
| `VBVO` | Valor Bruto de Venda do Orçamento | `Σ VBVA` |
| `CFO`  | Custo de Fábrica do Orçamento | `Σ CFA` |
| `VBNO` | Valor Bruto Negociado do Orçamento | `Σ VBNA` |
| `VAVO` | Valor à Vista do Orçamento | `Σ VAVA` |
| `Com_Arq` | Comissão do Arquiteto (orçamento) | `Σ Com_Arq_amb` |
| `Pro_Fid` | Programa Fidelidade (orçamento) | `Σ Pro_Fid_amb` |
| `Cust_Via` | Custo Viagem recuperado pelo orçamento | total rateado (fração do projeto) |
| `Bri` | Brinde recuperado pelo orçamento | total igual/ambiente (fração do projeto) |
| `Cust_Ad` | Custos Adicionais | `Com_Arq + Pro_Fid + Cust_Via + Bri` (cada parcela só se seu toggle = true) |
| `Val_Liq` | Valor Líquido (o que a loja leva) | `VAVO − Cust_Ad` |
| `Desc_Tot` | Desconto Total efetivo (%) | `(VBVO − Val_Liq) / VBVO` |
| `Markup` | Markup | `Val_Liq / CFO` |
| `Cust_Fin` | Custo Financeiro | `Val_Cont − VAVO` (da forma de pagamento, `mod_fin`) |
| `Val_Cont` | Valor de Contrato | `VAVO + Cust_Fin` (= `total_cliente` da forma de pagamento) |
| `Prov_Imp` | Provisão de Impostos (informativo) | `%Car_Trib × Val_Cont` |
| `Num_Amb` | nº de ambientes do orçamento | — |

## 4. Contexto do PROJETO (pool)

| Termo | Definição |
|-------|-----------|
| `n_total_proj` | nº de `PoolAmbiente` do projeto (denominador do brinde, distribuição igual) |
| `vbvo_proj` | `Σ budget_total` do pool (denominador da viagem, distribuição proporcional) |

Brinde e viagem são **totais do projeto** distribuídos pelo pool; um orçamento (subconjunto)
recupera a sua fração.

## 5. Parâmetros (entradas) e onde ficam salvos

| Parâmetro | Toggle (spec) | Armazenamento (fonte de verdade) |
|-----------|---------------|----------------------------------|
| `incluir_custos` | `Tog_Cadi` | `Projeto.parametros_json` |
| `comissao_arq_ativa` / `comissao_arq_pct` | `Tog_Carq` / `%Com_Arq` | `Projeto.parametros_json` |
| `fidelidade_ativa` / `fidelidade_pct` | `Tog_Fid` / `%Pro_Fid` | `Projeto.parametros_json` |
| `fora_da_sede` / `custo_viagem` | `Tog_Cvia` | `Projeto.parametros_json` (custo_viagem = TOTAL do projeto) |
| `brinde_ativo` / `brinde` | `Tog_Bri` | `Projeto.parametros_json` (brinde = TOTAL do projeto) |
| `carga_trib` | `%Car_Trib` | `Projeto.parametros_json` |
| `desconto_pct` | — | `Orcamento.desconto_pct` (por orçamento) |
| `desconto_individual_pct` | — | `OrcamentoAmbiente.desconto_individual_pct` (por ambiente) |
| forma de pagamento (modalidade, parcelas, datas, `total_cliente`) | — | `Orcamento.forma_pagamento` + `negociacao_json` |

**Saídas autoritativas gravadas** (pelo motor, em `_recalcular_orcamento`):
`Orcamento.valor_total = Val_Cont` e `Orcamento.valor_liquido = Val_Liq`.

## 6. Nomenclatura REMOVIDA na faxina — **não reusar**

O cálculo legado de margem (`mod_margens.calcular_margens`) e a discriminação por ambiente foram
removidos. **Não** voltar a usar estes nomes (eles competiam com as siglas e geravam confusão):

- `saldo_apos_desconto`, `saldo_apos_financeiro`, `saldo_apos_viagem`, `saldo_apos_brinde`,
  `saldo_apos_arq`, `saldo_apos_fidelidade`
- `valor_liquido_avista`, `acrescimo_financeiro`, `custo_financeiro`, `total_deducoes`, `valor_final`
- `margem_interna`
- `custo_financeiro_pct` **como parâmetro de margem** (o custo financeiro hoje é `Cust_Fin`, derivado da forma de pagamento)
- endpoint `POST /calcular_margens` (removido)
- painel "discriminação por ambiente" (removido; se refeito no futuro, usar o breakdown do motor)

**Pendente (passo futuro, irreversível — exige backup + aprovação):** remover a coluna duplicada
`Orcamento.margens` (legada; o motor lê `parametros_json` + `desconto_pct`, não `orc.margens`).

## 7. Mantido (não confundir com o legado)

- `mod_margens._normalizar_faixas` / `_pmt` — **vivos**, normalizam as faixas de parcelamento
  (servem o endpoint de faixas; o nome do módulo permanece por ora).
- `mod_fin` — cálculo do parcelamento / `total_cliente` (origem do `Cust_Fin`).
