### Task 6: Assets — CSS, shell HTML e logo

**Files:**
- Create: `contrato_template/contrato.css`
- Create: `contrato_template/contrato.html`
- Create: `contrato_template/logo_dalmobile.png`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Produces: constante `CONTRATO_TEMPLATE_DIR` em `mod_contrato.py` apontando para `contrato_template/`; o shell contém os marcadores de bloco `<!--CAPA-->` e `<!--CORPO-->`.

- [ ] **Step 1: Extrair o logo do `.docx` (uma vez)**

Run:
```bash
python3 - <<'PY'
import zipfile, os
z = zipfile.ZipFile("modelo_contrato_mapeado.docx")
imgs = [n for n in z.namelist() if n.startswith("word/media/")]
print("midias:", imgs)
os.makedirs("contrato_template", exist_ok=True)
# escolha a imagem do logo (normalmente a 1a / maior png)
alvo = next((n for n in imgs if n.lower().endswith((".png",".jpg",".jpeg"))), None)
assert alvo, "nenhuma imagem no docx"
with open("contrato_template/logo_dalmobile.png", "wb") as f:
    f.write(z.read(alvo))
print("logo salvo de", alvo)
PY
```
Expected: imprime as mídias e salva `contrato_template/logo_dalmobile.png`. Se houver mais de uma imagem, confira qual é o logo (abrir a imagem) e reexecute apontando para a correta.

- [ ] **Step 2: Criar o shell `contrato.html`**

```html
<!-- contrato_template/contrato.html -->
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="contrato.css">
</head>
<body>
  <!--CAPA-->
  <div class="contrato-corpo">
    <!--CORPO-->
  </div>
</body>
</html>
```

- [ ] **Step 3: Criar `contrato.css`**

```css
/* contrato_template/contrato.css */
@page {
  size: A4;
  margin: 1cm;
  @top-left  { content: element(cabecalho); }
  @bottom-center { content: "Página " counter(page) " de " counter(pages);
                   font-size: 7pt; color: #888; }
}
#cabecalho { position: running(cabecalho); width: 100%;
             border-bottom: 2px solid #000; padding-bottom: 2px; }
#cabecalho .logo { height: 34px; }
#cabecalho .num  { float: right; text-align: right; font-weight: bold; font-size: 9pt; }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 8.5pt; color: #000; }

/* ---- Capa ---- */
.secao { break-inside: avoid; margin-bottom: 6pt; }
.secao > .titulo { background: #3b2f2a; color: #C4A265; font-weight: bold;
                   padding: 3pt 6pt; font-size: 10pt; }
.secao table { width: 100%; border-collapse: collapse; }
.secao td { border: 0.5px solid #ddd; padding: 3pt 6pt; vertical-align: top; }
.rotulo { display: block; color: #888888; font-size: 7pt; }
.valor  { display: block; font-weight: bold; font-size: 8.5pt; }
.amb-rotulo { color: #888888; font-size: 7pt; }
.amb-valor  { font-weight: bold; }
.total-lbl { font-weight: bold; text-align: center; }
.total-val { font-weight: bold; text-align: right; }
.pc-valor, .pc-data { font-size: 8pt; }
.quebra-capa { break-after: page; }

/* ---- Cláusulas (números literais + hanging por nível) ---- */
.contrato-corpo h1, .contrato-corpo h2 { font-size: 9.5pt; font-weight: bold;
  margin: 8pt 0 3pt; }
.contrato-corpo p { margin: 0 0 4pt; text-align: justify; }
.cl-1 { padding-left: 1.2cm; text-indent: -1.2cm; }
.cl-2 { padding-left: 1.4cm; text-indent: -1.0cm; }
.cl-3 { padding-left: 1.7cm; text-indent: -1.0cm; }
.cl-alinea { padding-left: 1.9cm; text-indent: -0.8cm; }
```

- [ ] **Step 4: Teste (assets existem e constante aponta certo)**

```python
def test_assets_template_existem():
    import os
    from mod_contrato import CONTRATO_TEMPLATE_DIR
    for f in ("contrato.css", "contrato.html", "logo_dalmobile.png"):
        assert os.path.exists(os.path.join(CONTRATO_TEMPLATE_DIR, f)), f
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"), encoding="utf-8").read()
    assert "<!--CAPA-->" in shell and "<!--CORPO-->" in shell
```

Em `mod_contrato.py` adicione:

```python
CONTRATO_TEMPLATE_DIR = os.path.join(_THIS_DIR, "contrato_template")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k assets_template -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add contrato_template/ mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): assets do template (css, shell html, logo)"
```

---

