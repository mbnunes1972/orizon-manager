### Task 3: Linhas de ambientes (HTML)

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_formatar_valor`, `_TRACO`.
- Produces: `_html_ambientes_linhas(itens_valores: list[tuple[str,float]]) -> str` — devolve `<tr>`s de dados (2 ambientes por linha; sobra ímpar com `_TRACO` nas 4 células). Não inclui header nem linha de total.

- [ ] **Step 1: Teste que falha**

```python
def test_html_ambientes_linhas_par_e_impar():
    from mod_contrato import _html_ambientes_linhas, _TRACO
    html = _html_ambientes_linhas([("Cozinha", 20000.0), ("Sala", 12000.0), ("Closet", 6000.0)])
    assert html.count("<tr") == 2                      # ceil(3/2)=2 linhas
    assert "Cozinha" in html and "R$ 20.000,00" in html
    assert "Sala" in html and "Closet" in html
    # sobra ímpar: 2ª metade da última linha em traços
    assert html.count(_TRACO) == 2                     # nome+valor vazios


def test_html_ambientes_linhas_vazio():
    from mod_contrato import _html_ambientes_linhas, _TRACO
    html = _html_ambientes_linhas([])
    assert html.count("<tr") == 1 and html.count(_TRACO) == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k html_ambientes -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
def _cel_amb(rotulo, valor):
    return (f'<td class="amb-rotulo">{rotulo}</td>'
            f'<td class="amb-valor">{valor}</td>')

def _html_ambientes_linhas(itens_valores):
    """<tr>s da tabela de ambientes: 2 por linha; sobra ímpar em traços."""
    from html import escape
    n = len(itens_valores)
    n_linhas = max(1, (n + 1) // 2)
    linhas = []
    for k in range(n_linhas):
        cels = []
        for slot in (0, 1):
            idx = 2 * k + slot
            if idx < n:
                nome, val = itens_valores[idx]
                cels.append(_cel_amb(escape(str(nome)), _formatar_valor(val)))
            else:
                cels.append(_cel_amb(_TRACO, _TRACO))
        linhas.append("<tr>" + "".join(cels) + "</tr>")
    return "\n".join(linhas)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k html_ambientes -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): linhas HTML de ambientes (2/linha, tracos na sobra)"
```

---

