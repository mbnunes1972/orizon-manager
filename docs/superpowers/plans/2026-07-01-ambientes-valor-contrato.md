# Lista de ambientes com valor no contrato — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar à capa do contrato uma seção "4. Ambientes" (a "Forma de Pagamento" passa a "5") com uma linha por ambiente do orçamento, valor com financiamento, e uma linha de Total que bate com o `TOTAL_CONTRATO`.

**Architecture:** Um cálculo puro (`ambientes_valor_contrato`) distribui o `Val_Cont` pelos ambientes proporcional ao VAVA, com reconciliação de centavos. Na geração do `.docx`, um helper (`_preencher_ambientes`) constrói a tabela em código e a insere **antes** da tabela de Forma de Pagamento; o preenchimento da grade de parcelas passa a localizar a tabela **por conteúdo** (não por índice fixo), imune ao deslocamento. As rotas de geração de contrato injetam a lista de ambientes calculada no `ctx`.

**Tech Stack:** Python 3 (`python3`), `python-docx`, `pytest`. Servidor `main.py` (BaseHTTPRequestHandler). Sem dependências novas.

## Global Constraints

- Interpretador: **`python3`** (não `python`) no WSL.
- Motor de negociação (`mod_negociacao.py`) **não é alterado**.
- Fórmula do valor por ambiente (verbatim do spec): `Val_Cont_Amb = VAVA × (Val_Cont / VAVO)`; rateio proporcional ao VAVA; resíduo de arredondamento no **último** ambiente; `Σ = round(Val_Cont, 2)`.
- Nome do ambiente = `PoolAmbiente.nome_exibicao`. Ambas as colunas **justificadas à esquerda**.
- Escopo: **somente o contrato**. Proposta é frente seguinte (não tocar `modelo_proposta.docx` nem `mod_proposta.py`).
- Contrato protegido: as células de **valor** dos ambientes entram no `coletor` de regiões editáveis; a linha **Total** não.
- Testes de contrato isolam `CONTRATOS_DIR` via fixture autouse já existente em `tests/test_contrato.py` — colocar os testes novos nesse arquivo para reusá-la.

---

## File Structure

- `mod_contrato.py` — cálculo puro + helpers de docx + fiação em `preencher_contrato`.
- `main.py` — helper que monta a lista de ambientes a partir do breakdown + injeção nas 2 rotas de geração.
- `tests/test_contrato.py` — todos os testes novos (reusa a fixture de isolamento).

---

## Task 1: Cálculo puro `ambientes_valor_contrato`

**Files:**
- Modify: `mod_contrato.py` (adicionar função perto de `_formatar_valor`, ~linha 53)
- Test: `tests/test_contrato.py`

**Interfaces:**
- Produces: `ambientes_valor_contrato(itens, vavo, val_cont) -> list[tuple[str, float]]`
  - `itens`: `list[tuple[str, float]]` — `(nome, VAVA)` por ambiente, na ordem do orçamento.
  - `vavo`: `float` — soma dos VAVA (`d["VAVO"]`).
  - `val_cont`: `float` — valor de contrato do orçamento (`d["Val_Cont"]`).
  - Retorna `[(nome, valor_float), ...]` com `Σ valor == round(val_cont, 2)`.

- [ ] **Step 1: Write the failing tests**

Adicionar ao final de `tests/test_contrato.py`:

```python
# ── Valor por ambiente no contrato (rateio do financeiro) ──────────────────────

def test_ambientes_valor_proporcional_ao_vava():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("Cozinha", 100.0), ("Sala", 300.0)],
                                   vavo=400.0, val_cont=440.0)
    assert out == [("Cozinha", 110.0), ("Sala", 330.0)]
    assert round(sum(v for _, v in out), 2) == 440.0


def test_ambientes_reconciliacao_residuo_no_ultimo():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato(
        [("A", 33.33), ("B", 33.33), ("C", 33.34)], vavo=100.0, val_cont=100.01)
    assert round(sum(v for _, v in out), 2) == 100.01
    # o resíduo de arredondamento cai no último ambiente
    assert out[-1][0] == "C"
    assert out[0][1] == 33.33 and out[1][1] == 33.33


def test_ambientes_sem_financeiro_valor_igual_vava():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("A", 100.0), ("B", 300.0)],
                                   vavo=400.0, val_cont=400.0)
    assert out == [("A", 100.0), ("B", 300.0)]


def test_ambientes_vavo_zero_nao_divide():
    from mod_contrato import ambientes_valor_contrato
    out = ambientes_valor_contrato([("A", 0.0), ("B", 0.0)], vavo=0.0, val_cont=0.0)
    assert out == [("A", 0.0), ("B", 0.0)]


def test_ambientes_lista_vazia():
    from mod_contrato import ambientes_valor_contrato
    assert ambientes_valor_contrato([], vavo=0.0, val_cont=0.0) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_contrato.py -k "ambientes_valor or ambientes_reconcil or ambientes_sem or ambientes_vavo or ambientes_lista" -v`
Expected: FAIL com `ImportError: cannot import name 'ambientes_valor_contrato'`.

- [ ] **Step 3: Write minimal implementation**

Em `mod_contrato.py`, logo após `_formatar_valor_str` (~linha 62):

```python
def ambientes_valor_contrato(itens, vavo, val_cont):
    """Distribui Val_Cont pelos ambientes, proporcional ao VAVA.

    itens: lista [(nome, VAVA_float), ...] na ordem do orçamento.
    Retorna [(nome, valor_float), ...] com Σ valor == round(val_cont, 2);
    o resíduo de arredondamento é absorvido pelo último ambiente.
    vavo<=0 → devolve os próprios VAVA arredondados (sem divisão por zero).
    """
    if not itens:
        return []
    alvo = round(float(val_cont or 0.0), 2)
    if not vavo or vavo <= 0:
        return [(n, round(float(v or 0.0), 2)) for n, v in itens]
    fator = alvo / vavo
    out = [(n, round(float(v or 0.0) * fator, 2)) for n, v in itens]
    resid = round(alvo - sum(v for _, v in out), 2)
    if resid:
        n_ult, v_ult = out[-1]
        out[-1] = (n_ult, round(v_ult + resid, 2))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_contrato.py -k "ambientes_valor or ambientes_reconcil or ambientes_sem or ambientes_vavo or ambientes_lista" -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): calculo do valor por ambiente com financeiro (rateio VAVA)"
```

---

## Task 2: Localizar a grade de parcelas por conteúdo (refactor defensivo)

Antes de inserir a nova tabela, tornar `_preencher_grade` imune ao deslocamento de índice: parar de usar `doc.tables[3]` fixo e localizar por cabeçalho.

**Files:**
- Modify: `mod_contrato.py` — adicionar `_localizar_tabela`; alterar `_preencher_grade` (~linha 222, `t3 = doc.tables[3]`)
- Test: `tests/test_contrato.py`

**Interfaces:**
- Produces: `_localizar_tabela(doc, titulo_substr) -> docx.table.Table | None` — 1ª tabela cujo texto da 1ª linha contém `titulo_substr` (case-insensitive).

- [ ] **Step 1: Write the failing test**

Adicionar ao final de `tests/test_contrato.py`:

```python
def test_localizar_tabela_forma_pagamento():
    from docx import Document
    from mod_contrato import _localizar_tabela, _MODELO
    doc = Document(_MODELO)
    t = _localizar_tabela(doc, "forma de pagamento")
    assert t is not None
    cab = " ".join(c.text for c in t.rows[0].cells).lower()
    assert "forma de pagamento" in cab
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_contrato.py::test_localizar_tabela_forma_pagamento -v`
Expected: FAIL com `ImportError: cannot import name '_localizar_tabela'`.

- [ ] **Step 3: Add the helper and use it in `_preencher_grade`**

Em `mod_contrato.py`, adicionar antes de `_preencher_grade` (~linha 202):

```python
def _localizar_tabela(doc, titulo_substr):
    """1ª tabela cujo texto da 1ª linha contém titulo_substr (case-insensitive)."""
    alvo = titulo_substr.lower()
    for t in doc.tables:
        cab = " ".join(c.text for c in t.rows[0].cells).lower()
        if alvo in cab:
            return t
    return None
```

Dentro de `_preencher_grade`, trocar a linha `t3 = doc.tables[3]` por:

```python
    t3 = _localizar_tabela(doc, "forma de pagamento")
    if t3 is None:
        return
```

- [ ] **Step 4: Run tests to verify grade still fills (no regression)**

Run: `python3 -m pytest tests/test_contrato.py -v`
Expected: todos passam — em especial `test_geracao_completa_sem_marcadores_remanescentes` (que valida a grade: `R$ 4.820,00`) e `test_localizar_tabela_forma_pagamento`.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "refactor(contrato): localiza grade de parcelas por conteudo, nao por indice"
```

---

## Task 3: Seção "4. Ambientes" no docx + fiação em `preencher_contrato`

**Files:**
- Modify: `mod_contrato.py` — import `WD_ALIGN_PARAGRAPH`; adicionar `_preencher_ambientes`; alterar `preencher_contrato` (~linha 546)
- Test: `tests/test_contrato.py`

**Interfaces:**
- Consumes (de Task 1): `_formatar_valor`, `_set_cell_text`, `_unique_cells`, `_localizar_tabela`.
- Produces: `_preencher_ambientes(doc, itens_valores, coletor=None) -> None`
  - `itens_valores`: `list[tuple[str, float]]` já calculada por `ambientes_valor_contrato` (Task 1).
  - Insere a seção "4. Ambientes" antes da tabela de Forma de Pagamento, adiciona linha "Total", renumera "Forma de Pagamento" para "5.". Lista vazia → no-op.
  - `preencher_contrato` passa a ler `ctx.get("_ambientes")` e chamar `_preencher_ambientes`.

- [ ] **Step 1: Write the failing test**

Adicionar ao final de `tests/test_contrato.py`:

```python
def test_contrato_com_secao_ambientes():
    import os, json
    from docx import Document
    from mod_contrato import preencher_contrato, construir_contexto
    loja = {"nome": "INSPIRIUM MOVEIS LTDA", "cnpj": "19.152.134/0001-56",
            "testemunha1_nome": "Jaime", "testemunha1_cpf": "123.456.789-00",
            "testemunha2_nome": "Felipe", "testemunha2_cpf": "987.654.321-00"}
    ctx = construir_contexto(
        cliente={"nome": "Ana", "cpf": "111.222.333-44", "email": "a@x.com",
                 "telefone": "(12) 90000-0000", "logradouro": "Rua A", "numero": "10",
                 "complemento": "", "bairro": "Centro", "cidade": "SJC", "cep": "12000-000",
                 "estado": "SP", "inst_mesmo_residencial": True, "inst_logradouro": "",
                 "inst_numero": "", "inst_complemento": "", "inst_bairro": "", "inst_cidade": "",
                 "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Consultor Z", "telefone": "(12) 91111-1111", "email": "z@x.com"},
        forma_pagamento_json=json.dumps({
            "tipo": "aymore", "nome_forma": "Financiamento Aymoré",
            "entrada_valor": 20000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
            "total_cliente": 26445.67, "texto_cartao": "",
            "parcelas": [{"num": i+1, "data": f"18/{7+i:02d}/2026", "valor": 4820.0} for i in range(3)]}),
        loja=loja)
    ctx["num_contrato"]  = "INS-2026-07-01-001"
    ctx["data_contrato"] = "01/07/2026"
    ctx["_ambientes"] = [("Cozinha", 12345.67), ("Dormitório", 8900.0), ("Home Theater", 5200.0)]
    path = preencher_contrato(93001, ctx)
    doc = Document(path)
    # coleta texto de todas as tabelas
    tbl_blob = ""
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                tbl_blob += "\n" + c.text
    os.remove(path)
    # seção de ambientes presente com nomes e valores
    assert "4. Ambientes" in tbl_blob
    assert "Cozinha" in tbl_blob and "Dormitório" in tbl_blob and "Home Theater" in tbl_blob
    assert "R$ 12.345,67" in tbl_blob and "R$ 8.900,00" in tbl_blob and "R$ 5.200,00" in tbl_blob
    # total = soma
    assert "Total" in tbl_blob and "R$ 26.445,67" in tbl_blob
    # Forma de pagamento renumerada e grade ainda preenchida
    assert "5. Forma de Pagamento" in tbl_blob
    assert "R$ 4.820,00" in tbl_blob
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_contrato.py::test_contrato_com_secao_ambientes -v`
Expected: FAIL (`"4. Ambientes"` ausente — a seção ainda não é gerada).

- [ ] **Step 3: Implement `_preencher_ambientes` and wire it into `preencher_contrato`**

Em `mod_contrato.py`, adicionar o import perto do topo (após `from docx import Document`, ~linha 14):

```python
from docx.enum.text import WD_ALIGN_PARAGRAPH
```

Adicionar a função (após `_preencher_grade`, ~linha 245):

```python
def _preencher_ambientes(doc, itens_valores, coletor=None):
    """Insere a seção '4. Ambientes' antes da tabela de Forma de Pagamento.

    itens_valores: [(nome, valor_float), ...] (já calculado por
    ambientes_valor_contrato). Adiciona uma linha 'Total' = soma e renumera
    'Forma de Pagamento' para '5.'. Ambas as colunas justificadas à esquerda.
    As células de valor (menos a do Total) entram no coletor de regiões editáveis.
    Lista vazia → não faz nada.
    """
    if not itens_valores:
        return
    grade = _localizar_tabela(doc, "forma de pagamento")
    if grade is None:
        return
    # Renumerar o título da seção de pagamento: '4.' -> '5.'
    _set_cell_text(_unique_cells(grade.rows[0])[0], "5. Forma de Pagamento")

    total = round(sum(v for _, v in itens_valores), 2)
    linhas = list(itens_valores) + [("Total", total)]

    tbl = doc.add_table(rows=0, cols=2)
    tbl.style = grade.style
    # título da seção, mesclado nas 2 colunas
    titulo = tbl.add_row().cells
    titulo[0].merge(titulo[1])
    _set_cell_text(titulo[0], "4. Ambientes")
    for nome, val in linhas:
        cels = tbl.add_row().cells
        _set_cell_text(cels[0], nome)
        _set_cell_text(cels[1], _formatar_valor(val),
                       coletor if nome != "Total" else None)
        for c in cels:
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT

    # posiciona [tabela ambientes][parágrafo separador][grade]
    sep = doc.add_paragraph()
    grade._tbl.addprevious(tbl._tbl)
    grade._tbl.addprevious(sep._p)
```

Em `preencher_contrato`, logo após a linha `_preencher_grade(doc, pag, coletor=coletor)` (~linha 546), adicionar:

```python
    _preencher_ambientes(doc, ctx.get("_ambientes") or [], coletor=coletor)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_contrato.py -v`
Expected: todos passam, incluindo `test_contrato_com_secao_ambientes` e o `test_geracao_completa_sem_marcadores_remanescentes` (que **não** passa `_ambientes` → seção omitida, grade `4.` mantida — sem `5.`; asserts desse teste não checam numeração, então continuam válidos).

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): secao 4. Ambientes com valor por ambiente + total; Forma de Pagamento -> 5"
```

---

## Task 4: Injetar `_ambientes` nas rotas de geração de contrato

As duas rotas que geram o `.docx` (`POST /api/projetos/<nome>/contrato` e a de edição/regeração) montam `variaveis` e chamam `gerar_pdf_contrato`. Ambas passam a calcular e injetar `variaveis["_ambientes"]`.

**Files:**
- Modify: `main.py` — novo helper `_ambientes_valor_para_contrato`; injeção nos 2 blocos `variaveis.update({...})` (~linha 3529 e ~linha 4138)
- Test: `tests/test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura` (estender asserts)

**Interfaces:**
- Consumes (de Task 1): `mod_contrato.ambientes_valor_contrato`.
- Consumes (existente em `main.py`): `_negociacao_breakdown(orc, db)` → `d` com `d["ambientes"]` (cada item tem `id` e `VAVA`), `d["VAVO"]`, `d["Val_Cont"]`.
- Produces: `_ambientes_valor_para_contrato(orcamento_id, db) -> list[tuple[str, float]]`.

- [ ] **Step 1: Write the failing test (estende o E2E de geração real)**

Em `tests/test_fluxo_completo_e2e.py`, dentro de `test_contrato_real_geracao_e_assinatura`, após a geração real do contrato e a localização do `.docx`/`.pdf`, adicionar a verificação da seção de ambientes. Localizar o ponto onde o teste abre/valida o documento gerado e acrescentar:

```python
    # A capa do contrato deve conter a seção "4. Ambientes" com o(s) ambiente(s)
    # do orçamento e a Forma de Pagamento renumerada para "5".
    from docx import Document as _Doc
    _docx = contrato_docx_path  # caminho do .docx gerado (ajustar ao nome usado no teste)
    _blob = ""
    for _t in _Doc(_docx).tables:
        for _r in _t.rows:
            for _c in _r.cells:
                _blob += "\n" + _c.text
    assert "4. Ambientes" in _blob
    assert "5. Forma de Pagamento" in _blob
```

> Nota para quem implementa: use a variável do próprio teste que já aponta para o arquivo gerado (o teste hoje serve `GET /contrato/pdf`; o `.docx` fica em `CONTRATOS_DIR/contrato_<id>.docx`). Se não houver variável pronta, componha o caminho a partir do `contrato_id` retornado pela rota e de `mod_contrato.CONTRATOS_DIR`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura -v`
Expected: FAIL em `assert "4. Ambientes" in _blob` (rota ainda não injeta `_ambientes`).

- [ ] **Step 3: Add the helper and inject in both routes**

Em `main.py`, adicionar o helper perto de `_montar_dados_projeto_para_contrato` (~linha 4645):

```python
def _ambientes_valor_para_contrato(orcamento_id, db):
    """Lista [(nome_exibicao, valor_com_financeiro), ...] para a seção de ambientes
    do contrato. Reusa o breakdown do motor e o rateio de mod_contrato."""
    from mod_contrato import ambientes_valor_contrato
    orc = db.get(Orcamento, orcamento_id)
    if not orc:
        return []
    d = _negociacao_breakdown(orc, db)
    nome_por_id = {
        oa.pool_ambiente_id: oa.pool_ambiente.nome_exibicao
        for oa in db.query(OrcamentoAmbiente)
                    .filter_by(orcamento_id=orcamento_id)
                    .join(PoolAmbiente).all()
    }
    itens = [(nome_por_id.get(a.get("id"), ""), float(a.get("VAVA") or 0.0))
             for a in d.get("ambientes", [])]
    return ambientes_valor_contrato(itens, d.get("VAVO", 0.0), d.get("Val_Cont", 0.0))
```

Na **rota `POST /api/projetos/<nome>/contrato`**, dentro do `variaveis.update({...})` (~linha 3529), acrescentar a chave:

```python
                        "_ambientes":      _ambientes_valor_para_contrato(orcamento_id, db),
```

Na **rota de edição/regeração** (~linha 4138), dentro do respectivo `variaveis.update({...})`, acrescentar (usa o orçamento do contrato):

```python
                        "_ambientes":      _ambientes_valor_para_contrato(contrato.orcamento_id, db),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_fluxo_completo_e2e.py::test_contrato_real_geracao_e_assinatura -v`
Expected: PASS (seção "4. Ambientes" e "5. Forma de Pagamento" presentes no contrato real).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_fluxo_completo_e2e.py
git commit -m "feat(contrato): rotas injetam ambientes+valor no ctx do contrato"
```

---

## Task 5: Suíte completa + verificação final

- [ ] **Step 1: Run the full suite**

Run: `python3 -m pytest -q`
Expected: tudo verde (partindo de 378 passed + os testes novos), **sem regressão** nos testes de contrato/proposta/E2E.

- [ ] **Step 2: Conferência visual (manual, registrar no DEV_LOG)**

Gerar um contrato real no ambiente com LibreOffice (`python3 main.py`, porta 8765) e conferir no PDF: a seção "4. Ambientes" aparece antes da "5. Forma de Pagamento", nomes e valores alinhados à esquerda, linha Total batendo com o total do contrato. (Sem LibreOffice, abrir o `.docx`.)

- [ ] **Step 3: Atualizar o DEV_LOG**

Registrar a frente em `DEV_LOG.md` (nova sessão): seção "4. Ambientes" no contrato, rateio do financeiro proporcional ao VAVA, grade localizada por conteúdo, proposta como próxima frente.

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — secao Ambientes com valor no contrato"
```

---

## Self-Review (preenchido)

**Spec coverage:**
- §1 objetivo / §5 posição (antes da Forma de Pagamento, renumerada) → Task 3.
- §2 conteúdo (nome à esquerda, valor à esquerda, linha Total) → Task 3 (`_preencher_ambientes`) + teste.
- §3 cálculo `Val_Cont_Amb` proporcional ao VAVA → Task 1.
- §3.1 reconciliação de centavos (último ambiente) → Task 1 + teste dedicado.
- §4 origem dos dados (breakdown, sem alterar o motor) → Task 4 (`_ambientes_valor_para_contrato`).
- §6.3 grade por conteúdo, não por índice → Task 2.
- §6.5 proteção read-only nas células de valor → Task 3 (coletor nas células de valor, exceto Total).
- §7 fora de escopo (proposta) → não tocada; registrada como próxima frente (Task 5.3).
- §8 testes (unit + template + trava de índice) → Tasks 1, 2, 3; §9 aceite → Task 5.

**Placeholder scan:** sem TBD/TODO; todo passo de código traz o código. A única nota interpretativa é o nome da variável do caminho do `.docx` no teste E2E (Task 4, Step 1) — instrução explícita de como compô-lo a partir de `contrato_id` + `mod_contrato.CONTRATOS_DIR`.

**Type consistency:** `ambientes_valor_contrato(itens, vavo, val_cont)` e `_preencher_ambientes(doc, itens_valores, coletor)` recebem/retornam `list[tuple[str, float]]` de forma consistente entre Tasks 1, 3 e 4; `_localizar_tabela(doc, titulo_substr)` idem entre Tasks 2 e 3.
