# Documentação — Orizon Manager
## Dalmóbile | Sistema de Gestão Comercial

---

## Como usar esta documentação

Esta documentação é **viva** — deve ser atualizada a cada mudança relevante no sistema.

| Quando | O que fazer |
|---|---|
| Antes de implementar algo novo | Ler o SPEC.md do módulo afetado |
| Ao tomar uma decisão de arquitetura | Registrar em `arquitetura/DECISOES.md` |
| Ao concluir uma funcionalidade | Atualizar o SPEC.md e o BACKLOG.md |
| Ao encontrar um bug | Registrar a causa em `arquitetura/DECISOES.md` |
| Ao iniciar sessão com IA | Colar o DEV_LOG.md + SPEC.md do módulo em trabalho |

---

## Índice

### Arquitetura
- [Stack técnica](arquitetura/STACK.md)
- [Banco de dados](arquitetura/BANCO_DE_DADOS.md)
- [Rotas HTTP](arquitetura/ROTAS.md)
- [Decisões de arquitetura](arquitetura/DECISOES.md)

### Módulos
- [Autenticação](modulos/autenticacao/SPEC.md)
- [Clientes](modulos/clientes/SPEC.md)
- [Parceiros](modulos/parceiros/SPEC.md)
- [Projetos](modulos/projetos/SPEC.md)
- [Negociação](modulos/negociacao/SPEC.md)
- [Financeiro](modulos/financeiro/SPEC.md)
- [Contratos](modulos/contratos/SPEC.md)
- [Kanban](modulos/kanban/SPEC.md)
- [Integração Omie](modulos/integracao_omie/SPEC.md)
- [Pós-venda](modulos/pos_venda/SPEC.md)

### Processos
- [Fluxo 38 etapas](processos/FLUXO_38_ETAPAS.md)
- [Documentos D1–D45](processos/DOCUMENTOS_D1_D45.md)
- [Deploy](processos/DEPLOY.md)

### Histórias
- [Template de user story](historias/TEMPLATE.md)
- [Backlog](historias/BACKLOG.md)

---

## Convenções

- `[VALIDAR]` — ponto que precisa de confirmação com Marcelo
- `[TODO]` — funcionalidade planejada mas não implementada
- `[IMPLEMENTADO]` — funcionalidade concluída e testada
- `[BUG]` — comportamento incorreto conhecido
