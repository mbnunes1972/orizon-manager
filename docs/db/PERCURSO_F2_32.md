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

---

# Percurso da leva de 07/09 — F2-37 a F2-40

Escrito em 07/09. **Atenção: são QUATRO pacotes numa tag só.** A última implantada é a
`v2026.09.06-beta2`, que contém até o F2-36; F2-37, F2-38, F2-39 e F2-40 sobem juntos. Percorra
os quatro blocos, mesmo que só o último pareça novo — é a primeira vez que os três do meio veem
uma tela de verdade.

> Regra do percurso, de novo: quando um passo falhar, **pare ali** e anote o número que apareceu
> ao lado do esperado.

## A — Item Especial na tela (F2-37)

1. Na negociação, botão **Item Especial** ao lado de "Novo Ambiente". Lançar um valor.
2. Esperado: linha na tabela de ambientes, **Desc. % fixo em 0 e não editável**, à vista pelo
   valor cheio, e "Com financiamento" pelo mesmo fator das outras linhas.
3. O rodapé da tabela **não pode somar duas vezes** — o total à vista tem que continuar igual ao
   Valor à Vista do cabeçalho.
4. Zerar o item pela caixa: a linha some. **Apagar o campo** (deixar vazio) e salvar: mesma coisa.
   Era isso que estava quebrado antes do F2-37, então vale testar os dois jeitos.
5. A caixa de edição mostra **R$ formatado** enquanto se digita.

## B — Item Especial fora das bases (F2-38)

Este é o bloco dos números; vale abrir o painel de provisões antes e depois.

6. Com um Item Especial lançado, conferir no painel da AF:
   - **comissões** (administrativa, venda, medidor, projeto) **não mudam** com o item;
   - **montagem, garantia, assistência, frete local, insumos** **não mudam**;
   - **imposto muda** — é a única coisa que o item alcança;
   - a **margem em reais** cai exatamente o valor do imposto do item, e nada além.
7. Se o item for grande, conferir que a **faixa de comissão de venda não sobe** por causa dele.

## C — Painel da AF (F2-39)

8. Todos os campos do painel agora têm **formato monetário**. Digitar 4000 → "R$ 4.000,00";
   aprovar → o valor gravado é 4000,00. Testar também 12345,67, para o ponto de milhar não virar
   separador decimal.
9. **Item Especial aparece como linha** no painel, não editável, com a coluna **"Atual"** mostrando
   o saldo de 2.1.04.22.
10. **Outros Fornecedores voltou a aceitar redução.** Sequência: subir de 0 para 3.000, baixar
    para 1.000, zerar. A cada passo, `2.1.04.06 + 2.1.04.14` tem que continuar igual ao CFO
    congelado. Valor negativo continua recusado.
11. O Item Especial **não se move** em nenhum desses passos.

## D — Complemento (F2-40)

12. Na **Aprovação do Projeto Executivo (11e)**, botão **Gerar Complemento** no cabeçalho do card
    — e **não** mais no bloco de upload de XML.
13. O modal abre com a tabela contrato × complemento × diferença, coluna de **desconto por
    ambiente** e os totais. Ambiente sem diferença: campo desabilitado, "—" em A cobrar.
14. **Não existe campo de desconto global** — se aparecer um, é defeito: o motor o neutraliza.
15. Desconto acima do limite do perfil: pede autorização, pela trava que já existe.
16. **Condição de pagamento**: escolher e conferir que o Termo Aditivo sai com ela. Se o aditivo
    sair à vista sem ninguém ter escolhido, é o defeito que o pacote mandou evitar.
17. **Gerar Termo Aditivo** → aditivo criado sobre o complemento certo.

## E — Aprovação financeira fora da vista (F2-40 Fatia 3)

18. Entrar com um perfil **sem** `pode_aprovar_financeiro` (um consultor) e percorrer o ciclo:
    as etapas **8 e 11d não aparecem** — nem aba, nem card, nem aviso de restrição.
19. A navegação do ciclo continua funcionando de ponta a ponta, e as etapas seguintes continuam
    esperando corretamente a aprovação de quem pode.

## F — Exploratório, se sobrar fôlego: o caminho "Cobrar" da AF2

[ABERTO 07/09] Medido: existem **zero** complementos por fase em Homologação. O mecanismo tem
rota, dimensão própria no Termo Aditivo e mensagem de sucesso — e nunca produziu uma linha.

20. Na AF2 (11d), com divergência de PE, clicar **Cobrar** e gerar o complemento da fase.
21. Conferir que a mensagem aponta o **nome do orçamento** e que ele aparece no seletor de
    orçamentos, negociável como qualquer outro.
22. Anotar o que quebrar. É a primeira vez que esse caminho é percorrido desde 14/08.
