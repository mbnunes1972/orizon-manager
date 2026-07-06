### Task 10: Integração da rota + wire do texto complementar

**Files:**
- Modify: `main.py` (rota `POST /api/projetos/<nome>/contrato`, ~L3436–3570)
- Test: `tests/test_fluxo_completo_e2e.py` (ajuste do hook, se necessário)

**Interfaces:**
- Consumes: `gerar_pdf_contrato(contrato.id, variaveis)` (nova, retorna PDF).

- [ ] **Step 1: Trocar a geração e remover o fallback docx**

No handler, substitua o bloco:

```python
                    aviso = None
                    try:
                        pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                        contrato.pdf_path = pdf_path
                    except LibreOfficeIndisponivel as lo:
                        # Salva o .docx e avança mesmo sem PDF
                        ...
```

por:

```python
                    aviso = None
                    pdf_path = gerar_pdf_contrato(contrato.id, variaveis)
                    contrato.pdf_path = pdf_path
```

(remova completamente o `except LibreOfficeIndisponivel` e seu corpo.)

- [ ] **Step 2: Remover imports mortos**

No topo de `main.py`, remova `LibreOfficeIndisponivel` do import de `mod_contrato` (e qualquer uso remanescente). O `variaveis` já traz `"adendo"` → o motor mapeia `TEXTO_COMPLEMENTAR` a partir dele (Task 7); nenhuma mudança extra necessária aqui.

- [ ] **Step 3: Ajustar o E2E (hook de contrato)**

Em `tests/test_fluxo_completo_e2e.py`, o passo 5 exercita o hook de geração. Rode a suíte E2E; se o teste assumia LibreOffice ausente / `.docx`, atualize para o novo caminho (PDF sempre; sem `LibreOfficeIndisponivel`).

Run: `python3 -m pytest tests/test_fluxo_completo_e2e.py -q`
Expected: PASS (ajuste o teste se referenciar o caminho antigo).

- [ ] **Step 4: Rodar a suíte inteira**

Run: `python3 -m pytest -q`
Expected: PASS (com os testes de docx ainda presentes vão falhar — serão removidos na Task 11; se preferir, execute Task 11 antes deste Step).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_fluxo_completo_e2e.py
git commit -m "feat(contrato): rota gera PDF via novo motor; remove fallback LibreOffice"
```

---

