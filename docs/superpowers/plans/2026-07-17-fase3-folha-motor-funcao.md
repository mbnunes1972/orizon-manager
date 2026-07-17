# Folha de Pagamento — Fase 3: Motor Calculando pela Função

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o motor da Folha calcular a remuneração a partir da **Função** do funcionário (salário fixo + comissão + benefícios), com base de comissão editável na Folha e lançamento contábil dos benefícios.

**Architecture:** `mod_folha.calcular_folha` deixa de ler `funcionario.remuneracao_fixa/tipo` (legado, esvaziado na Fase 2) e passa a resolver pela `Funcao` vinculada (`funcionario.funcao_id`): `salario_fixo`, `comissao_json`/`usa_comissao_vendas` e `beneficios_json`. A base da comissão vira coluna editável (`base_comissao`) no registro da folha; editá-la recalcula o pct da faixa e a parte variável. O `pagar` posta três despesas (fixa→5.3.06, variável→5.3.01, benefícios→5.3.16). Frontend exibe as novas colunas e permite editar a base.

**Tech Stack:** Python (http.server + SQLAlchemy), pytest (SQLite default; suíte também validada contra Postgres), frontend single-file `static/index.html`.

**Convenções do repo (obrigatório):**
- Coluna nova em modelo → adicionar em **AMBOS** os caminhos de migração: `_add_cols(...)` (SQLite, PRAGMA) **e** `_migrar_colunas_pg()` (Postgres, `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`). Dev roda em Postgres.
- Backend via TDD. Frontend verificado com `node --check` (extrair maior `<script>` no WSL).
- Trabalhar em worktree sob `.claude/worktrees/`; FF-merge para `main`. **Não** commitar `perfis_config.json` (runtime) nem tocar no WIP de migração do usuário.
- Push só quando o usuário pedir.

---

## Estruturas de dados

**`Funcao` (já existe, Fase 1):**
- `salario_fixo` (Float) — parte fixa mensal.
- `usa_comissao_vendas` (Integer 0/1) — 1 = comissão vem do `comissao_vendas` da loja (Consultor).
- `comissao_json` (Text) — `{"por_meta": bool, "base": float, "pct": float, "faixas": [{"venda_ate": float|null, "pct": float}]}` (funções não-consultor).
- `beneficios_json` (Text) — `{"at": {"on": bool, "valor": float}, "va": {...}, "ps": {...}}`.

**`FolhaPagamento` (colunas novas nesta fase):**
- `base_comissao` (Float, default 0.0) — base efetiva da comissão, **editável**. Inicializada no auto-cálculo (consultor: vendas líquidas; demais: 0).
- `beneficios` (Float, default 0.0) — soma dos benefícios ativos da função.

**Retorno de `calcular_folha`** passa a incluir `base_comissao` e `beneficios`:
```python
{"parte_fixa": float, "vendas_liq": float, "base_comissao": float,
 "faixa_pct": float, "parte_variavel": float, "beneficios": float, "total": float}
```
- `vendas_liq` = referência auto do consultor (só display; 0 para não-consultor).
- `base_comissao` = base usada no cálculo do pct/variável (editável).
- `total` = `parte_fixa + parte_variavel + beneficios`.

---

## File Structure

- `database.py` — modelo `FolhaPagamento` (+2 colunas) + `_add_cols("folha_pagamento", ...)` (SQLite) + `_migrar_colunas_pg()` (Postgres).
- `mod_contabil.py` — conta `5.3.16` no plano + evento `folha_beneficios` no dict `EVENTOS`.
- `mod_folha.py` — reescrever `calcular_folha` (resolve pela Função) + helper `_resolver_pct_funcao` + helper `recalcular_variavel` (para PATCH) + `gerar_folha` (persistir novas colunas) + `pagar` (postar benefícios) + `serialize`/`listar` (expor colunas).
- `main.py` — endpoint `PATCH /api/folha/<id>` (editar `base_comissao`).
- `static/index.html` — `folhaRender` (colunas fixa/base editável/%/variável/benefícios/total) + `folhaSalvarBase(id, valor)`.
- `tests/test_folha.py` — reescrever fixtures para montar remuneração na **Função**; novos testes de benefícios e base editável.

---

### Task 1: Colunas `base_comissao` + `beneficios` no modelo (migração dupla)

**Files:**
- Modify: `database.py` (modelo `FolhaPagamento` ~linha 273; `_add_cols` ~linha 1326; `_migrar_colunas_pg` ~linha 1069)
- Test: `tests/test_folha.py`

- [ ] **Step 1: Escrever teste que falha (colunas existem e default 0)**

Adicionar em `tests/test_folha.py`:
```python
def test_folha_pagamento_tem_colunas_base_e_beneficios(app_db):
    cols = {c.name for c in app_db.FolhaPagamento.__table__.columns}
    assert "base_comissao" in cols
    assert "beneficios" in cols
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py::test_folha_pagamento_tem_colunas_base_e_beneficios -q`
Expected: FAIL (AssertionError — colunas ausentes).

- [ ] **Step 3: Adicionar colunas ao modelo**

Em `database.py`, na classe `FolhaPagamento`, logo após `parte_variavel = Column(...)`:
```python
    base_comissao  = Column(Float,       nullable=True, default=0.0)   # base editável da comissão
    beneficios     = Column(Float,       nullable=True, default=0.0)   # Σ AT/VA/PS ativos da função
```

- [ ] **Step 4: Migração SQLite (`_add_cols`)**

Em `database.py`, junto às demais chamadas `_add_cols(...)` (após a de `"funcoes"`):
```python
        _add_cols("folha_pagamento", [("base_comissao", "FLOAT"), ("beneficios", "FLOAT")])
```

- [ ] **Step 5: Migração Postgres (`_migrar_colunas_pg`)**

Em `database.py`, dentro de `_migrar_colunas_pg()`, acrescentar (seguindo o padrão `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` já usado na função):
```python
        ("folha_pagamento", "base_comissao", "DOUBLE PRECISION"),
        ("folha_pagamento", "beneficios",    "DOUBLE PRECISION"),
```
(Se `_migrar_colunas_pg` usar outra estrutura — ex. lista de statements — inserir os dois `ALTER TABLE folha_pagamento ADD COLUMN IF NOT EXISTS ...` no mesmo formato dos vizinhos. Ler a função antes de editar.)

- [ ] **Step 6: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py::test_folha_pagamento_tem_colunas_base_e_beneficios -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add database.py tests/test_folha.py
git commit -m "feat(folha): colunas base_comissao e beneficios em folha_pagamento (migração SQLite+PG)"
```

---

### Task 2: Conta 5.3.16 + evento contábil `folha_beneficios`

**Files:**
- Modify: `mod_contabil.py` (plano de contas 5.3.xx ~linha 85-92; dict `EVENTOS` ~linha 474)
- Test: `tests/test_folha.py`

- [ ] **Step 1: Escrever teste que falha (evento resolve conta 5.3.16)**

Em `tests/test_folha.py`:
```python
def test_evento_folha_beneficios_mapeia_5316():
    import mod_contabil as mc
    deb, cred, _desc = mc.EVENTOS["folha_beneficios"]
    assert deb == "5.3.16"
    assert cred == "1.1.01"
    # conta existe no plano
    nomes = dict(mc.PLANO_DE_CONTAS) if isinstance(mc.PLANO_DE_CONTAS, (list, tuple)) else mc.PLANO_DE_CONTAS
    assert "5.3.16" in nomes
```
(Ajustar o acesso ao plano ao nome real da constante em `mod_contabil.py` — ler o topo do arquivo para confirmar se é `PLANO_DE_CONTAS`/`CONTAS`/lista de tuplas.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py::test_evento_folha_beneficios_mapeia_5316 -q`
Expected: FAIL (KeyError `folha_beneficios`).

- [ ] **Step 3: Adicionar conta 5.3.16 ao plano**

Na lista de contas 5.3.xx (após `("5.3.15", ...)`):
```python
    ("5.3.16", "Benefícios a Funcionários (AT/VA/PS)"),
```

- [ ] **Step 4: Adicionar evento ao dict `EVENTOS`**

Logo após a linha `"folha_variavel": (...)`:
```python
    "folha_beneficios":             ("5.3.16", "1.1.01",    "Folha — benefícios (AT/VA/PS)"),
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py::test_evento_folha_beneficios_mapeia_5316 -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_contabil.py tests/test_folha.py
git commit -m "feat(contabil): conta 5.3.16 Benefícios a Funcionários + evento folha_beneficios"
```

---

### Task 3: Motor `calcular_folha` resolvendo pela Função

**Files:**
- Modify: `mod_folha.py` (`calcular_folha` linhas 37-48; imports linha 12; `gerar_folha` linhas 51-67)
- Test: `tests/test_folha.py` (reescrever fixtures — remuneração vai para a Função)

- [ ] **Step 1: Reescrever o teste fixa+variável do consultor usando Função**

Substituir `test_calcular_folha_fixa_mais_variavel` por versão que monta a remuneração na Função:
```python
def test_calcular_folha_consultor_fixa_mais_variavel(seed, app_db):
    db = app_db.get_session()
    u = db.query(app_db.Usuario).filter_by(login="cons_l1").first()   # consultor loja1
    loja = u.loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Consultor de Vendas", salario_fixo=2000.0,
                       usa_comissao_vendas=1, status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="Vend", funcao_id=fn.id, usuario_id=u.id, status="ativo")
    db.add(f); db.flush()
    db.add(app_db.Projeto(nome_safe="PFolha", loja_id=loja, criado_por_id=u.id,
                          status="fechado", status_at=datetime(2026, 7, 15)))
    db.add(app_db.Orcamento(projeto_id="PFolha", nome="O", ordem=1, loja_id=loja, valor_liquido=10000.0))
    db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", _cfg_pct(3.0))
    assert c["parte_fixa"] == 2000.0
    assert c["base_comissao"] == 10000.0     # consultor: base = vendas líquidas
    assert c["faixa_pct"] == 3.0
    assert c["parte_variavel"] == 300.0       # 10000 × 3%
    assert c["beneficios"] == 0.0
    assert c["total"] == 2300.0
    db.close()
```

- [ ] **Step 2: Escrever teste de benefícios (função com AT/VA/PS)**

```python
def test_calcular_folha_soma_beneficios_da_funcao(seed, app_db):
    import json
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    ben = {"at": {"on": True, "valor": 200.0}, "va": {"on": True, "valor": 500.0},
           "ps": {"on": False, "valor": 300.0}}
    fn = app_db.Funcao(loja_id=loja, nome="Montador", salario_fixo=1800.0,
                       usa_comissao_vendas=0, beneficios_json=json.dumps(ben), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="M", funcao_id=fn.id, status="ativo")
    db.add(f); db.commit()
    c = mod_folha.calcular_folha(db, loja, f, "2026-07", _cfg_pct(0.0))
    assert c["parte_fixa"] == 1800.0
    assert c["beneficios"] == 700.0           # AT 200 + VA 500 (PS off)
    assert c["parte_variavel"] == 0.0         # base editável inicia 0
    assert c["total"] == 2500.0               # 1800 + 0 + 700
    db.close()
```

- [ ] **Step 3: Escrever teste de comissão por meta (não-consultor, base editável já preenchida via cálculo)**

```python
def test_resolver_pct_funcao_por_meta():
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    assert mod_folha._resolver_pct_funcao(com, 50000.0) == 0.5    # até 100k → 0,5%
    assert mod_folha._resolver_pct_funcao(com, 150000.0) == 1.0   # acima → 1,0%

def test_resolver_pct_funcao_flat():
    com = {"por_meta": False, "pct": 2.0}
    assert mod_folha._resolver_pct_funcao(com, 999.0) == 2.0
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py -q -k "consultor_fixa or beneficios_da_funcao or resolver_pct_funcao"`
Expected: FAIL (`_resolver_pct_funcao` inexistente; retorno sem `base_comissao`/`beneficios`).

- [ ] **Step 5: Implementar `_resolver_pct_funcao` + reescrever `calcular_folha`**

Em `mod_folha.py`, ajustar import (linha 12) para incluir `Funcao`:
```python
from database import Funcionario, Funcao, Projeto, Orcamento, FolhaPagamento
```
Adicionar helpers e reescrever `calcular_folha`:
```python
import json


def _resolver_pct_funcao(com, base):
    """% da comissão de uma função não-consultor, dado o `com` (comissao_json) e a base.
    por_meta=True → resolve pela lista de faixas (venda_ate crescente; None = topo).
    por_meta=False → pct fixo."""
    com = com or {}
    if not com.get("por_meta"):
        return round(float(com.get("pct") or 0.0), 4)
    faixas = com.get("faixas") or []
    for fx in faixas:
        ate = fx.get("venda_ate")
        if ate is None or float(base) < float(ate):
            return round(float(fx.get("pct") or 0.0), 4)
    return round(float(faixas[-1].get("pct") or 0.0), 4) if faixas else 0.0


def _beneficios_total(funcao):
    try:
        b = json.loads(funcao.beneficios_json) if funcao and funcao.beneficios_json else {}
    except (ValueError, TypeError):
        b = {}
    total = 0.0
    for k in ("at", "va", "ps"):
        item = b.get(k) or {}
        if item.get("on"):
            total += float(item.get("valor") or 0.0)
    return round(total, 2)


def calcular_folha(db, loja_id, funcionario, competencia, cfg, base_override=None):
    """Calcula a remuneração a partir da FUNÇÃO do funcionário.
    Retorna dict com parte_fixa, vendas_liq, base_comissao, faixa_pct, parte_variavel, beneficios, total.
    `base_override` (se não None) força a base da comissão (usado ao editar na Folha)."""
    funcao = db.get(Funcao, funcionario.funcao_id) if funcionario.funcao_id else None
    fixa = float(funcao.salario_fixo or 0.0) if funcao else 0.0
    beneficios = _beneficios_total(funcao)
    vendas_liq = 0.0
    base = 0.0
    pct = 0.0
    if funcao and funcao.usa_comissao_vendas:
        vendas_liq = vendas_liquido_consultor(db, loja_id, funcionario.usuario_id, competencia)
        base = vendas_liq if base_override is None else float(base_override)
        pct = mod_provisoes.resolver_comissao_venda(cfg, base, 0.0)
    elif funcao and funcao.comissao_json:
        try:
            com = json.loads(funcao.comissao_json)
        except (ValueError, TypeError):
            com = {}
        base = float(com.get("base") or 0.0) if base_override is None else float(base_override)
        pct = _resolver_pct_funcao(com, base)
    variavel = round(base * pct / 100.0, 2)
    return {"parte_fixa": round(fixa, 2), "vendas_liq": round(vendas_liq, 2),
            "base_comissao": round(base, 2), "faixa_pct": pct, "parte_variavel": variavel,
            "beneficios": beneficios, "total": round(fixa + variavel + beneficios, 2)}
```

- [ ] **Step 6: Persistir novas colunas em `gerar_folha`**

Em `gerar_folha`, na atribuição do registro:
```python
        c = calcular_folha(db, loja_id, f, competencia, cfg)
        reg.parte_fixa = c["parte_fixa"]; reg.vendas_liq = c["vendas_liq"]; reg.faixa_pct = c["faixa_pct"]
        reg.base_comissao = c["base_comissao"]; reg.parte_variavel = c["parte_variavel"]
        reg.beneficios = c["beneficios"]; reg.total = c["total"]; reg.status = "aberta"
```

- [ ] **Step 7: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py -q`
Expected: PASS (ajustar quaisquer outros testes que ainda montem remuneração no funcionário — migrá-los para Função).

- [ ] **Step 8: Commit**

```bash
git add mod_folha.py tests/test_folha.py
git commit -m "feat(folha): motor calcula pela Funcao (salario_fixo + comissao/faixas + beneficios)"
```

---

### Task 4: Base de comissão editável — helper + `PATCH /api/folha/<id>`

**Files:**
- Modify: `mod_folha.py` (novo helper `editar_base`); `main.py` (rota PATCH)
- Test: `tests/test_folha.py`

- [ ] **Step 1: Escrever teste do helper de reedição da base**

```python
def test_editar_base_recalcula_variavel(seed, app_db):
    import json
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    com = {"por_meta": True, "faixas": [{"venda_ate": 100000.0, "pct": 0.5},
                                        {"venda_ate": None, "pct": 1.0}]}
    fn = app_db.Funcao(loja_id=loja, nome="CFO", salario_fixo=0.0, usa_comissao_vendas=0,
                       comissao_json=json.dumps(com), status="ativo")
    db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="X", funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07")
    db.add(reg); db.flush()
    mod_folha.editar_base(db, loja, reg, 150000.0, _cfg_pct(0.0))
    assert reg.base_comissao == 150000.0
    assert reg.faixa_pct == 1.0               # acima de 100k
    assert reg.parte_variavel == 1500.0       # 150000 × 1%
    assert reg.total == reg.parte_fixa + 1500.0 + (reg.beneficios or 0.0)
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py::test_editar_base_recalcula_variavel -q`
Expected: FAIL (`editar_base` inexistente).

- [ ] **Step 3: Implementar `editar_base` em `mod_folha.py`**

```python
def editar_base(db, loja_id, reg, base, cfg):
    """Reedita a base da comissão de um registro de folha (status != 'paga') e recalcula
    faixa_pct/parte_variavel/total. A parte fixa e os benefícios vêm da Função (não mudam aqui)."""
    if reg.status == "paga":
        return False, "folha já paga"
    f = db.get(Funcionario, reg.funcionario_id)
    c = calcular_folha(db, loja_id, f, reg.competencia, cfg, base_override=base)
    reg.base_comissao = c["base_comissao"]; reg.faixa_pct = c["faixa_pct"]
    reg.parte_variavel = c["parte_variavel"]; reg.parte_fixa = c["parte_fixa"]
    reg.beneficios = c["beneficios"]; reg.total = c["total"]
    db.flush()
    return True, None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py::test_editar_base_recalcula_variavel -q`
Expected: PASS.

- [ ] **Step 5: Adicionar rota `PATCH /api/folha/<id>` em `main.py`**

Localizar o handler das rotas `/api/folha` existentes (gerar/listar/pagar) e adicionar o ramo PATCH, seguindo o padrão de auth/tenancy já usado ali (resolver loja ativa, `_ator_dict`, ler `id` da URL, corpo JSON `{"base_comissao": <num>}`):
```python
# PATCH /api/folha/<id>  → edita base da comissão e recalcula
# (dentro do dispatch de /api/folha, ramo method == "PATCH")
reg = db.query(FolhaPagamento).filter_by(id=folha_id, loja_id=loja_id).first()
if reg is None:
    return _json(handler, 404, {"erro": "folha não encontrada"})
base = float((corpo or {}).get("base_comissao") or 0.0)
cfg = mod_provisoes.carregar_config(db, loja_id)   # mesma fonte de cfg usada em gerar/pagar
ok, err = mod_folha.editar_base(db, loja_id, reg, base, cfg)
if not ok:
    return _json(handler, 409, {"erro": err})
db.commit()
return _json(handler, 200, mod_folha.serialize(db, reg))
```
(Ajustar nomes: `folha_id`, `_json`, `carregar_config`/fonte de `cfg`, e a forma de extrair loja ativa exatamente como nas rotas irmãs de `/api/folha`. Ler o handler existente antes de editar.)

- [ ] **Step 6: Escrever teste de endpoint (via helper HTTP dos testes)**

Seguir o padrão de `tests/test_folha.py`/`test_endpoints*` para PATCH e assertar `base_comissao`/`parte_variavel` atualizados e bloqueio quando `status == "paga"` (409).

- [ ] **Step 7: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add mod_folha.py main.py tests/test_folha.py
git commit -m "feat(folha): base de comissao editavel — helper editar_base + PATCH /api/folha/<id>"
```

---

### Task 5: `pagar` posta despesa de benefícios

**Files:**
- Modify: `mod_folha.py` (`pagar` linhas 70-81)
- Test: `tests/test_folha.py`

- [ ] **Step 1: Escrever teste que falha (pagamento posta 3 eventos)**

```python
def test_pagar_posta_fixa_variavel_e_beneficios(seed, app_db, monkeypatch):
    import mod_folha
    postados = []
    def fake_registrar(db, ot, oid, evento, valor, ref=None):
        postados.append((evento, round(valor, 2)))
    monkeypatch.setattr(mod_folha.mod_contabil, "registrar_evento", fake_registrar)
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=1, competencia="2026-07",
                                parte_fixa=1800.0, parte_variavel=300.0, beneficios=700.0,
                                total=2800.0, status="aberta")
    db.add(reg); db.flush()
    ok, err = mod_folha.pagar(db, "loja", loja, reg)
    assert ok and reg.status == "paga"
    assert ("folha_fixa", 1800.0) in postados
    assert ("folha_variavel", 300.0) in postados
    assert ("folha_beneficios", 700.0) in postados
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py::test_pagar_posta_fixa_variavel_e_beneficios -q`
Expected: FAIL (evento `folha_beneficios` não é postado).

- [ ] **Step 3: Adicionar o lançamento de benefícios em `pagar`**

Após o bloco `if (reg.parte_variavel or 0) > 0:`:
```python
    if (reg.beneficios or 0) > 0:
        mod_contabil.registrar_evento(db, owner_tipo, owner_id, "folha_beneficios", reg.beneficios, ref=ref + ":ben")
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py::test_pagar_posta_fixa_variavel_e_beneficios -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_folha.py tests/test_folha.py
git commit -m "feat(folha): pagar posta despesa de beneficios (folha_beneficios -> 5.3.16)"
```

---

### Task 6: `serialize`/`listar` expõem base editável e benefícios

**Files:**
- Modify: `mod_folha.py` (`serialize` linhas 94-99; `listar` linhas 102-110)
- Test: `tests/test_folha.py`

- [ ] **Step 1: Escrever teste que falha (serialize inclui campos novos)**

```python
def test_serialize_e_listar_expoem_base_e_beneficios(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="Z", status="ativo"); db.add(f); db.flush()
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
                                parte_fixa=1000.0, base_comissao=5000.0, parte_variavel=50.0,
                                beneficios=200.0, total=1250.0, status="aberta")
    db.add(reg); db.commit()
    d = mod_folha.serialize(db, reg)
    assert d["base_comissao"] == 5000.0 and d["beneficios"] == 200.0
    out = mod_folha.listar(db, loja, "2026-07")
    assert out["total_beneficios"] == 200.0
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_folha.py::test_serialize_e_listar_expoem_base_e_beneficios -q`
Expected: FAIL (KeyError `base_comissao`/`total_beneficios`).

- [ ] **Step 3: Atualizar `serialize` e `listar`**

`serialize` — acrescentar ao dict:
```python
            "base_comissao": reg.base_comissao, "beneficios": reg.beneficios,
```
`listar` — acrescentar ao dict de retorno:
```python
            "total_beneficios": round(sum(x["beneficios"] or 0 for x in itens), 2),
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_folha.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_folha.py tests/test_folha.py
git commit -m "feat(folha): serialize/listar expoem base_comissao, beneficios e total_beneficios"
```

---

### Task 7: Frontend — Folha do mês com base editável e benefícios

**Files:**
- Modify: `static/index.html` (`folhaRender` / `folhaMesCarregar`; usa `#folha-mes-box`)

- [ ] **Step 1: Localizar `folhaRender` e a montagem da tabela da folha do mês**

Run (WSL): `grep -n "folhaRender\|folha-mes-box\|parte_variavel\|/api/folha" static/index.html`
Ler o trecho para casar com o padrão de tabela/coluna já usado.

- [ ] **Step 2: Adicionar colunas Base (editável), Benefícios e ajustar Totais**

No cabeçalho da tabela da folha do mês, incluir colunas `Fixo`, `Base comissão`, `%`, `Variável`, `Benefícios`, `Total`. Na linha de cada item, a célula **Base** é um input editável (somente quando `status !== 'paga'`):
```javascript
`<td class="num">${status==='paga'
   ? fmtBRL(it.base_comissao)
   : `<input type="number" step="0.01" value="${it.base_comissao||0}" class="inp-base"
        style="width:120px;text-align:right"
        onchange="folhaSalvarBase(${it.id}, this.value)">`}</td>`
```
Colunas `Benefícios` (`fmtBRL(it.beneficios)`) e `Total` (`fmtBRL(it.total)`). No rodapé, somar `total_fixa`, `total_variavel`, `total_beneficios`, `total_geral`.

- [ ] **Step 3: Implementar `folhaSalvarBase`**

Próximo às funções da folha:
```javascript
async function folhaSalvarBase(id, valor){
  const r = await api('/api/folha/'+id, {method:'PATCH', body:{base_comissao: parseFloat(valor)||0}});
  if(r && !r.erro){ folhaMesCarregar(); }   // recarrega para refletir pct/variável/total recalculados
  else { toast((r&&r.erro)||'Erro ao salvar base'); }
}
```
(Usar o wrapper HTTP e o `toast` reais do arquivo — confirmar nomes `api`/`toast`/`fmtBRL`/`folhaMesCarregar` no código.)

- [ ] **Step 4: Verificar sintaxe do frontend**

Extrair o maior `<script>` e rodar `node --check` (WSL), como no fluxo padrão do repo. Expected: `JS_OK`.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(folha/ui): folha do mes com base de comissao editavel + coluna Beneficios"
```

---

## Verificação final

- [ ] Rodar suíte completa: `python3 -m pytest -q` (SQLite). Expected: verde.
- [ ] Conferir migração Postgres: subir o app com `DATABASE_URL` de dev e confirmar que `folha_pagamento.base_comissao`/`beneficios` existem (sem crash de coluna ausente).
- [ ] Smoke manual: gerar folha do mês, editar a base de um consultor/não-consultor, confirmar recálculo de %/variável/total; pagar e conferir os 3 lançamentos (5.3.06 / 5.3.01 / 5.3.16).
- [ ] FF-merge para `main`. **Não** commitar `perfis_config.json`. Push só quando o usuário pedir.

---

## Self-Review (cobertura da spec)

- Motor pela Função (fixa + comissão + benefícios) → Tasks 3, 5, 6. ✅
- Comissão do Consultor mantém `resolver_comissao_venda` + acrescenta fixa → Task 3. ✅
- Comissão não-consultor por meta (faixas com o "próximo campo de %") ou pct fixo → Task 3 (`_resolver_pct_funcao`). ✅
- Base de comissão editável na Folha → Task 4 (`editar_base` + PATCH). ✅
- Benefícios AT/VA/PS com valores, compondo despesa → Tasks 3, 5 (conta 5.3.16). ✅
- Migração dupla SQLite+Postgres → Task 1. ✅
- Frontend exibindo/editando → Task 7. ✅

**Fora de escopo (documentado):** cálculo de comissão de papéis não-consultor via Mapa de Atribuições (fase futura); níveis de salário por função; conta contábil definitiva dos benefícios (a validar com a contabilidade — 5.3.16 é provisória).
