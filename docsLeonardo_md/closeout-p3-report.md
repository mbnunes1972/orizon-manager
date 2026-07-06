# Closeout Report — Contract Staleness Guard

**Status:** DONE — 357 passed, 0 regressions

## Commits (2)
1. `1382ad9` — `feat(contrato): flag 'desatualizado' quando pagamento mudou apos a geracao`
2. `66f4fcc` — `feat(contrato): aviso de contrato desatualizado na UI da etapa`

## Backend changes
- `mod_contrato.py`: added `contrato_desatualizado()` helper (lines 360–375)
- `main.py`: GET `/api/projetos/<nome>/contrato` now fetches `_orc_src` via `db.get(Orcamento, ...)` and adds `desatualizado` + `orcamento_id` to response dict (lines 1201–1219)

## Tests — RED → GREEN
- `tests/test_contrato_staleness.py`: 12 tests (10 pure unit + 2 E2E)
- All tests confirmed RED (AttributeError) before implementation, GREEN after
- Full suite: 357 passed, 522 warnings (only pre-existing datetime.utcnow deprecations)

## Frontend
- `static/index.html` line 8116: ternary banner in `renderContratoUI()` — only renders when `contrato.desatualizado` is truthy; uses `var(--warn)` + `#1a1200` background matching LibreOffice warn banner style

## Concerns
- None. `db.get()` returns `None` if orcamento deleted (guarded by `if _orc_src else None`).

**Report path:** `/mnt/e/2026/estudo_de_ia/omie_v3/.superpowers/sdd/closeout-p3-report.md`
