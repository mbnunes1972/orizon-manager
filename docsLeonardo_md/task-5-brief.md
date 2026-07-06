### Task 5: Nível de cláusula + corpo Markdown→HTML

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: lib `markdown`.
- Produces:
  - `_nivel_clausula(texto: str) -> int | None` — nº do nível pela numeração literal no início da linha (`2.` → 1, `2.3.` → 2, `2.3.1.` → 3); `a)`/`b)` → 4 (alínea); `None` se não for cláusula numerada.
  - `_html_corpo(md_texto: str) -> str` — Markdown → HTML, com classe `cl-N` nos `<p>` de cláusula (nível N) e `cl-alinea` nas alíneas.

- [ ] **Step 1: Teste que falha**

```python
def test_nivel_clausula():
    from mod_contrato import _nivel_clausula
    assert _nivel_clausula("2. Após a assinatura...") == 1
    assert _nivel_clausula("2.3. A execução...") == 2
    assert _nivel_clausula("2.3.1. O Termo...") == 3
    assert _nivel_clausula("a) MEDIÇÃO: ...") == 4
    assert _nivel_clausula("Texto sem número") is None


def test_html_corpo_aplica_classe_por_nivel():
    from mod_contrato import _html_corpo
    md = "# CLÁUSULA PRIMEIRA\n\n1. Item um.\n\n1.1. Sub item.\n\na) alinea.\n"
    html = _html_corpo(md)
    assert "<h1" in html or "<h2" in html            # título de cláusula
    assert 'class="cl-1"' in html and "Item um" in html
    assert 'class="cl-2"' in html
    assert 'class="cl-alinea"' in html
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k "nivel or html_corpo" -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
import re as _re2

_RE_NUM = _re2.compile(r'^\s*(\d+(?:\.\d+)*)\.\s')
_RE_ALINEA = _re2.compile(r'^\s*[a-z]\)\s')

def _nivel_clausula(texto):
    m = _RE_NUM.match(texto or "")
    if m:
        return m.group(1).count(".") + 1
    if _RE_ALINEA.match(texto or ""):
        return 4
    return None

def _html_corpo(md_texto):
    """Markdown -> HTML com classe cl-N por nível de cláusula (numeração literal)."""
    import markdown
    html = markdown.markdown(md_texto, output_format="html5")

    def _classificar(m):
        interno = m.group(1)
        nivel = _nivel_clausula(interno)
        if nivel is None:
            return m.group(0)
        classe = "cl-alinea" if nivel == 4 else f"cl-{nivel}"
        return f'<p class="{classe}">{interno}</p>'

    return _re2.sub(r'<p>(.*?)</p>', _classificar, html, flags=_re2.DOTALL)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k "nivel or html_corpo" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): corpo Markdown->HTML com classe por nivel de clausula"
```

---

