# Cutover do Motor de Negociação (Fase B) — Design

**Data:** 2026-06-23
**Status:** Em revisão (design)
**Base:** `docs/superpowers/specs/negociacao/2026-06-22-mecanismo-negociacao-design.md` (§12 descreve Fases B/C).
**Escopo:** Fazer a **tela de negociação e o modal de parâmetros usarem o motor `mod_negociacao`**
(não mais o cálculo legado do frontend), com a persistência (`valor_total`/`valor_liquido`)
e o contrato passando a refletir o motor. O motor já está validado em modo sombra.

---

## 1. Problema

Hoje, mesmo com o motor validado, os valores que o usuário **vê e salva** ainda vêm do
**cálculo legado do frontend** (`mpAtualizarApoio`/`renderTabelaNeg`, gross-up em
`static/index.html:4700` e `5132`). O motor só aparece no bloco de validação (sombra). O
`valor_total`/`valor_liquido` são calculados no frontend e gravados via `PATCH
/api/orcamentos/<id>` (main.py:3622-3629); o contrato lê esses campos (main.py:3276-3278).
Resultado: a negociação real e o contrato usam a conta antiga.

## 2. Objetivo

A tela de negociação e o modal passam a exibir e persistir os valores do **motor** (fonte
única), ao vivo, via um **endpoint de preview** (sem gravar) para display e um **recálculo
autoritativo no backend** no save.

### Não-escopo (Fase C — spec/plano próprios depois)
- Aposentar o bloco duplicado de params em `orcamentos.margens`.
- Remover o `custo_financeiro_pct` duplicado de `mod_margens`.
- Limite de desconto **configurável por loja** (mantém-se 35% hardcoded nesta fase).

### Decisões confirmadas
- **`mod_fin` reusado como está** (sem mexer nas tabelas de pagamento): `Cust_Fin`/`Val_Cont`
  vêm de `mod_fin.calcular(VAVO, entrada, parcelas, data, modalidade)`.
- **Limite de desconto: 35% hardcoded**, só trocando a base para o `%Desc_Tot` do motor.

---

## 3. §1 — Endpoint de preview (infra que destrava o display ao vivo)

**`POST /api/orcamentos/<id>/negociacao-preview`** — PURO de leitura (não grava), escopado à
loja (tenancy, padrão dos outros endpoints de orçamento).

- **Entrada (JSON, estado em edição do modal/tela):**
  `{ params: {<parametros_json do projeto, em edição>}, desc_orc: float,
     descontos_amb: {pool_ambiente_id: pct}, pagamento: {codigo, n_parcelas, entrada, data} }`
  (qualquer campo ausente cai no valor salvo do orçamento/projeto.)
- **Processa:** carrega os ambientes do orçamento (`OrcamentoAmbiente`→`PoolAmbiente`
  `budget_total`/`order_total`) com os descontos por ambiente (em edição ou salvos) →
  `mod_negociacao.calcular_orcamento(ambientes, params, desc_orc)` → calcula `Cust_Fin` via
  `mod_fin` a partir do `VAVO` e da modalidade → `Val_Cont = VAVO + Cust_Fin`.
- **Devolve:** `{ ok, sombra: {<cadeia completa do motor>}, ambientes: [{VBVA,CFA,VBNA,VAVA}] }`
  — mesmo formato do sub-objeto `_sombra_dict`, acrescido da lista por ambiente.

## 4. §2 — Persistência: recálculo autoritativo no backend

Extrair um helper **`_recalcular_orcamento(orc, db)`** (fonte única do recálculo persistido):
- monta ambientes + params + desconto do orçamento; chama `mod_negociacao` + `mod_fin`;
- grava as colunas sombra (`vbvo..prov_imp`, `com_arq_orc`, `pro_fid_orc`) **e**
  `valor_total = Val_Cont`, `valor_liquido = Val_Liq` (hoje o `valor_liquido` guardava o
  bruto — agora fica correto).
- É o mesmo cálculo do preview, mas **persistindo**.

**Pontos de chamada (onde a negociação muda):**
- `POST /api/orcamentos/<id>/margens` (já calcula o motor em sombra) — passa a chamar o
  helper e gravar `valor_total`/`valor_liquido` também.
- `PATCH /api/orcamentos/<id>` quando muda `forma_pagamento`/`negociacao_json` (a modalidade
  altera o `Cust_Fin`) — passa a **recalcular** em vez de aceitar `valor_total`/`valor_liquido`
  do frontend.

**O frontend para de enviar** `valor_total`/`valor_liquido`; o backend os **ignora** se vierem
(passam a ser derivados, nunca recebidos).

## 5. §3 — UI: tela de negociação e modal usam o preview

- `mpAtualizarApoio` e `renderTabelaNeg` **deixam de rodar o gross-up legado** e passam a
  exibir os números do **preview** (chamado com debounce a cada mudança de parâmetro/desconto).
- **Some a coluna HOJE**: o bloco "Validação HOJE × NOVO" vira o display normal (só o motor).
- A **estrutura** da tela é preservada (seleção de ambientes, inputs de desconto, modalidade
  de pagamento e plano de parcelas via `mod_fin`); **muda só a fonte dos valores**.
- Os campos por ambiente (`renderTabelaNeg`) usam os `VBNA`/`VAVA` do preview.

## 6. §4 — Limite de desconto

`_LIMITE_DESC_TOTAL = 35` (index.html:1836) passa a ser checado contra o **`%Desc_Tot` do
preview** (motor), no lugar do `_margemAtual` legado. Bloqueio mantém o comportamento atual
(impede fechar acima de 35%), só com a base correta.

## 7. §5 — Contrato

Sem mudança de código: o contrato já lê `valor_total`/`valor_liquido` do orçamento
(main.py:3276-3278). Após o §2, esses campos vêm do motor → o contrato reflete
automaticamente, e o `valor_liquido` exibido fica correto pela primeira vez. Contratos
**assinados** seguem protegidos (PDF é artefato baked + `_contrato_assinado` bloqueia edição).

## 8. §6 — Segurança (golden-master + fases revertíveis)

- **Golden-master:** antes do §2, fotografar `valor_total`/`valor_liquido` legados de todos os
  orçamentos (`scripts/snapshot_negociacao.py`, já existe — capturar `hoje`). Após o cutover,
  comparar old×new; cada diferença tem que ser explicada (é a correção do motor).
- **Fases revertíveis:**
  - **B1** — preview endpoint + UI lê o preview (displays no motor; persistência ainda legada).
  - **B2** — `_recalcular_orcamento` grava `valor_total`/`valor_liquido` do motor; contrato reflete.
  - **B3** — **reset de teste** (operação à parte, pós-cutover): cancela contratos, volta todos
    os projetos à fase de orçamento e recalcula tudo, para teste do fluxo inteiro + transições
    de fase. Com backup do banco antes.
- **Rollback:** branch a partir do `main` atual; tag `pre-refator-negociacao` como rede final.

## 9. §7 — Testes

- **E2E (preview):** `negociacao-preview` devolve os valores do motor (casa com a âncora LELEU
  do `mod_negociacao`); respeita escopo de loja (403/404 fora do escopo).
- **E2E (save):** salvar negociação grava `valor_total = Val_Cont` e `valor_liquido = Val_Liq`;
  trocar a modalidade de pagamento recalcula `valor_total`; o frontend não consegue mais
  sobrescrever `valor_total`/`valor_liquido` via PATCH.
- **E2E (limite):** `%Desc_Tot` do motor acima de 35% bloqueia; abaixo, libera.
- **Unitário:** `_recalcular_orcamento` e o preview compartilham o mesmo cálculo do motor
  (sem divergência).
- **Manual (sem harness JS):** tela de negociação/modal exibindo o motor ao vivo; salvar e
  conferir o contrato.
- **Golden-master:** relatório old×new dos `valor_total`/`valor_liquido` persistidos.

## 10. Arquivos afetados

- `main.py` — novo endpoint `negociacao-preview`; helper `_recalcular_orcamento`; chamadas no
  `POST /margens` e no `PATCH /api/orcamentos/<id>`; deixar de aceitar `valor_total`/`valor_liquido`.
- `mod_negociacao.py` — sem mudança (já validado); possível helper de integração `mod_fin`.
- `static/index.html` — `mpAtualizarApoio`/`renderTabelaNeg` consomem o preview; remover o
  gross-up legado; limite de desconto usa `%Desc_Tot`; remover envio de `valor_total`/`valor_liquido`.
- `scripts/` — golden-master old×new; (o reset de teste B3 é script à parte).
- `tests/` — E2E do preview, do save, do limite.
- docs — atualizar a base spec (marcar Fase B como em execução).
