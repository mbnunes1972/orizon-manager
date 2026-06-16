# Contract Module — Fixes & Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir 6 bugs no módulo de contrato e adicionar dados do cliente no cabeçalho, tabela dinâmica de pagamento e etapas pós-assinatura.

**Architecture:** Todas as mudanças são em `static/index.html` (frontend SPA), `main.py` (rotas HTTP), `mod_contrato.py` (geração do contrato) e `database.py` (modelos). O template `.docx` é atualizado via `scripts/configurar_template_contrato.py`.

**Tech Stack:** Python 3.12 · BaseHTTPRequestHandler · SQLAlchemy · docxtpl · JavaScript vanilla · HTML/CSS

---

## Mapa de Arquivos

| Arquivo | Seções alteradas |
|---|---|
| `static/index.html` | `abrirProjeto()`, `mascaraMoedaInput()`, `parseMoeda()`, `renderContratoUI()`, `_renderCardGenerico()`, `abrirAprovacaoComDados()`, `abrirModalAprovacaoOrcamento()`, `gerarContrato()`, `salvarValorNegociado()`, nova função `_capturarPagamento()` |
| `main.py` | `do_POST` rota `desfazer_aprovacao`, `_montar_dados_projeto_para_contrato()`, rota `POST /contrato`, nova rota `PATCH /api/projetos/<nome>/ciclo/<cod>/concluir` |
| `mod_contrato.py` | `montar_variaveis_contrato()`, nova `_formatar_bloco_pagamento()` |
| `database.py` | Campo `pagamento_json` em `Contrato` |
| `scripts/configurar_template_contrato.py` | Novos placeholders |

---

## Task 1 — Fix: Trocar de Projeto Mostra Contrato Errado

**Problema:** `_cicloAberto = true` persiste entre projetos. Ao trocar de projeto, o painel Ciclo continua aberto mostrando HTML do projeto anterior. Ao clicar em Gerar Contrato, usa `projetoAtivo` (projeto novo) mas o UI já estava com dados do projeto anterior.

**Arquivo:** `static/index.html` linha ~2207 (função `abrirProjeto`)

- [ ] **Step 1: Fechar painel ciclo ao trocar de projeto**

Localizar a linha em `abrirProjeto()` onde `projetoAtivo = d.projeto;` é atribuído (linha ~2212). Logo ANTES dessa linha, adicionar:

```js
// Resetar estado do ciclo antes de trocar de projeto
if (_cicloAberto) fecharCiclo();
_cicloData = {};
```

O bloco completo fica:
```js
async function abrirProjeto(nome_safe){
  try{
    const r = await fetch('/projetos/'+encodeURIComponent(nome_safe));
    const d = await r.json();
    if(!d.ok){ showToast('Erro: '+(d.erro||'falha'), true); return; }
    // Resetar estado do ciclo antes de trocar de projeto
    if (_cicloAberto) fecharCiclo();
    _cicloData = {};
    projetoAtivo = d.projeto;
    // ... restante do código existente
```

- [ ] **Step 2: Mesmo reset em criarProjeto (linha ~2580)**

Em `criarProjeto()`, após `const d = await r.json(); if(!d.ok){...}`:

```js
if (_cicloAberto) fecharCiclo();
_cicloData = {};
projetoAtivo = d.projeto;
```

- [ ] **Step 3: Testar manualmente**

1. Abrir projeto A → Abrir Ciclo → Abrir card 7 (Contrato)
2. Voltar para lista → Abrir projeto B
3. Verificar que o painel Ciclo está fechado
4. Abrir Ciclo no projeto B → confirmar que dados são do projeto B

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "fix: resetar estado do ciclo ao trocar de projeto"
```

---

## Task 2 — Fix: "Voltar ao Orçamento" — Unexpected end of JSON input

**Problema:** Em `do_POST`, a rota `desfazer_aprovacao` tem `json.loads(body)` **fora** do bloco `try/except`. Se `body` for vazio (Content-Length: 0) ou malformado, o `JSONDecodeError` sobe até o `BaseHTTPRequestHandler` que retorna HTML 500 — o browser lê esse HTML como JSON e falha com "Unexpected end of JSON input".

**Arquivo:** `main.py` linha ~1696–1735

- [ ] **Step 1: Mover json.loads para dentro do try/except**

Localizar:
```python
m = _re.match(r'^/api/projetos/([^/]+)/ciclo/desfazer_aprovacao$', path)
if m:
    nome_safe = unquote(m.group(1))
    req   = json.loads(body)
    login = (req.get("login") or "").strip()
    senha = (req.get("senha") or "").strip()
    db = get_session()
    try:
```

Substituir por:
```python
m = _re.match(r'^/api/projetos/([^/]+)/ciclo/desfazer_aprovacao$', path)
if m:
    nome_safe = unquote(m.group(1))
    db = get_session()
    try:
        req   = json.loads(body or b'{}')
        login = (req.get("login") or "").strip()
        senha = (req.get("senha") or "").strip()
```

- [ ] **Step 2: Verificar que do_POST lê body de forma segura**

Localizar início de `do_POST` (~linha 586–589):
```python
def do_POST(self):
    length = int(self.headers.get("Content-Length", 0))
    body   = self.rfile.read(length)
```

Alterar para:
```python
def do_POST(self):
    length = int(self.headers.get("Content-Length", 0))
    body   = self.rfile.read(length) if length else b'{}'
```

- [ ] **Step 3: Testar**

1. Abrir projeto com contrato gerado
2. Clicar "Voltar ao Orçamento"
3. Preencher login e senha de gerente
4. Verificar que retorna ao orçamento sem erro de rede

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "fix: json.loads dentro do try/except em desfazer_aprovacao + body seguro no do_POST"
```

---

## Task 3 — Fix: Máscara Moeda — "15000" em vez de "R$ 15.000,00"

**Problema:** `mascaraMoedaInput` usa lógica centavos-first: digitar "15000" vira "R$ 150,00" (trata todos os dígitos como centavos). O usuário quer digitar 15000 e ver "R$ 15.000,00".

**Arquivo:** `static/index.html` linha ~6236

- [ ] **Step 1: Reescrever mascaraMoedaInput**

Localizar `function mascaraMoedaInput(el) {` e substituir a função inteira por:

```js
function mascaraMoedaInput(el) {
  // Separa parte inteira e decimal no ponto de digitação da vírgula
  const raw = el.value.replace(/[^0-9,]/g, '');
  const partes = raw.split(',');
  let inteiro = partes[0].replace(/^0+/, '') || '0';
  // Adiciona separador de milhar
  inteiro = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  let resultado = 'R$ ' + inteiro;
  if (partes.length > 1) {
    resultado += ',' + partes[1].slice(0, 2);
  }
  const cursorFim = el.selectionStart === el.value.length;
  el.value = resultado;
  if (cursorFim) {
    el.setSelectionRange(resultado.length, resultado.length);
  }
}
```

- [ ] **Step 2: Verificar parseMoeda é compatível**

`parseMoeda` (linha ~6252) faz:
```js
const s = str.replace(/[R$\s]/g, '').replace(/\./g, '').replace(',', '.');
return parseFloat(s) || 0;
```

Para "R$ 15.000,00" → "15000.00" → 15000.0 ✓. Nenhuma mudança necessária.

- [ ] **Step 3: Verificar campo de entrada no modal de aprovação**

O campo `apr-entrada` (linha ~6489) tem `oninput="mascaraMoedaInput(this)"`. Ao abrir o modal, o valor inicial é setado como string formatada. Verificar que o valor inicial já está no formato "R$ X.XXX,XX":

```js
value="${pagAtual.entrada > 0 
  ? 'R$ ' + pagAtual.entrada.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}) 
  : ''}"
```

Se `pagAtual.entrada = 15000`, isso produz `"R$ 15.000,00"` ✓. Sem alteração necessária aqui.

- [ ] **Step 4: Testar**

1. Abrir modal de aprovação
2. No campo "Entrada", digitar "15000" → deve mostrar "R$ 15.000,00"
3. Digitar "15000,50" → deve mostrar "R$ 15.000,50"
4. Apagar tudo e digitar "0" → deve ficar "R$ 0"

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "fix: máscara moeda — formato reais inteiros (digitar 15000 → R\$ 15.000,00)"
```

---

## Task 4 — Fix: Valores Errados no Contrato + Salvar valor_liquido

**Problema:** `salvarValorNegociado()` salva `valor_total` (do `neg-total-final`) mas nunca salva `valor_liquido`. O contrato mostra `valor_liquido = R$ 0,00`. Também adicionar campo `valor_negociado` (alias claro do valor final pago pelo cliente).

**Arquivos:** `static/index.html` linha ~6358, `main.py` linha ~1928, `mod_contrato.py` linha ~54

- [ ] **Step 1: Capturar valor_liquido no salvarValorNegociado**

Localizar `async function salvarValorNegociado()` (linha ~6358):

```js
async function salvarValorNegociado() {
  if (!_orcamentoAtivoId) return;
  const elTotal = document.getElementById('neg-total-final');
  const elPag   = document.getElementById('neg-pagamento');
  const raw = (elTotal?.value || '').replace(/\./g,'').replace(',','.').replace(/[^\d.]/g,'');
  const valor = parseFloat(raw) || 0;
  if (!valor) return;
  try {
    await fetch(`/orcamentos/${_orcamentoAtivoId}/valor`, {
      method: 'PATCH', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ valor_total: valor, forma_pagamento: elPag?.value || null }),
    });
  } catch(e) { console.warn('salvarValorNegociado:', e); }
}
```

Substituir por (adiciona `valor_liquido` a partir de `neg-avista`):

```js
async function salvarValorNegociado() {
  if (!_orcamentoAtivoId) return;
  const elTotal   = document.getElementById('neg-total-final');
  const elAvista  = document.getElementById('neg-avista');
  const elPag     = document.getElementById('neg-pagamento');
  const rawTotal  = (elTotal?.value || '').replace(/\./g,'').replace(',','.').replace(/[^\d.]/g,'');
  const rawAvista = (elAvista?.textContent || '').replace(/[R$\s.]/g,'').replace(',','.');
  const valor        = parseFloat(rawTotal)  || 0;
  const valorLiquido = parseFloat(rawAvista) || 0;
  if (!valor) return;
  try {
    await fetch(`/orcamentos/${_orcamentoAtivoId}/valor`, {
      method: 'PATCH', credentials: 'same-origin',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        valor_total:     valor,
        valor_liquido:   valorLiquido,
        forma_pagamento: elPag?.value || null,
      }),
    });
  } catch(e) { console.warn('salvarValorNegociado:', e); }
}
```

- [ ] **Step 2: Aceitar valor_liquido na rota PATCH /orcamentos/<id>/valor**

Localizar rota em `main.py` linha ~1928–1952. Adicionar:

```python
if "valor_liquido" in req:
    orc.valor_liquido = float(req["valor_liquido"] or 0)
```

O bloco fica:
```python
if "valor_total" in req:
    orc.valor_total = float(req["valor_total"] or 0)
if "valor_liquido" in req:
    orc.valor_liquido = float(req["valor_liquido"] or 0)
if "forma_pagamento" in req:
    orc.forma_pagamento = req["forma_pagamento"] or None
```

- [ ] **Step 3: Adicionar valor_negociado como alias no contrato**

Em `montar_variaveis_contrato` (`mod_contrato.py` linha ~72), adicionar:

```python
"valor_negociado": _formatar_valor(orcamento.get("valor_total", 0.0)),  # alias claro
```

E atualizar o dict completo para incluir `cliente_email`:
```python
return {
    "cliente_nome":                   cliente.get("nome", ""),
    "cliente_cpf":                    cliente.get("cpf", ""),
    "cliente_email":                  cliente.get("email", ""),
    "cliente_telefone":               cliente.get("telefone", ""),
    "cliente_endereco_correspondencia": endereco_cliente,
    "cliente_endereco_instalacao":    endereco_instalacao or endereco_cliente,
    "projeto_nome":                   projeto.get("nome_projeto", ""),
    "projeto_data":                   projeto.get("criado_em", ""),
    "orcamento_nome":                 orcamento.get("nome", ""),
    "consultor_nome":                 projeto.get("consultor", ""),
    "data_contrato":                  datetime.now().strftime("%d/%m/%Y"),
    "valor_negociado":                _formatar_valor(orcamento.get("valor_total", 0.0)),
    "valor_total":                    _formatar_valor(orcamento.get("valor_total", 0.0)),
    "valor_liquido":                  _formatar_valor(orcamento.get("valor_liquido", 0.0)),
    "forma_pagamento":                orcamento.get("forma_pagamento", ""),
    "entrada_valor":                  _formatar_valor(entrada_valor),
    "parcelas_descricao":             parcelas_descricao or "",
    "ambientes_lista":                "\n".join(orcamento.get("ambientes", [])),
    "adendo":                         adendo or "",
    "pagamento_bloco":                "",  # preenchido em Task 7
}
```

- [ ] **Step 4: Atualizar assinatura de montar_variaveis_contrato**

A assinatura atual:
```python
def montar_variaveis_contrato(
    projeto: dict,
    cliente: dict,
    orcamento: dict,
    endereco_instalacao: str,
    entrada_valor: float,
    parcelas_descricao: str,
    adendo: str | None,
) -> dict:
```

Renomear `endereco_instalacao` para deixar explícito — sem quebrar chamadas (sem mudança na assinatura por ora, o campo interno é que muda o nome no dict).

- [ ] **Step 5: Passar email em _montar_dados_projeto_para_contrato**

Em `main.py` linha ~2140, `cliente_dict` já tem `telefone`. Adicionar `email`:

```python
cliente_dict = {
    "nome":       cliente.nome       if cliente else proj.get("nome_cliente", ""),
    "cpf":        cliente.cpf        if cliente else "",
    "email":      cliente.email      if cliente else "",
    "telefone":   cliente.telefone   if cliente else "",
    "logradouro": cliente.logradouro if cliente else "",
    "numero":     cliente.numero     if cliente else "",
    "bairro":     cliente.bairro     if cliente else "",
    "cidade":     cliente.cidade     if cliente else "",
    "estado":     cliente.estado     if cliente else "",
}
```

- [ ] **Step 6: Commit**

```bash
git add static/index.html main.py mod_contrato.py
git commit -m "fix: salvar valor_liquido na aprovação + email no contrato + valor_negociado como variável"
```

---

## Task 5 — UX Quick Fixes: Botão, Checkbox, Botão Avançar

**Arquivo:** `static/index.html`

- [ ] **Step 1: Renomear "Revisar / Regenerar" → "Revisar"**

Localizar (linha ~6163):
```js
<button onclick="fecharCiclo();abrirAprovacaoComDados()" class="btn-ciclo" style="font-size:.82rem">
  Revisar / Regenerar
</button>
```

Substituir:
```js
<button onclick="fecharCiclo();abrirAprovacaoComDados()" class="btn-ciclo" style="font-size:.82rem">
  Revisar
</button>
```

- [ ] **Step 2: Desabilitar checkbox após qualquer assinatura**

Localizar em `renderContratoUI` (linha ~6191):
```js
<input type="checkbox" id="chk-leu-contrato" onchange="toggleAssinaturas()"
  ${jaAssinou ? 'checked' : ''}>
```

Substituir por:
```js
<input type="checkbox" id="chk-leu-contrato" onchange="toggleAssinaturas()"
  ${jaAssinou ? 'checked disabled' : ''}>
```

- [ ] **Step 3: Adicionar botão "Avançar" quando contrato assinado**

Localizar em `renderContratoUI` (linha ~6187):
```js
${['assinado','vigente'].includes(status)
  ? `<p style="color:var(--ok);margin:0">&#x2713; Contrato assinado — ambas as partes confirmaram.</p>`
```

Substituir por:
```js
${['assinado','vigente'].includes(status)
  ? `<div>
      <p style="color:var(--ok);margin:0 0 14px">&#x2713; Contrato assinado — ambas as partes confirmaram.</p>
      <button onclick="fecharCiclo();toggleCicloCard('8')" class="btn-ciclo" style="font-size:.9rem">
        &#x27A1; Avan&ccedil;ar &mdash; Aprova&ccedil;&atilde;o Financeira I
      </button>
    </div>`
```

- [ ] **Step 4: Testar**

1. Abrir contrato em estado `para_assinatura` → verificar botão "Revisar" (não mais "Revisar / Regenerar")
2. Assinar o contrato → verificar que o checkbox fica disabled (não desmarcável)
3. Após assinado → verificar botão "Avançar — Aprovação Financeira I"
4. Clicar Avançar → deve fechar painel ciclo e abrir card da etapa 8

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "fix: botão Revisar, checkbox disabled após assinatura, botão Avançar pós-contrato"
```

---

## Task 6 — Feature: Forma de Pagamento da Entrada + Parcelas

**Objetivo:** Adicionar campos `forma_entrada` (como a entrada será paga) e `forma_parcelas` (como as parcelas serão pagas) no modal de aprovação. Esses dados vão para o contrato.

**Arquivo:** `static/index.html`

- [ ] **Step 1: Adicionar selects de forma de pagamento no modal**

Em `abrirModalAprovacaoOrcamento` (linha ~6432), dentro da div "Condição de Pagamento", APÓS o campo "Entrada (R$)", adicionar:

```js
<div style="margin-bottom:8px">
  <label style="font-size:.8rem;color:var(--muted);display:block;margin-bottom:3px">Forma de Pagamento da Entrada</label>
  <select id="apr-forma-entrada"
    style="width:100%;box-sizing:border-box;background:var(--input,#0d1a0d);border:1px solid var(--border);
    color:var(--fg);padding:7px;border-radius:4px;font-size:.88rem">
    <option value="pix">Pix</option>
    <option value="transferencia">Transferência Bancária</option>
    <option value="boleto">Boleto Bancário</option>
    <option value="cartao_credito">Cartão de Crédito</option>
    <option value="cartao_debito">Cartão de Débito</option>
    <option value="cheque">Cheque</option>
  </select>
</div>
<div>
  <label style="font-size:.8rem;color:var(--muted);display:block;margin-bottom:3px">Forma das Parcelas</label>
  <select id="apr-forma-parcelas"
    style="width:100%;box-sizing:border-box;background:var(--input,#0d1a0d);border:1px solid var(--border);
    color:var(--fg);padding:7px;border-radius:4px;font-size:.88rem">
    <option value="boleto">Boleto Bancário</option>
    <option value="debito_automatico">Débito Automático</option>
    <option value="transferencia">Transferência Bancária</option>
    <option value="cartao_credito">Cartão de Crédito</option>
    <option value="cheque">Cheque</option>
  </select>
</div>
```

- [ ] **Step 2: Capturar esses valores em gerarContrato()**

Em `gerarContrato()` (linha ~6543), após capturar `adendo`:

```js
const formaEntrada   = document.getElementById('apr-forma-entrada')?.value || 'pix';
const formaParcelas  = document.getElementById('apr-forma-parcelas')?.value || 'boleto';
```

E passar no body do POST:
```js
body: JSON.stringify({
    orcamento_id:        _orcamentoAtivoId,
    endereco_instalacao: endInstalacao,
    entrada_valor:       entrada,
    parcelas_descricao:  parcelas,
    forma_entrada:       formaEntrada,
    forma_parcelas:      formaParcelas,
    adendo:              adendo,
}),
```

- [ ] **Step 3: Aceitar no backend (main.py)**

Na rota `POST /api/projetos/<nome>/contrato` (linha ~1816), adicionar:

```python
forma_entrada   = req.get("forma_entrada", "pix")
forma_parcelas  = req.get("forma_parcelas", "boleto")
```

E passar para `montar_variaveis_contrato` (via kwargs ou expandindo o dict).

- [ ] **Step 4: Adicionar à assinatura de montar_variaveis_contrato**

Em `mod_contrato.py`, adicionar parâmetros e variáveis:

```python
def montar_variaveis_contrato(
    projeto, cliente, orcamento,
    endereco_instalacao, entrada_valor,
    parcelas_descricao, adendo,
    forma_entrada="pix", forma_parcelas="boleto",
) -> dict:
    # ... código existente ...
    FORMAS = {
        "pix": "Pix", "transferencia": "Transferência Bancária",
        "boleto": "Boleto Bancário", "cartao_credito": "Cartão de Crédito",
        "cartao_debito": "Cartão de Débito", "cheque": "Cheque",
        "debito_automatico": "Débito Automático",
    }
    return {
        # ... existentes ...
        "entrada_forma":   FORMAS.get(forma_entrada, forma_entrada),
        "parcelas_forma":  FORMAS.get(forma_parcelas, forma_parcelas),
    }
```

- [ ] **Step 5: Commit**

```bash
git add static/index.html main.py mod_contrato.py
git commit -m "feat: forma de pagamento da entrada e parcelas no modal de aprovação e contrato"
```

---

## Task 7 — Feature: Tabela Dinâmica de Pagamento no Contrato

**Objetivo:** Capturar o cronograma de parcelas do painel ativo (Aymoré, VP, Cartão, etc.) e gerar um bloco de pagamento estruturado para o contrato. Cartão: apenas texto. Demais: tabela com datas.

**Arquivo:** `static/index.html`, `mod_contrato.py`, `main.py`, `database.py`

- [ ] **Step 1: Adicionar campo pagamento_json em Contrato (database.py)**

Em `database.py`, classe `Contrato` (linha ~210):

```python
pagamento_json = Column(Text, nullable=True)   # JSON com cronograma de parcelas
```

- [ ] **Step 2: Criar função _capturarPagamento() no frontend**

Adicionar ANTES de `gerarContrato()` em `static/index.html`:

```js
function _capturarPagamento(formaEntrada, formaParcelas) {
  const ayAtivo = document.getElementById('painel-aymore')?.style.display !== 'none';
  const ccAtivo = document.getElementById('painel-cartao')?.style.display !== 'none';
  const vpAtivo = document.getElementById('painel-vp')?.style.display !== 'none';
  const tfAtivo = document.getElementById('painel-tf')?.style.display !== 'none';

  // Labels amigáveis para a forma de pagamento principal
  const nomesForma = {
    aymore: 'Financiamento Aymoré', cartao: 'Cartão de Crédito',
    vp: 'Venda Programada', tf: 'Total Flex', avista: 'À Vista / Boleto Loja',
  };

  const entrada = parseMoeda(document.getElementById('apr-entrada')?.value);
  const entradaData = (() => {
    if (ayAtivo) return document.getElementById('ay-data-contrato')?.value || '';
    if (vpAtivo) return document.getElementById('vp-data-contrato')?.value || '';
    if (tfAtivo) return document.getElementById('tf-data-contrato')?.value || '';
    return '';
  })();

  // Cartão: só texto, sem datas
  if (ccAtivo) {
    const ccParcelas = parseInt(document.getElementById('cc-parcelas')?.value || '1') || 1;
    const total      = parseMoeda(document.getElementById('neg-total-final')?.value);
    const valParcela = ccParcelas > 1 ? ((total - entrada) / ccParcelas) : 0;
    let texto = `R$ ${total.toLocaleString('pt-BR',{minimumFractionDigits:2})}`;
    if (entrada > 0)
      texto += ` — Entrada de R$ ${entrada.toLocaleString('pt-BR',{minimumFractionDigits:2})}`;
    if (ccParcelas > 1)
      texto += ` e ${ccParcelas}x R$ ${valParcela.toLocaleString('pt-BR',{minimumFractionDigits:2})}`;
    return { tipo: 'cartao', nome_forma: 'Cartão de Crédito', texto, parcelas: [] };
  }

  // Para todos os outros: capturar tabela de parcelas das linhas da tabela no DOM
  const tipo = ayAtivo ? 'aymore' : vpAtivo ? 'vp' : tfAtivo ? 'tf' : 'avista';
  const nomeForma = nomesForma[tipo];

  // Cada painel tem linhas de tabela — coletar datas e valores das células
  const painelId = { aymore: 'painel-aymore', vp: 'painel-vp', tf: 'painel-tf', avista: null }[tipo];
  const parcelas = [];
  if (painelId) {
    const tbody = document.querySelector(`#${painelId} tbody`);
    if (tbody) {
      tbody.querySelectorAll('tr').forEach((tr, i) => {
        const tds = tr.querySelectorAll('td');
        if (tds.length < 2) return;
        const desc   = (tds[0]?.textContent || '').trim();
        const data   = (tds[1]?.textContent || '').trim();
        const valor  = (tds[2]?.textContent || tds[1]?.textContent || '').trim();
        if (!desc || desc === 'Assinatura') return;
        parcelas.push({ seq: i + 1, descricao: desc, data, valor, forma: formaParcelas });
      });
    }
  }

  return { tipo, nome_forma: nomeForma, parcelas, texto: '' };
}
```

- [ ] **Step 3: Usar _capturarPagamento em gerarContrato()**

Em `gerarContrato()`, logo antes do `fetch POST /contrato`:

```js
const pagamento = _capturarPagamento(formaEntrada, formaParcelas);
// Adicionar dados da entrada ao objeto de pagamento
pagamento.entrada_valor = entrada;
pagamento.entrada_data  = (() => {
  const ayAtivo = document.getElementById('painel-aymore')?.style.display !== 'none';
  if (ayAtivo) return document.getElementById('ay-data-contrato')?.value || '';
  return '';
})();
pagamento.entrada_forma = formaEntrada;
```

E no body do POST, adicionar:
```js
pagamento_json: JSON.stringify(pagamento),
```

- [ ] **Step 4: Backend — receber e salvar pagamento_json**

Na rota `POST /api/projetos/<nome>/contrato` (main.py linha ~1816):

```python
pagamento_json_str = req.get("pagamento_json", "")
```

Após criar/atualizar o `contrato`:
```python
contrato.pagamento_json = pagamento_json_str
```

- [ ] **Step 5: Criar _formatar_bloco_pagamento em mod_contrato.py**

Adicionar função em `mod_contrato.py`:

```python
import json as _json

def _formatar_bloco_pagamento(pagamento_json_str: str, entrada_valor: float, forma_entrada: str) -> str:
    """
    Formata o bloco de pagamento para inserção no template.
    Cartão: texto livre. Demais: tabela ASCII simples.
    """
    if not pagamento_json_str:
        return ""
    try:
        pag = _json.loads(pagamento_json_str)
    except Exception:
        return pagamento_json_str  # fallback: usar como texto bruto

    tipo = pag.get("tipo", "")
    nome_forma = pag.get("nome_forma", "")
    parcelas = pag.get("parcelas", [])
    entrada_data = pag.get("entrada_data", "")
    entrada_forma_label = forma_entrada

    linhas = [f"Forma de Pagamento: {nome_forma}"]

    # Cartão — apenas texto
    if tipo == "cartao":
        texto = pag.get("texto", "")
        linhas.append(texto)
        return "\n".join(linhas)

    # Tabela para os demais tipos
    # Linha de entrada (sempre presente)
    ent_fmt = _formatar_valor(entrada_valor)
    ent_data_fmt = _formatar_data_br(entrada_data) if entrada_data else "—"
    linhas.append("")
    linhas.append(f"{'Seq':<5}{'Descrição':<22}{'Data':<14}{'Valor':<18}{'Forma'}")
    linhas.append("-" * 75)
    linhas.append(f"{'Ent':<5}{'Entrada':<22}{ent_data_fmt:<14}{ent_fmt:<18}{entrada_forma_label}")

    for p in parcelas:
        seq  = str(p.get("seq", ""))
        desc = p.get("descricao", "")[:20]
        data = _formatar_data_br(p.get("data", ""))
        val  = p.get("valor", "")
        forma = p.get("forma", "")
        linhas.append(f"{seq:<5}{desc:<22}{data:<14}{val:<18}{forma}")

    linhas.append("-" * 75)
    linhas.append(f"{'Total':<27}{'':<14}{_formatar_valor(sum(_parse_valor(p.get('valor','')) for p in parcelas) + entrada_valor)}")

    return "\n".join(linhas)


def _formatar_data_br(iso_date: str) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/AAAA'. Retorna o original se inválido."""
    if not iso_date or len(iso_date) < 10:
        return iso_date or "—"
    try:
        from datetime import datetime as _dt
        return _dt.strptime(iso_date[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def _parse_valor(val_str: str) -> float:
    """Converte 'R$ 4.820,00' para 4820.0."""
    if not val_str:
        return 0.0
    s = val_str.replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0
```

- [ ] **Step 6: Usar _formatar_bloco_pagamento em montar_variaveis_contrato**

Atualizar a assinatura de `montar_variaveis_contrato` para aceitar `pagamento_json` e `forma_entrada`:

```python
def montar_variaveis_contrato(
    projeto, cliente, orcamento,
    endereco_instalacao, entrada_valor,
    parcelas_descricao, adendo,
    forma_entrada="pix", forma_parcelas="boleto",
    pagamento_json="",
) -> dict:
    # ... código existente ...
    bloco_pag = _formatar_bloco_pagamento(pagamento_json, entrada_valor, FORMAS.get(forma_entrada, forma_entrada))
    return {
        # ... todas as variáveis existentes ...
        "pagamento_bloco": bloco_pag or parcelas_descricao,
    }
```

- [ ] **Step 7: Atualizar chamadas de montar_variaveis_contrato em main.py**

Há 2 chamadas em main.py (POST e PATCH /contrato). Atualizar ambas para passar:
```python
variaveis = montar_variaveis_contrato(
    projeto_dict, cliente_dict, orcamento_dict,
    endereco_instalacao=endereco_instalacao,
    entrada_valor=entrada_valor,
    parcelas_descricao=parcelas_descricao,
    adendo=adendo,
    forma_entrada=forma_entrada,
    forma_parcelas=forma_parcelas,
    pagamento_json=pagamento_json_str,
)
```

- [ ] **Step 8: Commit**

```bash
git add static/index.html main.py mod_contrato.py database.py
git commit -m "feat: captura cronograma de pagamento do painel ativo e gera bloco estruturado no contrato"
```

---

## Task 8 — Feature: Etapa 8 — Aprovação Financeira I com Botão de Ação

**Problema:** `_renderCardGenerico` apenas exibe "Nenhuma informação registrada." para todas as etapas não-especiais. A etapa 8 (Aprovação Financeira I) precisa de um botão para marcar como aprovada.

**Arquivo:** `static/index.html`

- [ ] **Step 1: Adicionar lógica de render para etapa 8 em renderCiclo()**

Localizar em `renderCiclo()` (linha ~6045):
```js
${etapa.acao === 'contrato' ? _renderCardContrato() : _renderCardGenerico(etapa, dados)}
```

Substituir por:
```js
${etapa.acao === 'contrato'
  ? _renderCardContrato()
  : etapa.codigo === '8'
    ? _renderCardAprovacaoFinanceira(dados)
    : _renderCardGenerico(etapa, dados)}
```

- [ ] **Step 2: Criar _renderCardAprovacaoFinanceira()**

Adicionar APÓS `_renderCardGenerico`:

```js
function _renderCardAprovacaoFinanceira(dados) {
  const concluido = dados.status === 'concluido';
  if (concluido) {
    const dt = dados.concluido_em ? new Date(dados.concluido_em).toLocaleDateString('pt-BR') : '';
    return `
      <p style="color:var(--ok);margin:0 0 10px">&#x2713; Aprovação financeira concluída${dt ? ' em ' + dt : ''}.</p>
      <button onclick="toggleCicloEtapa('8')"
        style="background:none;border:1px solid var(--muted);color:var(--muted);
        border-radius:5px;padding:4px 12px;font-size:.8rem;cursor:pointer">
        Reabrir
      </button>`;
  }
  return `
    <p style="color:var(--muted);font-size:.85rem;margin:0 0 14px">
      Confirme que a análise de crédito ou aprovação interna foi concluída.
    </p>
    <button onclick="concluirAprovacaoFinanceira()"
      style="background:#b8960c;color:#000;border:none;border-radius:6px;
      padding:8px 18px;font-size:.9rem;font-weight:700;cursor:pointer">
      &#x2713; Marcar Aprovação Financeira como Concluída
    </button>`;
}

async function concluirAprovacaoFinanceira() {
  try {
    const r = await fetch(
      `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/8`,
      {
        method: 'PATCH', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ status: 'concluido' }),
      }
    );
    const d = await r.json();
    if (!d.ok) { showToast('Erro: ' + (d.erro || 'falha'), true); return; }
    showToast('Aprovação Financeira I concluída!', false);
    await carregarCiclo();
  } catch(e) { showToast('Erro de rede: ' + e.message, true); }
}
```

- [ ] **Step 3: Testar**

1. Assinar contrato → clicar "Avançar"
2. Card 8 deve mostrar botão "Marcar Aprovação Financeira como Concluída"
3. Clicar → etapa 8 deve ficar verde com ✓
4. Botão "Reabrir" deve desfazer

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: card de Aprovação Financeira I (etapa 8) com botão de confirmação"
```

---

## Task 9 — Feature: Adendo como Anexo Assinado no Contrato

**Objetivo:** O adendo deve aparecer no contrato como uma seção separada com suas próprias linhas de assinatura (cliente e loja). No template, isso é controlado via variáveis `{{ adendo }}` (conteúdo) e `{{ tem_adendo }}` (flag booleana).

**Arquivos:** `mod_contrato.py`, `scripts/configurar_template_contrato.py`

- [ ] **Step 1: Adicionar flag tem_adendo em montar_variaveis_contrato**

Em `mod_contrato.py`, no return dict de `montar_variaveis_contrato`:

```python
"tem_adendo":  bool(adendo),
"adendo":      adendo or "",
```

- [ ] **Step 2: Atualizar configurar_template_contrato.py com novos placeholders**

Abrir `scripts/configurar_template_contrato.py`. Adicionar ao dict de substituições:

```python
substituicoes = {
    # Existentes (preservar)
    "NOME DO CLIENTE":          "{{ cliente_nome }}",
    "CPF DO CLIENTE":           "{{ cliente_cpf }}",
    # Novos
    "EMAIL DO CLIENTE":         "{{ cliente_email }}",
    "TELEFONE DO CLIENTE":      "{{ cliente_telefone }}",
    "ENDEREÇO DE CORRESPONDÊNCIA": "{{ cliente_endereco_correspondencia }}",
    "ENDEREÇO DE INSTALAÇÃO":   "{{ cliente_endereco_instalacao }}",
    "VALOR NEGOCIADO":          "{{ valor_negociado }}",
    "BLOCO DE PAGAMENTO":       "{{ pagamento_bloco }}",
    "FORMA DA ENTRADA":         "{{ entrada_forma }}",
    "FORMA DAS PARCELAS":       "{{ parcelas_forma }}",
    "CONTEÚDO DO ADENDO":       "{{ adendo }}",
}
```

- [ ] **Step 3: Orientar o usuário sobre o template**

O template Word (`Modelo de Contrato.docx`) precisa ter uma seção de adendo com assinaturas. Como essa seção existe no documento Word do usuário, adicionar ao final de `gerar_pdf_contrato` uma verificação de que `tem_adendo` está no dict de variáveis passado ao DocxTemplate, e docxtpl renderizará `{% if tem_adendo %}...{% endif %}` naturalmente.

Garantir que o template Word tenha (editado pelo usuário ou via script):
```
{% if tem_adendo %}
ADENDO
{{ adendo }}

Assinatura do Cliente: _________________________   Data: ___/___/______
Assinatura Empresa:    _________________________   Data: ___/___/______
{% endif %}
```

- [ ] **Step 4: Documentar no DEV_LOG**

Anotar que o usuário precisa atualizar `Modelo de Contrato.docx` adicionando as novas variáveis e a seção de adendo com `{% if tem_adendo %}...{% endif %}`.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py scripts/configurar_template_contrato.py
git commit -m "feat: tem_adendo flag + email/endereços separados + novas variáveis no configurador de template"
```

---

## Self-Review

### Cobertura do spec

| Requisito do usuário | Task |
|---|---|
| Dados do cliente no cabeçalho (endereços, telefone, email) | Task 4 (variáveis) + Task 9 (template) |
| Forma de pagamento abaixo dos dados | Task 7 (pagamento_bloco) |
| Tabela dinâmica (Aymoré, boleto, VP, à vista) | Task 7 |
| Cartão: só texto sem datas | Task 7 |
| Forma de pag. da entrada | Task 6 |
| Coluna total → linha de consolidação | Task 7 (linha Total no bloco) |
| Valores errados no contrato | Task 4 |
| Trocar projeto abre contrato errado | Task 1 |
| "Voltar ao Orçamento" erro JSON | Task 2 |
| Botão "Revisar" (não "Revisar / Regenerar") | Task 5 |
| Adendo como anexo assinado | Task 9 |
| Máscara moeda (15000 → R$ 15.000,00) | Task 3 |
| Botão Avançar após assinar | Task 5 |
| Aprovação Financeira I sem modal | Task 8 |
| Checkbox desabilitado após assinar | Task 5 |

### Checklist de placeholders

- Sem TBDs ou TODOs nas tasks
- Todos os snippets de código são completos
- Tipos consistentes: `forma_entrada` como string sempre, `pagamento_json` como string JSON
- `_formatar_bloco_pagamento` usa `_parse_valor` e `_formatar_data_br` definidos na mesma task

### Consistência de tipos

- `montar_variaveis_contrato` aceita `pagamento_json=""` (string, não dict)
- `_capturarPagamento()` retorna dict → `JSON.stringify()` antes de enviar
- `pagamento_json_str` no backend é string → passa direto para `montar_variaveis_contrato`
- `_formatar_bloco_pagamento` faz `_json.loads(pagamento_json_str)` internamente

---

## Notas de Implementação

**Ordem recomendada:** Tasks 1 → 2 → 3 → 5 → 4 → 6 → 7 → 8 → 9

**Tasks independentes que podem ser paralelizadas:**
- Task 1 (state reset) e Task 3 (mask) e Task 5 (UX) são frontend puro e independentes
- Task 2 (backend JSON) é backend puro e independente

**Template Word:** As Tasks 4, 7 e 9 adicionam novas variáveis ao template. O usuário precisa **editar o `Modelo de Contrato.docx`** adicionando os novos placeholders nos locais corretos e re-executar `python scripts/configurar_template_contrato.py`. Um template default atualizado pode ser gerado automaticamente pela script se o usuário não tiver um.
