# ADR — Ciclo é UM fluxo, apresentado em DUAS visões (Comercial × Execução)

**Data:** 2026-07-14 · **Status:** decisão aceita (registrar; implementação de UX futura, sem urgência).

## Contexto

Discutiu-se separar o ciclo em dois **módulos**: Orçamentos conteria o ciclo **até a assinatura do
contrato**; as demais fases migrariam para Projetos. A fronteira (assinatura) é real — antes é **venda**,
depois é **execução** —, com personas diferentes.

## Decisão

**NÃO partir o ciclo em dois módulos de dados. Manter UM ciclo (fonte única, escopo do PROJETO) e
apresentá-lo em DUAS VISÕES/lentes**, filtradas por faixa de etapa:

- **Orçamentos / Comercial** — lente **pré-assinatura** (etapas **1–7**: Cadastro → Contrato) + ferramentas
  de orçamento/negociação. Onde o **consultor** trabalha.
- **Projetos / Execução** — lente **pós-assinatura** (etapas **8+**: AF → Especificação Técnica → Produção →
  NF-e → Entrega → Montagem → Conciliação) + cronograma/agenda/logística. Onde **operação/gerência** trabalha.

A **assinatura do contrato é o "handoff"** (Comercial → Execução), sem duplicar dado. A **AF (8) já cai em
Projetos** (fronteira limpa: 7 = último passo de venda; 8 = primeiro de execução). O **transversal**
(auditoria contábil, agenda, cronograma) vive no **nível do projeto** e **lê o ciclo inteiro** (atravessa a
fronteira).

## Porquê

- O **Projeto é a espinha** (`projeto_meta.nome_safe` nasce no Cadastro); o **Orçamento é filho** do projeto
  (vários por projeto, EP-07). Colocar o ciclo inicial "em Orçamentos" **inverteria a hierarquia**.
- O ciclo é **chaveado por projeto** (`CicloEtapa.projeto_nome`), não por orçamento — partir brigaria com o
  modelo de dados.
- **Continuidade**: auditoria/agenda/cronograma atravessam a vida inteira do projeto; fragmentar em dois
  módulos perderia a visão contínua.
- **Risco**: `mod_ciclo`/gating/status/render assumem fluxo único; partir é caro e arriscado.

## Consequência

Ganha-se personas separadas, menos poluição e handoff natural na assinatura — **sem** o custo/risco de
partir o dado. Frente de **navegação/UX** (reusa Painel de Projetos + módulo Comercial), a fazer **depois**
de fechar fases/cronograma/agenda.
