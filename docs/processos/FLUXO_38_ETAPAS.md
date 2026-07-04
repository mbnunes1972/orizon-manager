# Fluxo de 38 Etapas - Processo Comercial Dalmobile

Status: [REFERENCIA] - mapeamento do processo completo
Modulo relacionado: docs/modulos/kanban/SPEC.md

---

## Visao geral

O processo comercial da Dalmobile e dividido em 6 fases,
totalizando 38 etapas desde a captacao do cliente ate o pos-venda.
Este fluxo e a base para o Kanban comercial (v0.4.0).

> NOTA: este mapeamento de 38 etapas e a referencia CONCEITUAL do processo
> comercial. O ciclo de vida REALMENTE IMPLEMENTADO no sistema e o
> **ciclo de 20 etapas** (`mod_ciclo.py` + `ciclo_etapas`), com ordem
> renumerada e gating sequencial — descrito na secao
> "Ciclo de 20 etapas implementado (reality atual)" mais abaixo e detalhado
> em `docs/modulos/projetos/SPEC.md`.

---

## Fase 1 - Pre-venda / Captacao

| Etapa | Descricao | Responsavel |
|---|---|---|
| 01 | Identificacao do lead (indicacao, visita, campanha) | Consultor |
| 02 | Primeiro contato e qualificacao | Consultor |
| 03 | Agendamento de visita a loja ou ao imove | Consultor |
| 04 | Visita e levantamento de necessidades | Consultor |
| 05 | Registro do cliente no sistema | Consultor |
| 06 | Registro do parceiro indicador (se houver) | Consultor |

---

## Fase 2 - Projeto

| Etapa | Descricao | Responsavel |
|---|---|---|
| 07 | Briefing tecnico do projeto | Consultor / Projetista |
| 08 | Elaboracao do projeto no Promob | Projetista |
| 09 | Revisao interna do projeto (Conferente) | Conferente |
| 10 | Apresentacao do projeto ao cliente | Consultor |
| 11 | Ajustes do projeto apos feedback do cliente | Projetista |
| 12 | Aprovacao final do projeto pelo cliente | Cliente / Consultor |

---

## Fase 3 - Negociacao

| Etapa | Descricao | Responsavel |
|---|---|---|
| 13 | Importacao do XML do Promob para o Orizon Manager | Consultor |
| 14 | Configuracao de margens e parametros | Consultor |
| 15 | Definicao da forma de pagamento | Consultor |
| 16 | Aplicacao de desconto (com autorizacao se necessario) | Consultor / Gerente |
| 17 | Apresentacao da proposta ao cliente | Consultor |
| 18 | Negociacao e ajuste final de condicoes | Consultor |
| 19 | Fechamento verbal do negocio | Consultor |

---

## Fase 4 - Contrato e Pedido

| Etapa | Descricao | Responsavel |
|---|---|---|
| 20 | Emissao da proposta comercial formal | Consultor |
| 21 | Assinatura do contrato pelo cliente | Cliente / Consultor |
| 22 | Registro do contrato no sistema | Consultor |
| 23 | Exportacao do pedido para o Omie | Consultor |
| 24 | Confirmacao do pedido na fabrica | Gerente / Adm |
| 25 | Registro e controle do pagamento (entrada + parcelas) | Adm / Financeiro |

---

## Fase 5 - Producao e Logistica

| Etapa | Descricao | Responsavel |
|---|---|---|
| 26 | Acompanhamento da producao na fabrica | Gerente |
| 27 | Medicao tecnica no imove do cliente | Tecnico |
| 28 | Elaboracao do projeto executivo | Projetista |
| 29 | Aprovacao do projeto executivo pelo cliente | Cliente / Consultor |
| 30 | Confirmacao de data de entrega com cliente | Consultor |
| 31 | Transporte e entrega dos moveis | Logistica |

---

## Fase 6 - Pos-venda

| Etapa | Descricao | Responsavel |
|---|---|---|
| 32 | Montagem dos moveis | Montador |
| 33 | Vistoria pos-montagem | Tecnico / Consultor |
| 34 | Aprovacao da montagem pelo cliente | Cliente |
| 35 | Abertura de ocorrencia em caso de nao conformidade | Consultor |
| 36 | Resolucao de nao conformidades | Tecnico / Fabrica |
| 37 | Pesquisa de satisfacao com o cliente | Consultor |
| 38 | Indicacao de novos clientes / recompra | Cliente |

---

## Implementacao no Kanban

O Kanban comercial (v0.4.0) representa cada etapa como uma coluna.
Cada projeto e um cartao que avanca pelas colunas conforme o processo evolui.

Agrupamento sugerido no Kanban:
- Coluna 01-06: Captacao
- Coluna 07-12: Projeto
- Coluna 13-19: Negociacao
- Coluna 20-25: Contrato
- Coluna 26-31: Producao
- Coluna 32-38: Pos-venda

---

## Ciclo de 20 etapas implementado (reality atual)

O que esta efetivamente implementado no sistema (`mod_ciclo.py`, tabela
`ciclo_etapas`, `PATCH /api/projetos/<nome>/ciclo/<codigo>`) e um ciclo de
**20 etapas principais** (algumas com sub-etapas), com **gating sequencial**.
Este e o fluxo operacional vigente; o mapeamento de 38 etapas acima permanece
como referencia conceitual do processo comercial.

### Ordem das etapas (renumerada)

| Codigo | Etapa |
|---|---|
| 1 | Cadastro do Cliente |
| 2 | Criacao do projeto |
| 3 | Briefing |
| 4 | Primeiro orcamento |
| 5 | Revisao de projeto |
| 6 | Aprovacao do orcamento pelo cliente |
| 7 | Contrato |
| 8 | Aprovacao financeira I |
| 9 | Solicitacao de medicao |
| 10 | Planta de pontos medidos |
| 11 | Projeto executivo (sub-etapas 11a-11e) |
| 12 | Implantacao do pedido |
| 13 | Producao |
| 14 | Entrega no deposito |
| 15 | Emissao da NFe do cliente |
| 16 | Entrega no cliente |
| 17 | Montagem (sub-etapa 17a) |
| 18 | Assistencia pos Montagem |
| 19 | Vistoria final |
| 20 | Aprovacao final |

> CORRECAO DE ORDEM: antes a etapa 2 era *Briefing* e a 3 era *Criacao do
> projeto*. A ordem foi INVERTIDA — agora 2 = Criacao do projeto e 3 = Briefing
> (renumeracao real, com migracao de banco trocando `etapa_codigo` 2 e 3 nas
> linhas existentes).

### Gating sequencial

Uma etapa PRINCIPAL so pode ser iniciada (`em_andamento`) ou concluida se a
principal imediatamente anterior estiver concluida.

- Backend: `PATCH /api/projetos/<nome>/ciclo/<codigo>` rejeita com HTTP 400 as
  tentativas fora de ordem; os endpoints de acao que avancam etapas (ex.:
  geracao de contrato = etapa 7) tambem validam o gating antes de executar.
- Frontend: etapas bloqueadas exibem 🔒, ficam nao-expansiveis e com acoes
  desabilitadas; so a "etapa corrente" (primeira principal nao concluida) tem
  acoes ativas.
- Sub-etapas (`11a-11e`, `17a`) sao LIVRES dentro do pai (nao entram no gating).
- Etapa 1 (Cadastro do Cliente) nao tem anterior — sempre liberada.
- Status que contam como "concluida": `concluido`, `aprovado`, `assinado`,
  `vigente`, `implantado`, `realizado`, `entregue`, `emitida`.

### Marcacao automatica e conclusoes

- Ao CRIAR o projeto: etapas 1 (Cadastro do Cliente) e 2 (Criacao) ficam concluidas; a
  3 (Briefing) fica PENDENTE e vira a etapa corrente (o Briefing e obrigatorio
  por projeto — nao nasce concluido).
- Etapa 4 (Primeiro orcamento): concluida ao salvar um orcamento com >=1
  ambiente (XML do Promob).
- Etapa 5 (Revisao): NAO tem toggle manual — e concluida automaticamente pela
  aprovacao do orcamento, junto da etapa 6.
- "Aprovar Orcamento" conclui as etapas 5 e 6 JUNTAS e entra na 7 (Contrato em
  `em_andamento`); o botao pos-aprovacao leva ao card de assinatura do contrato.

### Reabertura em cascata (gerencial)

`POST /api/projetos/<nome>/ciclo/<codigo>/reabrir` (com login + senha de nivel
gerente/diretor/admin) reabre a etapa-alvo e todas as posteriores (voltam a
`pendente`; sub-etapas dos pais afetados tambem). E auditada na tabela
`log_acoes_gerenciais` e BLOQUEADA se a cascata desfizer um contrato
assinado/vigente (etapa 7). Ha tambem `POST .../ciclo/desfazer_aprovacao`
(gerencial), que reseta as etapas 5/6/7 e devolve o contrato a rascunho.

A logica de ordem/gating fica centralizada em `mod_ciclo.py` (constante
`ETAPAS_PRINCIPAIS` + helpers `etapa_anterior` / `pode_avancar` /
`codigos_a_resetar`).

---

## Referencias

- docs/modulos/projetos/SPEC.md (ciclo de 20 etapas + gating — implementado)
- docs/modulos/kanban/SPEC.md
- docs/modulos/pos_venda/SPEC.md
- docs/historias/BACKLOG.md
