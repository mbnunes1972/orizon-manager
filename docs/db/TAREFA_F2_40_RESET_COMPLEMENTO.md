# F2-40 — Resposta à pergunta do reset em `POST /pe/complemento/orcamento`

Resposta à pergunta deixada em aberto pelo Claude Code ("read-existing-first, create-once —
sigo com esse desenho a menos que você redirecione"), com a medição que a fundamenta.

## 1. O que eu medi antes de responder

Quatro comportamentos estão hoje empacotados na MESMA chamada (`main.py:8285-8316`):

1. **Guarda do aditivo assinado** (8290-8292): se existe `Aditivo(orcamento_complemento_id=orc.id,
   status="assinado")`, `orc` vira `None` e um orçamento NOVO é criado. É o que impede que a
   mesma diferença seja vendida duas vezes.
2. **Create-if-none** (8293-8299).
3. **Resync dos vínculos** (8300-8308): adiciona `OrcamentoAmbiente` para cada `marcado` que
   falta e **deleta** os vínculos que deixaram de estar marcados.
4. **Apagar o plano de pagamento** (8312-8313): `forma_pagamento = None; negociacao_json = None`.

E medi quem lê o quê:

- `GET /pe/complemento/comparativo` (`main.py:5615`) → `_complemento_diferencas` →
  `main.py:17792`: `if not pa.renegociar_pe: continue`. **A tabela do modal lê as MARCAS da 11c,
  ao vivo. Nunca lê os vínculos do orçamento.**
- `_negociacao_breakdown` (`main.py:18443-18455`): itera
  `OrcamentoAmbiente.filter_by(orcamento_id=orc.id)` — **os VÍNCULOS** — e busca o valor em
  `compl_diff`, que vem das marcas ao vivo. Ou seja, o que é negociado é a **interseção**
  marcas ∩ vínculos.
- `_aditivo_dados_calculo` (`main.py:18003+`): as linhas do Termo Aditivo vêm de
  `_negociacao_breakdown(orc_aj)` — portanto, dos **vínculos**.

Consequência aritmética de largar o resync:

- Ambiente **marcado depois** da criação do orçamento: aparece na tabela do modal com sua
  diferença, mas o loop de `_negociacao_breakdown` nunca o visita → **não entra na negociação e
  não entra no aditivo**. Cobrança a menos, silenciosa, com a tela mostrando um número que o
  documento não carrega. É a família ACHADO-16/55 (o documento da decisão não fecha com o livro).
- Ambiente **desmarcado depois**: o vínculo sobrevive, `compl_diff.get(pid, 0.0)` = 0 → linha
  fantasma de valor zero. Inofensivo no número, feio na tela.

Hoje isso **não acontece**, e o motivo é exatamente o resync: o fluxo atual é
`abrirModalComplemento()` (`static/index.html:22181`, só lê o comparativo) → botão →
`peComplementoNegociar()` (`22223`) faz o POST, que resincroniza, e só então leva o usuário para
a página 2. Marcas e vínculos são idênticos no instante em que a negociação começa.

## 2. Decisão

**Aprovado o read-existing-first / create-once**, com três condições.

**(a) A guarda do aditivo assinado fica exatamente como está.** "Create-once" não pode significar
"reusar sempre": se há aditivo assinado apontando para o orçamento, o caminho continua sendo
criar um NOVO. Alteração depois da assinatura é evento novo, nunca sobrescrita.

**(b) O resync dos vínculos NÃO sai da chamada.** Continua incondicional, em toda chamada,
exatamente como está em 8300-8308. Ele não é um efeito colateral do reset — é o que garante que
a tabela que o gerente lê e o aditivo que o cliente assina falem do mesmo conjunto de ambientes.
A "lacuna do resync" levantada na pergunta não é aceitável para embarcar: sem ele, o caso
"marcou depois" cobra a menos e ninguém vê.

**(c) Só o apagar do plano de pagamento vira condicional.**
`forma_pagamento = None; negociacao_json = None` passa a rodar quando:

- o orçamento foi **criado nesta chamada** (inclusive o caso da guarda (a)); **ou**
- o corpo do POST trouxer `{"reiniciar": true}` — o caminho explícito para "recomeçar a
  negociação do zero".

Reabrir um complemento já negociado deixa de apagar o plano de pagamento salvo.

Por que isto é seguro agora: esse apagar nasceu para descontaminar o vazamento em que o painel do
contratado era capturado pela tela e persistido no complemento via auto-save (o `total_cliente`
do CONTRATO virando `cust_fin` do complemento). Esse vazamento tem hoje duas guardas próprias, a
montante: `_carregandoOrcamento` suprime o auto-save durante a carga
(`static/index.html:10485`) e `_ultimoPagSig` bloqueia o ciclo preview→painel→save (`10490`).
O apagar virou cinto sobre suspensório — e o preço dele é apagar o trabalho do gerente toda vez
que ele reabre a tela, que é justamente o que a tela nova da F2-40 vai fazer com frequência.

## 3. O que fazer

- `main.py:8285-8316`: manter (1) e (3) incondicionais; mover (4) para dentro de uma condição
  `if _criou_agora or bool(req.get("reiniciar")):`. Comentário no lugar do atual explicando as
  duas guardas do auto-save (com os números de linha do `index.html`) e por que o apagar deixou
  de ser incondicional.
- O modal da Fatia 2 chama o POST **sem** `reiniciar`. Se houver "recomeçar a negociação", que
  seja um botão explícito dentro do modal que reenvia com `{"reiniciar": true}` — não o
  comportamento default de abrir a tela.
- Nada muda em `_complemento_diferencas`, `_complemento_diferencas_fase`,
  `_negociacao_breakdown` ou `_aditivo_dados_calculo` neste pacote.

## 4. Aceite (o que eu vou pedir para ver)

1. Teste: complemento criado com 2 ambientes marcados → marca um 3º na 11c → reabre o modal e
   negocia → `_negociacao_breakdown` do complemento traz **3** linhas e o
   `_aditivo_dados_calculo` também. (Prova que o resync sobreviveu.)
2. Teste: complemento criado com 3 ambientes → **desmarca** um → reabre → o breakdown traz 2
   linhas, sem linha fantasma de zero.
3. Teste: complemento negociado com plano de pagamento salvo (parcelado, entrada > 0) → segunda
   chamada ao POST **sem** `reiniciar` → `orc.forma_pagamento` e `orc.negociacao_json`
   **preservados**; terceira chamada **com** `{"reiniciar": true}` → ambos `None`.
4. Teste: aditivo assinado apontando para o complemento → POST → orçamento **novo** (id
   diferente), com o plano de pagamento zerado.
5. Camadas b + c (módulos tocados + subconjunto contábil/negociação) verdes.

## 5. NÃO AUTORIZA

- Tocar Produção.
- Alterar `_complemento_diferencas`, `_complemento_diferencas_fase` ou a fórmula do fator.
- Remover ou condicionar o resync dos vínculos.
- Remover a guarda do aditivo assinado.
- Mexer nas guardas de auto-save do `index.html` (`_carregandoOrcamento`, `_ultimoPagSig`) — se
  elas caírem, o apagar incondicional volta a ser necessário.
