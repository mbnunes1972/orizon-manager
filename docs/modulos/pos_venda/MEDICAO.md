# Pós-venda: Medição — SPEC

**Status:** `[TODO]`  
**Etapas do fluxo:** 12–13

---

## Visão geral

A medição é a primeira etapa do pós-venda. O medidor vai ao local do cliente para confirmar as dimensões reais do ambiente antes do desenvolvimento do projeto executivo.

---

## Etapa 12 — Agendamento da medição

**Responsável:** Assistente Logístico

**Ações:**
- Contatar cliente para agendar data e horário
- Registrar no sistema: data, hora, endereço confirmado
- Atribuir medidor responsável

**Documentos:**
- Confirmação de agendamento (D12) `[VALIDAR]`

**Regras:**
- `[VALIDAR]` Prazo máximo para agendamento após contrato assinado?
- `[VALIDAR]` Notificar cliente por WhatsApp/email automaticamente?

---

## Etapa 13 — Medição in loco

**Responsável:** Medidor

**Ações:**
- Executar medição no local
- Fotografar ambientes
- Registrar divergências em relação ao projeto inicial
- Marcar medição como concluída no sistema

**Documentos:**
- Folha de medição (D13) `[VALIDAR]`
- Fotos dos ambientes

**Regras:**
- Se houver divergências significativas → alertar projetista e gerente
- `[VALIDAR]` Quais divergências são consideradas significativas?

---

## Campos a registrar

| Campo | Tipo | Descrição |
|---|---|---|
| Data agendada | DateTime | |
| Medidor | FK → usuários | `[VALIDAR]` perfil específico? |
| Data realizada | DateTime | Preenchida ao concluir |
| Status | Enum | agendado / realizado / cancelado |
| Observações | Text | Divergências, pendências |
| Fotos | Arquivos | Upload de imagens |

---

## User Stories

**US-MED-001** — Como assistente logístico, quero registrar o agendamento da medição com data, hora e medidor responsável.

**US-MED-002** — Como medidor, quero registrar a conclusão da medição com observações e fotos.

**US-MED-003** — Como gerente, quero ser notificado quando houver divergências na medição.
