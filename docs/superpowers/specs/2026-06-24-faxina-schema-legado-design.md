# Faxina de Schema/Legado (Fase 2 — item 3) — Design

**Data:** 2026-06-24
**Status:** ✅ Implementado (Sessão 30), com uma mudança de rumo: a discriminação por ambiente foi
**REMOVIDA** (decisão do usuário — tinha falhas, não é necessária agora), em vez de migrada ao motor.
Pendente: drop da coluna `Orcamento.margens` (irreversível — backup + aprovação). Ver `NOMENCLATURA.md` e DEV_LOG Sessão 30.
**Base:** faxina single-source (Fase 1) + tela fonte única (Sessão 29). **Branch:** `faxina/schema-fase2`.
**Rollback:** tag `pre-refator-negociacao`.

> **Por que só design:** investigação (Explore + checagens) mostrou que **não há código morto seguro**
> para remover de forma autônoma — tudo está vivo ou é visual/irreversível. O usuário delegou a
> execução "enquanto descansa", mas executar destrutivo sem validação no navegador arriscaria
> regressões (histórico sensível). Esta spec deixa tudo pronto para executar **junto, com validação**.

## 1. Mapa vivo-vs-morto (corrigido)

A investigação **corrigiu suposições** sobre o que seria "morto":

| Alvo | Realidade | Risco |
|------|-----------|-------|
| `mod_margens.calcular_margens` | **VIVO** — chamado por `executarCalculo` (path legado) e `atualizarDiscriminacao` (tabela de discriminação) via `/calcular_margens` | Frontend-visual |
| `mod_margens._normalizar_faixas` | **VIVO** — chamado em `main.py:644` (endpoint de faixas) | Backend (não remover) |
| `custo_financeiro_pct` (param de `calcular_margens`) | No fluxo vivo é **sempre 0** (`index.html` 4601/5151); o motor não usa | Backend, depende do frontend |
| `executarCalculo` (EP-07) | **Já é single-source** — `if(_orcAmbientesAtivos!==null){ renderTabelaNeg; _atualizarPaineisAbertos; return; }` (não roda o legado) | Baixo |
| `atualizarDiscriminacao` → `discriminacao-tbody` | **VIVO** — ainda monta a tabela de discriminação pelo legado | Frontend-visual |
| `Orcamento.margens` (coluna JSON) | Legada; o motor lê `Projeto.parametros_json` + `Orcamento.desconto_pct`, **não** `orc.margens`. Ainda **escrita** em `POST /margens` e **retornada** em `GET /ambientes` (frontend mescla em `projetoAtivo.margens`) | DB + contrato + frontend |
| `valor_liquido` (coluna) | **VIVO** — é o `Val_Liq` do motor (`_recalcular_orcamento`), lido em contratos/listas. **Sem semântica legada diferente** | Não mexer |

## 2. Objetivo

Concluir o single-source eliminando o **cálculo legado de margem** (mod_margens no caminho de
exibição) e a **duplicação de armazenamento** (`Orcamento.margens`), sem mudar números visíveis
(o motor já é a fonte). `valor_liquido` e `_normalizar_faixas` ficam (estão vivos e corretos).

### Não-escopo
- `valor_liquido`: nada a fazer (sem legado real). Apenas documentar que é o `Val_Liq` do motor.
- Seletor de ambientes de brinde/viagem (Fase 2-passo 2).

## 3. Fases (por risco — cada uma valida antes da próxima)

### Fase A — Discriminação pelo motor (frontend-visual) ⚠️ valida no navegador
A tabela de **discriminação** (`discriminacao-tbody`, via `atualizarDiscriminacao` → `/calcular_margens`)
é o último consumidor visual do legado. Decisão a tomar **com o usuário**:
- **A1 (recomendado):** alimentar a discriminação pelo **breakdown do motor** (já traz, por ambiente,
  `VBVA/CFA/VBNA/VAVA` + `Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq`), eliminando `/calcular_margens` do
  fluxo. Conferir que cada coluna da discriminação tem equivalente no motor.
- **A2:** se a discriminação mostra algo que o motor não expõe, **estender o breakdown** (backend)
  antes de cortar o legado.
- **Validação:** abrir a discriminação e comparar número a número (motor × legado) antes de remover.

### Fase B — Remover o cálculo legado de margem (frontend + backend) ⚠️ depende de A
Após A, removível:
- Frontend: `executarCalculo` (resíduo do path legado não-EP-07, se confirmado sem uso),
  `atualizarDiscriminacao` (substituído por A), `lerMargensNegociacao`, e as chamadas a
  `/calcular_margens`. Confirmar que nenhum fluxo ativo restou (busca por `calcular_margens`,
  `_negBaseValues`, `_acrescimoFin` no caminho de exibição).
- Backend: endpoint `POST /calcular_margens` + `from mod_margens import calcular_margens`. Manter
  `_normalizar_faixas` (vivo no endpoint de faixas) — possivelmente movê-lo p/ `mod_fin`.
- `custo_financeiro_pct`: remover de `mod_margens.calcular_margens` (se a função sair, sai junto),
  `mod_omie.py:114`, `mod_orcamento_params.py` (default + `_FLOAT_KEYS`), `main.py:1419/1432`.
- **Testes:** `tests/test_margens.py` (8 testes de `calcular_margens`) saem se a função sair; senão,
  ajustar. Manter a suíte verde.

### Fase C — `Orcamento.margens` (duplicação) 🔴 migração de coluna (irreversível) — aprovação + backup
- Parar de **escrever** `orc.margens` (`POST /margens`, `main.py:~1996`) e de **retornar** em
  `GET /ambientes`; o frontend passa a usar só `parametros` (estruturais do projeto) + `desconto_pct`.
  Conferir que `projetoAtivo.margens` no frontend não dependa mais da parte `orc.margens`.
- **Só depois**, e **com backup do `omie.db` + aprovação**, dropar a coluna `Orcamento.margens`
  (database.py:329) — sqlite exige recriar a tabela. Dados já migrados (`parametros_json` +
  `desconto_pct`); reversível só pelo backup.
- **Validação:** salvar parâmetros/desconto e reabrir; conferir que tudo persiste sem `orc.margens`.

## 4. Testes / validação

- Backend: manter os 301 verdes a cada passo; ajustar/retirar `test_margens.py` conforme a Fase B.
- Frontend (manual, sem harness JS): **discriminação** (Fase A — comparação número a número),
  **modal de parâmetros e tela de negociação** (sem regressão de exibição após remover o legado),
  **persistência** de parâmetros/desconto (Fase C).
- Golden-master opcional: rodar `scripts/snapshot_cutover.py` antes e `scripts/diff_cutover.py`
  depois para garantir `valor_total/valor_liquido` inalterados.

## 5. Arquivos afetados (por fase)

- **A/B (frontend):** `static/index.html` — `atualizarDiscriminacao`, `executarCalculo`,
  `lerMargensNegociacao`, chamadas a `/calcular_margens`, `agendarCalculo`/`agendarDiscriminacao`.
- **B (backend):** `main.py` (endpoint `/calcular_margens`, import), `mod_margens.py`,
  `mod_omie.py`, `mod_orcamento_params.py`, `tests/test_margens.py`.
- **C (schema):** `database.py` (coluna `Orcamento.margens`), `main.py` (`POST /margens`,
  `GET /ambientes`), migração + backup do `omie.db`.

## 6. Recomendação

Executar **com o usuário presente**, fase a fase, validando no navegador entre cada uma. Começar
pela **Fase A** (discriminação pelo motor) — é o que destrava o resto. A Fase C (drop de coluna) só
após backup e aprovação explícita. Nada aqui deve mudar números visíveis (o motor já é a fonte).
