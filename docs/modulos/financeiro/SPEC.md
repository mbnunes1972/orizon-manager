# Módulo Financeiro — SPEC

---

## Visão geral

O módulo financeiro calcula o impacto de cada modalidade de pagamento no valor final apresentado ao cliente e na margem interna da loja.

**Princípio fundamental:** O cliente sempre vê o valor à vista como base. O custo financeiro (juros, taxas) é um acréscimo sobre esse valor — nunca um desconto.

---

## Modalidades disponíveis

| Modalidade | Status | Arquivo |
|---|---|---|
| À vista | `[IMPLEMENTADO]` | — |
| Boleto parcelado (até 4x sem juros) | `[TODO]` | — |
| Venda Programada | `[IMPLEMENTADO]` | `mod_fin/venda_programada.py` |
| Total Flex | `[IMPLEMENTADO]` | `mod_fin/total_flex.py` |
| Aymoré (financiamento) | `[IMPLEMENTADO]` | `mod_fin/aymore.py` |
| Cartão de Crédito — Preferencial (Itaú) | `[IMPLEMENTADO]` | `mod_fin/cartao.py` |
| Cartão de Crédito — Mercado | `[IMPLEMENTADO]` | `mod_fin/cartao.py` |

---

## 1. À Vista

**Status:** `[IMPLEMENTADO]`

Sem acréscimo financeiro. O cliente paga o valor à vista negociado.

```
Valor ao cliente = Valor bruto × (1 − desconto%)
```

**Exibição:** "1x" no select de parcelas (substituiu "A Vista").

---

## 2. Boleto Parcelado — até 4x sem juros

**Status:** `[TODO]`

**Regras:**
- Disponível em 1x, 2x, 3x ou 4x
- Sem acréscimo de juros ao cliente
- O custo do parcelamento é absorvido pela loja (reduz margem)
- Taxa interna de custo: `[VALIDAR]` — definir % de custo por parcela
- Vencimentos: entrada + parcelas mensais consecutivas

**A implementar:**
- Tabela de taxas internas por número de parcelas em `tabelas_financeiras/boleto_parcelado.json`
- Rota `POST /calcular_boleto_parcelado`
- Painel no frontend similar ao cartão de crédito

---

## 3. Venda Programada

**Status:** `[IMPLEMENTADO]`

Modalidade onde o cliente paga em parcelas com datas definidas, sem vínculo com financiadora. Ideal para obras longas.

**Regras:**
- Valor total dividido em parcelas de valor livre
- Datas de vencimento definidas manualmente
- Prazo máximo: 395 dias `[VALIDAR]`
- Última parcela não pode ser negativa
- Não há taxa de juros para o cliente — custo absorvido pela loja

**Campos:**
- Valor à vista base
- Número de parcelas
- Datas individuais editáveis
- Valor de cada parcela (editável com recálculo automático)

---

## 4. Total Flex

**Status:** `[IMPLEMENTADO]`

Financiamento próprio da loja com taxa de juros configurável.

**Regras de segurança:**
- A taxa de juros mensal **nunca é exibida** ao cliente no frontend
- Apenas gerentes e diretores podem ver/editar a taxa (autenticação delegada)
- A taxa fica oculta atrás do cadeado 🔒 na sidebar

**Campos:**
- Valor à vista base
- Entrada (opcional)
- Número de parcelas
- Taxa de juros mensal (oculta — só gerente/diretor)
- Parcelas calculadas automaticamente

**Arquivo de configuração:** `config/total_flex.json`

---

## 5. Aymoré (Financiamento)

**Status:** `[IMPLEMENTADO]`

Financiamento via financeira Aymoré. O sistema consulta a tabela de taxas local.

**Regras:**
- Valor financiado = valor à vista − entrada
- Tabela de coeficientes por prazo em `tabelas_financeiras/aymore.json`
- Parcela = valor financiado × coeficiente do prazo
- O cliente paga as parcelas diretamente para a Aymoré
- A loja recebe o valor à vista (menos taxa de repasse `[VALIDAR]`)

**Campos:**
- Valor à vista base
- Entrada
- Prazo (número de meses)
- Parcela calculada automaticamente

---

## 6. Cartão de Crédito

**Status:** `[IMPLEMENTADO]`

Duas opções disponíveis:

### 6a. Opção Preferencial — Itaú
- Taxas negociadas com o banco parceiro
- Taxas menores que o mercado
- Tabela em `tabelas_financeiras/cartao_credito.json`

### 6b. Opção Mercado
- Taxas de mercado padrão
- Usada quando o cliente não passa na opção preferencial
- Tabela em `tabelas_financeiras/cartao_credito_x.json`

**Regras comuns:**
- O acréscimo de juros é calculado por gross-up (embutido no valor final)
- Fórmula: `Valor cliente = Valor à vista / (1 − taxa%)`
- O cliente paga o valor acrescido em N parcelas
- Prazo mínimo: 2x | Prazo máximo: `[VALIDAR]` meses

**Campos:**
- Valor à vista base
- Número de parcelas
- Taxa por parcela (lida da tabela)
- Valor da parcela calculado automaticamente
- Total pago pelo cliente

---

## Cálculo de margens

A função `calcular_margens()` em `mod_margens.py` processa a seguinte sequência:

```
Valor bruto
    → × (1 − desconto%)           = Saldo após desconto
    → / (1 − custo_financeiro%)   = Saldo após financeiro (gross-up)
    → − custo_viagem (rateado)     = Saldo após viagem
    → − brinde (fixo/amb)          = Saldo após brinde
    → × (1 − arq%)                = Saldo após arquiteto
    → × (1 − fid%)                = Valor líquido final (margem da loja)
```

**Importante:** Os itens após "Saldo após financeiro" são custos **internos** da loja — não aparecem para o cliente.

---

## Arquivos relevantes

- `mod_fin/` — módulos de cálculo financeiro
- `mod_margens.py` — cálculo de margens
- `tabelas_financeiras/` — tabelas de taxas e coeficientes
- `static/index.html` — painéis de simulação financeira
