# Spec — Lista de ambientes com valor no contrato

**Data:** 2026-07-01
**Status:** design aprovado (aguardando plano de implementação)
**Escopo desta frente:** somente o **contrato**. A proposta é frente seguinte (ver §7).

---

## 1. Objetivo

Incluir na **capa do contrato** (primeira página) uma seção **"4. Ambientes"** — antes da
"Forma de Pagamento", que passa a numeração **"5"** — listando cada ambiente do orçamento com o
seu **valor com financiamento**, mais uma linha de **Total** que bate com o `TOTAL_CONTRATO`.

Motivação: o cliente enxerga, no próprio contrato, a composição por ambiente do valor que está
contratando. Esse valor por ambiente **já é exibido na tela de negociação** (coluna "Com
financiamento"); o contrato passa a reproduzir a mesma informação.

## 2. Conteúdo da tabela

Uma linha por ambiente presente no orçamento, mais uma linha de total:

```
Cozinha         R$ 12.345,67
Dormitório      R$  8.900,00
Home Theater    R$  5.200,00
---------------------------
Total           R$ 26.445,67
```

- **Coluna 1 — nome do ambiente:** `PoolAmbiente.nome_exibicao`, **justificado à esquerda**.
- **Coluna 2 — valor:** `Val_Cont_Amb` (definição em §3), formatado `R$ #.###,##`
  (`mod_contrato._formatar_valor`), **justificado à esquerda** na coluna dele.
- **Linha Total:** rótulo "Total" (col. 1) + `Val_Cont` (= `TOTAL_CONTRATO`) na col. 2.
- **Ordem das linhas:** ordem dos ambientes no orçamento (`OrcamentoAmbiente.ordem`), a mesma já
  usada na tela.

## 3. Cálculo — valor por ambiente com financiamento

O valor de cada linha é o **Valor de Contrato do Ambiente**:

```
Cust_Fin_Amb = Cust_Fin × (VAVA / VAVO)
Val_Cont_Amb = VAVA + Cust_Fin_Amb = VAVA × (Val_Cont / VAVO)
```

- `VAVA` — valor à vista do ambiente (com desconto individual + global), saída do motor por ambiente.
- `VAVO` — soma dos `VAVA` do orçamento (`d["VAVO"]`).
- `Val_Cont` — valor de contrato do orçamento (`d["Val_Cont"]` = `VAVO + Cust_Fin`).
- **Rateio do custo financeiro:** proporcional ao `VAVA` (o ambiente de maior valor absorve mais
  financeiro). Escolhido por fechar a conta: `Σ Val_Cont_Amb = Val_Cont` exatamente.

Esta é a **mesma fórmula já usada no frontend** em `static/index.html:5677-5687`
(`vava * (Val_Cont / VAVO)`). A implementação do backend replica esse cálculo a partir dos dados
que a geração do contrato já carrega.

### 3.1 Reconciliação de centavos

Arredondar cada `Val_Cont_Amb` para centavos pode gerar um resíduo de ±alguns centavos entre a soma
das linhas e o `Val_Cont`. Regra: **o último ambiente da lista absorve o resíduo**
(`ultimo += Val_Cont − Σ(demais arredondados)`), garantindo `Σ linhas == Val_Cont` ao centavo.

## 4. Origem dos dados na geração

A rota de geração do contrato já carrega os ambientes do orçamento (via `OrcamentoAmbiente` →
`PoolAmbiente`) e roda o motor `mod_negociacao.calcular_orcamento`, que retorna `d["ambientes"]`
(cada um com `VAVA` e `id`), `d["VAVO"]` e `d["Val_Cont"]` (ver `main.py` ~4576-4600). A frente
**reusa esses valores**; não altera o motor de negociação.

A lista para a tabela é composta de `(nome_exibicao, Val_Cont_Amb)` por ambiente — nome vindo do
`PoolAmbiente` correspondente ao `id` de cada item de `d["ambientes"]`.

## 5. Template `modelo_contrato_mapeado.docx`

Estrutura atual da capa (tabelas): `[0]` 1. Identificação · `[1]` 2. Endereço Residencial ·
`[2]` 3. Endereço de Instalação · `[3]` 4. Forma de Pagamento (grade de parcelas, 11×7).

Mudanças no template:

1. **Nova seção "4. Ambientes"** — tabela estilizada no padrão das demais (cabeçalho de seção +
   colunas Ambiente / Valor), inserida **antes** da atual "4. Forma de Pagamento".
2. **Renumerar** "4. Forma de Pagamento" → **"5. Forma de Pagamento"** (texto do cabeçalho da
   seção no template).

A tabela de ambientes tem **número de linhas variável** (N ambientes + total), então é preenchida
dinamicamente pelo código na geração — não é uma grade de posição fixa.

## 6. Alterações no código (`mod_contrato.py`)

1. **Novo helper `_preencher_ambientes(doc, ambientes_valores, coletor=None)`** — recebe a lista
   `[(nome, valor_float), ...]` já com a linha de total resolvida (ou monta o total internamente),
   localiza a tabela "4. Ambientes" e escreve as linhas com o alinhamento à esquerda em ambas as
   colunas. Cria linhas conforme a quantidade de ambientes.
2. **Nova função de cálculo `ambientes_valor_contrato(d)`** (ou equivalente) — a partir do retorno
   do motor (`d`), devolve `[(nome, Val_Cont_Amb), ...]` aplicando §3 e a reconciliação §3.1. Fica
   isolada e testável sem docx.
3. **`_preencher_grade` — localizar a grade por conteúdo, não por índice fixo.** Hoje usa
   `doc.tables[3]`. Com a nova seção, a grade passa a `tables[4]`. Trocar por uma busca robusta
   (ex.: a tabela cujo cabeçalho contém "Forma de Pagamento"), para não quebrar com o deslocamento
   e ficar imune a futuras reordenações.
4. **`preencher_contrato`** — chamar `_preencher_ambientes` junto de `_preencher_grade` /
   `_substituir_marcadores`. Passar a lista de ambientes via `ctx` (ex.: `ctx["_ambientes"]`),
   preenchido pela rota a partir de `d`.
5. **Proteção read-only:** as células de valor da tabela de ambientes entram no `coletor` de
   regiões editáveis, coerente com o resto do contrato protegido.

## 7. Fora de escopo (próxima frente)

- **Recriar `modelo_proposta.docx`** para espelhar a 1ª página do contrato, incluindo esta tabela
  de ambientes. A proposta hoje lista só nomes (`AMBIENTES_LISTA`) e precisa de revisão de formato.
  Vira spec própria após esta frente.
- Alterações no motor de negociação (`mod_negociacao.py`): nenhuma.

## 8. Testes (TDD)

**Unit — cálculo (`ambientes_valor_contrato`):**
- Rateio proporcional ao VAVA: dois ambientes de VAVA diferentes com `Cust_Fin > 0` → cada
  `Val_Cont_Amb = VAVA × Val_Cont/VAVO`.
- Reconciliação: caso com resíduo de arredondamento → `Σ Val_Cont_Amb == Val_Cont` ao centavo;
  o resíduo cai no último ambiente.
- Borda: `Cust_Fin == 0` → `Val_Cont_Amb == VAVA` e Σ == VAVO; `VAVO == 0` → sem divisão por zero.

**Template — geração:**
- Orçamento com N ambientes → tabela "4. Ambientes" com N linhas de `(nome, valor)` + linha Total
  correta.
- **Trava de índice:** a grade de parcelas ("5. Forma de Pagamento") continua sendo preenchida
  corretamente após a inserção da seção de ambientes (guarda contra o deslocamento `tables[3]`→`[4]`).
- Contrato protegido: as células de valor dos ambientes ficam nas regiões editáveis.

## 9. Critérios de aceite

- [ ] Contrato gerado exibe a seção "4. Ambientes" com uma linha por ambiente (nome à esquerda,
      valor à esquerda) e linha Total.
- [ ] Cada valor por ambiente = valor com financiamento idêntico ao mostrado na tela de negociação.
- [ ] Σ das linhas == `Val_Cont` == `TOTAL_CONTRATO`, ao centavo.
- [ ] "Forma de Pagamento" renumerada para "5" e a grade de parcelas segue correta.
- [ ] Suíte verde (unit + template), sem regressão nos testes de contrato existentes.
