# Multi-tenant F1 — Fundação de dados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preparar todo o schema para multi-tenant (`redes`, `lojas`, parceiros M:N, colunas `loja_id`/`rede_id`) com migração + backfill, **sem alterar nenhum comportamento observável**.

**Architecture:** Schema único SQLite com colunas de tenant. F1 é puramente aditiva: novas tabelas via `Base.metadata.create_all`, novas colunas em tabelas existentes via `_migrar_colunas()`, e uma migração de dados idempotente `tenancy_v1_2026` em `_run_migracoes()` que cria a loja seed (das constantes do contrato) e faz backfill de todos os registros existentes. Nenhuma rota, UI ou query de leitura muda.

**Tech Stack:** Python, SQLAlchemy (ORM + `Base.metadata.create_all`), sqlite3 (migrações raw), pytest (testes com SQLite in-memory / temp file).

**Spec:** `docs/superpowers/specs/2026-06-20-multitenant-f1-fundacao-design.md`

---

## Estrutura de arquivos

- **Modificar `database.py`:**
  - Novos models `Rede`, `Loja`, `ParceiroLoja`.
  - Colunas de tenant nos models existentes (`Usuario`, `Cliente`, `Projeto`, `Orcamento`, `Contrato`, `Parceiro`).
  - Constantes `_SEED_LOJA_*` (espelham `mod_contrato.py`, evita import circular).
  - `_migrar_colunas()`: ALTERs das colunas de tenant.
  - `_run_migracoes()`: migração `tenancy_v1_2026` (loja seed + backfill).
  - Helper `loja_seed_id(db)`.
- **Modificar `seed.py`:**
  - Função pura `criar_usuarios_seed(db, usuarios, loja_id)`.
  - `seed()` passa a vincular os usuários à loja seed.
- **Criar testes:**
  - `tests/test_tenancy_schema.py` (Task 1)
  - `tests/test_tenancy_colunas.py` (Task 2)
  - `tests/test_tenancy_migracao.py` (Task 3)
  - `tests/test_tenancy_seed.py` (Task 4)

**Nenhuma mudança em `main.py`, `mod_contrato.py`, `static/index.html`.**

---

## Task 1: Models de tenancy + colunas (schema para DBs novos)

**Files:**
- Modify: `database.py` (models)
- Test: `tests/test_tenancy_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_schema.py
from sqlalchemy import create_engine, inspect
import database


def _insp():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    return inspect(eng)


def test_tabelas_de_tenancy_criadas():
    insp = _insp()
    tabelas = set(insp.get_table_names())
    assert {"redes", "lojas", "parceiro_lojas"} <= tabelas


def test_colunas_de_tenant_nas_entidades_de_topo():
    insp = _insp()
    def cols(t):
        return {c["name"] for c in insp.get_columns(t)}
    assert {"loja_id", "rede_id"} <= cols("usuarios")
    assert "loja_id" in cols("clientes")
    assert "loja_id" in cols("projetos_meta")
    assert "loja_id" in cols("orcamentos")
    assert "loja_id" in cols("contratos")
    assert {"rede_id", "abrangencia"} <= cols("parceiros")
    assert {"parceiro_id", "loja_id", "comissao_padrao_pct", "ativo"} <= cols("parceiro_lojas")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_schema.py -v`
Expected: FAIL — `redes`/`lojas`/`parceiro_lojas` não existem; `loja_id` ausente.

- [ ] **Step 3: Add the three new models**

Adicionar em `database.py` logo após a classe `Parceiro` (≈ linha 168), antes de `class Projeto`:

```python
class Rede(Base):
    """Rede (franquia) que agrupa lojas. Loja avulsa tem rede_id NULL."""
    __tablename__ = "redes"

    id        = Column(Integer,     primary_key=True, autoincrement=True)
    nome      = Column(String(150), nullable=False)
    cnpj      = Column(String(18),  nullable=True)
    ativo     = Column(Integer,     default=1)
    criado_em = Column(DateTime,    default=datetime.utcnow)


class Loja(Base):
    """Loja (tenant). Pertence a uma rede ou é avulsa (rede_id NULL)."""
    __tablename__ = "lojas"

    id          = Column(Integer,     primary_key=True, autoincrement=True)
    rede_id     = Column(Integer,     ForeignKey("redes.id"), nullable=True)  # NULL = avulsa
    nome        = Column(String(150), nullable=False)
    cnpj        = Column(String(18),  nullable=True)
    codigo      = Column(String(8),   nullable=True, unique=True)   # 3 letras p/ num contrato
    telefone    = Column(String(20),  nullable=True)
    email       = Column(String(120), nullable=True)
    cep         = Column(String(9),   nullable=True)
    logradouro  = Column(String(200), nullable=True)
    numero      = Column(String(20),  nullable=True)
    complemento = Column(String(100), nullable=True)
    bairro      = Column(String(100), nullable=True)
    cidade      = Column(String(80),  nullable=True)
    estado      = Column(String(2),   nullable=True)
    testemunha1_nome = Column(String(120), nullable=True)
    testemunha1_cpf  = Column(String(14),  nullable=True)
    testemunha2_nome = Column(String(120), nullable=True)
    testemunha2_cpf  = Column(String(14),  nullable=True)
    ativo       = Column(Integer,  default=1)
    criado_em   = Column(DateTime, default=datetime.utcnow)


class ParceiroLoja(Base):
    """Vínculo M:N parceiro × loja, com comissão própria por loja."""
    __tablename__ = "parceiro_lojas"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    parceiro_id         = Column(Integer, ForeignKey("parceiros.id"), nullable=False)
    loja_id             = Column(Integer, ForeignKey("lojas.id"),     nullable=False)
    comissao_padrao_pct = Column(Float,   default=0.0)
    ativo               = Column(Integer, default=1)
```

- [ ] **Step 4: Add tenant columns to existing models**

Em `database.py`, adicionar as colunas (mantendo o alinhamento do arquivo):

`Usuario` (após `criado_em`, ≈ linha 34):
```python
    loja_id       = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    rede_id       = Column(Integer, ForeignKey("redes.id"), nullable=True)
```

`Cliente` (no fim das colunas da classe):
```python
    loja_id       = Column(Integer, ForeignKey("lojas.id"), nullable=True)
```

`Parceiro` (após `criado_em`, ≈ linha 167):
```python
    rede_id             = Column(Integer,    ForeignKey("redes.id"), nullable=True)
    abrangencia         = Column(String(10), default="loja")   # loja | rede
```

`Projeto` (após `parametros_json`, ≈ linha 179):
```python
    loja_id    = Column(Integer, ForeignKey("lojas.id"), nullable=True)
```

`Orcamento` — adicionar `loja_id = Column(Integer, ForeignKey("lojas.id"), nullable=True)` no fim das colunas da classe.

`Contrato` (após `d4sign_uuid`, ≈ linha 326):
```python
    loja_id              = Column(Integer, ForeignKey("lojas.id"), nullable=True)
```

> `Float` já está importado em `database.py` (usado em `PoolAmbiente`). Não adicionar import novo.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_schema.py -v`
Expected: PASS (2 testes).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_tenancy_schema.py
git commit -m "feat(db): models Rede/Loja/ParceiroLoja + colunas de tenant"
```

---

## Task 2: `_migrar_colunas` adiciona colunas de tenant em DBs existentes

**Files:**
- Modify: `database.py` (`_migrar_colunas`, ≈ linhas 356-444)
- Test: `tests/test_tenancy_colunas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_colunas.py
import sqlite3
import database

_TABELAS_LEGADO = [
    "clientes", "usuarios", "projetos_meta", "contratos",
    "orcamentos", "orcamento_ambientes", "briefings", "parceiros",
]


def _db_legado(path):
    """Cria um DB 'antigo': as tabelas existem mas sem as colunas de tenant."""
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    for t in _TABELAS_LEGADO:
        cur.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


def test_migrar_colunas_adiciona_tenant(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)

    database._migrar_colunas()

    conn = sqlite3.connect(db)
    def cols(t):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({t})")}
    assert {"loja_id", "rede_id"} <= cols("usuarios")
    assert "loja_id" in cols("clientes")
    assert "loja_id" in cols("projetos_meta")
    assert "loja_id" in cols("orcamentos")
    assert "loja_id" in cols("contratos")
    assert {"rede_id", "abrangencia"} <= cols("parceiros")
    conn.close()


def test_migrar_colunas_idempotente(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    database._migrar_colunas()   # 2ª vez não pode quebrar
    conn = sqlite3.connect(db)
    assert "loja_id" in {r[1] for r in conn.execute("PRAGMA table_info(clientes)")}
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_colunas.py -v`
Expected: FAIL — `loja_id`/`rede_id`/`abrangencia` ausentes.

- [ ] **Step 3: Add tenant ALTERs to `_migrar_colunas`**

Em `database.py`, dentro de `_migrar_colunas`:

(a) No bloco `clientes` (lista em ≈ linha 366-382), acrescentar à lista de tuplas:
```python
            ("loja_id",                "INTEGER"),
```

(b) No bloco `usuarios` (≈ linha 387-391), logo após o `if "telefone" ...`:
```python
        for col in ("loja_id", "rede_id"):
            if col not in usr_cols:
                cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} INTEGER")
```

(c) No bloco `projetos_meta` (≈ linha 393-399), acrescentar:
```python
        if "loja_id" not in prj_cols:
            cur.execute("ALTER TABLE projetos_meta ADD COLUMN loja_id INTEGER")
```

(d) No bloco `contratos` (lista em ≈ linha 404-413), acrescentar à lista:
```python
            ("loja_id",         "INTEGER"),
```

(e) No bloco `orcamentos` (lista em ≈ linha 418-425), acrescentar à lista:
```python
            ("loja_id",         "INTEGER"),
```

(f) Adicionar um bloco novo para `parceiros`, logo antes de `conn.commit()` (≈ linha 440):
```python
        # ── parceiros (tenant) ────────────────────────────────────────────────
        cur.execute("PRAGMA table_info(parceiros)")
        par_cols = {row[1] for row in cur.fetchall()}
        if "rede_id" not in par_cols:
            cur.execute("ALTER TABLE parceiros ADD COLUMN rede_id INTEGER")
        if "abrangencia" not in par_cols:
            cur.execute("ALTER TABLE parceiros ADD COLUMN abrangencia VARCHAR(10) DEFAULT 'loja'")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_colunas.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_tenancy_colunas.py
git commit -m "feat(db): _migrar_colunas adiciona colunas de tenant (DBs existentes)"
```

---

## Task 3: Migração de dados `tenancy_v1_2026` (loja seed + backfill)

**Files:**
- Modify: `database.py` (constantes `_SEED_LOJA_*` + bloco em `_run_migracoes`)
- Test: `tests/test_tenancy_migracao.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_migracao.py
import sqlite3
import database


def _conn_tenancy():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE lojas (
        id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, codigo TEXT,
        telefone TEXT, email TEXT,
        testemunha1_nome TEXT, testemunha1_cpf TEXT,
        testemunha2_nome TEXT, testemunha2_cpf TEXT, ativo INTEGER)""")
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT, loja_id INTEGER)")
    cur.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE projetos_meta (nome_safe TEXT PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE orcamentos (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("CREATE TABLE contratos (id INTEGER PRIMARY KEY, loja_id INTEGER)")
    cur.execute("""CREATE TABLE parceiros (
        id INTEGER PRIMARY KEY, comissao_padrao_pct REAL, abrangencia TEXT, rede_id INTEGER)""")
    cur.execute("""CREATE TABLE parceiro_lojas (
        id INTEGER PRIMARY KEY, parceiro_id INTEGER, loja_id INTEGER,
        comissao_padrao_pct REAL, ativo INTEGER)""")
    conn.commit()
    return conn


def test_cria_loja_seed_e_backfill():
    conn = _conn_tenancy()
    cur = conn.cursor()
    cur.execute("INSERT INTO usuarios(id, nivel) VALUES (1, 'diretor')")
    cur.execute("INSERT INTO clientes(id) VALUES (1)")
    cur.execute("INSERT INTO projetos_meta(nome_safe) VALUES ('proj_a')")
    cur.execute("INSERT INTO orcamentos(id) VALUES (1)")
    cur.execute("INSERT INTO contratos(id) VALUES (1)")
    cur.execute("INSERT INTO parceiros(id, comissao_padrao_pct) VALUES (1, 5.0)")
    conn.commit()

    database._run_migracoes(conn)

    lojas = conn.execute("SELECT id, codigo, cnpj FROM lojas").fetchall()
    assert len(lojas) == 1
    loja_id, codigo, cnpj = lojas[0]
    assert codigo == "INS"
    assert cnpj == "19.152.134/0001-56"

    for tbl in ("usuarios", "clientes", "orcamentos", "contratos"):
        nulos = conn.execute(f"SELECT COUNT(*) FROM {tbl} WHERE loja_id IS NULL").fetchone()[0]
        assert nulos == 0, tbl
    assert conn.execute("SELECT loja_id FROM projetos_meta").fetchone()[0] == loja_id

    vinc = conn.execute(
        "SELECT parceiro_id, loja_id, comissao_padrao_pct FROM parceiro_lojas").fetchall()
    assert vinc == [(1, loja_id, 5.0)]
    assert conn.execute("SELECT abrangencia FROM parceiros WHERE id=1").fetchone()[0] == "loja"


def test_idempotente():
    conn = _conn_tenancy()
    conn.execute("INSERT INTO parceiros(id, comissao_padrao_pct) VALUES (1, 5.0)")
    conn.commit()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    assert conn.execute("SELECT COUNT(*) FROM lojas").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM parceiro_lojas").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_migracao.py -v`
Expected: FAIL — nenhuma loja criada / `parceiro_lojas` vazio.

- [ ] **Step 3: Add seed constants**

Em `database.py`, imediatamente acima de `def _tabela_existe(cur, nome):` (≈ linha 446):

```python
# ── Loja seed (F1 multi-tenant) ───────────────────────────────────────────────
# Espelha as constantes de mod_contrato.py (evita import circular database<->mod_contrato).
# Os CPFs das testemunhas são placeholders — corrigidos no configurador de lojas (F2).
_SEED_LOJA_NOME   = "INSPIRIUM MOVEIS PLANEJADOS E DECORACAO LTDA"
_SEED_LOJA_CNPJ   = "19.152.134/0001-56"
_SEED_LOJA_CODIGO = "INS"
_SEED_LOJA_TEL    = "(12) 3341-8777"
_SEED_LOJA_EMAIL  = "sac@dalmobilesjc.com.br"
_SEED_TEST1_NOME  = "Jaime Perinazzo"
_SEED_TEST1_CPF   = "xxx.xxx.xxx-xx"
_SEED_TEST2_NOME  = "Felipe Guizalberte"
_SEED_TEST2_CPF   = "yyy.yyy.yyy-yy"
```

- [ ] **Step 4: Add the migration block to `_run_migracoes`**

Em `database.py`, dentro de `_run_migracoes`, logo após o bloco `perfis_v2_2026` e **antes** de `conn.commit()` (≈ linha 475):

```python
    # 2026-06-20: F1 multi-tenant — loja seed (das constantes do contrato) + backfill.
    if "tenancy_v1_2026" not in aplicadas and _tabela_existe(cur, "lojas"):
        cur.execute("SELECT id FROM lojas ORDER BY id LIMIT 1")
        row = cur.fetchone()
        if row is None:
            cur.execute(
                """INSERT INTO lojas
                   (nome, cnpj, codigo, telefone, email,
                    testemunha1_nome, testemunha1_cpf,
                    testemunha2_nome, testemunha2_cpf, ativo)
                   VALUES (?,?,?,?,?,?,?,?,?,1)""",
                (_SEED_LOJA_NOME, _SEED_LOJA_CNPJ, _SEED_LOJA_CODIGO,
                 _SEED_LOJA_TEL, _SEED_LOJA_EMAIL,
                 _SEED_TEST1_NOME, _SEED_TEST1_CPF,
                 _SEED_TEST2_NOME, _SEED_TEST2_CPF))
            loja_id = cur.lastrowid
        else:
            loja_id = row[0]

        for tbl in ("usuarios", "clientes", "projetos_meta", "orcamentos", "contratos"):
            if _tabela_existe(cur, tbl):
                cur.execute(f"UPDATE {tbl} SET loja_id=? WHERE loja_id IS NULL", (loja_id,))

        if _tabela_existe(cur, "parceiros"):
            cur.execute("UPDATE parceiros SET abrangencia='loja' WHERE abrangencia IS NULL")
            cur.execute("SELECT id, comissao_padrao_pct FROM parceiros")
            for pid, com in cur.fetchall():
                cur.execute("SELECT 1 FROM parceiro_lojas WHERE parceiro_id=? AND loja_id=?",
                            (pid, loja_id))
                if cur.fetchone() is None:
                    cur.execute(
                        """INSERT INTO parceiro_lojas
                           (parceiro_id, loja_id, comissao_padrao_pct, ativo)
                           VALUES (?,?,?,1)""",
                        (pid, loja_id, com or 0.0))

        cur.execute("INSERT INTO schema_migrations(id) VALUES('tenancy_v1_2026')")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_migracao.py -v`
Expected: PASS (2 testes).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_tenancy_migracao.py
git commit -m "feat(db): migracao tenancy_v1_2026 (loja seed + backfill idempotente)"
```

---

## Task 4: `seed.py` cria a loja seed e vincula os usuários

**Files:**
- Modify: `database.py` (helper `loja_seed_id`)
- Modify: `seed.py` (`criar_usuarios_seed` + uso na `seed()`)
- Test: `tests/test_tenancy_seed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_seed.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
import seed


def _mem_session():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def test_loja_seed_id():
    db = _mem_session()
    assert database.loja_seed_id(db) is None
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()
    assert database.loja_seed_id(db) == loja.id


def test_criar_usuarios_seed_vincula_loja():
    db = _mem_session()
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()

    n = seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)

    assert n == len(seed.USUARIOS)
    usuarios = db.query(database.Usuario).all()
    assert len(usuarios) == len(seed.USUARIOS)
    assert all(u.loja_id == loja.id for u in usuarios)


def test_criar_usuarios_seed_idempotente():
    db = _mem_session()
    loja = database.Loja(nome="X", codigo="INS")
    db.add(loja); db.commit()
    seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)
    n2 = seed.criar_usuarios_seed(db, seed.USUARIOS, loja.id)   # 2ª vez não recria
    assert n2 == 0
    assert db.query(database.Usuario).count() == len(seed.USUARIOS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_seed.py -v`
Expected: FAIL — `database.loja_seed_id` e `seed.criar_usuarios_seed` não existem.

- [ ] **Step 3: Add `loja_seed_id` helper**

Em `database.py`, logo após `def get_session():` (≈ linha 545):

```python
def loja_seed_id(db):
    """Id da loja seed (a 1ª loja por id), ou None se ainda não houver loja."""
    loja = db.query(Loja).order_by(Loja.id).first()
    return loja.id if loja else None
```

- [ ] **Step 4: Refactor `seed.py` to link users to the seed loja**

Substituir o conteúdo de `seed.py` por:

```python
"""
seed.py — Cria os usuários iniciais no banco de dados
Omie_V3 | Dalmóbile

Uso: python3 seed.py
"""

from database import init_db, get_session, Usuario, loja_seed_id

USUARIOS = [
    {"nome": "Pedro da Mota",        "login": "pdm2026", "senha": "teste123", "nivel": "diretor"},
    {"nome": "Luiz da Silva",        "login": "lds2026", "senha": "teste234", "nivel": "gerente_vendas"},
    {"nome": "Marcia dos Santos",    "login": "mds2026", "senha": "teste345", "nivel": "consultor"},
    {"nome": "Gabriela Adm/Fin",     "login": "gaf2026", "senha": "teste456", "nivel": "gerente_adm_fin"},
    {"nome": "Alex Logística",        "login": "alg2026", "senha": "teste567", "nivel": "assistente_logistico"},
    {"nome": "Carla Conferente",     "login": "ccf2026", "senha": "teste678", "nivel": "conferente"},
    {"nome": "Sergio Montagem",      "login": "smt2026", "senha": "teste789", "nivel": "supervisor_montagem"},
    {"nome": "Aline Administrativo", "login": "aad2026", "senha": "teste890", "nivel": "assistente_administrativo"},
    {"nome": "Paulo Projetista",     "login": "ppe2026", "senha": "teste901", "nivel": "projetista_executivo"},
    {"nome": "Marcos Medidor",       "login": "med2026", "senha": "teste012", "nivel": "medidor"},
]


def criar_usuarios_seed(db, usuarios, loja_id):
    """Cria os usuários que ainda não existem, vinculados à loja `loja_id`.
    Idempotente: pula logins já existentes. Retorna o nº de usuários criados."""
    criados = 0
    for dados in usuarios:
        if db.query(Usuario).filter_by(login=dados["login"]).first():
            print(f"  [ja existe] {dados['login']} ({dados['nivel']})")
            continue
        u = Usuario(nome=dados["nome"], login=dados["login"],
                    nivel=dados["nivel"], loja_id=loja_id)
        u.set_senha(dados["senha"])
        db.add(u)
        criados += 1
        print(f"  [criado]    {dados['login']} ({dados['nivel']}) - {dados['nome']}")
    db.commit()
    return criados


def seed():
    init_db()                         # cria schema + roda tenancy_v1_2026 (cria a loja seed)
    db = get_session()
    try:
        loja_id = loja_seed_id(db)    # a loja seed já existe pela migração
        criados = criar_usuarios_seed(db, USUARIOS, loja_id)
        print(f"\n  OK: {criados} usuario(s) criado(s); loja seed id={loja_id}.")
    finally:
        db.close()


if __name__ == "__main__":
    print("\nCriando usuarios iniciais...\n")
    seed()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_seed.py -v`
Expected: PASS (3 testes).

- [ ] **Step 6: Commit**

```bash
git add database.py seed.py tests/test_tenancy_seed.py
git commit -m "feat(seed): vincula usuarios-exemplo a loja seed"
```

---

## Task 5: Verificação de suíte completa + regressão (sem mudança de comportamento)

**Files:** nenhum (verificação).

- [ ] **Step 1: Rodar a suíte inteira**

Run: `python -m pytest -q`
Expected: PASS em tudo (157 anteriores + os novos de Tasks 1-4). Nenhum teste pré-existente quebrado — F1 não muda comportamento.

- [ ] **Step 2: Smoke do schema num DB de descarte**

Run:
```bash
python -c "import database; database.init_db(); db=database.get_session(); print('loja_seed_id=', database.loja_seed_id(db)); db.close()"
```
Expected: imprime um `loja_seed_id=` com um inteiro (a loja seed criada pela migração no DB real). Se o DB real já tinha dados, confirmar que não houve erro.

> Lembrete (memória do projeto): após mudar `.py`, **reiniciar o servidor** antes de testar na UI; `index.html` é hot do disco.

- [ ] **Step 3: Regressão manual/Playwright (app idêntico)**

Subir o servidor e confirmar, em aba anônima (evitar cache do SPA):
- login (`pdm2026`) ok;
- lista de projetos carrega igual;
- abrir um projeto, gerar/abrir contrato — conteúdo **idêntico** ao de antes (ainda usa as constantes do `mod_contrato.py`);
- lista de parceiros carrega igual;
- 0 erros de console/página.

Expected: nenhuma diferença visível em relação ao comportamento atual.

- [ ] **Step 4: Atualizar o DEV_LOG**

Adicionar uma entrada de sessão no `DEV_LOG.md` resumindo a F1 (fundação multi-tenant: tabelas `redes`/`lojas`/`parceiro_lojas`, colunas de tenant, migração `tenancy_v1_2026`, loja seed, `seed.py` vinculado) e registrando que F2/F3/F4 seguem o programa. Commit:

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — F1 fundacao multi-tenant"
```

---

## Self-review (cobertura do spec)

- Tabelas `redes`/`lojas`/`parceiro_lojas` → Task 1. ✓
- Colunas de tenant nas 5 entidades de topo + `rede_id`/`abrangencia` em parceiros → Task 1 (models) + Task 2 (DBs existentes). ✓
- Tabelas-filhas **sem** `loja_id` → respeitado (nenhuma task as toca). ✓
- Migração `tenancy_v1_2026` (loja seed das constantes + backfill + idempotência) → Task 3. ✓
- `seed.py` cria/vincula loja seed → Task 4. ✓
- Não-objetivos (sem isolamento, sem UI, `mod_contrato` intacto) → garantido: nenhuma task toca `main.py`/`mod_contrato.py`/`static`; Task 5 confirma regressão zero. ✓
- Verificação (pytest + smoke + Playwright) → Task 5. ✓

Consistência de nomes verificada: `loja_seed_id`, `criar_usuarios_seed`, `tenancy_v1_2026`, `_SEED_LOJA_*`, `parceiro_lojas`/`ParceiroLoja` usados de forma idêntica entre tasks.
