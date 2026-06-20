# Parâmetros estruturais por projeto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mover os parâmetros estruturais da negociação (incluir custos, comissão do arquiteto, fidelidade, custo viagem, brinde, carga tributária) para o nível do PROJETO (compartilhados por todos os orçamentos), mantendo desconto e pagamento por orçamento.

**Architecture:** Nova coluna JSON `projetos_meta.parametros_json` guarda os 10 campos estruturais (fonte única do projeto). `orcamentos.margens` mantém só `desconto_pct` (+`custo_financeiro_pct` derivado). O frontend monta `projetoAtivo.margens` combinando os parâmetros do projeto com o `desconto_pct` do orçamento; ao salvar, separa estruturais (→ projeto) de desconto (→ orçamento).

**Tech Stack:** Python stdlib http.server + SQLAlchemy/SQLite; SPA vanilla-JS; pytest; Playwright.

**Convenção de testes:** lógica pura/modelos/migração → pytest; handlers HTTP + SPA → API real + Playwright. Tasks 1–3 são TDD pytest; Tasks 4–5 wiring verificado na Task 6.

**Campos estruturais (10):** `incluir_custos`, `comissao_arq_pct`, `comissao_arq_ativa`, `fidelidade_pct`, `fidelidade_ativa`, `fora_da_sede`, `custo_viagem`, `brinde`, `brinde_ativo`, `carga_trib`. (= margens menos `desconto_pct` e `custo_financeiro_pct`.)

---

## File Structure

- `database.py` — coluna `parametros_json` em `Projeto`; `_migrar_colunas`; função `migrar_parametros_para_projeto(session, ...)`.
- `mod_orcamento_params.py` — `PARAMETROS_DEFAULT` + `merge_parametros(atual, req)` (reusa `_coerce_bool`).
- `main.py` — GET/POST `/api/projetos/<nome>/parametros`; GET ambientes inclui `parametros`; POST margens persiste só `desconto_pct`; chama a migração no startup.
- `static/index.html` — load monta `projetoAtivo.margens` combinado; save separa estruturais/desconto.
- `tests/test_parametros_projeto.py` (novo).

---

## Task 1: Coluna `parametros_json` em `projetos_meta`

**Files:** Modify `database.py` (classe `Projeto` ~170-178; `_migrar_colunas`). Test: `tests/test_parametros_projeto.py` (novo).

- [ ] **Step 1: Write the failing test** — create `tests/test_parametros_projeto.py`:

```python
import pytest, sys, os, json
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


def test_parametros_json_persiste():
    from database import get_session, Projeto
    db = get_session()
    p = Projeto(nome_safe="Proj_P", parametros_json=json.dumps({"carga_trib": 8.0, "brinde": 300}))
    db.add(p); db.commit()
    lido = db.get(Projeto, "Proj_P")
    assert json.loads(lido.parametros_json)["brinde"] == 300
    db.close()


def test_parametros_json_default_none():
    from database import get_session, Projeto
    db = get_session()
    p = Projeto(nome_safe="Proj_P2")
    db.add(p); db.commit()
    assert db.get(Projeto, "Proj_P2").parametros_json is None
    db.close()
```

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/test_parametros_projeto.py -v` → FAIL (invalid keyword `parametros_json`).

- [ ] **Step 3: Add the column** — em `database.py`, classe `Projeto`, após `perdido_em = Column(...)`:

```python
    parametros_json = Column(Text, nullable=True)   # parâmetros estruturais da negociação (JSON, projeto-wide)
```

(`Text` já é importado em database.py.)

- [ ] **Step 4: Add to `_migrar_colunas`** — em `database.py`, no `_migrar_colunas`, no bloco `# ── projetos_meta ──` (onde já adiciona `cliente_id`), acrescentar:

```python
        if "parametros_json" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN parametros_json TEXT")
```

- [ ] **Step 5: Run to verify pass** — `python -m pytest tests/test_parametros_projeto.py -v` → 2 passed.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_parametros_projeto.py
git commit -m "feat(banco): coluna parametros_json em projetos_meta"
```

---

## Task 2: `PARAMETROS_DEFAULT` + `merge_parametros` (módulo puro)

**Files:** Modify `mod_orcamento_params.py`. Test: `tests/test_orcamento_params.py` (append).

- [ ] **Step 1: Write the failing test** — append to `tests/test_orcamento_params.py`:

```python
def test_parametros_default_tem_10_chaves_estruturais():
    from mod_orcamento_params import PARAMETROS_DEFAULT
    assert set(PARAMETROS_DEFAULT) == {
        "incluir_custos", "comissao_arq_pct", "comissao_arq_ativa",
        "fidelidade_pct", "fidelidade_ativa", "fora_da_sede", "custo_viagem",
        "brinde", "brinde_ativo", "carga_trib"}
    assert "desconto_pct" not in PARAMETROS_DEFAULT
    assert PARAMETROS_DEFAULT["carga_trib"] == 8.0


def test_merge_parametros_coage_e_preserva():
    from mod_orcamento_params import merge_parametros, PARAMETROS_DEFAULT
    atual = dict(PARAMETROS_DEFAULT, comissao_arq_pct=10.0)
    out = merge_parametros(atual, {"brinde": "300", "fora_da_sede": "true"})
    assert out["brinde"] == 300.0
    assert out["fora_da_sede"] is True
    assert out["comissao_arq_pct"] == 10.0      # preservado
    assert "desconto_pct" not in out            # estruturais não incluem desconto
```

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/test_orcamento_params.py -k parametros -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — em `mod_orcamento_params.py`, após `merge_margens` (reusa `_coerce_bool` já existente), adicionar:

```python
PARAMETROS_DEFAULT = {
    "incluir_custos":     False,
    "comissao_arq_pct":   0.0,
    "comissao_arq_ativa": False,
    "fidelidade_pct":     0.0,
    "fidelidade_ativa":   False,
    "fora_da_sede":       False,
    "custo_viagem":       0.0,
    "brinde":             0.0,
    "brinde_ativo":       False,
    "carga_trib":         8.0,
}

_PARAM_FLOAT_KEYS = ("comissao_arq_pct", "fidelidade_pct", "custo_viagem", "brinde", "carga_trib")
_PARAM_BOOL_KEYS  = ("incluir_custos", "comissao_arq_ativa", "fidelidade_ativa",
                     "fora_da_sede", "brinde_ativo")


def merge_parametros(atual: dict, req: dict) -> dict:
    base = dict(PARAMETROS_DEFAULT)
    if atual:
        base.update({k: atual[k] for k in PARAMETROS_DEFAULT if k in atual})
    for k in _PARAM_FLOAT_KEYS:
        if k in req:
            base[k] = float(req[k])
    for k in _PARAM_BOOL_KEYS:
        if k in req:
            base[k] = _coerce_bool(req[k])
    return base
```

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_orcamento_params.py -v` → all pass.

- [ ] **Step 5: Commit**

```bash
git add mod_orcamento_params.py tests/test_orcamento_params.py
git commit -m "feat(orcamento): PARAMETROS_DEFAULT + merge_parametros (estruturais do projeto)"
```

---

## Task 3: Migração `migrar_parametros_para_projeto`

**Files:** Modify `database.py` (função nova + wire no startup via main.py). Test: `tests/test_parametros_projeto.py` (append).

- [ ] **Step 1: Write the failing test** — append to `tests/test_parametros_projeto.py`:

```python
def test_migracao_copia_estruturais_do_orcamento():
    import json
    from database import get_session, Orcamento, Projeto, migrar_parametros_para_projeto
    db = get_session()
    db.add(Projeto(nome_safe="Proj_M", status="quente"))
    db.add(Orcamento(projeto_id="Proj_M", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"desconto_pct": 5.0, "carga_trib": 8.0,
                                         "comissao_arq_pct": 10.0, "brinde": 200})))
    db.commit()
    n = migrar_parametros_para_projeto(db)
    assert n == 1
    p = db.get(Projeto, "Proj_M")
    par = json.loads(p.parametros_json)
    assert par["comissao_arq_pct"] == 10.0 and par["brinde"] == 200
    assert "desconto_pct" not in par
    db.close()


def test_migracao_parametros_idempotente():
    import json
    from database import get_session, Orcamento, Projeto, migrar_parametros_para_projeto
    db = get_session()
    db.add(Projeto(nome_safe="Proj_I", status="quente",
                   parametros_json=json.dumps({"comissao_arq_pct": 99.0})))
    db.add(Orcamento(projeto_id="Proj_I", nome="Orçamento 1", ordem=1,
                     margens=json.dumps({"comissao_arq_pct": 10.0})))
    db.commit()
    assert migrar_parametros_para_projeto(db) == 0     # já tem parametros → não toca
    assert json.loads(db.get(Projeto, "Proj_I").parametros_json)["comissao_arq_pct"] == 99.0
    db.close()
```

- [ ] **Step 2: Run to verify fail** — `python -m pytest tests/test_parametros_projeto.py -k migracao -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — em `database.py`, nível de módulo (após `migrar_margens_para_orcamentos`):

```python
def migrar_parametros_para_projeto(session):
    """Copia os parâmetros estruturais de um orçamento existente para
    projetos_meta.parametros_json, para projetos que ainda não têm. Idempotente.
    Retorna o nº de projetos atualizados."""
    import json
    from mod_orcamento_params import PARAMETROS_DEFAULT
    atualizados = 0
    projetos = session.query(Projeto).filter(
        (Projeto.parametros_json.is_(None)) | (Projeto.parametros_json == "")
    ).all()
    for p in projetos:
        orc = (session.query(Orcamento)
                      .filter_by(projeto_id=p.nome_safe)
                      .order_by(Orcamento.updated_at.desc().nullslast(), Orcamento.id.desc())
                      .first())
        if not orc or not orc.margens:
            continue
        try:
            m = json.loads(orc.margens)
        except Exception:
            continue
        par = {k: m[k] for k in PARAMETROS_DEFAULT if k in m}
        if not par:
            continue
        p.parametros_json = json.dumps({**PARAMETROS_DEFAULT, **par}, ensure_ascii=False)
        atualizados += 1
    if atualizados:
        session.commit()
    return atualizados
```

NOTE: `Projeto` e `Orcamento` estão no escopo de database.py. Se `nullslast` não estiver disponível na versão do SQLAlchemy, troque a ordenação por `.order_by(Orcamento.id.desc())` (suficiente). Verifique e adapte; reporte qual usou.

- [ ] **Step 4: Run to verify pass** — `python -m pytest tests/test_parametros_projeto.py -v` → all pass.

- [ ] **Step 5: Wire into startup** — em `main.py`, logo após o bloco que chama `migrar_margens_para_orcamentos` (startup, ~3300), acrescentar (na mesma área protegida):

```python
    try:
        _db_par = get_session()
        try:
            from database import migrar_parametros_para_projeto
            migrar_parametros_para_projeto(_db_par)
        finally:
            _db_par.close()
    except Exception as _e:
        print("[MIGRACAO] parametros->projeto:", _e)
```

- [ ] **Step 6: Smoke + commit**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"` → `ok`; `python -m pytest -q` → green.

```bash
git add database.py main.py tests/test_parametros_projeto.py
git commit -m "feat(banco): migracao dos estruturais para projetos_meta.parametros_json"
```

---

## Task 4: Backend — endpoints de parâmetros do projeto + GET ambientes + margens só desconto

**Files:** Modify `main.py`.

- [ ] **Step 1: GET/POST `/api/projetos/<nome>/parametros`** — em `main.py`, no `do_GET` (junto às rotas `/api/projetos/...`) adicionar o GET; e no `do_POST` (junto ao handler de margens ~1504) adicionar o POST.

GET (em `do_GET`):
```python
            m = _re.match(r'^/api/projetos/([^/]+)/parametros$', path)
            if m:
                nome_safe = unquote(m.group(1))
                from mod_orcamento_params import PARAMETROS_DEFAULT
                db = get_session()
                try:
                    p = db.get(Projeto, nome_safe)
                    par = json.loads(p.parametros_json) if (p and p.parametros_json) else dict(PARAMETROS_DEFAULT)
                    self.send_json({"ok": True, "parametros": par})
                except Exception as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

POST (no `do_POST`, como novo `elif` antes do `else:` que cai nas rotas legadas, espelhando o handler de margens):
```python
        elif re.match(r"^/api/projetos/([^/]+)/parametros$", path):
            m_par = re.match(r"^/api/projetos/([^/]+)/parametros$", path)
            nome_safe = m_par.group(1)
            db = get_session()
            try:
                from mod_orcamento_params import merge_parametros
                req = json.loads(body.decode("utf-8", "replace")) if body else {}
                if _projeto_esta_bloqueado(nome_safe):
                    self.send_json({"ok": False, "erro": "Projeto bloqueado — alteracoes nao permitidas apos aprovacao."}, code=400)
                    return
                if _contrato_assinado(nome_safe, db):
                    self.send_json({"ok": False, "erro": "Contrato assinado — alterações não permitidas."}, code=403)
                    return
                p = db.get(Projeto, nome_safe)
                if not p:
                    p = Projeto(nome_safe=nome_safe); db.add(p)
                atual = json.loads(p.parametros_json) if p.parametros_json else {}
                novos = merge_parametros(atual, req)
                p.parametros_json = json.dumps(novos, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True, "parametros": novos})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
```
(Confirme: `unquote`, `Projeto`, `_projeto_esta_bloqueado`, `_contrato_assinado` em escopo — todos já usados em main.py.)

- [ ] **Step 2: GET ambientes inclui `parametros`** — no handler `^/orcamentos/(\d+)/ambientes$` (~537-542), após obter `orc`, adicionar:

```python
                    orc = db.get(Orcamento, oid)
                    margens = json.loads(orc.margens) if (orc and orc.margens) else {}
                    negociacao = json.loads(orc.negociacao_json) if (orc and orc.negociacao_json) else None
                    parametros = {}
                    if orc:
                        from mod_orcamento_params import PARAMETROS_DEFAULT
                        _p = db.get(Projeto, orc.projeto_id)
                        parametros = json.loads(_p.parametros_json) if (_p and _p.parametros_json) else dict(PARAMETROS_DEFAULT)
                    self.send_json({"ok": True, "orcamento_id": oid,
                                    "margens": margens, "negociacao": negociacao,
                                    "parametros": parametros, "ambientes": ambientes})
```

- [ ] **Step 3: POST margens persiste só `desconto_pct`** — no handler `^/api/orcamentos/(\d+)/margens$` (~1526-1530), trocar a gravação para apenas o desconto:

De:
```python
                atual = json.loads(orc.margens) if orc.margens else {}
                novas = merge_margens(atual, req)
                orc.margens = json.dumps(novas, ensure_ascii=False)
                if "desconto_pct" in req:
                    orc.desconto_pct = float(req["desconto_pct"])
                db.commit()
                self.send_json({"ok": True, "margens": novas})
```
Para (mantém `custo_financeiro_pct` se já existir; ignora chaves estruturais):
```python
                atual = json.loads(orc.margens) if orc.margens else {}
                if "desconto_pct" in req:
                    atual["desconto_pct"] = float(req["desconto_pct"])
                    orc.desconto_pct = float(req["desconto_pct"])
                orc.margens = json.dumps(atual, ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True, "margens": atual})
```
(Pode remover o `from mod_orcamento_params import merge_margens` deste handler se ele ficar sem uso ali; verifique.)

- [ ] **Step 4: Smoke + suite + commit**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"` → `ok`; `python -m pytest -q` → green.

```bash
git add main.py
git commit -m "feat(api): GET/POST parametros do projeto; GET ambientes devolve parametros; margens grava so desconto"
```

---

## Task 5: Frontend — load combinado + save separado

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Load combina parâmetros do projeto + desconto do orçamento** — em `_aplicarFiltroOrcamento` (~2522), trocar:

```javascript
    if(projetoAtivo) projetoAtivo.margens = d.margens || {};
```
por (estruturais do projeto sobrescrevem; `desconto_pct` vem do orçamento):
```javascript
    if(projetoAtivo) projetoAtivo.margens = Object.assign({}, d.margens || {}, d.parametros || {});
```

- [ ] **Step 2: Save separa estruturais (→ projeto) e desconto (→ orçamento)** — em `fecharModalParams`, no caminho de salvar (~5466-5494), substituir o objeto `mg` único + o fetch por dois envios:

```javascript
    const id = s => document.getElementById(s);
    const novoIncluirCustos = document.getElementById('mp-incluir-custos')?.checked || false;
    _incluirCustos = novoIncluirCustos;
    const parametros = {
      comissao_arq_ativa: id('mp-arq-ativa').checked,
      comissao_arq_pct:   parseFloat(id('mp-arq-pct').value)||0,
      fidelidade_ativa:   id('mp-fid-ativa').checked,
      fidelidade_pct:     parseFloat(id('mp-fid-pct').value)||0,
      fora_da_sede:       id('mp-fora-sede').checked,
      custo_viagem:       parseFloat(id('mp-viagem').value)||0,
      brinde_ativo:       id('mp-brinde-ativo').checked,
      brinde:             parseFloat(id('mp-brinde').value)||0,
      incluir_custos:     novoIncluirCustos,
      carga_trib:         parseFloat(id('mp-carga-trib').value)||0,
    };
    const desconto = parseFloat(id('mp-desconto').value)||0;
    try{
      const rp = await fetch('/api/projetos/'+encodeURIComponent(projetoAtivo.nome_safe)+'/parametros',{
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(parametros),
      });
      const dp = await rp.json();
      if(!dp.ok){ showToast('Erro ao salvar parametros: '+(dp.erro||''), true); return; }
      await fetch('/api/orcamentos/'+_orcamentoAtivoId+'/margens',{
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({desconto_pct: desconto}),
      });
      showToast('Parametros salvos!');
      const elDesc = document.getElementById('neg-desconto');
      if(elDesc) elDesc.value = desconto;
      await carregarMargensSalvas();
    }catch(e){ showToast('Erro ao salvar parametros', true); }
```
(Mantenha o restante de `fecharModalParams` — fechar modal, snapshot de cancelamento — como está. Leia a função inteira antes para encaixar exatamente onde o `mg`/fetch antigos estavam.)

- [ ] **Step 3: Smoke (load)** — iniciar o app, hard-refresh, abrir um projeto; sem erro de console. (Comportamento completo na Task 6.)

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(front): parametros estruturais salvos no projeto; desconto por orcamento; load combinado"
```

---

## Task 6: Verificação end-to-end

**Files:** nenhum (execução/verificação).

- [ ] **Step 1: pytest** — `python -m pytest -q` → tudo verde (inclui os novos).

- [ ] **Step 2: API real** (app rodando, login `pdm2026`/`teste123`):
  - `POST /api/projetos/<nome>/parametros` grava; `GET .../parametros` reflete; `GET /orcamentos/<id>/ambientes` devolve `parametros`.
  - Dois orçamentos do mesmo projeto: salvar parâmetros estruturais (ex.: comissão 12, brinde 500) → `GET ambientes` de AMBOS mostra os mesmos `parametros`.
  - `POST /api/orcamentos/<idA>/margens {"desconto_pct":7}` → só o A muda; B mantém o desconto.

- [ ] **Step 3: Playwright (UI, dados reais)** — ver `gui-verification-playwright`:
  - Projeto com 2 orçamentos: no modal de parâmetros do orçamento A, mudar **comissão do arquiteto / brinde / carga tributária / incluir custos** → ao abrir o orçamento B, esses valores **aparecem iguais**.
  - Mudar **desconto** e **forma de pagamento** em A → abrir B → **não** mudaram em B.
  - Console sem erros.

- [ ] **Step 4: DEV_LOG + finalizar branch**
  - Acrescentar seção de sessão ao `DEV_LOG.md`.
  - Seguir `superpowers:finishing-a-development-branch`.

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — parametros estruturais por projeto"
```

---

## Self-Review (cobertura da spec)

- **Coluna `parametros_json` no projeto** → Task 1.
- **`PARAMETROS_DEFAULT` + `merge_parametros` (10 estruturais, sem desconto)** → Task 2.
- **Migração idempotente (estruturais do orçamento → projeto)** → Task 3.
- **GET/POST parametros do projeto + gate** → Task 4.
- **GET ambientes devolve `parametros`; margens grava só `desconto_pct`** → Task 4.
- **Frontend: load combinado + save separado** → Task 5.
- **Estruturais compartilhados / desconto e pagamento por orçamento** → verificado na Task 6.
- **Consistência de nomes:** `parametros_json`, `PARAMETROS_DEFAULT`, `merge_parametros`, `migrar_parametros_para_projeto`, rota `/api/projetos/<nome>/parametros`, chave `parametros` no GET ambientes — idênticos entre as tasks.
