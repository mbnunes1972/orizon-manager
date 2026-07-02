# Contrato em HTML/Markdown → PDF — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar o contrato como PDF a partir de HTML (capa) + Markdown (cláusulas) via WeasyPrint, aposentando o template `.docx` + LibreOffice e a rota de edição in-place.

**Architecture:** `mod_contrato.py` mantém os helpers de dado/cálculo e ganha um motor de PDF. A capa (5 seções) é montada como HTML com linhas dinâmicas de ambientes/parcelas; as cláusulas vêm de `contrato_template/contrato.md` (números literais) convertidas para HTML com classe por nível; um shell HTML + `contrato.css` dá layout (margens, cabeçalho/rodapé corridos, alinhamento). WeasyPrint renderiza o PDF. A assinatura (hash em DB) não muda.

**Tech Stack:** Python 3 (`http.server`, sem framework), `weasyprint`, `markdown` (python-markdown), SQLAlchemy, pytest.

## Global Constraints

- Servidor: **Ubuntu 24.04**, deps via **apt** (PEP 668): `weasyprint` (67.0), `python3-markdown` (3.10). Dev (WSL, Python 3.14): `pip`.
- **Português (pt-BR)** em copy/rótulos e mensagens; manter os textos de rótulo existentes ("Nome", "CPF/CNPJ", "Logradouro", "Bairro", "VALOR DO CONTRATO", "Forma de Pagamento" etc.).
- Marcadores: `[MARCADOR]` em **MAIÚSCULAS**, tolera `[[`; marcador sem chave é **mantido** (não apagado).
- Traço de slot vazio: a constante `_TRACO = "--------"` (já existe em `mod_contrato.py`).
- **Sem edição in-place**: contrato é sempre PDF; nenhum fallback para `.docx`.
- **Escopo: só o contrato.** LibreOffice permanece como dependência **da proposta** — não desinstalar do servidor nesta frente.
- Rodar Python com `python3` (não `python`). Suíte: `python3 -m pytest`.
- TDD: teste falha primeiro; commits frequentes; DRY; YAGNI.

---

## Estrutura de arquivos

- **Modificar** `mod_contrato.py` — remove o caminho docx; adiciona o motor de PDF (funções `_substituir_marcadores_html`, `_html_ambientes_linhas`, `_html_parcelas_linhas`, `_html_capa`, `_nivel_clausula`, `_html_corpo`, `_montar_html_contrato`, `gerar_pdf_contrato`).
- **Criar** `contrato_template/contrato.css` — folha de impressão (`@page`, cabeçalho/rodapé, capa, cláusulas).
- **Criar** `contrato_template/contrato.html` — shell com pontos de injeção `<!--CAPA-->` e `<!--CORPO-->`.
- **Criar** `contrato_template/contrato.md` — texto das cláusulas migrado do `.docx` (Task 8).
- **Criar** `contrato_template/logo_dalmobile.png` — extraído do `.docx` (Task 6).
- **Modificar** `main.py` — rota `POST /contrato` chama o novo motor; remove `except LibreOfficeIndisponivel`; wire `TEXTO_COMPLEMENTAR`. Remove rota `POST /contrato/editar`.
- **Modificar** `requirements.txt` — adiciona `weasyprint`, `markdown`.
- **Modificar** `tests/test_contrato.py` — novos testes; remove os específicos de docx.
- **Criar** `scripts/extrair_clausulas_docx.py` — script de migração (Task 8).

---

### Task 1: Dependências + guard de teste

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_contrato_pdf.py`

**Interfaces:**
- Produces: marcador de skip `_weasy_ausente` reutilizado pelos testes de PDF.

- [ ] **Step 1: Adicionar deps ao requirements.txt**

No topo (bloco de deps de runtime), acrescente após `SQLAlchemy`:

```
weasyprint
markdown
```

E no comentário do `apt` do servidor, acrescente `weasyprint python3-markdown` à linha de instalação.

- [ ] **Step 2: Instalar no dev**

Run: `python3 -m pip install --user weasyprint markdown`
Expected: instala sem erro (se falhar por libs de sistema, anote — os testes de PDF serão pulados; o restante roda).

- [ ] **Step 3: Criar o arquivo de teste com o guard**

```python
# tests/test_contrato_pdf.py
import importlib.util
import pytest

_weasy_ausente = importlib.util.find_spec("weasyprint") is None
skip_sem_weasy = pytest.mark.skipif(_weasy_ausente, reason="weasyprint não instalado")


def test_markdown_disponivel():
    import markdown  # noqa: F401
```

- [ ] **Step 4: Rodar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -q`
Expected: PASS (1 passed) — se `markdown` não instalou, corrigir a instalação antes de seguir.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_contrato_pdf.py
git commit -m "chore(contrato): deps weasyprint+markdown e guard de teste de PDF"
```

---

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

### Task 7: Capa e HTML final

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato_pdf.py`

**Interfaces:**
- Consumes: `_html_ambientes_linhas`, `_html_parcelas_linhas`, `_html_corpo`, `_substituir_marcadores_html`, `_montar_mapping`, `CONTRATO_TEMPLATE_DIR`.
- Produces:
  - `_html_capa(ctx: dict) -> str` — HTML das 5 seções (identificação/endereços com rótulos+`[MARCADORES]`; ambientes e parcelas com linhas dinâmicas; termina com `<div class="quebra-capa"></div>`).
  - `_montar_html_contrato(ctx: dict) -> str` — injeta capa+corpo no shell e substitui `[MARCADORES]` (inclui `TEXTO_COMPLEMENTAR = ctx.get("adendo","")`).

- [ ] **Step 1: Teste que falha**

```python
def test_montar_html_contrato_substitui_e_inclui_secoes():
    import json
    from mod_contrato import construir_contexto, _montar_html_contrato
    loja = {"nome": "L", "cnpj": "1", "codigo": "INS",
            "testemunha1_nome": "J", "testemunha1_cpf": "1",
            "testemunha2_nome": "F", "testemunha2_cpf": "2"}
    ctx = construir_contexto(
        {"nome": "Ana Paula", "cpf": "111.222.333-44", "email": "a@x.com",
         "telefone": "(12)9", "logradouro": "Rua A", "numero": "10", "complemento": "",
         "bairro": "Jardim Aquarius", "cidade": "SJC", "cep": "12000", "estado": "SP",
         "inst_mesmo_residencial": True},
        {"nome": "Z", "telefone": "(12)9", "email": "z@x.com"},
        json.dumps({"tipo": "aymore", "nome_forma": "Aymoré", "total_cliente": 26445.67,
                    "parcelas": [{"num": i + 1, "data": f"18/0{7+i}/2026", "valor": 4820.0}
                                 for i in range(3)]}),
        loja)
    ctx["num_contrato"] = "INS-1"
    ctx["adendo"] = "Acordo especial de entrega."
    ctx["_ambientes"] = [("Cozinha", 12345.67), ("Sala", 14100.0)]
    html = _montar_html_contrato(ctx)
    assert "Ana Paula" in html and "Jardim Aquarius" in html
    assert "Cozinha" in html and "R$ 12.345,67" in html
    assert "R$ 4.820,00" in html                     # parcela
    assert "Acordo especial de entrega." in html     # TEXTO_COMPLEMENTAR
    assert "[" not in html.split("contrato-corpo")[0] or "NOME_" not in html  # marcadores da capa consumidos
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Adicione em `mod_contrato.py` (ajuste os rótulos/estrutura das seções 1–3 conforme o `.docx` atual — Nome/CPF/Email/Telefone; endereço residencial e de instalação):

```python
def _html_capa(ctx):
    amb = _html_ambientes_linhas(ctx.get("_ambientes") or [])
    parc = _html_parcelas_linhas(ctx.get("_pag") or {})
    return f"""
<div id="cabecalho">
  <img class="logo" src="logo_dalmobile.png">
  <span class="num">[NUM_CONTRATO]<br>[DATA_CONTRATO]</span>
</div>

<div class="secao">
  <div class="titulo">1. Identificação do Cliente</div>
  <table><tr>
    <td><span class="rotulo">Nome</span><span class="valor">[NOME_CLIENTE]</span></td>
    <td><span class="rotulo">CPF/CNPJ</span><span class="valor">[CPF]</span></td>
  </tr><tr>
    <td><span class="rotulo">E-mail</span><span class="valor">[EMAIL]</span></td>
    <td><span class="rotulo">Telefone</span><span class="valor">[TELEFONE]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">2. Endereço Residencial</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[RES_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[RES_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[RES_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[RES_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[RES_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[RES_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[RES_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">3. Endereço de Instalação</div>
  <table><tr>
    <td colspan="3"><span class="rotulo">Logradouro</span><span class="valor">[INST_LOGRADOURO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Número</span><span class="valor">[INST_NUMERO]</span></td>
    <td><span class="rotulo">Complemento</span><span class="valor">[INST_COMPLEMENTO]</span></td>
    <td><span class="rotulo">Bairro</span><span class="valor">[INST_BAIRRO]</span></td>
  </tr><tr>
    <td><span class="rotulo">Cidade</span><span class="valor">[INST_CIDADE]</span></td>
    <td><span class="rotulo">CEP</span><span class="valor">[INST_CEP]</span></td>
    <td><span class="rotulo">Estado/UF</span><span class="valor">[INST_UF]</span></td>
  </tr></table>
</div>

<div class="secao">
  <div class="titulo">4. Ambientes do Projeto</div>
  <table>
    {amb}
    <tr><td class="total-lbl" colspan="2">VALOR DO CONTRATO</td>
        <td class="total-val" colspan="2">[TOTAL_CONTRATO]</td></tr>
  </table>
</div>

<div class="secao">
  <div class="titulo">5. Forma de Pagamento</div>
  <table><tr>
    <td><span class="rotulo">Entrada</span><span class="valor">[VALOR_ENTRADA]</span></td>
    <td><span class="rotulo">Tipo</span><span class="valor">[FORMA_ENTRADA]</span></td>
    <td><span class="rotulo">Data</span><span class="valor">[DATA_ENTRADA]</span></td>
  </tr><tr>
    <td><span class="rotulo">Modalidade</span><span class="valor">[MODALIDADE]</span></td>
    <td><span class="rotulo">Parcelas</span><span class="valor">[NUM_PARCELAS] / [TIPO]</span></td>
    <td><span class="rotulo">Valor do Contrato</span><span class="valor">[TOTAL_CONTRATO]</span></td>
  </tr></table>
  <table>{parc}</table>
</div>

<div class="quebra-capa"></div>
"""

def _montar_html_contrato(ctx):
    pag = ctx.get("_pag", {})
    mapping = _montar_mapping(ctx, pag)
    mapping["TEXTO_COMPLEMENTAR"] = ctx.get("adendo", "") or ""
    shell = open(os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.html"),
                 encoding="utf-8").read()
    capa = _html_capa(ctx)
    corpo = _html_corpo(_carregar_md())
    html = shell.replace("<!--CAPA-->", capa).replace("<!--CORPO-->", corpo)
    return _substituir_marcadores_html(html, mapping)

def _carregar_md():
    p = os.path.join(CONTRATO_TEMPLATE_DIR, "contrato.md")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""
```

Nota: `_montar_mapping` continua com assinatura `(ctx, pag)`. Se `[TEXTO_COMPLEMENTAR]` deve aparecer no corpo, incluir o marcador no `contrato.md` (Task 8).

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_contrato_pdf.py -k montar_html -q`
Expected: PASS. (o `contrato.md` pode estar vazio nesta etapa — o corpo fica vazio; o teste só checa capa/marcadores.)

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_pdf.py
git commit -m "feat(contrato): montagem da capa HTML + HTML final com marcadores"
```

---

### Task 8: Migração do texto jurídico → contrato.md

**Files:**
- Create: `scripts/extrair_clausulas_docx.py`
- Create: `contrato_template/contrato.md`

**Interfaces:**
- Produces: `contrato_template/contrato.md` com o texto **exato** das cláusulas (numeração literal), começando após a capa; inclui um marcador `[TEXTO_COMPLEMENTAR]` no ponto adequado (ex.: cláusula de "acordos complementares"), se o `.docx` tiver esse ponto — senão, adicionar uma seção curta ao final do corpo.

- [ ] **Step 1: Script de extração**

```python
# scripts/extrair_clausulas_docx.py
"""Extrai o corpo (após a última tabela da capa) do modelo .docx para Markdown,
preservando o texto literal e os números. Saída: contrato_template/contrato.md.
REVISAR o resultado — documento jurídico."""
from docx import Document
from docx.text.paragraph import Paragraph

d = Document("modelo_contrato_mapeado.docx")
body = d.element.body
blocks = list(body.iterchildren())
# começa após a última tabela (fim da capa)
ult_tbl = max(i for i, c in enumerate(blocks) if c.tag.endswith("}tbl"))
linhas = []
for c in blocks[ult_tbl + 1:]:
    if not c.tag.endswith("}p"):
        continue
    p = Paragraph(c, d)
    t = p.text.strip()
    if not t:
        linhas.append("")
        continue
    # títulos "CLÁUSULA ..." viram heading
    if t.upper().startswith("CLÁUSULA"):
        linhas.append(f"# {t}")
    else:
        linhas.append(t)
out = "\n".join(linhas).strip() + "\n"
open("contrato_template/contrato.md", "w", encoding="utf-8").write(out)
print("linhas:", len(linhas))
```

- [ ] **Step 2: Rodar a extração**

Run: `python3 scripts/extrair_clausulas_docx.py`
Expected: cria `contrato_template/contrato.md`; imprime a contagem de linhas (~150).

- [ ] **Step 3: REVISAR o contrato.md (gate manual/humano)**

Abrir `contrato_template/contrato.md` e conferir contra o `.docx`:
- todo o texto legal está presente e **idêntico** (sem cláusula perdida/cortada);
- os números literais estão corretos (`1.`, `1.1.`, `a)`…);
- inserir o marcador `[TEXTO_COMPLEMENTAR]` no ponto onde o acordo complementar deve aparecer (ex.: uma linha `Acordos complementares: [TEXTO_COMPLEMENTAR]` na cláusula pertinente).

Este passo **bloqueia** o avanço até a revisão estar OK.

- [ ] **Step 4: Teste de sanidade do corpo**

```python
def test_corpo_md_gera_clausulas():
    from mod_contrato import _html_corpo, _carregar_md
    html = _html_corpo(_carregar_md())
    assert "CLÁUSULA" in html.upper()
    assert 'class="cl-1"' in html            # há cláusulas de 1º nível
    assert "[TEXTO_COMPLEMENTAR]" in html    # marcador presente no corpo
```

Run: `python3 -m pytest tests/test_contrato_pdf.py -k corpo_md -q`
Expected: PASS (após a revisão do Step 3).

- [ ] **Step 5: Commit**

```bash
git add scripts/extrair_clausulas_docx.py contrato_template/contrato.md tests/test_contrato_pdf.py
git commit -m "feat(contrato): migra clausulas do docx para contrato.md (revisado)"
```

---

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

### Task 11: Remover código docx, rota /contrato/editar e testes antigos

**Files:**
- Modify: `mod_contrato.py`, `main.py`, `tests/test_contrato.py`

**Interfaces:** nenhuma nova (remoção).

- [ ] **Step 1: Remover funções docx de `mod_contrato.py`**

Apague: `preencher_contrato`, `_preencher_grade`, `_preencher_ambientes`, `_subst_paragrafo`, `_substituir_marcadores`, `_set_cell_text`, `_localizar_tabela`, `_unique_cells`, `_proteger_editaveis`, `_libreoffice_cmd`, `_converter_pdf`, `LibreOfficeIndisponivel`, `montar_variaveis_contrato`, `_formatar_bloco_pagamento`, e a constante `_MODELO`. Remova imports mortos (`from docx import Document`, `platform`, `subprocess`, `hashlib` se não usado — conferir; `hashlib` é usado por `calcular_hash_assinatura`, manter).

- [ ] **Step 2: Remover a rota `POST /contrato/editar`**

Em `main.py`, apague o handler `POST /api/projetos/<nome>/contrato/editar` (~L3353–3436) inteiro, e o botão/uso no frontend (`static/`) que chama `/contrato/editar` (grep por `contrato/editar`).

Run: `grep -rn "contrato/editar" main.py static/ 2>/dev/null`
Expected: sem resultados após a remoção.

- [ ] **Step 3: Remover testes específicos de docx**

Em `tests/test_contrato.py`, apague os testes que dependem do `.docx`/funções removidas: `test_preencher_grade_*`, `test_preencher_ambientes_*` (as versões docx), `test_subst_*`, `test_localizar_tabela_*`, `test_substituir_marcadores_*`, `test_template_*` (que abrem `_MODELO`), `test_protegido_*`, `test_geracao_completa_*`. **Mantenha** os testes de `ambientes_valor_contrato`, `_parse_pagamento`, `gerar_num_contrato`, `calcular_hash_assinatura`, `contrato_desatualizado`, `validar_*`.

- [ ] **Step 4: Rodar a suíte inteira**

Run: `python3 -m pytest -q`
Expected: PASS (verde). Corrigir qualquer import residual apontado pelos erros.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py main.py tests/test_contrato.py static/
git commit -m "refactor(contrato): remove caminho docx, rota /contrato/editar e testes antigos"
```

---

### Task 12: Verificação visual (PDF real)

**Files:** nenhuma (verificação).

- [ ] **Step 1: Gerar um PDF real de exemplo**

Use o snippet do teste do Step 1 da Task 9 (5 ambientes ímpar + 10 parcelas) para gerar `CONTRATOS/contrato_90002.pdf` num ambiente com weasyprint.

- [ ] **Step 2: Renderizar a página 1 (capa) para conferência**

Run (WSL com LibreOffice do Windows apenas para *visualizar*, ou qualquer visualizador de PDF): abrir o PDF e conferir:
- cabeçalho com logo + número/data, margens ~1cm;
- seções 1–5 com rótulos cinza + valores em negrito;
- ambientes 2/linha + traços na sobra + total;
- grade de parcelas só com linhas usadas + traços;
- cláusulas na página 2+, numeração alinhada (número na calha, texto quebrado alinhado), rodapé "Página X de Y".

- [ ] **Step 3: Conferir contrato mínimo e longo**

Gere também um contrato mínimo (1 ambiente, 1 parcela) e confira que a capa fica na página 1 e as cláusulas na 2. Confirme quebra de página e cabeçalho corrido nas páginas seguintes.

- [ ] **Step 4: Registrar no DEV_LOG**

Acrescente uma seção no `DEV_LOG.md` descrevendo a nova arquitetura (HTML/Markdown → PDF via WeasyPrint), o corte do docx e a pendência da proposta.

- [ ] **Step 5: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — contrato migrado para HTML/Markdown -> PDF (WeasyPrint)"
```

---

## Notas de execução

- **Ordem sugerida:** Task 11 pode ser feita logo após a Task 10 para deixar a suíte verde (os testes de docx quebram quando o código é removido; remova código e testes juntos).
- **Sem weasyprint no dev:** os testes de PDF (Tasks 9, 12) são pulados; toda a lógica de HTML (Tasks 2–8) é testada por asserções de string e roda em qualquer ambiente. A verificação visual usa um ambiente com a lib (servidor ou máquina com weasyprint).
- **Fidelidade da capa:** ajuste `contrato.css` iterando com PDFs reais (Task 12) — cores/paddings podem precisar de refino fino vs. o `.docx` atual.
