### Task 9: Motor de PDF (WeasyPrint)

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_montar_html_contrato`, `CONTRATO_TEMPLATE_DIR`, `CONTRATOS_DIR`.
- Produces: `gerar_pdf_contrato(contrato_id: int, ctx: dict, destino: str = None) -> str` — renderiza o HTML final em PDF e devolve o caminho `CONTRATOS/contrato_<id>.pdf`. **Substitui** a `gerar_pdf_contrato` atual (docx→LibreOffice).

- [ ] **Step 1: Teste que falha (smoke, pula sem weasyprint)**

```python
@skip_sem_weasy
def test_gerar_pdf_contrato_gera_pdf(tmp_path):
    import json, os
    from mod_contrato import gerar_pdf_contrato, construir_contexto
    loja = {"nome": "L", "cnpj": "1", "codigo": "INS",
            "testemunha1_nome": "J", "testemunha1_cpf": "1",
            "testemunha2_nome": "F", "testemunha2_cpf": "2"}
    ctx = construir_contexto(
        {"nome": "Ana", "cpf": "1", "email": "a@x", "telefone": "1", "logradouro": "R",
         "numero": "1", "complemento": "", "bairro": "C", "cidade": "S", "cep": "1",
         "estado": "SP", "inst_mesmo_residencial": True},
        {"nome": "Z", "telefone": "1", "email": "z@x"},
        json.dumps({"tipo": "aymore", "nome_forma": "A", "total_cliente": 100.0,
                    "parcelas": [{"num": 1, "data": "18/07/2026", "valor": 100.0}]}),
        loja)
    ctx["num_contrato"] = "INS-1"; ctx["_ambientes"] = [("Cozinha", 100.0)]
    path = gerar_pdf_contrato(99001, ctx, destino=str(tmp_path))
    assert path.endswith(".pdf") and os.path.getsize(path) > 1000
    with open(path, "rb") as f:
        assert f.read(5) == b"%PDF-"
```

- [ ] **Step 2: Rodar e ver falhar (ou skip)**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k gerar_pdf_contrato -q`
Expected: FAIL (nova assinatura/erro) — ou SKIP se weasyprint ausente (nesse caso, valide o motor manualmente no Step 4).

- [ ] **Step 3: Implementar**

```python
def gerar_pdf_contrato(contrato_id, ctx, destino=None):
    """Renderiza o contrato (HTML -> PDF) via WeasyPrint. Retorna o caminho do PDF."""
    from weasyprint import HTML
    destino = destino or CONTRATOS_DIR
    os.makedirs(destino, exist_ok=True)
    html = _montar_html_contrato(ctx)
    pdf_path = os.path.join(destino, f"contrato_{contrato_id}.pdf")
    HTML(string=html, base_url=CONTRATO_TEMPLATE_DIR).write_pdf(pdf_path)
    return pdf_path
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k gerar_pdf_contrato -q`
Expected: PASS (ou SKIP sem weasyprint — nesse caso, gere um PDF manualmente com o snippet do teste e confira o `%PDF-`).

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): motor de PDF via WeasyPrint (substitui docx->LibreOffice)"
```

---

