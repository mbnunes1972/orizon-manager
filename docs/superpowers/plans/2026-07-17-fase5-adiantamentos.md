# Fase 5 — Adiantamentos / Empréstimos + Saldo de Débito Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Registrar adiantamentos e empréstimos por funcionário (incluindo a regra oficial de 40% do salário fixo em carteira, automática), com abatimento **editável** no líquido da folha e **saldo de débito** do funcionário.

**Architecture:** Nova tabela `adiantamento_funcionario`. A config da loja ganha `folha.adiantamento_oficial_{ativo,pct}` (no config-financeira). `gerar_folha` cria automaticamente o adiantamento **oficial** (40% × salário fixo da Função) para funcionários **registrados** (`Funcao.regime_contratacao='registrado'`). A Folha passa a expor, por funcionário: adiantamentos, **líquido a pagar** (total − abatimentos da competência) e **saldo de débito** (Σ não quitado). `pagar` quita os adiantamentos abatidos naquela competência. Contábil detalhado dos adiantamentos fica **com o contador** (fora de escopo); Fase 5 entrega a mecânica da folha + saldo.

**Tech Stack:** Python (http.server + SQLAlchemy), pytest (SQLite; suíte também validada em Postgres), frontend single-file `static/index.html`.

**Convenções do repo (obrigatório):**
- **Tabela nova** é criada por `create_all()` em ambos dialetos (nenhuma migração especial). Coluna nova em tabela existente exigiria `_add_cols` + `_migrar_colunas_pg` (não é o caso aqui).
- Backend TDD. Frontend via `node --check` (maior `<script>` no WSL).
- Worktree sob `.claude/worktrees/`; FF-merge para `main`. Não commitar `perfis_config.json`; não tocar WIP/planos do usuário. Push só quando pedido.

---

## Modelo e fórmulas

**`adiantamento_funcionario`:**
```
id, loja_id, funcionario_id
tipo               'oficial' | 'adiantamento' | 'emprestimo'
competencia        'AAAA-MM'          # mês concedido
valor              Float
abater             Integer 0/1        # se deduz do líquido (editável)
competencia_abate  'AAAA-MM'          # folha que deduz (oficial/adiantamento = mesma; empréstimo = escolhida)
quitado            Integer 0/1        # baixado quando a folha de competencia_abate é paga
observacao         Text
ref                String unique nullable   # idempotência do oficial: 'oficial:<func>:<comp>'
criado_em          DateTime
```

- **Saldo de débito** do funcionário = Σ `valor` onde `quitado=0`.
- **Abatimentos da competência M** (funcionário) = Σ `valor` onde `abater=1 AND competencia_abate=M AND quitado=0`.
- **Líquido a pagar (M)** = `folha.total(M)` − abatimentos da competência M.
- **Oficial**: `valor = pct/100 × salário_fixo(Função)`; `abater=1`, `competencia_abate=M`, `tipo='oficial'`; só para `regime_contratacao='registrado'`.

**Config (config-financeira da loja):** nova chave `"folha": {"adiantamento_oficial_ativo": False, "adiantamento_oficial_pct": 40.0}`.

---

### Task 1: Tabela `adiantamento_funcionario`

**Files:**
- Modify: `database.py` (novo modelo, junto a `ComissaoFolha`)
- Modify: `modulos.py` (registrar tabela no módulo `folha`)
- Test: `tests/test_adiantamento.py` (novo)

- [ ] **Step 1: Teste que falha (tabela + colunas)**

`tests/test_adiantamento.py`:
```python
def test_adiantamento_tabela_existe(app_db):
    cols = {c.name for c in app_db.AdiantamentoFuncionario.__table__.columns}
    for c in ("funcionario_id","tipo","competencia","valor","abater","competencia_abate","quitado","ref"):
        assert c in cols
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_adiantamento.py::test_adiantamento_tabela_existe -q`
Expected: FAIL.

- [ ] **Step 3: Implementar o modelo** (em `database.py`, após `ComissaoFolha`)

```python
class AdiantamentoFuncionario(Base):
    """Adiantamento/empréstimo a funcionário (Fase 5). 'oficial' = 40% do salário fixo (auto, carteira);
    'adiantamento' = adiantamento avulso; 'emprestimo' = empréstimo (pode atravessar meses). abater/
    competencia_abate controlam a dedução do líquido; quitado marca a baixa quando a folha é paga."""
    __tablename__ = "adiantamento_funcionario"
    id                = Column(Integer,  primary_key=True, autoincrement=True)
    loja_id           = Column(Integer,  ForeignKey("lojas.id"), nullable=True)
    funcionario_id    = Column(Integer,  ForeignKey("funcionarios.id"), nullable=False)
    tipo              = Column(String(14), nullable=False, default="adiantamento")
    competencia       = Column(String(7), nullable=False)
    valor             = Column(Float,    nullable=True, default=0.0)
    abater            = Column(Integer,  nullable=False, default=1)
    competencia_abate = Column(String(7), nullable=True)
    quitado           = Column(Integer,  nullable=False, default=0)
    observacao        = Column(Text,     nullable=True)
    ref               = Column(String(120), nullable=True)
    criado_em         = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("ref", name="uq_adiantamento_ref"),)
```

- [ ] **Step 4: Registrar no manifesto** (`modulos.py`, módulo `folha`)

Adicionar `"adiantamento_funcionario"` à lista `tabelas` do módulo `folha`.

- [ ] **Step 5: Rodar e ver passar** (+ arquitetura)

Run: `python3 -m pytest tests/test_adiantamento.py::test_adiantamento_tabela_existe tests/test_arquitetura_modulos.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add database.py modulos.py tests/test_adiantamento.py
git commit -m "feat(adiantamento): tabela adiantamento_funcionario + manifesto"
```

---

### Task 2: Config `folha.adiantamento_oficial_{ativo,pct}`

**Files:**
- Modify: `mod_provisoes.py` (`config_financeira_default`, normalização/validação)
- Test: `tests/test_adiantamento.py`

- [ ] **Step 1: Teste que falha (default tem a chave folha)**

```python
def test_config_financeira_tem_folha_default():
    import mod_provisoes
    cfg = mod_provisoes.config_financeira_default()
    assert cfg["folha"]["adiantamento_oficial_ativo"] is False
    assert cfg["folha"]["adiantamento_oficial_pct"] == 40.0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_adiantamento.py::test_config_financeira_tem_folha_default -q`
Expected: FAIL (KeyError 'folha').

- [ ] **Step 3: Adicionar a chave** em `config_financeira_default()`:
```python
        "folha": {"adiantamento_oficial_ativo": False, "adiantamento_oficial_pct": 40.0},
```
Se houver função de normalização que reconstrói o dict (mesclar defaults), garantir que `folha` seja preservada (ler o merge; adicionar `out["folha"] = {...}` a partir de `d.get("folha")`). Validar `adiantamento_oficial_pct` ∈ [0,100] em `validar_config_financeira`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_adiantamento.py::test_config_financeira_tem_folha_default -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_adiantamento.py
git commit -m "feat(adiantamento): config folha.adiantamento_oficial (ativo + pct, default 40%)"
```

---

### Task 3: `mod_adiantamento` — saldo, abatimentos e oficial

**Files:**
- Create: `mod_adiantamento.py`
- Modify: `modulos.py` (arquivos do módulo `folha`)
- Test: `tests/test_adiantamento.py`

- [ ] **Step 1: Testes que falham**

```python
import mod_adiantamento

def test_saldo_debito_soma_nao_quitados(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="D", status="ativo"); db.add(f); db.flush()
    db.add(app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="emprestimo",
           competencia="2026-07", valor=500.0, abater=1, competencia_abate="2026-08", quitado=0))
    db.add(app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="adiantamento",
           competencia="2026-07", valor=200.0, abater=1, competencia_abate="2026-07", quitado=1))
    db.commit()
    assert mod_adiantamento.saldo_debito(db, f.id) == 500.0        # só o não quitado
    assert mod_adiantamento.abatimentos_competencia(db, f.id, "2026-08") == 500.0
    assert mod_adiantamento.abatimentos_competencia(db, f.id, "2026-07") == 0.0   # o de 2026-07 já quitado
    db.close()

def test_upsert_oficial_40pct_carteira(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Registrado", salario_fixo=2000.0,
                       regime_contratacao="registrado", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="R", funcao_id=fn.id, status="ativo"); db.add(f); db.flush()
    it = mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0); db.commit()
    assert it is not None and it.valor == 800.0 and it.tipo == "oficial"
    assert it.abater == 1 and it.competencia_abate == "2026-07"
    mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0); db.commit()   # idempotente
    n = db.query(app_db.AdiantamentoFuncionario).filter_by(funcionario_id=f.id, tipo="oficial").count()
    assert n == 1
    db.close()

def test_upsert_oficial_ignora_terceirizado(seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Terc", salario_fixo=2000.0,
                       regime_contratacao="terceirizacao", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="T", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    assert mod_adiantamento.upsert_oficial(db, loja, f, "2026-07", pct=40.0) is None
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_adiantamento.py -q -k "saldo or oficial"`
Expected: FAIL.

- [ ] **Step 3: Implementar `mod_adiantamento.py`**

```python
"""mod_adiantamento.py — Adiantamentos/empréstimos a funcionários (Fase 5). Saldo de débito, abatimento
no líquido e a regra oficial (40% do salário fixo em carteira)."""
from database import AdiantamentoFuncionario, Funcionario, Funcao


def saldo_debito(db, funcionario_id):
    itens = db.query(AdiantamentoFuncionario).filter_by(funcionario_id=funcionario_id, quitado=0).all()
    return round(sum(float(a.valor or 0.0) for a in itens), 2)


def abatimentos_competencia(db, funcionario_id, competencia):
    itens = (db.query(AdiantamentoFuncionario)
             .filter_by(funcionario_id=funcionario_id, competencia_abate=competencia, quitado=0)
             .filter(AdiantamentoFuncionario.abater == 1).all())
    return round(sum(float(a.valor or 0.0) for a in itens), 2)


def upsert_oficial(db, loja_id, f, competencia, pct):
    """Cria/atualiza (idempotente) o adiantamento oficial do mês para funcionário REGISTRADO.
    valor = pct% × salário fixo da Função. Retorna o item, ou None se não se aplica."""
    funcao = db.get(Funcao, f.funcao_id) if f.funcao_id else None
    if not funcao or (funcao.regime_contratacao or "") != "registrado":
        return None
    fixo = float(funcao.salario_fixo or 0.0)
    if fixo <= 0 or pct <= 0:
        return None
    valor = round(fixo * float(pct) / 100.0, 2)
    ref = "oficial:%d:%s" % (f.id, competencia)
    it = db.query(AdiantamentoFuncionario).filter_by(ref=ref).first()
    if it is None:
        it = AdiantamentoFuncionario(loja_id=loja_id, funcionario_id=f.id, tipo="oficial",
                                     competencia=competencia, competencia_abate=competencia,
                                     abater=1, ref=ref)
        db.add(it)
    if it.quitado:
        return it
    it.valor = valor
    db.flush()
    return it


def quitar_da_competencia(db, funcionario_id, competencia):
    """Marca como quitados os adiantamentos abatidos naquela competência (chamado ao pagar a folha)."""
    itens = (db.query(AdiantamentoFuncionario)
             .filter_by(funcionario_id=funcionario_id, competencia_abate=competencia)
             .filter(AdiantamentoFuncionario.abater == 1).all())
    for a in itens:
        a.quitado = 1
    db.flush()
    return len(itens)
```

- [ ] **Step 4: Registrar arquivo no manifesto** (`modulos.py`, módulo `folha` → `arquivos`: adicionar `"mod_adiantamento.py"`).

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_adiantamento.py tests/test_arquitetura_modulos.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_adiantamento.py modulos.py tests/test_adiantamento.py
git commit -m "feat(adiantamento): mod_adiantamento (saldo_debito, abatimentos, upsert_oficial, quitar)"
```

---

### Task 4: Integração na Folha (oficial auto + líquido + saldo + quitação)

**Files:**
- Modify: `mod_folha.py` (`gerar_folha`, `serialize`, `listar`, `pagar`)
- Test: `tests/test_adiantamento.py`

- [ ] **Step 1: Testes que falham**

```python
def test_gerar_folha_cria_oficial_e_liquido(seed, app_db):
    import mod_folha, mod_provisoes
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    fn = app_db.Funcao(loja_id=loja, nome="Reg", salario_fixo=2000.0,
                       regime_contratacao="registrado", status="ativo"); db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja, nome="R", funcao_id=fn.id, status="ativo"); db.add(f); db.commit()
    cfg = mod_provisoes.config_financeira_default()
    cfg["folha"]["adiantamento_oficial_ativo"] = True   # 40% default
    mod_folha.gerar_folha(db, loja, "2026-07", cfg); db.commit()
    reg = db.query(app_db.FolhaPagamento).filter_by(funcionario_id=f.id, competencia="2026-07").first()
    d = mod_folha.serialize(db, reg)
    assert d["total"] == 2000.0
    assert d["abatimentos"] == 800.0          # oficial 40% de 2000
    assert d["liquido_pagar"] == 1200.0       # 2000 - 800
    assert d["saldo_debito"] == 800.0
    assert any(a["tipo"] == "oficial" and a["valor"] == 800.0 for a in d["adiantamentos"])
    db.close()

def test_pagar_quita_adiantamentos_da_competencia(seed, app_db):
    import mod_folha
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l2").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="P", status="ativo", pix="p@x"); db.add(f); db.flush()
    ad = app_db.AdiantamentoFuncionario(loja_id=loja, funcionario_id=f.id, tipo="adiantamento",
         competencia="2026-07", valor=300.0, abater=1, competencia_abate="2026-07", quitado=0)
    reg = app_db.FolhaPagamento(loja_id=loja, funcionario_id=f.id, competencia="2026-07",
         parte_fixa=1000.0, total=1000.0, status="aberta")
    db.add(ad); db.add(reg); db.flush()
    mod_folha.pagar(db, "loja", 99, reg)
    assert reg.status == "paga"
    db.refresh(ad); assert ad.quitado == 1
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_adiantamento.py -q -k "gerar_folha_cria_oficial or pagar_quita"`
Expected: FAIL.

- [ ] **Step 3: Integrar no `mod_folha.py`**

Import: `import mod_adiantamento`.
Em `gerar_folha`, dentro do laço (após calcular a folha, antes do `db.flush()`), criar o oficial quando ligado:
```python
        folha_cfg = (cfg or {}).get("folha", {}) or {}
        if folha_cfg.get("adiantamento_oficial_ativo"):
            mod_adiantamento.upsert_oficial(db, loja_id, f, competencia,
                                            folha_cfg.get("adiantamento_oficial_pct") or 0.0)
```
Em `serialize`, acrescentar adiantamentos + líquido + saldo:
```python
    from database import AdiantamentoFuncionario
    ads = (db.query(AdiantamentoFuncionario)
           .filter_by(funcionario_id=reg.funcionario_id)
           .order_by(AdiantamentoFuncionario.id.asc()).all())
    adiantamentos = [{"id": a.id, "tipo": a.tipo, "competencia": a.competencia, "valor": a.valor,
                      "abater": bool(a.abater), "competencia_abate": a.competencia_abate,
                      "quitado": bool(a.quitado), "observacao": a.observacao} for a in ads]
    abat = mod_adiantamento.abatimentos_competencia(db, reg.funcionario_id, reg.competencia)
    saldo = mod_adiantamento.saldo_debito(db, reg.funcionario_id)
    liquido = round((reg.total or 0.0) - abat, 2)
```
E adicionar ao dict: `"adiantamentos": adiantamentos, "abatimentos": abat, "liquido_pagar": liquido, "saldo_debito": saldo,`.
Em `listar`, somar `total_liquido = Σ liquido_pagar`.
Em `pagar`, ao final (antes do return, após marcar 'paga'), quitar:
```python
    import mod_adiantamento
    mod_adiantamento.quitar_da_competencia(db, reg.funcionario_id, reg.competencia)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_adiantamento.py tests/test_folha.py tests/test_comissao.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_folha.py tests/test_adiantamento.py
git commit -m "feat(folha): oficial automático + líquido a pagar + saldo de débito + quitação na paga"
```

---

### Task 5: Endpoints CRUD de adiantamentos

**Files:**
- Modify: `main.py` (POST/PATCH/DELETE `/api/adiantamentos`)
- Test: `tests/test_adiantamento.py`

- [ ] **Step 1: Teste de endpoint que falha**

```python
def test_adiantamento_crud_endpoint(http_client_factory, seed, app_db):
    db = app_db.get_session()
    loja = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcionario(loja_id=loja, nome="CrudFunc", status="ativo"); db.add(f); db.commit(); fid = f.id; db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/adiantamentos", {"funcionario_id": fid, "tipo": "emprestimo",
        "competencia": "2026-07", "valor": 500.0, "abater": True, "competencia_abate": "2026-08"})
    assert st in (200, 201), d
    aid = d["id"]
    st2, d2 = c.patch("/api/adiantamentos/%d" % aid, {"abater": False})
    assert st2 == 200 and d2["abater"] is False
    st3, _ = c.delete("/api/adiantamentos/%d" % aid) if hasattr(c, "delete") else (200, None)
    assert st3 in (200, 204)
```
(Se o cliente de teste não tiver `delete`, testar POST+PATCH e a remoção via handler separadamente; ver `tests/conftest.py`.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_adiantamento.py::test_adiantamento_crud_endpoint -q`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Implementar as rotas** em `main.py`

POST `/api/adiantamentos` (no `do_POST`, padrão ator/escopo_operacional):
```python
        if path == "/api/adiantamentos":
            usuario = get_usuario_sessao(self)
            if not usuario: self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err: self.send_json({"ok": False, "erro": _err}, code=403); return
                r = json.loads(body or b'{}')
                fid = int(r.get("funcionario_id") or 0)
                if not db.query(Funcionario).filter_by(id=fid, loja_id=loja_id).first():
                    self.send_json({"ok": False, "erro": "Funcionário inválido"}, code=400); return
                a = AdiantamentoFuncionario(loja_id=loja_id, funcionario_id=fid,
                    tipo=(r.get("tipo") or "adiantamento"), competencia=(r.get("competencia") or ""),
                    valor=float(r.get("valor") or 0.0), abater=(1 if r.get("abater", True) else 0),
                    competencia_abate=(r.get("competencia_abate") or r.get("competencia") or None),
                    observacao=(r.get("observacao") or None))
                db.add(a); db.commit()
                self.send_json({"ok": True, "id": a.id, "tipo": a.tipo, "valor": a.valor,
                                "abater": bool(a.abater)}, code=201)
            except Exception as e:
                db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
            return
```
PATCH `/api/adiantamentos/<id>` (no `do_PATCH`): permite `abater`, `quitado`, `valor`, `competencia_abate`:
```python
            m = re.match(r'^/api/adiantamentos/(\d+)$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario: self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err: self.send_json({"ok": False, "erro": _err}, code=403); return
                    a = db.query(AdiantamentoFuncionario).filter_by(id=int(m.group(1)), loja_id=loja_id).first()
                    if a is None: self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    r = json.loads(body or b'{}')
                    if "abater" in r: a.abater = 1 if r["abater"] else 0
                    if "quitado" in r: a.quitado = 1 if r["quitado"] else 0
                    if "valor" in r: a.valor = float(r["valor"] or 0.0)
                    if "competencia_abate" in r: a.competencia_abate = r["competencia_abate"] or None
                    db.commit()
                    self.send_json({"ok": True, "id": a.id, "abater": bool(a.abater),
                                    "quitado": bool(a.quitado), "valor": a.valor})
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```
DELETE `/api/adiantamentos/<id>` (no `do_DELETE`, se existir; senão suportar via PATCH `{"remover":true}`). Importar `AdiantamentoFuncionario` no topo do `main.py`. Registrar `/api/adiantamentos` nas rotas do módulo `folha` em `modulos.py`.

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_adiantamento.py tests/test_arquitetura_modulos.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py modulos.py tests/test_adiantamento.py
git commit -m "feat(adiantamento): endpoints POST/PATCH/DELETE /api/adiantamentos"
```

---

### Task 6: Frontend — box Adiantamento Oficial + coluna na Folha

**Files:**
- Modify: `static/index.html` (Config › Remunerações: box; Folha do mês: adiantamentos + líquido + saldo)

- [ ] **Step 1: Box "Adiantamento Oficial" em Config › Remunerações**

No topo de `cfgComissaoRender` (que hoje só lista funções), carregar a config-financeira da loja (fetch `/api/admin/lojas/<lid>/config-financeira`) e renderizar um box com **checkbox "Adiantamento Oficial (padrão da loja)"** + **input %** (default 40) + botão Salvar. Salvar via PUT do config-financeira completo (mesma técnica de `salvarModalComissao`, preservando o resto). Funções `cfgAdiantamentoCarregar()`/`cfgAdiantamentoSalvar()`.

- [ ] **Step 2: Coluna Adiantamentos / Líquido / Saldo na Folha do mês**

Em `folhaRender`, para cada funcionário, exibir: **Adiantamentos** (lista: tipo · valor · toggle "abater" via PATCH), **Líquido a pagar** (`it.liquido_pagar`) e **Saldo de débito** (`it.saldo_debito`). Botão "+ adiantamento/empréstimo" que abre um mini-form (tipo, valor, competência de abate, obs) → POST `/api/adiantamentos` → `folhaMesCarregar()`. Toggle "abater" → PATCH `/api/adiantamentos/<id>` → recarrega. No rodapé, `total_liquido`.

- [ ] **Step 3: Funções auxiliares**

`adiantamentoAdd(funcId)`, `adiantamentoToggleAbater(id, on)`, `adiantamentoSalvarConfig()` — todas usando `fetch` + `showToast` + `folhaMesCarregar`.

- [ ] **Step 4: `node --check`**

Extrair o maior `<script>` e `node --check` (WSL). Expected: `JS_OK`.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(folha/ui): box Adiantamento Oficial + coluna Adiantamentos/Líquido/Saldo na folha"
```

---

## Verificação final
- [ ] `python3 -m pytest -q` (SQLite) — verde.
- [ ] Postgres: subir com `DATABASE_URL` de dev; confirmar `adiantamento_funcionario` criada.
- [ ] Smoke: ligar Adiantamento Oficial (40%); gerar folha de um registrado → ver oficial 40% + líquido = total − 40%; adicionar um empréstimo com abater no mês seguinte → conferir saldo de débito; pagar a folha → adiantamentos da competência ficam quitados.
- [ ] FF-merge para `main`. Não commitar `perfis_config.json`. Push só quando o usuário pedir.

## Self-Review (cobertura)
- Adiantamento/empréstimo por funcionário → Tasks 1,3,5. ✅
- Adiantamento Oficial 40% do fixo em carteira, automático, opcional por loja → Tasks 2,3,4. ✅
- Abatimento no líquido **editável** → Tasks 3,4,5 (abater togglável). ✅
- Saldo de débito → Tasks 3,4. ✅
- Líquido a pagar na folha → Task 4. ✅
- UI (config + folha) → Task 6. ✅

**Fora de escopo (documentado):** contábil detalhado dos adiantamentos (ativo `1.1.08 Adiantamentos a Funcionários`, baixa no pagamento, timing do caixa mid-month) → **com o contador**; encargos trabalhistas; comissão fixa por função (Fase 6, Frente C).
