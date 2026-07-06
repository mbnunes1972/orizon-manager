# Faxina Fase 1 — Frontend Single-Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O motor (backend) vira a única fonte de todos os números de negociação; o frontend só edita (auto-save) e exibe a saída do motor, com `_aplicarPreviewNaTela` como único escritor.

**Architecture:** O backend lê os insumos salvos (`parametros_json`, `orc.desconto_pct`, descontos por ambiente, `forma_pagamento`) e o motor calcula tudo. Os endpoints de save recalculam e devolvem o breakdown no shape do motor. O frontend apaga todo cálculo/estado/sincronização legada e apenas aplica o breakdown vindo das respostas.

**Tech Stack:** Python 3 (stdlib http.server, SQLAlchemy/sqlite), frontend HTML/JS vanilla em `static/index.html`, pytest. No WSL é `python3` (não `python`).

## Global Constraints

- **Backend é a fonte única:** o frontend NÃO calcula nem empacota params. `_negociacao_breakdown` lê SÓ dos salvos (sem overrides do frontend).
- **Shape do breakdown (siglas MAIÚSCULAS do motor), idêntico no preview e nas respostas de save:** `{ VBVO, CFO, VBNO, VAVO, Com_Arq, Pro_Fid, Cust_Via, Bri, Cust_Ad, Val_Liq, Desc_Tot, Markup, Cust_Fin, Val_Cont, Prov_Imp, ambientes:[{id, VBVA, CFA, VBNA, VAVA}] }`. NÃO usar `_sombra_dict` (minúsculo) nas respostas consumidas pelo frontend.
- **`_aplicarPreviewNaTela(s)` é o ÚNICO escritor** dos campos `mp-a-*`, `neg-*` e células por ambiente.
- **Desconto: input único** (`neg-desconto` + por ambiente, na tela). No modal é read-only.
- **Não-destrutivo em schema:** nenhuma coluna/JSON removida nesta fase (Fase 2 cuida disso). `mod_fin` reusado como está.
- **Persistência autoritativa intacta:** `_recalcular_orcamento` continua gravando `valor_total=Val_Cont`/`valor_liquido=Val_Liq`. Contrato assinado segue bloqueado.
- `python3 -m pytest`. Commits por task. `git add` só dos arquivos da task. Sem harness JS → frontend é validação manual.

---

### Task 1: Motor devolve Cust_Via e Bri

**Files:**
- Modify: `mod_negociacao.py` (dict de retorno, ~linha 75-82)
- Test: `tests/test_negociacao.py`

**Interfaces:**
- Produces: `calcular_orcamento(...)` retorna também `"Cust_Via"` (viagem total = `cust_via if tog_cvia else 0`) e `"Bri"` (brinde total = `bri if tog_bri else 0`).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_negociacao.py
def test_retorna_cust_via_e_bri():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 300,
         "brinde_ativo": True, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 300.0
    assert d["Bri"] == 200.0
    # cadeia fecha: VAVO − Com_Arq − Pro_Fid − Cust_Via − Bri == Val_Liq
    assert abs((d["VAVO"] - d["Com_Arq"] - d["Pro_Fid"] - d["Cust_Via"] - d["Bri"]) - d["Val_Liq"]) < 0.05

def test_cust_via_bri_zerados_quando_toggle_off():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": False, "custo_viagem": 300,
         "brinde_ativo": False, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 0.0 and d["Bri"] == 0.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao.py::test_retorna_cust_via_e_bri -v`
Expected: FAIL (KeyError 'Cust_Via').

- [ ] **Step 3: Implementar**

Em `mod_negociacao.py`, no dict de retorno, acrescentar as duas chaves (logo após `Cust_Ad`):

```python
        "Cust_Via": round(cust_via if tog_cvia else 0.0, 2),
        "Bri": round(bri if tog_bri else 0.0, 2),
```

- [ ] **Step 4: Rodar e ver passar + suíte do motor**

Run: `python3 -m pytest tests/test_negociacao.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_negociacao.py tests/test_negociacao.py
git commit -m "feat(motor): retorna Cust_Via e Bri (viagem/brinde totais)"
```

---

### Task 2: `_negociacao_breakdown` lê só dos salvos; preview sem corpo

**Files:**
- Modify: `main.py` (`_negociacao_breakdown` ~4220; `_recalcular_orcamento` ~4248; handler `negociacao-preview`)
- Test: `tests/test_cutover_e2e.py`

**Interfaces:**
- Consumes: `mod_negociacao.calcular_orcamento`.
- Produces: `_negociacao_breakdown(orc, db) -> dict` — lê tudo do banco (parametros_json, orc.desconto_pct, OrcamentoAmbiente.desconto_individual_pct, orc.forma_pagamento.total_cliente). Sem parâmetros de override. Retorna o dict do motor (com `id` por ambiente).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_cutover_e2e.py
def test_preview_ignora_overrides_do_corpo(http_client_factory, seed, app_db):
    """O preview lê só dos salvos: enviar params/desc_orc no corpo NÃO altera o resultado."""
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    pj = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="A", nome_exibicao="A", xml_path="a.xml",
                             ambientes_json="{}", projeto_id=pj, budget_total=10000.0, order_total=4000.0)
    db.add(pa); db.flush(); db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pa.id, ordem=1))
    db.commit(); db.close()
    c = _login(http_client_factory, "dir_l1")
    st, base = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    st2, comov = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {"desc_orc": 50, "params": {"comissao_arq_ativa": True, "comissao_arq_pct": 99}})
    assert st == 200 and st2 == 200
    assert base["sombra"]["VAVO"] == comov["sombra"]["VAVO"]   # overrides ignorados
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cutover_e2e.py::test_preview_ignora_overrides_do_corpo -v`
Expected: FAIL (hoje os overrides do corpo mudam o resultado).

- [ ] **Step 3: Reescrever `_negociacao_breakdown` para ler só dos salvos**

Substituir a assinatura/corpo por (lê total_cliente do próprio orçamento):

```python
def _negociacao_breakdown(orc, db):
    """Calcula a cadeia do motor lendo SÓ os insumos salvos (parametros_json, desconto do
    orçamento, descontos por ambiente, forma_pagamento). Sem overrides do frontend. NÃO grava."""
    import mod_negociacao
    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
    params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
    desc_orc = orc.desconto_pct or 0.0
    ambs, ids = [], []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                         "desc_amb_pct": float(lk.desconto_individual_pct or 0.0)})
            ids.append(lk.pool_ambiente_id)
    total_cliente = None
    try:
        fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else None
        if isinstance(fp, dict) and fp.get("total_cliente"):
            total_cliente = float(fp["total_cliente"])
    except Exception:
        total_cliente = None
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc)
    cust_fin = 0.0 if total_cliente is None else max(0.0, total_cliente - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin)
    for i, amb in enumerate(d.get("ambientes", [])):
        amb["id"] = ids[i] if i < len(ids) else None
    return d
```

- [ ] **Step 4: Ajustar os chamadores**

`_recalcular_orcamento`: trocar a chamada que passava `total_cliente=...` por `d = _negociacao_breakdown(orc, db)` (remover a leitura de total_cliente de lá — agora é interna ao breakdown). Manter as gravações (`orc.vbvo=...`, `valor_total=Val_Cont`, etc.).

Handler `negociacao-preview`: trocar a montagem com `req.get("params")/desc_orc/descontos_amb` por `d = _negociacao_breakdown(orc, db)` (ignora o corpo).

- [ ] **Step 5: Rodar e ver passar + suíte inteira**

Run: `python3 -m pytest tests/test_cutover_e2e.py -q && python3 -m pytest -q`
Expected: PASS (288+). Se algum teste antigo dependia de override, ajustar para o novo comportamento (saved-only) e descrever no relatório.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cutover_e2e.py
git commit -m "refactor(cutover): breakdown le so dos salvos; preview sem overrides"
```

---

### Task 3: Saves recalculam e devolvem o breakdown (shape do motor)

**Files:**
- Modify: `main.py` (`POST /api/orcamentos/<id>/margens` ~1987; `PUT /api/orcamentos/<id>/descontos` ~3547; `PUT/POST /api/projetos/<n>/parametros` ~1919)
- Test: `tests/test_cutover_e2e.py`

**Interfaces:**
- Consumes: `_recalcular_orcamento(orc, db)`, `_negociacao_breakdown(orc, db)` (Task 2).
- Produces: cada endpoint de save devolve `{"ok": True, "sombra": <breakdown maiúsculo>}` (mesmo shape do preview).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_cutover_e2e.py
def _seed_amb(app_db, oid, budget=10000.0):
    db = app_db.get_session()
    pj = db.get(app_db.Orcamento, oid).projeto_id
    pa = app_db.PoolAmbiente(nome="Z", nome_exibicao="Z", xml_path="z.xml", ambientes_json="{}",
                             projeto_id=pj, budget_total=budget, order_total=budget*0.4)
    db.add(pa); db.flush(); pid = pa.id
    db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close(); return pid

def test_save_margens_retorna_breakdown_maiusculo(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]; _seed_amb(app_db, oid)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200
    s = body["sombra"]
    for k in ("VBNO", "VAVO", "Cust_Via", "Bri", "Val_Liq", "ambientes"):
        assert k in s, f"falta {k} no breakdown: {list(s)}"
    assert s["ambientes"][0]["id"] is not None

def test_save_descontos_retorna_breakdown(http_client_factory, seed, app_db):
    oid = seed["orcamento_l1_id"]; pid = _seed_amb(app_db, oid)
    c = _login(http_client_factory, "dir_l1")
    st, body = c.put(f"/api/orcamentos/{oid}/descontos", {"descontos": {str(pid): 5}})
    assert st == 200 and "VAVO" in body["sombra"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cutover_e2e.py -k "breakdown" -v`
Expected: FAIL (margens devolve `_sombra_dict` minúsculo; `/descontos` não devolve sombra).

- [ ] **Step 3: Converger `/margens` para o breakdown maiúsculo**

No handler de `/margens`, após `_recalcular_orcamento(orc, db); db.commit()`, trocar a resposta:

```python
                self.send_json({"ok": True, "margens": atual,
                                "sombra": _negociacao_breakdown(orc, db)})
```

- [ ] **Step 4: `/descontos` recalcula e devolve o breakdown**

No handler `PUT /api/orcamentos/<id>/descontos`, após persistir os descontos por ambiente e `db.commit()`, acrescentar:

```python
                    try:
                        _recalcular_orcamento(orc, db); db.commit()
                        self.send_json({"ok": True, "sombra": _negociacao_breakdown(orc, db)})
                    except Exception as _e:
                        db.rollback()
                        self.send_json({"ok": True, "sombra": None, "erro_sombra": str(_e)})
                    return
```

(Confirme via Read o nome da variável do orçamento no handler — `orc` — e a posição exata do commit.)

- [ ] **Step 5: `/parametros` recalcula os orçamentos do projeto e devolve o breakdown do ativo**

No handler de `/parametros`, após salvar `parametros_json`, recalcular os orçamentos do projeto (os params são do projeto) e devolver o breakdown. Mínimo viável: recalcular todos os orçamentos do projeto e devolver o do primeiro (o frontend re-aplica ao ativo):

```python
                    proj_orcs = db.query(Orcamento).filter_by(projeto_id=<nome_safe>).all()
                    for o in proj_orcs:
                        try: _recalcular_orcamento(o, db)
                        except Exception as _e: print("[FAXINA] recalc parametros:", _e)
                    db.commit()
                    brk = _negociacao_breakdown(proj_orcs[0], db) if proj_orcs else None
                    self.send_json({"ok": True, "sombra": brk})
```

(Use o `nome_safe` real capturado no handler; preserve o resto da resposta existente se houver campos extras esperados pelo frontend.)

- [ ] **Step 6: Rodar e ver passar + suíte**

Run: `python3 -m pytest tests/test_cutover_e2e.py -q && python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_cutover_e2e.py
git commit -m "feat(faxina): saves recalculam e devolvem o breakdown do motor (shape maiusculo)"
```

---

### Task 4: Frontend — verificar path não-EP07 e mapear remoções

**Files:**
- Inspecionar: `static/index.html`

> Task de investigação (sem commit de código). Produz a decisão para as Tasks 5-6.

- [ ] **Step 1: Verificar se o path legado não-EP07 ainda é exercido**

Run: `grep -n "_negBaseValues\|PATH LEGADO\|projetoAtivo.ambientes" static/index.html | head -30`
Determinar: o fluxo atual sempre usa orçamento (EP-07) e `_orcamentoAtivoId`? Se os projetos sempre têm orçamento (EP-07), o path legado (renderTabelaNeg/executarCalculo não-EP07, `_negBaseValues`) é morto e pode ser removido nas Tasks 5-6. Se ainda houver projeto sem orçamento, preservar esse ramo isolado.

- [ ] **Step 2: Registrar a decisão**

Anotar no relatório da task: lista exata de funções a APAGAR vs a MANTER (com nº de linha), conforme a verificação. Sem alteração de código.

---

### Task 5: Frontend — `_aplicarPreviewNaTela` único escritor + consumir respostas dos saves

**Files:**
- Modify: `static/index.html`

> Refactor de UI delicado, sem teste automatizado → validação MANUAL no browser (passo final). Edições cirúrgicas; use Read para localizar cada ponto.

- [ ] **Step 1: `_aplicarPreviewNaTela` exibe viagem/brinde do motor**

Em `_aplicarPreviewNaTela(s)`, trocar os ecos de input por valores do motor:
`mp-a-viagem` ← `s.Cust_Via` (`'− R$ '` se > 0, senão `'R$ 0,00'`); `mp-a-brinde` ← `s.Bri` (idem). Manter os demais campos já vindos do motor (VBNO/VAVO/Com_Arq/Pro_Fid/Val_Liq/Desc_Tot, desconto=VBNO−VAVO, neg-*, células por ambiente).

- [ ] **Step 2: Helper para aplicar o breakdown das respostas de save**

Adicionar:

```javascript
function aplicarBreakdownResposta(d) {
  if (d && d.ok && d.sombra) { _previewNeg = d.sombra; _aplicarPreviewNaTela(d.sombra); }
}
```

Nos auto-saves (desconto global, descontos por ambiente, parâmetros), após o `fetch`, chamar `aplicarBreakdownResposta(await r.json())` em vez de recalcular no JS.

- [ ] **Step 3: `mpAtualizarApoio` só dispara o preview (apoio)**

Garantir que o ramo EP-07 de `mpAtualizarApoio` apenas mostra/esconde o painel e chama `agendarPreview()` (já feito); remover quaisquer ecos de viagem/brinde legados que sobraram (agora vêm do motor).

- [ ] **Step 4: Validação manual**

Run: `python3 main.py` → hard refresh. Editar desconto e params; conferir que apoio e tela batem e a cadeia do apoio fecha (à vista − arq − fid − viagem − brinde = líquido).

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(faxina): _aplicarPreviewNaTela unico escritor (viagem/brinde do motor)"
```

---

### Task 6: Frontend — apagar cálculo/sync legado; desconto único; modal read-only

**Files:**
- Modify: `static/index.html`

> Validação MANUAL no browser. Apagar somente o que a Task 4 confirmou como morto.

- [ ] **Step 1: Remover os escritores legados dos campos compartilhados**

Neutralizar a parte de **cálculo e escrita** de: `negAtualizarDescontoEfetivo`, `renderTabelaNeg` (bloco `upd` que escreve `neg-*` e o cálculo das células — manter só a construção das linhas/inputs com `data-ep07-id`), `executarCalculo` (escrita de `neg-*`), `_ep07DistribuirFinanciado`. Cada um passa a NÃO escrever os campos compartilhados (o motor escreve via `_aplicarPreviewNaTela`).

- [ ] **Step 2: Apagar funções de cálculo/empacotamento/sync legadas**

Remover (e seus chamadores): `lerMargensModal`, `calcularValorBrutoCliente`, `mpRecalcularEstruturalModal`, `negSyncModal`, `negSyncSidebar`. Simplificar `lerMargensNegociacao` para só o que ainda for usado (ou remover se nada depender). Ajustar os `oninput/onchange` que chamavam essas funções.

- [ ] **Step 3: Desconto único + modal read-only**

Tela de negociação: `neg-desconto` `oninput` → validar limite → auto-save (debounced) → `aplicarBreakdownResposta`. Remover `negSyncModal/Sidebar` das chamadas. No modal: tornar o campo de desconto **read-only** (atributo `readonly`, sem `oninput` de edição) exibindo o valor atual; remover `mp-desconto` como editor.

- [ ] **Step 4: Validação manual completa**

Run: `python3 main.py` → hard refresh. Roteiro: (a) com modal FECHADO, alterar desconto na tela → tudo atualiza ao vivo; (b) abrir modal → bruto/desconto/à vista batem com a tela (mesma fonte); (c) alterar param no modal → apoio atualiza; (d) reabrir/recarregar → valores persistem.

- [ ] **Step 5: Commit + DEV_LOG**

```bash
git add static/index.html DEV_LOG.md
git commit -m "feat(faxina): apaga calculo/sync legado; desconto unico; modal read-only"
```

(Acrescentar entrada no DEV_LOG: faxina Fase 1 concluída — motor é fonte única; legado removido; Fase 2 = limpeza de schema.)

---

## Self-Review (autor)

**Cobertura do spec:**
- §3.1 motor Cust_Via/Bri → Task 1. ✔
- §3.2 breakdown saved-only → Task 2. ✔
- §3.3 saves retornam breakdown (shape maiúsculo) → Task 3. ✔
- §3.4 preview sem corpo → Task 2 Step 4. ✔
- §4 único escritor (incl viagem/brinde) → Task 5. ✔
- §5 apagar legado / renderTabelaNeg estrutura → Tasks 4 (verificar) + 6. ✔
- §6 desconto único / modal read-only → Task 6 Step 3. ✔
- §8 testes/golden-master/rollback → Tasks 1-3 (E2E), 5-6 (manual), DEV_LOG. ✔

**Consistência de nomes:** `_negociacao_breakdown(orc, db)` (sem overrides), `aplicarBreakdownResposta(d)`, `_aplicarPreviewNaTela(s)` com `s.Cust_Via`/`s.Bri`, shape `"sombra"` maiúsculo — usados igual entre Tasks 2/3/5/6.

**Observações:** Tasks 5-6 (UI) sem teste automatizado (sem harness JS; refactor frontend delicado) → manual; a lógica por trás (motor/saves) é coberta por Tasks 1-3. Task 4 (investigação) gate as remoções da Task 6 para não apagar código vivo.
