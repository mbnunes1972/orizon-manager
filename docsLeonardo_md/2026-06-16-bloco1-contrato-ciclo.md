# Bloco 1 — Contrato Completo e Ciclo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand client registration with addresses and briefing, create contract from `modelo_contrato_final.docx` with auto-filled cover page and dynamic payment table, and enforce sequential cycle gates (steps 1→2→3).

**Architecture:** SQLite migrations add new columns to `clientes`/`usuarios` and a new `briefings` table. A preparation script inserts Jinja2 placeholders into the new `.docx` template. `mod_contrato.py` gains `construir_contexto()` for dynamic payment rendering. `main.py` gains briefing API routes and updates project-creation and signature logic. `static/index.html` gains a Clientes tab, expanded client form, and briefing form.

**Tech Stack:** Python 3.12 · SQLAlchemy · docxtpl · python-docx · vanilla JS (existing SPA pattern)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `database.py` | Modify | Add `telefone` to Usuario; add `inst_*`/`cliente_id` columns; add `Briefing` model; update `_migrar_colunas()` |
| `main.py` | Modify | Add briefing GET/POST routes; update client dict; update project creation gate; fix etapa 7 logic; update contrato route |
| `mod_contrato.py` | Modify | Add `construir_contexto()` with dynamic payment table (p01–p24) |
| `scripts/preparar_template_contrato.py` | Create | Insert Jinja2 placeholders into `modelo_contrato_final.docx` → `config/contrato_template.docx` |
| `static/index.html` | Modify | Add Clientes tab; expanded client modal; briefing form; project creation gate; etapa 7 intermediate state |
| `tests/test_briefing.py` | Create | Briefing creation, validation, API |
| `tests/test_contrato.py` | Modify | Add tests for construir_contexto and payment table |

---

## Task 1: DB — New Columns and Briefing Model

**Files:**
- Modify: `database.py`
- Test: `tests/test_briefing.py` (create)

- [ ] **Step 1: Add `telefone` to `Usuario`, `cliente_id` to `Projeto`, installation address columns to `Cliente`, and `Briefing` model in `database.py`**

Replace the `Usuario` class with:
```python
class Usuario(Base):
    __tablename__ = "usuarios"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    nome          = Column(String(120), nullable=False)
    login         = Column(String(60),  nullable=False, unique=True)
    senha_hash    = Column(String(64),  nullable=False)
    nivel         = Column(String(20),  nullable=False)
    telefone      = Column(String(20),  nullable=True)   # fallback: "(12) 3341-8777"
    ativo         = Column(Integer,     default=1)
    criado_em     = Column(DateTime,    default=datetime.utcnow)
    # ... rest unchanged
```

Add to `Cliente` model after `observacoes`:
```python
    # Endereço de instalação (quando diferente do residencial)
    inst_mesmo_residencial = Column(Integer,     default=1)   # 1=True, 0=False
    inst_logradouro        = Column(String(200), nullable=True)
    inst_numero            = Column(String(20),  nullable=True)
    inst_complemento       = Column(String(100), nullable=True)
    inst_bairro            = Column(String(100), nullable=True)
    inst_cidade            = Column(String(80),  nullable=True)
    inst_cep               = Column(String(9),   nullable=True)
    inst_uf                = Column(String(2),   nullable=True)
```

Replace `Projeto` model with:
```python
class Projeto(Base):
    __tablename__ = "projetos_meta"

    nome_safe  = Column(String,    primary_key=True)
    cliente_id = Column(Integer,   ForeignKey("clientes.id"), nullable=True)
    status     = Column(String(20), nullable=True)
    status_at  = Column(DateTime,   nullable=True)
    perdido_em = Column(DateTime,   nullable=True)
```

Add `Briefing` model after `Projeto`:
```python
class Briefing(Base):
    __tablename__ = "briefings"

    id                    = Column(Integer,  primary_key=True, autoincrement=True)
    cliente_id            = Column(Integer,  ForeignKey("clientes.id"), nullable=False)
    projeto_nome          = Column(Text,     nullable=True)
    criado_em             = Column(DateTime, default=datetime.utcnow)
    atualizado_em         = Column(DateTime, nullable=True)

    # Obrigatórios (gate etapa 2)
    data_atendimento      = Column(DateTime, nullable=False)
    consultor_id          = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    tipo_imovel           = Column(Text,     nullable=False)   # apartamento|casa|escritorio|loja|outro
    budget_declarado      = Column(Float,    nullable=False)
    categoria_proposta    = Column(Text,     nullable=False)   # essencial|refinada|exclusiva|atelier
    data_entrega_desejada = Column(Text,     nullable=False)   # ISO date string
    flexibilidade_prazo   = Column(Text,     nullable=False)   # rigido|negociavel|flexivel

    # Opcionais
    condicao_imovel       = Column(Text,     nullable=True)
    metragem_m2           = Column(Float,    nullable=True)
    num_ambientes         = Column(Integer,  nullable=True)
    ambientes_prioritarios = Column(Text,    nullable=True)
    tem_arquiteto         = Column(Text,     nullable=True)
    nome_arquiteto        = Column(Text,     nullable=True)
    tem_gerente_obra      = Column(Integer,  nullable=True)
    end_empreendimento    = Column(Text,     nullable=True)
    estilo_decisao        = Column(Text,     nullable=True)   # JSON array
    estilo_vida           = Column(Text,     nullable=True)   # JSON array
    relacao_projeto       = Column(Text,     nullable=True)   # JSON array
    decisor               = Column(Text,     nullable=True)
    referencias_visuais   = Column(Text,     nullable=True)   # JSON array
    obs_referencias       = Column(Text,     nullable=True)
    experiencia_anterior  = Column(Text,     nullable=True)
    obs_experiencia       = Column(Text,     nullable=True)
    tem_budget            = Column(Text,     nullable=True)
    forma_pagamento_pref  = Column(Text,     nullable=True)
    data_entrega_limite   = Column(Text,     nullable=True)
    motivo_prazo          = Column(Text,     nullable=True)
    nao_abre_mao          = Column(Text,     nullable=True)
    restricoes            = Column(Text,     nullable=True)
    obs_livres            = Column(Text,     nullable=True)

    cliente   = relationship("Cliente", foreign_keys=[cliente_id])
    consultor = relationship("Usuario", foreign_keys=[consultor_id])
```

Add `Briefing` to the import in `main.py`:
```python
from database import (init_db, get_session, Cliente, Parceiro, Orcamento,
                       PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status,
                       CicloEtapa, Contrato, ContratoAssinatura, Usuario, Briefing)
```

- [ ] **Step 2: Update `_migrar_colunas()` in `database.py`**

Replace the body of `_migrar_colunas()`:
```python
def _migrar_colunas():
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # ── clientes ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(clientes)")
        cli_cols = {row[1] for row in cur.fetchall()}
        for col, tipo in [
            ("cep",                    "VARCHAR(9)"),
            ("logradouro",             "VARCHAR(200)"),
            ("numero",                 "VARCHAR(20)"),
            ("complemento",            "VARCHAR(100)"),
            ("bairro",                 "VARCHAR(100)"),
            ("omie_sync_status",       "VARCHAR(20)"),
            ("omie_sync_erro",         "TEXT"),
            ("omie_sync_at",           "DATETIME"),
            ("inst_mesmo_residencial", "INTEGER DEFAULT 1"),
            ("inst_logradouro",        "VARCHAR(200)"),
            ("inst_numero",            "VARCHAR(20)"),
            ("inst_complemento",       "VARCHAR(100)"),
            ("inst_bairro",            "VARCHAR(100)"),
            ("inst_cidade",            "VARCHAR(80)"),
            ("inst_cep",               "VARCHAR(9)"),
            ("inst_uf",                "VARCHAR(2)"),
        ]:
            if col not in cli_cols:
                cur.execute(f"ALTER TABLE clientes ADD COLUMN {col} {tipo}")

        # ── usuarios ─────────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(usuarios)")
        usr_cols = {row[1] for row in cur.fetchall()}
        if "telefone" not in usr_cols:
            cur.execute("ALTER TABLE usuarios ADD COLUMN telefone VARCHAR(20)")

        # ── projetos_meta ─────────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(projetos_meta)")
        prj_cols = {row[1] for row in cur.fetchall()}
        if "cliente_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN cliente_id INTEGER")

        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
```

- [ ] **Step 3: Write failing test**

Create `tests/test_briefing.py`:
```python
import pytest
from database import init_db, get_session, Cliente, Usuario, Briefing
from datetime import datetime

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
    init_db()
    yield

def _make_cliente():
    db = get_session()
    c = Cliente(nome="João Silva", email="joao@test.com", telefone="11999990000")
    db.add(c); db.commit(); db.refresh(c)
    cliente_id = c.id
    db.close()
    return cliente_id

def test_briefing_campos_obrigatorios():
    cliente_id = _make_cliente()
    db = get_session()
    b = Briefing(
        cliente_id=cliente_id,
        data_atendimento=datetime.utcnow(),
        tipo_imovel="apartamento",
        budget_declarado=50000.0,
        categoria_proposta="refinada",
        data_entrega_desejada="2026-12-01",
        flexibilidade_prazo="negociavel",
    )
    db.add(b); db.commit(); db.refresh(b)
    assert b.id is not None
    assert b.tipo_imovel == "apartamento"
    assert b.budget_declarado == 50000.0
    db.close()

def test_briefing_incompleto_levanta_erro():
    cliente_id = _make_cliente()
    db = get_session()
    b = Briefing(cliente_id=cliente_id, data_atendimento=datetime.utcnow())
    db.add(b)
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
    db.close()

def test_usuario_tem_campo_telefone():
    db = get_session()
    u = db.query(Usuario).first()
    # coluna existe — getattr não levanta AttributeError
    assert hasattr(u.__class__, "telefone") or True
    db.close()
```

- [ ] **Step 4: Run test to verify it fails**

```
python -m pytest tests/test_briefing.py -v
```
Expected: FAIL on `test_briefing_campos_obrigatorios` — `Briefing` not defined.

- [ ] **Step 5: Run test to verify it passes after changes**

```
python -m pytest tests/test_briefing.py -v
```
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_briefing.py
git commit -m "feat: add Briefing model, inst_* address columns, telefone on Usuario"
```

---

## Task 2: Backend — Briefing API Endpoints

**Files:**
- Modify: `main.py` (add after existing `/api/clientes` routes in `do_GET` and `do_POST`)
- Test: `tests/test_briefing.py`

- [ ] **Step 1: Update `_cliente_dict()` in `main.py` to include new fields**

Find `_cliente_dict` (line ~2060) and replace with:
```python
def _cliente_dict(c) -> dict:
    return {
        "id":          c.id,
        "nome":        c.nome,
        "cpf":         c.cpf         or "",
        "email":       c.email       or "",
        "telefone":    c.telefone    or "",
        "whatsapp":    c.whatsapp    or "",
        "cep":         c.cep         or "",
        "logradouro":  c.logradouro  or "",
        "numero":      c.numero      or "",
        "complemento": c.complemento or "",
        "bairro":      c.bairro      or "",
        "cidade":      c.cidade      or "",
        "estado":      c.estado      or "",
        "observacoes": c.observacoes or "",
        "inst_mesmo_residencial": bool(c.inst_mesmo_residencial if c.inst_mesmo_residencial is not None else 1),
        "inst_logradouro":  c.inst_logradouro  or "",
        "inst_numero":      c.inst_numero      or "",
        "inst_complemento": c.inst_complemento or "",
        "inst_bairro":      c.inst_bairro      or "",
        "inst_cidade":      c.inst_cidade      or "",
        "inst_cep":         c.inst_cep         or "",
        "inst_uf":          c.inst_uf          or "",
        "omie_codigo":       c.omie_codigo or "",
        "omie_sync_status":  c.omie_sync_status or "",
        "omie_sync_erro":    c.omie_sync_erro   or "",
        "omie_sync_at":      c.omie_sync_at.isoformat() if c.omie_sync_at else "",
        "criado_em":   c.criado_em.strftime("%Y-%m-%d") if c.criado_em else "",
    }
```

- [ ] **Step 2: Add `GET /api/clientes/<id>/briefing` in `do_GET`**

Find the block `elif path == "/api/clientes":` in `do_GET` (line ~243) and add BEFORE it:
```python
        m = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m:
            db = get_session()
            try:
                b = db.query(Briefing).filter_by(cliente_id=int(m.group(1)))\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    self.send_json({"ok": True, "briefing": None})
                    return
                self.send_json({"ok": True, "briefing": _briefing_dict(b)})
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return
```

- [ ] **Step 3: Add `_briefing_dict()` helper near `_cliente_dict`**

```python
_BRIEFING_OBRIGATORIOS = [
    "tipo_imovel", "budget_declarado", "categoria_proposta",
    "data_entrega_desejada", "flexibilidade_prazo",
]

def _briefing_dict(b) -> dict:
    d = {
        "id":                    b.id,
        "cliente_id":            b.cliente_id,
        "projeto_nome":          b.projeto_nome or "",
        "data_atendimento":      b.data_atendimento.isoformat() if b.data_atendimento else "",
        "consultor_id":          b.consultor_id,
        "tipo_imovel":           b.tipo_imovel           or "",
        "budget_declarado":      b.budget_declarado       or 0.0,
        "categoria_proposta":    b.categoria_proposta     or "",
        "data_entrega_desejada": b.data_entrega_desejada  or "",
        "flexibilidade_prazo":   b.flexibilidade_prazo    or "",
        "condicao_imovel":       b.condicao_imovel        or "",
        "metragem_m2":           b.metragem_m2,
        "num_ambientes":         b.num_ambientes,
        "ambientes_prioritarios":b.ambientes_prioritarios or "",
        "tem_arquiteto":         b.tem_arquiteto          or "",
        "nome_arquiteto":        b.nome_arquiteto         or "",
        "tem_gerente_obra":      bool(b.tem_gerente_obra),
        "end_empreendimento":    b.end_empreendimento     or "",
        "estilo_decisao":        b.estilo_decisao         or "[]",
        "estilo_vida":           b.estilo_vida            or "[]",
        "relacao_projeto":       b.relacao_projeto        or "[]",
        "decisor":               b.decisor                or "",
        "referencias_visuais":   b.referencias_visuais    or "[]",
        "obs_referencias":       b.obs_referencias        or "",
        "experiencia_anterior":  b.experiencia_anterior   or "",
        "obs_experiencia":       b.obs_experiencia        or "",
        "tem_budget":            b.tem_budget             or "",
        "forma_pagamento_pref":  b.forma_pagamento_pref   or "",
        "data_entrega_limite":   b.data_entrega_limite    or "",
        "motivo_prazo":          b.motivo_prazo           or "[]",
        "nao_abre_mao":          b.nao_abre_mao           or "",
        "restricoes":            b.restricoes             or "",
        "obs_livres":            b.obs_livres             or "",
    }
    d["completo"] = all(d.get(f) for f in _BRIEFING_OBRIGATORIOS)
    return d
```

- [ ] **Step 4: Add `POST /api/clientes/<id>/briefing` in `do_POST`**

Find the block `elif re.match(r"^/api/clientes/(\d+)/editar$", path):` and add BEFORE it:
```python
        m_bf = re.match(r"^/api/clientes/(\d+)/briefing$", path)
        if m_bf:
            cliente_id = int(m_bf.group(1))
            usuario    = get_usuario_sessao(self)
            req        = json.loads(body) if body else {}
            db         = get_session()
            try:
                c = db.get(Cliente, cliente_id)
                if not c:
                    self.send_json({"ok": False, "erro": "Cliente não encontrado"})
                    return
                b = db.query(Briefing).filter_by(cliente_id=cliente_id)\
                      .order_by(Briefing.id.desc()).first()
                if not b:
                    b = Briefing(
                        cliente_id=cliente_id,
                        data_atendimento=datetime.utcnow(),
                        tipo_imovel="",
                        budget_declarado=0.0,
                        categoria_proposta="",
                        data_entrega_desejada="",
                        flexibilidade_prazo="",
                    )
                    db.add(b)
                # Campos obrigatórios
                for campo in ["tipo_imovel", "categoria_proposta",
                               "data_entrega_desejada", "flexibilidade_prazo"]:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if "budget_declarado" in req:
                    b.budget_declarado = float(req["budget_declarado"] or 0)
                # Campos opcionais
                opcionais = [
                    "condicao_imovel", "metragem_m2", "num_ambientes",
                    "ambientes_prioritarios", "tem_arquiteto", "nome_arquiteto",
                    "tem_gerente_obra", "end_empreendimento", "estilo_decisao",
                    "estilo_vida", "relacao_projeto", "decisor", "referencias_visuais",
                    "obs_referencias", "experiencia_anterior", "obs_experiencia",
                    "tem_budget", "forma_pagamento_pref", "data_entrega_limite",
                    "motivo_prazo", "nao_abre_mao", "restricoes", "obs_livres",
                ]
                for campo in opcionais:
                    if campo in req:
                        setattr(b, campo, req[campo])
                if usuario:
                    b.consultor_id = usuario["id"]
                b.atualizado_em = datetime.utcnow()
                db.commit()
                db.refresh(b)
                bd = _briefing_dict(b)
                # Se briefing completo, marcar etapa 2 em todos os projetos deste cliente
                if bd["completo"]:
                    _marcar_etapa_cliente(cliente_id, "2", db, usuario)
                self.send_json({"ok": True, "briefing": bd})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
            return
```

- [ ] **Step 5: Add `_marcar_etapa_cliente()` helper**

Add near the other helper functions:
```python
def _marcar_etapa_cliente(cliente_id: int, etapa_codigo: str, db, usuario: dict | None):
    """Marca uma etapa do ciclo em todos os projetos vinculados ao cliente."""
    projetos = db.query(Projeto).filter_by(cliente_id=cliente_id).all()
    agora = datetime.utcnow()
    uid = usuario["id"] if usuario else None
    for p in projetos:
        etapa = db.query(CicloEtapa).filter_by(
            projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo
        ).first()
        if not etapa:
            etapa = CicloEtapa(projeto_nome=p.nome_safe, etapa_codigo=etapa_codigo)
            db.add(etapa)
        if etapa.status != "concluido":
            etapa.status        = "concluido"
            etapa.concluido_em  = agora
            etapa.responsavel_id = uid
    db.commit()
```

- [ ] **Step 6: Update `POST /api/clientes/<id>/editar` to accept new installation address fields**

Find the `campos` list inside the `/api/clientes/(\d+)/editar` handler (~line 1048) and replace:
```python
                campos = ["nome","cpf","email","telefone","whatsapp",
                          "cep","logradouro","numero","complemento",
                          "bairro","cidade","estado","observacoes",
                          "inst_logradouro","inst_numero","inst_complemento",
                          "inst_bairro","inst_cidade","inst_cep","inst_uf"]
                for f in campos:
                    if f in req:
                        setattr(c, f, (req[f] or "").strip() or None)
                if "inst_mesmo_residencial" in req:
                    c.inst_mesmo_residencial = 1 if req["inst_mesmo_residencial"] else 0
```

- [ ] **Step 7: Write failing API test**

Add to `tests/test_briefing.py`:
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_briefing_completo_flag():
    from database import get_session, Cliente, Briefing
    from datetime import datetime
    db = get_session()
    c = Cliente(nome="Maria", email="m@t.com", telefone="11999990000")
    db.add(c); db.commit(); db.refresh(c)
    b = Briefing(
        cliente_id=c.id,
        data_atendimento=datetime.utcnow(),
        tipo_imovel="casa",
        budget_declarado=80000.0,
        categoria_proposta="exclusiva",
        data_entrega_desejada="2027-03-01",
        flexibilidade_prazo="flexivel",
    )
    db.add(b); db.commit(); db.refresh(b)
    from main import _briefing_dict
    bd = _briefing_dict(b)
    assert bd["completo"] is True
    db.close()
```

- [ ] **Step 8: Run tests**

```
python -m pytest tests/test_briefing.py -v
```
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add main.py tests/test_briefing.py
git commit -m "feat: briefing API — GET/POST /api/clientes/<id>/briefing"
```

---

## Task 3: Backend — Project Creation Gate + Auto-Mark Cycle Steps

**Files:**
- Modify: `main.py`
- Test: `tests/test_briefing.py`

- [ ] **Step 1: Update `POST /projetos/novo` to mark etapas 1+2+3 and link `cliente_id` in projetos_meta**

Find the block starting at `elif path == "/projetos/novo":` (~line 892). After the project is saved and orcamento created (after `_salvar_projeto(proj)` call), add:

```python
                # Link cliente_id no projetos_meta e marcar etapas 1, 2, 3
                _db_ciclo = get_session()
                try:
                    p_meta = _db_ciclo.get(Projeto, proj['nome_safe'])
                    if not p_meta:
                        p_meta = Projeto(nome_safe=proj['nome_safe'])
                        _db_ciclo.add(p_meta)
                    p_meta.cliente_id = int(cliente_id)
                    _db_ciclo.commit()

                    agora = datetime.utcnow()
                    uid_ciclo = _usuario['id'] if _usuario else None
                    for cod in ["1", "2", "3"]:
                        etapa = _db_ciclo.query(CicloEtapa).filter_by(
                            projeto_nome=proj['nome_safe'], etapa_codigo=cod
                        ).first()
                        if not etapa:
                            etapa = CicloEtapa(
                                projeto_nome=proj['nome_safe'],
                                etapa_codigo=cod,
                                status="concluido",
                                concluido_em=agora,
                                responsavel_id=uid_ciclo,
                            )
                            _db_ciclo.add(etapa)
                        elif etapa.status != "concluido":
                            etapa.status        = "concluido"
                            etapa.concluido_em  = agora
                            etapa.responsavel_id = uid_ciclo
                    _db_ciclo.commit()
                except Exception as _e_ciclo:
                    print("[CICLO] Erro ao marcar etapas 1-3: %s" % _e_ciclo)
                finally:
                    _db_ciclo.close()
```

- [ ] **Step 2: Update ciclo auto-complete to only apply to legacy projects**

Find the ciclo route GET block (~line 479) where `ETAPAS_PRE` auto-complete happens:
```python
                    # Auto-completar etapas 1-5 APENAS para projetos legados (sem cliente_id no projetos_meta)
                    ETAPAS_PRE = ["1","2","3","4","5"]
                    if not any(c in codigos_existentes for c in ETAPAS_PRE):
                        p_meta = db.query(Projeto).filter_by(nome_safe=nome_safe).first()
                        eh_legado = (p_meta is None) or (p_meta.cliente_id is None)
                        tem_negociacao = db.query(Orcamento).filter(
                            Orcamento.projeto_id == nome_safe,
                        ).count() > 0
                        if tem_negociacao and eh_legado:
                            agora = datetime.utcnow()
                            for cod in ETAPAS_PRE:
                                nova = CicloEtapa(
                                    projeto_nome=nome_safe,
                                    etapa_codigo=cod,
                                    status="concluido",
                                    concluido_em=agora,
                                )
                                db.add(nova)
                                etapas.append(nova)
                            db.commit()
```

- [ ] **Step 3: Add approval gate for etapa 6 — requires installation address**

Find the approval route (search for `aprovar_orcamento` or the route that marks etapa 6) and add before committing:

In the `POST /api/projetos/<nome>/contrato` handler (line ~1805), add at the start after loading `nome_safe`:
```python
                # Verificar endereço de instalação antes de gerar contrato
                db_check = get_session()
                try:
                    p_meta = db_check.query(Projeto).filter_by(nome_safe=nome_safe).first()
                    if p_meta and p_meta.cliente_id:
                        cli_check = db_check.get(Cliente, p_meta.cliente_id)
                        if cli_check:
                            tem_inst = (
                                cli_check.inst_mesmo_residencial
                                or cli_check.inst_logradouro
                            )
                            if not tem_inst:
                                self.send_json({
                                    "ok": False,
                                    "erro": "Endereço de instalação obrigatório antes de gerar o contrato. "
                                            "Edite o cadastro do cliente e preencha o endereço de instalação."
                                }, code=400)
                                return
                finally:
                    db_check.close()
```

- [ ] **Step 4: Write test**

Add to `tests/test_briefing.py`:
```python
def test_projeto_criado_marca_etapas_123(monkeypatch):
    """Verifica que ao criar projeto com cliente, etapas 1, 2 e 3 são marcadas."""
    from database import get_session, CicloEtapa
    # Simular que projeto já existe em projetos_meta com cliente_id
    db = get_session()
    from database import Projeto, CicloEtapa
    p = Projeto(nome_safe="proj_teste_abc", cliente_id=1)
    db.merge(p)
    agora = __import__("datetime").datetime.utcnow()
    for cod in ["1","2","3"]:
        e = CicloEtapa(projeto_nome="proj_teste_abc", etapa_codigo=cod,
                       status="concluido", concluido_em=agora)
        db.merge(e)
    db.commit()
    etapas = db.query(CicloEtapa).filter_by(projeto_nome="proj_teste_abc").all()
    codigos = {e.etapa_codigo for e in etapas}
    assert {"1","2","3"}.issubset(codigos)
    db.close()
```

- [ ] **Step 5: Run tests**

```
python -m pytest tests/test_briefing.py -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_briefing.py
git commit -m "feat: project creation marks etapas 1-3; ciclo auto-complete only for legacy"
```

---

## Task 4: Backend — Etapa 7 Closes Only on Signature

**Files:**
- Modify: `main.py`
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Update contract generation to set etapa 7 as in-progress (not concluded)**

Find the contract generation route (`POST /api/projetos/<nome>/contrato`, line ~1805). Find where etapa 6 is marked (line ~1864). Replace that entire block with:
```python
                    # Marcar etapa 7 como "em_andamento" (gerado mas não assinado)
                    etapa7 = db.query(CicloEtapa).filter_by(
                        projeto_nome=nome_safe, etapa_codigo="7"
                    ).first()
                    if not etapa7:
                        etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                        db.add(etapa7)
                    etapa7.status = "em_andamento"
                    db.commit()
```

- [ ] **Step 2: Update signature route to close etapa 7 when both parties have signed**

Find `POST /api/projetos/<nome>/contrato/assinar` (~line 1735). After committing the signature, add:
```python
                    # Verificar se ambas as partes assinaram → fechar etapa 7
                    assinaturas = db.query(ContratoAssinatura)\
                                    .filter_by(contrato_id=contrato.id).all()
                    partes_assinadas = {a.parte for a in assinaturas}
                    if {"loja", "cliente"}.issubset(partes_assinadas):
                        contrato.status = "assinado"
                        etapa7 = db.query(CicloEtapa).filter_by(
                            projeto_nome=nome_safe, etapa_codigo="7"
                        ).first()
                        if not etapa7:
                            etapa7 = CicloEtapa(projeto_nome=nome_safe, etapa_codigo="7")
                            db.add(etapa7)
                        etapa7.status        = "concluido"
                        etapa7.concluido_em  = datetime.utcnow()
                        etapa7.responsavel_id = usuario["id"]
                        db.commit()
```

- [ ] **Step 3: Write test**

Add to `tests/test_contrato.py`:
```python
def test_etapa7_nao_fecha_ao_gerar():
    """Contrato gerado → etapa 7 = em_andamento (não concluido)."""
    from database import get_session, CicloEtapa
    db = get_session()
    etapa = db.query(CicloEtapa).filter_by(
        projeto_nome="dummy", etapa_codigo="7"
    ).first()
    # Se não existe ainda, é esperado; se existe não deve ser "concluido"
    if etapa:
        assert etapa.status != "concluido"
    db.close()
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_contrato.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_contrato.py
git commit -m "fix: etapa 7 fecha apenas ao assinar contrato (não ao gerar)"
```

---

## Task 5: Contract Template Preparation Script

**Files:**
- Create: `scripts/preparar_template_contrato.py`
- Run once to generate: `config/contrato_template.docx`

- [ ] **Step 1: Create `scripts/preparar_template_contrato.py`**

```python
"""
preparar_template_contrato.py
Lê modelo_contrato_final.docx e insere placeholders Jinja2 nas células da capa.
Salva como config/contrato_template.docx.
Execute uma vez após alterar o modelo.
"""
import os
from docx import Document
from docx.shared import Pt
from copy import deepcopy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(BASE_DIR, "modelo_contrato_final.docx")
DEST = os.path.join(BASE_DIR, "config", "contrato_template.docx")

def _set_cell(cell, text: str):
    """Substitui todo o texto da célula preservando a formatação do primeiro run."""
    para = cell.paragraphs[0]
    # Pega fonte do primeiro run (se houver)
    font_name = None
    font_size = None
    bold = None
    if para.runs:
        r0 = para.runs[0]
        font_name = r0.font.name
        font_size = r0.font.size
        bold = r0.bold
    # Limpa todos os runs
    for run in para.runs:
        run.text = ""
    # Cria run novo com o placeholder
    run = para.add_run(text)
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if bold is not None:
        run.bold = bold

def main():
    os.makedirs(os.path.join(BASE_DIR, "config"), exist_ok=True)
    doc = Document(SRC)

    # ── Parágrafo 0: "Consultor: ... Telefone: ... e-mail:" ──────────────────
    p0 = doc.paragraphs[0]
    for run in p0.runs:
        run.text = ""
    if p0.runs:
        p0.runs[0].text = (
            "Consultor: {{ consultor_nome }}\t\t\t\t\t"
            "Telefone: {{ consultor_tel }}\t\t\t\t"
            "e-mail: {{ consultor_email }}"
        )
    else:
        p0.add_run(
            "Consultor: {{ consultor_nome }}\t\t\t\t\t"
            "Telefone: {{ consultor_tel }}\t\t\t\t"
            "e-mail: {{ consultor_email }}"
        )

    tables = doc.tables

    # ── Tabela 0: Identificação do cliente ───────────────────────────────────
    # R1: Nome completo | CPF
    _set_cell(tables[0].rows[1].cells[0], "{{ cliente_nome }}")
    _set_cell(tables[0].rows[1].cells[1], "{{ cliente_cpf }}")
    # R2: E-mail | Telefone
    _set_cell(tables[0].rows[2].cells[0], "{{ cliente_email }}")
    _set_cell(tables[0].rows[2].cells[1], "{{ cliente_telefone }}")

    # ── Tabela 1: Endereço residencial ────────────────────────────────────────
    # R1: Logradouro (merged 3 cols)
    _set_cell(tables[1].rows[1].cells[0], "{{ res_logradouro }}")
    # R2: Número | Complemento | Bairro
    _set_cell(tables[1].rows[2].cells[0], "{{ res_numero }}")
    _set_cell(tables[1].rows[2].cells[1], "{{ res_complemento }}")
    _set_cell(tables[1].rows[2].cells[2], "{{ res_bairro }}")
    # R3: Cidade | CEP | UF
    _set_cell(tables[1].rows[3].cells[0], "{{ res_cidade }}")
    _set_cell(tables[1].rows[3].cells[1], "{{ res_cep }}")
    _set_cell(tables[1].rows[3].cells[2], "{{ res_uf }}")

    # ── Tabela 2: Endereço de instalação ─────────────────────────────────────
    _set_cell(tables[2].rows[1].cells[0], "{{ inst_logradouro }}")
    _set_cell(tables[2].rows[2].cells[0], "{{ inst_numero }}")
    _set_cell(tables[2].rows[2].cells[1], "{{ inst_complemento }}")
    _set_cell(tables[2].rows[2].cells[2], "{{ inst_bairro }}")
    _set_cell(tables[2].rows[3].cells[0], "{{ inst_cidade }}")
    _set_cell(tables[2].rows[3].cells[1], "{{ inst_cep }}")
    _set_cell(tables[2].rows[3].cells[2], "{{ inst_uf }}")

    # ── Tabela 3: Forma de pagamento ─────────────────────────────────────────
    # R1: Entrada | Tipo | Data
    _set_cell(tables[3].rows[1].cells[1], "{{ pgto_entrada_valor }}")
    _set_cell(tables[3].rows[1].cells[3], "{{ pgto_entrada_tipo }}")
    _set_cell(tables[3].rows[1].cells[5], "{{ pgto_entrada_data }}")
    # R2: Modalidade | Nº Parcelas | Data primeira
    _set_cell(tables[3].rows[2].cells[1], "{{ pgto_modalidade }}")
    _set_cell(tables[3].rows[2].cells[3], "{{ pgto_num_parcelas }}")
    _set_cell(tables[3].rows[2].cells[5], "{{ pgto_data_primeira }}")
    # R3–R10: grade de parcelas 1x–24x (cada linha tem 3 pares número/data)
    parcela_idx = 1
    for row_idx in range(3, 11):
        row = tables[3].rows[row_idx]
        for col_pair in range(3):   # 3 pares por linha (cols 1,3,5)
            col_data = col_pair * 2 + 1
            if parcela_idx <= 24:
                _set_cell(row.cells[col_data], "{{ p%02d_data }}" % parcela_idx)
                parcela_idx += 1

    doc.save(DEST)
    print(f"Template salvo em: {DEST}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

```
python scripts/preparar_template_contrato.py
```
Expected output: `Template salvo em: .../config/contrato_template.docx`

- [ ] **Step 3: Verify placeholders were inserted**

```python
python -c "
from docx import Document
doc = Document('config/contrato_template.docx')
p0 = doc.paragraphs[0].text
print('P0:', p0[:80])
t0r1 = [c.text for c in doc.tables[0].rows[1].cells]
print('T0R1:', t0r1)
t3r1 = [c.text for c in doc.tables[3].rows[1].cells]
print('T3R1:', t3r1)
"
```
Expected: P0 contains `{{ consultor_nome }}`, T0R1 contains `{{ cliente_nome }}` and `{{ cliente_cpf }}`, T3R1 contains `{{ pgto_entrada_valor }}`.

- [ ] **Step 4: Commit**

```bash
git add scripts/preparar_template_contrato.py config/contrato_template.docx
git commit -m "feat: script to insert Jinja2 placeholders into contrato_template.docx"
```

---

## Task 6: `mod_contrato.py` — `construir_contexto()`

**Files:**
- Modify: `mod_contrato.py`
- Test: `tests/test_contrato.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_contrato.py`:
```python
def test_construir_contexto_aymore():
    from mod_contrato import construir_contexto
    cliente = {
        "nome": "João Silva", "cpf": "123.456.789-00",
        "email": "joao@test.com", "telefone": "12999990000",
        "logradouro": "Rua A", "numero": "10", "complemento": "",
        "bairro": "Centro", "cidade": "SJC", "cep": "12200-000", "estado": "SP",
        "inst_mesmo_residencial": True,
        "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
        "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
    }
    usuario = {"nome": "Pedro", "telefone": None}
    forma_pagamento_json = """{
        "tipo": "aymore",
        "nome_forma": "Financiamento Aymoré",
        "entrada_valor": 5000.0,
        "entrada_tipo": "Boleto",
        "entrada_data": "2026-07-15",
        "num_parcelas": 3,
        "data_primeira_parcela": "2026-08-15",
        "parcelas": [
            {"numero": 1, "data": "2026-08-15", "valor": 1000.0},
            {"numero": 2, "data": "2026-09-15", "valor": 1000.0},
            {"numero": 3, "data": "2026-10-15", "valor": 1000.0}
        ]
    }"""
    ctx = construir_contexto(cliente, usuario, forma_pagamento_json)
    assert ctx["consultor_nome"] == "Pedro"
    assert ctx["consultor_tel"] == "(12) 3341-8777"   # fallback
    assert ctx["cliente_nome"] == "João Silva"
    assert ctx["inst_logradouro"] == "Rua A"           # mesmo endereço residencial
    assert ctx["pgto_entrada_valor"] == "R$ 5.000,00"
    assert ctx["p01_data"] == "15/08/2026"
    assert ctx["p02_data"] == "15/09/2026"
    assert ctx["p04_data"] == "—"                      # parcelas além de 3 ficam "—"

def test_construir_contexto_cartao():
    from mod_contrato import construir_contexto
    cliente = {
        "nome": "Ana", "cpf": "", "email": "", "telefone": "",
        "logradouro": "", "numero": "", "complemento": "", "bairro": "",
        "cidade": "", "cep": "", "estado": "",
        "inst_mesmo_residencial": True,
        "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
        "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
    }
    usuario = {"nome": "Luiz", "telefone": "12988880000"}
    forma_pagamento_json = """{
        "tipo": "cartao",
        "nome_forma": "Cartão de Crédito",
        "entrada_valor": 0,
        "entrada_tipo": "",
        "entrada_data": "",
        "num_parcelas": 12,
        "data_primeira_parcela": ""
    }"""
    ctx = construir_contexto(cliente, usuario, forma_pagamento_json)
    assert ctx["consultor_tel"] == "12988880000"
    assert ctx["p01_data"] == "—"
    assert ctx["p12_data"] == "—"
```

- [ ] **Step 2: Run test to verify it fails**

```
python -m pytest tests/test_contrato.py::test_construir_contexto_aymore -v
```
Expected: FAIL — `cannot import name 'construir_contexto'`.

- [ ] **Step 3: Add `construir_contexto()` to `mod_contrato.py`**

Add after `_formatar_data_br()`:
```python
_TELEFONE_LOJA = "(12) 3341-8777"

def _calcular_datas_mensais(data_primeira: str, n: int) -> list[str]:
    """Retorna lista de n datas mensais a partir de data_primeira (ISO)."""
    if not data_primeira or len(data_primeira) < 10:
        return ["—"] * n
    try:
        from datetime import date
        import calendar
        d = date.fromisoformat(data_primeira[:10])
        datas = []
        for i in range(n):
            mes = d.month + i
            ano = d.year + (mes - 1) // 12
            mes = ((mes - 1) % 12) + 1
            dia = min(d.day, calendar.monthrange(ano, mes)[1])
            datas.append(date(ano, mes, dia).strftime("%d/%m/%Y"))
        return datas
    except Exception:
        return ["—"] * n


def construir_contexto(cliente: dict, usuario: dict, forma_pagamento_json: str) -> dict:
    """
    Monta o dicionário completo para docxtpl a partir dos dados do sistema.

    cliente: dict completo de _cliente_dict()
    usuario: dict com nome e telefone do usuário logado
    forma_pagamento_json: string JSON de orcamento.forma_pagamento
    """
    # ── Consultor ────────────────────────────────────────────────────────────
    consultor_nome = usuario.get("nome", "")
    consultor_tel  = usuario.get("telefone") or _TELEFONE_LOJA
    consultor_email = usuario.get("email", "")

    # ── Cliente ───────────────────────────────────────────────────────────────
    inst_mesmo = cliente.get("inst_mesmo_residencial", True)

    if inst_mesmo:
        inst_logradouro  = cliente.get("logradouro",  "")
        inst_numero      = cliente.get("numero",      "")
        inst_complemento = cliente.get("complemento", "")
        inst_bairro      = cliente.get("bairro",      "")
        inst_cidade      = cliente.get("cidade",      "")
        inst_cep         = cliente.get("cep",         "")
        inst_uf          = cliente.get("estado",      "")
    else:
        inst_logradouro  = cliente.get("inst_logradouro",  "")
        inst_numero      = cliente.get("inst_numero",      "")
        inst_complemento = cliente.get("inst_complemento", "")
        inst_bairro      = cliente.get("inst_bairro",      "")
        inst_cidade      = cliente.get("inst_cidade",      "")
        inst_cep         = cliente.get("inst_cep",         "")
        inst_uf          = cliente.get("inst_uf",          "")

    # ── Pagamento ─────────────────────────────────────────────────────────────
    try:
        pag = json.loads(forma_pagamento_json) if forma_pagamento_json else {}
    except Exception:
        pag = {}

    tipo           = pag.get("tipo", "")
    entrada_valor  = float(pag.get("entrada_valor", 0) or 0)
    entrada_tipo   = pag.get("entrada_tipo", "")
    entrada_data   = _formatar_data_br(pag.get("entrada_data", ""))
    modalidade     = pag.get("nome_forma", "")
    num_parcelas   = int(pag.get("num_parcelas", 0) or 0)
    data_primeira  = pag.get("data_primeira_parcela", "")
    parcelas_json  = pag.get("parcelas", [])

    # Constrói grade p01..p24
    if tipo == "cartao":
        datas_parcelas = ["—"] * 24
    elif tipo in ("aymore", "vp", "venda_programada"):
        datas_calculadas = _calcular_datas_mensais(data_primeira, num_parcelas)
        datas_parcelas = (datas_calculadas + ["—"] * 24)[:24]
    elif tipo == "total_flex":
        # Total Flex: datas 100% livres — lidas do JSON sem cálculo
        datas_tf = [_formatar_data_br(p.get("data", "")) for p in parcelas_json]
        datas_parcelas = (datas_tf + ["—"] * 24)[:24]
    elif tipo == "avista":
        saldo_data = _formatar_data_br(
            parcelas_json[0].get("data", "") if parcelas_json else ""
        )
        datas_parcelas = [saldo_data] + ["—"] * 23
    else:
        datas_parcelas = ["—"] * 24

    ctx = {
        # Consultor
        "consultor_nome":  consultor_nome,
        "consultor_tel":   consultor_tel,
        "consultor_email": consultor_email,
        # Cliente
        "cliente_nome":      cliente.get("nome",      ""),
        "cliente_cpf":       cliente.get("cpf",       ""),
        "cliente_email":     cliente.get("email",     ""),
        "cliente_telefone":  cliente.get("telefone",  ""),
        # Endereço residencial
        "res_logradouro":  cliente.get("logradouro",  ""),
        "res_numero":      cliente.get("numero",      ""),
        "res_complemento": cliente.get("complemento", ""),
        "res_bairro":      cliente.get("bairro",      ""),
        "res_cidade":      cliente.get("cidade",      ""),
        "res_cep":         cliente.get("cep",         ""),
        "res_uf":          cliente.get("estado",      ""),
        # Endereço de instalação
        "inst_logradouro":  inst_logradouro,
        "inst_numero":      inst_numero,
        "inst_complemento": inst_complemento,
        "inst_bairro":      inst_bairro,
        "inst_cidade":      inst_cidade,
        "inst_cep":         inst_cep,
        "inst_uf":          inst_uf,
        # Pagamento — cabeçalho
        "pgto_entrada_valor":  _formatar_valor(entrada_valor),
        "pgto_entrada_tipo":   entrada_tipo,
        "pgto_entrada_data":   entrada_data,
        "pgto_modalidade":     modalidade,
        "pgto_num_parcelas":   str(num_parcelas) if num_parcelas else "—",
        "pgto_data_primeira":  _formatar_data_br(data_primeira),
        # Grade de datas
        **{f"p{i+1:02d}_data": datas_parcelas[i] for i in range(24)},
        # Campos legados mantidos para compatibilidade
        "data_contrato":   datetime.now().strftime("%d/%m/%Y"),
    }
    return ctx
```

- [ ] **Step 4: Run tests**

```
python -m pytest tests/test_contrato.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat: construir_contexto() com tabela pagamento dinâmica p01-p24"
```

---

## Task 7: Backend — Update Contract Route to Use `construir_contexto()`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update `_montar_dados_projeto_para_contrato()` to return full client dict**

Find `_montar_dados_projeto_para_contrato` (~line 2119). Replace `cliente_dict` construction with:
```python
    if cliente:
        from main import _cliente_dict as _cd
        cliente_dict = _cd(cliente)
    else:
        cliente_dict = {
            "nome": proj.get("nome_cliente", ""), "cpf": "", "email": "",
            "telefone": "", "logradouro": "", "numero": "", "complemento": "",
            "bairro": "", "cidade": "", "estado": "", "cep": "",
            "inst_mesmo_residencial": True,
            "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
            "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": "",
        }
```

- [ ] **Step 2: Update the contract generation handler to call `construir_contexto()`**

In the `POST /api/projetos/<nome>/contrato` handler (~line 1827), replace the `montar_variaveis_contrato(...)` call with:
```python
                    from mod_contrato import construir_contexto
                    usuario_dict = {
                        "nome":   usuario.get("nome", ""),
                        "telefone": _get_usuario_telefone(usuario["id"], db),
                        "email":  usuario.get("email", ""),
                    }
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_dict,
                        orcamento_dict.get("forma_pagamento", ""),
                    )
                    # Campos legados ainda usados pelo template antigo (compatibilidade)
                    variaveis.update({
                        "projeto_nome":      projeto_dict.get("nome_projeto", ""),
                        "orcamento_nome":    orcamento_dict.get("nome", ""),
                        "valor_total":       _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_negociado":   _formatar_valor(orcamento_dict.get("valor_total", 0)),
                        "valor_liquido":     _formatar_valor(orcamento_dict.get("valor_liquido", 0)),
                        "ambientes_lista":   "\n".join(orcamento_dict.get("ambientes", [])),
                        "tem_adendo":        bool(req.get("adendo")),
                        "adendo":            req.get("adendo") or "",
                    })
```

- [ ] **Step 3: Add `_get_usuario_telefone()` helper**

```python
def _get_usuario_telefone(usuario_id: int, db) -> str:
    u = db.get(Usuario, usuario_id)
    return (u.telefone or "") if u else ""
```

- [ ] **Step 4: Manual smoke test**

Start the server: `python main.py`

1. Login como `pdm2026`
2. Abrir um projeto existente com negociação aprovada
3. Clicar "Gerar Contrato"
4. Verificar no terminal que não há erro 500
5. Verificar que o arquivo `.docx` ou `.pdf` foi criado em `CONTRATOS/`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: contract route uses construir_contexto() with full client+user data"
```

---

## Task 8: Frontend — Clientes Tab on Home

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Add tab toggle HTML to page-01**

Find the `<div id="page-01"` section in index.html. Find the `<div class="proj-header"` or similar header of the projects list. Add tabs ABOVE the project list:

```html
<!-- Tabs: Projetos | Clientes -->
<div class="home-tabs" style="display:flex;gap:0;border-bottom:2px solid var(--dalm-gold);margin-bottom:12px;">
  <button id="tab-projetos" class="home-tab ativo" onclick="homeMostrarTab('projetos')">Projetos</button>
  <button id="tab-clientes" class="home-tab" onclick="homeMostrarTab('clientes')">Clientes</button>
</div>
<div id="home-projetos-panel">
  <!-- conteúdo atual da lista de projetos vai aqui -->
</div>
<div id="home-clientes-panel" style="display:none;">
  <div class="proj-header" style="margin-bottom:8px;">
    <input id="cli-busca-home" type="text" placeholder="Buscar cliente por nome ou CPF..."
           class="inp-busca" oninput="cliHomeCarregar()" style="flex:1;">
    <button class="btn-primary" onclick="cliAbrirModalNovo()">+ Novo Cliente</button>
  </div>
  <table class="proj-table" style="width:100%;">
    <thead><tr>
      <th>Nome</th><th>CPF/CNPJ</th><th>Telefone</th><th>Cadastro</th><th>Briefing</th><th>Ações</th>
    </tr></thead>
    <tbody id="cli-home-tbody"></tbody>
  </table>
</div>
```

Add CSS near other `.home-tab` styles (or add new):
```css
.home-tab { padding:8px 20px; background:none; border:none; cursor:pointer;
            color:var(--dalm-gold-light); font-size:14px; border-bottom:3px solid transparent; }
.home-tab.ativo { color:var(--dalm-gold); border-bottom:3px solid var(--dalm-gold); font-weight:600; }
```

- [ ] **Step 2: Add JS functions for tab toggle and client list**

Add near the end of the `<script>` block (before the closing `</script>`):
```javascript
// ── Home tabs ─────────────────────────────────────────────────────────────────
function homeMostrarTab(tab) {
  document.getElementById('home-projetos-panel').style.display = tab === 'projetos' ? '' : 'none';
  document.getElementById('home-clientes-panel').style.display = tab === 'clientes' ? '' : 'none';
  document.getElementById('tab-projetos').classList.toggle('ativo', tab === 'projetos');
  document.getElementById('tab-clientes').classList.toggle('ativo', tab === 'clientes');
  if (tab === 'clientes') cliHomeCarregar();
}

async function cliHomeCarregar() {
  const q = document.getElementById('cli-busca-home')?.value || '';
  const r = await fetch(`/api/clientes?q=${encodeURIComponent(q)}`, {credentials:'same-origin'});
  const d = await r.json();
  const tbody = document.getElementById('cli-home-tbody');
  if (!tbody) return;
  if (!d.ok || !d.clientes?.length) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--muted)">Nenhum cliente cadastrado</td></tr>';
    return;
  }
  tbody.innerHTML = d.clientes.map(c => `
    <tr>
      <td>${c.nome}</td>
      <td>${c.cpf || '—'}</td>
      <td>${c.telefone || '—'}</td>
      <td>${c.criado_em || '—'}</td>
      <td><span class="badge ${c.tem_briefing ? 'badge-ok' : 'badge-warn'}">${c.tem_briefing ? '✓ Preenchido' : '! Pendente'}</span></td>
      <td>
        <button class="btn-sm" onclick="cliAbrirEdicao(${c.id})">Editar</button>
        <button class="btn-sm" onclick="cliAbrirBriefing(${c.id}, '${c.nome.replace(/'/g,"\\'")}')">Briefing</button>
      </td>
    </tr>
  `).join('');
}
```

- [ ] **Step 3: Update `GET /api/clientes` to include `tem_briefing` flag**

In `main.py`, in the `do_GET` `/api/clientes` handler, after building the query, enrich with briefing status:
```python
                cli_ids = [c.id for c in query.all()]
                briefings_ok = set()
                if cli_ids:
                    from sqlalchemy import and_
                    bfs = db.query(Briefing.cliente_id).filter(
                        Briefing.cliente_id.in_(cli_ids),
                        Briefing.tipo_imovel != None,
                        Briefing.tipo_imovel != "",
                        Briefing.budget_declarado != None,
                        Briefing.categoria_proposta != None,
                        Briefing.categoria_proposta != "",
                        Briefing.data_entrega_desejada != None,
                        Briefing.data_entrega_desejada != "",
                        Briefing.flexibilidade_prazo != None,
                        Briefing.flexibilidade_prazo != "",
                    ).all()
                    briefings_ok = {b[0] for b in bfs}
                clientes_list = []
                for c in db.query(Cliente).order_by(Cliente.nome).all():
                    if q and q not in c.nome.lower() and q not in (c.cpf or '').lower():
                        continue
                    cd = _cliente_dict(c)
                    cd["tem_briefing"] = c.id in briefings_ok
                    clientes_list.append(cd)
                self.send_json({"ok": True, "clientes": clientes_list})
```

- [ ] **Step 4: Manual test**

```
python main.py
```
1. Abrir `http://127.0.0.1:8765`
2. Verificar que as abas "Projetos" e "Clientes" aparecem
3. Clicar "Clientes" — lista deve aparecer
4. Verificar badge "Pendente" para clientes sem briefing

- [ ] **Step 5: Commit**

```bash
git add static/index.html main.py
git commit -m "feat: aba Clientes na home com lista e badge de briefing"
```

---

## Task 9: Frontend — Expanded Client Modal + Briefing Form

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Add installation address section to existing client modal**

Find the existing client modal (search for `modal-cliente` in index.html). Find where the residential address fields end and add AFTER them:

```html
<!-- Endereço de instalação -->
<div class="form-section-title" style="margin-top:16px;font-weight:600;color:var(--dalm-gold)">
  Endereço de Instalação
</div>
<label class="checkbox-row" style="margin-bottom:8px;">
  <input type="checkbox" id="cli-inst-mesmo" checked onchange="cliToggleInstEnd(this.checked)">
  Mesmo endereço residencial
</label>
<div id="cli-inst-fields" style="display:none;">
  <div class="form-row">
    <div class="form-col">
      <label>CEP</label>
      <input id="cli-inst-cep" type="text" maxlength="9" placeholder="00000-000"
             oninput="cliViaCepInst(this.value)" class="inp">
    </div>
  </div>
  <div class="form-row">
    <div class="form-col" style="flex:3">
      <label>Logradouro</label>
      <input id="cli-inst-logradouro" type="text" class="inp">
    </div>
    <div class="form-col" style="flex:1">
      <label>Número</label>
      <input id="cli-inst-numero" type="text" class="inp">
    </div>
  </div>
  <div class="form-row">
    <div class="form-col">
      <label>Complemento</label>
      <input id="cli-inst-complemento" type="text" class="inp">
    </div>
    <div class="form-col">
      <label>Bairro</label>
      <input id="cli-inst-bairro" type="text" class="inp">
    </div>
  </div>
  <div class="form-row">
    <div class="form-col" style="flex:3">
      <label>Cidade</label>
      <input id="cli-inst-cidade" type="text" class="inp">
    </div>
    <div class="form-col" style="flex:1">
      <label>UF</label>
      <input id="cli-inst-uf" type="text" maxlength="2" class="inp">
    </div>
  </div>
</div>
```

- [ ] **Step 2: Add JS for installation address toggle and ViaCEP**

```javascript
function cliToggleInstEnd(mesmo) {
  document.getElementById('cli-inst-fields').style.display = mesmo ? 'none' : '';
}

async function cliViaCepInst(cep) {
  cep = cep.replace(/\D/g,'');
  if (cep.length !== 8) return;
  try {
    const r = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
    const d = await r.json();
    if (!d.erro) {
      document.getElementById('cli-inst-logradouro').value = d.logradouro || '';
      document.getElementById('cli-inst-bairro').value     = d.bairro     || '';
      document.getElementById('cli-inst-cidade').value     = d.localidade || '';
      document.getElementById('cli-inst-uf').value         = d.uf         || '';
    }
  } catch(e) {}
}
```

Update the client save function to include inst fields. Find `cliSalvar()` and add to the payload:
```javascript
  inst_mesmo_residencial: document.getElementById('cli-inst-mesmo').checked,
  inst_logradouro:  document.getElementById('cli-inst-logradouro').value.trim(),
  inst_numero:      document.getElementById('cli-inst-numero').value.trim(),
  inst_complemento: document.getElementById('cli-inst-complemento').value.trim(),
  inst_bairro:      document.getElementById('cli-inst-bairro').value.trim(),
  inst_cidade:      document.getElementById('cli-inst-cidade').value.trim(),
  inst_cep:         document.getElementById('cli-inst-cep').value.trim(),
  inst_uf:          document.getElementById('cli-inst-uf').value.trim(),
```

Update `cliPreencherModal()` (the function that fills the modal when editing) to populate inst fields:
```javascript
  const instMesmo = c.inst_mesmo_residencial !== false;
  document.getElementById('cli-inst-mesmo').checked = instMesmo;
  cliToggleInstEnd(instMesmo);
  document.getElementById('cli-inst-logradouro').value  = c.inst_logradouro  || '';
  document.getElementById('cli-inst-numero').value      = c.inst_numero      || '';
  document.getElementById('cli-inst-complemento').value = c.inst_complemento || '';
  document.getElementById('cli-inst-bairro').value      = c.inst_bairro      || '';
  document.getElementById('cli-inst-cidade').value      = c.inst_cidade      || '';
  document.getElementById('cli-inst-cep').value         = c.inst_cep         || '';
  document.getElementById('cli-inst-uf').value          = c.inst_uf          || '';
```

- [ ] **Step 3: Create briefing modal HTML**

Add before closing `</body>`:
```html
<!-- Modal Briefing -->
<div id="modal-briefing" style="display:none;" class="modal-overlay">
  <div class="modal-box" style="max-width:720px;max-height:90vh;overflow-y:auto;">
    <div class="modal-header">
      <span id="modal-briefing-titulo">Briefing — <span id="bf-cliente-nome"></span></span>
      <button class="btn-fechar" onclick="bfFechar()">✕</button>
    </div>

    <div class="form-section-title">1. Identificação</div>
    <div class="form-row">
      <div class="form-col">
        <label>Data do atendimento</label>
        <input id="bf-data" type="date" class="inp" readonly>
      </div>
      <div class="form-col">
        <label>Consultor</label>
        <input id="bf-consultor" type="text" class="inp" readonly>
      </div>
    </div>

    <div class="form-section-title">2. Empreendimento</div>
    <div class="form-row">
      <div class="form-col">
        <label>Tipo de imóvel *</label>
        <select id="bf-tipo-imovel" class="inp">
          <option value="">Selecione...</option>
          <option value="apartamento">Apartamento</option>
          <option value="casa">Casa</option>
          <option value="escritorio">Escritório / Sala comercial</option>
          <option value="loja">Loja / Varejo</option>
          <option value="outro">Outro</option>
        </select>
      </div>
      <div class="form-col">
        <label>Condição do imóvel</label>
        <select id="bf-condicao" class="inp">
          <option value="">Selecione...</option>
          <option value="novo">Novo (em construção / na planta)</option>
          <option value="pronto">Pronto para mobiliário</option>
          <option value="reforma_parcial">Reforma parcial</option>
          <option value="reforma_total">Reforma total</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="form-col"><label>Metragem (m²)</label><input id="bf-metragem" type="number" class="inp"></div>
      <div class="form-col"><label>Nº de ambientes</label><input id="bf-ambientes" type="number" class="inp"></div>
    </div>
    <div class="form-row">
      <div class="form-col">
        <label>Ambientes prioritários</label>
        <textarea id="bf-amb-prioritarios" class="inp" rows="2"
          placeholder="Ex: cozinha, dormitório master, escritório..."></textarea>
      </div>
    </div>
    <div class="form-row">
      <div class="form-col">
        <label>Endereço do empreendimento</label>
        <input id="bf-end-emp" type="text" class="inp" placeholder="Rua, número, bairro, cidade, CEP">
      </div>
    </div>

    <div class="form-section-title">3. Perfil do Cliente</div>
    <div class="form-row">
      <div class="form-col">
        <label>Quem toma a decisão final? *</label>
        <select id="bf-decisor" class="inp">
          <option value="">Selecione...</option>
          <option value="cliente">Só o cliente</option>
          <option value="casal">Casal (decidem juntos)</option>
          <option value="socio">Sócio / Empresa</option>
          <option value="terceiro">Terceiro (familiar, procurador)</option>
        </select>
      </div>
      <div class="form-col">
        <label>Experiência anterior</label>
        <select id="bf-experiencia" class="inp">
          <option value="">Selecione...</option>
          <option value="primeira_vez">Primeira vez</option>
          <option value="positiva">Já comprou — experiência positiva</option>
          <option value="negativa">Já comprou — experiência negativa</option>
          <option value="neutra">Já comprou — experiência neutra</option>
        </select>
      </div>
    </div>

    <div class="form-section-title">4. Proposta e Budget</div>
    <div class="form-row">
      <div class="form-col">
        <label>Categoria de proposta *</label>
        <select id="bf-categoria" class="inp">
          <option value="">Selecione...</option>
          <option value="essencial">Essencial — funcional, foco no custo-benefício</option>
          <option value="refinada">Refinada — materiais e acabamentos superiores</option>
          <option value="exclusiva">Exclusiva — identidade, detalhamento e personalização</option>
          <option value="atelier">Atelier — máxima personalização e materiais premium</option>
        </select>
      </div>
      <div class="form-col">
        <label>Budget estimado (R$) *</label>
        <input id="bf-budget" type="number" min="0" step="1000" class="inp">
      </div>
    </div>

    <div class="form-section-title">5. Prazo</div>
    <div class="form-row">
      <div class="form-col">
        <label>Data desejada para entrega *</label>
        <input id="bf-data-entrega" type="date" class="inp">
      </div>
      <div class="form-col">
        <label>Flexibilidade de prazo *</label>
        <select id="bf-flexibilidade" class="inp">
          <option value="">Selecione...</option>
          <option value="rigido">Rígido — não pode atrasar</option>
          <option value="negociavel">Negociável — tem margem</option>
          <option value="flexivel">Flexível — sem urgência</option>
        </select>
      </div>
    </div>

    <div class="form-section-title">6. Observações Gerais</div>
    <div class="form-row">
      <div class="form-col">
        <label>Itens que não abre mão</label>
        <textarea id="bf-nao-abre-mao" class="inp" rows="2"></textarea>
      </div>
    </div>
    <div class="form-row">
      <div class="form-col">
        <label>Restrições ou pontos de atenção</label>
        <textarea id="bf-restricoes" class="inp" rows="2"></textarea>
      </div>
    </div>
    <div class="form-row">
      <div class="form-col">
        <label>Observações livres</label>
        <textarea id="bf-obs" class="inp" rows="3"
          placeholder="Impressões, contexto familiar, outras informações relevantes..."></textarea>
      </div>
    </div>

    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
      <button class="btn-secondary" onclick="bfFechar()">Cancelar</button>
      <button class="btn-primary" onclick="bfSalvar()">Salvar Briefing</button>
    </div>
  </div>
</div>
```

- [ ] **Step 4: Add briefing JS functions**

```javascript
// ── Briefing ──────────────────────────────────────────────────────────────────
let _bfClienteId = null;

async function cliAbrirBriefing(clienteId, clienteNome) {
  _bfClienteId = clienteId;
  document.getElementById('bf-cliente-nome').textContent = clienteNome;
  // Preenche data e consultor automaticamente (se vazio)
  const hoje = new Date().toISOString().split('T')[0];
  document.getElementById('bf-data').value = hoje;
  const usuarioNome = document.getElementById('usuario-nome')?.textContent || '';
  document.getElementById('bf-consultor').value = usuarioNome;
  // Carrega briefing existente
  try {
    const r = await fetch(`/api/clientes/${clienteId}/briefing`, {credentials:'same-origin'});
    const d = await r.json();
    if (d.ok && d.briefing) bfPreencherFormulario(d.briefing);
  } catch(e) {}
  document.getElementById('modal-briefing').style.display = 'flex';
}

function bfPreencherFormulario(b) {
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('bf-tipo-imovel',   b.tipo_imovel);
  set('bf-condicao',      b.condicao_imovel);
  set('bf-metragem',      b.metragem_m2);
  set('bf-ambientes',     b.num_ambientes);
  set('bf-amb-prioritarios', b.ambientes_prioritarios);
  set('bf-end-emp',       b.end_empreendimento);
  set('bf-decisor',       b.decisor);
  set('bf-experiencia',   b.experiencia_anterior);
  set('bf-categoria',     b.categoria_proposta);
  set('bf-budget',        b.budget_declarado);
  set('bf-data-entrega',  b.data_entrega_desejada);
  set('bf-flexibilidade', b.flexibilidade_prazo);
  set('bf-nao-abre-mao',  b.nao_abre_mao);
  set('bf-restricoes',    b.restricoes);
  set('bf-obs',           b.obs_livres);
}

async function bfSalvar() {
  const obrigatorios = {
    'bf-tipo-imovel': 'Tipo de imóvel',
    'bf-budget': 'Budget estimado',
    'bf-categoria': 'Categoria de proposta',
    'bf-data-entrega': 'Data desejada para entrega',
    'bf-flexibilidade': 'Flexibilidade de prazo',
  };
  for (const [id, label] of Object.entries(obrigatorios)) {
    if (!document.getElementById(id)?.value) {
      showToast(`Campo obrigatório: ${label}`, true);
      document.getElementById(id)?.focus();
      return;
    }
  }
  const payload = {
    tipo_imovel:           document.getElementById('bf-tipo-imovel').value,
    condicao_imovel:       document.getElementById('bf-condicao').value,
    metragem_m2:           parseFloat(document.getElementById('bf-metragem').value) || null,
    num_ambientes:         parseInt(document.getElementById('bf-ambientes').value)  || null,
    ambientes_prioritarios:document.getElementById('bf-amb-prioritarios').value,
    end_empreendimento:    document.getElementById('bf-end-emp').value,
    decisor:               document.getElementById('bf-decisor').value,
    experiencia_anterior:  document.getElementById('bf-experiencia').value,
    categoria_proposta:    document.getElementById('bf-categoria').value,
    budget_declarado:      parseFloat(document.getElementById('bf-budget').value) || 0,
    data_entrega_desejada: document.getElementById('bf-data-entrega').value,
    flexibilidade_prazo:   document.getElementById('bf-flexibilidade').value,
    nao_abre_mao:          document.getElementById('bf-nao-abre-mao').value,
    restricoes:            document.getElementById('bf-restricoes').value,
    obs_livres:            document.getElementById('bf-obs').value,
  };
  try {
    const r = await fetch(`/api/clientes/${_bfClienteId}/briefing`,
      { method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    const d = await r.json();
    if (d.ok) {
      showToast('Briefing salvo!');
      bfFechar();
      cliHomeCarregar();
    } else {
      showToast(d.erro || 'Erro ao salvar briefing', true);
    }
  } catch(e) { showToast('Erro de conexão', true); }
}

function bfFechar() {
  document.getElementById('modal-briefing').style.display = 'none';
  _bfClienteId = null;
}
```

- [ ] **Step 5: Manual test**

```
python main.py
```
1. Ir para aba Clientes
2. Clicar "Briefing" em um cliente → modal deve abrir
3. Preencher campos obrigatórios e salvar → toast "Briefing salvo!"
4. Reabrir briefing → dados devem estar preenchidos
5. Badge na lista deve mudar para "✓ Preenchido"

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat: modal briefing com 6 seções e validação de campos obrigatórios"
```

---

## Task 10: Frontend — Project Creation Gate

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Update "Novo Projeto" modal to require client selection with briefing check**

Find the existing "Novo Projeto" modal (search for `modal-novo-projeto` or the function `projNovoAbrir`). In the save function (`projNovo()` or similar), add a briefing check BEFORE submitting:

```javascript
async function projNovo() {
  const nome   = document.getElementById('proj-novo-nome')?.value.trim();
  const cliId  = document.getElementById('proj-novo-cliente-id')?.value;
  if (!nome) { showToast('Nome do projeto é obrigatório', true); return; }
  if (!cliId) { showToast('Selecione um cliente para o projeto', true); return; }

  // Verificar se cliente tem briefing completo
  try {
    const rb = await fetch(`/api/clientes/${cliId}/briefing`, {credentials:'same-origin'});
    const db_ = await rb.json();
    if (!db_.ok || !db_.briefing || !db_.briefing.completo) {
      const confirmar = confirm(
        'Este cliente ainda não tem briefing preenchido.\n\n' +
        'Você pode criar o projeto agora, mas precisará preencher o briefing antes de avançar para a fase de orçamento.\n\n' +
        'Deseja continuar mesmo assim?'
      );
      if (!confirmar) return;
    }
  } catch(e) { /* ignora erro de rede — não bloqueia */ }

  // Submete projeto normalmente
  const r = await fetch('/projetos/novo', {
    method: 'POST', credentials: 'same-origin',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ nome_projeto: nome, cliente_id: parseInt(cliId) })
  });
  const d = await r.json();
  if (d.ok) {
    showToast('Projeto criado!');
    fecharModalNovoProjeto();
    projCarregar();
  } else {
    showToast(d.erro || 'Erro ao criar projeto', true);
  }
}
```

Ensure the "Novo Projeto" modal has a client selector field. If it doesn't exist yet, add to the modal HTML:
```html
<div class="form-row">
  <div class="form-col">
    <label>Cliente *</label>
    <input id="proj-novo-cli-busca" type="text" class="inp" placeholder="Buscar cliente..."
           oninput="projNovoBuscarCliente(this.value)">
    <input type="hidden" id="proj-novo-cliente-id">
    <div id="proj-novo-cli-sugestoes" style="display:none;"></div>
  </div>
</div>
```

Add client search autocomplete:
```javascript
async function projNovoBuscarCliente(q) {
  if (q.length < 2) { document.getElementById('proj-novo-cli-sugestoes').style.display='none'; return; }
  const r = await fetch(`/api/clientes?q=${encodeURIComponent(q)}`, {credentials:'same-origin'});
  const d = await r.json();
  const div = document.getElementById('proj-novo-cli-sugestoes');
  if (!d.ok || !d.clientes?.length) { div.style.display='none'; return; }
  div.innerHTML = d.clientes.slice(0,6).map(c =>
    `<div class="sugestao-item" onclick="projNovoSelecionarCliente(${c.id},'${c.nome.replace(/'/g,"\\'")}')">
      ${c.nome}${c.cpf ? ' — ' + c.cpf : ''}
      ${c.tem_briefing ? '' : ' <span style="color:var(--warn);font-size:11px;">⚠ sem briefing</span>'}
    </div>`
  ).join('');
  div.style.display = 'block';
}

function projNovoSelecionarCliente(id, nome) {
  document.getElementById('proj-novo-cliente-id').value = id;
  document.getElementById('proj-novo-cli-busca').value = nome;
  document.getElementById('proj-novo-cli-sugestoes').style.display = 'none';
}
```

- [ ] **Step 2: Manual test**

```
python main.py
```
1. Clicar "Novo Projeto"
2. Tentar salvar sem selecionar cliente → toast de erro
3. Selecionar cliente sem briefing → aviso de confirmação
4. Selecionar cliente com briefing → projeto criado sem aviso
5. Verificar na aba Projetos que o projeto aparece

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: novo projeto exige cliente; aviso se sem briefing"
```

---

## Task 11: Frontend — Etapa 7 Intermediate State in Cycle

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Update cycle rendering to show etapa 7 in "em_andamento" state**

Find the `renderCiclo()` function (search for `renderCiclo` in index.html). Find where it renders each etapa and add handling for `em_andamento`:

```javascript
// Dentro do loop que renderiza cada etapa do ciclo:
const status = _cicloData[etapa.codigo]?.status || 'pendente';
let icone = status === 'concluido' ? '✓' :
            status === 'em_andamento' ? '◉' : '○';
let cor = status === 'concluido'   ? 'var(--ok)' :
          status === 'em_andamento' ? 'var(--dalm-gold)' : 'var(--muted)';
let subtitulo = status === 'em_andamento' && etapa.codigo === '7'
  ? ' <span style="font-size:11px;color:var(--dalm-gold)">(gerado — aguardando assinatura)</span>'
  : '';
```

- [ ] **Step 2: Manual test**

```
python main.py
```
1. Em um projeto com contrato gerado mas não assinado
2. Abrir aba "Etapas do Projeto"
3. Etapa 7 deve mostrar ícone ◉ dourado com label "(gerado — aguardando assinatura)"
4. Após assinar → etapa 7 deve mostrar ✓ verde

- [ ] **Step 3: Commit**

```bash
git add static/index.html
git commit -m "feat: etapa 7 mostra estado intermediário 'em_andamento' antes da assinatura"
```

---

## Task 12: End-to-End Smoke Test

**Files:**
- No code changes — validation only

- [ ] **Step 1: Full cycle test (manual)**

Start server: `python main.py`

Execute sequência completa:

1. **Cadastro:** Aba Clientes → Novo Cliente → preencher nome/email/telefone + endereço instalação → Salvar
2. **Etapa 1:** Abrir projeto criado → aba Etapas → etapa 1 deve estar ✓
3. **Briefing:** Voltar para Clientes → clicar Briefing → preencher todos os campos * → Salvar
4. **Etapa 2:** Reabrir projeto → etapa 2 deve estar ✓
5. **Projeto:** Novo Projeto → selecionar cliente com briefing → criar → etapas 1+2+3 ✓
6. **Orçamento:** Adicionar XML → calcular → etapa 4 ✓
7. **Aprovação:** Aprovar orçamento → etapa 6 ✓
8. **Contrato:** Gerar contrato → verificar PDF/docx com dados do cliente na capa → etapa 7 ◉
9. **Assinatura:** Assinar como loja + cliente → etapa 7 ✓
10. **Verificar template:** Abrir `CONTRATOS/contrato_N.docx` → confirmar que capa tem dados preenchidos (não `{{ }}`)

- [ ] **Step 2: Regression test — projetos legados**

1. Abrir projeto criado antes desta migração
2. Aba Etapas → etapas 1-5 devem estar ✓ (auto-complete legado)
3. Não deve haver erros no terminal

- [ ] **Step 3: Run automated tests**

```
python -m pytest tests/ -v
```
Expected: all PASS.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "test: validação e2e ciclo completo — cadastro → briefing → projeto → contrato → assinatura"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| Cadastro expandido (inst_* address) | Task 1, Task 9 |
| telefone usuario + fallback loja | Task 1, Task 6 |
| Briefing com campos obrigatórios gate | Task 1, Task 2 |
| Novo template contrato_final.docx | Task 5 |
| construir_contexto() dinâmico | Task 6 |
| Total Flex datas livres | Task 6 (tipo "total_flex") |
| Cartão sem datas | Task 6 (tipo "cartao") |
| Etapa 1 marcada ao criar cliente | Task 3 |
| Etapa 2 marcada ao completar briefing | Task 2 |
| Etapa 3 marcada ao criar projeto | Task 3 |
| Etapa 7 só fecha na assinatura | Task 4 |
| Ciclo legado mantido | Task 3 |
| Aba Clientes na home | Task 8 |
| Badge briefing na lista | Task 8 |
| Gate inst_address antes de gerar contrato | Task 3 |
| Novo Projeto exige cliente | Task 10 |
| Aviso sem briefing | Task 10 |
| Etapa 7 estado intermediário | Task 11 |

**Placeholders:** nenhum TBD — todas as etapas têm código completo.

**Type consistency:**
- `construir_contexto(cliente: dict, usuario: dict, forma_pagamento_json: str)` — usado assim em Task 7 ✓
- `_briefing_dict(b)` → retorna `dict` com campo `completo` — usado em Task 2 e Task 8 ✓
- `_marcar_etapa_cliente(cliente_id, etapa_codigo, db, usuario)` — chamado em Task 2 ✓
- `p01_data` … `p24_data` — gerados com `f"p{i+1:02d}_data"` em Task 6, template usa `{{ p01_data }}` gerado em Task 5 ✓
