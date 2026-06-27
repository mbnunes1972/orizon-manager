# Provisões versionadas + aprovação financeira — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar as provisões como previsão de despesa versionada (Venda → Rev 1 → Rev 2) e dar ao Gerente Adm/Fin o fluxo Concorda/Revisa em cada aprovação financeira.

**Architecture:** Tabela nova `provisao_registro` (uma linha por versão por orçamento). A "Venda" é gravada na geração do contrato (Etapa 7) a partir do breakdown do motor. Rotas GET (ver as versões + atual) e POST (Concorda/Revisa com senha) por orçamento. Itemização só a partir da Etapa 8; a negociação fica inalterada (agregado). Funções puras em `mod_provisoes`.

**Tech Stack:** Python 3 (`python3` no WSL), SQLAlchemy/SQLite, `http.server` (`main.Handler`), SPA vanilla, `pytest` (frontend = verificação manual).

## Global Constraints

- Rodar com `python3`/`python3 -m pytest` (WSL), nunca `python`.
- **Rubricas (10):** `frete_fab, com_adm, com_venda, com_med, com_proj_exec, frete_loc, assist, ins_loc, prov_imp, out_forn` — mapeadas das siglas do breakdown `Frete_Fab_Orc, Com_Adm_Orc, Com_Venda_Orc, Com_Med_Orc, Com_Proj_Exec_Orc, Frete_Loc_Orc, Assist_Orc, Ins_Loc_Orc, Prov_Imp, Out_Forn`.
- **`Cust_Var = CFO + Σ(itens)`** (os itens já incluem `out_forn` e `prov_imp`); **`Marg_Cont = (Val_Liq − Cust_Var)/Val_Liq`** (`Val_Liq==0 → 0.0`).
- **Versões:** `venda` (snapshot na geração do contrato, `decisao=null`), `rev1` (Etapa 8), `rev2` (Etapa 11d). `UNIQUE(orcamento_id, versao)`; re-snapshot da `venda` sobrescreve a linha.
- **Concorda** = copia a versão anterior. **Revisa** = grava itens editados (clamp `≥0`) + recalcula `cust_var`/`marg_cont` a partir do `cfo`/`val_liq` **da própria venda** (base congelada).
- **Auth:** ver provisões = sessão com `aprovar_financeiro`; revisar = `_aprovador_financeiro(db, login, senha)` (ativo + senha + `aprovar_financeiro`). Escopo por loja via `_obj_da_loja`/`escopo_operacional`.
- **Rev 1 exige `venda`; Rev 2 exige `rev1`** (senão 409). Itemização só a partir da Etapa 8 (negociação inalterada).
- Seguir padrões: modelos como `UsuarioLoja` (`database.py:232`); rotas finas; funções puras em `mod_provisoes`.

---

### Task 1: Modelo `ProvisaoRegistro`

**Files:**
- Modify: `database.py` (modelo novo após `CicloEtapa` ~linha 400)
- Test: `tests/test_provisao_registro.py`

**Interfaces:**
- Produces: `ProvisaoRegistro` (tabela `provisao_registro`): `id`, `orcamento_id` (FK), `versao` (str), `itens_json` (Text), `cfo` (Float), `val_liq` (Float), `cust_var` (Float), `marg_cont` (Float), `decisao` (str/null), `por_id` (FK usuarios), `criado_em` (DateTime). `UNIQUE(orcamento_id, versao)`. A tabela é criada por `Base.metadata.create_all` no `init_db` (sem ALTER).

- [ ] **Step 1: Write the failing test**

Criar `tests/test_provisao_registro.py`:

```python
import json


def test_provisao_registro_persiste(app_db, seed):
    db = app_db.get_session()
    try:
        r = app_db.ProvisaoRegistro(
            orcamento_id=seed["orcamento_l1_id"], versao="venda",
            itens_json=json.dumps({"frete_fab": 100.0, "out_forn": 0.0}),
            cfo=4000.0, val_liq=9000.0, cust_var=4100.0, marg_cont=0.5444, decisao=None)
        db.add(r); db.commit()
        got = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").first()
        assert got is not None
        assert json.loads(got.itens_json)["frete_fab"] == 100.0
        assert got.cfo == 4000.0 and got.val_liq == 9000.0
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisao_registro.py -v`
Expected: FAIL (`AttributeError: ... has no attribute 'ProvisaoRegistro'`).

- [ ] **Step 3: Write minimal implementation**

Em `database.py`, após a classe `CicloEtapa` (~linha 400):

```python
class ProvisaoRegistro(Base):
    """Provisões registradas por versão (venda/rev1/rev2) de um orçamento.
    venda = snapshot na geração do contrato; rev1/rev2 = aprovação financeira I/II."""
    __tablename__ = "provisao_registro"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)
    versao       = Column(String(8), nullable=False)   # 'venda' | 'rev1' | 'rev2'
    itens_json   = Column(Text,      nullable=False)    # {rubrica: valor_R$}
    cfo          = Column(Float, default=0.0)           # base congelada p/ recalcular margem
    val_liq      = Column(Float, default=0.0)
    cust_var     = Column(Float, default=0.0)
    marg_cont    = Column(Float, default=0.0)
    decisao      = Column(String(10), nullable=True)    # 'concorda' | 'revisa' | None (venda)
    por_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    criado_em    = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("orcamento_id", "versao", name="uq_provisao_orc_versao"),)
```

(`Column`, `Integer`, `String`, `Text`, `Float`, `DateTime`, `ForeignKey`, `UniqueConstraint`, `datetime` já estão importados em `database.py`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisao_registro.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde (tabela nova criada por create_all; sem regressão).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_provisao_registro.py
git commit -m "feat(provisoes): modelo ProvisaoRegistro (versoes venda/rev1/rev2)"
```

---

### Task 2: `mod_provisoes` — `itens_provisao` + `cust_var_marg_cont` (puros)

**Files:**
- Modify: `mod_provisoes.py`
- Test: `tests/test_provisoes.py`

**Interfaces:**
- Produces: `itens_provisao(siglas) -> dict` (10 rubricas a partir do breakdown); `cust_var_marg_cont(cfo, val_liq, itens) -> (cust_var, marg_cont)` (recalcula a partir de itens editados: `Cust_Var = CFO + Σ itens`).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisoes.py`:

```python
def test_itens_provisao_mapeia_rubricas():
    d = {"Frete_Fab_Orc": 100.0, "Com_Adm_Orc": 200.0, "Com_Venda_Orc": 0.0,
         "Com_Med_Orc": 0.0, "Com_Proj_Exec_Orc": 0.0, "Frete_Loc_Orc": 50.0,
         "Assist_Orc": 0.0, "Ins_Loc_Orc": 0.0, "Prov_Imp": 0.0, "Out_Forn": 300.0}
    itens = mod_provisoes.itens_provisao(d)
    assert set(itens.keys()) == {"frete_fab","com_adm","com_venda","com_med",
        "com_proj_exec","frete_loc","assist","ins_loc","prov_imp","out_forn"}
    assert itens["frete_fab"] == 100.0 and itens["out_forn"] == 300.0 and itens["frete_loc"] == 50.0


def test_cust_var_marg_cont_recalcula():
    itens = {"frete_fab": 100.0, "com_adm": 200.0, "out_forn": 300.0}  # Σ = 600
    cv, mc = mod_provisoes.cust_var_marg_cont(cfo=4000.0, val_liq=9000.0, itens=itens)
    assert cv == 4600.0                      # 4000 + 600
    assert mc == round((9000.0 - 4600.0)/9000.0, 4)
    # val_liq 0 -> margem 0
    assert mod_provisoes.cust_var_marg_cont(0.0, 0.0, {})[1] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisoes.py -k "itens_provisao or cust_var_marg_cont" -v`
Expected: FAIL (`AttributeError`).

- [ ] **Step 3: Write minimal implementation**

Acrescentar a `mod_provisoes.py`:

```python
_RUBRICAS = {
    "frete_fab": "Frete_Fab_Orc", "com_adm": "Com_Adm_Orc", "com_venda": "Com_Venda_Orc",
    "com_med": "Com_Med_Orc", "com_proj_exec": "Com_Proj_Exec_Orc", "frete_loc": "Frete_Loc_Orc",
    "assist": "Assist_Orc", "ins_loc": "Ins_Loc_Orc", "prov_imp": "Prov_Imp", "out_forn": "Out_Forn",
}


def itens_provisao(siglas):
    """Extrai as 10 rubricas de provisão do breakdown do motor (dict {rubrica: valor R$})."""
    s = siglas or {}
    return {k: round(_f(s.get(v)), 2) for k, v in _RUBRICAS.items()}


def cust_var_marg_cont(cfo, val_liq, itens):
    """Recalcula (Cust_Var, Marg_Cont) a partir de itens (possivelmente editados).
    Cust_Var = CFO + Σ itens (os itens já incluem out_forn e prov_imp)."""
    cust_var = round(_f(cfo) + sum(_f(v) for v in (itens or {}).values()), 2)
    vl = _f(val_liq)
    marg = round((vl - cust_var) / vl, 4) if vl else 0.0
    return cust_var, marg
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisoes.py -k "itens_provisao or cust_var_marg_cont" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_provisoes.py
git commit -m "feat(provisoes): itens_provisao + cust_var_marg_cont (puros)"
```

---

### Task 3: Gravar a "Venda" na geração do contrato

**Files:**
- Modify: `main.py` (helper `_registrar_provisao_venda` + chamada no handler de geração do contrato ~3399)
- Test: `tests/test_provisao_registro.py`

**Interfaces:**
- Consumes: `mod_provisoes.itens_provisao`, `_negociacao_breakdown`, `ProvisaoRegistro`.
- Produces: `_registrar_provisao_venda(db, orc, por_id)` — computa o breakdown, monta os itens e **upserta** a linha `venda` (sobrescreve se já existir → re-snapshot). Grava `cfo`, `val_liq`, `cust_var`, `marg_cont`.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisao_registro.py`:

```python
def test_registrar_venda(app_db, seed, projetos_dir):
    import main
    db = app_db.get_session()
    try:
        # ambiente com valor p/ o motor calcular
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Amb", versao=1,
                                 nome_exibicao="Amb", xml_path="", ambientes_json="[]",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
        r = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").first()
        assert r is not None and r.decisao is None
        import json as _j
        assert set(_j.loads(r.itens_json).keys()) >= {"frete_fab", "out_forn", "prov_imp"}
        assert r.cfo == 4000.0          # CFO = order_total
        # idempotente / re-snapshot: chamar de novo não duplica
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
        n = db.query(app_db.ProvisaoRegistro).filter_by(
            orcamento_id=seed["orcamento_l1_id"], versao="venda").count()
        assert n == 1
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisao_registro.py -k registrar_venda -v`
Expected: FAIL (`AttributeError: ... _registrar_provisao_venda`).

- [ ] **Step 3: Write minimal implementation**

3a. Adicionar o helper em `main.py` (junto dos outros helpers `_...`, ex.: perto de `_negociacao_breakdown`):

```python
def _registrar_provisao_venda(db, orc, por_id):
    """Grava (ou re-snapshota) a versão 'venda' das provisões a partir do breakdown atual."""
    import mod_provisoes
    d = _negociacao_breakdown(orc, db)
    itens = mod_provisoes.itens_provisao(d)
    existente = db.query(ProvisaoRegistro).filter_by(
        orcamento_id=orc.id, versao="venda").first()
    if existente:
        db.delete(existente); db.flush()
    db.add(ProvisaoRegistro(
        orcamento_id=orc.id, versao="venda",
        itens_json=json.dumps(itens, ensure_ascii=False),
        cfo=_f(d.get("CFO")), val_liq=_f(d.get("Val_Liq")),
        cust_var=_f(d.get("Cust_Var")), marg_cont=_f(d.get("Marg_Cont")),
        decisao=None, por_id=por_id))
```

(`ProvisaoRegistro` precisa ser importado de `database` no topo de `main.py`; `json` já está. `_f` é o helper numérico de main.py — se não existir, use `float(x or 0)`.)

3b. No handler de **geração do contrato**, logo após o `db.commit()` que finaliza o contrato (~`main.py:3399`, onde `contrato.num_contrato`/`pdf_path` já foram gravados), acrescentar:

```python
                    _registrar_provisao_venda(db, db.get(Orcamento, contrato.orcamento_id),
                                              por_id=(usuario.get("id") if usuario else None))
                    db.commit()
```

(Use o `contrato` e o `usuario` já existentes nesse handler. Leia ~30 linhas ao redor para inserir no ponto certo, depois que o contrato está persistido.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisao_registro.py -k registrar_venda -v`
Expected: PASS.

- [ ] **Step 5: Run full suite (regressão da geração de contrato)**

Run: `python3 -m pytest -q`
Expected: verde (a gravação da venda é aditiva; não altera o contrato).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_provisao_registro.py
git commit -m "feat(provisoes): grava 'venda' na geracao do contrato (re-snapshot na regeração)"
```

---

### Task 4: Rota `GET /api/orcamentos/<id>/provisoes`

**Files:**
- Modify: `main.py` (ramo em `do_GET`)
- Test: `tests/test_provisao_registro.py`

**Interfaces:**
- Consumes: `ProvisaoRegistro`, `mod_provisoes.itens_provisao`, `_negociacao_breakdown`, `_obj_da_loja`, `escopo_operacional`.
- Produces: `GET /api/orcamentos/<id>/provisoes` → `{"ok":true, "provisoes": {"venda":{...}|null, "rev1":..., "rev2":..., "atual": {"itens":{...}, "cfo","val_liq","cust_var","marg_cont"}, "desatualizado": bool}}`. Auth: `aprovar_financeiro`.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisao_registro.py`:

```python
def test_get_provisoes(http_client_factory, app_db, seed, projetos_dir):
    import main, json as _j
    db = app_db.get_session()
    try:
        pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="A", versao=1,
                                 nome_exibicao="A", xml_path="", ambientes_json="[]",
                                 budget_total=10000.0, order_total=4000.0)
        db.add(pa); db.flush()
        db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                        pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        db.commit()
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
    finally:
        db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")   # diretor tem aprovar_financeiro
    st, body = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert st == 200 and body["ok"] is True
    assert body["provisoes"]["venda"] is not None
    assert "frete_fab" in body["provisoes"]["atual"]["itens"]
    assert body["provisoes"]["desatualizado"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisao_registro.py -k get_provisoes -v`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Write minimal implementation**

No `do_GET` de `main.py`, junto das rotas `/api/orcamentos/...`, adicionar:

```python
        elif re.match(r"^/api/orcamentos/(\d+)/provisoes$", path):
            import mod_provisoes
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            oid = int(re.match(r"^/api/orcamentos/(\d+)/provisoes$", path).group(1))
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return

                def _reg(versao):
                    r = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                    if not r:
                        return None
                    return {"itens": json.loads(r.itens_json), "cfo": r.cfo, "val_liq": r.val_liq,
                            "cust_var": r.cust_var, "marg_cont": r.marg_cont, "decisao": r.decisao,
                            "criado_em": r.criado_em.isoformat() if r.criado_em else None}
                venda = _reg("venda")
                d = _negociacao_breakdown(orc, db)
                atual = {"itens": mod_provisoes.itens_provisao(d), "cfo": _f(d.get("CFO")),
                         "val_liq": _f(d.get("Val_Liq")), "cust_var": _f(d.get("Cust_Var")),
                         "marg_cont": _f(d.get("Marg_Cont"))}
                desatualizado = bool(venda and venda["itens"] != atual["itens"])
                self.send_json({"ok": True, "provisoes": {
                    "venda": venda, "rev1": _reg("rev1"), "rev2": _reg("rev2"),
                    "atual": atual, "desatualizado": desatualizado}})
            finally:
                db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisao_registro.py -k get_provisoes -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_provisao_registro.py
git commit -m "feat(provisoes): GET /api/orcamentos/<id>/provisoes (versoes + atual + desatualizado)"
```

---

### Task 5: Rota `POST /api/orcamentos/<id>/provisoes/<rev1|rev2>` (Concorda/Revisa)

**Files:**
- Modify: `main.py` (ramo em `do_POST`)
- Test: `tests/test_provisao_registro.py`

**Interfaces:**
- Consumes: `ProvisaoRegistro`, `mod_provisoes.cust_var_marg_cont`, `_aprovador_financeiro`, `_obj_da_loja`, `escopo_operacional`.
- Produces: `POST /api/orcamentos/<id>/provisoes/<rev1|rev2>` corpo `{decisao, itens?, login, senha}`. `concorda` → copia a versão anterior (rev1←venda, rev2←rev1). `revisa` → grava `itens` editados (clamp `≥0`) e recalcula `cust_var`/`marg_cont` com `cfo`/`val_liq` da venda. Auth `_aprovador_financeiro`. Rev1 sem venda / Rev2 sem rev1 → 409.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_provisao_registro.py`:

```python
def _setup_venda(app_db, seed):
    import main
    db = app_db.get_session()
    try:
        if not db.query(app_db.PoolAmbiente).filter_by(projeto_id=seed["projeto_l1"]).first():
            pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="A", versao=1,
                                     nome_exibicao="A", xml_path="", ambientes_json="[]",
                                     budget_total=10000.0, order_total=4000.0)
            db.add(pa); db.flush()
            db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                            pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
            db.commit()
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        main._registrar_provisao_venda(db, orc, por_id=1); db.commit()
    finally:
        db.close()


def test_rev1_concorda_copia_venda(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov["provisoes"]["rev1"]["itens"] == prov["provisoes"]["venda"]["itens"]
    assert prov["provisoes"]["rev1"]["decisao"] == "concorda"


def test_rev1_revisa_grava_editado(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    itens = {"frete_fab": 999.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 0.0, "out_forn": -50.0}   # out_forn negativo -> clamp 0
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True
    _, prov = c.get("/api/orcamentos/%d/provisoes" % seed["orcamento_l1_id"])
    assert prov["provisoes"]["rev1"]["itens"]["frete_fab"] == 999.0
    assert prov["provisoes"]["rev1"]["itens"]["out_forn"] == 0.0   # clampado


def test_rev1_senha_invalida_403(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/orcamentos/%d/provisoes/rev1" % seed["orcamento_l1_id"],
                   {"decisao": "concorda", "login": "dir_l1", "senha": "errada"})
    assert st == 403


def test_rev2_sem_rev1_409(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/orcamentos/%d/provisoes/rev2" % seed["orcamento_l1_id"],
                   {"decisao": "concorda", "login": "dir_l1", "senha": "senha123"})
    assert st == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_provisao_registro.py -k "rev1 or rev2" -v`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Write minimal implementation**

No `do_POST` de `main.py`, adicionar:

```python
            m_prov = re.match(r"^/api/orcamentos/(\d+)/provisoes/(rev1|rev2)$", path)
            if m_prov:
                import mod_provisoes
                oid = int(m_prov.group(1)); versao = m_prov.group(2)
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    aprovador = _aprovador_financeiro(db, req.get("login"), req.get("senha"))
                    if not aprovador:
                        self.send_json({"ok": False, "erro": "Senha/perfil inválido para aprovar"}, code=403); return
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403); return
                    orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    anterior_versao = "venda" if versao == "rev1" else "rev1"
                    anterior = db.query(ProvisaoRegistro).filter_by(
                        orcamento_id=oid, versao=anterior_versao).first()
                    if not anterior:
                        self.send_json({"ok": False,
                            "erro": "Registre a versão anterior primeiro (%s)." % anterior_versao},
                            code=409); return
                    decisao = (req.get("decisao") or "").strip()
                    if decisao == "concorda":
                        itens = json.loads(anterior.itens_json)
                        cfo, vl = anterior.cfo, anterior.val_liq
                    elif decisao == "revisa":
                        itens = {k: max(0.0, float(v or 0)) for k, v in (req.get("itens") or {}).items()}
                        cfo, vl = anterior.cfo, anterior.val_liq   # base congelada da venda
                    else:
                        self.send_json({"ok": False, "erro": "decisao deve ser concorda|revisa"}); return
                    cust_var, marg = mod_provisoes.cust_var_marg_cont(cfo, vl, itens)
                    existente = db.query(ProvisaoRegistro).filter_by(orcamento_id=oid, versao=versao).first()
                    if existente:
                        db.delete(existente); db.flush()
                    db.add(ProvisaoRegistro(orcamento_id=oid, versao=versao,
                        itens_json=json.dumps(itens, ensure_ascii=False),
                        cfo=cfo, val_liq=vl, cust_var=cust_var, marg_cont=marg,
                        decisao=decisao, por_id=aprovador.id))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return
```

(`_aprovador_financeiro`, `_obj_da_loja`, `_ator_dict`, `mod_tenancy`, `ProvisaoRegistro`, `Orcamento`, `re`, `json` já disponíveis em main.py.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_provisao_registro.py -k "rev1 or rev2" -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_provisao_registro.py
git commit -m "feat(provisoes): POST rev1/rev2 (concorda/revisa, senha aprovar_financeiro)"
```

---

### Task 6: Frontend — botão "Provisões" na etapa de aprovação financeira

**Files:**
- Modify: `static/index.html` (UI da etapa de aprovação financeira: botão + tabelas + Concorda/Revisa)

**Interfaces:**
- Consumes: `GET /api/orcamentos/<id>/provisoes`, `POST /api/orcamentos/<id>/provisoes/<rev>`.
- Produces: na etapa de aprovação financeira (8 e 11d) um botão **"Provisões"** que abre uma tela/modal com as tabelas **Venda | Rev 1 | Rev 2** (conforme existirem) lado a lado, e as ações **Concorda** / **Revisa** (com senha). Aviso quando `desatualizado`.

- [ ] **Step 1: Localizar a etapa de aprovação financeira**

Leia no `index.html` a UI das etapas do ciclo (`renderContratoUI` é o padrão para a etapa Contrato; procure o render das etapas 8 / 11d — `etapa.acao` / `ETAPA_NOME` / o card da etapa de aprovação financeira). Identifique onde acrescentar o botão "Provisões" para o orçamento ativo (`_orcamentoAtivoId`).

- [ ] **Step 2: Modal/tela de provisões + ações**

Adicionar `abrirProvisoes(oid)` que faz `GET /api/orcamentos/${oid}/provisoes` e renderiza um modal (padrão `modal-overlay`/`modal-box`) com:
- um aviso de "⚠️ provisões desatualizadas" quando `desatualizado`;
- as colunas **Venda | Rev 1 | Rev 2** (as que existirem) + a coluna **Atual** (calculada), listando as 10 rubricas + `Cust_Var` + `Marg_Cont`;
- ações **Concorda** e **Revisa** para a próxima versão pendente (rev1 se não existe; senão rev2). Revisa abre os campos editáveis das rubricas; ambos pedem **login + senha** (de quem aprova) e fazem `POST /api/orcamentos/${oid}/provisoes/${rev}` com `{decisao, itens?, login, senha}`; ao sucesso, recarrega.

Implementar seguindo o padrão de modais e de chamadas `fetch` já existentes (ex.: `abrirModalLiberarImpostos` para o padrão de senha financeira). Reusar `esc()` e `showToast`/`avisoPopup`.

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py
```
Como diretor/gerente adm-fin: num projeto com contrato gerado, ir na **etapa de aprovação financeira** → **Provisões** → ver a tabela **Venda** → **Concorda** (Rev 1 = Venda) ou **Revisa** (editar valores + senha) → conferir que a Rev 1 aparece. Repetir na 2ª aprovação (Rev 2). Conferir o aviso de desatualizado ao mudar a negociação depois.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(provisoes): botao Provisoes + tabelas Venda/Rev1/Rev2 + Concorda/Revisa na etapa"
```

---

## Notas de implementação

- **Ordem/dependências:** Tasks 1→2 base (modelo + puros); Task 3 grava a venda na geração do contrato; Tasks 4-5 rotas; Task 6 frontend (depende de 4-5).
- **Branch:** `feat/provisoes-versionadas` (do `main` já com a Frente C mergeada).
- **Fora deste plano (futuro):** editar as taxas % por negócio; itemização na negociação; Rev 3+; relatório consolidado de provisões por loja/período.
- **Reaproveitamento:** o snapshot da venda na regeração do contrato espelha o `_resolver_pdf_contrato`/staleness já existentes; o aviso de desatualizado usa a comparação de itens (Venda × Atual).
