# Reconciliação — 38 etapas (referência) ↔ Ciclo implementado (18 principais + 6 sub)

> **Doc GERADO pelo Claude** (derivado da referência + do código). Não é fonte de verdade do processo.
> **Fonte canônica das 38 etapas:** `docs/referencia/01-fluxo-de-processos.md` (transcrição do
> `1.FLUXO_DE_PROCESSOS.docx`; editável pelo usuário). **Fonte do ciclo:** `mod_ciclo.py` + `ciclo_etapas`.
> Atualizado: 2026-07-06.

> ### ⚠ SUBSTITUI o modelo antigo de "38 etapas"
> A versão anterior deste arquivo trazia um **modelo diferente** de 38 etapas (Pré-venda 1–6 / Projeto
> 7–12 / Negociação 13–19 / Contrato 20–25 / Produção 26–31 / Pós-venda 32–38). Esse modelo **não bate**
> com o documento organizacional canônico (`1.FLUXO_DE_PROCESSOS.docx`), que é o de **6 fases** abaixo.
> O modelo antigo fica **aposentado** — use a referência canônica + esta reconciliação.

## Ciclo REALMENTE implementado (reality atual)

**18 etapas principais + 6 sub-etapas**, com gating sequencial (`mod_ciclo.py`, `ETAPAS_PRINCIPAIS`).
As antigas etapas **5 e 6 foram eliminadas** (Orçamento 4 → Contrato 7). Sub-etapas são livres dentro do pai.

| Código | Etapa | Subs |
|---|---|---|
| 1 | Cadastro do Cliente | |
| 2 | Criação do projeto | |
| 3 | Briefing | |
| 4 | Orçamento | |
| 7 | Contrato | |
| 8 | Aprovação financeira I | |
| 9 | Solicitação de medição | |
| 10 | Medição | |
| 11 | Projeto executivo | 11a Planta de pontos · 11b Reunião de alinhamento · 11c Revisão de PE · **11d Aprovação financeira II** · 11e Aprovação do PE pelo cliente |
| 12 | Implantação do pedido | |
| 13 | Produção | |
| 14 | Entrega no depósito | |
| 15 | Emissão da NFe do cliente | |
| 16 | Entrega no cliente | |
| 17 | Montagem | 17a Pendências de montagem |
| 18 | Assistência pós Montagem | |
| 19 | Vistoria final | |
| 20 | Aprovação final | |

Faixas de titularidade (venda / gates financeiros / pós-venda / logística): ver
`docs/ARQUITETURA-MODULOS.md` › **Governança do Ciclo**.

## Mapa de reconciliação (referência → ciclo)

Cada etapa do ciclo **cobre** uma ou mais das 38 micro-etapas do documento canônico:

| Etapa do ciclo | Cobre (38 etapas — ref.) |
|---|---|
| **1** Cadastro do Cliente | 1 Qualificação do lead · 2 Agendamento do briefing |
| **2** Criação do projeto | 5 Desenvolvimento do projeto (Promob) — criação |
| **3** Briefing | 3 Briefing com cliente · 4 Briefing com arquiteto |
| **4** Orçamento | 5 (lista de produtos) · 6 Revisão interna · 7 Apresentação · 8 Ajustes · 9 Negociação/desconto |
| **7** Contrato | 10 Fechamento do contrato |
| **8** Aprovação financeira I | 11 Handoff para o pós-venda *(gate venda→pós-venda)* |
| **9** Solicitação de medição | 12 Agendamento da medição |
| **10** Medição | 13 Medição in loco |
| **11a** Planta de pontos de PE | 14 Validação da Planta de Pontos *(gate de qualidade)* |
| **11b** Reunião de alinhamento | 16 Alinhamento inicial × executivo |
| **11c** Revisão de PE | 15 Desenvolvimento do projeto executivo |
| **11d** Aprovação financeira II | 20 Aprovação Financeira *(+ 17 impacto financeiro)* |
| **11e** Aprovação do PE pelo cliente | 17 Aprovação do PE · 18 Assinatura do PE |
| **12** Implantação do pedido | 19 Conferência · 21 Implantação · 22 Transferência ao CD |
| **13** Produção | 23 Execução dos pedidos de compra · 24 Planejamento logístico |
| **14** Entrega no depósito | 25 Recebimento da mercadoria (+ produção local) · 26 Processamento e separação |
| **15** Emissão da NFe do cliente | *(embutido na)* 28 — "NF de venda emitida pelo CD" |
| **16** Entrega no cliente | 27 Agendamento da entrega · 28 Entrega no local |
| **17** Montagem | 29 Briefing de montagem · 30 Execução da montagem |
| **17a** Pendências de montagem | 31 Assistências em montagem |
| **18** Assistência pós Montagem | 37 Tratamento de ocorrências |
| **19** Vistoria final | 32 Vistoria parcial · 33 Vistoria final com cliente |
| **20** Aprovação final | 35 Encerramento no CRM |

## Lacunas (micro-etapas do canônico SEM casa no ciclo)

1. **🧾 34 Emissão da NF de serviço de montagem (NFS-e) — NÃO modelado.** O ciclo só tem a **15** (NF-e de
   **produto**). Falta a **NFS-e de montagem** por estado (SP/RJ/CE — doc D43). → **Módulo Fiscal.**
2. **36 Follow-up pós-entrega** e **38 Indicação/recompra** — sem etapa (pós-20). → **Pós-venda / Marketing.**
3. **Descompasso da Aprovação Financeira:** canônico coloca em **Fase 3 (20), depois do PE**; o ciclo puxou
   para **dentro do PE (11d)**. Semânticas distintas ("aprovar antes de detalhar o PE" × "aprovar a lista
   final pós-PE, antes de comprar"). → **decisão a tomar.**
4. **Conferência (19)** e **Transferência ao CD (22)** achatadas dentro da **12 (Implantação)** — sem marco próprio.

## Ainda aberto (não travar operação por número de etapa)

A numeração 38 (referência) × 18+6 (implementação) **diverge por desenho** — a reconciliação acima é o
vínculo estável. Decisões pendentes derivadas das lacunas: (a) modelar a **NFS-e de montagem** no Fiscal;
(b) posição da **Aprovação Financeira** (11d × Fase 3); (c) se **Pós-entrega (36–38)** vira etapa(s).
Ver também `docs/ARQUITETURA-MODULOS.md` › ⚠ CONFLITO ABERTO.
