# Negociação: bloqueio pós-aprovação, Rever Orçamento, À Vista e Formas de Pagamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Após aprovar o orçamento, travar toda a negociação (somente-leitura) com desbloqueio via "Rever Orçamento" (senha gerencial) na própria tela de negociação; adicionar painel À Vista (entrada + liquidação), calendário clicável em todos os campos de data, e captura da forma de pagamento (entrada/parcelas) por modalidade levada ao contrato.

**Architecture:** O frontend é um SPA de arquivo único (`static/index.html`, JS inline) — a negociação passa a ser a **fonte da verdade** da forma de pagamento (regras por modalidade), gravada em `window._planoPagamento` e persistida no `forma_pagamento` JSON do orçamento; o modal de aprovação pré-seleciona desses valores. O backend (`mod_contrato.py`) converte os códigos de forma para rótulos pt-BR e preenche um novo marcador `[TIPO]` (forma das parcelas) no template, inserido por script idempotente.

**Tech Stack:** Python (stdlib `http.server`, SQLAlchemy, python-docx), pytest, HTML/CSS/JS vanilla, verificação via Playwright (instalado) + endpoints de cálculo (`/calcular_aymore` etc.).

---

## File Structure

- **Modificar** `mod_contrato.py` — mapa de rótulos de forma; `forma_parcela` em `_parse_pagamento`; `"TIPO"` em `_montar_mapping`.
- **Criar** `scripts/inserir_marcador_tipo.py` — script idempotente que insere `[TIPO]` junto de `[NUM_PARCELAS]` no `modelo_contrato_mapeado.docx`.
- **Modificar** `modelo_contrato_mapeado.docx` — passa a conter `[NUM_PARCELAS] / [TIPO]` (gerado pelo script).
- **Modificar** `tests/test_contrato.py` — novos testes (rótulos, forma_parcela, TIPO no template, geração end-to-end com forma).
- **Modificar** `static/index.html` — calendário; seletores de forma na negociação; painel À Vista; bloqueio pós-aprovação; botão "Rever Orçamento"; pré-preenchimento/persistência da forma.

> **Nota sobre testes de frontend:** o projeto não tem harness de teste JS. Tarefas de frontend usam *implementar → verificar com Playwright/dados reais → commit*. Tarefas de backend usam TDD com pytest. Rodar a suíte completa (`python -m pytest -q`) ao fim de cada tarefa de backend e na verificação final.

---

## Task 1: Backend — rótulos de forma + `forma_parcela` + marcador `TIPO`

**Files:**
- Modify: `mod_contrato.py` (`_parse_pagamento` ~256-303; `_montar_mapping` ~361-394)
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `tests/test_contrato.py`:

```python
# ── Forma de pagamento: rótulos pt-BR + forma_parcela + marcador TIPO ──────────

def test_forma_label_mapeia_codigos():
    from mod_contrato import _forma_label
    assert _forma_label("pix") == "Pix"
    assert _forma_label("ted") == "TED"
    assert _forma_label("transferencia") == "TED"
    assert _forma_label("boleto") == "Boleto"
    assert _forma_label("cheque") == "Cheque"
    assert _forma_label("dinheiro") == "Dinheiro"
    assert _forma_label("cartao_credito") == "Cartão de Crédito"
    assert _forma_label("") == ""
    assert _forma_label("Boleto") == "Boleto"   # já-rótulo passa adiante


def test_parse_pagamento_forma_parcela_de_parcelas():
    import json
    from mod_contrato import _parse_pagamento
    pag = json.dumps({
        "tipo": "venda_programada", "nome_forma": "Venda Programada",
        "entrada_valor": 1000, "entrada_forma": "pix", "total_cliente": 5000,
        "parcelas": [
            {"num": 1, "data": "10/07/2026", "valor": 2000.0, "forma": "cheque"},
            {"num": 2, "data": "10/08/2026", "valor": 2000.0, "forma": "cheque"},
        ],
    })
    d = _parse_pagamento(pag)
    assert d["entrada_tipo"] == "Pix"
    assert d["forma_parcela"] == "Cheque"


def test_parse_pagamento_forma_parcela_cartao():
    import json
    from mod_contrato import _parse_pagamento
    d = _parse_pagamento(json.dumps({
        "tipo": "cartao", "nome_forma": "Cartão de Crédito",
        "texto_cartao": "12x R$ 10.000,00", "total_cliente": 120000, "parcelas": []}))
    assert d["forma_parcela"] == "Cartão de Crédito"


def test_montar_mapping_inclui_tipo():
    from mod_contrato import _montar_mapping
    ctx = {}
    pag = {"forma_parcela": "Boleto", "entrada_tipo": "Pix", "num_parcelas": "3"}
    m = _montar_mapping(ctx, pag)
    assert m["TIPO"] == "Boleto"
    assert m["FORMA_ENTRADA"] == "Pix"
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `python -m pytest tests/test_contrato.py::test_forma_label_mapeia_codigos tests/test_contrato.py::test_parse_pagamento_forma_parcela_de_parcelas tests/test_contrato.py::test_parse_pagamento_forma_parcela_cartao tests/test_contrato.py::test_montar_mapping_inclui_tipo -v`
Expected: FAIL — `ImportError: cannot import name '_forma_label'` / `KeyError: 'TIPO'` / `KeyError: 'forma_parcela'`.

- [ ] **Step 3: Implementar `_forma_label` + ajustar `_parse_pagamento`**

Em `mod_contrato.py`, adicionar antes de `_parse_pagamento` (após a seção "Parser de pagamento", ~linha 254):

```python
_FORMA_LABELS = {
    "pix": "Pix",
    "ted": "TED",
    "transferencia": "TED",
    "boleto": "Boleto",
    "cheque": "Cheque",
    "dinheiro": "Dinheiro",
    "cartao_credito": "Cartão de Crédito",
    "cartao_debito": "Cartão de Débito",
    "debito_automatico": "Débito Automático",
}


def _forma_label(codigo: str) -> str:
    """Converte código de forma de pagamento em rótulo pt-BR. Idempotente:
    um rótulo já formatado (não encontrado no mapa) é devolvido como veio."""
    if not codigo:
        return ""
    return _FORMA_LABELS.get(str(codigo).strip().lower(), str(codigo).strip())
```

Dentro de `_parse_pagamento`, na atribuição de `entrada_tipo` (~linha 276), envolver com o rótulo e derivar `forma_parcela`:

```python
    entrada_tipo = _forma_label(pag.get("entrada_forma") or pag.get("entrada_tipo") or "")
    parcelas     = pag.get("parcelas") or []
    num_parcelas = len(parcelas)

    if tipo == "cartao":
        forma_parcela = "Cartão de Crédito"
    elif parcelas:
        forma_parcela = _forma_label(parcelas[0].get("forma") or "")
    else:
        forma_parcela = ""
```

E adicionar ao dict retornado por `_parse_pagamento` (junto dos outros campos):

```python
        "forma_parcela":    forma_parcela,
```

- [ ] **Step 4: Mapear `TIPO` em `_montar_mapping`**

Em `_montar_mapping`, junto de `"NUM_PARCELAS"` (~linha 386), adicionar:

```python
        "TIPO":             pag.get("forma_parcela", "") or "",
```

- [ ] **Step 5: Rodar os testes da Task 1**

Run: `python -m pytest tests/test_contrato.py -k "forma or mapping" -v`
Expected: PASS (4 novos testes).

- [ ] **Step 6: Rodar a suíte completa (sem regressões)**

Run: `python -m pytest -q`
Expected: PASS (93 + 4 = 97 testes; nenhum quebrado).

- [ ] **Step 7: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): rotulos de forma de pagamento + forma_parcela + marcador TIPO"
```

---

## Task 2: Backend — script idempotente que insere `[TIPO]` no template

**Files:**
- Create: `scripts/inserir_marcador_tipo.py`
- Modify: `modelo_contrato_mapeado.docx` (saída do script)
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao final de `tests/test_contrato.py`:

```python
def test_template_tem_marcador_tipo():
    import os
    from docx import Document
    from mod_contrato import _MODELO
    assert os.path.exists(_MODELO)
    d = Document(_MODELO)
    blob = "\n".join(p.text for p in d.paragraphs)
    for t in d.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    assert "[TIPO]" in blob
    # garante que [TIPO] convive com [NUM_PARCELAS] (não substituiu)
    assert "[NUM_PARCELAS]" in blob


def test_geracao_completa_com_forma_parcela():
    import os, json, re
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome": "Ana", "cpf": "1", "email": "a@x.com", "telefone": "(12)9",
                 "logradouro": "Rua A", "numero": "10", "complemento": "", "bairro": "Centro",
                 "cidade": "SJC", "cep": "12000", "estado": "SP", "inst_mesmo_residencial": True,
                 "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
                 "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""},
        usuario={"nome": "Z", "telefone": "", "email": ""},
        forma_pagamento_json=json.dumps({
            "tipo": "venda_programada", "nome_forma": "Venda Programada",
            "entrada_valor": 1000, "entrada_data": "2026-06-18", "entrada_forma": "pix",
            "total_cliente": 5000.0, "texto_cartao": "",
            "parcelas": [{"num": i+1, "data": f"18/{7+i:02d}/2026", "valor": 2000.0,
                          "forma": "cheque"} for i in range(2)]}))
    ctx["num_contrato"] = "INS-2026-06-18-001"; ctx["data_contrato"] = "18/06/2026"
    path = preencher_contrato(93001, ctx)
    doc = Document(path)
    blob = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                blob += "\n" + c.text
    os.remove(path)
    assert "Cheque" in blob          # forma das parcelas (TIPO)
    assert "Pix" in blob             # forma da entrada (FORMA_ENTRADA)
    assert re.findall(r'\[[A-Za-z0-9_ ]+\]', blob) == []   # nenhum marcador sobra
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `python -m pytest tests/test_contrato.py::test_template_tem_marcador_tipo tests/test_contrato.py::test_geracao_completa_com_forma_parcela -v`
Expected: FAIL — `assert "[TIPO]" in blob` falha (template ainda não tem o marcador).

- [ ] **Step 3: Criar o script idempotente**

Criar `scripts/inserir_marcador_tipo.py`:

```python
"""Insere o marcador [TIPO] (forma das parcelas) junto de [NUM_PARCELAS] no
modelo_contrato_mapeado.docx. Idempotente: não duplica se já existir [TIPO].

Uso: python scripts/inserir_marcador_tipo.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from docx import Document  # noqa: E402

MODELO = os.path.join(os.path.dirname(__file__), "..", "modelo_contrato_mapeado.docx")


def _inserir_em_paragrafo(par):
    """Se o parágrafo contém [NUM_PARCELAS] e não contém [TIPO], reescreve seus
    runs inserindo ' / [TIPO]' logo após [NUM_PARCELAS], preservando a fonte do
    primeiro run. Retorna True se alterou."""
    txt = "".join(r.text for r in par.runs)
    if "[NUM_PARCELAS]" not in txt or "[TIPO]" in txt:
        return False
    novo = txt.replace("[NUM_PARCELAS]", "[NUM_PARCELAS] / [TIPO]")
    base = par.runs[0] if par.runs else None
    name = base.font.name if base is not None else None
    size = base.font.size if base is not None else None
    bold = base.bold if base is not None else None
    for r in list(par.runs):
        r._r.getparent().remove(r._r)
    run = par.add_run(novo)
    if name is not None:
        run.font.name = name
    if size is not None:
        run.font.size = size
    if bold is not None:
        run.bold = bold
    return True


def main():
    doc = Document(MODELO)
    alterou = False
    for par in doc.paragraphs:
        alterou = _inserir_em_paragrafo(par) or alterou
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for par in cell.paragraphs:
                    alterou = _inserir_em_paragrafo(par) or alterou
    if alterou:
        doc.save(MODELO)
        print("[OK] [TIPO] inserido junto de [NUM_PARCELAS].")
    else:
        print("[OK] Nada a fazer (já contém [TIPO] ou não achou [NUM_PARCELAS]).")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Executar o script (com o Word fechado)**

Run: `python scripts/inserir_marcador_tipo.py`
Expected: `[OK] [TIPO] inserido junto de [NUM_PARCELAS].`

- [ ] **Step 5: Rodar o script de novo (verificar idempotência)**

Run: `python scripts/inserir_marcador_tipo.py`
Expected: `[OK] Nada a fazer (já contém [TIPO] ou não achou [NUM_PARCELAS]).`

- [ ] **Step 6: Rodar os testes da Task 2 + suíte completa**

Run: `python -m pytest tests/test_contrato.py -q`
Expected: PASS, incluindo `test_template_tem_marcador_tipo` e `test_geracao_completa_com_forma_parcela`.

Run: `python -m pytest -q`
Expected: PASS (99 testes).

- [ ] **Step 7: Commit**

```bash
git add scripts/inserir_marcador_tipo.py modelo_contrato_mapeado.docx tests/test_contrato.py
git commit -m "feat(contrato): marcador [TIPO] no template via script idempotente"
```

---

## Task 3: Frontend — calendário clicável em todos os campos de data

**Files:**
- Modify: `static/index.html` (bloco `<style>` e um listener global no JS)

- [ ] **Step 1: Adicionar CSS para o ícone do calendário**

No bloco `<style>` do `index.html`, adicionar:

```css
/* Calendário: ícone visível e campo inteiro clicável */
input[type="date"] { cursor: pointer; }
input[type="date"]::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 1;
  filter: invert(0.7);
}
```

- [ ] **Step 2: Adicionar listener global que abre o picker ao clicar**

No JS, dentro de um bloco de inicialização global (ex.: junto ao listener de `DOMContentLoaded` existente, perto de `projCarregar()`), adicionar:

```javascript
// Abre o calendário nativo ao clicar em qualquer parte de um campo de data
document.addEventListener('click', (e) => {
  const el = e.target.closest('input[type="date"]');
  if (el && !el.disabled && !el.readOnly && typeof el.showPicker === 'function') {
    try { el.showPicker(); } catch (_) { /* alguns navegadores bloqueiam fora de gesto */ }
  }
});
```

> A delegação cobre os campos dinâmicos das tabelas VP/TF (criados depois).

- [ ] **Step 3: Verificar com o app rodando (Playwright)**

Run (background): `python main.py`
Verificar em `http://127.0.0.1:8765`: abrir um projeto → negociação → selecionar Aymoré → clicar no campo "Data do contrato" (em qualquer ponto, não só no ícone) e confirmar que o calendário abre. Repetir em um campo de data dentro da tabela VP.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): calendario nativo clicavel em todos os campos de data"
```

---

## Task 4: Frontend — seletores de forma de pagamento na negociação (por modalidade)

**Files:**
- Modify: `static/index.html` (HTML após `neg-parcelas` ~436-439; JS `onPagamentoChange` ~3068; os 4 blocos `window._planoPagamento` ~3314/3425/3568/4003)

- [ ] **Step 1: Adicionar os seletores no HTML**

Logo após o `<select id="neg-parcelas">…</select>` (linha ~439), inserir:

```html
    <label class="sb-label" id="neg-forma-entrada-lbl">Forma da entrada</label>
    <select id="neg-forma-entrada" onchange="onFormaChange()" class="sb-select"></select>

    <div id="neg-forma-parcela-wrap">
      <label class="sb-label">Forma das parcelas</label>
      <select id="neg-forma-parcela" onchange="onFormaChange()" class="sb-select"></select>
    </div>
```

- [ ] **Step 2: Adicionar estado e tabelas de opções no JS**

Perto de `let _codigoPagAtivo` (~linha 3028), adicionar:

```javascript
let _formaEntrada = 'pix';
let _formaParcela = 'boleto';

const _FORMAS_ENTRADA = [['pix','Pix'],['ted','TED'],['boleto','Boleto']];
const _FORMAS_AVISTA  = [['pix','Pix'],['ted','TED'],['boleto','Boleto'],['cheque','Cheque'],['dinheiro','Dinheiro']];
const _FORMAS_PARC_VPTF = [['boleto','Boleto'],['cheque','Cheque']];

function _preencherSelectFormas(sel, opcoes, valorAtual) {
  sel.innerHTML = opcoes.map(([v,l]) => `<option value="${v}">${l}</option>`).join('');
  if (opcoes.find(([v]) => v === valorAtual)) sel.value = valorAtual;
  else sel.value = opcoes[0] ? opcoes[0][0] : '';
  return sel.value;
}

function onFormaChange() {
  const selE = document.getElementById('neg-forma-entrada');
  const selP = document.getElementById('neg-forma-parcela');
  if (selE) _formaEntrada = selE.value;
  if (selP && !selP.disabled) _formaParcela = selP.value;
  agendarCalculo();
}

// Aplica as regras de forma de pagamento por modalidade.
function atualizarFormasPagamento(codigo) {
  const selE   = document.getElementById('neg-forma-entrada');
  const lblE   = document.getElementById('neg-forma-entrada-lbl');
  const wrapP  = document.getElementById('neg-forma-parcela-wrap');
  const selP   = document.getElementById('neg-forma-parcela');
  if (!selE || !selP) return;

  if (codigo === 'a_vista') {
    // À vista usa o painel-avista (entrada + liquidação); oculta estes seletores.
    selE.parentElement.style.display = 'none';   // o <select> e seu <label> via wrappers? ver nota
    lblE.style.display = 'none';
    selE.style.display = 'none';
    wrapP.style.display = 'none';
    return;
  }
  lblE.style.display = ''; selE.style.display = ''; wrapP.style.display = '';

  // Entrada: sempre Pix/TED/Boleto
  _formaEntrada = _preencherSelectFormas(selE, _FORMAS_ENTRADA, _formaEntrada);

  // Parcelas: depende da modalidade
  if (codigo === 'cartao_credito' || codigo === 'cartao_credito_x') {
    selP.innerHTML = '<option value="cartao_credito">Cartão de Crédito</option>';
    selP.value = 'cartao_credito'; selP.disabled = true; _formaParcela = 'cartao_credito';
  } else if (codigo === 'aymore') {
    selP.innerHTML = '<option value="boleto">Boleto</option>';
    selP.value = 'boleto'; selP.disabled = true; _formaParcela = 'boleto';
  } else if (codigo === 'venda_programada' || codigo === 'total_flex') {
    selP.disabled = false;
    _formaParcela = _preencherSelectFormas(selP, _FORMAS_PARC_VPTF, _formaParcela);
  } else {
    // fallback (ex.: outras modalidades): livre Pix/TED/Boleto
    selP.disabled = false;
    _formaParcela = _preencherSelectFormas(selP, _FORMAS_ENTRADA, _formaParcela);
  }
}
```

> **Nota de implementação:** o HTML do Step 1 coloca `neg-forma-entrada` sem wrapper próprio; ajuste o `display:none` para esconder apenas `lblE` e `selE` (remova a linha `selE.parentElement.style.display`). Mantido aqui para deixar explícita a intenção de ocultar o par label+select no caso à vista.

- [ ] **Step 3: Chamar `atualizarFormasPagamento` em `onPagamentoChange`**

Em `onPagamentoChange()`, junto das chamadas `ayMostrarPainel(...)` / `cartaoMostrarPainel(...)` (~linha 3098-3101), adicionar:

```javascript
    atualizarFormasPagamento(codigo);
```

E no bloco `catch` do mesmo `onPagamentoChange` (~3104), adicionar também `atualizarFormasPagamento('a_vista');` para estado seguro.

- [ ] **Step 4: Levar a forma ao `window._planoPagamento` (4 painéis)**

Em cada um dos 4 blocos `window._planoPagamento = {…}`:

- Aymoré (~3314): trocar `entrada_forma: ''` por `entrada_forma: _formaEntrada,` e em `parcelas: (…).map((p,i)=>({ num:i+1, data:p.data, valor:d.valor_parcela }))` adicionar `forma: _formaParcela` a cada parcela.
- Cartão (~3425): `entrada_forma: _formaEntrada` (parcelas ficam no `texto_cartao`; sem alterar).
- Venda Programada (~3568): `entrada_forma: _formaEntrada` e `forma: _formaParcela` em cada parcela.
- Total Flex (~4003): `entrada_forma: _formaEntrada` e `forma: _formaParcela` em cada parcela.

Exemplo (aymoré):

```javascript
  window._planoPagamento = {
    tipo: 'aymore', nome_forma: 'Financiamento Aymoré',
    entrada_valor: entrada,
    entrada_data: document.getElementById('ay-data-contrato')?.value || '',
    entrada_forma: _formaEntrada,
    total_cliente: d.total_cliente, texto_cartao: '',
    parcelas: (d.parcelas || [])
      .filter(p => p.tipo === 'primeira' || p.tipo === 'parcela')
      .map((p, i) => ({ num: i + 1, data: p.data, valor: d.valor_parcela, forma: _formaParcela })),
  };
```

> Para Cartão, defina `_formaParcela = 'cartao_credito'` (já feito por `atualizarFormasPagamento`); não é necessário pôr `forma` em parcelas (lista vazia).

- [ ] **Step 5: Verificar com Playwright**

Com `python main.py` rodando: abrir projeto → negociação. Para cada modalidade confirmar:
- Cartão de Crédito: "Forma das parcelas" mostra só "Cartão de Crédito" desabilitado; entrada com Pix/TED/Boleto.
- Aymoré: parcelas só "Boleto" desabilitado.
- Venda Programada / Total Flex: parcelas com Boleto/Cheque selecionáveis.
No console do navegador, após calcular, inspecionar `JSON.stringify(window._planoPagamento)` e confirmar `entrada_forma` e `parcelas[].forma` corretos.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): seletores de forma de pagamento por modalidade"
```

---

## Task 5: Frontend — painel À Vista (entrada + liquidação)

**Files:**
- Modify: `static/index.html` (HTML dos painéis de modalidade após `painel-tf` ~975-1013; JS novo `avistaMostrarPainel` + bloco `_planoPagamento`; `onPagamentoChange` ~3097)

- [ ] **Step 1: Adicionar o HTML do painel À Vista**

Após o fechamento do `<div class="mod-panel" id="painel-tf">…</div>` (~linha 1013), inserir:

```html
    <div class="mod-panel" id="painel-avista" style="display:none">
      <div class="mod-panel-title">&#x1F4B5; À Vista</div>
      <div class="mp-row">
        <label>Valor da entrada</label>
        <input type="text" id="av-entrada-valor" inputmode="numeric"
               placeholder="R$ 0,00" oninput="mascaraMoedaInput(this); avistaRecalcular()">
      </div>
      <div class="mp-row">
        <label>Data da entrada</label>
        <input type="date" id="av-entrada-data" oninput="avistaRecalcular()">
      </div>
      <div class="mp-row">
        <label>Forma da entrada</label>
        <select id="av-entrada-forma" onchange="avistaRecalcular()"></select>
      </div>
      <div class="mp-row">
        <label>Valor da liquidação</label>
        <input type="text" id="av-liq-valor" readonly>
      </div>
      <div class="mp-row">
        <label>Data da liquidação</label>
        <input type="date" id="av-liq-data" oninput="avistaRecalcular()">
      </div>
      <div class="mp-row">
        <label>Forma da liquidação</label>
        <select id="av-liq-forma" onchange="avistaRecalcular()"></select>
      </div>
    </div>
```

> Ajustar classes (`mp-row` etc.) para casar com o CSS dos demais painéis se necessário; reutilizar o padrão visual de `painel-tf`.

- [ ] **Step 2: Implementar `avistaMostrarPainel` e `avistaRecalcular`**

No JS (junto aos demais `*MostrarPainel`), adicionar:

```javascript
function avistaMostrarPainel(mostrar) {
  const p = document.getElementById('painel-avista');
  if (p) p.style.display = mostrar ? 'block' : 'none';
  if (mostrar) {
    const selE = document.getElementById('av-entrada-forma');
    const selL = document.getElementById('av-liq-forma');
    if (selE && !selE.options.length)
      selE.innerHTML = _FORMAS_AVISTA.map(([v,l]) => `<option value="${v}">${l}</option>`).join('');
    if (selL && !selL.options.length)
      selL.innerHTML = _FORMAS_AVISTA.map(([v,l]) => `<option value="${v}">${l}</option>`).join('');
    const dE = document.getElementById('av-entrada-data');
    if (dE && !dE.value) dE.value = new Date().toISOString().split('T')[0];
    avistaRecalcular();
  }
}

function avistaRecalcular() {
  const total   = _ayGetValorVenda() || 0;               // valor à vista da negociação
  const entrada = parseMoeda(document.getElementById('av-entrada-valor')?.value) || 0;
  const saldo   = Math.max(0, total - entrada);
  const elLiq = document.getElementById('av-liq-valor');
  if (elLiq) elLiq.value = 'R$ ' + fmt(saldo);

  const entradaData = document.getElementById('av-entrada-data')?.value || '';
  const liqData     = document.getElementById('av-liq-data')?.value || '';
  const entradaForma= document.getElementById('av-entrada-forma')?.value || 'pix';
  const liqForma    = document.getElementById('av-liq-forma')?.value || 'pix';

  window._planoPagamento = {
    tipo: 'avista', nome_forma: 'À Vista',
    entrada_valor: entrada,
    entrada_data: entradaData,
    entrada_forma: entradaForma,
    total_cliente: total, texto_cartao: '',
    parcelas: saldo > 0 ? [{ num: 1, data: liqData, valor: saldo, forma: liqForma }] : [],
  };
}
```

> `_ayGetValorVenda()` (existente, ~3223) devolve o valor à vista calculado da negociação; reaproveitado como total da modalidade à vista.

- [ ] **Step 3: Mostrar/ocultar o painel em `onPagamentoChange`**

Junto das outras chamadas de painel (~3097-3101), adicionar:

```javascript
    avistaMostrarPainel(codigo === 'a_vista');
```

E no `catch` (~3106-3109) adicionar `avistaMostrarPainel(false);`.

- [ ] **Step 4: Verificar com Playwright**

Com `python main.py` rodando: negociação → modalidade "1x" (à vista). Confirmar: painel À Vista aparece; ao digitar entrada, "Valor da liquidação" = total − entrada (read-only); datas com calendário; `window._planoPagamento.tipo === 'avista'` e a "parcela" = liquidação com forma escolhida.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): painel A Vista com entrada + liquidacao"
```

---

## Task 6: Frontend — bloqueio total da negociação após aprovação

**Files:**
- Modify: `static/index.html` (`atualizarBotoesAprovacao` ~6225; nova função `aplicarBloqueioNegociacao`)

- [ ] **Step 1: Implementar `aplicarBloqueioNegociacao`**

Adicionar perto de `atualizarBotoesAprovacao` (~6225):

```javascript
// Trava/destrava todos os controles de edição da negociação (page-02),
// exceto os botões de ação (que são tratados em atualizarBotoesAprovacao).
function aplicarBloqueioNegociacao(travar) {
  const root = document.getElementById('page-02');
  if (!root) return;
  const seletor = 'input, select, textarea';
  root.querySelectorAll(seletor).forEach(el => {
    if (el.closest('.action-row')) return;            // não mexe nos botões de ação
    if (el.dataset.noLock === '1') return;             // escape-hatch opcional
    if (travar) {
      if (el.tagName === 'SELECT') el.disabled = true;
      else el.readOnly = true;
      el.classList.add('neg-locked');
    } else {
      // só destrava o que ESTE bloqueio travou (preserva selects já desabilitados por regra)
      if (el.classList.contains('neg-locked')) {
        if (el.tagName === 'SELECT') el.disabled = false;
        else el.readOnly = false;
        el.classList.remove('neg-locked');
      }
    }
  });
  // Reaplica as regras de forma (ex.: parcelas fixas voltam a ficar disabled corretamente)
  if (!travar && typeof atualizarFormasPagamento === 'function') {
    atualizarFormasPagamento(document.getElementById('neg-pagamento')?.value || 'a_vista');
  }
}
```

Adicionar o CSS de "travado" no `<style>`:

```css
.neg-locked { opacity: .6; cursor: not-allowed; }
```

- [ ] **Step 2: Chamar a partir de `atualizarBotoesAprovacao`**

No início de `atualizarBotoesAprovacao` (após `const aprovado = _orcamentoAprovado();`), adicionar:

```javascript
  aplicarBloqueioNegociacao(aprovado);
```

- [ ] **Step 3: Garantir bloqueio ao recarregar orçamento aprovado**

`atualizarBotoesAprovacao()` já é chamada após carregar o ciclo (ver `_fetchCiclo`/`atualizarBotoesAprovacao` ~6216). Confirmar que, ao reabrir um projeto com etapa 6 concluída, a negociação já abre travada. Se houver caminho que renderiza a negociação sem chamar `atualizarBotoesAprovacao`, adicionar a chamada ali.

- [ ] **Step 4: Verificar com Playwright**

Com `python main.py`: aprovar um orçamento → confirmar que TODOS os campos (desconto, modalidade, parcelas, datas, entrada, total editável, formas) ficam somente-leitura. Recarregar a página/reabrir o projeto → continua travado.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): bloqueio total da negociacao apos aprovacao"
```

---

## Task 7: Frontend — botão "Rever Orçamento" na tela de negociação

**Files:**
- Modify: `static/index.html` (`atualizarBotoesAprovacao` ~6231-6242; remover botão do card 7 ~6591-6594; renomear `abrirModalVoltarOrcamento`/handler ~6747, 6786-6805)

- [ ] **Step 1: Adicionar "Rever Orçamento" na action-row pós-aprovação**

Em `atualizarBotoesAprovacao`, dentro do `if (aprovado)`, após criar `#btn-assinar-contrato`, adicionar a criação do segundo botão:

```javascript
    if (!actionRow.querySelector('#btn-rever-orcamento')) {
      const btnR = document.createElement('button');
      btnR.id = 'btn-rever-orcamento';
      btnR.className = 'btn btn-ghost';
      btnR.style.cssText = 'border-color:var(--warn,#c8a84b);color:var(--warn,#c8a84b);font-size:.85rem;font-weight:600;padding:8px 16px;border-radius:4px;cursor:pointer';
      btnR.innerHTML = '&#x270E; Rever Or&ccedil;amento';
      btnR.onclick = () => abrirModalReverOrcamento();
      actionRow.appendChild(btnR);
    }
```

E no `else` (não aprovado), remover também esse botão:

```javascript
    const bR = actionRow.querySelector('#btn-rever-orcamento');
    if (bR) bR.remove();
```

- [ ] **Step 2: Remover o "Voltar ao Orçamento" do card 7 do Ciclo**

Em `renderCiclo`/card do contrato (~6591-6594), remover o bloco:

```html
        <button onclick="abrirModalVoltarOrcamento()" class="btn-ciclo"
          style="font-size:.82rem;border-color:var(--warn,#c8a84b);color:var(--warn,#c8a84b)">
          &#x21A9; Voltar ao Or&ccedil;amento
        </button>
```

(Manter o botão "Revisar" ao lado.)

- [ ] **Step 3: Renomear a função e o modal**

Renomear `abrirModalVoltarOrcamento` → `abrirModalReverOrcamento` (~6747) e os textos do modal de "Voltar ao Orçamento" para "Rever Orçamento". No handler de sucesso (~6798-6803), após `desfazer_aprovacao` retornar ok, garantir o destravamento imediato da negociação:

```javascript
    document.getElementById('modal-voltar-overlay')?.remove();
    showToast('Orçamento reaberto. Edições liberadas.', false);
    await carregarCicloSilencioso();
    if (_cicloAberto) { await carregarCiclo(); }
    fecharCiclo();
    atualizarBotoesAprovacao();   // re-exibe Salvar/Aprovar, remove botões e DESTRAVA a negociação
```

> `atualizarBotoesAprovacao()` chama `aplicarBloqueioNegociacao(false)` (Task 6), destravando tudo. Manter o id `modal-voltar-overlay` para reaproveitar o modal existente, ou renomear consistentemente para `modal-rever-overlay` em todas as referências (`abrirModalReverOrcamento`, o `onclick` de cancelar e o `confirmar`).

- [ ] **Step 4: Atualizar referências restantes**

Buscar e atualizar qualquer outra referência a `abrirModalVoltarOrcamento` no arquivo. Confirmar que o submit chama `POST /ciclo/desfazer_aprovacao` (inalterado no backend).

- [ ] **Step 5: Verificar com Playwright**

Com `python main.py`: aprovar orçamento → na tela de negociação aparecem os dois botões lado a lado ("🔒 …assinar contrato" e "✎ Rever Orçamento"). Clicar em "Rever Orçamento" → modal de senha gerencial → autenticar (gerente, ex.: `lds2026`) → negociação destrava, botões Salvar/Aprovar voltam, e os dois botões somem. Confirmar que o card 7 do Ciclo não tem mais "Voltar ao Orçamento".

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(negociacao): botao Rever Orcamento (substitui Voltar ao Orcamento) na tela de negociacao"
```

---

## Task 8: Frontend — pré-preenchimento e persistência da forma de pagamento

**Files:**
- Modify: `static/index.html` (modal de aprovação `apr-forma-entrada`/`apr-forma-parcelas` ~6995-7016 e onde `pagAtual` é montado; persistência via `salvarValorNegociado`/`PATCH /orcamentos/<id>/valor`)

- [ ] **Step 1: Pré-selecionar as formas no modal de aprovação a partir de `_planoPagamento`**

Onde o modal de aprovação é montado (a função que cria `apr-forma-entrada`/`apr-forma-parcelas`), após inserir o HTML, pré-selecionar:

```javascript
  const pp = window._planoPagamento || {};
  const selFE = document.getElementById('apr-forma-entrada');
  const selFP = document.getElementById('apr-forma-parcelas');
  if (selFE && pp.entrada_forma) selFE.value = pp.entrada_forma;
  if (selFP && pp.parcelas && pp.parcelas[0]?.forma) selFP.value = pp.parcelas[0].forma;
```

> Mapear valores equivalentes: a negociação usa `ted`; o select do modal usa `transferencia`. Ao pré-selecionar, se `pp.entrada_forma === 'ted'` e não houver opção `ted`, selecionar `transferencia`. (Alternativa: adicionar `<option value="ted">TED</option>` ao select do modal e remover `transferencia`, deixando o backend mapear ambos — já suportado por `_forma_label`.)

- [ ] **Step 2: Persistir a forma no `forma_pagamento` do orçamento**

Localizar `salvarValorNegociado()` (persiste `valor_negociado` e `forma_pagamento` via `PATCH /orcamentos/<id>/valor`). Incluir no payload `forma_pagamento` o JSON do plano atual (capturado das formas da negociação):

```javascript
  const plano = _capturarPagamento(_formaEntrada, _formaParcela);
  // ... no body do PATCH:
  //   forma_pagamento: JSON.stringify(plano)
```

> Verificar a assinatura atual de `salvarValorNegociado` e do endpoint `PATCH /orcamentos/<id>/valor` antes de editar; manter os campos já enviados.

- [ ] **Step 3: Restaurar a forma ao reabrir o orçamento**

Onde a negociação carrega um orçamento existente (com `forma_pagamento` salvo), se houver `entrada_forma`/`parcelas[].forma`, ajustar `_formaEntrada`/`_formaParcela` antes de `atualizarFormasPagamento(...)`, para que os selects reflitam o salvo. (Se o parse do `forma_pagamento` salvo não estiver disponível no fluxo de carregamento, registrar como limitação aceita — o recálculo regenera `_planoPagamento`.)

- [ ] **Step 4: Verificar com Playwright (dados reais)**

Com `python main.py`: na negociação, escolher VP com parcelas "Cheque", entrada "Pix" → abrir "Aprovar Orçamento" → confirmar que os selects do modal vêm pré-selecionados (Pix / Cheque). Gerar contrato → baixar o `.docx`/PDF e confirmar que aparece "Pix" (entrada) e "Cheque" (parcelas — campo `[NUM_PARCELAS] / [TIPO]`).

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(aprovacao): pre-preenche e persiste forma de pagamento da negociacao"
```

---

## Task 9: Verificação integrada (dados reais) + suíte completa

**Files:** nenhuma alteração (apenas verificação); corrigir inline se algo falhar.

- [ ] **Step 1: Suíte de testes backend**

Run: `python -m pytest -q`
Expected: PASS (todos verdes; ~99 testes).

- [ ] **Step 2: Verificação end-to-end com Playwright e cálculo real**

Com `python main.py` rodando, em um projeto com ambientes reais (sem fabricar `pagamento_json`):
1. Negociação à vista: entrada + liquidação automática + formas; gerar contrato; conferir grade com 1 linha (liquidação) e forma.
2. Aymoré: entrada Pix, parcelas Boleto (fixo); contrato com "Boleto" no campo de parcelas.
3. Venda Programada: parcelas Cheque; contrato com "Cheque".
4. Cartão: só forma da entrada; parcelas = "Cartão de Crédito".
5. Total Flex: parcelas Boleto/Cheque.
6. Aprovar → negociação trava 100%; "Rever Orçamento" (senha gerente) destrava; "assinar contrato" abre o card 7.
7. Calendário abre em todos os campos de data (fixos e dinâmicos).

- [ ] **Step 3: Atualizar DEV_LOG.md**

Adicionar entrada da sessão 10 no `DEV_LOG.md` (RESUMO ATUAL + HISTÓRICO) descrevendo: bloqueio pós-aprovação, Rever Orçamento na negociação, painel À Vista, calendário, formas por modalidade, marcador `[TIPO]` no contrato.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: atualiza DEV_LOG (sessao 10 — bloqueio, rever orcamento, a vista, formas)"
```

---

## Self-Review (cobertura do spec)

- **Bloqueio pós-aprovação** → Task 6. ✓
- **Rever Orçamento (substitui Voltar ao Orçamento, na negociação, senha gerencial, reseta 6/7)** → Task 7. ✓
- **À Vista (entrada valor+data, liquidação valor automático+data)** → Task 5. ✓
- **Calendário em todos os campos de data (nativo)** → Task 3. ✓
- **Formas de pagamento por modalidade (entrada/parcelas)** → Tasks 4, 8 (+ backend 1). ✓
- **Contrato: `[TIPO]` junto de `[NUM_PARCELAS]` via script + mapeamento; entrada via `[FORMA_ENTRADA]`** → Tasks 1, 2. ✓
- **Verificação com dados reais (não fabricar `pagamento_json`)** → Task 9. ✓
- **YAGNI:** sem datepicker de terceiros, sem forma por-parcela, sem mudança no cálculo financeiro. ✓

**Consistência de nomes:** `_formaEntrada`/`_formaParcela`, `atualizarFormasPagamento`, `avistaMostrarPainel`/`avistaRecalcular`, `aplicarBloqueioNegociacao`, `abrirModalReverOrcamento`, `_forma_label`, `forma_parcela`, marcador `TIPO` — usados de forma idêntica entre as tarefas.
