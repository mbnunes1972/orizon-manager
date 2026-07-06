# Config financeira da loja + provisões + margem real (Frente C, v1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configurar as taxas financeiras por loja e fazer o motor calcular a margem real (`Cust_Var`/`Marg_Cont`) de cada orçamento.

**Architecture:** Config por loja num JSON (`lojas.config_financeira_json`) + `Out_Forn` por orçamento (`orcamentos.out_forn`). Módulo puro novo `mod_provisoes.py` (recebe as siglas do motor + a config, devolve provisões + `Cust_Var`/`Marg_Cont`). Integração no ponto único `_negociacao_breakdown` (read-time, sem persistir na v1). Rotas finas GET/PUT da config. Frontend: aba "Financeiro" no nível Loja + modal de comissão + exibição restrita da margem real.

**Tech Stack:** Python 3 (`python3` no WSL), SQLAlchemy/SQLite, `http.server` (`main.Handler`), SPA vanilla, `pytest` (frontend = verificação manual).

## Global Constraints

- Rodar com `python3`/`python3 -m pytest` (WSL), nunca `python`.
- **Percentuais** são guardados como número-percent (ex.: `10` = 10%) e divididos por 100 no cálculo — **mesma convenção do `mod_negociacao`** (`_f(p.get("comissao_arq_pct"))/100.0`).
- **`mod_provisoes` é puro** (sem I/O/ORM): recebe `siglas` (dict do motor) + `cfg` (dict da config) e devolve dicts.
- **Fórmulas FECHADAS** (não inventar siglas — ver `docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md`):
  - `Frete_Fab_Orc = %Frete_Fab × CFO`
  - `Com_Adm_Orc = %Com_Adm × Val_Liq` · `Com_Venda_Orc = %Com_Venda × Val_Liq` · `Com_Med_Orc = %Com_Med × Val_Liq` · `Com_Proj_Exec_Orc = %Com_Proj_Exec × Val_Liq`
  - `Frete_Loc_Orc = %Frete_Loc × VAVO` · `Assist_Orc = %Assist × VAVO` · `Ins_Loc_Orc = %Ins_Loc × VAVO`
  - `Cust_Var = CFO + Out_Forn + Frete_Fab_Orc + Com_Adm_Orc + Com_Venda_Orc + Com_Med_Orc + Com_Proj_Exec_Orc + Frete_Loc_Orc + Assist_Orc + Ins_Loc_Orc + Prov_Imp`
  - `Marg_Cont = (Val_Liq − Cust_Var) / Val_Liq` (sobre o **valor líquido**; pode ser negativa; `Val_Liq==0 → 0.0`)
- **v1 da comissão:** `%Com_Venda` resolvido com `val_liq_mes = Val_Liq do próprio orçamento` (sem acumulação mensal — isso é fase 2).
- **Margem real exposta no breakdown** (read-time), **não persistida** na v1.
- **Acesso:** editar config = `editar_dados_loja` + escopo de tenancy (admin_rede só lojas da rede); ver margem real = atrás do cadeado dos impostos (`liberar_impostos`). Regra da comissão **no backend**.
- Seguir padrões: migração idempotente `ALTER TABLE` no `init_db`; rotas admin finas; funções puras em módulo.

---

### Task 1: Colunas `lojas.config_financeira_json` e `orcamentos.out_forn` + migração

**Files:**
- Modify: `database.py` (modelo `Loja` + modelo `Orcamento` + bloco de migração do `init_db`)
- Test: `tests/test_config_financeira.py`

**Interfaces:**
- Produces: `Loja.config_financeira_json` (Text, nullable); `Orcamento.out_forn` (Float, default 0.0); migração idempotente que faz `ALTER TABLE` em DBs existentes.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_config_financeira.py`:

```python
import json


def test_loja_guarda_config_financeira_json(app_db, seed):
    db = app_db.get_session()
    try:
        l = db.get(app_db.Loja, seed["loja1_id"])
        l.config_financeira_json = json.dumps({"provisoes": {"frete_fab_pct": 5.0}})
        db.commit()
        l2 = db.get(app_db.Loja, seed["loja1_id"])
        assert json.loads(l2.config_financeira_json)["provisoes"]["frete_fab_pct"] == 5.0
    finally:
        db.close()


def test_orcamento_tem_out_forn_default_zero(app_db, seed):
    db = app_db.get_session()
    try:
        o = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        assert (o.out_forn or 0.0) == 0.0
        o.out_forn = 1234.5
        db.commit()
        assert db.get(app_db.Orcamento, seed["orcamento_l1_id"]).out_forn == 1234.5
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_financeira.py -v`
Expected: FAIL (`AttributeError`/coluna inexistente).

- [ ] **Step 3: Write minimal implementation**

Em `database.py`:
- Na classe `Loja`, adicionar (perto de `criado_em`):
```python
    config_financeira_json = Column(Text, nullable=True)   # config financeira da loja (JSON)
```
- Na classe `Orcamento`, adicionar (junto das colunas-sombra):
```python
    out_forn = Column(Float, default=0.0)   # Outros Fornecedores (editável Gerente Adm/Fin)
```
- No bloco de migração do `init_db` (onde outras colunas são adicionadas via `ALTER TABLE` — procurar `ADD COLUMN parametros_json`), seguir o MESMO padrão de checagem de coluna existente e adicionar:
```python
    # 2026-06-24: config financeira da loja + Out_Forn por orçamento
    loja_cols = [c[1] for c in cur.execute("PRAGMA table_info(lojas)").fetchall()]
    if "config_financeira_json" not in loja_cols:
        cur.execute("ALTER TABLE lojas ADD COLUMN config_financeira_json TEXT")
    orc_cols = [c[1] for c in cur.execute("PRAGMA table_info(orcamentos)").fetchall()]
    if "out_forn" not in orc_cols:
        cur.execute("ALTER TABLE orcamentos ADD COLUMN out_forn REAL DEFAULT 0")
```
(Ajuste o nome do cursor (`cur`) ao usado no bloco; o `PRAGMA table_info` é o mesmo padrão já presente.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config_financeira.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Run full suite (migração idempotente)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_config_financeira.py
git commit -m "feat(financeira): colunas lojas.config_financeira_json + orcamentos.out_forn"
```

---

### Task 2: `mod_provisoes` — defaults + validação da config (puro)

**Files:**
- Create: `mod_provisoes.py`
- Test: `tests/test_provisoes.py`

**Interfaces:**
- Produces: `config_financeira_default() -> dict` (estrutura completa, tudo 0/inativo); `validar_config_financeira(dados) -> list[str]` (erros; vazia se válido).

- [ ] **Step 1: Write the failing test**

Criar `tests/test_provisoes.py`:

```python
import mod_provisoes


def test_default_tem_estrutura_completa():
    c = mod_provisoes.config_financeira_default()
    assert set(c.keys()) == {"defaults_negociacao", "provisoes", "comissao_vendas"}
    assert c["provisoes"]["frete_fab_pct"] == 0.0
    assert c["comissao_vendas"]["limitador_desconto"]["ativo"] is False


def test_validar_aceita_default():
    assert mod_provisoes.validar_config_financeira(mod_provisoes.config_financeira_default()) == []


def test_validar_rejeita_percentual_negativo():
    c = mod_provisoes.config_financeira_default()
    c["provisoes"]["com_adm_pct"] = -1.0
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros and any("negativ" in e.lower() for e in erros)


def test_validar_rejeita_faixa_sem_pct():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": 1000.0}]
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes.py -v`
Expected: FAIL (`ModuleNotFoundError: mod_provisoes`).

- [ ] **Step 3: Write minimal implementation**

Criar `mod_provisoes.py`:

```python
# -*- coding: utf-8 -*-
"""mod_provisoes.py — Provisões pós-fechamento e margem real (PURO, sem I/O).

Recebe as siglas do motor (mod_negociacao) + a config financeira da loja e devolve
as provisões por orçamento, Cust_Var e Marg_Cont. Percentuais em número-percent
(10 = 10%), divididos por 100 aqui — mesma convenção do mod_negociacao.
Fórmulas fechadas: docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md.
"""

_PROV_KEYS = ("frete_fab_pct", "com_adm_pct", "com_med_pct", "com_proj_exec_pct",
              "frete_loc_pct", "assist_pct", "ins_loc_pct")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def config_financeira_default():
    return {
        "defaults_negociacao": {"comissao_arq_pct": 0.0, "fidelidade_pct": 0.0, "carga_trib_pct": 0.0},
        "provisoes": {k: 0.0 for k in _PROV_KEYS},
        "comissao_vendas": {
            "meta_mensal": 0.0,
            "faixas_comissao": [{"venda_ate": None, "pct": 0.0}],
            "limitador_desconto": {"ativo": False, "base_desconto": "Desc_Orc", "limites": []},
        },
    }


def validar_config_financeira(dados):
    erros = []
    d = dados or {}
    prov = d.get("provisoes", {})
    for k in _PROV_KEYS:
        if _f(prov.get(k)) < 0:
            erros.append(f"Provisão {k} não pode ser negativa.")
    for k, v in (d.get("defaults_negociacao", {}) or {}).items():
        if _f(v) < 0:
            erros.append(f"Default {k} não pode ser negativo.")
    cv = d.get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", [])
    if not faixas:
        erros.append("Comissão de vendas precisa de ao menos uma faixa.")
    for fx in faixas:
        if "pct" not in fx:
            erros.append("Cada faixa de comissão precisa de 'pct'.")
        elif _f(fx.get("pct")) < 0:
            erros.append("Percentual de faixa não pode ser negativo.")
    for lim in (cv.get("limitador_desconto", {}) or {}).get("limites", []):
        if _f(lim.get("redutor_pct")) < 0 or _f(lim.get("desconto_acima_de")) < 0:
            erros.append("Limite de desconto com valor negativo.")
    return erros
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_provisoes.py
git commit -m "feat(provisoes): config_financeira_default + validar_config_financeira"
```

---

### Task 3: `mod_provisoes.resolver_comissao_venda` (puro)

**Files:**
- Modify: `mod_provisoes.py`
- Test: `tests/test_provisoes.py`

**Interfaces:**
- Consumes: `cfg["comissao_vendas"]`.
- Produces: `resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct) -> float` (percent). Faixa por `val_liq_mes` (limiar `venda_ate` exclusivo no topo; `None` = faixa final sem teto); se `limitador_desconto.ativo`, aplica o `redutor_pct` do MAIOR limite cujo `desconto_acima_de < desc_orc_pct`, multiplicativo: `pct × (1 − redutor/100)`.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisoes.py`:

```python
def _cfg_comissao():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [
        {"venda_ate": 10000.0, "pct": 1.0},   # < 10k
        {"venda_ate": 30000.0, "pct": 2.0},   # 10k–30k
        {"venda_ate": None,    "pct": 3.0},   # ≥ 30k
    ]
    c["comissao_vendas"]["limitador_desconto"] = {
        "ativo": True, "base_desconto": "Desc_Orc",
        "limites": [{"desconto_acima_de": 5.0, "redutor_pct": 50.0},
                    {"desconto_acima_de": 10.0, "redutor_pct": 80.0}],
    }
    return c


def test_faixa_por_venda():
    c = _cfg_comissao()
    assert mod_provisoes.resolver_comissao_venda(c, 5000.0, 0.0) == 1.0
    assert mod_provisoes.resolver_comissao_venda(c, 20000.0, 0.0) == 2.0
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 0.0) == 3.0


def test_redutor_por_desconto():
    c = _cfg_comissao()
    # faixa 3% (venda 50k), desconto 12% > 10% → redutor 80% → 3 × 0.2 = 0.6
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 0.6
    # desconto 7% → redutor 50% → 3 × 0.5 = 1.5
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 7.0) == 1.5


def test_limitador_desligado_nao_reduz():
    c = _cfg_comissao()
    c["comissao_vendas"]["limitador_desconto"]["ativo"] = False
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 3.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes.py -k "faixa or redutor or limitador" -v`
Expected: FAIL (`AttributeError: resolver_comissao_venda`).

- [ ] **Step 3: Write minimal implementation**

Acrescentar a `mod_provisoes.py`:

```python
def resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct):
    cv = (cfg or {}).get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", []) or []
    pct = 0.0
    for fx in faixas:
        ate = fx.get("venda_ate")
        if ate is None or _f(val_liq_mes) < _f(ate):
            pct = _f(fx.get("pct"))
            break
    else:
        pct = _f(faixas[-1].get("pct")) if faixas else 0.0
    lim = cv.get("limitador_desconto", {}) or {}
    if lim.get("ativo"):
        redutor = 0.0
        for L in sorted(lim.get("limites", []) or [], key=lambda x: _f(x.get("desconto_acima_de"))):
            if _f(desc_orc_pct) > _f(L.get("desconto_acima_de")):
                redutor = _f(L.get("redutor_pct"))
        pct = pct * (1 - redutor / 100.0)
    return round(pct, 4)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_provisoes.py
git commit -m "feat(provisoes): resolver_comissao_venda (faixa + limitador de desconto)"
```

---

### Task 4: `mod_provisoes.provisoes_orcamento` — Cust_Var + Marg_Cont (puro)

**Files:**
- Modify: `mod_provisoes.py`
- Test: `tests/test_provisoes.py`

**Interfaces:**
- Consumes: `siglas` (dict do motor com `CFO`, `Val_Liq`, `VAVO`, `Prov_Imp`), `cfg["provisoes"]`.
- Produces: `provisoes_orcamento(siglas, cfg, out_forn=0.0, com_venda_pct=0.0) -> dict` com chaves `Frete_Fab_Orc, Com_Adm_Orc, Com_Venda_Orc, Com_Med_Orc, Com_Proj_Exec_Orc, Frete_Loc_Orc, Assist_Orc, Ins_Loc_Orc, Out_Forn, Cust_Var, Marg_Cont`. `com_venda_pct` = percent já resolvido (Task 3).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisoes.py`:

```python
def test_provisoes_e_margem():
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    c["provisoes"].update({"frete_fab_pct": 10.0, "com_adm_pct": 5.0,
                           "frete_loc_pct": 2.0})
    r = mod_provisoes.provisoes_orcamento(siglas, c, out_forn=300.0, com_venda_pct=1.0)
    assert r["Frete_Fab_Orc"] == 100.0      # 10% × 1000 CFO
    assert r["Com_Adm_Orc"] == 100.0        # 5% × 2000 Val_Liq
    assert r["Com_Venda_Orc"] == 20.0       # 1% × 2000 Val_Liq
    assert r["Frete_Loc_Orc"] == 50.0       # 2% × 2500 VAVO
    assert r["Out_Forn"] == 300.0
    # Cust_Var = 1000 CFO + 300 Out + 100 + 100 + 20 + 0 + 0 + 50 + 0 + 0 + 0 Prov_Imp = 1570
    assert r["Cust_Var"] == 1570.0
    # Marg_Cont = (2000 - 1570)/2000 = 0.215
    assert r["Marg_Cont"] == 0.215


def test_margem_negativa_e_val_liq_zero():
    siglas = {"CFO": 5000.0, "Val_Liq": 1000.0, "VAVO": 1000.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    r = mod_provisoes.provisoes_orcamento(siglas, c)
    assert r["Marg_Cont"] < 0                       # Cust_Var (5000) > Val_Liq (1000)
    siglas0 = {"CFO": 0.0, "Val_Liq": 0.0, "VAVO": 0.0, "Prov_Imp": 0.0}
    assert mod_provisoes.provisoes_orcamento(siglas0, c)["Marg_Cont"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes.py -k "provisoes_e_margem or margem_negativa" -v`
Expected: FAIL (`AttributeError: provisoes_orcamento`).

- [ ] **Step 3: Write minimal implementation**

Acrescentar a `mod_provisoes.py`:

```python
def provisoes_orcamento(siglas, cfg, out_forn=0.0, com_venda_pct=0.0):
    s = siglas or {}
    CFO = _f(s.get("CFO")); Val_Liq = _f(s.get("Val_Liq"))
    VAVO = _f(s.get("VAVO")); Prov_Imp = _f(s.get("Prov_Imp"))
    prov = (cfg or {}).get("provisoes", {}) or {}
    out_forn = _f(out_forn)

    frete_fab = _f(prov.get("frete_fab_pct")) / 100.0 * CFO
    com_adm   = _f(prov.get("com_adm_pct"))   / 100.0 * Val_Liq
    com_venda = _f(com_venda_pct)             / 100.0 * Val_Liq
    com_med   = _f(prov.get("com_med_pct"))   / 100.0 * Val_Liq
    com_proj  = _f(prov.get("com_proj_exec_pct")) / 100.0 * Val_Liq
    frete_loc = _f(prov.get("frete_loc_pct")) / 100.0 * VAVO
    assist    = _f(prov.get("assist_pct"))    / 100.0 * VAVO
    ins_loc   = _f(prov.get("ins_loc_pct"))   / 100.0 * VAVO

    cust_var = (CFO + out_forn + frete_fab + com_adm + com_venda + com_med
                + com_proj + frete_loc + assist + ins_loc + Prov_Imp)
    marg_cont = ((Val_Liq - cust_var) / Val_Liq) if Val_Liq else 0.0
    return {
        "Frete_Fab_Orc": round(frete_fab, 2), "Com_Adm_Orc": round(com_adm, 2),
        "Com_Venda_Orc": round(com_venda, 2), "Com_Med_Orc": round(com_med, 2),
        "Com_Proj_Exec_Orc": round(com_proj, 2), "Frete_Loc_Orc": round(frete_loc, 2),
        "Assist_Orc": round(assist, 2), "Ins_Loc_Orc": round(ins_loc, 2),
        "Out_Forn": round(out_forn, 2),
        "Cust_Var": round(cust_var, 2), "Marg_Cont": round(marg_cont, 4),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_provisoes.py
git commit -m "feat(provisoes): provisoes_orcamento (Cust_Var + Marg_Cont)"
```

---

### Task 5: Integrar no `_negociacao_breakdown` (motor expõe Cust_Var/Marg_Cont)

**Files:**
- Modify: `main.py` (`_negociacao_breakdown` ~4307)
- Test: `tests/test_provisoes_e2e.py`

**Interfaces:**
- Consumes: `mod_provisoes.{provisoes_orcamento, resolver_comissao_venda, config_financeira_default}`; `database` (Loja, Orcamento).
- Produces: o dict `d` retornado por `_negociacao_breakdown` ganha as chaves de provisão + `Cust_Var` + `Marg_Cont`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_provisoes_e2e.py`:

```python
import json


def test_breakdown_inclui_margem_real(app_db, seed, projetos_dir):
    import main, mod_provisoes
    db = app_db.get_session()
    try:
        # configura a loja 1 com frete fábrica 10% e injeta ambientes no orçamento L1
        loja = db.get(app_db.Loja, seed["loja1_id"])
        cfg = mod_provisoes.config_financeira_default()
        cfg["provisoes"]["frete_fab_pct"] = 10.0
        loja.config_financeira_json = json.dumps(cfg)
        # pool ambiente + vínculo no orçamento L1 (VBVA/CFA não-nulos)
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        d = main._negociacao_breakdown(orc, db)
    finally:
        db.close()
    assert "Cust_Var" in d and "Marg_Cont" in d
    assert d["Frete_Fab_Orc"] == round(0.10 * d["CFO"], 2)
    # Cust_Var >= CFO (custo de fábrica sempre entra)
    assert d["Cust_Var"] >= d["CFO"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes_e2e.py -v`
Expected: FAIL (`KeyError: 'Cust_Var'`).

- [ ] **Step 3: Write minimal implementation**

Em `main.py`, no fim de `_negociacao_breakdown` (logo antes de `return d`), inserir:

```python
    import mod_provisoes
    cfg = {}
    loja = db.get(Loja, orc.loja_id) if getattr(orc, "loja_id", None) else None
    if loja and loja.config_financeira_json:
        try:
            cfg = json.loads(loja.config_financeira_json)
        except Exception:
            cfg = {}
    if not cfg:
        cfg = mod_provisoes.config_financeira_default()
    com_venda_pct = mod_provisoes.resolver_comissao_venda(cfg, d.get("Val_Liq", 0.0), desc_orc)
    prov = mod_provisoes.provisoes_orcamento(d, cfg, out_forn=(orc.out_forn or 0.0),
                                             com_venda_pct=com_venda_pct)
    d.update(prov)
```

(`desc_orc` já existe na função = `orc.desconto_pct or 0.0`. `Loja`/`Orcamento` já estão importados em `main.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite (regressão do motor/breakdown)**

Run: `python3 -m pytest -q`
Expected: verde — config zerada não altera as siglas existentes; `Cust_Var`/`Marg_Cont` são chaves novas.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_provisoes_e2e.py
git commit -m "feat(provisoes): _negociacao_breakdown expoe Cust_Var/Marg_Cont"
```

---

### Task 6: Rotas da config financeira + `Out_Forn` por orçamento

**Files:**
- Modify: `main.py` (GET/PUT `/api/admin/lojas/<id>/config-financeira` em `do_GET`/`do_PUT`; PATCH `out_forn` no orçamento)
- Test: `tests/test_provisoes_e2e.py`

**Interfaces:**
- Consumes: `mod_provisoes.{config_financeira_default, validar_config_financeira}`; `mod_tenancy.pode_ver_loja`; helpers `get_usuario_sessao`, `_ator_dict`.
- Produces: `GET /api/admin/lojas/<id>/config-financeira` → `{"ok":true,"config":{...}}`; `PUT` mesma rota grava (valida); `PATCH /projetos/<nome>/orcamentos/<oid>/out-forn` grava `out_forn` (escopo operacional).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisoes_e2e.py`:

```python
def test_get_put_config_financeira(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")   # diretor: editar_dados_loja
    st, body = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    assert st == 200 and "config" in body
    cfg = body["config"]; cfg["provisoes"]["com_adm_pct"] = 7.0
    st2, body2 = c.put("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"], cfg)
    assert st2 == 200 and body2["ok"] is True
    st3, body3 = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    assert body3["config"]["provisoes"]["com_adm_pct"] == 7.0


def test_put_config_rejeita_invalido(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    _, body = c.get("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"])
    cfg = body["config"]; cfg["provisoes"]["frete_fab_pct"] = -5.0
    st, b = c.put("/api/admin/lojas/%d/config-financeira" % seed["loja1_id"], cfg)
    assert b["ok"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes_e2e.py -k config_financeira -v`
Expected: FAIL (rotas inexistentes).

- [ ] **Step 3: Write minimal implementation**

3a. No `do_GET` de `main.py`, junto das rotas `/api/admin/lojas/...` (após o bloco de projetos da árvore, mesmo padrão), adicionar:

```python
        elif path.startswith("/api/admin/lojas/") and path.endswith("/config-financeira"):
            import re as _re, mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            m = _re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                cfg = json.loads(loja.config_financeira_json) if loja.config_financeira_json \
                    else mod_provisoes.config_financeira_default()
                self.send_json({"ok": True, "config": cfg})
            finally:
                db.close()
```

3b. No `do_PUT` de `main.py` (no início, junto da rota de renomear orçamento), adicionar o ramo:

```python
        m_cfg = re.match(r"^/api/admin/lojas/(\d+)/config-financeira$", path)
        if m_cfg:
            import mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "editar_dados_loja"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}); return
            erros = mod_provisoes.validar_config_financeira(req)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)}); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_cfg.group(1)))
                if not loja or not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Loja fora do escopo"}, code=403); return
                loja.config_financeira_json = json.dumps(req, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return
```

(`HttpClient.put` já existe no conftest. `re`, `json`, `mod_tenancy`, `perfis`, `Loja` já estão no escopo de `main.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes_e2e.py -k config_financeira -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_provisoes_e2e.py
git commit -m "feat(provisoes): rotas GET/PUT config-financeira da loja"
```

> **Out_Forn por orçamento:** a edição de `out_forn` (PATCH operacional por orçamento, Gerente Adm/Fin) é uma adição pequena; está coberta no frontend (Task 10) lendo/gravando via uma rota PATCH análoga às de orçamento. Se preferir, trate `out_forn` junto do PATCH de orçamento existente. Mantido fora do caminho crítico da margem (entra como 0 até ser editado).

---

### Task 7: Defaults da loja na criação do `parametros_json` do projeto

**Files:**
- Modify: `mod_orcamento_params.py` (helper) e o ponto de criação do default
- Test: `tests/test_provisoes.py`

**Interfaces:**
- Consumes: a config da loja (`defaults_negociacao`).
- Produces: `parametros_default_loja(cfg) -> dict` — um `parametros_json` inicial com `comissao_arq_pct`/`fidelidade_pct`/`carga_trib` vindos da loja (cai no `PARAMETROS_DEFAULT` quando a loja não tem config).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisoes.py`:

```python
import mod_orcamento_params


def test_parametros_default_loja_usa_config():
    cfg = {"defaults_negociacao": {"comissao_arq_pct": 12.0, "fidelidade_pct": 3.0, "carga_trib_pct": 8.0}}
    p = mod_orcamento_params.parametros_default_loja(cfg)
    assert p["comissao_arq_pct"] == 12.0
    assert p["fidelidade_pct"] == 3.0
    assert p["carga_trib"] == 8.0
    # chaves do PARAMETROS_DEFAULT preservadas
    assert "incluir_custos" in p


def test_parametros_default_loja_sem_config_cai_no_default():
    p = mod_orcamento_params.parametros_default_loja(None)
    assert p == dict(mod_orcamento_params.PARAMETROS_DEFAULT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes.py -k parametros_default_loja -v`
Expected: FAIL (`AttributeError: parametros_default_loja`).

- [ ] **Step 3: Write minimal implementation**

Em `mod_orcamento_params.py`, adicionar:

```python
def parametros_default_loja(cfg):
    """parametros_json inicial de um projeto, com defaults da loja sobre o PARAMETROS_DEFAULT."""
    base = dict(PARAMETROS_DEFAULT)
    dn = (cfg or {}).get("defaults_negociacao", {}) or {}
    if "comissao_arq_pct" in dn: base["comissao_arq_pct"] = float(dn["comissao_arq_pct"] or 0)
    if "fidelidade_pct" in dn:   base["fidelidade_pct"]   = float(dn["fidelidade_pct"] or 0)
    if "carga_trib_pct" in dn:   base["carga_trib"]       = float(dn["carga_trib_pct"] or 0)
    return base
```

(Verifique no `PARAMETROS_DEFAULT` os nomes exatos das chaves — `comissao_arq_pct`, `fidelidade_pct`, `carga_trib` — e ajuste se diferirem.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes.py -k parametros_default_loja -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_orcamento_params.py tests/test_provisoes.py
git commit -m "feat(provisoes): parametros_default_loja (defaults de negociacao por loja)"
```

> **Wiring opcional (mesmo commit ou seguinte):** no ponto onde um projeto novo recebe `parametros_json` pela primeira vez (hoje `dict(PARAMETROS_DEFAULT)` em `main.py`), passar a usar `parametros_default_loja(cfg_da_loja_do_projeto)`. Como projetos existentes já têm `parametros_json`, isso só afeta projetos novos — sem regressão. Se o ponto de criação não estiver óbvio, deixar o helper pronto e fazer o wiring numa tarefa de follow-up (documentar no relatório).

---

### Task 8: Frontend — aba "Financeiro" no nível Loja (editar config)

**Files:**
- Modify: `static/index.html` (nível Loja do Painel Admin — `adminRenderLoja`/`adminLojaTab`; novas funções de carregar/salvar)

**Interfaces:**
- Consumes: `GET/PUT /api/admin/lojas/<id>/config-financeira`.
- Produces: 4ª aba "Financeiro" no nível Loja, com campos de `defaults_negociacao` + `provisoes` e botão Salvar.

- [ ] **Step 1: Adicionar a aba e o painel**

Em `adminRenderLoja` (a função que monta as abas Dados/Usuários/Projetos), acrescentar o botão de aba e o painel:
```javascript
// no <div> das abas:
'<button class="home-tab" id="loja-tab-financeiro" onclick="adminLojaTab(\'financeiro\')">Financeiro</button>'
// após os panels existentes:
'<div id="loja-panel-financeiro" style="display:none"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>'
```
E em `adminLojaTab`, incluir `'financeiro'` na lista de abas e chamar `adminFinanceiroCarregar()` quando `qual==='financeiro'` (mesmo padrão da aba Projetos).

- [ ] **Step 2: Loader + saver da config financeira**

Adicionar:
```javascript
let _cfgFin = null;
async function adminFinanceiroCarregar(){
  const panel = document.getElementById('loja-panel-financeiro');
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  if (!panel || !lid) return;
  const r = await fetch('/api/admin/lojas/'+lid+'/config-financeira', {credentials:'same-origin'});
  if (r.status === 403){ panel.innerHTML = '<em style="color:var(--muted)">Sem acesso.</em>'; return; }
  const d = await r.json().catch(()=>({}));
  _cfgFin = d.config || {};
  const prov = _cfgFin.provisoes || {};
  const dn = _cfgFin.defaults_negociacao || {};
  const campo = (id,lbl,val)=>`<div><label class="field-label">${lbl}</label>
    <input id="${id}" type="number" step="0.01" value="${val||0}"
     style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>`;
  panel.innerHTML = `
    <div class="grid2" style="gap:14px;margin-bottom:14px">
      ${campo('fin-com-arq','% Comissão arquiteto (default)',dn.comissao_arq_pct)}
      ${campo('fin-fid','% Fidelidade (default)',dn.fidelidade_pct)}
      ${campo('fin-trib','% Carga tributária',dn.carga_trib_pct)}
      ${campo('fin-frete-fab','% Frete fábrica→loja',prov.frete_fab_pct)}
      ${campo('fin-com-adm','% Comissões administrativas',prov.com_adm_pct)}
      ${campo('fin-com-med','% Comissão de medidor',prov.com_med_pct)}
      ${campo('fin-com-pe','% Comissão projeto executivo',prov.com_proj_exec_pct)}
      ${campo('fin-frete-loc','% Frete local',prov.frete_loc_pct)}
      ${campo('fin-assist','% Assistências',prov.assist_pct)}
      ${campo('fin-ins','% Insumos locais',prov.ins_loc_pct)}
    </div>
    <button class="btn btn-primary btn-sm" onclick="adminFinanceiroSalvar(${lid})">Salvar config financeira</button>`;
}
async function adminFinanceiroSalvar(lid){
  const n = id => parseFloat(document.getElementById(id).value || '0') || 0;
  _cfgFin.defaults_negociacao = {comissao_arq_pct:n('fin-com-arq'), fidelidade_pct:n('fin-fid'), carga_trib_pct:n('fin-trib')};
  _cfgFin.provisoes = {frete_fab_pct:n('fin-frete-fab'), com_adm_pct:n('fin-com-adm'), com_med_pct:n('fin-com-med'),
    com_proj_exec_pct:n('fin-com-pe'), frete_loc_pct:n('fin-frete-loc'), assist_pct:n('fin-assist'), ins_loc_pct:n('fin-ins')};
  const r = await fetch('/api/admin/lojas/'+lid+'/config-financeira', {method:'PUT', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(_cfgFin)});
  const d = await r.json();
  if(!d.ok){ await avisoPopup(d.erro||'Erro', {titulo:'Config financeira'}); return; }
  showToast('Config financeira salva.', false);
}
```

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py
```
Como diretor/gerente adm/fin (ou super_admin): Painel Admin → loja → aba **Financeiro** → editar percentuais → Salvar → recarregar a aba e conferir que persistiu.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(financeira): aba Financeiro no nivel Loja (edita config)"
```

---

### Task 9: Frontend — modal de comissão de vendas (faixas + limitador)

**Files:**
- Modify: `static/index.html` (botão na aba Financeiro + modal com 2 tabelas)

**Interfaces:**
- Consumes: `_cfgFin.comissao_vendas` (carregado na Task 8); grava no mesmo PUT.
- Produces: modal que edita `faixas_comissao` (linhas {venda_ate, pct}) e `limitador_desconto` (toggle + linhas {desconto_acima_de, redutor_pct}).

- [ ] **Step 1: Botão + modal**

Na aba Financeiro (Task 8), adicionar um botão "Configurar comissão de vendas" que abre um modal. O modal tem: campo `meta_mensal`; uma tabela editável de **faixas** (`+ faixa` adiciona linha {venda_ate, pct}; última faixa com `venda_ate` vazio = sem teto); um **toggle** "limitador de desconto ativo"; uma tabela editável de **limites** ({desconto_acima_de, redutor_pct}). Salvar escreve em `_cfgFin.comissao_vendas` e dispara `adminFinanceiroSalvar(lid)`.

Implementar com o mesmo padrão de modal já usado (`modal-overlay`/`modal-box`); coletar as linhas das tabelas em arrays. Código de referência (resumido — o implementador completa seguindo o padrão dos outros modais):
```javascript
function abrirModalComissao(lid){
  const cv = _cfgFin.comissao_vendas || (_cfgFin.comissao_vendas = {meta_mensal:0,
    faixas_comissao:[{venda_ate:null,pct:0}], limitador_desconto:{ativo:false,base_desconto:'Desc_Orc',limites:[]}});
  // renderizar tabelas editáveis de cv.faixas_comissao e cv.limitador_desconto.limites
  // toggle: cv.limitador_desconto.ativo
  // ... (HTML do modal + handlers de +linha/-linha) ...
  document.getElementById('modal-comissao').style.display='flex';
}
function salvarModalComissao(lid){
  // ler meta_mensal, as linhas de faixas (venda_ate vazio => null), o toggle e as linhas de limites
  // gravar em _cfgFin.comissao_vendas e chamar adminFinanceiroSalvar(lid)
}
```

- [ ] **Step 2: Verificação manual**

```bash
python3 main.py
```
Aba Financeiro → "Configurar comissão de vendas" → definir 2-3 faixas e ativar/desativar o limitador com limites → Salvar → reabrir e conferir persistência. Conferir no backend (via `resolver_comissao_venda`/teste) que os valores batem.

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat(financeira): modal de comissao de vendas (faixas + limitador)"
```

---

### Task 10: Frontend — margem real na negociação (atrás do cadeado dos impostos) + `Out_Forn`

**Files:**
- Modify: `static/index.html` (tela de negociação — exibir `Marg_Cont`/`Cust_Var` e campo `Out_Forn`)

**Interfaces:**
- Consumes: o breakdown (`d`) agora traz `Cust_Var`, `Marg_Cont`, `Out_Forn` e as provisões (Task 5).
- Produces: bloco de **margem real** exibido junto dos impostos, sob o mesmo controle `_impostosLiberados`; campo editável `Out_Forn` (Gerente Adm/Fin) que dispara recálculo.

- [ ] **Step 1: Exibir a margem real sob o cadeado**

Onde a tela de negociação já renderiza os campos de impostos sob `_impostosLiberados` (`_renderImpostosLock`), acrescentar a exibição de `Cust_Var` e `Marg_Cont` (formatados; `Marg_Cont × 100` com `%`). Reutilizar a mesma condição de visibilidade dos impostos — nenhum novo controle de acesso.

- [ ] **Step 2: Campo `Out_Forn` editável**

Adicionar um campo "Outros fornecedores (R$)" visível para quem pode aprovar financeiro, que ao alterar grava `out_forn` no orçamento (PATCH) e re-busca o breakdown (a margem recalcula). Seguir o padrão de auto-save/recalculo já usado nos campos da negociação.

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py
```
Na negociação de um projeto: revelar os impostos (senha financeira) → ver **Custo variável** e **Margem de contribuição**; editar **Outros fornecedores** → a margem recalcula. Conferir que sem revelar os impostos a margem fica oculta.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(financeira): margem real na negociacao (sob cadeado) + Out_Forn editavel"
```

---

## Notas de implementação

- **Ordem/dependências:** Tasks 1→4 são a base pura (DB + `mod_provisoes`). Task 5 integra no motor. Task 6 (rotas) e Task 7 (defaults) dependem de 1-2. Tasks 8-10 (frontend) dependem de 5-6 mergeadas.
- **Branch:** implementar a partir do `main` **já com as frentes A (árvore) e B (multi-loja) mergeadas** — Task 5/6 tocam `main.py`/`static/index.html`, áreas que A/B também mexem.
- **Fora desta v1 (fases futuras do spec):** acumulador mensal + fechamento de ciclo da comissão; custo financeiro absorvido em `Cust_Var`; condições de pagamento por loja; divisão de `Com_Adm` por função adm.
- **Micro-pontos da comissão** (defaults adotados; confirmar antes da fase 2): limiares R$ absolutos; `redutor` multiplicativo; fronteira `venda_ate` exclusiva no topo / `desconto_acima_de` estritamente maior.
