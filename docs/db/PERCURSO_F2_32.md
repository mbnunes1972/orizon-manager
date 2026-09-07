# Percurso de teste — F2-31 (ACHADO-61) + F2-32 (ACHADO-63/64)

Escrito em 06/09/2026 para o Marcelo executar em Homologação. Ordem importa: o
bloco A gasta o momento único da assinatura do Projeto 8; o bloco B pode ser
repetido à vontade em qualquer orçamento não assinado.

**Antes de começar:** confirmar que a build em Homologação contém as duas
frentes. Se o F2-32 ainda não tiver fechado, fazer só o bloco A.

> Regra do percurso: quando um passo falhar, **parar ali** e anotar o número que
> apareceu ao lado do esperado. Seguir adiante com um passo vermelho embaralha a
> causa — foi assim que o ACHADO-59 escondeu o ACHADO-61 por um dia.

---

## Bloco A — Outros Fornecedores nasce no contrato (ACHADO-61)

Projeto 8, ainda sem contrato. Este bloco tem um tiro só: a assinatura acontece
uma vez.

**A1. Antes de assinar** — na tela de Parâmetros da negociação, lançar
**R$ 2.000,00** em Outros Fornecedores. Salvar.
- Esperado: o valor aparece no painel e entra no Custo Variável.

**A2. Fechar o contrato.** Abrir os lançamentos do projeto e procurar o lote da
assinatura.
- Esperado: um lançamento **débito 1.1.06.14 × crédito 2.1.04.14, R$ 2.000,00**.
- Esperado: a Provisão de Custo de Fábrica (2.1.04.06) igual ao **CFO congelado
  integral**, sem desconto nenhum.
- Se o Custo de Fábrica vier reduzido em 2.000: a regra econômica saiu trocada
  (no contrato a rubrica é aditiva, não substitutiva). Parar.

**A3. AF1 — subir Outros Fornecedores de 2.000 para 4.000.** Aprovar.
- Esperado: migração de **2.000** (a diferença), não de 4.000.
- Esperado: 2.1.04.14 = 4.000,00 e 2.1.04.06 = CFO congelado − 2.000,00.
- Esperado no registro da revisão: a coluna Rev1 de Custo de Fábrica bate com a
  coluna "Atual" (o snapshot fecha consigo mesmo — F2-30 Fatia 1).

**A4. NÃO TESTAR AINDA: baixar o valor de Outros Fornecedores na AF.**
Esse é o ACHADO-62, conhecido e ainda não consertado (F2-31 Fatia 2 escrita, não
entregue). A tela aceita a redução e o razão não se mexe. Não é o pacote novo
falhando.

---

## Bloco B — o desconto e o Valor Bruto (ACHADO-63/64)

Pode ser feito em qualquer orçamento não assinado. Usar valores redondos para a
conferência ser de cabeça. Ligar o toggle master de custos adicionais (repassar
ao cliente) — com ele desligado nada disto se aplica.

**B1. Linha de base.** Sem nenhum custo adicional, anotar o Valor Bruto e o Valor
à Vista com desconto **0%**. Chamar o Bruto de `M`.

**B2. Desconto de 30%, ainda sem custos.**
- Esperado: Bruto continua `M`; à vista = `M × 0,70`.

**B3. Uma rubrica de cada vez, com o desconto de 30% ligado.** Para cada uma —
**Custo de Viagem**, **Brinde**, **Custo Especial** — lançar **R$ 1.000,00**,
conferir, e zerar antes de passar à seguinte:
- Esperado: **Bruto = `M` + 1.000,00**, exatamente. O Bruto **não pode** mudar
  quando o desconto muda.
- Esperado: **à vista = Bruto × 0,70**, exato até os centavos.
- Esperado: o Valor Líquido cai **300,00** em relação ao B2 (= 1.000 × 30%).
  Essa queda é a correção funcionando, não regressão: é a parte do custo que o
  cliente não pagou.
- Conferência cruzada: com o desconto em 0%, o Bruto tem que ser o mesmo
  `M` + 1.000,00. Se ele mudar ao mexer só no desconto, o achado voltou.

**B4. As três juntas + comissão de arquiteto e fidelidade.** Viagem 1.500,
brinde 1.000, custo especial 800, desconto 25%.
- Esperado: **à vista = Bruto × 0,75**, diferença 0,00.
- Esperado: o Valor Líquido menor em **825,00** (= 3.300 × 25%) que o mesmo
  cenário sem os três custos.
- Esperado: comissão de arquiteto e fidelidade se comportam como sempre — o
  Bruto delas nunca dependeu do desconto.

**B5. As duas colunas nos parâmetros.** No painel de apoio, cada uma das três
rubricas mostra o que **custa** e o que o **cliente paga**.
- Esperado com 25%: brinde "custa R$ 1.000,00 / cliente paga R$ 750,00".

**B6. O desconto efetivo.** No quadro do Valor de Contrato, acima dos botões.
- Sem desconto por ambiente: igual ao percentual digitado.
- Com desconto por ambiente: **maior** que o digitado. Exemplo conferível — 25%
  global e 10% num ambiente que vale ~30% do orçamento dá algo perto de 27,3%.
  O que tem que fechar sempre: **à vista = Bruto × (1 − efetivo)**.
- Este número **não é** o da trava de autorização (que usa o pior ambiente,
  32,5% no mesmo exemplo). São dois números diferentes de propósito.

**B7. O campo "Total do Contrato" (ACHADO-64).** Clicar no valor, digitar um
total e sair do campo.
- Esperado: o à vista fecha **exatamente** no valor digitado e o campo de
  desconto recebe o percentual correspondente. Antes deste pacote, digitar ali
  não fazia absolutamente nada.
- Repetir com uma modalidade parcelada (taxa de retenção > 0): o valor digitado
  é o **contrato**; o à vista é o contrato menos o custo financeiro.
- Digitar um valor maior que o Bruto: a recusa que já existe aparece, sem gravar.

**B8. Recalcular ao sair da célula.** Editar uma rubrica no painel da AF e sair
do campo com Tab.
- Esperado: os totais atualizam sem precisar salvar. (Se ainda não atualizarem,
  é a F2-31 Fatia 2 / F2-32 Fatia 3 pendente, não regressão.)

---

## O que observar de canto de olho, nos dois blocos

- **A margem vai parecer pior** em todo projeto com viagem, brinde ou custo
  especial. É a perda que já existia e não aparecia. Ordem de grandeza medida:
  0,38 ponto percentual num caso de 3.300 de custos a 25%.
- **A trava de margem líquida negativa fica mais perto.** Um orçamento no limite
  pode passar a ser recusado onde antes passava. Se isso acontecer numa venda de
  verdade, anotar os números — é comportamento esperado, mas o limite pode
  precisar de recalibração.
- **Orçamentos em aberto mudam de número** no próximo save. Contratos assinados
  não mudam (usam o VAVO gravado na assinatura).
