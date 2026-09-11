# TAREFA F2-43 — o plano de pagamento estranho ao entrar no Complemento

Achado de percurso em Homologação, candidato `v2026.09.09-beta1` (`871817b`),
09/09/2026. Frente aberta imediatamente depois do F2-42.

## O sintoma, como foi visto

Na etapa 11e, cliquei em **"Negociar Complemento"** e segui para a
negociação (handoff de "Definir forma de pagamento"). A tela abriu numa
**negociação à vista** — modalidade certa — mas com um **plano de pagamento
estranho**: valores que não correspondem ao complemento e **juros aparentes**
numa condição que não tem juros.

Selecionei **Cartão de Crédito** e voltei para **À vista**. O problema
**desapareceu** — a tela passou a mostrar o plano correto do complemento.

## O que esse "desapareceu" já diz, e o que não diz

Diz que o **dado persistido provavelmente está certo** e que o defeito está
na **primeira renderização**: trocar de modalidade e voltar é um
*re-render*, não uma correção de dado. Se o `forma_pagamento` gravado
estivesse errado, ir e voltar não consertaria.

**Não diz** qual estado sobrou de quem. Não conclua isso da minha descrição —
meça.

## Medir ANTES de consertar

Esta é a regra do projeto e ela já se pagou duas vezes nesta mesma frente
(o C5 do F2-42: minha hipótese de trava invertida não bateu com o código; a
premissa do F2-40 sobre a 11c também estava errada). **Meça primeiro, e me
diga o que mediu antes de escrever conserto.**

### Passo 1 — reproduzir e fotografar o estado

Reproduza o caminho exato: 11e → "Negociar Complemento" → "Definir forma de
pagamento" → tela de negociação. No momento em que a tela abre, **antes de
tocar em qualquer coisa**, colha:

- `_orcamentoAtivoId`, `_pagamentoDoOrc`, `_tipoAtivo`, `_codigoPagAtivo`;
- `window._planoPagamento`;
- o `forma_pagamento` **persistido** do orçamento de complemento
  (`GET /projetos/<nome>/orcamentos`, campo `forma_pagamento`) e o do
  orçamento **contratado**;
- o conteúdo visível de `#neg-parcelado`, `#av-liq-valor`, `#neg-total`,
  `#neg-total-final`, `#neg-avista`.

Depois troque para Cartão, volte para À vista, e colha **os mesmos oito**.
A diferença entre as duas fotos é o defeito.

### Passo 2 — de quem é o número que apareceu

Compare o plano estranho contra o **plano do orçamento contratado**. Se os
valores/parcelas/juros forem os do contratado, é vazamento de estado entre
orçamentos. Se não forem de ninguém, é cálculo derivado sobre base errada.
São defeitos diferentes e o conserto é diferente.

## Candidatos a medir (hipóteses, não conclusões)

Levantei três ao ler o código. Trate como pistas, não como diagnóstico.

**(a) A ordem entre `_resetPagamentoPadrao()` e `avistaRecalcular()`.**
Em `static/index.html` ~11145-11155, na troca de orçamento sem negociação
salva, o caminho é: `carregarModalidades()` → se não há `_negociacaoPendente`
e `!_mesmoOrc` → `await _resetPagamentoPadrao()` (à vista, entrada R$ 0,00).
Já as caixas derivadas da modalidade à vista — "Valor Total do Contrato"
(`#neg-parcelado`), "Valor da liquidação" (`#av-liq-valor`) e
`window._planoPagamento` — só se atualizam por `avistaRecalcular()`, chamada
de `_aplicarPreviewNaTela` **sob o gate `_tipoAtivo === 'avista'`**
(~11715). Se o preview do motor rodou **antes** de `_tipoAtivo` virar
`'avista'`, ou se `_resetPagamentoPadrao` não dispara um preview depois de
si, essas três caixas ficam com o que estava na tela. Trocar de modalidade e
voltar dispara `onPagamentoChange` → recalcula → some. **Meça a ordem real
das chamadas**, com log ou breakpoint, não por leitura.

**(b) O guard `_mesmoOrc` cobrindo só metade do caminho.**
O vazamento "modalidade/entrada/total do CONTRATADO apareciam no complemento"
**já foi achado e consertado antes** (comentário em ~11141-11147, "teste do
usuário"): a captura de `_capturarNegociacao()` passou a exigir
`_pagamentoDoOrc === _orcamentoAtivoId`. Verifique se o guard cobre **todos**
os pontos que escrevem a barra de pagamento, ou se protege a captura e deixa
solto o *render*. Se for isso, é o mesmo defeito por outra porta —
**regra dos irmãos (ACHADO-26)**: enumere todo caminho capaz de popular
`#neg-parcelado`/`window._planoPagamento`, não conserte o que eu descrevi.

**(c) Precedente idêntico, 2026-08-17.** O comentário em ~11708-11714
descreve exatamente esta classe: as caixas da modalidade à vista "só
atualizavam via `avistaRecalcular()`, disparada pelo `oninput` dos campos —
nunca ao só CARREGAR/VER o orçamento. Ficavam com o que a tela restaurou do
`forma_pagamento` SALVO, desatualizado assim que desconto/ambientes mudam
depois de salvo — chegou a mostrar um Total do Contrato MENOR que o Valor à
Vista, impossível pela fórmula real." O conserto de então foi chamar
`avistaRecalcular()` no preview. **Se o defeito de hoje é a mesma doença numa
terceira porta, o conserto tem que fechar a classe, não a instância** — foi
o que o F2-40 fez com os cinco lugares que decidiam o lock.

## Fronteira do que estou pedindo

- **Não é** para mexer no motor (`mod_negociacao.calcular_orcamento`). Se o
  número do complemento estiver certo depois do re-render, o motor está
  certo — o defeito é de tela.
- **Não é** para duplicar a barra de pagamento no modal. Foi medido no F2-40
  que ela é uma sidebar de ~154 ids fixos, nunca pensada para duas
  instâncias, e a decisão de não duplicar continua valendo.
- **Não é** para tocar em Produção, nem cortar tag, sem pedido.
- Se a medição mostrar que o **dado persistido** está errado (e não só o
  render), **pare e me conte** antes de consertar — aí a decisão é minha,
  porque mexe no que é cobrado.

## O que eu quero de volta

1. As duas fotos do Passo 1, lado a lado, e a resposta do Passo 2: **de quem
   era aquele número**.
2. A enumeração dos irmãos — todo caminho que popula a barra de pagamento na
   troca de orçamento — antes de qualquer conserto.
3. Só então o conserto, com **teste primeiro**: um `xfail(strict=True)` que
   descreve o defeito, e que vira verde e obriga a remover o marcador quando
   o conserto entra.
4. Um E2E que prove o caminho inteiro: 11e → Negociar Complemento → Definir
   forma de pagamento → **a tela abre com o plano certo na primeira
   renderização**, sem precisar trocar de modalidade e voltar.
5. Verificação em camadas, como nas rodadas anteriores.

## Contexto que ajuda

- Este caminho é novo: o handoff de pagamento entrou no **F2-40** (08/09) e o
  modal foi reescrito no **F2-42** (fechado 00h40 de 09/09). **Ninguém
  percorreu a versão final antes de mim.**
- O item **8.4.5/8.4.6** do `docs/db/PERCURSO_HOMOLOGACAO.md` cobre este
  trecho; o defeito apareceu ali.
- `peComplModalDefinirPagamento()` (~22351) faz
  `fecharCiclo() → goPage(2) → carregarOrcamentos() → ativarOrcamento(st.orcId)`.
  `ativarOrcamento` (~8160) chama `_aplicarFiltroOrcamento` e o helper do
  lock, e **não** repõe a barra de pagamento por conta própria — quem faz
  isso é a cadeia de `carregarModalidades`/`_restaurarNegociacao`/
  `_resetPagamentoPadrao`.
- `_restaurarNegociacao(snap)` (~8960) **retorna cedo** quando `snap` não tem
  `codigo`. Verifique o que fica na tela nesse retorno.
