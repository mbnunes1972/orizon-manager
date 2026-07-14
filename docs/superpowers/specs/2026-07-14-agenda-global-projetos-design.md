# Agenda Global de Projetos — Design (RASCUNHO)

**Data:** 2026-07-14 · **Status:** rascunho para brainstorm (decisões em aberto marcadas). O épico **não existe**
ainda (nenhuma spec/implementação); isto é o ponto de partida para discutir antes de espectar/planejar.

## Problema

Hoje o acompanhamento é **por projeto** (Cronograma do Ciclo dentro de cada projeto) ou uma **lista** de projetos
(Painel de Projetos, `renderProjResultados`). Falta a visão **temporal consolidada**: _o que vence quando, em TODOS
os projetos, e de quem é a responsabilidade_ — a "agenda" que uma loja usa para não deixar etapa atrasar.

## Alicerce que já existe (nada novo a persistir)

`CicloEtapa` (por projeto × etapa) já tem tudo:
- `data_prevista_conclusao` (D0 + prazo do Cronograma Padrão, `mod_cronograma.gerar_cronograma_projeto`),
- `concluido_em` (data real) + `status`,
- `funcao_responsavel_id` (função responsável) e `responsavel_id` (quem concluiu),
- escopo/tenancy pronto (Consultor vê os seus projetos; gerente+ vê todos; filtro por loja).

→ A Agenda Global é uma **VIEW/agregação read-only** sobre isso (mesmo princípio "fonte única = razão"): uma função
por escopo que varre os `CicloEtapa` abertos e os ordena por `data_prevista_conclusao`. **Sem tabela nova.**

## Visões propostas

- **MVP — Worklist "Atrasadas · Hoje · Próximas".** Lista agrupada por prazo; cada item = **projeto · etapa ·
  previsão · responsável (função/pessoa) · status**, com atalho para abrir o projeto na etapa. Filtros: responsável,
  loja, período, status. É a visão operacional que evita atraso.
- **V2 — Calendário mensal.** Os mesmos itens dispostos num mês (heat de carga por dia).
- **V3 — Por responsável.** A agenda de cada função/pessoa (o que está na mão de quem).

## Escopo/tenancy

Reusa o escopo existente: Consultor → só os projetos que criou; gerente+ → todos da loja; Diretor/rede → filtro por
loja. Uma única função de agregação parametrizada pelo escopo (não duplicar consulta).

## Decisões em aberto (para confirmar)

1. **Eixo do tempo** = `data_prevista_conclusao` de cada etapa (previsão de conclusão). Confirmar que é esse o
   "quando" da agenda (e não, por ex., data de início prevista).
2. **Público primário do MVP**: operacional/logística (worklist "o que fazer") **ou** gerência (visão de carteira/
   carga)? Define o layout inicial — recomendo **worklist operacional** primeiro (mais acionável).
3. **Onde mora**: item de menu próprio **"Agenda"** vs **aba no Painel de Projetos**. Recomendo menu próprio (é uma
   visão transversal, não uma faceta da lista).
4. **Só etapas abertas** (pendentes/em andamento/atrasadas) no MVP, ou também as concluídas (histórico)? Recomendo
   só abertas no MVP; concluídas entram como filtro depois.

## Plano por fases (quando aprovado)

- **A** — Núcleo de agregação (puro/TDD): `agenda_global(escopo, período, filtros)` → itens ordenados por previsão,
  com bucket (atrasada/hoje/próxima) derivado de `data_prevista_conclusao` vs hoje. Deriva de `CicloEtapa`.
- **B** — Endpoint `GET /api/agenda` (aplica escopo/tenancy) + testes e2e.
- **C** — Tela Worklist (MVP) no frontend + filtros + atalho pra etapa.
- **D** — Calendário mensal (V2) e visão por responsável (V3).

> Observação: encaixa naturalmente com o **desmembramento em Fases** (cada Fase percorre seu ciclo) — a agenda
> passaria a listar etapas **por Fase** quando o projeto for desmembrado. Considerar na fase A do agregador.
