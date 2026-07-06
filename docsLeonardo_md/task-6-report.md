# Task 6: Assets — CSS, shell HTML e logo

## Status
✅ COMPLETED

## Commit
- **3112c17** `feat(contrato): assets do template (css, shell html, logo)`

## Implementation Summary

### Step 1: Logo Extraction
- Executed Python snippet to extract logo from `modelo_contrato_mapeado.docx`
- Found single image in `word/media/image1.png`
- Extracted PNG and saved as `contrato_template/logo_dalmobile.png` (11,782 bytes)

### Step 2: HTML Shell Creation
- Created `contrato_template/contrato.html` with DOCTYPE HTML5, pt-BR language, charset UTF-8
- Shell contains both required markers: `<!--CAPA-->` and `<!--CORPO-->`
- Linked to `contrato.css` via `<link>` tag
- File size: 257 bytes

### Step 3: CSS Stylesheet Creation
- Created `contrato_template/contrato.css` with WeasyPrint directives
- Includes `@page` rules for A4 (1cm margins), page header (via `element(cabecalho)`), and footer (page counter)
- Style classes for contract sections, tables, clauses (levels 1-3 + alinea), break control
- Font: DejaVu Sans, 8.5pt base
- Colors: #3b2f2a background, #C4A265 accent
- File size: 1,755 bytes

### Step 4: Constant + Test
- Added `CONTRATO_TEMPLATE_DIR` constant to `mod_contrato.py`:
  ```python
  CONTRATO_TEMPLATE_DIR = os.path.join(_THIS_DIR, "contrato_template")
  ```
- Placed alongside `CONTRATOS_DIR`, after `_THIS_DIR` definition
- Added `test_assets_template_existem()` to `tests/test_contrato_pdf.py`
  - Verifies all three files exist under `CONTRATO_TEMPLATE_DIR`
  - Confirms HTML shell contains both `<!--CAPA-->` and `<!--CORPO-->` markers

### Step 5: Test Verification
- `test_assets_template_existem`: ✅ PASS
- Full suite `tests/test_contrato_pdf.py`: ✅ 10/10 PASS (0.20s)

### Step 6: Git Commit
- Added: `contrato_template/`, `mod_contrato.py`, `tests/test_contrato_pdf.py`
- Message: `feat(contrato): assets do template (css, shell html, logo)`
- Branch: `feat/contrato-html-pdf`

## Files Created/Modified
- ✅ `contrato_template/contrato.html` (new)
- ✅ `contrato_template/contrato.css` (new)
- ✅ `contrato_template/logo_dalmobile.png` (new, extracted)
- ✅ `mod_contrato.py` (modified — added constant)
- ✅ `tests/test_contrato_pdf.py` (modified — added test)

## Self-Review Checklist
- ✅ All 3 assets exist in `contrato_template/`
- ✅ HTML shell contains exact markers `<!--CAPA-->` and `<!--CORPO-->`
- ✅ CSS content matches brief exactly (WeasyPrint directives, classes, styling)
- ✅ `CONTRATO_TEMPLATE_DIR` constant defined correctly in `mod_contrato.py`
- ✅ Test verifies file existence and shell markers
- ✅ Test suite passes (10/10)
- ✅ Commit message matches brief exactly
- ✅ Working tree clean (only intended changes committed)

## Logo Selection
**Image: `word/media/image1.png`**
- Only image found in `.docx` media folder
- Extracted as PNG (not JPG/JPEG)
- Matches brief preference: "normalmente a 1ª / maior png"
- No ambiguity; confirmed single media file

## Concerns
None. All steps completed successfully. Tests pass. Assets are properly integrated with the template infrastructure.
