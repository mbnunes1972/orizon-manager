# Pós-venda: Assistência Técnica — SPEC

**Status:** `[TODO]`  
**Etapas do fluxo:** 36–38

---

## Visão geral

A assistência cobre dois momentos: durante a montagem (pendências técnicas) e após a entrega (suporte e ocorrências pós-instalação).

---

## Etapa 36 — Follow-up pós-entrega

**Responsável:** Consultor + Marketing

**Ações:**
- Contatar cliente após X dias da entrega `[VALIDAR prazo]`
- Verificar satisfação
- Registrar feedback
- Identificar oportunidade de recompra ou indicação

**Regras:**
- `[VALIDAR]` Prazo para primeiro contato pós-entrega?
- `[VALIDAR]` Script de follow-up?

---

## Etapa 37 — Tratamento de ocorrências

**Responsável:** Assistente Logístico

**Ações:**
- Registrar ocorrência reportada pelo cliente
- Classificar: defeito de fábrica / problema de montagem / uso inadequado
- Acionar fornecedor ou equipe de montagem
- Acompanhar resolução até encerramento
- Notificar cliente sobre o andamento

**Tipos de ocorrência:**
- Peça com defeito
- Peça faltante
- Problema de montagem
- Divergência com projeto
- Dano durante entrega
- `[VALIDAR]` outros tipos?

**SLA de atendimento:** `[VALIDAR]` prazo máximo para cada tipo de ocorrência

---

## Etapa 38 — Indicação e recompra

**Responsável:** Marketing

**Ações:**
- Identificar clientes satisfeitos para programa de indicação
- Registrar indicações recebidas
- Vincular indicação ao parceiro/cliente indicador
- `[VALIDAR]` Existe programa de indicação com recompensa?

---

## Campos da ocorrência

| Campo | Tipo | Descrição |
|---|---|---|
| projeto_id | FK | Projeto relacionado |
| tipo | Enum | Ver tipos acima |
| descricao | Text | Descrição detalhada |
| status | Enum | aberta / em_andamento / resolvida / cancelada |
| responsavel | FK → usuários | Quem está tratando |
| data_abertura | DateTime | |
| data_resolucao | DateTime | Preenchida ao resolver |
| fotos | Arquivos | Evidências |
| resolucao | Text | Descrição da solução aplicada |

---

## User Stories

**US-ASS-001** — Como assistente logístico, quero registrar uma ocorrência relatada pelo cliente com tipo, descrição e fotos.

**US-ASS-002** — Como assistente logístico, quero acompanhar o status de todas as ocorrências abertas.

**US-ASS-003** — Como consultor, quero registrar o follow-up pós-entrega com o feedback do cliente.

**US-ASS-004** — Como gerente, quero ver um relatório de ocorrências por tipo e status para identificar problemas recorrentes.
