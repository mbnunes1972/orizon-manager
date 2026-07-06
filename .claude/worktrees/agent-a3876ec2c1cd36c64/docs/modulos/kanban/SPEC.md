# Módulo Kanban — SPEC

**Status:** `[TODO]`

---

## Visão geral

Painel visual de gestão do pipeline comercial e operacional. Permite acompanhar todos os projetos em andamento por fase, identificar gargalos e priorizar ações.

---

## Boards previstos

### 1. Pipeline Comercial
Acompanha projetos da prospecção até o contrato assinado.

| Coluna | Descrição |
|---|---|
| Lead | Cliente cadastrado, sem projeto |
| Briefing | Projeto criado, aguardando XML |
| Projeto em Desenvolvimento | XML carregado, em negociação |
| Proposta Enviada | Orçamento salvo, aguardando cliente |
| Em Negociação | Cliente retornou, ajustes em andamento |
| Aprovado | Orçamento aprovado |
| Contrato Assinado | Contrato vigente |

### 2. Pipeline Operacional `[TODO]`
Acompanha projetos após o contrato.

| Coluna | Descrição |
|---|---|
| Aguardando Medição | Contrato assinado, medição não agendada |
| Medição Agendada | Data confirmada |
| Projeto Executivo | Em desenvolvimento |
| Conferência | Checklist técnico em andamento |
| Pedido Implantado | Pedido enviado ao CD |
| Em Produção | CD processando |
| Entrega Agendada | Data confirmada |
| Em Montagem | Montagem em andamento |
| Assistência | Pendências pós-montagem |
| Concluído | Projeto encerrado |

---

## Funcionalidades

### Cartão do projeto
Cada projeto aparece como um cartão com:
- Nome do projeto
- Nome do cliente
- Consultor responsável
- Data de criação / última atualização
- Valor do orçamento
- Indicador de prazo (verde/amarelo/vermelho)

### Interações
- Arrastar e soltar entre colunas (drag and drop)
- Clicar no cartão abre o projeto
- Filtrar por consultor, período, valor

### Alertas automáticos `[TODO]`
- Projeto parado há X dias na mesma coluna
- Prazo de entrega se aproximando
- Pagamento em atraso

---

## Integração com o fluxo existente

A mudança de status no Kanban deve refletir e ser refletida pelo status do projeto:
- Aprovar orçamento → move para "Aprovado"
- Assinar contrato → move para "Contrato Assinado"
- etc.

---

## Implementação recomendada

Usar biblioteca JavaScript de drag-and-drop (ex: `SortableJS` — disponível via CDN) integrada ao frontend existente. Os dados de status ficam em `projeto.json`.

---

## User Stories

**US-KAN-001** — Como gerente, quero ver todos os projetos em andamento organizados por fase em um único painel.

**US-KAN-002** — Como consultor, quero mover um projeto para a próxima fase ao arrastar seu cartão.

**US-KAN-003** — Como gerente, quero identificar projetos parados há muito tempo em uma fase.

**US-KAN-004** — Como diretor, quero filtrar o Kanban por consultor para acompanhar a performance da equipe.
