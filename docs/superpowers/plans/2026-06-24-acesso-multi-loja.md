# Acesso multi-loja por usuário (loja ativa) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que um usuário acesse várias lojas, operando numa "loja ativa" por vez (escolhida por requisição via header `X-Loja-Ativa`), com o admin de rede definindo quais lojas cada usuário acessa.

**Architecture:** Tabela M:N `usuario_lojas` (espelha `parceiro_lojas`); `usuarios.loja_id` permanece como loja default. A loja ativa viaja no header `X-Loja-Ativa`, lido um único ponto (`_ator_dict`, via contexto de requisição — servidor é single-thread), resolvida contra a membership por `mod_tenancy.resolver_loja_ativa`, e exposta pelo funil único `escopo_operacional(ator)`. Frontend injeta o header por interceptação de `window.fetch` e tem um seletor de loja.

**Tech Stack:** Python 3 (`python3` no WSL), SQLAlchemy/SQLite, `http.server` single-thread (`main.Handler`), SPA vanilla em arquivo único, `pytest` (frontend = verificação manual).

## Global Constraints

- Rodar com `python3`/`python3 -m pytest` (WSL), nunca `python`.
- **Loja ativa por requisição:** header `X-Loja-Ativa` lido só em `_ator_dict`; `escopo_operacional(ator)` é o funil — os ~62 call sites de `_ator_dict`/~51 de `escopo_operacional` NÃO mudam de assinatura.
- **`usuarios.loja_id` NÃO é removido** — permanece como loja primária/default. `usuario_lojas` é o conjunto de lojas acessíveis.
- **Resolução da loja ativa** (`resolver_loja_ativa(memberships, header, default)`): header presente e ∈ (memberships ∪ {default}) → header; header presente e inválido → `None` (→ 403); sem header → default se acessível, senão membership única, senão `None`.
- **Segurança:** a loja ativa só pode ser loja acessível; header inválido → `escopo_operacional` retorna `(None, motivo)` → endpoint operacional responde 403. super_admin/admin_rede (sem loja/sem membership) seguem 403 nos endpoints operacionais.
- **Compat:** usuário de loja única (só `loja_id`, sem/1 linha em `usuario_lojas`) funciona idêntico a hoje (sem header → default).
- Seguir os padrões existentes (`ParceiroLoja`, migrações idempotentes em `database.py`, rotas finas em `main.py`, funções puras em `mod_tenancy`).

---

### Task 1: Modelo `UsuarioLoja` + migração/backfill + helper de membership

**Files:**
- Modify: `database.py` (modelo novo após `ParceiroLoja` ~linha 229; backfill no bloco de migração do `init_db`; helper `membership_loja_ids`)
- Test: `tests/test_multi_loja.py`

**Interfaces:**
- Produces: classe `UsuarioLoja` (tabela `usuario_lojas`: `id`, `usuario_id` FK usuarios, `loja_id` FK lojas, `UNIQUE(usuario_id, loja_id)`); função `membership_loja_ids(db, usuario_id) -> list[int]`; função de backfill `_backfill_usuario_lojas(cur)` executada no `init_db`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_multi_loja.py`:

```python
import pytest
import database


def test_membership_vazio_para_usuario_sem_vinculo(app_db, seed):
    db = app_db.get_session()
    try:
        # cria um usuário sem nenhuma linha em usuario_lojas
        u = app_db.Usuario(nome="Sem Loja", login="semloja", nivel="consultor", ativo=1)
        u.set_senha("x"); db.add(u); db.commit()
        assert database.membership_loja_ids(db, u.id) == []
    finally:
        db.close()


def test_membership_lista_lojas(app_db, seed):
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="Multi", login="multi1", nivel="diretor",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("x"); db.add(u); db.flush()
        db.add_all([
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja1_id"]),
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja2_id"]),
        ])
        db.commit()
        assert set(database.membership_loja_ids(db, u.id)) == {seed["loja1_id"], seed["loja2_id"]}
    finally:
        db.close()


def test_backfill_cria_uma_membership_por_loja_id(app_db, seed):
    import sqlite3
    # usuário com loja_id e SEM membership (simula estado pré-migração)
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="Legado", login="legado1", nivel="consultor",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("x"); db.add(u); db.commit()
        uid = u.id
    finally:
        db.close()
    # roda o backfill direto sobre a conexão sqlite
    con = sqlite3.connect(database.DB_PATH)
    try:
        database._backfill_usuario_lojas(con.cursor()); con.commit()
    finally:
        con.close()
    db = app_db.get_session()
    try:
        assert database.membership_loja_ids(db, uid) == [seed["loja1_id"]]
        # idempotente: rodar de novo não duplica
    finally:
        db.close()
    con = sqlite3.connect(database.DB_PATH)
    try:
        database._backfill_usuario_lojas(con.cursor()); con.commit()
    finally:
        con.close()
    db = app_db.get_session()
    try:
        assert database.membership_loja_ids(db, uid) == [seed["loja1_id"]]
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_loja.py -v`
Expected: FAIL (`AttributeError: module 'database' has no attribute 'membership_loja_ids'` / sem `UsuarioLoja`).

- [ ] **Step 3: Write minimal implementation**

Em `database.py`, após a classe `ParceiroLoja` (~linha 229):

```python
class UsuarioLoja(Base):
    """Vínculo M:N usuário × loja (lojas acessíveis). loja_id em usuarios = loja primária/default."""
    __tablename__ = "usuario_lojas"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    loja_id    = Column(Integer, ForeignKey("lojas.id"),    nullable=False)

    __table_args__ = (UniqueConstraint("usuario_id", "loja_id", name="uq_usuario_loja"),)
```

Adicionar o helper (junto dos outros helpers de módulo, ex. perto de `upsert_projeto_status`):

```python
def membership_loja_ids(db, usuario_id):
    """IDs das lojas acessíveis do usuário (via usuario_lojas)."""
    rows = (db.query(UsuarioLoja.loja_id)
              .filter(UsuarioLoja.usuario_id == usuario_id).all())
    return [r[0] for r in rows]


def _backfill_usuario_lojas(cur):
    """Idempotente: cria 1 membership para cada usuário com loja_id e sem vínculo ainda."""
    cur.execute("""
        INSERT INTO usuario_lojas (usuario_id, loja_id)
        SELECT u.id, u.loja_id FROM usuarios u
        WHERE u.loja_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM usuario_lojas ul
                          WHERE ul.usuario_id = u.id AND ul.loja_id = u.loja_id)
    """)
```

No `init_db()`, no bloco de migrações (após `Base.metadata.create_all(...)` que já cria a tabela nova), chamar o backfill via cursor sqlite. Localizar onde outras migrações usam `cur`/`conn` e adicionar:

```python
    # 2026-06-24: backfill de usuario_lojas a partir de usuarios.loja_id (multi-loja)
    _backfill_usuario_lojas(cur)
```

(Se o bloco de migração usa um nome diferente para o cursor, use o mesmo; o backfill só precisa de um cursor sqlite com `execute`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_loja.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Run full suite (regressão do schema/migração)**

Run: `python3 -m pytest -q`
Expected: tudo verde (migração idempotente, sem quebrar bootstrap).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_multi_loja.py
git commit -m "feat(multi-loja): tabela usuario_lojas + backfill + membership_loja_ids"
```

---

### Task 2: `resolver_loja_ativa` (pura, mod_tenancy)

**Files:**
- Modify: `mod_tenancy.py` (nova função pura)
- Test: `tests/test_multi_loja.py`

**Interfaces:**
- Produces: `resolver_loja_ativa(memberships, header_loja_id, default_loja_id) -> int | None`. `memberships` = lista de ints; `header_loja_id`/`default_loja_id` = int ou None.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_multi_loja.py`:

```python
import mod_tenancy


def test_resolver_header_valido():
    assert mod_tenancy.resolver_loja_ativa([1, 2], 2, 1) == 2

def test_resolver_header_default_incluso_mesmo_sem_membership():
    # default sempre acessível mesmo se não estiver em memberships
    assert mod_tenancy.resolver_loja_ativa([], None, 5) == 5

def test_resolver_header_invalido_retorna_none():
    assert mod_tenancy.resolver_loja_ativa([1, 2], 9, 1) is None

def test_resolver_sem_header_usa_default():
    assert mod_tenancy.resolver_loja_ativa([1, 2], None, 1) == 1

def test_resolver_sem_header_sem_default_membership_unica():
    assert mod_tenancy.resolver_loja_ativa([7], None, None) == 7

def test_resolver_nada_resolvivel():
    assert mod_tenancy.resolver_loja_ativa([], None, None) is None
    assert mod_tenancy.resolver_loja_ativa([1, 2], None, None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_loja.py -k resolver -v`
Expected: FAIL (`AttributeError: ... has no attribute 'resolver_loja_ativa'`).

- [ ] **Step 3: Write minimal implementation**

Em `mod_tenancy.py` (após `escopo_operacional`):

```python
def resolver_loja_ativa(memberships, header_loja_id, default_loja_id):
    """Decide a loja ativa de uma requisição operacional.

    acessíveis = memberships ∪ {default}. header presente → só vale se acessível
    (senão None → 403). Sem header → default se acessível; senão membership única; senão None.
    """
    acessiveis = set(memberships or [])
    if default_loja_id is not None:
        acessiveis.add(default_loja_id)
    if header_loja_id is not None:
        return header_loja_id if header_loja_id in acessiveis else None
    if default_loja_id is not None and default_loja_id in acessiveis:
        return default_loja_id
    if len(acessiveis) == 1:
        return next(iter(acessiveis))
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_loja.py -k resolver -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_tenancy.py tests/test_multi_loja.py
git commit -m "feat(multi-loja): resolver_loja_ativa (pura)"
```

---

### Task 3: Plumbing do header → `_ator_dict` → `escopo_operacional`

**Files:**
- Modify: `main.py` (contexto de requisição do header nos 3 dispatch; `_ator_dict`; nada nos call sites)
- Modify: `mod_tenancy.py` (`escopo_operacional` lê `active_loja_id`)
- Test: `tests/test_multi_loja_e2e.py`

**Interfaces:**
- Consumes: `database.membership_loja_ids`, `mod_tenancy.resolver_loja_ativa`.
- Produces: `_ator_dict` agora retorna também `active_loja_id` e `lojas_ids`; `escopo_operacional(ator)` retorna `(ator["active_loja_id"], None)` ou `(None, motivo)`. Header lido de `X-Loja-Ativa`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_multi_loja_e2e.py` (o `HttpClient` do conftest não manda headers extras, então definimos um helper local `_get_h`; **não modifique conftest.py**):

```python
import json as _json, urllib.request, urllib.error
import pytest


def _get_h(client, path, headers=None):
    """GET reaproveitando o cookie do HttpClient, com headers extras (ex.: X-Loja-Ativa)."""
    req = urllib.request.Request(client.base + path, method="GET")
    if client.cookie:
        req.add_header("Cookie", client.cookie)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    try:
        out = _json.loads(raw) if raw else None
    except Exception:
        out = raw
    return status, out


@pytest.fixture(scope="module")
def dir_l1_multiloja(app_db, seed):
    """Torna dir_l1 (default loja1) membro também da loja2."""
    db = app_db.get_session()
    try:
        u = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
        db.add_all([
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja1_id"]),
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja2_id"]),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def _clientes_nomes(body):
    return {c["nome"] for c in (body.get("clientes") or [])}


def test_sem_header_usa_loja_default(http_client_factory, dir_l1_multiloja):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = _get_h(c, "/api/clientes?q=")
    assert st == 200
    assert "Cliente L1" in _clientes_nomes(body)
    assert "Cliente L2" not in _clientes_nomes(body)


def test_header_loja2_muda_contexto(http_client_factory, dir_l1_multiloja, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = _get_h(c, "/api/clientes?q=", {"X-Loja-Ativa": str(seed["loja2_id"])})
    assert st == 200
    assert "Cliente L2" in _clientes_nomes(body)
    assert "Cliente L1" not in _clientes_nomes(body)


def test_header_loja_nao_membro_da_403(http_client_factory, seed):
    # dir_l2 tem loja_id=loja2 e sem membership; default (loja2) é sempre acessível.
    # Header loja1 (não-membro) não está em {loja2} -> resolver None -> 403.
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = _get_h(c, "/api/clientes?q=", {"X-Loja-Ativa": str(seed["loja1_id"])})
    assert st == 403
```

> Confirme que `GET /api/clientes?q=` (q vazio) responde `{ok, clientes:[{nome,...}]}` filtrado pela loja ativa (handler ~`main.py:417`). Se esse endpoint exigir `q` não-vazio, use outro endpoint de listagem operacional escopado por loja (ex.: projetos), mantendo a mesma asserção de contexto.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -v`
Expected: FAIL — sem o plumbing, o header é ignorado (`test_header_loja2_muda_contexto` retorna Cliente L1; `test_header_loja_nao_membro_da_403` retorna 200).

- [ ] **Step 3: Write minimal implementation**

3a. Em `main.py`, no nível de módulo (perto dos outros globais do Handler), adicionar o contexto de requisição (servidor é single-thread → seguro):

```python
_REQ_LOJA_ATIVA = None   # header X-Loja-Ativa da requisição atual (HTTPServer single-thread)

def _ler_loja_ativa_header(handler):
    raw = (handler.headers.get("X-Loja-Ativa") or "").strip()
    return int(raw) if raw.isdigit() else None
```

3b. No início de `do_GET`, `do_POST` e `do_PATCH` (logo após `path = urlparse(self.path).path`), setar o contexto:

```python
        global _REQ_LOJA_ATIVA
        _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)
```

3c. Alterar `_ator_dict` (`main.py:4469`) para resolver a loja ativa:

```python
def _ator_dict(db, usuario_sessao, header_loja_id=None):
    """Re-consulta o usuário logado e resolve a loja ativa (multi-loja)."""
    if header_loja_id is None:
        header_loja_id = _REQ_LOJA_ATIVA
    u = db.get(Usuario, usuario_sessao.get("id"))
    if not u:
        return {"nivel": usuario_sessao.get("nivel"), "loja_id": None,
                "rede_id": None, "active_loja_id": None, "lojas_ids": []}
    membership = membership_loja_ids(db, u.id)
    active = mod_tenancy.resolver_loja_ativa(membership, header_loja_id, u.loja_id)
    return {"nivel": u.nivel, "loja_id": u.loja_id, "rede_id": u.rede_id,
            "active_loja_id": active, "lojas_ids": membership}
```

(Garanta que `membership_loja_ids` esteja importado de `database` no topo de `main.py` — adicionar `membership_loja_ids` à lista de imports `from database import (...)`.)

3d. Em `mod_tenancy.py`, alterar `escopo_operacional`:

```python
def escopo_operacional(ator):
    """Escopo de uma operação NA LOJA: usa a loja ATIVA resolvida.

    (loja_id, None) quando há loja ativa; (None, motivo) quando não há
    (perfil administrativo, sem loja, ou header de loja inválido).
    """
    loja_id = ator.get("active_loja_id")
    if loja_id is None:
        return (None, "Sem acesso operacional (perfil administrativo, sem loja, ou loja inválida).")
    return (loja_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Run full suite (regressão crítica — 51 call sites operacionais)**

Run: `python3 -m pytest -q`
Expected: tudo verde. Usuários de loja única (sem header) resolvem para o default → comportamento idêntico.

- [ ] **Step 6: Commit**

```bash
git add main.py mod_tenancy.py tests/test_multi_loja_e2e.py
git commit -m "feat(multi-loja): loja ativa por header em _ator_dict + escopo_operacional"
```

---

### Task 4: Payload `/api/auth/me` expõe `lojas` + `loja_ativa_id`

**Files:**
- Modify: `auth_routes.py` (handler `/api/auth/me`)
- Test: `tests/test_multi_loja_e2e.py`

**Interfaces:**
- Consumes: `database.membership_loja_ids`, `database.get_session`, `database.Loja`.
- Produces: resposta de `/api/auth/me` ganha `usuario.lojas = [{id, nome, codigo}, ...]` (acessíveis = membership ∪ {default}) e `usuario.loja_ativa_id` (= `loja_id` default).

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_multi_loja_e2e.py`:

```python
def test_auth_me_expoe_lojas_acessiveis(http_client_factory, dir_l1_multiloja, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.get("/api/auth/me")
    assert st == 200
    u = body["usuario"]
    ids = {l["id"] for l in u["lojas"]}
    assert ids == {seed["loja1_id"], seed["loja2_id"]}
    assert u["loja_ativa_id"] == seed["loja1_id"]
    assert all("nome" in l and "codigo" in l for l in u["lojas"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -k auth_me -v`
Expected: FAIL (`KeyError: 'lojas'`).

- [ ] **Step 3: Write minimal implementation**

Em `auth_routes.py`, no topo, garantir os imports: `from database import get_session, Loja, membership_loja_ids`.

Alterar o ramo `/api/auth/me` (linha 65):

```python
    if path == "/api/auth/me":
        usuario = get_usuario_sessao(handler)
        if not usuario:
            _send_json(handler, {"ok": False, "erro": "Não autenticado."}, 401)
        else:
            db = get_session()
            try:
                ids = membership_loja_ids(db, usuario["id"])
                if usuario.get("loja_id") and usuario["loja_id"] not in ids:
                    ids = ids + [usuario["loja_id"]]
                lojas = [{"id": l.id, "nome": l.nome, "codigo": l.codigo}
                         for l in db.query(Loja).filter(Loja.id.in_(ids)).all()] if ids else []
                usuario["lojas"] = lojas
                usuario["loja_ativa_id"] = usuario.get("loja_id")
            finally:
                db.close()
            _send_json(handler, {"ok": True, "usuario": usuario})
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -k auth_me -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add auth_routes.py tests/test_multi_loja_e2e.py
git commit -m "feat(multi-loja): /api/auth/me expoe lojas acessiveis + loja_ativa_id"
```

---

### Task 5: Atribuição de lojas — `atribuir_tenant_usuario` + rotas de usuário aceitam `loja_ids`

**Files:**
- Modify: `mod_tenancy.py` (`atribuir_tenant_usuario` aceita `loja_ids`)
- Modify: `main.py` (POST `/api/admin/usuarios` ~2723 e PATCH `/api/admin/usuarios/<id>` ~3879: gravar `usuario_lojas`)
- Test: `tests/test_multi_loja_e2e.py`

**Interfaces:**
- Consumes: `database.UsuarioLoja`, `mod_tenancy.pode_ver_loja`.
- Produces: criação/edição de usuário grava as memberships; `usuarios.loja_id = loja_ids[0]` (primária). admin_rede só pode atribuir lojas da própria rede.

- [ ] **Step 1: Write the failing test**

Acrescentar a `tests/test_multi_loja_e2e.py`:

```python
def test_admin_rede_cria_usuario_multiloja_na_propria_rede(http_client_factory, seed):
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Novo Diretor", "login": "novodir", "senha": "senha123",
        "nivel": "diretor", "loja_ids": [seed["loja1_id"], seed["loja2_id"]],
    })
    assert st == 200 and body["ok"] is True
    # confere que as memberships foram gravadas via /api/auth/me do novo usuário
    c2 = http_client_factory(); c2.login("novodir", "senha123")
    _, me = c2.get("/api/auth/me")
    ids = {l["id"] for l in me["usuario"]["lojas"]}
    assert ids == {seed["loja1_id"], seed["loja2_id"]}


def test_admin_rede_barrado_em_loja_de_outra_rede(http_client_factory, app_db, seed):
    # cria uma loja em outra rede
    db = app_db.get_session()
    try:
        rb = app_db.Rede(nome="Rede C"); db.add(rb); db.flush()
        lb = app_db.Loja(nome="Loja C", rede_id=rb.id, codigo="LJC"); db.add(lb); db.commit()
        loja_c = lb.id
    finally:
        db.close()
    c = http_client_factory(); c.login("adm_rede", "senha123")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Invasor", "login": "invasor", "senha": "senha123",
        "nivel": "diretor", "loja_ids": [seed["loja1_id"], loja_c],
    })
    assert body["ok"] is False  # loja_c fora do escopo da rede do adm_rede
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -k "multiloja_na_propria or barrado" -v`
Expected: FAIL (rota ainda usa loja única; `loja_ids` ignorado; novo usuário sem memberships).

- [ ] **Step 3: Write minimal implementation**

3a. Em `mod_tenancy.py`, adicionar uma função pura que normaliza/valida a lista a partir de `atribuir_tenant_usuario`. Estender `atribuir_tenant_usuario` para também devolver `loja_ids`:

```python
def lojas_do_novo_usuario(ator, dados):
    """Lista de loja_ids para o novo usuário operacional (>=1) ou [] para papéis admin.
    Retorna (loja_ids, erros). A checagem de que cada loja ∈ escopo do ator é feita na rota."""
    nivel_novo = (dados.get("nivel") or "").strip()
    if nivel_novo in ("super_admin", "admin_rede"):
        return ([], [])
    ids = dados.get("loja_ids")
    if ids is None and dados.get("loja_id") is not None:
        ids = [dados.get("loja_id")]          # compat: aceita loja_id único
    ids = [int(x) for x in (ids or [])]
    if not ids:
        return ([], ["Selecione ao menos uma loja."])
    # se o ator é usuário de loja (diretor), só pode a própria loja
    if (not _eh_super_admin(ator) and not _eh_admin_rede(ator)
            and ator.get("loja_id") is not None):
        ids = [ator.get("loja_id")]
    return (ids, [])
```

3b. No POST `/api/admin/usuarios` (`main.py:2723`), após a validação de tenant existente, resolver e validar as lojas, criar o usuário e gravar memberships. Substituir o trecho que hoje calcula/valida `loja_id` único por:

```python
                    loja_id, rede_id, erros_tenant = mod_tenancy.atribuir_tenant_usuario(ator, req)
                    loja_ids, erros_lojas = mod_tenancy.lojas_do_novo_usuario(ator, req)
                    erros = erros + erros_tenant + erros_lojas
                    # valida cada loja no escopo do ator (admin_rede/diretor)
                    if not erros and loja_ids and not mod_tenancy._eh_super_admin(ator):
                        for lid in loja_ids:
                            loja = db.get(Loja, lid)
                            if not loja or not mod_tenancy.pode_ver_loja(
                                    ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                erros = erros + ["Loja fora do seu escopo."]; break
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
```

E, ao montar o `Usuario`, usar `loja_id = loja_ids[0] if loja_ids else None` (a primária) em vez do `loja_id` antigo; após `db.add(u); db.flush()`, gravar as memberships:

```python
                    u.loja_id = loja_ids[0] if loja_ids else None
                    db.add(u); db.flush()
                    for lid in loja_ids:
                        db.add(UsuarioLoja(usuario_id=u.id, loja_id=lid))
                    db.commit()
```

(Garanta `UsuarioLoja` importado de `database` no topo de `main.py`. Ajuste o código existente que setava `loja_id=loja_id` no construtor de `Usuario` para usar a primária.)

3c. No PATCH `/api/admin/usuarios/<id>` (`main.py:3879`), quando `loja_ids` vier no corpo, refazer as memberships (apaga as atuais e regrava as válidas no escopo) e atualizar `usuarios.loja_id` para `loja_ids[0]`. Adicionar, dentro do bloco que aplica as alterações do usuário:

```python
                    if "loja_ids" in req:
                        novas, erros_l = mod_tenancy.lojas_do_novo_usuario(ator, req)
                        if erros_l:
                            self.send_json({"ok": False, "erro": " ".join(erros_l)}); return
                        if not mod_tenancy._eh_super_admin(ator):
                            for lid in novas:
                                loja = db.get(Loja, lid)
                                if not loja or not mod_tenancy.pode_ver_loja(
                                        ator, {"id": loja.id, "rede_id": loja.rede_id}):
                                    self.send_json({"ok": False, "erro": "Loja fora do seu escopo."}); return
                        db.query(UsuarioLoja).filter(UsuarioLoja.usuario_id == alvo.id).delete()
                        for lid in novas:
                            db.add(UsuarioLoja(usuario_id=alvo.id, loja_id=lid))
                        alvo.loja_id = novas[0] if novas else alvo.loja_id
```

(`alvo` = o objeto `Usuario` sendo editado no handler PATCH; use o nome de variável real do handler.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_multi_loja_e2e.py -k "multiloja_na_propria or barrado" -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde (criação de usuário de loja única via `loja_id` continua funcionando pelo ramo de compat em `lojas_do_novo_usuario`).

- [ ] **Step 6: Commit**

```bash
git add mod_tenancy.py main.py tests/test_multi_loja_e2e.py
git commit -m "feat(multi-loja): atribuicao de N lojas na criacao/edicao de usuario"
```

---

### Task 6: Criação de contrato usa a loja ativa

**Files:**
- Modify: `main.py` (criação de contrato ~3283: trocar `ator.get("loja_id")` pela loja ativa)
- Test: regressão (suite existente de contrato)

**Interfaces:**
- Consumes: `mod_tenancy.escopo_operacional(ator)`.
- Produces: o contrato é carimbado com a loja ATIVA (código + `loja_snapshot_json`).

- [ ] **Step 1: Localizar e alterar**

No handler de geração de contrato (`main.py`, ~linha 3283), trocar:

```python
loja_dict = _loja_dict_para_contrato(db, ator.get("loja_id"))
```

por (usa a loja ativa, que é o escopo operacional; já há um `ator` no handler):

```python
_loja_ativa, _err_loja = mod_tenancy.escopo_operacional(ator)
if _err_loja:
    self.send_json({"ok": False, "erro": _err_loja}, code=403); return
loja_dict = _loja_dict_para_contrato(db, _loja_ativa)
```

(Se o handler já chama `escopo_operacional` antes para validar o projeto, reutilize aquela variável em vez de chamar de novo.)

- [ ] **Step 2: Rodar a suíte de contrato (regressão)**

Run: `python3 -m pytest tests/test_contrato_loja.py tests/test_contrato.py tests/test_contrato_assinado.py -v`
Expected: verde — usuários de loja única: loja ativa == default, comportamento idêntico.

- [ ] **Step 3: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(multi-loja): contrato usa a loja ativa (escopo_operacional)"
```

> Verificação multi-loja do contrato (loja ativa != default) fica para a validação manual no browser (Task 8), pois montar um contrato completo via e2e é custoso.

---

### Task 7: Frontend — interceptação de `window.fetch` + seletor de loja ativa

**Files:**
- Modify: `static/index.html` (instalar interceptor no boot; ler `lojas`/`loja_ativa_id`; seletor)

**Interfaces:**
- Consumes: payload de `/api/auth/me` (`lojas`, `loja_ativa_id`); `_usuarioAtual`.
- Produces: global `_lojaAtiva`; toda chamada `/api/...` carrega `X-Loja-Ativa`; seletor visível quando `lojas.length > 1`.

- [ ] **Step 1: Instalar o interceptor de fetch (uma vez, no boot)**

Adicionar, cedo no script (antes de qualquer chamada a `/api`), e definir o global:

```javascript
let _lojaAtiva = null;   // loja ativa atual (multi-loja); null = usa default do backend
(function _instalarFetchLojaAtiva(){
  const _origFetch = window.fetch.bind(window);
  window.fetch = function(input, init){
    init = init || {};
    try {
      const url = (typeof input === 'string') ? input : (input && input.url) || '';
      if (_lojaAtiva && url.indexOf('/api/') !== -1 && url.indexOf('//') === -1) {
        const h = new Headers(init.headers || (typeof input!=='string' && input.headers) || {});
        h.set('X-Loja-Ativa', String(_lojaAtiva));
        init.headers = h;
      }
    } catch(e){ /* não bloquear a requisição por erro do interceptor */ }
    return _origFetch(input, init);
  };
})();
```

- [ ] **Step 2: Inicializar `_lojaAtiva` a partir do usuário e do localStorage**

Em `carregarUsuarioAutenticado`, após `_usuarioAtual = d.usuario;`, definir a loja ativa inicial:

```javascript
    const _lojas = _usuarioAtual.lojas || [];
    const _salva = parseInt(localStorage.getItem('loja_ativa') || '', 10);
    const _idsValidos = _lojas.map(l => l.id);
    _lojaAtiva = (_salva && _idsValidos.indexOf(_salva) !== -1)
      ? _salva : (_usuarioAtual.loja_ativa_id || null);
```

- [ ] **Step 3: Renderizar o seletor (só quando lojas.length > 1)**

Adicionar uma função e chamá-la em `_atualizarUIUsuario`:

```javascript
function _renderSeletorLoja(){
  const lojas = (_usuarioAtual && _usuarioAtual.lojas) || [];
  let host = document.getElementById('seletor-loja-wrap');
  if (!host) return;                       // host fixo no HTML (ver Step 4)
  if (lojas.length <= 1){ host.style.display = 'none'; return; }
  host.style.display = '';
  host.innerHTML = '<label class="field-label" style="margin:0 6px 0 0">Loja</label>' +
    '<select id="seletor-loja" style="background:var(--surface);border:1px solid var(--border);'
    + 'border-radius:8px;padding:6px 10px;color:var(--text);font-size:12px"></select>';
  const sel = document.getElementById('seletor-loja');
  sel.innerHTML = lojas.map(l => `<option value="${l.id}">${esc(l.nome)}</option>`).join('');
  if (_lojaAtiva) sel.value = String(_lojaAtiva);
  sel.onchange = function(){
    _lojaAtiva = parseInt(sel.value, 10);
    localStorage.setItem('loja_ativa', String(_lojaAtiva));
    location.reload();                      // recarrega as views no contexto da nova loja
  };
}
```

E chamar `_renderSeletorLoja();` ao final de `_atualizarUIUsuario`.

- [ ] **Step 4: Adicionar o host do seletor no HTML do topo/sidebar**

No cabeçalho/sidebar (perto da identificação do usuário, ex. próximo a `sb-user-nome`), adicionar:

```html
<div id="seletor-loja-wrap" style="display:none;align-items:center;margin:8px 0"></div>
```

- [ ] **Step 5: Verificação manual**

```bash
python3 main.py
```
- Criar (como super_admin ou admin_rede) um usuário diretor com 2 lojas; logar com ele: o **seletor de loja** aparece. Trocar a loja → a página recarrega e Projetos/Clientes passam a mostrar a outra loja.
- Logar com usuário de loja única: **sem seletor**, tudo como antes.
- Gerar um contrato com a loja ativa “secundária” selecionada → o número/snapshot usam a loja ativa.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(multi-loja): interceptor de fetch + seletor de loja ativa"
```

---

### Task 8: Frontend — seleção multi-loja no modal de usuário

**Files:**
- Modify: `static/index.html` (modal de usuário: multi-seleção de lojas; `salvarModalUsuario` envia `loja_ids`)

**Interfaces:**
- Consumes: lista de lojas do escopo (já buscada para o nível Rede/Loja via `/api/admin/lojas?rede_id=...`).
- Produces: o POST/PATCH de usuário envia `loja_ids: [...]`.

- [ ] **Step 1: Adicionar o seletor de lojas ao modal (escopo operacional)**

No `abrirModalUsuario`, quando `ctx.escopo === 'loja'` ou `'rede'` (criação de papel operacional dentro de uma rede), buscar as lojas do escopo e renderizar checkboxes num container `#musr-lojas`. Carregar via `GET /api/admin/lojas?rede_id=<rede>` (ou a loja única do contexto), e pré-marcar `ctx.loja_ids` na edição:

```javascript
async function _carregarLojasModalUsuario(ctx){
  const box = document.getElementById('musr-lojas-wrap');
  if (!box) return;
  let lojas = [];
  if (ctx.rede_id) {
    const d = await fetch('/api/admin/lojas?rede_id=' + ctx.rede_id, {credentials:'same-origin'})
      .then(r=>r.json()).catch(()=>({lojas:[]}));
    lojas = d.lojas || [];
  } else if (ctx.loja_id) {
    lojas = [{ id: ctx.loja_id, nome: '(loja atual)' }];
  }
  const sel = new Set(ctx.loja_ids || (ctx.loja_id ? [ctx.loja_id] : []));
  box.style.display = lojas.length ? '' : 'none';
  document.getElementById('musr-lojas').innerHTML = lojas.map(l =>
    `<label style="display:block;font-size:12px"><input type="checkbox" class="musr-loja-cb" `
    + `value="${l.id}" ${sel.has(l.id)?'checked':''}> ${esc(l.nome)}</label>`).join('');
}
```

Chamar `_carregarLojasModalUsuario(ctx)` dentro de `abrirModalUsuario` (após resolver o escopo). Adicionar no HTML do modal um bloco:

```html
<div id="musr-lojas-wrap" style="display:none;grid-column:1/-1">
  <label class="field-label">Lojas que pode acessar</label>
  <div id="musr-lojas" style="max-height:140px;overflow:auto;border:1px solid var(--border);border-radius:8px;padding:8px"></div>
</div>
```

- [ ] **Step 2: Enviar `loja_ids` no save**

Em `salvarModalUsuario`, montar `loja_ids` a partir dos checkboxes marcados e incluir no payload (em vez de/somando ao `loja_id` antigo):

```javascript
  const lojaIds = Array.from(document.querySelectorAll('.musr-loja-cb:checked'))
    .map(cb => parseInt(cb.value, 10));
  if (lojaIds.length) payload.loja_ids = lojaIds;
```

(Manter o envio para papéis admin sem `loja_ids`.)

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py
```
- Como admin_rede: “+ Novo administrador”/“+ Novo usuário” na loja → o modal lista as **lojas da rede** com checkboxes; marcar 2; salvar; reabrir em edição → as 2 vêm marcadas.
- Tentar (via UI de outra rede) não deve oferecer lojas fora do escopo (a lista vem de `/api/admin/lojas?rede_id=<sua rede>`); o backend (Task 5) recusa lojas fora do escopo de qualquer forma.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(multi-loja): selecao de N lojas no modal de usuario"
```

---

## Notas de implementação

- **Ordem/dependências:** Tasks 1→2→3 são a base (modelo + resolução + plumbing). Task 4 (payload) e Task 5 (atribuição) dependem da 1. Task 6 (contrato) depende da 3. Tasks 7 e 8 (frontend) dependem de 4 e 5 mergeadas.
- **Branch:** implementar a partir do `main` já com o slice da árvore (#1+#2) mergeado, pois ambos tocam `static/index.html`/tenancy.
- **Fora deste plano (slices futuros):** multi-papel (login com papéis distintos); visão agregada cross-loja; modais "Nova rede"/"Nova loja" (substituir `prompt()`).
