# Sub-projeto C — Semântica de aprovação + botão de assinatura

**Data:** 2026-06-17
**Projeto:** Omie_V3 — Dalmóbile / Orizon Soluções
**Escopo:** "Aprovar Orçamento" conclui Revisão (etapa 5) **e** Aprovação (etapa 6) juntas; etapa 5 deixa de ter toggle manual; botão pós-aprovação vira clicável "Orçamento aprovado – assinar contrato" levando ao card de assinatura. `desfazer_aprovacao` passa a resetar 5/6/7.
**Parte de:** Redesenho do ciclo de vida (A/B/C/D). A e B já entregues e mergeados.
**Cobre os pontos do usuário:** 9 (1º orçamento por XML — já atendido), 10 e 11 (revisão concluída pela aprovação; "Aprovar Orçamento" conclui as duas fases), 13 (botão clicável renomeado para assinatura).

---

## 1. Contexto (estado atual)

- **Etapa 4 (Primeiro orçamento):** concluída automaticamente ao **salvar orçamento com ≥1 ambiente** (vindo de XML) — `salvarOrcamento()` faz `PATCH /ciclo/4` (`static/index.html:~5918-5930`). **Ponto 9 já atendido.**
- **Etapa 5 (Revisão de projeto):** `{codigo:"5", toggleavel:true}` (`static/index.html:6122`); só **toggle manual** via `toggleSalvarEtapa` (botão "Marcar como Concluída", render ~`6337`). Nada a conclui automaticamente.
- **"Aprovar Orçamento":** botão em page-02 → `abrirAprovacaoComDados()` → `abrirModalAprovacaoOrcamento()` → `gerarContrato()` → `POST /api/projetos/<nome>/contrato`. O endpoint marca **etapa 6 concluída** e **etapa 7 em_andamento** (`main.py:~2106-2125`). **Não marca a 5.**
- **Pós-aprovação:** `atualizarUIBloqueio()` (`static/index.html:~3632-3658`) desabilita "Aprovar Orçamento" (texto vira `🔒 Orçamento Aprovado`); um banner *"Orçamento aprovado — em geração de contrato"* aparece e os botões Salvar/Aprovar são ocultados (`~6207-6227`). **Não há botão clicável para ir à assinatura.**
- **Assinatura:** acontece no card da etapa 7 (Ciclo) — `abrirCiclo()` + `toggleCicloCard('7')` → `carregarDadosContrato()` → `renderContratoUI()` com iframe do PDF e botões de assinatura.
- **`desfazer_aprovacao`** (gerencial, `main.py:~1835-1873`): hoje reseta etapas **6 e 7** e volta o contrato para rascunho.

### Decisões validadas com o usuário
- **(a)** Etapa 5 **só é concluída pela aprovação** — remover o toggle manual.
- **(b)** Botão pós-aprovação **clicável** que leva direto ao card de assinatura do contrato.

---

## 2. Etapa 5 (Revisão) concluída pela aprovação

### 2.1 Backend
No handler `POST /api/projetos/<nome>/contrato` (`main.py:~2106`), onde hoje marca a etapa 6 como `concluido`, marcar **também a etapa 5 como `concluido`** (mesmo `concluido_em`/`responsavel_id`, no mesmo commit). Resultado da aprovação: **5 concluída, 6 concluída, 7 em_andamento**.

### 2.2 `desfazer_aprovacao` (consistência)
No handler `desfazer_aprovacao` (`main.py:~1835-1873`), além de resetar 6 e 7, **resetar também a etapa 5** (voltar a `pendente`, limpar `concluido_em`/`responsavel_id`). Mantém o invariante "aprovação concluiu 5+6 → desfazer reabre 5+6+7". A trava existente (contrato assinado/vigente bloqueia o desfazer) permanece.

### 2.3 Frontend
- **Remover o toggle manual da etapa 5:** tirar `toggleavel: true` da entrada `{codigo:"5"}` em `ETAPAS_CICLO` (`static/index.html:6122`). Sem `toggleavel`, o card não renderiza o botão "Marcar como Concluída".
- **Card da etapa 5:** quando pendente (em revisão), exibir uma nota explicativa no corpo do card genérico, ex.: *"Em revisão — conclua aprovando o orçamento na aba Negociação."* (sem botão de concluir). Quando concluída, comportamento normal (✓).

---

## 3. Botão pós-aprovação "Orçamento aprovado – assinar contrato" (ponto 13)

Quando o projeto está aprovado (`projetoAtivo.bloqueado === true`):

- Em vez do banner/texto *"Orçamento aprovado — em geração de contrato"* e do botão desabilitado `🔒 Orçamento Aprovado`, exibir um **botão clicável** com o texto **"Orçamento aprovado – assinar contrato"** (com cadeado/dourado para indicar estado aprovado, mas **habilitado e clicável**).
- **Ação ao clicar:** navegar para a assinatura — `abrirCiclo()` seguido de `toggleCicloCard('7')` (mesmo destino que `gerarContrato()` usa no sucesso). Isso abre a aba Ciclo e o card do contrato (etapa 7), onde estão o PDF e os botões de assinar.
- Ajustar `atualizarUIBloqueio()` (`static/index.html:~3632-3658`) e/ou o bloco do banner (`~6207-6227`) para renderizar esse botão clicável no estado bloqueado. Renomear o texto "em geração de contrato" → "assinar contrato".

---

## 4. Etapa 4 — sem mudança

Já conclui ao salvar orçamento com ≥1 ambiente (ponto 9 atendido). Nenhuma alteração.

---

## 5. Testes

1. **Backend (novo):** ao gerar contrato com cadastro completo, as etapas **5 e 6** ficam `concluido` e a **7** `em_andamento`. (Verificar via runtime drive do endpoint, como no Sub-projeto B, ou extrair a marcação numa função testável se viável.)
2. **Backend (novo):** `desfazer_aprovacao` reseta **5, 6 e 7** para `pendente` (quando o contrato não está assinado/vigente).
3. **Frontend (manual + Playwright):**
   - Após aprovar um orçamento (cadastro completo), o botão mostra "Orçamento aprovado – assinar contrato" e, ao clicar, abre o card de assinatura (etapa 7).
   - A etapa 5 no Ciclo não tem mais botão "Marcar como Concluída"; aparece concluída após a aprovação.

---

## 6. Fora de escopo
- **D** — Briefing obrigatório após criação do projeto.
- Mudanças no fluxo de assinatura em si (apenas navegamos até ele).
- Remoção da coluna vestigial `contrato.endereco_instalacao` (limpeza futura).

---

## 7. Arquivos afetados (estimativa)

| Arquivo | Mudança |
|---|---|
| `main.py` | endpoint de contrato marca etapa 5 (além de 6/7); `desfazer_aprovacao` reseta 5 também |
| `static/index.html` | remove `toggleavel` da etapa 5 + nota no card; botão pós-aprovação clicável "assinar contrato" navegando para o card 7 |
