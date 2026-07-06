### Task 2: Substituição de marcadores sobre HTML

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_MARK_RE` (regex de marcador já existente em `mod_contrato.py`).
- Produces: `_substituir_marcadores_html(html: str, mapping: dict) -> str` — substitui `[MARCADOR]` (chave MAIÚSCULA sem colchetes); marcador sem chave é mantido.

- [ ] **Step 1: Teste que falha**

```python
# tests/test_contrato_pdf.py
def test_subst_marcadores_html_substitui_e_mantem_desconhecido():
    from mod_contrato import _substituir_marcadores_html
    html = "<p>Nome: [NOME_CLIENTE] — Falta: [NAO_EXISTE]</p>"
    out = _substituir_marcadores_html(html, {"NOME_CLIENTE": "Ana Paula"})
    assert "Ana Paula" in out
    assert "[NAO_EXISTE]" in out
    assert "[NOME_CLIENTE]" not in out


def test_subst_marcadores_html_case_e_duplo_colchete():
    from mod_contrato import _substituir_marcadores_html
    out = _substituir_marcadores_html("N:[Num_Contrato] D:[[Data_Contrato]",
                                      {"NUM_CONTRATO": "INS-1", "DATA_CONTRATO": "02/07/2026"})
    assert "INS-1" in out and "02/07/2026" in out and "[" not in out
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k marcadores_html -q`
Expected: FAIL (ImportError / função não definida).

- [ ] **Step 3: Implementar**

Em `mod_contrato.py`, junto ao `_MARK_RE` existente:

```python
def _substituir_marcadores_html(html, mapping):
    """Substitui [MARCADOR] (case-insensitive, tolera '[[') numa string HTML/texto.
    Chaves do mapping em MAIÚSCULAS sem colchetes. Marcador sem chave é mantido."""
    def repl(m):
        chave = m.group(1).strip().upper().replace(" ", "_")
        return mapping[chave] if chave in mapping else m.group(0)
    return _MARK_RE.sub(repl, html)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k marcadores_html -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): substituicao de [MARCADOR] sobre HTML"
```

---

