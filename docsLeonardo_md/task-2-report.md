# Task 2 Report: Substituição de marcadores sobre HTML

## Status
**DONE**

## What was done
Implemented `_substituir_marcadores_html(html: str, mapping: dict) -> str` function in `mod_contrato.py` that substitutes `[MARCADOR]` markers in HTML/text strings, reusing the existing `_MARK_RE` regex pattern.

### Implementation Details
- **Location:** `mod_contrato.py`, lines 115-119
- **Reused:** Existing `_MARK_RE` regex pattern (line 105) — no new regex created
- **Logic:** Identical to `_aplica_mark()` but named for HTML context:
  - Extracts marker text from `[MARCADOR]` pattern (case-insensitive)
  - Converts to UPPERCASE, replaces spaces with underscores
  - Returns mapped value if key exists, otherwise preserves original marker
  - Tolerates `[[` (multiple opening brackets) via `_MARK_RE` pattern `\[+`

## TDD Evidence

### Step 1: Write failing tests ✓
Added two tests to `tests/test_contrato_pdf.py`:
1. `test_subst_marcadores_html_substitui_e_mantem_desconhecido()` — substitutes known markers, preserves unknown ones
2. `test_subst_marcadores_html_case_e_duplo_colchete()` — handles case-insensitivity and `[[` double brackets

### Step 2: RED phase ✓
```bash
$ python3 -m pytest tests/test_contrato_pdf.py -k marcadores_html -v
FAILED tests/test_contrato_pdf.py::test_subst_marcadores_html_substitui_e_mantem_desconhecido
FAILED tests/test_contrato_pdf.py::test_subst_marcadores_html_case_e_duplo_colchete
ImportError: cannot import name '_substituir_marcadores_html'
```

### Step 3: Implementation ✓
Added to `mod_contrato.py` (lines 115-119):
```python
def _substituir_marcadores_html(html, mapping):
    """Substitui [MARCADOR] (case-insensitive, tolera '[[') numa string HTML/texto.
    Chaves do mapping em MAIÚSCULAS sem colchetes. Marcador sem chave é mantido."""
    def repl(m):
        chave = m.group(1).strip().upper().replace(" ", "_")
        return mapping[chave] if chave in mapping else m.group(0)
    return _MARK_RE.sub(repl, html)
```

### Step 4: GREEN phase ✓
```bash
$ python3 -m pytest tests/test_contrato_pdf.py -k marcadores_html -v
PASSED tests/test_contrato_pdf.py::test_subst_marcadores_html_substitui_e_mantem_desconhecido
PASSED tests/test_contrato_pdf.py::test_subst_marcadores_html_case_e_duplo_colchete
2 passed, 1 deselected in 0.19s
```

### Step 5: Full suite validation ✓
```bash
$ python3 -m pytest tests/ -q
392 passed, 647 warnings in 10.92s
```
All tests pass — no regressions.

### Step 6: Commit ✓
```
a918bdf feat(contrato): substituicao de [MARCADOR] sobre HTML
```

## Files Changed
- `mod_contrato.py` — Added `_substituir_marcadores_html()` function (5 lines)
- `tests/test_contrato_pdf.py` — Added 2 test cases (14 lines)

## Self-Review

### Completeness ✓
- Substitutes known markers with mapping values
- Preserves unknown markers (e.g., `[NAO_EXISTE]` stays in output)
- Case-insensitive (converts to UPPERCASE internally)
- Tolerates `[[` double brackets via existing `_MARK_RE` pattern
- Handles spaces in markers (replaces with underscores)

### YAGNI ✓
- Only the function requested in brief implemented
- No extra utilities or configuration
- Reused existing `_MARK_RE` — no duplication of regex logic

### Test Coverage ✓
- `test_subst_marcadores_html_substitui_e_mantem_desconhecido()` tests substitution + unknown marker preservation
- `test_subst_marcadores_html_case_e_duplo_colchete()` tests case-insensitivity and `[[` tolerance
- Both tests verify real behavior, not just imports

### Code Quality ✓
- Pristine output — no debug code
- Consistent style with existing `_aplica_mark()` function
- Clear docstring

## Concerns
None. Task completed per brief specification.

---
**Executed:** 2026-07-02 | **Framework:** pytest 9.1.1 | **Python:** 3.14.4
