# Persistência dos parâmetros de negociação por orçamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir, no banco e por orçamento, as margens de negociação (12 chaves) e o desconto individual por ambiente — hoje guardados em `projeto.json` (compartilhado) e no `localStorage`, respectivamente.

**Architecture:** A coluna `orcamentos.margens` (TEXT, já existe) passa a ser a fonte oficial das margens (JSON por orçamento). Uma nova coluna `orcamento_ambientes.desconto_individual_pct` guarda o desconto por ambiente. Lógica pura de validação/merge fica em `mod_orcamento_params.py` (testável); `main.py` só faz o wiring HTTP. Uma migração idempotente copia as margens existentes do `projeto.json` para os orçamentos. O frontend passa a carregar/salvar margens e descontos por orçamento ativo.

**Tech Stack:** Python stdlib `http.server` (sem framework), SQLAlchemy + SQLite, pytest, SPA em `static/index.html` (vanilla JS), Playwright para verificação de UI.

**Convenção de testes deste repo:** funções puras e modelos são testados com pytest (fixture `setup_db` estilo `tests/test_briefing.py`); os handlers HTTP são verificados via **API real + Playwright** (ver histórico no `DEV_LOG.md`), não por pytest. Este plano segue essa convenção: Tasks 1–3 são TDD com pytest; Tasks 4–7 são wiring verificado end-to-end na Task 8.

---

## File Structure

- `database.py` — adiciona coluna `desconto_individual_pct` em `_migrar_colunas`; adiciona função `migrar_margens_para_orcamentos(session, projetos_dir)`.
- `mod_orcamento_params.py` *(novo)* — `MARGENS_DEFAULT`, `merge_margens(atual, req)`, `sanear_descontos(pares, ids_validos)`. Lógica pura, sem I/O.
- `main.py` — novos handlers `POST /api/orcamentos/<id>/margens` e `PUT /api/orcamentos/<id>/descontos`; GET ambientes inclui `margens` + `desconto_individual_pct`; criação de orçamento copia margens da origem; remove handler `POST /projetos/<nome>/margens`; chama a migração no startup.
- `static/index.html` — carregar/salvar margens e descontos por orçamento; `confirmarNovoOrc` envia `origem_id`; remove usos da rota antiga.
- `tests/test_orcamento_params.py` *(novo)* — testes das funções puras.
- `tests/test_orcamento_persistencia.py` *(novo)* — coluna nova + migração.

---

## Task 1: Coluna `desconto_individual_pct` em `orcamento_ambientes`

**Files:**
- Modify: `database.py` (classe `OrcamentoAmbiente` ~273-283; função `_migrar_colunas` ~410-419)
- Test: `tests/test_orcamento_persistencia.py` (novo)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orcamento_persistencia.py
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    import database
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DB_PATH", db_file)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=engine))
    database.init_db()
    yield


def test_desconto_individual_pct_persiste():
    from database import get_session, PoolAmbiente, Orcamento, OrcamentoAmbiente
    db = get_session()
    o = Orcamento(projeto_id="Proj_X", nome="Orçamento 1", ordem=1)
    pa = PoolAmbiente(projeto_id="Proj_X", nome="Cozinha", nome_exibicao="Cozinha",
                      xml_path="x.xml", ambientes_json="[]", budget_total=100.0, order_total=100.0)
    db.add_all([o, pa]); db.commit(); db.refresh(o); db.refresh(pa)
    link = OrcamentoAmbiente(orcamento_id=o.id, pool_ambiente_id=pa.id, ordem=1,
                             desconto_individual_pct=7.5)
    db.add(link); db.commit()
    lido = db.query(OrcamentoAmbiente).filter_by(orcamento_id=o.id, pool_ambiente_id=pa.id).first()
    assert lido.desconto_individual_pct == 7.5
    db.close()


def test_desconto_individual_pct_default_zero():
    from database import get_session, PoolAmbiente, Orcamento, OrcamentoAmbiente
    db = get_session()
    o = Orcamento(projeto_id="Proj_Y", nome="Orçamento 1", ordem=1)
    pa = PoolAmbiente(projeto_id="Proj_Y", nome="Sala", nome_exibicao="Sala",
                      xml_path="s.xml", ambientes_json="[]", budget_total=50.0, order_total=50.0)
    db.add_all([o, pa]); db.commit(); db.refresh(o); db.refresh(pa)
    link = OrcamentoAmbiente(orcamento_id=o.id, pool_ambiente_id=pa.id, ordem=1)
    db.add(link); db.commit()
    lido = db.query(OrcamentoAmbiente).filter_by(orcamento_id=o.id).first()
    assert (lido.desconto_individual_pct or 0) == 0
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orcamento_persistencia.py -v`
Expected: FAIL (`TypeError: 'desconto_individual_pct' is an invalid keyword argument` ou AttributeError).

- [ ] **Step 3: Add the column to the model**

Em `database.py`, na classe `OrcamentoAmbiente`, após a linha `added_at = Column(...)`:

```python
    desconto_individual_pct = Column(Float, nullable=False, default=0.0, server_default="0")
```

- [ ] **Step 4: Add the column to `_migrar_colunas`**

Em `database.py`, dentro de `_migrar_colunas`, após o bloco `# ── orcamentos ──` (antes de `# ── briefings ──`), acrescente:

```python
        # ── orcamento_ambientes ───────────────────────────────────────────────
        cur.execute("PRAGMA table_info(orcamento_ambientes)")
        oa_cols = {row[1] for row in cur.fetchall()}
        if "desconto_individual_pct" not in oa_cols:
            cur.execute("ALTER TABLE orcamento_ambientes "
                        "ADD COLUMN desconto_individual_pct REAL NOT NULL DEFAULT 0")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_orcamento_persistencia.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_orcamento_persistencia.py
git commit -m "feat(banco): coluna desconto_individual_pct em orcamento_ambientes"
```

---

## Task 2: Módulo puro `mod_orcamento_params.py`

**Files:**
- Create: `mod_orcamento_params.py`
- Test: `tests/test_orcamento_params.py` (novo)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_orcamento_params.py
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mod_orcamento_params import MARGENS_DEFAULT, merge_margens, sanear_descontos


def test_merge_usa_defaults_quando_vazio():
    out = merge_margens({}, {})
    assert out == MARGENS_DEFAULT
    assert out["carga_trib"] == 8.0
    assert out["incluir_custos"] is False


def test_merge_atualiza_apenas_enviados_preservando_resto():
    atual = dict(MARGENS_DEFAULT, comissao_arq_pct=10.0, comissao_arq_ativa=True)
    out = merge_margens(atual, {"desconto_pct": 5})
    assert out["desconto_pct"] == 5.0
    assert out["comissao_arq_pct"] == 10.0      # preservado
    assert out["comissao_arq_ativa"] is True    # preservado


def test_merge_coage_tipos():
    out = merge_margens({}, {"desconto_pct": "12.5", "fora_da_sede": 1, "brinde": "300"})
    assert out["desconto_pct"] == 12.5
    assert out["fora_da_sede"] is True
    assert out["brinde"] == 300.0


def test_sanear_descontos_filtra_ids_fora_do_orcamento():
    out = sanear_descontos({"1": 5, "2": 10, "99": 50}, ids_validos={1, 2})
    assert out == {1: 5.0, 2: 10.0}     # 99 ignorado


def test_sanear_descontos_rejeita_fora_de_faixa():
    with pytest.raises(ValueError):
        sanear_descontos({"1": 150}, ids_validos={1})
    with pytest.raises(ValueError):
        sanear_descontos({"1": -1}, ids_validos={1})


def test_sanear_descontos_aceita_limites():
    out = sanear_descontos({"1": 0, "2": 100}, ids_validos={1, 2})
    assert out == {1: 0.0, 2: 100.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orcamento_params.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'mod_orcamento_params'`).

- [ ] **Step 3: Write the module**

```python
# mod_orcamento_params.py
"""Lógica pura dos parâmetros de negociação por orçamento (sem I/O).

- MARGENS_DEFAULT: valores padrão das 12 chaves de margens.
- merge_margens(atual, req): aplica sobre `atual` somente as chaves enviadas em `req`,
  coagindo tipos. Espelha o merge que antes vivia no handler POST /projetos/<nome>/margens.
- sanear_descontos(pares, ids_validos): normaliza {pool_ambiente_id: pct}, filtra ids fora
  do orçamento e exige 0 <= pct <= 100.
"""

MARGENS_DEFAULT = {
    "desconto_pct":         0.0,
    "custo_financeiro_pct": 0.0,
    "custo_viagem":         0.0,
    "fora_da_sede":         False,
    "brinde":               0.0,
    "brinde_ativo":         False,
    "comissao_arq_pct":     0.0,
    "comissao_arq_ativa":   False,
    "fidelidade_pct":       0.0,
    "fidelidade_ativa":     False,
    "incluir_custos":       False,
    "carga_trib":           8.0,
}

_FLOAT_KEYS = ("desconto_pct", "custo_financeiro_pct", "custo_viagem", "brinde",
               "comissao_arq_pct", "fidelidade_pct", "carga_trib")
_BOOL_KEYS  = ("fora_da_sede", "brinde_ativo", "comissao_arq_ativa",
               "fidelidade_ativa", "incluir_custos")


def merge_margens(atual: dict, req: dict) -> dict:
    base = dict(MARGENS_DEFAULT)
    if atual:
        base.update({k: atual[k] for k in MARGENS_DEFAULT if k in atual})
    for k in _FLOAT_KEYS:
        if k in req:
            base[k] = float(req[k])
    for k in _BOOL_KEYS:
        if k in req:
            base[k] = bool(req[k])
    return base


def sanear_descontos(pares, ids_validos) -> dict:
    ids_validos = set(ids_validos)
    out = {}
    itens = pares.items() if isinstance(pares, dict) else pares
    for pid, pct in itens:
        pid = int(pid)
        if pid not in ids_validos:
            continue
        pct = float(pct)
        if pct < 0 or pct > 100:
            raise ValueError(f"Desconto fora da faixa 0..100: {pct}")
        out[pid] = pct
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orcamento_params.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add mod_orcamento_params.py tests/test_orcamento_params.py
git commit -m "feat(orcamento): modulo puro de margens e descontos por orcamento"
```

---

## Task 3: Migração `migrar_margens_para_orcamentos`

**Files:**
- Modify: `database.py` (nova função no nível de módulo)
- Test: `tests/test_orcamento_persistencia.py` (acrescenta testes)

- [ ] **Step 1: Write the failing test** (acrescente ao final de `tests/test_orcamento_persistencia.py`)

```python
def _escrever_projeto_json(tmp_path, nome_safe, margens):
    import json
    d = tmp_path / nome_safe
    d.mkdir(parents=True, exist_ok=True)
    (d / "projeto.json").write_text(
        json.dumps({"nome_safe": nome_safe, "margens": margens}, ensure_ascii=False),
        encoding="utf-8")
    return str(tmp_path)


def test_migracao_copia_margens_do_projeto_json(tmp_path):
    import json
    from database import get_session, Orcamento, migrar_margens_para_orcamentos
    db = get_session()
    db.add(Orcamento(projeto_id="Proj_M", nome="Orçamento 1", ordem=1)); db.commit()
    projetos_dir = _escrever_projeto_json(tmp_path, "Proj_M",
                                          {"desconto_pct": 5.0, "carga_trib": 8.0})
    n = migrar_margens_para_orcamentos(db, projetos_dir)
    assert n == 1
    o = db.query(Orcamento).filter_by(projeto_id="Proj_M").first()
    assert json.loads(o.margens)["desconto_pct"] == 5.0
    db.close()


def test_migracao_idempotente_nao_sobrescreve(tmp_path):
    import json
    from database import get_session, Orcamento, migrar_margens_para_orcamentos
    db = get_session()
    db.add(Orcamento(projeto_id="Proj_I", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"desconto_pct": 99.0}))); db.commit()
    projetos_dir = _escrever_projeto_json(tmp_path, "Proj_I", {"desconto_pct": 5.0})
    n = migrar_margens_para_orcamentos(db, projetos_dir)
    assert n == 0   # já tinha margens → não toca
    o = db.query(Orcamento).filter_by(projeto_id="Proj_I").first()
    assert json.loads(o.margens)["desconto_pct"] == 99.0
    # 2ª passada também é no-op
    assert migrar_margens_para_orcamentos(db, projetos_dir) == 0
    db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orcamento_persistencia.py -k migracao -v`
Expected: FAIL (`ImportError: cannot import name 'migrar_margens_para_orcamentos'`).

- [ ] **Step 3: Write the migration function** em `database.py` (nível de módulo, após `_run_migracoes`)

```python
def migrar_margens_para_orcamentos(session, projetos_dir):
    """Copia margens de cada PROJETOS/<nome>/projeto.json para os Orcamentos do projeto
    que ainda estão sem margens. Idempotente: só preenche margens vazias/nulas.
    Retorna o nº de orçamentos atualizados."""
    import glob, json, os
    atualizados = 0
    for pj in glob.glob(os.path.join(projetos_dir, "*", "projeto.json")):
        try:
            data = json.loads(open(pj, encoding="utf-8").read())
        except Exception:
            continue
        margens = data.get("margens")
        if not margens:
            continue
        nome_safe = data.get("nome_safe") or os.path.basename(os.path.dirname(pj))
        for o in session.query(Orcamento).filter_by(projeto_id=nome_safe).all():
            if not o.margens:
                o.margens = json.dumps(margens, ensure_ascii=False)
                atualizados += 1
    if atualizados:
        session.commit()
    return atualizados
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orcamento_persistencia.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Wire into startup** — em `main.py`, logo após `init_db()` (linha ~3129):

```python
    init_db()
    try:
        _db_mig = get_session()
        from database import migrar_margens_para_orcamentos
        migrar_margens_para_orcamentos(_db_mig, PROJETOS_DIR)
        _db_mig.close()
    except Exception as _e:
        print("[MIGRACAO] margens->orcamento:", _e)
```

- [ ] **Step 6: Commit**

```bash
git add database.py main.py tests/test_orcamento_persistencia.py
git commit -m "feat(banco): migracao idempotente de margens do projeto.json para orcamentos"
```

---

## Task 4: Handler `POST /api/orcamentos/<id>/margens`

**Files:**
- Modify: `main.py` (no bloco `do_POST`, junto aos handlers de orçamento ~1497)

- [ ] **Step 1: Add the handler** — em `main.py`, dentro de `do_POST`, antes do handler `POST /projetos/<nome>/orcamentos` (linha ~1497):

```python
            # ── POST /api/orcamentos/<id>/margens — salva margens do orçamento ─────
            m_orc_mar = _re.match(r"^/api/orcamentos/(\d+)/margens$", path)
            if m_orc_mar:
                oid = int(m_orc_mar.group(1))
                db = get_session()
                try:
                    from mod_orcamento_params import merge_margens
                    req = json.loads(body.decode("utf-8", "replace")) if body else {}
                    orc = db.get(Orcamento, oid)
                    if not orc:
                        self.send_json({"ok": False, "erro": "Orçamento não encontrado"}, code=404)
                        return
                    if _projeto_bloqueado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                       code=400)
                        return
                    atual = json.loads(orc.margens) if orc.margens else {}
                    novas = merge_margens(atual, req)
                    orc.margens = json.dumps(novas, ensure_ascii=False)
                    if "desconto_pct" in req:
                        orc.desconto_pct = float(req["desconto_pct"])
                    db.commit()
                    self.send_json({"ok": True, "margens": novas})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 2: Add the `_projeto_bloqueado` helper if missing**

Verifique se já existe um helper que diga se o projeto está bloqueado pós-aprovação. Procure:

Run: `python -c "import re,io; print('_projeto_bloqueado' in open('main.py',encoding='utf-8').read())"`

Se imprimir `False`, adicione perto dos outros helpers de projeto (ex.: após `_carregar_projeto`):

```python
def _projeto_bloqueado(nome_safe, db) -> bool:
    """True se o projeto está bloqueado para edição (orçamento aprovado).
    Reusa a marca usada pelo handler POST /projetos/<nome>/margens (campo `bloqueado`
    do projeto.json), preservando o comportamento atual."""
    proj = _carregar_projeto(nome_safe)
    return bool(proj and proj.get("bloqueado"))
```

> Nota: se já existir lógica de bloqueio diferente (ex.: via etapa 6 do ciclo / contrato), use-a em vez do `projeto.json`. Confirme com `grep -n "bloqueado" main.py mod_omie.py` antes de implementar e siga o padrão existente.

- [ ] **Step 3: Smoke check (sintaxe)**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(api): POST /api/orcamentos/<id>/margens (margens por orcamento)"
```

---

## Task 5: Handler `PUT /api/orcamentos/<id>/descontos`

**Files:**
- Modify: `main.py` (bloco `do_PUT`; se não existir, ver Step 2)

- [ ] **Step 1: Confirm `do_PUT` exists**

Run: `python -c "print('def do_PUT' in open('main.py',encoding='utf-8').read())"`
Expected: `True` (já há `PUT /projetos/<nome>/orcamentos/<oid>` para renomear). Caso `False`, replique a estrutura de `do_POST` para um método `do_PUT`.

- [ ] **Step 2: Add the handler** dentro de `do_PUT`, junto aos demais matches:

```python
            # ── PUT /api/orcamentos/<id>/descontos — descontos individuais em lote ──
            m_desc = _re.match(r"^/api/orcamentos/(\d+)/descontos$", path)
            if m_desc:
                oid = int(m_desc.group(1))
                db = get_session()
                try:
                    from mod_orcamento_params import sanear_descontos
                    req = json.loads(body.decode("utf-8", "replace")) if body else {}
                    pares = req.get("descontos", req)   # aceita {"descontos":{...}} ou {...}
                    orc = db.get(Orcamento, oid)
                    if not orc:
                        self.send_json({"ok": False, "erro": "Orçamento não encontrado"}, code=404)
                        return
                    if _projeto_bloqueado(orc.projeto_id, db):
                        self.send_json({"ok": False,
                                        "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."},
                                       code=400)
                        return
                    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=oid).all()
                    ids_validos = {lk.pool_ambiente_id for lk in links}
                    limpos = sanear_descontos(pares, ids_validos)
                    by_id = {lk.pool_ambiente_id: lk for lk in links}
                    for pid, pct in limpos.items():
                        by_id[pid].desconto_individual_pct = pct
                    db.commit()
                    self.send_json({"ok": True, "descontos": {str(k): v for k, v in limpos.items()}})
                except ValueError as ve:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(ve)}, code=400)
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

- [ ] **Step 3: Ensure `OrcamentoAmbiente` is imported in main.py**

Run: `python -c "print('OrcamentoAmbiente' in open('main.py',encoding='utf-8').read())"`
Expected: `True` (já usado nos handlers de ambiente). Se `False`, adicione ao import de `database`.

- [ ] **Step 4: Smoke check (sintaxe)**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(api): PUT /api/orcamentos/<id>/descontos (desconto por ambiente em lote)"
```

---

## Task 6: GET ambientes inclui margens + desconto; novo orçamento copia margens

**Files:**
- Modify: `main.py` (GET ambientes ~519-541; criação de orçamento ~1521-1530)

- [ ] **Step 1: Incluir `desconto_individual_pct` e `margens` no GET ambientes**

Em `main.py`, no handler `GET /orcamentos/<oid>/ambientes` (~519), substitua o corpo do `for lk in links` e o `send_json`:

```python
                    ambientes = []
                    for lk in links:
                        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                        if pa:
                            d = _pool_ambiente_dict(pa)
                            d["ordem"] = lk.ordem
                            d["desconto_individual_pct"] = lk.desconto_individual_pct or 0.0
                            ambientes.append(d)
                    orc = db.get(Orcamento, oid)
                    margens = json.loads(orc.margens) if (orc and orc.margens) else {}
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "margens": margens, "ambientes": ambientes})
```

- [ ] **Step 2: Copiar margens da origem ao criar orçamento**

Em `main.py`, no handler `POST /projetos/<nome>/orcamentos` (~1521), antes de `db.add(orc)`, leia `origem_id` do `req` e copie as margens:

```python
                    _origem_id = req.get("origem_id")
                    _margens_novo = None
                    if _origem_id:
                        _origem = db.get(Orcamento, int(_origem_id))
                        if _origem and _origem.margens:
                            _margens_novo = _origem.margens
                    orc = Orcamento(
                        projeto_id=nome_safe,
                        nome=      nome_orc,
                        ordem=     proxima_ordem,
                        margens=   _margens_novo,
                        created_by=_usuario['id'] if _usuario else None,
                    )
```

- [ ] **Step 3: Smoke check (sintaxe)**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(api): GET ambientes devolve margens+desconto; novo orcamento copia margens da origem"
```

---

## Task 7: Frontend — carregar/salvar por orçamento

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Ao ativar orçamento, carregar margens e descontos do servidor**

Em `_aplicarFiltroOrcamento` (~2495), após `_orcAmbientesAtivos = d.ambientes || [];` adicione:

```javascript
    if(projetoAtivo) projetoAtivo.margens = d.margens || {};
    _descIndividual = {};
    (d.ambientes || []).forEach(pa => {
      if(pa.desconto_individual_pct) _descIndividual['ep07_'+pa.id] = pa.desconto_individual_pct;
    });
    if(typeof carregarMargensSalvas === 'function') carregarMargensSalvas();
```

- [ ] **Step 2: Salvar margens no endpoint por-orçamento**

Em `fecharModalParams` (~5359) troque a URL do fetch:

De:
```javascript
      const r = await fetch('/projetos/'+encodeURIComponent(projetoAtivo.nome_safe)+'/margens',{
```
Para:
```javascript
      const r = await fetch('/api/orcamentos/'+_orcamentoAtivoId+'/margens',{
```

Em `salvarDescontoAutomatico` (~4811) troque a URL do fetch da mesma forma:

De:
```javascript
    const r = await fetch('/projetos/'+encodeURIComponent(projetoAtivo.nome_safe)+'/margens',{
```
Para:
```javascript
    const r = await fetch('/api/orcamentos/'+_orcamentoAtivoId+'/margens',{
```

- [ ] **Step 3: Persistir desconto individual no servidor**

Adicione uma função helper perto de `_onDescIndBlur` (~1788):

```javascript
async function _persistirDescontosOrc(){
  if(!_orcamentoAtivoId) return;
  const lote = {};
  Object.keys(_descIndividual).forEach(k => {
    if(k.startsWith('ep07_')) lote[k.slice(5)] = _descIndividual[k];
  });
  try{
    await fetch('/api/orcamentos/'+_orcamentoAtivoId+'/descontos',{
      method:'PUT', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({descontos: lote}),
    });
  }catch(e){}
}
```

No final de `_onDescIndBlur` (após a validação de limite, antes do fechamento da função), para o caminho EP-07, dispare a persistência:

```javascript
  if(isEP07) _persistirDescontosOrc();
```

- [ ] **Step 4: Novo orçamento envia `origem_id`**

Em `confirmarNovoOrc` (~2529), inclua `origem_id` no body:

De:
```javascript
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({nome})
```
Para:
```javascript
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({nome, origem_id: _orcamentoAtivoId})
```

- [ ] **Step 5: Smoke check — servir e abrir sem erro de console**

Inicie o app (ver `gui-verification-playwright`) e confirme no console do navegador que não há erro de sintaxe JS ao carregar `index.html`. (Verificação completa na Task 8.)

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(front): margens e descontos por orcamento (carrega/salva no banco)"
```

---

## Task 8: Aposentar a rota antiga `POST /projetos/<nome>/margens`

**Files:**
- Modify: `main.py` (remove handler ~1951-1982)

- [ ] **Step 1: Confirmar que o frontend não usa mais a rota antiga**

Run: `python -c "t=open('static/index.html',encoding='utf-8').read(); print(t.count(\"/margens'\"), 'ocorrencias /margens (deve ser por /api/orcamentos)')"`
Inspecione com `grep -n "nome_safe)+'/margens'" static/index.html` — não deve haver mais nenhuma ocorrência da rota por projeto.

- [ ] **Step 2: Remover o handler antigo**

Em `main.py`, remova o bloco inteiro do handler `# Rota: POST /projetos/<nome_safe>/margens` (~1951-1982), do comentário até o `return` final do bloco.

- [ ] **Step 3: Smoke check (sintaxe)**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "refactor(api): remove POST /projetos/<nome>/margens (substituido por endpoint por orcamento)"
```

---

## Task 9: Verificação end-to-end

**Files:** nenhum (apenas execução/verificação)

- [ ] **Step 1: Suíte pytest completa**

Run: `python -m pytest -q`
Expected: tudo verde (≥125 testes anteriores + os novos das Tasks 1–3).

- [ ] **Step 2: Verificação por API real**

Com o app rodando, exercite (via script Python `requests`/Playwright `fetch`, ver `contrato-verificacao-dados-reais` e `gui-verification-playwright`):
- `POST /api/orcamentos/<id>/margens` grava e `GET /orcamentos/<id>/ambientes` devolve as mesmas margens.
- Dois orçamentos do mesmo projeto com margens distintas → **isolamento** (alterar um não muda o outro).
- `PUT /api/orcamentos/<id>/descontos` grava; GET devolve `desconto_individual_pct`; pct fora de 0..100 → 400; id fora do orçamento ignorado.
- Criar orçamento com `origem_id` herda as margens; sem `origem_id` usa defaults.
- Gate de bloqueio: projeto aprovado → 400 nos dois endpoints.

- [ ] **Step 3: Verificação Playwright (UI, dados reais)**

- Abrir projeto, definir parâmetros e desconto por ambiente no Orçamento A; criar Orçamento B; confirmar que B começou com cópia de A e que editar B não altera A.
- Recarregar a página (novo "acesso", simulando outra máquina/cache limpo) e confirmar que o desconto individual e as margens **persistem** (vêm do servidor, não do localStorage).
- Console sem erros de página.

- [ ] **Step 4: Atualizar DEV_LOG e finalizar a branch**

- Acrescentar uma seção de sessão ao `DEV_LOG.md` descrevendo a mudança.
- Seguir `superpowers:finishing-a-development-branch` para revisão final e merge em `main`.

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — parametros de negociacao por orcamento"
```

---

## Self-Review (cobertura da spec)

- **Desconto individual no banco** → Tasks 1, 5, 7 (col + endpoint + UI).
- **Margens por orçamento no banco** → Tasks 2, 4, 6, 7.
- **Migração automática idempotente** → Task 3.
- **Orçamento novo copia margens da origem** → Task 6 (back) + Task 7 (front `origem_id`).
- **Forma antiga aposentada** → Task 8.
- **GET devolve margens + desconto** → Task 6.
- **Gate de bloqueio pós-aprovação** → Tasks 4 e 5.
- **Testes (isolamento, persistência, idempotência)** → Tasks 1–3 (pytest) + Task 9 (API/Playwright).
- **Tipos/nomes consistentes:** `merge_margens`, `sanear_descontos`, `migrar_margens_para_orcamentos`, `desconto_individual_pct`, `origem_id`, `_persistirDescontosOrc` — usados de forma idêntica em todas as tasks.
