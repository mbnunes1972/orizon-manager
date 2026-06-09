# Módulo de Pós-venda — SPEC

**Status:** `[TODO]`

---

## Visão geral

O pós-venda cobre todas as etapas após a assinatura do contrato até o encerramento do projeto, incluindo medição, projeto executivo, produção, entrega, montagem e assistência técnica.

Baseado no documento `1_FLUXO_DE_PROCESSOS.docx` — fases 2 a 6 das 38 etapas.

---

## Fases do pós-venda

### Fase 2 — Medição e Projeto Executivo (etapas 12–18)

Ver [MEDICAO.md](MEDICAO.md) e [PROJETO_EXECUTIVO.md](PROJETO_EXECUTIVO.md)

### Fase 3 — Conferência e Pedido (etapas 19–22)

Ver [IMPLANTACAO.md](IMPLANTACAO.md)

### Fase 4 — CD: Compra e Logística (etapas 23–28)

Ver [PRODUCAO.md](PRODUCAO.md) e [TRANSPORTE_ENTREGA.md](TRANSPORTE_ENTREGA.md)

### Fase 5 — Montagem e Entrega Final (etapas 29–35)

Ver [MONTAGEM.md](MONTAGEM.md)

### Fase 6 — Pós-entrega (etapas 36–38)

Ver [ASSISTENCIA.md](ASSISTENCIA.md)

---

## Princípios do módulo

1. **Rastreabilidade** — cada etapa registra quem fez, quando e o resultado
2. **Documentação** — documentos obrigatórios por fase são cobrados pelo sistema
3. **Alertas** — sistema notifica sobre pendências e prazos
4. **Histórico** — log de todas as ações para resolução de disputas

---

## Gatilhos de início

O pós-venda inicia automaticamente quando:
- Contrato assinado (`status = vigente`) OU
- Orçamento exportado para o Omie (`status = exportado`)

`[VALIDAR]` — qual evento dispara o pós-venda na Dalmóbile?

---

## Responsáveis por fase

| Fase | Responsável principal |
|---|---|
| Medição | Medidor / Assistente Logístico |
| Projeto Executivo | Projetista Executivo |
| Conferência | Conferente |
| Pedido / CD | Ger. Adm. Financeiro |
| Transporte | Assistente Logístico |
| Montagem | Supervisor de Montagem |
| Assistência | Assistente Logístico |

`[VALIDAR]` — esses perfis precisam de acesso ao sistema? Com quais permissões?

---

## User Stories (visão geral)

**US-PV-001** — Como conferente, quero receber uma notificação quando um projeto for aprovado e estiver pronto para a fase de medição.

**US-PV-002** — Como assistente logístico, quero registrar a data de agendamento da medição.

**US-PV-003** — Como projetista, quero anexar o projeto executivo ao projeto e marcar como aprovado pelo cliente.

**US-PV-004** — Como supervisor de montagem, quero registrar o início e fim da montagem com fotos.

**US-PV-005** — Como consultor, quero acompanhar em qual fase do pós-venda está o projeto do meu cliente.
