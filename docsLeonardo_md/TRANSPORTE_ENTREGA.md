# Pós-venda: Transporte e Entrega — SPEC

**Status:** `[TODO]`  
**Etapas do fluxo:** 27–28

---

## Etapa 27 — Agendamento da entrega

**Responsável:** Assistente Logístico

**Ações:**
- Contatar cliente para agendar data e horário de entrega
- Confirmar endereço de entrega
- Registrar no sistema

**Regras:**
- `[VALIDAR]` Prazo mínimo de antecedência para agendamento?
- `[VALIDAR]` Notificar cliente automaticamente por WhatsApp/email?

---

## Etapa 28 — Entrega no local do cliente

**Responsável:** Assistente Logístico

**Ações:**
- Executar entrega
- Coletar assinatura de recebimento do cliente
- Registrar entrega concluída no sistema
- Fotografar itens entregues

**Documentos:**
- Comprovante de entrega assinado (D28) `[VALIDAR]`

**Regras:**
- Se cliente recusar algum item → registrar não conformidade
- Não conformidade → acionar assistência técnica

---

## Custo de viagem / fora da sede

`[VALIDAR]` — como é definido se um projeto é "fora da sede"? Por cidade? Por distância?

O campo `fora_da_sede` no projeto já existe e afeta o cálculo de margem. Deve ser sincronizado com o endereço do cliente cadastrado.

---

## User Stories

**US-ENT-001** — Como assistente logístico, quero registrar o agendamento de entrega com data, hora e endereço confirmado.

**US-ENT-002** — Como assistente logístico, quero confirmar a entrega realizada e registrar o comprovante.

**US-ENT-003** — Como assistente logístico, quero registrar não conformidades na entrega para acionar assistência.
