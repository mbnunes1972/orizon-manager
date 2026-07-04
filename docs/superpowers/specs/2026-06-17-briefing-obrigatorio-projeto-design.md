# Sub-projeto D — Briefing obrigatório por-projeto

**Data:** 2026-06-17
**Projeto:** Orizon Manager — Dalmóbile / Orizon Soluções
**Escopo:** Briefing passa a ser **por-projeto** (não por-cliente). Depois de criar o projeto, o consultor é obrigado a preencher os campos obrigatórios do briefing daquele projeto antes de negociar. Backend bloqueia negociação sem briefing.
**Parte de:** Redesenho do ciclo de vida (A/B/C/D). A, B e C já entregues e mergeados. **D é o último.**
**Cobre os pontos do usuário:** 7 (briefing obrigatório após criar o projeto), 8 (passado o briefing, inicia o 1º orçamento/negociação).

---

## 1. Contexto (estado atual)

- **Campos obrigatórios do briefing** (`main.py:_BRIEFING_OBRIGATORIOS`): `tipo_imovel`, `budget_declarado`, `categoria_proposta`, `data_entrega_desejada`, `flexibilidade_prazo`. "Briefing OK" = todos os 5 obrigatórios preenchidos (`all(d.get(f) for f in _BRIEFING_OBRIGATORIOS)`); demais campos são opcionais.
- **Briefing hoje é POR CLIENTE:** tabela `Briefing` tem `cliente_id`, sem vínculo de projeto. Vários projetos do mesmo cliente compartilham um briefing.
- **Salvar briefing:** `POST /api/clientes/<id>/briefing` (`main.py:1123`); quando OK, chama `_marcar_etapa_cliente(cliente_id, "3", ...)` que marca a etapa 3 em **todos** os projetos do cliente.
- **Criar projeto:** `criarProjeto()` (`static/index.html:2657`) hoje **exige briefing ANTES** de criar (bloqueia a criação) — isso conflita com a nova ordem (2 Criação → 3 Briefing) e com o ponto 7. Após criar, navega para a negociação (`goPage(2)`).
- **Lacuna:** `POST /projetos/<nome>/orcamentos` e `POST /projetos/<nome>/pool` (XML) **não checam briefing** — dá para negociar sem briefing.
- **Aprovação** já checa briefing (`abrirAprovacaoComDados`, `static/index.html:6813`), mas por-cliente.

### Decisões validadas com o usuário
- **(a)** `projeto_nome` na tabela `Briefing`; endpoints **por projeto**. Briefings antigos (sem `projeto_nome`) viram legado, ignorados pelo fluxo de projeto. **Começar do zero** (sem migração heurística — dados são de teste).
- **(b)** Etapa 3 marcada **só no projeto** do briefing (não em todos do cliente).
- **(c)** Backend bloqueia `orcamentos`/`pool` sem os **campos obrigatórios** do briefing daquele projeto.
- "Briefing OK" = **campos obrigatórios** preenchidos (os 5), não "todos os campos".

---

## 2. Modelo de dados: briefing por-projeto

- Adicionar coluna **`projeto_nome`** (`TEXT`, nullable) à tabela `briefings` — via `_migrar_colunas()` (mesmo padrão `ALTER TABLE ... ADD COLUMN` idempotente já usado para clientes/contratos/etc.). Adicionar também o campo ao modelo `Briefing` em `database.py`.
- Semântica: um briefing pertence a **(cliente_id, projeto_nome)**. A busca do briefing de um projeto é por `projeto_nome`. Briefings legados têm `projeto_nome IS NULL` e não são considerados pelo fluxo de projeto.

---

## 3. Backend: endpoints por-projeto + etapa 3

### 3.1 Endpoints novos
- **`GET /api/projetos/<nome>/briefing`** — retorna o briefing do projeto (`Briefing.filter_by(projeto_nome=nome).order_by(id.desc()).first()`), no formato de `_briefing_dict` (com `completo` = obrigatórios preenchidos). Se não houver, retorna um briefing vazio/`completo:false`.
- **`POST /api/projetos/<nome>/briefing`** — upsert do briefing **daquele projeto**: deriva `cliente_id` do projeto (`projetos_meta.cliente_id` / `projeto.json`); cria/atualiza a linha com `projeto_nome=nome`. Quando os obrigatórios estão preenchidos, marca a **etapa 3 só desse projeto** (`CicloEtapa(projeto_nome=nome, etapa_codigo="3", status="concluido")`).

### 3.2 Helper testável
- **`_briefing_projeto_completo(nome_safe, db) -> bool`** — True se o projeto tem um briefing por-projeto com todos os obrigatórios preenchidos. Reutiliza a regra `_BRIEFING_OBRIGATORIOS`.

### 3.3 Endpoint legado
- `POST /api/clientes/<id>/briefing` permanece para a aba Clientes, mas **deixa de marcar a etapa 3** (`_marcar_etapa_cliente(..., "3", ...)` é removido dessa rota) — a etapa 3 agora é responsabilidade do endpoint por-projeto. O briefing por-cliente vira informativo/legado.

---

## 4. Backend: gate de negociação

Em `POST /projetos/<nome>/orcamentos` (`main.py:1271`) e `POST /projetos/<nome>/pool` (`main.py:1311`): antes de executar, checar `_briefing_projeto_completo(nome_safe, db)`. Se falso, retornar **HTTP 400** com mensagem clara (ex.: `"Preencha o briefing do projeto antes de iniciar a negociação."`). Defesa em profundidade — o frontend também guia, mas o backend é a autoridade.

> Nota: a criação automática de "Orçamento 1" no `POST /projetos/novo` permanece (placeholder vazio). O gate impede **adicionar XML/ambientes e criar novos orçamentos** sem briefing; a negociação efetiva só começa após o briefing.

---

## 5. Frontend: fluxo criar → briefing → negociar

- **`criarProjeto()`**: **remover** a checagem de briefing **antes** da criação (`static/index.html:2668-2680`). Após criar o projeto com sucesso, **abrir o briefing daquele projeto** (obrigatório) em vez de ir direto para a negociação.
- **Briefing por-projeto no modal:** uma função (ex.: `abrirBriefingProjeto(nome_safe)`) carrega `GET /api/projetos/<nome>/briefing`, reaproveita o formulário do modal de briefing existente, e salva em `POST /api/projetos/<nome>/briefing`. Ao salvar com os obrigatórios preenchidos → fechar e seguir para a negociação (`goPage(2)`).
- **Aprovação:** `abrirAprovacaoComDados` passa a checar o briefing **do projeto** (`GET /api/projetos/<nome>/briefing`) em vez do briefing do cliente.
- Se o consultor tentar negociar sem briefing (ex.: subir XML), o backend retorna 400 e o frontend mostra o aviso com ação "Preencher Briefing".

---

## 6. Testes

1. **Backend (helper):** `_briefing_projeto_completo` — falso sem briefing/obrigatórios; verdadeiro com os 5 obrigatórios; ignora briefing legado (sem `projeto_nome`).
2. **Backend (runtime/API):** `POST /projetos/<nome>/orcamentos` e `/pool` retornam 400 sem briefing; passam após o briefing por-projeto. `POST /api/projetos/<nome>/briefing` marca a etapa 3 **só** daquele projeto (não de outro projeto do mesmo cliente).
3. **Frontend (Playwright):** criar projeto → abre o briefing obrigatório → preencher os 5 obrigatórios → negociação liberada. Um 2º projeto do mesmo cliente exige briefing novo.

---

## 7. Fora de escopo
- Remoção/redesenho da UI de briefing por-cliente na aba Clientes (vira legado; não removida agora).
- `_briefing_locked` (somente-leitura) — hoje é por-cliente e não está em uso; pode ser alinhado a por-projeto numa limpeza futura.
- Mover a criação do "Orçamento 1" para depois do briefing (mantido no `POST /projetos/novo`).

---

## 8. Arquivos afetados (estimativa)

| Arquivo | Mudança |
|---|---|
| `database.py` | coluna `projeto_nome` em `briefings` (modelo + `_migrar_colunas`) |
| `main.py` | endpoints `GET/POST /api/projetos/<nome>/briefing`; `_briefing_projeto_completo`; gate em `orcamentos`/`pool`; remove etapa-3 do endpoint de cliente |
| `static/index.html` | `criarProjeto` sem checagem prévia + abre briefing do projeto; `abrirBriefingProjeto`; aprovação usa briefing do projeto |
| `tests/` | testes de `_briefing_projeto_completo` |
