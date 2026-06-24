# Tela de Negociação — Fonte Única do Total e Colunas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O motor (backend) vira a fonte única dos números da tabela por ambiente: desconto robusto, duas colunas (à vista e financiada) e o Total de contrato sem corrida entre escritores.

**Architecture:** `renderTabelaNeg` lê o desconto do dado do ambiente; `_aplicarPreviewNaTela` é o único escritor das células (à vista=`VAVA`, financiada=`VAVA×Val_Cont/VAVO`) e do Total (`Val_Cont`). O fluxo de pagamento deixa de escrever células/Total; ao trocar a modalidade, **auto-salva** `forma_pagamento` → o motor recalcula `Val_Cont` → exibe.

**Tech Stack:** Frontend HTML/JS vanilla em `static/index.html`. Sem harness JS → validação MANUAL no browser. Backend já provê `VAVA`/`Val_Cont`/`VAVO` no breakdown; pytest deve seguir 301 verde.

## Global Constraints

- **Único escritor:** `_aplicarPreviewNaTela` é o único que escreve as células de valor (`data-ep07-id`), o Total (`neg-total`/`neg-total-final`) e os totais de coluna. O fluxo de pagamento NÃO escreve esses campos.
- **Colunas:** à vista = `a.VAVA`; financiada = `a.VAVA × (Val_Cont/VAVO)` (se `VAVO=0` → financiada = à vista). Soma da financiada = `Val_Cont`.
- **Total = `Val_Cont`** (financiado, do motor). À vista total = `VAVO`.
- **Auto-save do pagamento:** ao recalcular o plano (`atualizar{Aymore,Cartao,VP,TF}`), dispara `salvarValorNegociado` (debounced) → `aplicarBreakdownResposta` (motor reflete o `total_cliente` salvo em `Val_Cont`).
- **Não-destrutivo no backend** (sem mudança prevista). `git add` só `static/index.html` por task.

---

### Task 1: §1 — Desconto por ambiente robusto

**Files:**
- Modify: `static/index.html` (`renderTabelaNeg` EP-07, ~linha 4786)

> Sem teste automatizado → validação manual.

- [ ] **Step 1: Ler o desconto do dado do ambiente**

No ramo EP-07 de `renderTabelaNeg`, onde hoje é `const disc_i = parseFloat(_descIndividual['ep07_'+pa.id])||0;`, trocar por:

```javascript
      const _dk = 'ep07_'+pa.id;
      const disc_i = (_dk in _descIndividual) ? (parseFloat(_descIndividual[_dk])||0)
                                              : (parseFloat(pa.desconto_individual_pct)||0);
```

(`_descIndividual` só como override de edição em andamento; o valor salvo vem de `pa.desconto_individual_pct`, que o fetch `/orcamentos/<id>/ambientes` já devolve.)

- [ ] **Step 2: Validação manual + commit**

Run: `python3 main.py` → hard refresh. Entrar num orçamento com desconto por ambiente salvo → o input mostra o valor **na 1ª entrada** (sem sair e voltar).

```bash
git add static/index.html
git commit -m "fix(negociacao): desconto por ambiente le do dado do ambiente (robusto a timing)"
```

---

### Task 2: §2 — Duas colunas por ambiente (à vista e financiada), do motor

**Files:**
- Modify: `static/index.html` (thead ~797-800; tfoot ~805-808; `renderTabelaNeg` EP-07 célula de valor ~4806; `_aplicarPreviewNaTela` ~5639; retirar a distribuição de células de `_ep07DistribuirFinanciado` ~4626)

- [ ] **Step 1: Cabeçalho — duas colunas de valor**

No `<thead>` da tabela de negociação, trocar a `<th>Valor</th>` única por duas:

```html
          <th style="text-align:right;width:130px">À vista</th>
          <th style="text-align:right;width:130px">Com financiamento</th>
```

- [ ] **Step 2: tfoot — total à vista + total financiado**

No `<tfoot>`, trocar a linha do Total (hoje `colspan=3` + `neg-total`) por:

```html
          <tr style="border-top:2px solid var(--border2)">
            <td colspan="3" style="padding:12px 14px;font-family:'Epilogue',sans-serif;font-weight:700;font-size:13px">Total</td>
            <td id="neg-total-avista" style="padding:12px 14px;text-align:right;font-family:'Epilogue',sans-serif;font-weight:700;font-size:14px;color:var(--muted);white-space:nowrap">—</td>
            <td id="neg-total" style="padding:12px 14px;text-align:right;font-family:'Epilogue',sans-serif;font-weight:900;font-size:18px;color:var(--ok);white-space:nowrap">—</td>
          </tr>
```

(A célula vazia "Nenhum ambiente selecionado" do tbody deve ficar `colspan="5"` — ajustar onde aparecer.)

- [ ] **Step 3: `renderTabelaNeg` monta as duas `<td>` de valor**

No ramo EP-07, substituir a `<td data-ep07-avista=... data-ep07-id=...>R$ ${fmt(final_)}</td>` por DUAS células (placeholder; o motor preenche):

```javascript
        <td data-ep07-id="${pa.id}" data-col="avista" style="text-align:right;padding:10px 14px;border-bottom:1px solid var(--border);font-weight:700;color:var(--muted)">R$ —</td>
        <td data-ep07-id="${pa.id}" data-col="fin" style="text-align:right;padding:10px 14px;border-bottom:1px solid var(--border);font-weight:700;color:var(--ok)">R$ —</td>
```

(Remover o atributo `data-ep07-avista` e o cálculo legado `final_`/`avista`/`bruto` que só servia para essa célula, se não for mais usado no EP-07.)

- [ ] **Step 4: `_aplicarPreviewNaTela` preenche as duas colunas + total à vista**

Substituir o bloco de células por ambiente por (usando `VAVO`/`Val_Cont` do breakdown para o fator financeiro):

```javascript
  // ── células por ambiente: à vista (VAVA) e financiada (VAVA × Val_Cont/VAVO) ──
  const _vavo = Number(s.VAVO) || 0;
  const _fin_factor = _vavo > 0 ? ((Number(s.Val_Cont) || _vavo) / _vavo) : 1;
  if (Array.isArray(s.ambientes)) {
    s.ambientes.forEach(a => {
      if (a.id == null) return;
      const vava = Number(a.VAVA) || 0;
      const cAv = document.querySelector('[data-ep07-id="' + a.id + '"][data-col="avista"]');
      const cFn = document.querySelector('[data-ep07-id="' + a.id + '"][data-col="fin"]');
      if (cAv) cAv.textContent = 'R$ ' + fmt(vava);
      if (cFn) cFn.textContent = 'R$ ' + fmt(Math.round(vava * _fin_factor * 100) / 100);
    });
  }
  const _elTAv = id('neg-total-avista');
  if (_elTAv) _elTAv.textContent = 'R$ ' + fmt(_vavo);   // total à vista (VAVO)
```

- [ ] **Step 5: Aposentar a distribuição de células do `_ep07DistribuirFinanciado`**

Em `_ep07DistribuirFinanciado`, remover o loop que escreve `#neg-tbody td[data-ep07-avista]` (as células agora vêm do motor). Manter por ora as escritas de `neg-total`/`neg-total-final` (serão tratadas na Task 3) — OU, se preferir, deixar a função vazia/no-op e tratar tudo na Task 3. (Confirme via Read o corpo atual.)

- [ ] **Step 6: Validação manual + commit**

Run: `python3 main.py` → hard refresh. A tabela mostra **duas colunas** (à vista × com financiamento) por ambiente; a soma da coluna financiada bate com o Total.

```bash
git add static/index.html
git commit -m "feat(negociacao): duas colunas por ambiente (a vista e financiada) do motor"
```

---

### Task 3: §3 — Total único (motor) + auto-save do pagamento

**Files:**
- Modify: `static/index.html` (`_aplicarPreviewNaTela` Total ~5636; remover writes de `neg-total`/`neg-total-final` do fluxo de pagamento: `atualizar*` ~3613/3726/3893/4427 e `_ep07DistribuirFinanciado` ~4630/4632; auto-save nos `atualizar*`)

- [ ] **Step 1: O motor é o único a escrever o Total**

Garantir que `_aplicarPreviewNaTela` escreve `neg-total` (textContent) e `neg-total-final` (value, com guard `_editando`) = `s.Val_Cont`. (Já faz `neg-total`/`neg-total-final` no código atual — confirmar; se faltar `neg-total`, acrescentar `setR('neg-total', s.Val_Cont)`.)

- [ ] **Step 2: Remover as escritas de Total do fluxo de pagamento**

Remover/neutralizar as linhas que escrevem `neg-total-final` nos `atualizar*` (`const elTot = document.getElementById('neg-total-final'); if (elTot && !elTot._editando) elTot.value = fmt(d.total_cliente);` em ~3613, ~3726, ~3893, ~4427) e as escritas de `neg-total`/`neg-total-final` em `_ep07DistribuirFinanciado` (~4630, ~4632). O Total passa a vir só do motor.

- [ ] **Step 3: Auto-save do pagamento (torna o Val_Cont vivo)**

Adicionar um helper debounced e chamá-lo ao fim de cada `atualizar{Aymore,Cartao,VP,TF}` (após setar `window._planoPagamento`):

```javascript
let _pagSalvarTimer = null;
function agendarSalvarPagamento(){
  clearTimeout(_pagSalvarTimer);
  _pagSalvarTimer = setTimeout(async () => {
    const sv = await salvarValorNegociado();
    // salvarValorNegociado persiste forma_pagamento; recarrega o breakdown (Val_Cont vivo)
    if (sv && sv.ok) { try { await negPreview(); } catch(e){} }
  }, 500);
}
```

(`salvarValorNegociado` hoje retorna `{ok}` sem o breakdown; por isso chamamos `negPreview()` depois para o motor reexibir o Total/coluna financiada com o `Val_Cont` recém-salvo. Em cada `atualizar*`, após `window._planoPagamento = {...}`, acrescentar `agendarSalvarPagamento();`.)

- [ ] **Step 4: Validação manual + commit**

Run: `python3 main.py` → hard refresh. Trocar a modalidade de pagamento várias vezes → o **Total** e a **coluna financiada** atualizam de forma **estável** (sem "às vezes certo, às vezes errado"); à vista (sem financiamento) → Total = total à vista. `python3 -m pytest -q` → 301 verde.

```bash
git add static/index.html
git commit -m "feat(negociacao): Total de contrato fonte unica (motor); auto-save do pagamento"
```

---

## Self-Review (autor)

**Cobertura do spec:**
- §1 desconto robusto → Task 1. ✔
- §2 duas colunas do motor + aposentar distribuição de células → Task 2. ✔
- §3 Total único (motor) + remover writes do pagamento + auto-save → Task 3. ✔
- §4 testes (backend 301; manual frontend) → passos de validação. ✔

**Consistência de nomes:** `data-ep07-id`+`data-col` (avista/fin), `neg-total`/`neg-total-final`/`neg-total-avista`, `_fin_factor = Val_Cont/VAVO`, `agendarSalvarPagamento`, `aplicarBreakdownResposta`/`negPreview` — usados igual entre as tasks.

**Observações:** Tudo frontend sem teste automatizado (sem harness JS) → validação manual pelo usuário; a lógica de cálculo por trás (VAVA/Val_Cont/VAVO) é do motor, já coberta. Task 2 retira a distribuição de células do `_ep07DistribuirFinanciado`; Task 3 retira as escritas de Total dele e dos `atualizar*` — verificar via Read o corpo atual antes de cada remoção (arquivo grande, linhas deslocam).
