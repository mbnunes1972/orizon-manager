# Fase 1 — Config › Remunerações (config por função) — Plano

> TDD no backend (`python3 -m pytest`, SQLite por padrão; **dev é Postgres** → coluna nova nos DOIS caminhos: `_add_cols` + `_migrar_colunas_pg`). Frontend com `node --check` (via WSL) + verificação manual. Spec: `docs/superpowers/specs/2026-07-17-remuneracoes-folha-design.md`.

**Goal:** a `Funcao` ganha a config de remuneração (salário fixo, comissão, benefícios) e o painel **Config › "Remunerações"** (renomeia "Comissão de Vendas") lista as funções, cada uma abrindo um **modal de remuneração**. Só config/armazenamento (o motor da Folha usa isso na Fase 3).

**Base:** branch `feat/folha-remuneracoes` (a partir da `main`).

---

## Task F1.1 (backend, TDD): colunas de remuneração na Função + serialize/aplicar

**Files:** `database.py` (modelo + migrações), `mod_cadastro.py` (funcao_serialize/aplicar), `tests/test_funcao_remuneracao.py`.

- [ ] **Step 1 — teste que falha** (`tests/test_funcao_remuneracao.py`):
```python
"""Fase 1: config de remuneração por Função — salário fixo, comissão (por meta?), benefícios."""


def _funcoes(c):
    _, d = c.get("/api/funcoes")
    return d.get("itens") or []


def _fid(app_db):
    db = app_db.get_session()
    lid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcao(loja_id=lid, nome="Montador X", status="ativo"); db.add(f); db.commit()
    fid = f.id; db.close(); return fid


def test_grava_remuneracao(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, out = c.post(f"/api/funcoes/{fid}", {
        "salario_fixo": 2500.50,
        "comissao": {"por_meta": False, "base": "fabrica", "pct": 3.0},
        "beneficios": {"at": {"on": True, "valor": 200.0},
                       "va": {"on": True, "valor": 600.0},
                       "ps": {"on": False, "valor": 0.0}},
    })
    assert out.get("ok"), out
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["salario_fixo"] == 2500.50
    assert fn["comissao"]["por_meta"] is False and fn["comissao"]["base"] == "fabrica" and fn["comissao"]["pct"] == 3.0
    assert fn["beneficios"]["at"]["on"] is True and fn["beneficios"]["at"]["valor"] == 200.0
    assert fn["beneficios"]["ps"]["on"] is False


def test_comissao_por_meta_e_base_invalida(http_client_factory, seed, app_db):
    fid = _fid(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post(f"/api/funcoes/{fid}", {"comissao": {"por_meta": True, "base": "xxx",
                                                "faixas": [{"venda_ate": 50000, "pct": 2.0}, {"venda_ate": None, "pct": 4.0}]}})
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["comissao"]["por_meta"] is True
    assert fn["comissao"]["base"] == "liquido"          # base inválida -> default liquido
    assert len(fn["comissao"]["faixas"]) == 2
```

- [ ] **Step 2:** `python3 -m pytest tests/test_funcao_remuneracao.py -q` → FAIL (campos inexistentes).

- [ ] **Step 3 — implementar.**
  (a) `database.py` modelo `Funcao` (após `descricao`):
```python
    salario_fixo        = Column(Float,   nullable=True)   # parte fixa mensal da função
    beneficios_json     = Column(Text,    nullable=True)   # {"at":{"on","valor"},"va":..,"ps":..}
    comissao_json       = Column(Text,    nullable=True)   # {"por_meta","base","pct"|"faixas"} (não-consultor)
    usa_comissao_vendas = Column(Integer, default=0)       # 1 = comissão vem do comissao_vendas da loja (Consultor)
```
  (b) `database.py` migração SQLite — estender o `_add_cols("funcoes", [...])`:
```python
                                   ("descricao", "TEXT"),
                                   ("salario_fixo", "REAL"),
                                   ("beneficios_json", "TEXT"),
                                   ("comissao_json", "TEXT"),
                                   ("usa_comissao_vendas", "INTEGER")])
```
  (c) `database.py` migração Postgres — em `_migrar_colunas_pg()` (após a linha `descricao`):
```python
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS salario_fixo DOUBLE PRECISION",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS beneficios_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS comissao_json TEXT",
        "ALTER TABLE funcoes ADD COLUMN IF NOT EXISTS usa_comissao_vendas INTEGER DEFAULT 0",
```
  (d) `mod_cadastro.py` — `funcao_serialize` acrescenta (helpers `_json`, `_s`, `_f` já existem):
```python
    def _load(s):
        try: return _json.loads(s or "null")
        except Exception: return None
    com = _load(getattr(f, "comissao_json", None)) or {}
    ben = _load(getattr(f, "beneficios_json", None)) or {}
    # ...no return, ACRESCENTAR:
        "salario_fixo": getattr(f, "salario_fixo", None),
        "usa_comissao_vendas": bool(getattr(f, "usa_comissao_vendas", 0)),
        "comissao": {"por_meta": bool(com.get("por_meta")),
                     "base": com.get("base") if com.get("base") in ("liquido", "fabrica") else "liquido",
                     "pct": com.get("pct"), "faixas": com.get("faixas") or []},
        "beneficios": {k: {"on": bool((ben.get(k) or {}).get("on")),
                           "valor": float((ben.get(k) or {}).get("valor") or 0.0)} for k in ("at", "va", "ps")},
```
  `funcao_aplicar` acrescenta (validação):
```python
    if "salario_fixo" in req:
        f.salario_fixo = _f(req.get("salario_fixo"))
    if "comissao" in req:
        cm = req.get("comissao") or {}
        base = cm.get("base"); base = base if base in ("liquido", "fabrica") else "liquido"
        out = {"por_meta": bool(cm.get("por_meta")), "base": base}
        if out["por_meta"]:
            out["faixas"] = [{"venda_ate": _f(fx.get("venda_ate")), "pct": _f(fx.get("pct")) or 0.0}
                             for fx in (cm.get("faixas") or []) if isinstance(fx, dict)]
        else:
            out["pct"] = _f(cm.get("pct")) or 0.0
        f.comissao_json = _json.dumps(out)
    if "beneficios" in req:
        bn = req.get("beneficios") or {}
        f.beneficios_json = _json.dumps({k: {"on": bool((bn.get(k) or {}).get("on")),
                                             "valor": _f((bn.get(k) or {}).get("valor")) or 0.0} for k in ("at", "va", "ps")})
```
  _(Nota: `usa_comissao_vendas` **não** entra pelo `funcao_aplicar` — é flag de sistema, semeada na F1.2.)_

- [ ] **Step 4:** `python3 -m pytest tests/test_funcao_remuneracao.py tests/test_funcao_campos.py -q` → verde.
- [ ] **Step 5 (regressão):** `python3 -m pytest tests/test_funcoes_seed.py tests/test_cronograma.py -q` → verde.
- [ ] **Step 6 (commit):** `git add database.py mod_cadastro.py tests/test_funcao_remuneracao.py && git commit -m "feat(funcoes): config de remuneração (salário fixo/comissão/benefícios) + migração SQLite/PG"`

## Task F1.2 (backend, TDD): semear `usa_comissao_vendas` no "Consultor de Vendas"

**Files:** `database.py` (seed `criar_funcoes_seed` + migração de backfill), `tests/test_funcao_remuneracao.py`.

- [ ] **Step 1 — teste** (acrescentar):
```python
def test_consultor_vendas_usa_comissao_da_loja(seed, app_db):
    from database import criar_funcoes_seed, Funcao, Session
    db = Session()
    lid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    criar_funcoes_seed(db, lid)   # idempotente
    cv = db.query(Funcao).filter_by(loja_id=lid, nome="Consultor de Vendas").first()
    assert cv is not None and bool(cv.usa_comissao_vendas) is True
    db.close()
```
- [ ] **Step 2:** rodar → FAIL (flag não semeada).
- [ ] **Step 3 — implementar:** em `criar_funcoes_seed`, ao criar/garantir a função, setar `usa_comissao_vendas=1` quando `nome == "Consultor de Vendas"`. Backfill idempotente em `_run_migracoes` (novo id em `schema_migrations`, ex.: `comissao_vendas_flag_v1`): `UPDATE funcoes SET usa_comissao_vendas=1 WHERE nome='Consultor de Vendas'`.
- [ ] **Step 4:** rodar → passa.
- [ ] **Step 5 (commit).**

## Task F1.3 (frontend): Config › "Remunerações" — lista de funções + modal por função

**Files:** `static/index.html` (rótulo da aba, `cfgComissaoRender`, novo modal + salvar).

- [ ] **Step 1 — renomear a aba:** o botão `cfg-tab-comissao` passa de "Comissão de Vendas" para **"Remunerações"**.
- [ ] **Step 2 — `cfgComissaoRender` vira lista de funções:** busca `/api/funcoes`, tabela com cada função + botão **"Remuneração"** por linha → `cfgRemuneracaoEditar(id)`.
- [ ] **Step 3 — modal `cfgRemuneracaoEditar(id)`** (dinâmico, como o modal de função do item 1): lê a função de um cache/refetch. Campos:
  - **Salário Fixo** (R$, `id="rm-fixo"`).
  - **Comissão:** checkbox **"por meta?"** (`rm-pormeta`) + select **base** (Líquido de Vendas / Custo Fábrica, `rm-base`). Se por meta desligado → input **% simples** (`rm-pct`). Se ligado → editor de **faixas** (venda_ate + pct, add/remover). **Exceção Consultor:** se `f.usa_comissao_vendas`, em vez do editor de comissão, mostrar aviso "Comissão de vendas por metas (usada também na negociação)" + botão **"Configurar comissão de vendas"** que abre o modal existente `abrirModalComissao(lid)` (grava no `comissao_vendas` da loja) — o resto do modal (fixo/benefícios) é igual.
  - **Benefícios:** AT/VA/PS, cada um checkbox (`rm-b-at-on`…) + valor R$ (`rm-b-at-val`…).
  - **Salvar** → `POST /api/funcoes/<id>` com `{salario_fixo, comissao:{por_meta,base,pct|faixas}, beneficios:{at,va,ps}}` (para o Consultor, a comissão vai pelo modal próprio; o salvar manda só fixo+benefícios).
- [ ] **Step 4:** `node --check` (extrair `<script>` + `node --check` via WSL) → `JS_OK`.
- [ ] **Step 5 (commit):** só `static/index.html`.

## Task F1.4: verificação + FF
- [ ] Suíte completa `python3 -m pytest -q` verde.
- [ ] Verificação manual: Config › Remunerações lista as funções; editar uma não-consultor (fixo + comissão por meta/simples + base + benefícios) → reabrir persiste; no Consultor, o botão de comissão de vendas abre o editor existente; fixo/benefícios salvam.
- [ ] FF na `main`; reiniciar o servidor (colunas novas → `_migrar_colunas_pg` no seu Postgres).

## Notas
- **usa_comissao_vendas** é flag de sistema (semeada), não editável na tela.
- **Consultor:** comissão continua no `config_financeira_json.comissao_vendas` da loja (alimenta a negociação); o modal reusa `abrirModalComissao`. As demais funções gravam em `comissao_json`.
- Fase 2 (Funcionários na Folha) e Fase 3 (motor calcula) vêm depois — planos próprios.
