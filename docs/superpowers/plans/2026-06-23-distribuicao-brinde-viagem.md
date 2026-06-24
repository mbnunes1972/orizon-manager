# Distribuição de Brinde/Viagem pelo Pool — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Brinde e custo viagem distribuem-se pelos ambientes do POOL do projeto; cada orçamento recupera sua fração (3 de 7 ambientes → brinde 3/7, viagem proporcional ao valor).

**Architecture:** O motor ganha o contexto do projeto (`n_total_proj`, `vbvo_proj`) como argumentos; `num_bri = bri/n_total_proj`, `num_via = cust_via × vbva/vbvo_proj`. O backend (`_negociacao_breakdown`) calcula esse contexto a partir do pool e passa ao motor. Fallback ao comportamento atual quando os args são `None`.

**Tech Stack:** Python 3 (stdlib http.server, SQLAlchemy/sqlite), pytest. No WSL é `python3` (não `python`).

## Global Constraints

- **Brinde igual por ambiente:** `num_bri = bri / n_total_proj`. **Viagem proporcional ao valor:** `num_via = cust_via × vbva / vbvo_proj`.
- **Denominador = TODOS os `PoolAmbiente` do projeto** (`n_total_proj` = contagem; `vbvo_proj` = Σ `budget_total`).
- **Fallback (args `None`):** comportamento atual — `num_bri = bri/num_amb`, `num_via = cust_via × vbva/VBVO_orçamento`. Garante que chamadas/testes legados (incl. a âncora LELEU, que NÃO passa contexto) continuem idênticos.
- **Sem migração de schema** (o parâmetro já guarda o TOTAL pós-faxina). Seletor de ambientes = passo 2 futuro (fora deste plano).
- **Ponto único:** `_negociacao_breakdown` é usado pelo preview e pelo `_recalcular_orcamento` — passar o contexto lá cobre os dois.
- `python3 -m pytest`. ~298 testes a manter verdes. Commits por task; `git add` só dos arquivos da task.

---

### Task 1: Motor distribui brinde/viagem pelo contexto do projeto

**Files:**
- Modify: `mod_negociacao.py` (assinatura + `num_bri`/`num_via`, ~linha 16 e 44-45)
- Test: `tests/test_negociacao.py`

**Interfaces:**
- Produces: `calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0, n_total_proj=None, vbvo_proj=None) -> dict`. `num_bri = bri/n_total_proj`, `num_via = cust_via × vbva/vbvo_proj` quando os args são passados; fallback (`num_amb`/`VBVO`) quando `None`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_negociacao.py
import mod_negociacao as mn

def test_distribuicao_3_de_7():
    """Projeto com 7 ambientes (pool), orçamento com 3 → brinde 3/7; viagem proporcional."""
    # orçamento = 3 ambientes (valores 10000, 10000, 10000); projeto = 7 ambientes
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    n_total_proj = 7
    vbvo_proj = 70000.0                      # 7 × 10000 (todos iguais p/ simplificar)
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0, n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    # brinde recuperado = 3 × (700/7) = 300
    assert abs(d["Bri"] - 300.0) < 0.01
    # viagem recuperada = 700 × (30000/70000) = 300
    assert abs(d["Cust_Via"] - 300.0) < 0.01

def test_fallback_sem_contexto_inalterado():
    """Sem n_total_proj/vbvo_proj → comportamento atual (orçamento recebe o valor cheio)."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0)    # sem contexto
    assert abs(d["Bri"] - 700.0) < 0.01      # cheio
    assert abs(d["Cust_Via"] - 700.0) < 0.01 # cheio
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao.py::test_distribuicao_3_de_7 -v`
Expected: FAIL (hoje `calcular_orcamento` não aceita `n_total_proj`/`vbvo_proj` → TypeError).

- [ ] **Step 3: Implementar no motor**

Alterar a assinatura (linha 16):

```python
def calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0, n_total_proj=None, vbvo_proj=None):
```

No corpo do loop, substituir as linhas de `num_via`/`num_bri` (atuais 44-45) por:

```python
        den_via = vbvo_proj if vbvo_proj else VBVO          # projeto (proporcional) ou orçamento (fallback)
        den_bri = n_total_proj if n_total_proj else num_amb # projeto (igual) ou orçamento (fallback)
        num_via = (cust_via * (vbva / den_via)) if (tog_cvia and den_via > 0) else 0.0
        num_bri = (bri / den_bri) if (tog_bri and den_bri) else 0.0
```

(VBVO já está calculado antes do loop; `num_amb` idem.)

- [ ] **Step 4: Rodar e ver passar + suíte do motor**

Run: `python3 -m pytest tests/test_negociacao.py -q`
Expected: PASS — incl. a âncora LELEU e `test_brinde_blindado_do_desconto` (não passam contexto → fallback → inalterados).

- [ ] **Step 5: Commit**

```bash
git add mod_negociacao.py tests/test_negociacao.py
git commit -m "feat(motor): distribui brinde/viagem pelo pool do projeto (n_total_proj/vbvo_proj + fallback)"
```

---

### Task 2: Backend calcula o contexto do projeto e passa ao motor

**Files:**
- Modify: `main.py` (`_negociacao_breakdown` ~4215 — as duas chamadas a `calcular_orcamento`)
- Test: `tests/test_cutover_e2e.py`

**Interfaces:**
- Consumes: `calcular_orcamento(..., n_total_proj=, vbvo_proj=)` (Task 1); modelos `PoolAmbiente` (`.projeto_id`, `.budget_total`).
- Produces: `_negociacao_breakdown(orc, db)` passa `n_total_proj`/`vbvo_proj` (do pool do projeto) às duas chamadas do motor.

- [ ] **Step 1: Escrever o teste E2E que falha**

```python
# tests/test_cutover_e2e.py
def test_breakdown_distribui_brinde_viagem_pelo_pool(http_client_factory, seed, app_db):
    """Projeto com 7 ambientes no pool; orçamento com 3 → Bri = 3/7 do total; viagem proporcional."""
    import json
    oid = seed["orcamento_l1_id"]
    db = app_db.get_session()
    o = db.get(app_db.Orcamento, oid); pj = o.projeto_id
    proj = db.query(app_db.Projeto).filter_by(nome_safe=pj).first()
    proj.parametros_json = json.dumps({"incluir_custos": False, "fora_da_sede": True,
        "custo_viagem": 700, "brinde_ativo": True, "brinde": 700})
    pool = []
    for i in range(7):
        pa = app_db.PoolAmbiente(nome=f"A{i}", nome_exibicao=f"A{i}", xml_path="x.xml",
            ambientes_json="{}", projeto_id=pj, budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush(); pool.append(pa.id)
    for pid in pool[:3]:                              # orçamento = 3 dos 7
        db.add(app_db.OrcamentoAmbiente(orcamento_id=oid, pool_ambiente_id=pid, ordem=1))
    db.commit(); db.close()

    c = _login(http_client_factory, "dir_l1")
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200
    s = body["sombra"]
    assert abs(s["Bri"] - 300.0) < 0.5            # 3/7 × 700
    assert abs(s["Cust_Via"] - 300.0) < 0.5       # 700 × 30000/70000
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cutover_e2e.py::test_breakdown_distribui_brinde_viagem_pelo_pool -v`
Expected: FAIL (hoje o breakdown não passa contexto → Bri/Cust_Via vêm cheios = 700).

- [ ] **Step 3: Implementar no `_negociacao_breakdown`**

Em `main.py`, no `_negociacao_breakdown`, antes das chamadas ao motor, calcular o contexto do pool e passá-lo às DUAS chamadas (`d0` e `d`):

```python
    pool_proj = db.query(PoolAmbiente).filter_by(projeto_id=orc.projeto_id).all()
    n_total_proj = len(pool_proj) or None
    vbvo_proj = sum((pa.budget_total or 0.0) for pa in pool_proj) or None
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc,
                                           n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    ...
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin,
                                          n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
```

(Localize as duas chamadas existentes a `calcular_orcamento` e acrescente os dois kwargs em ambas; mantenha o resto do helper.)

- [ ] **Step 4: Rodar e ver passar + suíte inteira**

Run: `python3 -m pytest tests/test_cutover_e2e.py -q && python3 -m pytest -q`
Expected: PASS (~300). Os testes de save/preview existentes seguem verdes (seus orçamentos = projeto inteiro → fração = 1).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cutover_e2e.py
git commit -m "feat(backend): _negociacao_breakdown passa contexto do pool (distribui brinde/viagem)"
```

---

## Self-Review (autor)

**Cobertura do spec:**
- §1 motor (n_total_proj/vbvo_proj + fallback) → Task 1. ✔
- §2 backend calcula contexto do pool e passa (ponto único) → Task 2. ✔
- §5 frontend sem mudança de cálculo → coberto (motor é a fonte; nada a fazer). ✔
- §6 dados existentes (sem migração) → Global Constraints. ✔
- §7 testes (3-de-7, fallback, âncora inalterada, E2E) → Tasks 1-2. ✔

**Consistência de nomes:** `calcular_orcamento(..., n_total_proj=None, vbvo_proj=None)`, `den_bri`/`den_via`, `_negociacao_breakdown` passando os kwargs nas DUAS chamadas — consistente entre Tasks 1-2.

**Observações:** A âncora LELEU e os testes de cutover existentes não passam contexto / têm orçamento = projeto inteiro → fração 1 → inalterados (verificado: a âncora não passa `n_total_proj`). Re-validação visual no navegador fica com o usuário (mudança de cálculo).
