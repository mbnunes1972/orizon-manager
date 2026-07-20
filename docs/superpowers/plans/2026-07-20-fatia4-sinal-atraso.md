# Fatia 4 — Sinal de Atraso Geral na Lista de Projetos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para executar task-a-task. Steps usam checkbox (`- [ ]`).

**Goal:** Iluminar na lista de projetos qualquer projeto com etapa vencida — o sinal de atraso é GERAL
(qualquer `CicloEtapa` aberta com previsão passada, ou entrega vencida com a etapa "16" aberta), não só
venda programada / entrega. Fecha a frente A+B (spec §6; o §7 — UI do card — já foi antecipado nas
Fatias 2–3).

**Architecture:** Função **pura** `mod_cronograma.projeto_em_atraso(etapas, data_entrega, hoje)` decide o
atraso a partir de tuplas `(codigo, data_prevista_conclusao, concluido_em)`. Um novo enriquecimento
`_enriquecer_projetos_com_atraso` em `main.py` (padrão dos `_enriquecer_projetos_com_*`) consulta
`CicloEtapa` + `Projeto` em lote e anota `p['atrasado']` e `p['data_entrega']` nos itens de `/projetos` e
`/projetos/buscar`. O frontend (`renderProjResultados`) ganha coluna **Entrega** com a data e o selo
**Atrasado** (tokens `--err`/`--err-soft`, padrão `.proj-status-badge`).

**Tech Stack:** Python puro (SQLAlchemy, http.server), pytest/TDD, frontend `static/index.html`.

**Escopo (spec §6):** view read-only (sem tabela nova), selo na lista. **Fora:** Agenda Global, IA
assistente, feriados, execução por ambiente (frente C).

**Referência:** `docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md` (§6).

---

## Decisões de design

- **Regra do atraso (pura):** atrasado ⇔ (∃ etapa com `concluido_em` nulo E `data_prevista_conclusao`
  não-nula E `data_prevista_conclusao < hoje`) OU (`data_entrega` não-nula E `hoje > data_entrega` E a
  etapa "16" está aberta — **ausente conta como aberta**, pois inexistir `CicloEtapa` "16" significa que a
  entrega não foi concluída).
- **Projetos encerrados não atrasam:** o enriquecimento força `atrasado = False` quando
  `Projeto.status ∈ {perdido, concluido, fechado}` — projeto morto/encerrado não acende selo.
- **Sem cronograma e sem data de entrega → nunca atrasado** (pré-assinatura não ilumina).
- `hoje` é parâmetro da função pura (testável); o chamador usa `datetime.utcnow()` (padrão do projeto).

## File Structure

- `mod_cronograma.py` — novo `projeto_em_atraso(etapas, data_entrega, hoje, codigo_entrega="16")` (puro).
- `main.py` — `_enriquecer_projetos_com_atraso(projetos)` + chamada em `/projetos` e `/projetos/buscar`.
- `static/index.html` — coluna Entrega + selo Atrasado em `renderProjResultados`; CSS `.proj-atraso-badge`.
- Testes: `tests/test_cronogramas_dois.py` (função pura), `tests/test_lista_projetos_atraso.py` (HTTP).

---

## Task 1: função pura `projeto_em_atraso`

**Files:** `mod_cronograma.py`; Test: `tests/test_cronogramas_dois.py`.

- [x] Testes: etapa aberta vencida → True; tudo concluído → False; etapa vencida mas concluída → False;
  sem etapas e sem data_entrega → False; `hoje > data_entrega` com "16" aberta → True; com "16"
  concluída → False; `hoje > data_entrega` sem nenhuma etapa "16" → True (ausente = aberta);
  previsão futura → False; `data_prevista` nula em etapa aberta não conta.
- [x] Implementar e rodar `python3 -m pytest tests/test_cronogramas_dois.py -q`.

## Task 2: enriquecimento HTTP da lista

**Files:** `main.py`; Test: `tests/test_lista_projetos_atraso.py`.

- [x] Testes (padrão dos testes HTTP existentes): `/projetos` devolve `atrasado:true` para projeto com
  etapa aberta vencida; `atrasado:false` para projeto em dia; `data_entrega` serializada (ISO);
  projeto `perdido` com etapa vencida → `atrasado:false`.
- [x] `_enriquecer_projetos_com_atraso`: 1 query `CicloEtapa` (in_ nomes) + reuso do `Projeto` já
  consultado; chamar nos dois endpoints; rodar a suíte.

## Task 3: frontend — coluna Entrega + selo

**Files:** `static/index.html`.

- [x] Coluna "Entrega" (`fmtData(p.data_entrega)`); selo `Atrasado` quando `p.atrasado` (CSS
  `.proj-atraso-badge{background:var(--err-soft);color:var(--err)}` no padrão `.proj-status-badge`).
- [x] `node --check` no `<script>` extraído; verificação manual no navegador (tema claro/escuro).

## Task 4: fechamento

- [x] Suíte inteira verde (`python3 -m pytest -q`).
- [x] DEV_LOG Sessão 86 + spec marcada como concluída (frente A+B fechada); commit/merge/push.
- [x] QA Vera: achado ALTO corrigido — `status="fechado"` é EXECUÇÃO (não terminal); terminais =
  perdido/concluido/cancelado. + reuso do `p['status']` (1 query a menos) + Kanban reusa `.proj-atraso-badge`.
- [ ] Re-ingerir MCP (bloqueado: Docker Desktop parado) + verificação manual no navegador (usuário).
