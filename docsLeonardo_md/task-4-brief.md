### Task 4: Grade de parcelas (HTML)

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_TRACO`. `pag` é o dict de `_parse_pagamento` (chaves `tipo`, `num_parcelas_int`, `valores` [24], `datas` [24]).
- Produces: `_html_parcelas_linhas(pag: dict) -> str` — devolve `<tr>`s da grade (3 parcelas por linha); **só as linhas com parcela**; slots vazios da última linha em `_TRACO`; cartão sem data (data em branco).

- [ ] **Step 1: Teste que falha**

```python
def test_html_parcelas_linhas_elimina_vazias_e_tracos():
    from mod_contrato import _html_parcelas_linhas, _TRACO
    pag = {"tipo": "aymore", "num_parcelas_int": 4,
           "valores": ["R$ 4.000,00"] * 4 + [""] * 20,
           "datas": ["10/08/2026", "10/09/2026", "10/10/2026", "10/11/2026"] + [""] * 20}
    html = _html_parcelas_linhas(pag)
    assert html.count("<tr") == 2                       # 4 parcelas -> ceil(4/3)=2 linhas
    assert "R$ 4.000,00" in html and "10/08/2026" in html
    assert _TRACO in html                               # slots 5,6 vazios na 2a linha


def test_html_parcelas_linhas_cartao_sem_data():
    from mod_contrato import _html_parcelas_linhas
    pag = {"tipo": "cartao", "num_parcelas_int": 3,
           "valores": ["R$ 100,00"] * 3 + [""] * 21, "datas": [""] * 24}
    html = _html_parcelas_linhas(pag)
    assert html.count("<tr") == 1 and html.count("R$ 100,00") == 3
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k html_parcelas -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
def _html_parcelas_linhas(pag):
    """<tr>s da grade de parcelas: 3 por linha, só linhas usadas, tracos no resto."""
    tipo = pag.get("tipo", "")
    num = pag.get("num_parcelas_int", 0)
    valores = pag.get("valores", [""] * 24)
    datas = pag.get("datas", [""] * 24)
    n_linhas = (num + 2) // 3  # ceil(num/3)
    linhas = []
    for gi in range(n_linhas):
        cels = []
        for j in range(3):
            p = gi * 3 + j + 1  # 1-based
            if p <= num and valores[p - 1]:
                val = valores[p - 1]
                data = "" if tipo == "cartao" else (datas[p - 1] or _TRACO)
            else:
                val, data = _TRACO, _TRACO
            cels.append(f'<td class="pc-valor">{val}</td>'
                        f'<td class="pc-data">{data}</td>')
        linhas.append("<tr>" + "".join(cels) + "</tr>")
    return "\n".join(linhas)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k html_parcelas -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): grade HTML de parcelas (linhas usadas, tracos, cartao sem data)"
```

---

