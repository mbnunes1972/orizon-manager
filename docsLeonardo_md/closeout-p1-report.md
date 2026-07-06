# Closeout Report — edição Out_Forn

**Status:** DONE — ambas as partes entregues, sem regressão.

**Commits (2):**
1. `4911c8d` feat(financeira): rota PUT out-forn por orcamento
2. `92a2222` feat(financeira): campo Out_Forn editavel no modal de parametros

**Backend (Parte A):**
- Rota inserida em `main.py` após a rota `/descontos` (~linha 3711), antes do 404 catch-all.
- Espelha exatamente o padrão de `/descontos`: sessão → `escopo_operacional` → `_obj_da_loja` → grava → `_negociacao_breakdown` na resposta.
- TDD: RED (404) → GREEN; suíte completa: **343 passed, 0 failed**.

**Frontend (Parte B):**
- Input `#mp-out-forn` adicionado no bloco `#mp-apoio` após `mp-a-marg-cont`.
- Preenchido em `abrirModalParams` com `_previewNeg.Out_Forn` (ou 0).
- `onchange` chama `mpSalvarOutForn(val)` → PUT → `_aplicarPreviewNaTela(d.sombra)`.
- Modo leitura: travado automaticamente por `_aplicarModoLeituraParams` (varredura do modal inteiro).
- Sanity estático: 6/6 checks OK (campo 1×, handler, função async, PUT, aplicarPreview, prefill).

**Concerns:** nenhum.

**Report path:** `/mnt/e/2026/estudo_de_ia/omie_v3/.superpowers/sdd/closeout-p1-report.md`

---

## Fix: clamp + IDOR

**Status:** DONE — sem regressão.

**Commit:** `059c7c5` fix(financeira): clamp out_forn>=0 + valida corpo + testes IDOR/clamp (review)

**Testes out_forn:** 3 passed (test_put_out_forn existente + test_out_forn_fora_de_escopo_403 + test_out_forn_clamp_negativo novos).

**Suíte completa:** 345 passed, 0 failed (8.96s).

**Mudanças:** `main.py` — wrap de `float()` em try/except (400 em corpo inválido) + `max(0.0, …)` (clamp). `tests/test_provisoes_e2e.py` — 2 novos testes IDOR e clamp.

**Concerns:** nenhum.
