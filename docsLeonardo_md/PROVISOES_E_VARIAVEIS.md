# Provisões e variáveis — config financeira por loja (referência do motor)

> Tabela canônica fornecida no desenvolvimento do motor. Define o que é **configurado por
> loja**, as variáveis de **projeto**, **orçamento** e **ambiente**, e as fórmulas das provisões.
> Fonte de verdade para o spec do painel de configurações financeiras da loja + margem real.

## Configurações financeiras da loja (taxas % por loja)

| Item | Sigla | Definição |
|------|-------|-----------|
| Frete Fábrica → Loja | `%Frete_Fab` | % do frete da fábrica para a loja — painel de config de custos da loja |
| Comissões Administrativas | `%Com_Adm` | % das comissões administrativas. **v1:** taxa agregada única. **Depois:** dividida por função adm (diretor, gerente comercial, gerente adm) |
| Comissão de Vendas | `%Com_Venda` | comissão **por consultor**. O `%` **não é um campo fixo** — é resultado de uma **rotina** (meta × margem de desconto). Ver "Rotina de %Com_Venda" abaixo |
| Comissão de Medidor | `%Com_Med` | % pago por medição |
| Comissão de Projeto Executivo | `%Com_Proj_Exec` | % pago por projeto executivo |
| Frete Local | `%Frete_Loc` | % do frete da loja para o cliente |
| Assistências | `%Assist` | índice % de assistências |
| Insumos Locais | `%Ins_Loc` | índice % de compras de suprimentos locais |
| Impostos | `%Car_Trib` | % de impostos da nota — extraído do sistema fiscal ou configurado no painel (valor já existe, passará a vir dessa fonte) |

> O modal é definido para todo o projeto, mas deve refletir cada orçamento conforme seus ambientes.

## Variáveis do Projeto (modal de parâmetros)

| Variável | Sigla | Tratamento |
|----------|-------|-----------|
| % Comissão Arquiteto | `%Com_Arq` | definido no modal — editável |
| % Programa Fidelidade | `%Pro_Fid` | definido no modal — editável |
| Custo Viagem | `Cust_Via` | definido no modal — editável |
| Brinde | `Bri` | definido no modal — editável |
| Toggle Custos Adicionais | `Tog_Cadi` | true → acrescenta custos ao VBVA; false → VBVA = VBNA (e VBVO = VBNO) |
| Toggle Comissão Arquiteto | `Tog_Carq` | true + Tog_Cadi true → acrescenta ao VBVA e repassa; Tog_Cadi false → abate do valor da venda p/ Val_Liq |
| Toggle Programa Fidelidade | `Tog_Fid` | idem Tog_Carq |
| Toggle Custo Viagem | `Tog_Cvia` | idem, proporcional |
| Toggle Brinde | `Tog_Bri` | idem (dividido igualmente pelos ambientes) |
| ~~Carga Tributária~~ | `%Car_Trib` | **movida do modal para a config da loja** (decisão); fica 0 até a 1ª versão (config manual; depois extraída do módulo fiscal) |

## Variáveis do Orçamento

| Variável | Sigla | Fórmula / tratamento |
|----------|-------|-----------|
| Desconto Orçamento | `%Desc_Orc` | % aplicado em todos os ambientes do orçamento |
| Forma de Pagamento | Texto | A vista / Cartão de Crédito / Venda Programada / Total Flex |
| Número de Parcelas | `Num_Parc` | conforme forma de pagamento |
| Forma Entrada | Texto | Pix / Cheque / Boleto / Cartão |
| Valor Entrada | `Val_Ent` | editável |
| Data Entrada | `Data_Ent` | editável |
| Datas de cada Parcela | `Data_Parc(n)` | conforme forma de pagamento |
| Valor de cada Parcela | `Val_Parc(n)` | conforme forma de pagamento e parcelamento |
| Provisão de Impostos | `Prov_Imp` | `Prov_Imp = %Car_Trib × (VAVO + Cust_Fin)` |
| Valor Bruto de Venda Orçamento | `VBVO` | Σ VBVA |
| Custo Fábrica Orçamento | `CFO` | Σ CFA |
| Outros Fornecedores | `Out_Forn` | compra de produtos de outros fornecedores (não Dalmóbile) — editável pelo Gerente Admin/Fin |
| Valor Bruto Negociado Orçamento | `VBNO` | Σ VBNA |
| Valor a Vista Orçamento | `VAVO` | Σ VAVA |
| Número de Ambientes | `Num_Amb` | nº de ambientes do orçamento |
| Custo Financeiro | `Cust_Fin` | da forma de pagamento/parcelamento (tabelas) |
| Valor de Contrato | `Val_Cont` | `Val_Cont = VAVO + Cust_Fin` |
| Valor Líquido de Contrato | `Val_Liq` | `Val_Liq = VAVO − Cust_Ad` |
| Desconto Total | `%Desc_Tot` | `(VBVO − Val_Liq) / VBVO` |
| Markup | `Markup` | `Val_Liq / CFO` |
| Comissão Arquiteto | `Com_Arq_Orc` | Σ Com_Arq_Amb |
| Programa Fidelidade | `Pro_Fid_Orc` | Σ Pro_Fid_Amb |
| Custos Adicionais | `Cust_Ad` | `Com_Arq + Pro_Fid + Cust_Via + Bri` |
| Frete Fábrica→Loja Orçamento | `Frete_Fab_Orc` | `%Frete_Fab × CFO` |
| Comissões Administrativas Orçamento | `Com_Adm_Orc` | `%Com_Adm × Val_Liq` |
| Comissão de Vendas Orçamento | `Com_Venda_Orc` | `%Com_Venda × Val_Liq` |
| Comissão de Medidor Orçamento | `Com_Med_Orc` | `%Com_Med × Val_Liq` |
| Comissão de Projeto Executivo Orçamento | `Com_Proj_Exec_Orc` | `%Com_Proj_Exec × Val_Liq` |
| Frete Local Orçamento | `Frete_Loc_Orc` | `%Frete_Loc × VAVO` |
| Assistências Orçamento | `Assist_Orc` | `%Assist × VAVO` |
| Insumos Locais Orçamento | `Ins_Loc_Orc` | `%Ins_Loc × VAVO` |
| Custo Variável | `Cust_Var` | `CFO + Out_Forn + Frete_Fab_Orc + Com_Adm_Orc + Com_Venda_Orc + Com_Med_Orc + Com_Proj_Exec_Orc + Frete_Loc_Orc + Assist_Orc + Ins_Loc_Orc + Prov_Imp` |
| Margem de Contribuição Orçamento | `Marg_Cont` | `(Val_Liq − Cust_Var) / Val_Liq` — margem **sobre o valor líquido** (pode ser negativa) |

> **Exceção de nomenclatura:** `Prov_Imp` é o único valor de provisão sem sufixo `_Orc`. Mantido
> assim de propósito — é sigla já consagrada/implementada no motor (NOMENCLATURA §3 + coluna-sombra
> `prov_imp`), a taxa é `%Car_Trib` (sem colisão) e não há versão por ambiente. **Não renomear.**

## Variáveis do Ambiente

| Variável | Sigla | Fórmula |
|----------|-------|---------|
| Desconto Ambiente | `%Desc_Amb` | % aplicado individualmente no ambiente |
| Valor Bruto de Venda Ambiente | `VBVA` | Σ valores de venda do XML do ambiente |
| Custo Fábrica Ambiente | `CFA` | Σ custos de fábrica (com frete) do XML do ambiente |
| Valor Bruto Negociado Ambiente | `VBNA` | `VBVA/[(1−Com_Arq)(1−Pro_Fid)] + [Cust_Via·(VBVA/VBVO) + Bri/Num_Amb]/[(1−%Desc_Orc)(1−%Desc_Amb)]` |
| VBNA com Financeiro | `VBNA_C_FIN` | `VBNA + Cust_Fin(do ambiente)` |
| Valor a Vista Ambiente | `VAVA` | `VBNA·(1−%Desc_Orc)·(1−%Desc_Amb)` |
| Comissão Arquiteto Ambiente | `Com_Arq_Amb` | `%Com_Arq·[VAVA − Pro_Fid_Amb − Cust_Via·(VBVA/VBVO) − Bri/Num_Amb]` |
| Programa Fidelidade Ambiente | `Pro_Fid_Amb` | `%Pro_Fid·[VAVA − Cust_Via·(VBVA/VBVO) − Bri/Num_Amb]` |
| Frete Fábrica→Loja Ambiente | `Frete_Fab_Amb` | `%Frete_Fab·CFA` |

## Rotina de `%Com_Venda` (configurador — por consultor, regra no backend)

`%Com_Venda` **não é um campo fixo**: sai de uma rotina configurável por loja, com **dois
configuradores** num **modal único**. A regra é avaliada **no backend** (segurança — o consultor
não pode forçar a própria comissão).

### Configurador 1 — Faixas de comissão por venda

Função-degrau do **valor de venda do consultor** = **`Val_Liq` acumulado no mês** (janela mensal).
A **meta é mensal e fixa** (por consultor). Quanto mais o consultor vendeu no mês (líquido), maior
a faixa. A 1ª faixa é a **comissão mínima**. O configurador define **nº de faixas**, **limiar** de
cada e **% de comissão** de cada.

```json
"faixas_comissao": [
  {"venda_ate": m,    "pct": a},   // Val_Liq_mês < m            → a% (mínima)
  {"venda_ate": n,    "pct": b},   // m ≤ Val_Liq_mês < n        → b%
  {"venda_ate": p,    "pct": c},   // n ≤ Val_Liq_mês < p        → c%
  {"venda_ate": null, "pct": d}    // Val_Liq_mês ≥ p (sem teto) → d%
]
```

> A **meta mensal fixa** por consultor é guardada na config (valor R$). Os limiares podem ser
> absolutos (R$) ou relativos à meta — **a confirmar** (ver micro-pontos abaixo).

### Configurador 2 — Limitador de desconto → redutor de comissão (com toggle)

Penaliza descontos altos **reduzindo o `%` de comissão daquela venda específica** (não a venda
creditada). Avaliado **por orçamento** (`%Desc_Orc`). **Tem toggle `ativo`** — muitas lojas não
usam. O configurador define **nº de limites**, **% de desconto** de cada e **% de redutor** de cada.

```json
"limitador_desconto": {
  "ativo": true,                         // toggle (default false p/ lojas que não usam)
  "base_desconto": "Desc_Orc",           // FECHADO: desconto do orçamento
  "limites": [
    {"desconto_acima_de": x, "redutor_pct": s},   // %Desc_Orc > x% → reduz o % daquela venda em s%
    {"desconto_acima_de": y, "redutor_pct": t}    // %Desc_Orc > y% (y>x) → redutor t%
  ]
}
```

### Resolução (backend)
1. `Val_Liq_mês` = acumulador parcial do consultor no mês (ver Acumulador abaixo).
2. `%_base` = faixa em `faixas_comissao` por `Val_Liq_mês`.
3. Para o orçamento: se `limitador_desconto.ativo` e `%Desc_Orc` ultrapassa limites, pega o
   `redutor_pct` do **maior** limite ultrapassado → `%_efetivo = %_base × (1 − redutor_pct)`;
   senão `%_efetivo = %_base`.
4. `Com_Venda_Orc = %_efetivo × Val_Liq` (do orçamento).

### Acumulador mensal por consultor (FECHADO)
- Um **acumulador parcial** por consultor soma o `Val_Liq` das vendas do mês corrente.
- A comissão é **provisória** durante o mês (faixa pelo acumulado parcial) e **fechada/definitiva
  ao final de cada ciclo mensal**.
- Implica estado persistente: total acumulado por (consultor, mês) + um fechamento de ciclo.

### Micro-pontos ainda a confirmar
- **Limiares das faixas**: absolutos em R$ ou relativos à **meta mensal** do consultor?
- **`redutor_pct`**: multiplicativo `%_base × (1 − s)` (adotado) ou em pontos `%_base − s`?
- **Fronteiras** `<`/`≤` nos limiares (definir inclusivas).

## Status e faseamento (aceito)

A tabela acima reflete o **plano geral do sistema**: a questão das **provisões**, o **módulo
financeiro** (margem real) e o **subsistema de cálculo de comissões**.

- **v1 — Config financeira da loja (`%` simples) + margem real.** Defaults de negociação por loja
  (`%Com_Arq`, `%Pro_Fid`, `%Car_Trib`) + taxas de provisão (`%Frete_Fab`, `%Com_Adm`, `%Com_Med`,
  `%Com_Proj_Exec`, `%Frete_Loc`, `%Assist`, `%Ins_Loc`) + `Out_Forn` (editável Gerente Adm/Fin) →
  motor calcula `Cust_Var` e `Marg_Cont`. As faixas/limitador da comissão de vendas **entram como
  config** já na v1.
- **Fase 2 — Subsistema de comissão de vendas (acumulador mensal).** Acumulador parcial de
  `Val_Liq` por (consultor, loja, mês), comissão **provisória** no mês e **definitiva no fechamento
  do ciclo** (faixa final do mês aplicada a todos os negócios do ciclo, com o redutor por negócio).
- **Fase 3 — Custo financeiro absorvido pela loja** entra em `Cust_Var` (quando houver modalidade
  com financeiro não repassado ao cliente).
- **Fase futura — Condições de pagamento por loja** (tabela `condicoes_financeiras` com `loja_id`,
  ver `FUTURO_CALCULO_FINANCEIRO.md`) e **divisão de `Com_Adm`** por função (diretor / gerente
  comercial / gerente adm).
