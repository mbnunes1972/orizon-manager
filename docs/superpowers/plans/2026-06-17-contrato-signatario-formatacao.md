# Contrato: Signatário, Testemunhas, Formatação + Enforcement de Aprovação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir 2 bugs de aprovação e ajustar o documento do contrato (2º signatário = cliente com fluxo "é o cliente cadastrado?", testemunhas provisórias, "CPF"→"CPF/CNPJ", tags de nomenclatura).

**Architecture:** O endpoint `POST /contrato` ganha um gate de ambiente e aceita `signatario_override`. O `mod_contrato.preencher_contrato` passa a: preencher o 2º signatário com o cliente, preencher as duas testemunhas (hardcoded provisório), relabelar "CPF"→"CPF/CNPJ" e adicionar tags de nomenclatura (rótulo cinza ~7pt) acima dos campos. O frontend corrige o popup, pré-checa ambiente e adiciona o fluxo "é o cliente cadastrado?" com modal de override.

**Tech Stack:** Python 3 + python-docx; `http.server`; pytest; frontend HTML/CSS/JS vanilla. Documento verificado gerando o `.docx` e inspecionando (python-docx).

**Spec:** `docs/superpowers/specs/contrato-documentos/2026-06-17-contrato-signatario-formatacao-design.md`
**Branch:** `feat/contrato-signatario-formatacao` (já criada).

---

## File Structure

| Arquivo | Mudança |
|---|---|
| `mod_contrato.py` | `_set_cell`/`_set_para` com `rotulo`; signatário=cliente + testemunhas; `_relabel_cpf_cnpj`; tags por call-site |
| `main.py` | gate de ambiente em `POST /contrato`; usar `signatario_override` quando enviado |
| `static/index.html` | bug 2 (popup troca modal); bug 3 (pré-check ambiente); fluxo "é o cliente cadastrado?" + modal de override |
| `tests/test_contrato.py` | gate de ambiente (helper) + geração de doc (signatário/testemunhas/CPF-CNPJ/tags) |

---

## Task 1: Backend — gate de ambiente + `signatario_override`

**Files:** Modify `main.py` (handler `POST /api/projetos/<nome>/contrato`, ~linha 2147 onde chama `_montar_dados_projeto_para_contrato`).

- [ ] **Step 1: Add the ambiente gate**

Em `main.py`, logo após a linha que atribui `projeto_dict, cliente_dict, orcamento_dict = _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)`, inserir o gate ANTES dos `from mod_contrato import ...`:

```python
                    projeto_dict, cliente_dict, orcamento_dict = \
                        _montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db)
                    # Gate: orçamento precisa ter ao menos um ambiente (1º orçamento concluído).
                    if not orcamento_dict.get("ambientes"):
                        self.send_json({
                            "ok": False,
                            "erro": "O orçamento não tem ambientes. Conclua o primeiro orçamento "
                                    "(com ambientes) antes de aprovar.",
                        }, code=400)
                        return
```

- [ ] **Step 2: Use `signatario_override` when present**

Logo após o gate acima (e antes do bloco `faltando = validar_cliente_para_contrato(cliente_dict)`), inserir:

```python
                    # Signatário alternativo: substitui o cadastro só para este contrato.
                    _override = req.get("signatario_override")
                    if isinstance(_override, dict) and _override.get("nome"):
                        cliente_dict = {**cliente_dict, **{k: v for k, v in _override.items() if v not in (None, "")}}
```

(`req` já foi lido como `json.loads(body)` no início do handler. `cliente_dict` é usado logo abaixo por `validar_cliente_para_contrato(cliente_dict)` e por `construir_contexto(cliente_dict, ...)`, então o override flui naturalmente.)

- [ ] **Step 3: Verify**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('syntax ok')"` → syntax ok
Run: `python -c "import main; print('import ok')"` → import ok
Run: `python -X utf8 -m pytest tests/ -q` → all pass (69; gate/override são caminhos HTTP — verificados em runtime na fase final).

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(contrato): gate de ambiente + signatario_override no POST /contrato"
```

---

## Task 2: mod_contrato — 2º signatário = cliente + testemunhas

**Files:** Modify `mod_contrato.py` (constantes no topo; loop de assinatura em `preencher_contrato`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_contrato.py`:

```python
def test_preencher_signatario_e_testemunhas(tmp_path):
    import os
    from mod_contrato import preencher_contrato, _MODELO, construir_contexto
    if not os.path.exists(_MODELO):
        return  # sem modelo no ambiente
    from docx import Document
    ctx = construir_contexto(
        cliente={"nome": "Ana Cliente", "cpf": "111.222.333-44", "email": "a@x.com",
                 "telefone": "(12) 9", "logradouro": "Rua A", "numero": "1", "complemento": "",
                 "bairro": "Centro", "cidade": "SJC", "cep": "12000", "estado": "SP",
                 "inst_mesmo_residencial": True, "inst_logradouro": "", "inst_numero": "",
                 "inst_complemento": "", "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor Z", "telefone": "", "email": ""},
        forma_pagamento_json="",
    )
    path = preencher_contrato(91001, ctx)
    full = "\n".join(p.text for p in Document(path).paragraphs)
    os.remove(path)
    assert "Ana Cliente" in full              # 2º signatário = cliente
    assert "Consultor Z" not in full          # consultor NÃO é signatário
    assert "Jaime Perinazzo" in full          # testemunha 1
    assert "Felipe Guizalberte" in full       # testemunha 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_contrato.py::test_preencher_signatario_e_testemunhas -v`
Expected: FAIL (currently "Consultor Z" appears as signatário and witnesses aren't filled).

- [ ] **Step 3: Add witness constants**

Em `mod_contrato.py`, junto às constantes do topo (perto de `_TELEFONE_LOJA`/`_EMAIL_LOJA`), adicionar:

```python
# Testemunhas provisórias — TODO: vir do painel de configuração de loja.
_TESTEMUNHAS = [
    ("Jaime Perinazzo",     "xxx.xxx.xxx-xx"),
    ("Felipe Guizalberte",  "yyy.yyy.yyy-yy"),
]
```

- [ ] **Step 4: Rewrite the signature/witness loop**

Em `preencher_contrato`, substituir o loop de parágrafos (o bloco `for para in doc.paragraphs:` que trata data/Ferreira Machado/NOME:/Documento:) por:

```python
    data_hoje = ctx.get("data_contrato", datetime.now().strftime("%d/%m/%Y"))
    _w_idx = 0  # índice da testemunha atual
    for para in doc.paragraphs:
        t = para.text.strip()
        # Data do contrato
        if t.startswith("São José dos Campos") and ("de 20" in t or "de 2026" in t):
            _set_para(para, f"São José dos Campos - SP, {data_hoje}.")
        # 2º signatário = CLIENTE (a linha INSPIRIUM acima permanece intacta)
        elif "Ferreira Machado" in t or "787.834" in t:
            _set_para(para, f"{ctx.get('cliente_nome', '')} CPF/CNPJ: {ctx.get('cliente_cpf', '')}")
        # Testemunhas (dois pares NOME:/Documento:)
        elif t == "NOME:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"NOME: {_TESTEMUNHAS[_w_idx][0]}")
        elif t == "Documento:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"CPF/CNPJ: {_TESTEMUNHAS[_w_idx][1]}")
            _w_idx += 1
```

(Isto remove o `break` antigo — agora preenche os DOIS pares de testemunha. **Sem `rotulo` aqui** — as tags são adicionadas na Task 4, que altera os helpers e todos os call-sites, inclusive este loop. `_set_para`/`_set_cell` permanecem com a assinatura atual `(target, text)` até a Task 4.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -X utf8 -m pytest tests/test_contrato.py::test_preencher_signatario_e_testemunhas -v`
Expected: PASS
Run: `python -X utf8 -m pytest tests/ -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): 2o signatario = cliente; preenche as duas testemunhas (provisorio)"
```

---

## Task 3: mod_contrato — "CPF" → "CPF/CNPJ" no documento

**Files:** Modify `mod_contrato.py` (novo `_relabel_cpf_cnpj`; chamada no fim de `preencher_contrato`).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_contrato.py`:

```python
def test_contrato_cpf_vira_cpf_cnpj():
    import os, re
    from mod_contrato import preencher_contrato, _MODELO, construir_contexto
    if not os.path.exists(_MODELO):
        return
    from docx import Document
    ctx = construir_contexto(
        cliente={"nome": "X", "cpf": "1", "email": "", "telefone": "",
                 "logradouro": "", "numero": "", "complemento": "", "bairro": "",
                 "cidade": "", "cep": "", "estado": "", "inst_mesmo_residencial": True,
                 "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
                 "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Y", "telefone": "", "email": ""}, forma_pagamento_json="")
    path = preencher_contrato(91002, ctx)
    doc = Document(path)
    texts = [p.text for p in doc.paragraphs]
    for tb in doc.tables:
        for row in tb.rows:
            for c in row.cells:
                texts.append(c.text)
    os.remove(path)
    blob = " ".join(texts)
    # nenhum "CPF" isolado (sempre "CPF/CNPJ"); e não há duplicação "CPF/CNPJ/CNPJ"
    assert re.search(r'CPF(?!/CNPJ)', blob) is None
    assert "CPF/CNPJ/CNPJ" not in blob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_contrato.py::test_contrato_cpf_vira_cpf_cnpj -v`
Expected: FAIL (o modelo tem "CPF" isolado na capa).

- [ ] **Step 3: Implement `_relabel_cpf_cnpj` and call it**

Em `mod_contrato.py`, adicionar (perto dos helpers, após `_set_para`):

```python
import re as _re_cpf

def _relabel_cpf_cnpj(doc):
    """Substitui 'CPF' por 'CPF/CNPJ' em parágrafos e células, sem duplicar."""
    def fix(para):
        for run in para.runs:
            if "CPF" in run.text:
                run.text = _re_cpf.sub(r'CPF(?!/CNPJ)', 'CPF/CNPJ', run.text)
    for para in doc.paragraphs:
        fix(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    fix(para)
```

Em `preencher_contrato`, imediatamente ANTES de `doc.save(docx_path)`, chamar:

```python
    _relabel_cpf_cnpj(doc)
    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -X utf8 -m pytest tests/test_contrato.py::test_contrato_cpf_vira_cpf_cnpj -v`
Expected: PASS
Run: `python -X utf8 -m pytest tests/ -q` → all pass.

> Nota: a substituição é por-run. Se "CPF" estiver dividido em runs diferentes no modelo, não casa — verificado no teste; se falhar, o run-merge fica como ajuste. No modelo atual os rótulos "CPF" são single-run.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): CPF -> CPF/CNPJ em todo o documento"
```

---

## Task 4: mod_contrato — tags de nomenclatura (rótulo cinza pequeno acima)

**Files:** Modify `mod_contrato.py` (`_set_cell`/`_set_para` usam `rotulo`; passar rótulos nos call-sites das tabelas).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_contrato.py`:

```python
def test_contrato_tags_nomenclatura():
    import os
    from mod_contrato import preencher_contrato, _MODELO, construir_contexto
    if not os.path.exists(_MODELO):
        return
    from docx import Document
    from docx.shared import Pt
    ctx = construir_contexto(
        cliente={"nome": "Ana", "cpf": "1", "email": "a@x.com", "telefone": "(12)9",
                 "logradouro": "Rua A", "numero": "10", "complemento": "", "bairro": "Centro",
                 "cidade": "SJC", "cep": "12000", "estado": "SP", "inst_mesmo_residencial": True,
                 "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
                 "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Y", "telefone": "", "email": ""}, forma_pagamento_json="")
    path = preencher_contrato(91003, ctx)
    doc = Document(path)
    # Tabela 0 (cliente): a célula do nome deve conter o rótulo "Nome" em runs pequenos.
    cell = doc.tables[0].rows[1].cells[0]
    runs = cell.paragraphs[0].runs
    os.remove(path)
    rotulos = [r.text for r in runs if r.font.size == Pt(7)]
    assert "Nome" in rotulos
    assert "Ana" in cell.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -X utf8 -m pytest tests/test_contrato.py::test_contrato_tags_nomenclatura -v`
Expected: FAIL (sem rótulo de 7pt).

- [ ] **Step 3: Implement the `rotulo` param in `_set_cell`/`_set_para`**

Em `mod_contrato.py`, adicionar o import de estilo no topo (junto a `from docx import Document`):

```python
from docx.shared import Pt, RGBColor
```

Substituir `_set_cell` por:

```python
def _set_cell(cell, text: str, rotulo: str = None):
    """Substitui o conteúdo de uma célula. Se `rotulo`, adiciona uma tag cinza pequena acima."""
    para = cell.paragraphs[0]
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name; font_size = r0.font.size; bold = r0.bold
    for run in para.runs:
        run.text = ""
    if rotulo:
        rl = para.add_run(rotulo)
        rl.font.size = Pt(7)
        rl.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        rl.add_break()
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold
```

Substituir `_set_para` por (mesmo padrão):

```python
def _set_para(para, text: str, rotulo: str = None):
    """Substitui o conteúdo de um parágrafo. Se `rotulo`, adiciona uma tag cinza pequena acima."""
    font_name = font_size = bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name; font_size = r0.font.size; bold = r0.bold
    for run in para.runs:
        run.text = ""
    if rotulo:
        rl = para.add_run(rotulo)
        rl.font.size = Pt(7)
        rl.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
        rl.add_break()
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold
```

- [ ] **Step 4: Pass `rotulo` at the table call-sites**

Em `preencher_contrato`, adicionar o `rotulo` em cada `_set_cell` das tabelas da capa. Atualizar exatamente estes call-sites:

```python
    # Tabela 0: Identificação do cliente
    _set_cell(tables[0].rows[1].cells[0], ctx.get("cliente_nome", ""),     rotulo="Nome")
    _set_cell(tables[0].rows[1].cells[1], ctx.get("cliente_cpf",  ""),     rotulo="CPF/CNPJ")
    _set_cell(tables[0].rows[2].cells[0], ctx.get("cliente_email", ""),    rotulo="E-mail")
    _set_cell(tables[0].rows[2].cells[1], ctx.get("cliente_telefone", ""), rotulo="Telefone")

    # Tabela 1: Endereço residencial
    _set_cell(_unique_cells(tables[1].rows[1])[0], ctx.get("res_logradouro", ""), rotulo="Logradouro")
    t1r2 = _unique_cells(tables[1].rows[2])
    if len(t1r2) >= 3:
        _set_cell(t1r2[0], ctx.get("res_numero",      ""), rotulo="Número")
        _set_cell(t1r2[1], ctx.get("res_complemento", ""), rotulo="Complemento")
        _set_cell(t1r2[2], ctx.get("res_bairro",      ""), rotulo="Bairro")
    t1r3 = _unique_cells(tables[1].rows[3])
    if len(t1r3) >= 3:
        _set_cell(t1r3[0], ctx.get("res_cidade", ""), rotulo="Cidade")
        _set_cell(t1r3[1], ctx.get("res_cep",    ""), rotulo="CEP")
        _set_cell(t1r3[2], ctx.get("res_uf",     ""), rotulo="Estado/UF")

    # Tabela 2: Endereço de instalação
    _set_cell(_unique_cells(tables[2].rows[1])[0], ctx.get("inst_logradouro", ""), rotulo="Logradouro")
    t2r2 = _unique_cells(tables[2].rows[2])
    if len(t2r2) >= 3:
        _set_cell(t2r2[0], ctx.get("inst_numero",      ""), rotulo="Número")
        _set_cell(t2r2[1], ctx.get("inst_complemento", ""), rotulo="Complemento")
        _set_cell(t2r2[2], ctx.get("inst_bairro",      ""), rotulo="Bairro")
    t2r3 = _unique_cells(tables[2].rows[3])
    if len(t2r3) >= 3:
        _set_cell(t2r3[0], ctx.get("inst_cidade", ""), rotulo="Cidade")
        _set_cell(t2r3[1], ctx.get("inst_cep",    ""), rotulo="CEP")
        _set_cell(t2r3[2], ctx.get("inst_uf",     ""), rotulo="Estado/UF")
```

E na Tabela 3 (forma de pagamento), nos `_set_cell` de `r1u`/`r2u`:

```python
    if len(r1u) >= 3:
        _set_cell(r1u[0], pag.get("entrada_valor", ""), rotulo="Entrada")
        _set_cell(r1u[1], pag.get("entrada_tipo",  ""), rotulo="Tipo")
        _set_cell(r1u[2], pag.get("entrada_data",  ""), rotulo="Data")
    if len(r2u) >= 3:
        _set_cell(r2u[0], pag.get("modalidade",    ""), rotulo="Modalidade")
        _set_cell(r2u[1], pag.get("num_parcelas",  ""), rotulo="Parcelas")
        _set_cell(r2u[2], pag.get("data_primeira", ""), rotulo="1ª data")
```

(A grade de datas das parcelas — os `_set_cell(row_cells[col], datas[p_idx])` no loop — **não** recebe rótulo, pois já tem o label "Nx" da própria grade.)

E no **loop de assinatura/testemunhas** (o que a Task 2 reescreveu), adicionar `rotulo` nos `_set_para`:

```python
        if t.startswith("São José dos Campos") and ("de 20" in t or "de 2026" in t):
            _set_para(para, f"São José dos Campos - SP, {data_hoje}.", rotulo="Data")
        elif "Ferreira Machado" in t or "787.834" in t:
            _set_para(para, f"{ctx.get('cliente_nome', '')} CPF/CNPJ: {ctx.get('cliente_cpf', '')}",
                      rotulo="Cliente (signatário)")
        elif t == "NOME:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"NOME: {_TESTEMUNHAS[_w_idx][0]}", rotulo="Testemunha")
        elif t == "Documento:" and _w_idx < len(_TESTEMUNHAS):
            _set_para(para, f"CPF/CNPJ: {_TESTEMUNHAS[_w_idx][1]}", rotulo="CPF/CNPJ")
            _w_idx += 1
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -X utf8 -m pytest tests/test_contrato.py -v`
Expected: PASS (incluindo `test_contrato_tags_nomenclatura` e os testes das tasks 2/3).
Run: `python -X utf8 -m pytest tests/ -q` → all pass.

- [ ] **Step 6: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): tags de nomenclatura (rotulo cinza pequeno) nos campos editaveis"
```

---

## Task 5: Frontend — bug 2 (popup troca modal) + bug 3 (pré-check ambiente)

**Files:** Modify `static/index.html` — `gerarContrato` (callback do popup) e `abrirAprovacaoComDados` (pré-check).

- [ ] **Step 1: Bug 2 — popup fecha o modal de aprovação**

Em `gerarContrato()`, no ramo `campos_faltando`, encontrar:

```javascript
          'Abrir Cadastro',
          () => { if (cliId) cliAbrirModal(cliId); }
```

Substituir o callback por:

```javascript
          'Abrir Cadastro',
          () => {
            document.getElementById('erro-modal-overlay')?.remove();
            document.getElementById('modal-aprovacao-overlay')?.remove();
            if (cliId) cliAbrirModal(cliId);
          }
```

- [ ] **Step 2: Bug 3 — pré-check de ambiente na aprovação**

Em `abrirAprovacaoComDados()`, logo após o check inicial `if (!_orcamentoAtivoId) { ... return; }`, inserir:

```javascript
  if (!_orcAmbientesAtivos || _orcAmbientesAtivos.length === 0) {
    mostrarErroModal('Adicione ao menos um ambiente (XML) e salve o orçamento antes de aprovar.');
    return;
  }
```

(`_orcAmbientesAtivos` é a mesma variável usada por `salvarOrcamento` para saber se há ambientes. Confirme o nome lendo `salvarOrcamento`; se for outro, use o mesmo critério dela.)

- [ ] **Step 3: Verify (static integrity)**

- Confirme um par `<script>`/`</script>` e paridade de crases.
- Run: `python -X utf8 -m pytest tests/ -q` → all pass (Python inalterado).

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "fix(aprovacao): popup Cadastro Incompleto troca de modal; bloqueia aprovacao sem ambiente"
```

---

## Task 6: Frontend — fluxo "é o cliente cadastrado?" + modal de override

**Files:** Modify `static/index.html` — `gerarContrato` (pergunta + envio de `signatario_override`); novo modal de signatário.

- [ ] **Step 1: Perguntar e (se necessário) coletar override antes de gerar**

Em `gerarContrato()`, ANTES do `fetch` que faz `POST .../contrato`, inserir a pergunta e a coleta. Localize o ponto onde o corpo do POST é montado (`body: JSON.stringify({ orcamento_id: ..., pagamento_json: ... })`) e, logo antes do `try { const r = await fetch(...)`, adicione:

```javascript
  // É o próprio cliente cadastrado que vai assinar?
  let signatarioOverride = null;
  const ehCliente = confirm('O signatário do contrato é o próprio cliente cadastrado?');
  if (!ehCliente) {
    signatarioOverride = await coletarSignatarioOverride();
    if (!signatarioOverride) {  // cancelou
      if (btn) { btn.disabled = false; btn.textContent = 'Gerar Contrato'; }
      return;
    }
  }
```

E no corpo do `POST`, adicionar o campo:

```javascript
      body: JSON.stringify({
        orcamento_id:       _orcamentoAtivoId,
        entrada_valor:      entrada,
        parcelas_descricao: parcelas,
        adendo:             adendo,
        forma_entrada:      formaEntrada,
        forma_parcelas:     formaParcelas,
        pagamento_json:     JSON.stringify(pagamento),
        signatario_override: signatarioOverride,
      }),
```

- [ ] **Step 2: Implement `coletarSignatarioOverride()` (modal com todos os dados do contrato)**

Adicionar perto de `gerarContrato`:

```javascript
async function coletarSignatarioOverride() {
  // Pré-preenche com o cadastro do cliente do projeto, se houver.
  let base = {};
  try {
    const c = await _carregarClienteProjeto();
    if (c) base = c;
  } catch(e) {}
  return new Promise((resolve) => {
    const campos = [
      ['nome','Nome'], ['cpf','CPF/CNPJ'], ['email','E-mail'], ['telefone','Telefone'],
      ['logradouro','Logradouro'], ['numero','Número'], ['complemento','Complemento'],
      ['bairro','Bairro'], ['cidade','Cidade'], ['cep','CEP'], ['estado','Estado/UF'],
    ];
    const ov = document.createElement('div');
    ov.id = 'modal-signatario-overlay';
    ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:10000;display:flex;align-items:flex-start;justify-content:center;overflow-y:auto;padding:24px 0';
    ov.innerHTML = `
      <div style="background:var(--card,#132013);border:1px solid #b8960c;border-radius:10px;padding:22px 26px;min-width:340px;max-width:520px;width:92%;margin:auto">
        <h3 style="margin:0 0 12px;color:#f0c84a;font-size:1rem">Dados do signatário (contrato)</h3>
        ${campos.map(([k,lbl]) => `
          <label style="display:block;font-size:.75rem;color:var(--muted);margin:6px 0 2px">${lbl}</label>
          <input id="sig-${k}" value="${(base[k]||'').toString().replace(/"/g,'&quot;')}"
            style="width:100%;background:var(--input,#0d1a0d);border:1px solid var(--border);color:var(--fg);padding:7px;border-radius:4px;font-size:.88rem">
        `).join('')}
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px">
          <button id="sig-cancel" style="background:none;border:1px solid var(--border);color:var(--muted);padding:7px 16px;border-radius:5px;cursor:pointer">Cancelar</button>
          <button id="sig-ok" style="background:#b8960c;color:#1a1200;border:none;font-weight:600;padding:7px 18px;border-radius:5px;cursor:pointer">Usar estes dados</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector('#sig-cancel').onclick = () => { ov.remove(); resolve(null); };
    ov.querySelector('#sig-ok').onclick = () => {
      const out = { inst_mesmo_residencial: true };
      campos.forEach(([k]) => { out[k] = document.getElementById('sig-'+k).value.trim(); });
      ov.remove(); resolve(out);
    };
  });
}
```

(Backend: `signatario_override` substitui os campos do `cliente_dict` correspondentes — chaves iguais às de `_cliente_dict`. `inst_mesmo_residencial: true` faz a instalação seguir o residencial do override.)

- [ ] **Step 3: Verify (static integrity)**

- Confirme um par `<script>`/`</script>`; paridade de crases.
- `coletarSignatarioOverride` definida e chamada em `gerarContrato`.
- Run: `python -X utf8 -m pytest tests/ -q` → all pass.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(contrato): fluxo 'e o cliente cadastrado?' + modal de signatario (override)"
```

---

## Final verification (fase /verify ao fim)

- [ ] **Suite:** `python -X utf8 -m pytest tests/ -q` → all pass (inclui os testes de doc).
- [ ] **Documento (inspeção real):** gerar um contrato e abrir o `.docx`: par. 128 = nome+CPF/CNPJ do cliente; testemunhas Jaime/Felipe; nenhum "CPF" isolado; tags cinza nos campos.
- [ ] **Runtime/API:** servidor fresco (matar instâncias antigas!); `POST /contrato` sem ambientes → 400; com `signatario_override` → contrato usa os dados do override.
- [ ] **GUI (Playwright/manual):** popup "Cadastro Incompleto" fecha o modal de aprovação e abre o cadastro; aprovação sem ambiente bloqueada; "Gerar Contrato" pergunta "é o cliente cadastrado?" e, no "não", abre o modal de signatário.

---

## Notas de escopo
- Testemunhas reais (painel de loja) — futuro; por ora hardcoded.
- Ajuste visual fino das tags pode precisar de iteração após ver o `.docx`.
