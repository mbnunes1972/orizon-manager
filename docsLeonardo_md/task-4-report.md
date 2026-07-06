# Task 4 Report: Grade de parcelas (HTML)

## Status: DONE

## Summary
Implemented `_html_parcelas_linhas(pag: dict) -> str` to generate HTML `<tr>` rows for the payment installment grid on the contract cover. The function produces 3 installments per row, eliminates empty rows, fills empty slots with `_TRACO`, and handles card payments without dates.

## TDD Evidence

### RED (Step 1-2)
Added two test functions to `tests/test_contrato_pdf.py`:
- `test_html_parcelas_linhas_elimina_vazias_e_tracos`: Verifies correct row count (ceil(4/3)=2), data presence, and empty slot filling
- `test_html_parcelas_linhas_cartao_sem_data`: Verifies card payments produce single row with no dates

Command: `python3 -m pytest tests/test_contrato_pdf.py -k html_parcelas -q`

Result: **FAILED (2 failures)** — ImportError: `_html_parcelas_linhas` does not exist.

### GREEN (Step 3-4)
Implemented `_html_parcelas_linhas` in `mod_contrato.py`:
- Calculates `n_linhas = ceil(num_parcelas / 3)` using `(num + 2) // 3`
- Iterates through rows and columns, generating 3 parcels per row
- Fills empty slots with `_TRACO` for both value and date
- For card payments (`tipo == "cartao"`), sets date to empty string `""`
- Returns newline-joined `<tr>` elements with proper class names (`pc-valor`, `pc-data`)

Command: `python3 -m pytest tests/test_contrato_pdf.py -k html_parcelas -q`

Result: **PASSED (2 passed in 0.20s)**

### Full suite (Step 5)
Command: `python3 -m pytest tests/test_contrato_pdf.py -q`

Result: **7 passed in 0.20s** — all tests pass, no regressions.

## Files Modified
- **mod_contrato.py**: Added `_html_parcelas_linhas` function (19 lines)
- **tests/test_contrato_pdf.py**: Added 2 test functions (12 lines)

## Commit
- SHA: `2e358ab`
- Message: `feat(contrato): grade HTML de parcelas (linhas usadas, tracos, cartao sem data)`

## Self-Review Checklist
- ✓ Row count: ceil(num/3) formula correctly implemented for 4→2 rows, 3→1 row
- ✓ Empty slots in last row filled with `_TRACO` (4 parcels → slots 5,6 get tracos)
- ✓ Card payments without dates: `tipo == "cartao"` sets date to `""`
- ✓ Reuses existing `_TRACO` constant (defined line 21)
- ✓ No over-engineering (YAGNI): simple, direct implementation following `_html_ambientes_linhas` pattern
- ✓ Tests verify actual behavior: row count, value/date presence, proper HTML structure
- ✓ Clean output: proper HTML `<tr>` and `<td>` tags with class names

## Concerns
None. Implementation follows established patterns from existing code and passes all tests.
