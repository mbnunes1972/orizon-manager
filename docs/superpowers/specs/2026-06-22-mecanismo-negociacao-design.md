# Mecanismo de Negociação — Nomenclatura Fechada e Refatoração do Cálculo

**Data:** 2026-06-22
**Status:** Aprovado — pronto para plano de implementação
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
| Custo Viagem | `Cust_Via` | valor editável no modal |
| Brinde | `Bri` | valor editável no modal |
| Toggle Custos Adicionais (master) | `Tog_Cadi` | true: repassa custos ao cliente (gross-up no VBNA); false: `VBNA = VBVA` (loja absorve) |
| Toggle Comissão Arquiteto | `Tog_Carq` | indica se o custo existe (sempre abate o líquido); repassa só se `Tog_Cadi` |
| Toggle Programa Fidelidade | `Tog_Fid` | idem |
| Toggle Custo Viagem | `Tog_Cvia` | idem (rateado proporcionalmente por `VBVA/VBVO`) |
| Toggle Brinde | `Tog_Bri` | idem (dividido **igualmente** por ambiente: `Bri/Num_Amb`) |
| Percentual Carga Tributária | `%Car_Trib` | percentual editável — **meramente informativo** na negociação |

### 3.2 Variáveis do Orçamento
| Variável | Sigla | Definição |
|---|---|---|
| Percentual Desconto Orçamento | `%Desc_Orc` | desconto aplicado a todos os ambientes do orçamento |
| Forma de Pagamento | texto | À vista / Cartão / Venda Programada / Total Flex |
| Número de Parcelas | `Num_Parc` | conforme a forma de pagamento |
| Forma de Entrada | texto | Pix / Cheque / Boleto / Cartão |
| Valor / Data de Entrada | `Val_Ent` / Data | editável |
| Datas / Valor de cada Parcela | Data / `Val_Parc` | conforme parcelamento |
| Provisão de Impostos | `Prov_Imp` | informativo — `Prov_Imp = %Car_Trib × Val_Cont` |
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
| Comissão Arquiteto (orçamento) | `Com_Arq_Orc` | `Σ Com_Arq_Amb` |
| Programa Fidelidade (orçamento) | `Pro_Fid_Orc` | `Σ Pro_Fid_Amb` |
| Custos Adicionais | `Cust_Ad` | `Cust_Ad = Com_Arq_Orc + Pro_Fid_Orc + Cust_Via + Bri` (cada parcela só se seu toggle = true) |

### 3.3 Variáveis do Ambiente
| Variável | Sigla | Definição |
|---|---|---|
| Percentual Desconto Ambiente | `%Desc_Amb` | desconto individual do ambiente |
| Valor Bruto de Venda Ambiente | `VBVA` | Σ valores de venda do XML do ambiente (`pool_ambientes.budget_total`) |
| Custo Fábrica Ambiente | `CFA` | Σ custos de fábrica c/ frete do XML (`pool_ambientes.order_total`) |
| Valor Bruto Negociado Ambiente | `VBNA` | fórmula condicional — §4 |
| Valor à Vista Ambiente | `VAVA` | `VAVA = VBNA × (1−%Desc_Orc) × (1−%Desc_Amb)` |
| Programa Fidelidade (ambiente) | `Pro_Fid_Amb` | `%Pro_Fid × [ VAVA − Cust_Via·(VBVA/VBVO) − Bri/Num_Amb ]` |
| Comissão Arquiteto (ambiente) | `Com_Arq_Amb` | `%Com_Arq × [ VAVA − Pro_Fid_Amb − Cust_Via·(VBVA/VBVO) − Bri/Num_Amb ]` — em cadeia: arq **não** ganha sobre a fidelidade |

---

## 4. Modelo de cálculo (fórmula condicional fechada)

Por ambiente:

```
Se Tog_Cadi (repassa ao cliente):
   VBNA = VBVA / [ (Tog_Carq ? 1−%Com_Arq : 1) · (Tog_Fid ? 1−%Pro_Fid : 1) ]
        + [ (Tog_Cvia ? Cust_Via · (VBVA/VBVO) : 0) + (Tog_Bri ? Bri/Num_Amb : 0) ]
          / [ (1−%Desc_Orc)·(1−%Desc_Amb) ]
   # viagem E brinde dentro do colchete /[(1-desc)] → blindados do desconto (recuperados 100%)
Senão (absorve):
   VBNA = VBVA

VAVA = VBNA · (1−%Desc_Orc) · (1−%Desc_Amb)
```

Agregação por orçamento (ordem de cálculo):

```
VBVO = Σ VBVA          CFO = Σ CFA          Num_Amb = nº ambientes
(VBVO precisa existir antes do rateio de viagem em cada VBNA)
VBNO = Σ VBNA          VAVO = Σ VAVA

# comissão EM CADEIA, por ambiente (arq não ganha sobre fid; e nem arq nem fid
# ganham sobre viagem/brinde — a base SEMPRE exclui esses custos, repassados ou absorvidos):
#   base_custos = (Tog_Cvia ? Cust_Via·(VBVA/VBVO) : 0) + (Tog_Bri ? Bri/Num_Amb : 0)
#   Pro_Fid_Amb = (Tog_Fid  ? %Pro_Fid · (VAVA − base_custos) : 0)
#   Com_Arq_Amb = (Tog_Carq ? %Com_Arq · (VAVA − Pro_Fid_Amb − base_custos) : 0)
Com_Arq_Orc = Σ Com_Arq_Amb
Pro_Fid_Orc = Σ Pro_Fid_Amb
Cust_Ad = Com_Arq_Orc + Pro_Fid_Orc + (Tog_Cvia ? Cust_Via : 0) + (Tog_Bri ? Bri : 0)

Val_Liq  = VAVO − Cust_Ad
%Desc_Tot = (VBVO − Val_Liq) / VBVO
Markup    = Val_Liq / CFO
Cust_Fin  = (custo da modalidade de pagamento via mod_fin)
Val_Cont  = VAVO + Cust_Fin
Prov_Imp  = %Car_Trib × Val_Cont        # informativo
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
| **Ambiente (qualidade — §8)** | `pool_ambientes` (colunas novas) | `qa_selo` (ok/bloqueado), `qa_pct_sem_acrescimo`, `qa_markup_xml`, `qa_custo_sem_venda`, `qa_override_por_id`, `qa_override_motivo` |

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
   exaustivos (incl. LELEU §9 e os 4 toggles em ON/OFF). Substitui `calcular_margens`.
2. **Validação de qualidade do XML (§8):** função pura no parser que calcula
   `qa_markup_xml`/`qa_pct_sem_acrescimo`/`qa_custo_sem_venda` e o `qa_selo`; o upload grava
   o selo e coloca 🔴 em quarentena. Testável isolada (Área Gourmet → 🔴, bons → 🟢).
3. **Migração de schema/dados:** colunas derivadas em `orcamentos` + colunas `qa_*` em
   `pool_ambientes`; mover params para o projeto; aposentar `valor_liquido`/bloco duplicado
   em `margens`.
4. **Endpoints:** ao salvar negociação, chamar `mod_negociacao` e gravar os derivados;
   no upload, recusar entrada de ambiente 🔴 em orçamento; endpoint de override
   (Diretor/Gerente Adm-Fin) com justificativa + log. `Cust_Fin` vem das tabelas `mod_fin`.
5. **UI (fase de validação):** o modal de parâmetros exibe os valores canônicos por
   orçamento, refletindo os ambientes marcados — para conferência visual contra casos
   conhecidos antes de seguir para as rubricas/AF.

---

## 8. Qualidade do dado de XML (trava de importação)

Validação por ambiente executada **no upload do XML**, para impedir que dado de fábrica
quebrado contamine a negociação e o financeiro. A trava só dispara em sinais que dão **0 em
dado bom** (sem falso-positivo nos ~16–20% de acessórios de valor zero normais).

### 8.1 Métricas (por ambiente, calculadas no parser e persistidas)
- `qa_markup_xml = ΣBUDGET / ΣORDER` (acréscimo médio do XML).
- `qa_pct_sem_acrescimo` = % do ΣBUDGET em itens com `BUDGET ≤ ORDER` (vendidos no custo ou abaixo).
- `qa_custo_sem_venda` = nº de itens com `ORDER>0 e BUDGET=0` (paga à fábrica, não cobra).

### 8.2 Selo de qualidade (`qa_selo`)
- 🔴 **Bloqueado** se qualquer: `qa_pct_sem_acrescimo ≥ limiar` (default **5%**) **ou**
  `qa_custo_sem_venda > 0`.
- 🟢 **OK** caso contrário.
- (Sem nível 🟡 nesta fase — os sinais ruidosos foram descartados: "itens sem preço" cru e
  "desconto de fábrica zerado" via `TABLE` disparam em orçamento bom e **não** entram na trava.)

### 8.3 Comportamento
- No **upload**, o ambiente é importado em **quarentena** quando 🔴: visível e inspecionável,
  mas **não pode entrar em nenhum orçamento**. A mensagem expõe o motivo (ex.: "100% do
  valor sem acréscimo — markup 1,00").
- **Override:** **Diretor** ou **Gerente Administrativo/Financeiro** libera o ambiente com
  **justificativa obrigatória** (ex.: cortesia). Grava `qa_override_por_id`/`qa_override_motivo`
  e registra em auditoria (`log_acoes_gerenciais`). Alternativa: re-exportar o XML correto.
- O **limiar** (default 5%) é **configurável por loja** no painel admin (junto das % `a–i`).

### 8.4 Caso de teste
- **Área Gourmet** (LELEU): `qa_markup_xml` 1,00; `qa_pct_sem_acrescimo` 100%;
  `qa_custo_sem_venda` 0 → **🔴 bloqueado**.
- **Banheiro / Sala Íntima / Suíte Master:** markup 2,78; `qa_pct_sem_acrescimo` 0%;
  `qa_custo_sem_venda` 0 → **🟢 OK** (passam limpos).

---

## 9. Caso de regressão — LELEU Orçamento 1 (id=19)

Entrada: 2 ambientes — Área Gourmet (`VBVA` 22.830,99 / `CFA` 22.830,99) e Banheiro Social
(`VBVA` 2.650,50 / `CFA` 953,40). Projeto: `%Com_Arq` 10%, `%Pro_Fid` 2%, `Cust_Via` 2.000,
`Bri` 500, todos os toggles ON. Orçamento: `%Desc_Orc` 20%, `%Desc_Amb` 0.

| Saída | Valor esperado |
|---|---|
| Área Gourmet — `VBNA` / `VAVA` | 28.437,93 / 22.750,35 |
| Banheiro Social — `VBNA` / `VAVA` | 3.577,64 / 2.862,11 |
| `VBVO` / `CFO` | 25.481,49 / 23.784,39 |
| `VBNO` / `VAVO` | 32.015,58 / 25.612,46 |
| `Com_Arq_Orc` / `Pro_Fid_Orc` | 2.265,02 / 462,25 |
| `Cust_Ad` (Com_Arq_Orc 2.265,02 + Pro_Fid_Orc 462,25 + Cust_Via 2.000 + Bri 500) | 5.227,27 |
| `Val_Liq` | **20.385,19** (= líquido sem custo, VBVO×0,80 — proteção total) |
| `%Desc_Tot` | **20,00%** (= `%Desc_Orc` — todos os custos repassados ao cliente) |
| `Markup` | 0,857 |
| `Cust_Fin` / `Val_Cont` | no fluxo real `Cust_Fin = valor_total − VAVO` ⇒ `Val_Cont = valor_total` armazenado (**26.925,90**) |

> **Blindagem + comissão em cadeia:** viagem e brinde entram **dentro** do colchete
> `/[(1−%Desc_Orc)·(1−%Desc_Amb)]` (blindados do desconto); a comissão é por ambiente e em
> cadeia (arq não ganha sobre fid; ambos excluem viagem/brinde). Resultado: com tudo
> repassado, `Val_Liq` = líquido sem custo e `%Desc_Tot` = `%Desc_Orc`.

Este caso vira o teste unitário-âncora do `mod_negociacao`.

## 10. Testes
- **Unitário (puro, `mod_negociacao`):** caso LELEU §9; matriz de toggles (cada um ON/OFF,
  `Tog_Cadi` ON/OFF — repassa vs absorve); `%Desc_Amb` por ambiente; orçamento de 1 e de N
  ambientes; rateio da viagem; ordem de cálculo (VBVO antes dos VBNA).
- **Unitário (qualidade XML §8):** Área Gourmet → 🔴 (markup 1,00 / 100% sem acréscimo);
  os 3 ambientes bons → 🟢; item `ORDER>0 e BUDGET=0` → 🔴; acessório de valor zero não acusa.
- **E2E:** salvar negociação grava os derivados corretos; troca de params do projeto
  reflete em todos os orçamentos; remover/incluir ambiente recalcula VBVO/CFO; upload 🔴
  fica em quarentena e não entra em orçamento; override por Diretor/Gerente Adm-Fin libera e loga.
- **Validação manual (fase seguinte):** modal de parâmetros exibindo os canônicos.

## 11. Decisões (todas resolvidas)
1. **Base do `Prov_Imp`:** ✅ `Prov_Imp = %Car_Trib × Val_Cont` (impostos sobre o valor de contrato).
2. **`Cust_Fin`:** ✅ vem do `mod_fin` existente — o motor calcula até `VAVO` e delega:
   `Val_Cont = mod_fin.calcular(VAVO, entrada, n_parcelas, data, modalidade).total_cliente`;
   `Cust_Fin = Val_Cont − VAVO`. A loja sempre recebe `VAVO`; `Cust_Fin` é pago pelo cliente,
   entra no `Val_Cont` e **não** toca `Val_Liq`/`Markup`. Remove-se o `custo_financeiro_pct`
   duplicado do `mod_margens`; `mod_fin` permanece como fonte única do financeiro.
3. **Qualidade do dado de XML:** ✅ bloqueio em quarentena no upload, sinais limpos
   (acréscimo zerado / custo sem venda), override Diretor+Gerente Adm-Fin. Ver §8.

---

## 12. Estratégia de implementação segura (modo sombra + rollback)

Refatorar o motor financeiro é arriscado porque os números viram contrato. **Parte da
dissonância é esperada e correta** (gross-up aditivo→divisivo; agregado→por ambiente;
`valor_liquido` legado que guardava o bruto). Logo, o objetivo da estratégia não é "não
mudar número" — é **distinguir diferença correta de regressão** e poder voltar.

1. **Ponto de retorno (git):** tag `pre-refator-negociacao` no `main` (commit `5b8524c`).
   Todo o trabalho em **branch**. Reverter = `git reset --hard pre-refator-negociacao`.
2. **Modo sombra:** o `mod_negociacao` novo roda **em paralelo** ao cálculo atual e grava os
   derivados em **colunas novas** (não sobrescreve nada). O modal de parâmetros mostra
   **valor de hoje × valor novo, lado a lado**, por orçamento. Validação visual antes de
   qualquer corte — esta é a "validação na interface".
3. **Golden-master:** antes de mexer, fotografar os valores calculados hoje de um conjunto
   de orçamentos reais (LELEU + outros). Os testes do motor novo comparam contra a foto e
   **exigem que cada diferença seja explicada**; diferença não-explicada barra o merge.
4. **Migração aditiva e reversível:** apenas **adicionar** colunas; `valor_liquido` e o bloco
   `margens` antigos ficam intactos (só param de ser lidos). A remoção real é uma fase de
   limpeza posterior, após validação.
5. **Corte em fases (cada uma revertível):** A) motor novo em sombra + UI lado a lado →
   validação; B) contrato/UI passam a usar os valores novos; C) limpeza do código/colunas
   antigos.

## 13. Próxima fase
Validar o mecanismo **na interface** (modal de parâmetros, modo sombra §12) — exibir os
valores canônicos por orçamento e conferir contra casos reais — antes de construir as
rubricas do item 6, as aprovações financeiras e a comissão de vendas, que consomem
`Val_Liq`, `CFO` e `Markup`.
