# Design — Parâmetros estruturais por projeto, desconto/pagamento por orçamento

> Data: 2026-06-20 · Correção/refino do modelo de parâmetros de negociação (revê a sessão 16,
> que deixou TODAS as margens por orçamento).

## Problema

Hoje todas as margens são por orçamento (`orcamentos.margens`). Mas os parâmetros **estruturais**
da negociação valem para o **projeto inteiro** e devem ser idênticos em todos os orçamentos:
mexeu num, vale para todos. Apenas o desconto e o pagamento são específicos de cada orçamento.

**Classificação (acordada):**

- **Do projeto (compartilhados por TODOS os orçamentos):** `incluir_custos` ("incluir custos
  adicionais"), `comissao_arq_pct`/`comissao_arq_ativa` ("comissão do arquiteto"),
  `fidelidade_pct`/`fidelidade_ativa` ("programa de fidelidade"), `fora_da_sede`/`custo_viagem`
  ("custo viagem"), `brinde`/`brinde_ativo` ("brinde"), `carga_trib` ("carga tributária").
- **Por orçamento:** `desconto_pct` (desconto global) e o desconto por ambiente
  (`orcamento_ambientes.desconto_individual_pct`); forma de pagamento, entrada (valor + data) e
  datas de pagamento (`orcamentos.negociacao_json`).
- **Fora da classificação:** `custo_financeiro_pct` = `_acrescimoFin`, derivado da
  modalidade/parcelas — não é campo do modal; permanece por orçamento (em `orcamentos.margens`).

## Decisões (acordadas)

- **Estruturais no banco**, em **`projetos_meta.parametros_json`** (não em `projeto.json`).
- A lista de estruturais acima está completa (os 6 grupos do modal).

## Modelo de dados

- **Nova coluna `projetos_meta.parametros_json`** (TEXT, JSON): os parâmetros estruturais do
  projeto (10 chaves acima). Fonte única — todos os orçamentos do projeto leem daqui.
- **`orcamentos.margens`** passa a ser per-orçamento de fato: `desconto_pct` (+
  `custo_financeiro_pct` derivado). Os campos estruturais deixam de ser a fonte aqui.
- **Inalterados:** `orcamentos.negociacao_json`, `orcamento_ambientes.desconto_individual_pct`.

## Backend (`main.py`, `database.py`)

- `_migrar_colunas`: adiciona `parametros_json` em `projetos_meta`.
- **Helpers puros** (em `mod_orcamento_params.py`): `PARAMETROS_DEFAULT` (10 chaves estruturais) e
  `merge_parametros(atual, req)` (merge + coerção de tipos, só dos estruturais — espelha
  `merge_margens`). `merge_margens` permanece como está; o handler de margens do orçamento passa a
  persistir **apenas `desconto_pct`** (ignora chaves estruturais que cheguem).
- **`GET /api/projetos/<nome>/parametros`** → `{ok, parametros}` (estruturais do projeto;
  defaults se ausente).
- **`POST /api/projetos/<nome>/parametros`** → grava os estruturais em `parametros_json`
  (merge + coerção). **Gate:** rejeita 403/400 se o contrato está assinado/bloqueado
  (reusa `_contrato_assinado`/`_projeto_esta_bloqueado`).
- **`POST /api/orcamentos/<id>/margens`**: passa a gravar **só** `desconto_pct` (ignora chaves
  estruturais que por ventura cheguem). Mantém o gate.
- **`GET /api/orcamentos/<id>/ambientes`** passa a incluir `parametros` (os estruturais do projeto
  dono do orçamento) — esse GET já devolve `margens`/`negociacao`, então o front carrega tudo numa
  chamada ao ativar o orçamento. (O `GET /api/projetos/<nome>/parametros` existe para leitura
  isolada/edição.)
- **Migração** `migrar_parametros_para_projeto` (idempotente): para cada projeto sem
  `parametros_json`, copia os estruturais de um orçamento existente (o de maior `updated_at`/`id`).
  `desconto_pct` permanece em cada orçamento.

## Frontend (`static/index.html`)

- Ao ativar/abrir um orçamento: carrega os **estruturais do projeto** + o `desconto_pct` do
  **orçamento** e monta `projetoAtivo.margens` = `{...parametros_projeto, desconto_pct}`. O resto
  do cálculo (que lê `projetoAtivo.margens`) **não muda**.
- Ao salvar o modal de parâmetros (`fecharModalParams`): os campos **estruturais** vão para
  `POST /api/projetos/<nome>/parametros` (valem para todos os orçamentos); o **desconto** vai para
  `POST /api/orcamentos/<id>/margens`. Após salvar, recarrega para refletir.
- Desconto rápido da sidebar (`salvarDescontoAutomatico`) continua por orçamento.

## Testes

- **Backend (pytest):** coluna nova; `merge_parametros`/`PARAMETROS_DEFAULT`; migração idempotente
  (copia estruturais de um orçamento; não sobrescreve). (Handlers HTTP verificados via API real.)
- **API real:** salvar parâmetros do projeto → `GET .../parametros` reflete; afeta o cálculo de
  todos os orçamentos; `desconto_pct` salvo num orçamento não muda outro.
- **Playwright (dados reais — [[gui-verification-playwright]]):** 2 orçamentos no mesmo projeto —
  alterar comissão do arquiteto / brinde / carga tributária num aparece no outro; alterar desconto
  e forma de pagamento num **não** afeta o outro.

## Fora de escopo

- Sub-projeto 3 (versionamento de documentos), pendente.
- Configurador de lojas, pendente.
