# Mecanismo de Negociação — Nomenclatura Fechada e Refatoração do Cálculo

**Data:** 2026-06-22
**Status:** Em revisão (design)
**Escopo:** Reorganizar o cálculo do **modal de parâmetros / negociação** sobre uma
nomenclatura fechada, com cálculo **por ambiente** (depois agregado por orçamento), um
único dono por parâmetro e os valores derivados canônicos persistidos. **Próxima fase:**
validar o mecanismo na interface.

---

## 1. Problema

Hoje o cálculo da negociação vive espalhado e com ambiguidade (ver levantamento sobre o
LELEU oç1):

- **Parâmetros duplicados** em dois lugares que divergem: `projetos_meta.parametros_json`
  (projeto) **e** `orcamentos.margens` (orçamento). No LELEU dão resultados diferentes.
- **Cálculo agregado**, não por ambiente — o `desconto_individual_pct`
  (`orcamento_ambientes`) existe mas **não entra** na conta.
- **Valores que importam não são persistidos** (calculados em runtime em `mod_margens`),
  e o campo persistido `orcamentos.valor_liquido` guarda o **bruto** (25.481,49 no LELEU),
  não o líquido — é enganoso e sem consumidor real.
- O gross-up era **aditivo**; a regra correta é **divisivo** (recupera o valor após pagar
  as comissões percentuais).

## 2. Objetivo

Um **motor de negociação puro** (estilo `mod_margens`/`mod_tenancy`, sem I/O) que calcula
**por ambiente** e agrega por orçamento, alimentado por parâmetros com **um único dono por
nível** (Projeto / Orçamento / Ambiente), produzindo os valores canônicos
(`VBVO, CFO, VBNO, VAVO, Cust_Ad, Val_Liq, Desc_Tot, Markup, Val_Cont`) que ficam
**persistidos** no orçamento — prontos para o contrato, as aprovações financeiras e a
comissão (fases seguintes).

### Não-escopo (fases posteriores, que consomem este motor)
- Rubricas de provisionamento do item 6 (frete fábrica, comissões adm/medidor/PE, frete
  local, assistências, insumos, impostos por loja). Constroem **sobre** `Val_Liq`/`CFO`.
- Aprovação Financeira I e II (snapshot e revisão editável).
- Comissão de vendas (metas + limitador de markup).

---

## 3. Nomenclatura fechada (fonte da verdade)

> Convenção: siglas com `%` são **percentuais** (fração, ex. 0,10); demais são **valores
> em R$** ou texto. Esta seção é a referência canônica — o código usa exatamente estes nomes.

### 3.1 Variáveis do Projeto (modal de parâmetros — valem para todos os orçamentos)
| Variável | Sigla | Definição |
|---|---|---|
| Percentual de Comissão Arquiteto | `%Com_Arq` | percentual editável no modal |
| Percentual Programa Fidelidade | `%Pro_Fid` | percentual editável no modal |
| Comissão Arquiteto (valor) | `Com_Arq` | `Com_Arq = %Com_Arq × VAVA` |
| Programa Fidelidade (valor) | `Pro_Fid` | `Pro_Fid = %Pro_Fid × VAVA` |
| Custo Viagem | `Cust_Via` | valor editável no modal |
| Brinde | `Bri` | valor editável no modal |
| Toggle Custos Adicionais (master) | `Tog_Cadi` | true: repassa custos ao cliente (gross-up no VBNA); false: `VBNA = VBVA` (loja absorve) |
| Toggle Comissão Arquiteto | `Tog_Carq` | indica se o custo existe (sempre abate o líquido); repassa só se `Tog_Cadi` |
| Toggle Programa Fidelidade | `Tog_Fid` | idem |
| Toggle Custo Viagem | `Tog_Cvia` | idem (rateado proporcionalmente por `VBVA/VBVO`) |
| Toggle Brinde | `Tog_Bri` | idem (dividido **igualmente** por ambiente: `Bri/Num_Amb`) |
| Percentual Carga Tributária | `%Car_Trib` | percentual editável — **meramente informativo** na negociação |
| Custos Adicionais | `Cust_Ad` | `Cust_Ad = Com_Arq + Pro_Fid + Cust_Via + Bri` (cada parcela só se seu toggle = true) |

### 3.2 Variáveis do Orçamento
| Variável | Sigla | Definição |
|---|---|---|
| Percentual Desconto Orçamento | `%Desc_Orc` | desconto aplicado a todos os ambientes do orçamento |
| Forma de Pagamento | texto | À vista / Cartão / Venda Programada / Total Flex |
| Número de Parcelas | `Num_Parc` | conforme a forma de pagamento |
| Forma de Entrada | texto | Pix / Cheque / Boleto / Cartão |
| Valor / Data de Entrada | `Val_Ent` / Data | editável |
| Datas / Valor de cada Parcela | Data / `Val_Parc` | conforme parcelamento |
| Provisão de Impostos | `Prov_Imp` | informativo — **proposta:** `Prov_Imp = %Car_Trib × Val_Cont` (confirmar §10) |
| Valor Bruto de Venda Orçamento | `VBVO` | `Σ VBVA` |
| Custo Fábrica Orçamento | `CFO` | `Σ CFA` |
| Valor Bruto Negociado Orçamento | `VBNO` | `Σ VBNA` |
| Valor à Vista Orçamento | `VAVO` | `Σ VAVA` |
| Número de Ambientes | `Num_Amb` | ambientes presentes no orçamento |
| Custo Financeiro | `Cust_Fin` | da forma de pagamento/parcelamento (tabelas `mod_fin`); `Cust_Fin = Val_Cont − VAVO` |
| Valor de Contrato | `Val_Cont` | `Val_Cont = VAVO + Cust_Fin` |
| Valor Líquido de Contrato | `Val_Liq` | `Val_Liq = VAVO − Cust_Ad` |
| Desconto Total | `%Desc_Tot` | `%Desc_Tot = (VBVO − Val_Liq) / VBVO` |
| Markup | `Markup` | `Markup = Val_Liq / CFO` |

### 3.3 Variáveis do Ambiente
| Variável | Sigla | Definição |
|---|---|---|
| Percentual Desconto Ambiente | `%Desc_Amb` | desconto individual do ambiente |
| Valor Bruto de Venda Ambiente | `VBVA` | Σ valores de venda do XML do ambiente (`pool_ambientes.budget_total`) |
| Custo Fábrica Ambiente | `CFA` | Σ custos de fábrica c/ frete do XML (`pool_ambientes.order_total`) |
| Valor Bruto Negociado Ambiente | `VBNA` | fórmula condicional — §4 |
| Valor à Vista Ambiente | `VAVA` | `VAVA = VBNA × (1−%Desc_Orc) × (1−%Desc_Amb)` |

---

## 4. Modelo de cálculo (fórmula condicional fechada)

Por ambiente:

```
Se Tog_Cadi (repassa ao cliente):
   VBNA = VBVA / [ (Tog_Carq ? 1−%Com_Arq : 1) · (Tog_Fid ? 1−%Pro_Fid : 1) ]
        + (Tog_Cvia ? Cust_Via · (VBVA/VBVO) / [ (1−%Desc_Orc)·(1−%Desc_Amb) ] : 0)
        + (Tog_Bri  ? Bri / Num_Amb : 0)
Senão (absorve):
   VBNA = VBVA

VAVA = VBNA · (1−%Desc_Orc) · (1−%Desc_Amb)
```

Agregação por orçamento (ordem de cálculo):

```
VBVO = Σ VBVA          CFO = Σ CFA          Num_Amb = nº ambientes
(VBVO precisa existir antes do rateio de viagem em cada VBNA)
VBNO = Σ VBNA          VAVO = Σ VAVA

Com_Arq = (Tog_Carq ? %Com_Arq × VAVO : 0)     # comissão sobre o à vista
Pro_Fid = (Tog_Fid  ? %Pro_Fid × VAVO : 0)
Cust_Ad = Com_Arq + Pro_Fid + (Tog_Cvia ? Cust_Via : 0) + (Tog_Bri ? Bri : 0)

Val_Liq  = VAVO − Cust_Ad
%Desc_Tot = (VBVO − Val_Liq) / VBVO
Markup    = Val_Liq / CFO
Cust_Fin  = (custo da modalidade de pagamento via mod_fin)
Val_Cont  = VAVO + Cust_Fin
Prov_Imp  = %Car_Trib × Val_Cont        # informativo (proposta — confirmar)
```

**Semântica dos toggles (decidida):** o toggle individual diz "este custo existe?" (sempre
abate o líquido via `Cust_Ad`); o `Tog_Cadi` diz "repassa (gross-up no VBNA) ou absorve?".

**Dependência de ordem:** o rateio da viagem usa `VBVA/VBVO`, então `VBVO` é calculado
antes dos `VBNA`. Não há circularidade (o rateio usa valores de XML, não os negociados).

---

## 5. Modelo de dados (um dono por valor, sem duplicidade)

| Nível | Onde mora | Conteúdo |
|---|---|---|
| **Projeto** | `projetos_meta.parametros_json` (**único** dono) | `%Com_Arq, %Pro_Fid, Cust_Via, Bri, %Car_Trib` + os 5 toggles |
| **Orçamento (entrada)** | `orcamentos` (colunas) | `%Desc_Orc` (= `desconto_pct`), forma de pagamento (`forma_pagamento`/`negociacao_json`) |
| **Orçamento (derivados materializados)** | `orcamentos` (colunas novas) | `VBVO, CFO, VBNO, VAVO, Cust_Ad, Val_Liq, %Desc_Tot, Markup, Cust_Fin, Val_Cont, Prov_Imp` |
| **Ambiente (entrada)** | `pool_ambientes` (`budget_total`→`VBVA`, `order_total`→`CFA`) + `orcamento_ambientes.desconto_individual_pct` (→`%Desc_Amb`) | já existem |

**Decisões de migração:**
1. **Eliminar a duplicação:** os custos adicionais e toggles passam a viver **só** em
   `parametros_json` (projeto). O bloco equivalente em `orcamentos.margens` é **aposentado**
   (migração move/zera; `%Desc_Orc` continua em `orcamentos.desconto_pct`).
2. **Aposentar `orcamentos.valor_liquido`** (hoje guarda o bruto, sem consumidor real —
   verificado). Substituído pelos derivados canônicos.
3. **Materializar os derivados** em colunas do orçamento — recalculados a cada save da
   negociação. Isso permite que contrato/AF/comissão (fases seguintes) leiam um snapshot
   estável, em vez de recalcular.

---

## 6. Mapeamento ao código atual

| Hoje | Vira |
|---|---|
| `mod_margens.calcular_margens(valor_bruto, …)` (agregado, gross-up aditivo) | **novo** `mod_negociacao.py` puro, por ambiente, com a fórmula §4 |
| `mod_orcamento_params.py` (`PARAMETROS_DEFAULT`, `MARGENS_DEFAULT` duplicados) | apenas `PARAMETROS_DEFAULT` (projeto); defaults de orçamento reduzidos a `%Desc_Orc` |
| Modal de Parâmetros `static/index.html` (`#modal-params`, `mpAtualizarApoio` ~5324) | consome o novo motor; exibe `VBVO/VBNO/VAVO/Cust_Ad/Val_Liq/%Desc_Tot/Markup` |
| Limite de desconto hardcoded 35% (`_LIMITE_DESC_TOTAL`) | passa a usar `%Desc_Tot` real (o cálculo correto §4) |
| `GET/POST /api/projetos/<n>/parametros`, `POST /api/orcamentos/<id>/margens` | gravam params no projeto; recalculam e materializam derivados no orçamento |

## 7. Sugestão de implementação (incremental, testável)

1. **`mod_negociacao.py` (puro):** `calcular_orcamento(ambientes, params, desc_orc) → dict`
   com todas as siglas. Sem I/O. **É onde mora toda a aritmética** — testes unitários
   exaustivos (incl. LELEU §8 e os 4 toggles em ON/OFF). Substitui `calcular_margens`.
2. **Migração de schema/dados:** colunas derivadas em `orcamentos`; mover params para o
   projeto; aposentar `valor_liquido`/bloco duplicado em `margens`.
3. **Endpoints:** ao salvar negociação, chamar `mod_negociacao` e gravar os derivados.
   `Cust_Fin` vem das tabelas `mod_fin` já existentes (modalidade de pagamento).
4. **UI (fase de validação):** o modal de parâmetros exibe os valores canônicos por
   orçamento, refletindo os ambientes marcados — para conferência visual contra casos
   conhecidos antes de seguir para as rubricas/AF.

---

## 8. Caso de regressão — LELEU Orçamento 1 (id=19)

Entrada: 2 ambientes — Área Gourmet (`VBVA` 22.830,99 / `CFA` 22.830,99) e Banheiro Social
(`VBVA` 2.650,50 / `CFA` 953,40). Projeto: `%Com_Arq` 10%, `%Pro_Fid` 2%, `Cust_Via` 2.000,
`Bri` 500, todos os toggles ON. Orçamento: `%Desc_Orc` 20%, `%Desc_Amb` 0.

| Saída | Valor esperado |
|---|---|
| Área Gourmet — `VBNA` / `VAVA` | 28.375,43 / 22.700,35 |
| Banheiro Social — `VBNA` / `VAVA` | 3.515,14 / 2.812,11 |
| `VBVO` / `CFO` | 25.481,49 / 23.784,39 |
| `VBNO` / `VAVO` | 31.890,58 / 25.512,46 |
| `Cust_Ad` (Com_Arq 2.551,25 + Pro_Fid 510,25 + Cust_Via 2.000 + Bri 500) | 5.561,50 |
| `Val_Liq` | 19.950,97 |
| `%Desc_Tot` | 21,70% |
| `Markup` | 0,839 |
| `Cust_Fin` / `Val_Cont` | 1.413,44 / **26.925,90** (= `valor_total` armazenado ✅) |

Este caso vira o teste unitário-âncora do `mod_negociacao`.

## 9. Testes
- **Unitário (puro, `mod_negociacao`):** caso LELEU §8; matriz de toggles (cada um ON/OFF,
  `Tog_Cadi` ON/OFF — repassa vs absorve); `%Desc_Amb` por ambiente; orçamento de 1 e de N
  ambientes; rateio da viagem; ordem de cálculo (VBVO antes dos VBNA).
- **E2E:** salvar negociação grava os derivados corretos; troca de params do projeto
  reflete em todos os orçamentos; remover/incluir ambiente recalcula VBVO/CFO.
- **Validação manual (fase seguinte):** modal de parâmetros exibindo os canônicos.

## 10. Decisões pendentes (confirmar na revisão)
1. **Base do `Prov_Imp`:** proposto `%Car_Trib × Val_Cont` (impostos sobre o contrato).
   Confirmar (ou `× VAVO`?).
2. **Validação de dado de XML:** quando `CFA == VBVA` (sem margem de fábrica — caso da Área
   Gourmet, que produz `Markup` 0,839), o sistema deve **sinalizar** o orçamento como
   "custo de fábrica suspeito". Confirmar como tratar (alerta visual? bloqueio?).
3. **`Cust_Fin`:** confirmar que a integração reusa as tabelas `mod_fin` existentes
   (modalidade de pagamento) sem recalcular nada novo nesta fase.

---

## 11. Próxima fase
Validar o mecanismo **na interface** (modal de parâmetros) — exibir os valores canônicos
por orçamento e conferir contra casos reais — antes de construir as rubricas do item 6, as
aprovações financeiras e a comissão de vendas, que consomem `Val_Liq`, `CFO` e `Markup`.
