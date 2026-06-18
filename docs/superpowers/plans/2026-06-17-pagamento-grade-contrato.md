# Pagamento correto + grade + template por marcadores (F1) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Gerar o contrato a partir de um template único por marcadores
(`modelo_contrato_mapeado.docx`), com parcelas (valor + data, sem ordinal), traços nos
vazios, total, número/data no cabeçalho, e cartão no primeiro campo — corrigindo a
captura de pagamento que trocava colunas.

**Architecture:** Frontend expõe `window._planoPagamento` estruturado (só parcelas
reais). Backend: `_parse_pagamento` lê a estrutura correta; `preencher_contrato`
preenche a grade por posição e substitui todos os demais marcadores via
`_substituir_marcadores`. Template `modelo_contrato_mapeado.docx` promovido a oficial.

**Tech Stack:** Python 3, python-docx, http.server/SQLAlchemy/sqlite; JS vanilla;
pytest; Playwright (verificação).

**Spec:** `docs/superpowers/specs/2026-06-17-pagamento-grade-contrato-design.md`

---

## File Structure

- `mod_contrato.py` — parser de pagamento, motor de marcadores, grade, mapping, `_MODELO`.
- `static/index.html` — `window._planoPagamento` nos renders; `_capturarPagamento`.
- `tests/test_contrato.py` — fixtures reais + testes do motor/grade/mapping.
- `modelo_contrato_mapeado.docx` — template oficial (versionado).
- `modelo_contrato_final.docx` — removido.

---

### Task 1: Promover o template e apontar `_MODELO`

**Files:**
- Modify: `mod_contrato.py:21` (`_MODELO`)
- Move: `modelo_contrato_mapeado.docx` → template oficial; remove `modelo_contrato_final.docx`
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever teste do template (marcadores presentes)**

```python
def test_template_oficial_tem_marcadores():
    import os
    from docx import Document
    from mod_contrato import _MODELO
    assert os.path.basename(_MODELO) == "modelo_contrato_mapeado.docx"
    assert os.path.exists(_MODELO)
    d = Document(_MODELO)
    blob = "\n".join(p.text for p in d.paragraphs)
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    assert "[NOME_CLIENTE]" in blob
    assert "[TOTAL_CONTRATO]" in blob
    assert "[DATA_PARCELA_1]" in blob
    assert "[VALOR_PARCELA]" in blob
```

- [ ] **Step 2: Rodar o teste — deve falhar** (`_MODELO` ainda aponta para final).

Run: `python -m pytest tests/test_contrato.py::test_template_oficial_tem_marcadores -v`
Expected: FAIL (basename != mapeado).

- [ ] **Step 3: Apontar `_MODELO` para o mapeado**

Em `mod_contrato.py:21`:
```python
_MODELO = os.path.join(_THIS_DIR, "modelo_contrato_mapeado.docx")
```

- [ ] **Step 4: Rodar o teste — deve passar.**

Run: `python -m pytest tests/test_contrato.py::test_template_oficial_tem_marcadores -v`
Expected: PASS.

- [ ] **Step 5: Versionar o template novo, remover o antigo, conferir .gitignore**

```bash
git rm --cached --ignore-unmatch modelo_contrato_final.docx
git rm modelo_contrato_final.docx
git add -f modelo_contrato_mapeado.docx
git status --short -- "*.docx"
```
Confirmar que `modelo_contrato_mapeado.docx` aparece como staged (A) e que `.gitignore`
não o exclui (não há regra `*.docx` que case; se houver, adicionar exceção
`!modelo_contrato_mapeado.docx`).

- [ ] **Step 6: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): promove modelo_contrato_mapeado.docx a template oficial"
```

---

### Task 2: `_parse_pagamento` para a estrutura real

**Files:**
- Modify: `mod_contrato.py` (`_parse_pagamento`, ~L175-225)
- Test: `tests/test_contrato.py`

Estrutura nova de entrada (do `window._planoPagamento`):
`{ tipo, nome_forma, entrada_valor, entrada_data, entrada_forma, total_cliente,
texto_cartao, parcelas:[{num, data:'18/07/2026', valor:4820.0}] }`.

- [ ] **Step 1: Escrever os testes (estrutura real)**

```python
def test_parse_pagamento_estrutura_real():
    import json
    from mod_contrato import _parse_pagamento
    pag = json.dumps({
        "tipo": "aymore", "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 20000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
        "total_cliente": 129572.01, "texto_cartao": "",
        "parcelas": [
            {"num": 1, "data": "18/07/2026", "valor": 4820.00},
            {"num": 2, "data": "17/08/2026", "valor": 4820.00},
        ],
    })
    d = _parse_pagamento(pag)
    assert d["num_parcelas_int"] == 2
    assert d["valores"][0] == "R$ 4.820,00"
    assert d["valores"][1] == "R$ 4.820,00"
    assert d["valores"][2] == ""
    assert d["datas"][0] == "18/07/2026"
    assert d["datas"][2] == ""
    assert d["valor_contrato"] == "R$ 129.572,01"
    assert len(d["valores"]) == 24 and len(d["datas"]) == 24

def test_parse_pagamento_cartao_texto():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({
        "tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "texto_cartao": "12x R$ 10.000,00", "total_cliente": 120000, "parcelas": []}))
    assert d["texto_cartao"] == "12x R$ 10.000,00"
    assert d["num_parcelas_int"] == 0
    assert d["valores"] == [""] * 24
    assert d["valor_contrato"] == "R$ 120.000,00"
```

- [ ] **Step 2: Rodar — deve falhar** (`valor_contrato`/`texto_cartao` não existem; `valores` vinham de `p.get("valor")` cru).

Run: `python -m pytest tests/test_contrato.py -k parse_pagamento -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Substituir o bloco de datas/valores e o `return` de `_parse_pagamento`:
```python
    parcelas     = pag.get("parcelas") or []
    num_parcelas = len(parcelas)

    datas, valores = [], []
    for p in parcelas:
        datas.append(_formatar_data_br(p.get("data") or ""))
        valores.append(_formatar_valor_str(p.get("valor")))
    datas   = (datas   + [""] * 24)[:24]
    valores = (valores + [""] * 24)[:24]

    total_cliente = pag.get("total_cliente") or 0
    return {
        "tipo":             tipo,
        "nome_forma":       nome_forma,
        "entrada_valor":    _formatar_valor(entrada_val),
        "entrada_tipo":     entrada_tipo,
        "entrada_data":     entrada_data,
        "modalidade":       nome_forma,
        "num_parcelas":     str(num_parcelas) if num_parcelas else "—",
        "num_parcelas_int": num_parcelas,
        "data_primeira":    (datas[0] if datas and datas[0] else ""),
        "datas":            datas,
        "valores":          valores,
        "valor_contrato":   _formatar_valor(total_cliente),
        "texto_cartao":     pag.get("texto_cartao") or "",
    }
```

Adicionar utilitário próximo a `_formatar_valor`:
```python
def _formatar_valor_str(v):
    """Aceita número ou string já formatada; devolve 'R$ x.xxx,xx' (ou '' se vazio)."""
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):
        return _formatar_valor(v)
    s = str(v).strip()
    return s            # já vem formatado do front (ex.: 'R$ 4.820,00')
```

(`_formatar_valor` já produz `R$ x.xxx,xx` a partir de número — confirmar assinatura no
arquivo e reutilizar.)

- [ ] **Step 4: Rodar — deve passar.**

Run: `python -m pytest tests/test_contrato.py -k parse_pagamento -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "fix(contrato): _parse_pagamento lê parcelas reais (valor/data/total)"
```

---

### Task 3: Motor de marcadores `_substituir_marcadores`

**Files:**
- Modify: `mod_contrato.py` (nova função)
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever os testes**

```python
def test_substituir_marcadores_basico():
    from docx import Document
    from mod_contrato import _substituir_marcadores
    d = Document()
    d.add_paragraph("Cliente: [NOME_CLIENTE] CPF/CNPJ: [CPF]")
    d.add_paragraph("Desconhecido: [NAO_EXISTE]")
    _substituir_marcadores(d, {"NOME_CLIENTE": "Ana Lima", "CPF": "111.222.333-44"})
    txt = "\n".join(p.text for p in d.paragraphs)
    assert "Cliente: Ana Lima CPF/CNPJ: 111.222.333-44" in txt
    assert "[NAO_EXISTE]" in txt          # desconhecido permanece

def test_substituir_marcadores_case_e_duplo_colchete():
    from docx import Document
    from mod_contrato import _substituir_marcadores
    d = Document()
    d.add_paragraph("N: [Num_Contrato]  D: [[Data_contrato]")
    _substituir_marcadores(d, {"NUM_CONTRATO": "INS-2026-06-17-001", "DATA_CONTRATO": "17/06/2026"})
    txt = d.paragraphs[0].text
    assert "INS-2026-06-17-001" in txt and "17/06/2026" in txt
    assert "[" not in txt
```

- [ ] **Step 2: Rodar — deve falhar** (função inexistente).

Run: `python -m pytest tests/test_contrato.py -k substituir_marcadores -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implementar**

```python
import re as _re_mark
_MARK_RE = _re_mark.compile(r'\[+\s*([A-Za-z0-9_ ]+?)\s*\]')

def _aplica_mark(texto, mapping):
    def repl(m):
        chave = m.group(1).strip().upper().replace(" ", "_")
        return mapping[chave] if chave in mapping else m.group(0)
    return _MARK_RE.sub(repl, texto)

def _subst_paragrafo(par, mapping):
    if "[" not in par.text:
        return
    novo = _aplica_mark(par.text, mapping)
    if novo == par.text:
        return
    if par.runs:
        par.runs[0].text = novo
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.text = novo

def _substituir_marcadores(doc, mapping):
    """Substitui [MARCADOR] (case-insensitive, tolera '[[') no corpo, tabelas e headers.
    Chaves do mapping SEM colchetes, em MAIÚSCULAS. Marcador sem chave é mantido."""
    from docx.oxml.ns import qn
    for par in doc.paragraphs:
        _subst_paragrafo(par, mapping)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    _subst_paragrafo(par, mapping)
    for sec in doc.sections:
        for hdr in (sec.header, sec.first_page_header, sec.even_page_header):
            for t_el in hdr._element.iter(qn('w:t')):
                if t_el.text and "[" in t_el.text:
                    t_el.text = _aplica_mark(t_el.text, mapping)
```

Nota: a chave normaliza espaços para `_` (cobre eventuais `[Valor Entrada]`), mas o
inventário usa `_`.

- [ ] **Step 4: Rodar — deve passar.**

Run: `python -m pytest tests/test_contrato.py -k substituir_marcadores -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): motor de substituição de marcadores"
```

---

### Task 4: Grade por posição `_preencher_grade` + `_set_cell_text`

**Files:**
- Modify: `mod_contrato.py` (nova `_preencher_grade`, helper `_set_cell_text`)
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever o teste (grade isolada)**

```python
def test_preencher_grade_valores_datas_e_tracos():
    from docx import Document
    from mod_contrato import _MODELO, _preencher_grade, _TRACO
    d = Document(_MODELO)
    pag = {"tipo": "aymore", "num_parcelas_int": 2,
           "valores": ["R$ 4.820,00", "R$ 4.820,00"] + [""] * 22,
           "datas":   ["18/07/2026", "17/08/2026"] + [""] * 22,
           "texto_cartao": ""}
    _preencher_grade(d, pag)
    t3 = d.tables[3]
    blob = " ".join(c.text for row in t3.rows for c in row.cells)
    assert "R$ 4.820,00" in blob
    assert "18/07/2026" in blob and "17/08/2026" in blob
    assert _TRACO in blob                     # slots vazios viram traços
    assert "[VALOR_PARCELA]" not in blob       # marcadores da grade sumiram
    assert "[DATA_PARCELA_3]" not in blob
    assert len(t3.rows) == 11                  # linhas preservadas

def test_preencher_grade_cartao_primeiro_campo():
    from docx import Document
    from mod_contrato import _MODELO, _preencher_grade, _TRACO
    d = Document(_MODELO)
    _preencher_grade(d, {"tipo": "cartao", "num_parcelas_int": 0,
                         "valores": [""] * 24, "datas": [""] * 24,
                         "texto_cartao": "12x R$ 10.000,00"})
    t3 = d.tables[3]
    c0 = t3.rows[3].cells[0].text
    blob = " ".join(c.text for row in t3.rows for c in row.cells)
    assert "12x R$ 10.000,00" in c0
    assert _TRACO in blob
```

- [ ] **Step 2: Rodar — deve falhar** (função inexistente).

Run: `python -m pytest tests/test_contrato.py -k preencher_grade -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

```python
def _set_cell_text(cell, txt):
    """Escreve txt no 1º parágrafo da célula, preservando o estilo; zera runs extras."""
    par = cell.paragraphs[0]
    if par.runs:
        par.runs[0].text = txt
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.text = txt
    # zera demais parágrafos da célula (se houver)
    for extra in cell.paragraphs[1:]:
        for r in extra.runs:
            r.text = ""

def _preencher_grade(doc, pag):
    tipo    = pag.get("tipo", "")
    num     = pag.get("num_parcelas_int", 0)
    valores = pag.get("valores", [""] * 24)
    datas   = pag.get("datas",   [""] * 24)
    texto   = pag.get("texto_cartao", "")
    t3 = doc.tables[3]
    for gi, row_idx in enumerate(range(3, 11)):
        cells = t3.rows[row_idx].cells
        for j, (vcol, dcol) in enumerate([(0, 1), (2, 3), (4, 5)]):
            if dcol >= len(cells):
                break
            p = gi * 3 + j + 1
            if tipo == "cartao":
                _set_cell_text(cells[vcol], texto if p == 1 else _TRACO)
                _set_cell_text(cells[dcol], "" if p == 1 else _TRACO)
            elif p <= num and valores[p-1]:
                _set_cell_text(cells[vcol], valores[p-1])
                _set_cell_text(cells[dcol], datas[p-1] or _TRACO)
            else:
                _set_cell_text(cells[vcol], _TRACO)
                _set_cell_text(cells[dcol], _TRACO)
```

(`_TRACO = "--------"` já existe no módulo.)

- [ ] **Step 4: Rodar — deve passar.**

Run: `python -m pytest tests/test_contrato.py -k preencher_grade -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): grade de parcelas por posição (valor+data, traços, cartão)"
```

---

### Task 5: `_montar_mapping` + reescrita de `preencher_contrato` (remover código antigo)

**Files:**
- Modify: `mod_contrato.py` (`preencher_contrato`, novo `_montar_mapping`; remover
  `_unique_cells`-based fills, `_set_cell` com rótulo na capa, `_relabel_cpf_cnpj`,
  matching por conteúdo, remoção de linhas, `_preencher_cabecalho`)
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever o teste de geração completa**

```python
def test_geracao_completa_sem_marcadores_remanescentes():
    import os, json
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome": "Ana Cliente", "cpf": "111.222.333-44", "email": "a@x.com",
                 "telefone": "(12) 90000-0000", "logradouro": "Rua A", "numero": "10",
                 "complemento": "ap 1", "bairro": "Centro", "cidade": "SJC", "cep": "12000-000",
                 "estado": "SP", "inst_mesmo_residencial": True, "inst_logradouro": "",
                 "inst_numero": "", "inst_complemento": "", "inst_bairro": "", "inst_cidade": "",
                 "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor Z", "telefone": "(12) 91111-1111", "email": "z@x.com"},
        forma_pagamento_json=json.dumps({
            "tipo": "aymore", "nome_forma": "Financiamento Aymoré",
            "entrada_valor": 20000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
            "total_cliente": 129572.01, "texto_cartao": "",
            "parcelas": [{"num": i+1, "data": f"18/{7+i:02d}/2026", "valor": 4820.0} for i in range(3)]}))
    ctx["num_contrato"]  = "INS-2026-06-17-009"
    ctx["data_contrato"] = "17/06/2026"
    path = preencher_contrato(92001, ctx)
    doc = Document(path)
    # coletar TODO o texto (corpo + tabelas + header)
    blob = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    for sec in doc.sections:
        for h in (sec.header,):
            blob += "\n" + "\n".join(tt.text or "" for tt in h._element.iter(qn('w:t')))
    os.remove(path)
    import re
    sobra = re.findall(r'\[[A-Za-z0-9_ ]+\]', blob)
    assert sobra == [], f"marcadores não substituídos: {sobra}"
    assert "Ana Cliente" in blob
    assert "INS-2026-06-17-009" in blob and "17/06/2026" in blob
    assert "R$ 129.572,01" in blob            # TOTAL_CONTRATO
    assert "R$ 4.820,00" in blob              # parcela
    assert "Jaime Perinazzo" in blob and "Felipe Guizalberte" in blob
```

- [ ] **Step 2: Rodar — deve falhar** (mapping/rewrite ausentes; sobram marcadores).

Run: `python -m pytest tests/test_contrato.py::test_geracao_completa_sem_marcadores_remanescentes -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `_montar_mapping` e reescrever `preencher_contrato`**

```python
def _montar_mapping(ctx, pag):
    return {
        "NUM_CONTRATO":     str(ctx.get("num_contrato", "") or ""),
        "DATA_CONTRATO":    str(ctx.get("data_contrato", "") or ""),
        "NOME_CLIENTE":     ctx.get("cliente_nome", "") or "",
        "CPF":              ctx.get("cliente_cpf", "") or "",
        "EMAIL":            ctx.get("cliente_email", "") or "",
        "TELEFONE":         ctx.get("cliente_telefone", "") or "",
        "RES_LOGRADOURO":   ctx.get("res_logradouro", "") or "",
        "RES_NUMERO":       ctx.get("res_numero", "") or "",
        "RES_COMPLEMENTO":  ctx.get("res_complemento", "") or "",
        "RES_BAIRRO":       ctx.get("res_bairro", "") or "",
        "RES_CIDADE":       ctx.get("res_cidade", "") or "",
        "RES_CEP":          ctx.get("res_cep", "") or "",
        "RES_UF":           ctx.get("res_uf", "") or "",
        "INST_LOGRADOURO":  ctx.get("inst_logradouro", "") or "",
        "INST_NUMERO":      ctx.get("inst_numero", "") or "",
        "INST_COMPLEMENTO": ctx.get("inst_complemento", "") or "",
        "INST_BAIRRO":      ctx.get("inst_bairro", "") or "",
        "INST_CIDADE":      ctx.get("inst_cidade", "") or "",
        "INST_CEP":         ctx.get("inst_cep", "") or "",
        "INST_UF":          ctx.get("inst_uf", "") or "",
        "VALOR_ENTRADA":    pag.get("entrada_valor", "") or "",
        "FORMA_ENTRADA":    pag.get("entrada_tipo", "") or "",
        "DATA_ENTRADA":     pag.get("entrada_data", "") or "",
        "MODALIDADE":       pag.get("nome_forma", "") or "",
        "NUM_PARCELAS":     pag.get("num_parcelas", "") or "",
        "TOTAL_CONTRATO":   pag.get("valor_contrato", "") or "",
        "CONSULTOR_NOME":     ctx.get("consultor_nome", "") or "",
        "CONSULTOR_TELEFONE": ctx.get("consultor_tel", "") or "",   # chave real em construir_contexto
        "TESTEMUNHA_1_NOME": _TESTEMUNHAS[0][0],
        "TESTEMUNHA_1_DOC":  _TESTEMUNHAS[0][1],
        "TESTEMUNHA_2_NOME": _TESTEMUNHAS[1][0],
        "TESTEMUNHA_2_DOC":  _TESTEMUNHAS[1][1],
    }

def preencher_contrato(contrato_id, ctx):
    doc = Document(_MODELO)
    pag = ctx.get("_pag", {})
    _preencher_grade(doc, pag)
    _substituir_marcadores(doc, _montar_mapping(ctx, pag))
    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)
    return docx_path
```

Remover do módulo (agora obsoletos): a versão antiga de `preencher_contrato`
(matching por conteúdo, `_unique_cells` fills, remoção de linhas), e a chamada a
`_relabel_cpf_cnpj`/`_preencher_cabecalho` dentro dela. **Conferir** as chaves de `ctx`
(`cliente_nome`, `cliente_cpf`, `cliente_email`, `cliente_telefone`, `res_*`, `inst_*`,
`consultor_nome`, `consultor_telefone`, `data_contrato`) em `construir_contexto` — se os
nomes diferirem, ajustar o mapping para casar com o que `construir_contexto` produz
(ler a função antes de implementar). Garantir que `construir_contexto` inclua
`cliente_email`/`cliente_telefone`/`res_*`/`inst_*`/`consultor_telefone`; se algum não
existir, adicioná-lo lá.

- [ ] **Step 4: Rodar o teste e a suíte de contrato.**

Run: `python -m pytest tests/test_contrato.py -v`
Expected: PASS. (Ajustar/retirar testes antigos que dependiam do template hardcoded
— `test_preencher_signatario_e_testemunhas`, `test_contrato_cpf_vira_cpf_cnpj`,
`test_contrato_tags_nomenclatura`, e os testes de grade com ordinal do merge anterior:
reescrevê-los para a estrutura real/marcadores ou removê-los se redundantes com os
novos. Documentar no commit o que mudou e por quê.)

- [ ] **Step 5: Rodar a suíte completa.**

Run: `python -m pytest tests/ -q`
Expected: PASS (sem regressões).

- [ ] **Step 6: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): geração por marcadores; remove lógica posicional antiga"
```

---

### Task 6: Frontend — `window._planoPagamento` + `_capturarPagamento`

**Files:**
- Modify: `static/index.html` — renders `atualizarAymore` (~L3245), cartão `atualizarCartao`
  (~L3391), VP (~L3559), TF (~L3979); `_capturarPagamento` (L6954).

- [ ] **Step 1: Stash do plano em cada render**

Em cada função de render, após calcular `d` (que tem `d.parcelas`, `d.valor_parcela`,
`d.total_cliente`), montar e atribuir o global. Exemplo (Aymoré, após o `tbody.innerHTML`
e antes do `_atualizarImpostos`):
```js
window._planoPagamento = {
  tipo: 'aymore', nome_forma: 'Financiamento Aymoré',
  entrada_valor: entrada,
  entrada_data: document.getElementById('ay-data-contrato')?.value || '',
  entrada_forma: (document.getElementById('apr-forma-entrada')?.value) || '',
  total_cliente: d.total_cliente, texto_cartao: '',
  parcelas: d.parcelas
    .filter(p => p.tipo === 'primeira' || p.tipo === 'parcela')
    .map((p, i) => ({ num: i + 1, data: p.data, valor: d.valor_parcela })),
};
```
VP: análogo (`tipo:'vp'`, datas de `d.parcelas`, `valor: d.valor_parcela`).
TF: `valor` por parcela = `p.valor_digitado`/efetivo; `data` = `p.data`.
Cartão (`atualizarCartao`): `tipo:'cartao'`, `parcelas: []`,
`texto_cartao` = a string montada (ex.: `n+'x R$ '+fmt(valParcela)`),
`total_cliente` = total do cartão.
(À vista / sem painel: ao escolher essa forma, definir
`window._planoPagamento = {tipo:'avista', parcelas:[], total_cliente:<total>, texto_cartao:'', ...}`.)

> Observação: usar os mesmos campos de entrada que `_capturarPagamento` lê hoje
> (`apr-forma-entrada`, `apr-forma-parcelas`) — esses só existem no modal de aprovação,
> então manter o fallback no `_capturarPagamento` (Step 2) para preenchê-los na captura.

- [ ] **Step 2: `_capturarPagamento` retorna o global**

Reescrever `_capturarPagamento(formaEntrada, formaParcelas)` para:
```js
function _capturarPagamento(formaEntrada, formaParcelas) {
  const base = window._planoPagamento || { tipo: 'avista', nome_forma: 'À Vista / Boleto Loja',
    parcelas: [], total_cliente: 0, texto_cartao: '', entrada_valor: 0, entrada_data: '' };
  // injeta as formas escolhidas no modal de aprovação
  return {
    tipo: base.tipo, nome_forma: base.nome_forma,
    entrada_valor: base.entrada_valor || 0,
    entrada_data: base.entrada_data || '',
    entrada_forma: formaEntrada || base.entrada_forma || '',
    total_cliente: base.total_cliente || 0,
    texto_cartao: base.texto_cartao || '',
    parcelas: (base.parcelas || []).map(p => ({ num: p.num, data: p.data, valor: p.valor, forma: formaParcelas })),
  };
}
```
Remover a antiga raspagem de DOM (e o ramo de cartão que montava `texto` — agora vem do
render via `texto_cartao`; manter o cálculo do `texto_cartao` no `atualizarCartao`).

- [ ] **Step 3: Verificação manual rápida no navegador (sanity)**

Abrir o app, montar um plano Aymoré, e no console: `JSON.stringify(window._planoPagamento)`
— confirmar `parcelas` só com parcelas reais, `valor` numérico e `data` de vencimento.
(Verificação completa na Task 7.)

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "fix(front): _planoPagamento estruturado; _capturarPagamento sem raspagem de DOM"
```

---

### Task 7: Verificação runtime (servidor fresco + dados reais)

**REQUIRED SUB-SKILL:** `verify`. Sem fabricar JSON — dirigir o app de verdade.

- [ ] **Step 1: Matar listeners antigos e subir UM servidor fresco**

```powershell
Get-NetTCPConnection -LocalPort 8765 -State Listen -EA SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }
```
Subir `python main.py` em background; confirmar que está servindo o código novo.

- [ ] **Step 2: Dirigir o app (Playwright)** — login, montar plano Aymoré (entrada + N
  parcelas), aprovar orçamento, gerar contrato. Capturar o `pagamento_json` real gravado.

- [ ] **Step 3: Inspecionar o `.docx` gerado**
  - cabeçalho: `INS-AAAA-MM-DD-NNN` + data;
  - grade: cada parcela com valor + data; traços nos vazios; 11 linhas (preservadas);
  - `[TOTAL_CONTRATO]` com o total; cartão (teste à parte): 1º campo `Nx R$ ...`;
  - cliente e testemunhas em linha; **zero** marcadores `[...]` sobrando.

- [ ] **Step 4: Confirmar persistência** — `Contrato.num_contrato` gravado e **estável**
  ao regerar o contrato (mesmo número).

- [ ] **Step 5: Encerrar o servidor de teste.**

---

## Self-Review (checklist do autor do plano)

- Cobertura do spec: captura (T6), parser (T2), motor de marcadores (T3), grade (T4),
  mapping/geração (T5), template (T1), verificação (T7). ✓
- Sem placeholders: cada passo tem código/comandos concretos. ✓
- Consistência de tipos: `_planoPagamento.parcelas[].valor` numérico → `_formatar_valor_str`
  no backend; `valor_contrato`/`texto_cartao` fluem do parser ao mapping/grade. ✓
- Risco: nomes de chaves do `ctx` em `construir_contexto` podem divergir do mapping —
  Task 5 Step 3 exige ler `construir_contexto` e casar/criar as chaves antes de implementar.
- Risco: testes antigos (template hardcoded) quebram — Task 5 Step 4 trata explicitamente.
