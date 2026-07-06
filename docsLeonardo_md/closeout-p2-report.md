# Closeout Report: parametros_default_loja wiring (P2)

**Date:** 2026-06-27

## What changed

### `main.py` — `_negociacao_breakdown` (lines ~4356-4403)

**Refactored** the function so the loja `cfg` is loaded **once**, near the top (right after `proj = ...`), instead of only at the end in the provisions block.

**Changed** the `params` line so projects without a saved `parametros_json` now receive `mod_orcamento_params.parametros_default_loja(cfg)` instead of an empty `{}`. This injects the loja's negotiation defaults (`comissao_arq_pct`, `fidelidade_pct`, `carga_trib`) into the motor calculation.

**Removed** the now-duplicate `import mod_provisoes` and duplicate loja/cfg loading that previously appeared only in the provisions block. The same `cfg` reference is reused for both purposes.

### `tests/test_provisoes_e2e.py`

**Added** `test_breakdown_usa_carga_trib_da_loja_quando_projeto_sem_params`: sets `carga_trib_pct = 10.0` on the loja, clears `proj.parametros_json = None`, attaches a `PoolAmbiente` (VBVA=10000, CFA=4000), calls `_negociacao_breakdown`, asserts `d["Prov_Imp"] > 0`.

## RED → GREEN

- **RED:** `assert d["Prov_Imp"] > 0` failed with `0.0 > 0` — with `params = {}`, `carga_trib` resolved to 0 (missing key → `_f(None)` → 0).
- **GREEN:** After wiring `parametros_default_loja(cfg)`, `carga_trib = 10.0` flows through `mod_negociacao.calcular_orcamento` → `Prov_Imp > 0`.

## Full suite

- **342 passed, 0 failed** (8.86s)
- No regressions.

## Concerns

None. The refactor is a pure consolidation — behavior for projects WITH saved `parametros_json` is unchanged (the `json.loads` branch runs identically). The only behavioral change is for projects without params, which now get loja defaults instead of PARAMETROS_DEFAULT (or empty dict). This is the intended design.
