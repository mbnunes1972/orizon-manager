# F2-42 — Rodada 2: fonte única do complemento + interface

Fecha o que a Rodada 1 (`docs/db/TAREFA_F2_41_FONTE_UNICA_COMPLEMENTO.md`) abriu, agora com o
mecanismo IDENTIFICADO, e junta os seis acertos de interface dos dois testes do Marcelo
(`Testes/2026-09-08 Teste_Revisão_PE.docx`, seções 1-3 e "Segundo Teste").

## A causa, medida — não é mais hipótese

Segundo teste, Projeto 11, oito ambientes, todos marcados. Divergência (modal − tela) dividida
pela variação relativa de cada ambiente:

| Ambiente | Divergência | Variação | Parcela fixa implícita |
|---|---|---|---|
| AArea Gourmet | +0,25 | +0,38% | 65,2 |
| ADespensa e chapelaria | +3,73 | +5,62% | 66,4 |
| Alavanderia | −11,68 | −17,58% | 66,4 |
| AQuarto Filho | +4,57 | +6,89% | 66,3 |
| ASala de tv TERREO | −0,25 | −0,38% | 66,3 |
| ASala superior | −0,53 | −0,80% | 66,5 |
| ASuite Master closet | −1,63 | −2,45% | 66,5 |
| ASuite Master PAINEIS | −4,88 | −7,36% | 66,3 |

Oito ambientes, de R$ 9,5 mil a R$ 63 mil, variações de −17,58% a +6,89%, nos DOIS sentidos —
**a mesma parcela fixa de ≈ R$ 66,40 em todos**, independente do tamanho. E 66,40 × (soma das
variações) = −10,40, contra os −10,42 observados na diferença dos totais.

A linha que produz isso é `mod_negociacao.py:80-81`:

```python
num_via = (cust_via * (vbva / den_via)) if (tog_cvia and den_via > 0) else 0.0  # PROPORCIONAL ao bruto
num_bri = (bri / den_bri) if (tog_bri and den_bri) else 0.0                     # IGUAL por ambiente
```

- **Viagem** é rateada proporcionalmente ao bruto do ambiente ⇒ comporta-se como percentual ⇒ a
  proporção a reproduz exatamente ⇒ **divergência zero**.
- **Brinde** é dividido em partes IGUAIS ⇒ é a parcela fixa `F = (bri/n) × fator_desc` ⇒ a
  proporção o multiplica junto com a mercadoria ⇒ **é a divergência inteira**.
- **Custo Especial** é linha do orçamento, não rateada nos ambientes (`mod_negociacao.py:130`, e
  o docstring de `_complemento_diferencas` diz o mesmo) ⇒ não entra no à vista por ambiente ⇒
  não pode causar divergência por ambiente.

Álgebra: `VAVA_i = k·VBVA_i + F`. A proporção calcula `k·VBVA_pe + F·(VBVA_pe/VBVA_ct)`; o motor
calcula `k·VBVA_pe + F`. Divergência = `F × (VBVA_pe/VBVA_ct − 1)`.

**Decisão do Marcelo (08/09): bater exato. O motor é a fonte única.** O motor não muda — ele
sempre foi a referência; muda quem lê.

## Parte A — fonte única

Os três consumidores de `valor_complemento_por_fator` **se movem juntos** (foram unificados em
15/08 exatamente para não divergirem entre si):

1. `_complemento_diferencas` (`main.py:17779`)
2. `_complemento_diferencas_fase` (`main.py:17964`)
3. `diferenca_valor_contrato_estimada` (`mod_conciliacao_pe.py:125`) — decisão/exibição da AF2,
   consumida em `main.py:2753`, `8058` e `17984`

O que fazer:

- O `diferenca` de cada linha passa a vir do **motor** — o valor que a sombra da Rodada 1 já
  calcula em `vava_motor`. A proporção deixa de decidir o que se cobra.
- **Inverter a sombra**: `vava_motor` vira o valor oficial e a proporção passa a ser o número
  sombra (`vava_proporcao`), mantendo `divergencia` e `divergencia_total` no resumo. Continuamos
  enxergando a diferença, agora do outro lado.
- **Fallback**: se o motor não puder rodar (sem orçamento contratado, exceção), cai na proporção
  e **registra no log com um prefixo próprio** (`[F2-42-FALLBACK]`). O fallback é exceção
  observável, nunca caminho silencioso.
- Comentário no código citando a medição acima e `mod_negociacao.py:80-81` — para que quem
  encontrar isso daqui a seis meses saiba por que o motor, e não a proporção.
- **Não** criar uma terceira conta: nada de replicar por fora o rateio do brinde para "consertar"
  a proporção. Ou o motor decide, ou não decide.

## Parte B — o experimento controlado vira teste commitado

O Claude Code montou este experimento fora dos testes na Rodada 1 e ele ficou só na conversa
(registrado em `CADERNO_DE_BORDO.md`, 08/09). Agora entra com nome próprio:

1. Contrato só com rubricas percentuais (comissão arq/fid), brinde = 0, viagem = 0 → divergência
   entre as duas fórmulas **exatamente zero**.
2. Mesmo contrato + **viagem** > 0, brinde = 0 → divergência **exatamente zero** (viagem é
   proporcional).
3. Mesmo contrato + **brinde** > 0 → divergência **diferente de zero**, e igual a
   `(brinde/n) × fator_desc × (VBVA_pe/VBVA_ct − 1)` para cada ambiente, dentro do arredondamento
   de centavos.
4. Custo Especial > 0, brinde = 0 → divergência **zero** (ele não é rateado por ambiente).

O teste 3 é o que prova a CAUSA; os outros três são os controles que a isolam.

## Parte C — interface

Seis itens, dos dois testes.

**C1. Texto do Item Especial** (`static/index.html:11591-11593`). Trocar o parágrafo atual por,
exatamente: **"Produto ou serviço negociado pelo valor de custo. Este item não tem aplicação de
descontos."** Sem a referência a ACHADO no texto visível (ela fica em comentário no código).

**C2. JSON cru da forma de pagamento no modal.** Hoje o modal despeja o objeto inteiro na tela —
no segundo teste, com dez parcelas, ocupou seis linhas. Substituir por um resumo legível de uma
linha: forma, valor total e parcelamento (ex.: `Cartão de Crédito — 10× R$ 751,14` /
`À vista — R$ 1.864,71`), mantendo o botão "Alterar" ao lado. O JSON não aparece em tela em
hipótese nenhuma.

**C3. Rodapé do modal.** "Diferença bruta" passa a ser **"Diferença"**. Fica **uma linha só**,
com o valor a cobrar — sem a linha "Desconto" e sem repetir o valor em "Complemento". Quando
houver desconto por ambiente diferente de zero, a linha fica "Diferença (com desconto)", para
não mentir sobre o número. *(Julgamento meu sobre o caso com desconto — o Marcelo pediu "não
mencionar desconto"; no caso normal, desconto zero, a linha sai limpa como ele pediu.)*

**C4. Salvar sem ação aparente** na tela de negociação do complemento. Ao salvar, deve **voltar
para a tela de aprovação do PE**, de onde se gera o aditivo. Hoje não há retorno e o usuário
fica sem saber se salvou.

**C5. O botão "Definir forma de pagamento" some depois do primeiro uso.** **MEÇA a causa antes
de corrigir** — não presuma. A hipótese óbvia (a trava "geração bloqueada até existir plano de
pagamento" invertida) pode estar errada; relate o que a medição mostrar. O comportamento certo:
o botão continua alcançável enquanto o complemento não virou aditivo assinado.

**C6.** Coberto por C1.

## Aceite

**O gabarito é o Projeto 11 do segundo teste.** Depois da Parte A, o modal do complemento tem que
mostrar EXATAMENTE os valores da tela de Revisão de PE:

| Ambiente | À vista (complemento) esperado |
|---|---|
| AArea Gourmet | 9.546,52 |
| ADespensa e chapelaria | 15.237,98 |
| Alavanderia | 15.814,03 |
| AQuarto Filho | 58.968,39 |
| ASala de tv TERREO | 18.717,78 |
| ASala superior | 26.645,93 |
| ASuite Master closet | 61.388,66 |
| ASuite Master PAINEIS | 32.331,52 |
| **Total** | **−3.118,72** (era −3.129,14) |

Mais:

1. Os quatro testes de propriedade da Rodada 1 continuam verdes.
2. Os quatro testes da Parte B, verdes.
3. Os três consumidores movidos juntos — provado por teste que compara a grandeza da AF2 com a do
   complemento no mesmo cenário.
4. `[F2-42-FALLBACK]` não aparece em nenhum cenário de teste normal.
5. Nenhum JSON visível em tela em nenhum estado do modal.
6. C4 e C5 provados por E2E.
7. Camadas b + c + d verdes; E2E um a um.

## NÃO AUTORIZA

- Tocar `mod_negociacao.calcular_orcamento`. O motor está certo; ele não é o alvo.
- Replicar o rateio do brinde fora do motor para "consertar" a proporção — seria uma terceira
  conta para o mesmo número.
- Mover só um ou dois dos três consumidores.
- Remover a sombra: ela inverte de lado, não sai.
- Tocar Produção.
