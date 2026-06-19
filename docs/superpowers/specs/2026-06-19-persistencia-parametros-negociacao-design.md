# Design — Persistência dos parâmetros de negociação no banco

> Data: 2026-06-19 · Sub-projeto: parâmetros de negociação por orçamento (banco)

## Problema

Dois dados de negociação não são persistidos de forma confiável e associada ao projeto:

1. **Desconto individual por ambiente** (coluna "Desc.%" da tabela de negociação) vive
   apenas no `localStorage` do navegador (`_descIndividual`, chave `ep07_<pool_id>`). Some
   ao trocar de máquina/navegador ou limpar o cache.
2. **Margens** (desconto global, custos, comissões, impostos — 12 chaves) ficam em
   `PROJETOS/<nome>/projeto.json`, **compartilhadas por todo o projeto**. Isso impede ter
   orçamentos paralelos com parâmetros distintos, ainda que o EP-07 permita múltiplos
   orçamentos editáveis. A coluna `orcamentos.margens` (TEXT) existe mas está vazia.

Viola a regra do projeto: todo dado/documento do projeto deve ser persistido (banco/disco),
nunca apenas no navegador.

## Decisões (acordadas)

- **Granularidade:** margens e descontos individuais passam a ser **por orçamento**.
- **Migração:** automática e idempotente — copia as margens de cada `projeto.json` para os
  orçamentos do projeto que ainda não têm margens. Projetos antigos não perdem nada.
- **Orçamento novo:** herda uma **cópia** das margens do orçamento ativo no momento da
  criação (snapshot). Sem orçamento de origem → defaults.
- **Forma antiga desativada:** `POST /projetos/<nome>/margens` (grava em `projeto.json`) é
  aposentado em favor do endpoint por-orçamento. `projeto.json` deixa de ser fonte de
  `margens` (continua guardando cliente snapshot, `codigo_projeto_omie`, etc.).

## Modelo de dados

- `orcamento_ambientes`: **nova coluna** `desconto_individual_pct FLOAT NOT NULL DEFAULT 0`.
  O desconto vive no vínculo orçamento↔ambiente, então é por-orçamento por construção.
- `orcamentos.margens` (TEXT já existente): **fonte oficial** das margens — JSON com as 12
  chaves atuais (`desconto_pct`, `custo_financeiro_pct`, `custo_viagem`, `fora_da_sede`,
  `brinde`, `brinde_ativo`, `comissao_arq_pct`, `comissao_arq_ativa`, `fidelidade_pct`,
  `fidelidade_ativa`, `incluir_custos`, `carga_trib`).

## Backend (`main.py`, `database.py`)

- `POST /api/orcamentos/<id>/margens` — salva as 12 chaves de margens **no orçamento**
  (mesmo merge/validação do handler atual). Mantém o gate de bloqueio pós-aprovação
  (rejeita se o projeto/contrato está aprovado). Retorna as margens salvas.
- `PUT /api/orcamentos/<id>/descontos` — grava em lote `{pool_ambiente_id: pct}` os
  descontos individuais nas linhas de `orcamento_ambientes` daquele orçamento. Valores fora
  de `0..100` rejeitados; pares cujo `pool_ambiente_id` não pertence ao orçamento são
  ignorados. Mantém o gate de bloqueio.
- `GET /api/orcamentos/<id>/ambientes` — passa a incluir `margens` (objeto) do orçamento e
  `desconto_individual_pct` em cada ambiente.
- **Criação de orçamento** (handler atual de "novo orçamento"): copia `margens` do orçamento
  ativo informado (`origem_id` no body) para o novo; defaults se ausente.
- **Migração** `_run_migracoes` (idempotente, rastreada em `schema_migrations`, id
  `margens_para_orcamento_2026`): para cada `projeto.json` com `margens`, para cada orçamento
  do projeto com `margens` vazia, grava o JSON. Não sobrescreve margens já preenchidas.
- `_migrar_colunas`: adiciona `desconto_individual_pct` em `orcamento_ambientes` se ausente.
- **Aposentar** `POST /projetos/<nome>/margens` (remover handler e seus usos no frontend).

## Frontend (`static/index.html`)

- Modal de parâmetros (salvar) → `POST /api/orcamentos/<_orcamentoAtivoId>/margens`.
- Coluna "Desc.%": ao sair do campo (`_onDescIndBlur`) e/ou ao salvar parâmetros, envia o
  lote para `PUT /api/orcamentos/<id>/descontos`. Servidor vira fonte de verdade.
- Ao ativar/trocar de orçamento (`ativarOrcamento`/`carregarOrcamentos`): recarrega `margens`
  e `desconto_individual_pct` **do servidor** (resposta do GET de ambientes), popula o painel
  de parâmetros e `_descIndividual`. Trocar de orçamento mostra os parâmetros daquele
  orçamento (isolamento real).
- `localStorage` deixa de ser autoritativo para desconto individual (pode permanecer como
  cache otimista de UI, mas o GET do servidor prevalece).
- Criar novo orçamento envia `origem_id = _orcamentoAtivoId`.

## Testes

**TDD backend** (`tests/`):
- Salvar margens por orçamento; **isolamento**: alterar margens do orçamento A não muda B.
- `PUT .../descontos` persiste e o GET devolve os valores; validação de faixa; pares fora do
  orçamento ignorados.
- Gate de bloqueio pós-aprovação nos dois endpoints.
- Migração: copia do `projeto.json`; idempotente (rodar 2x não duplica/sobrescreve); não
  toca margens já preenchidas.
- Criação de orçamento copia margens da origem; defaults sem origem.

**Playwright (dados reais)** — ver [[gui-verification-playwright]]:
- Dois orçamentos com parâmetros distintos; trocar entre eles confirma isolamento.
- Definir desconto individual, recarregar a página (simula novo acesso) e confirmar que o
  valor persiste (não dependia mais do localStorage).

## Fora de escopo

- Comissão de múltiplos parceiros (hoje só `comissao_arq_pct`). Mantido como está.
- Armazenamento dedicado de "projeto executivo" (entregável) — tratado em sub-projeto futuro;
  hoje a planta promob fica na medição.
