# F4 — Suíte de regressão E2E de isolamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma suíte de testes E2E que prova, por HTTP, que o isolamento multi-tenant da F4 funciona — e que trava os IDORs já corrigidos contra regressão — sem depender do ambiente real do usuário.

**Architecture:** Os testes sobem o servidor HTTP real (`main.Handler`) numa thread, apontado para um SQLite temporário (engine rebindada em `database`), e dirigem por HTTP com login real (cookie `omie_session`). O seed cria 2 lojas + usuários (operacionais e administrativos) e dados cross-loja. Cada linha da matriz de isolamento vira um teste.

**Tech Stack:** Python, pytest, `http.server.HTTPServer` (já no projeto), `urllib.request` (stdlib, sem nova dependência), SQLAlchemy (já no projeto).

> **Natureza dos testes:** o código de produção da F4 **já existe**. Estes são testes de
> **regressão/caracterização**: o esperado é **PASS** (prova o isolamento). Se um teste **FALHA**,
> isso é um **achado de segurança** (IDOR aberto) → documentar e corrigir o código de produção num
> commit próprio (ver Task 11), e o teste passa a guardá-lo. Isso inverte o TDD usual: aqui o teste
> é o entregável, não o código de produção.

---

## Fatos verificados do código (referência para todas as tasks)

- `database.py`: `DB_PATH`, `ENGINE = create_engine(f"sqlite:///{DB_PATH}")`, `Session = sessionmaker(bind=ENGINE)`, `get_session()` → `Session()`. `init_db()` = `Base.metadata.create_all(ENGINE)` + `_migrar_colunas()` (usa `sqlite3.connect(DB_PATH)`) + `_migrar_dados()`. Todos leem os globais **em tempo de chamada** → rebind funciona.
- Modelos (campos relevantes): `Rede(id, nome)`; `Loja(id, rede_id, nome, codigo)`; `Usuario(id, nome, login, senha_hash, nivel, loja_id, rede_id, ativo)` com `set_senha(senha)`; `Cliente(id, nome, cpf, ..., loja_id)` (loja_id em database.py:160); `Projeto(nome_safe[PK], cliente_id, status, loja_id)` (loja_id em database.py:238).
- Níveis (`perfis.py`): operacionais com loja = `diretor`/`consultor`/`gerente_*`; administrativos = `super_admin`, `admin_rede` (não têm acesso operacional → 403 via `escopo_operacional`).
- Login: `POST /api/auth/login` JSON `{"login","senha"}` → 200 + header `Set-Cookie: omie_session=<token>; Max-Age=28800; Path=/; HttpOnly`. Endpoints protegidos lêem `Cookie: omie_session=<token>`.
- Endpoints da matriz (paths exatos):
  - Listar clientes: `GET /api/clientes` (main.py:414). Abrir cliente: `GET /api/clientes/<id>` (771).
  - Listar projetos: `GET /projetos` (306). Abrir projeto: `GET /projetos/<nome>` (741).
  - Criar cliente: `POST /api/clientes` (1549). Criar projeto: `POST /projetos/novo` (1407).
  - Sem-auth corrigidos: `PATCH /api/projetos/<nome>/status` (3514), `PUT /api/orcamentos/<id>/descontos` (3414), `PATCH /orcamentos/<id>/valor` (3472, **sem** prefixo `/api`), `POST /api/parceiros` (1804), `POST /api/parceiros/<id>/editar` (1845), `GET /api/projetos/<nome>/briefing` (385), `POST /api/clientes/<id>/briefing` (1698), `POST /api/projetos/<nome>/briefing` (1618).
- Server bootstrap: `HTTPServer((host, port), Handler)`; `server.serve_forever()`. `main.init_db()` só roda sob `__main__` — importar `main` **não** abre o banco.

## File Structure

- **Modificar:** `tests/conftest.py` — adicionar fixtures (`app_db`, `http_client_factory`, `seed`, `servidor`, `dados`) e a classe helper `HttpClient`. Hoje só tem o `sys.path.insert`.
- **Criar:** `tests/test_isolamento_f4_e2e.py` — todos os testes da matriz, agrupados por categoria.

---

## Task 1: Fixture de banco isolado + teste-canário (decide harness real vs. plano B)

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever a fixture `app_db` no conftest**

Adicionar ao final de `tests/conftest.py`:

```python
import pytest


@pytest.fixture(scope="module")
def app_db(tmp_path_factory):
    """Rebinda a engine de `database` para um SQLite temporário e cria o schema.
    Como get_session/init_db lêem os globais em tempo de chamada, o rebind vale
    para todo o processo (inclusive o servidor em thread)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import database

    db_file = str(tmp_path_factory.mktemp("f4db") / "test.db")
    database.DB_PATH = db_file
    database.ENGINE = create_engine(f"sqlite:///{db_file}", echo=False)
    database.Session = sessionmaker(bind=database.ENGINE)
    database.init_db()
    return database
```

- [ ] **Step 2: Escrever o teste-canário**

Criar `tests/test_isolamento_f4_e2e.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_canary_banco_isolado(app_db):
    # o caminho aponta para o temp, não para o omie.db real
    assert "omie.db" not in app_db.DB_PATH
    # escrita+leitura sobrevivem entre sessões → engine temp está ativa
    db = app_db.get_session()
    loja = app_db.Loja(nome="Canary")
    db.add(loja); db.commit()
    lid = loja.id
    db.close()
    db2 = app_db.get_session()
    lido = db2.query(app_db.Loja).filter_by(id=lid).first()
    db2.close()
    assert lido is not None and lido.nome == "Canary"
```

- [ ] **Step 3: Rodar o canário**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py::test_canary_banco_isolado -v`
Expected: **PASS**.

> **Gate de decisão:** se passar, o harness de servidor-real (Tasks 2+) é viável — siga.
> Se FALHAR (engine não rebindou; algum módulo capturou `Session` por valor), pare e use o
> **Plano B** da seção 7 do spec: instanciar `main.Handler` com `rfile`/`wfile` fakes (BytesIO)
> e chamar `do_GET`/`do_POST` direto, simulando o header `Cookie`. A matriz (Tasks 4–11) é a
> mesma; só muda o transporte. Documente a decisão no topo de `test_isolamento_f4_e2e.py`.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): fixture de banco isolado + canario (harness real viavel)"
```

---

## Task 2: Cliente HTTP + servidor em thread + canário de login

**Files:**
- Modify: `tests/conftest.py`
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Adicionar a classe `HttpClient` e a fixture `servidor` no conftest**

Adicionar ao `tests/conftest.py`:

```python
import json as _json
import threading
import time
import urllib.request
import urllib.error


class HttpClient:
    """Cliente HTTP fininho com cookie jar de 1 sessão (header Cookie reusado)."""
    def __init__(self, base):
        self.base = base
        self.cookie = None

    def _req(self, method, path, body=None):
        data = _json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            status, raw, headers = resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            status, raw, headers = e.code, e.read(), e.headers
        sc = headers.get("Set-Cookie")
        if sc:
            self.cookie = sc.split(";")[0]
        try:
            out = _json.loads(raw) if raw else None
        except Exception:
            out = raw
        return status, out

    def get(self, path):            return self._req("GET", path)
    def post(self, path, body=None): return self._req("POST", path, body)
    def put(self, path, body=None):  return self._req("PUT", path, body)
    def patch(self, path, body=None):return self._req("PATCH", path, body)

    def login(self, login, senha):
        return self.post("/api/auth/login", {"login": login, "senha": senha})


@pytest.fixture(scope="module")
def servidor(app_db, seed):
    """Sobe main.Handler numa thread, porta efêmera, usando o banco isolado+seed."""
    import main
    from http.server import HTTPServer

    httpd = HTTPServer(("127.0.0.1", 0), main.Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    # aguarda o servidor aceitar conexão
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/login", timeout=1)
            break
        except urllib.error.HTTPError:
            break  # respondeu (mesmo que 4xx) → está no ar
        except Exception:
            time.sleep(0.05)
    yield base
    httpd.shutdown()


@pytest.fixture
def http_client_factory(servidor):
    """Fábrica de HttpClient apontando para o servidor de teste."""
    return lambda: HttpClient(servidor)
```

> **Nota:** `servidor` depende de `seed` (Task 3). Implemente o `seed` antes de rodar o login.
> Se estiver executando estritamente em ordem, escreva o `seed` da Task 3 agora e volte.

- [ ] **Step 2: Escrever o canário de login (depende de seed da Task 3)**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
def test_canary_login_via_http(http_client_factory):
    c = http_client_factory()
    status, body = c.login("dir_l1", "senha123")
    assert status == 200 and body.get("ok") is True
    assert c.cookie and c.cookie.startswith("omie_session=")
    # sessão autenticada acessa endpoint operacional
    status, _ = c.get("/api/clientes")
    assert status == 200
```

- [ ] **Step 3: Rodar o canário de login**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py::test_canary_login_via_http -v`
Expected: **PASS** (login emite cookie e o servidor em thread usa o banco seedado).

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): harness servidor-em-thread + cliente HTTP + canario de login"
```

---

## Task 3: Fixture de seed (lojas, usuários, dados cross-loja)

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Adicionar a fixture `seed`**

Adicionar ao `tests/conftest.py`:

```python
@pytest.fixture(scope="module")
def seed(app_db):
    """2 lojas na mesma rede; 1 diretor por loja; super_admin e admin_rede;
    e dados cross-loja (1 cliente + 1 projeto em cada loja). Inserção direta
    via modelos (não pela API) para isolar a montagem do baseline."""
    db = app_db.get_session()
    rede = app_db.Rede(nome="Rede Teste")
    db.add(rede); db.flush()

    l1 = app_db.Loja(nome="Loja 1", rede_id=rede.id, codigo="LJ1")
    l2 = app_db.Loja(nome="Loja 2", rede_id=rede.id, codigo="LJ2")
    db.add_all([l1, l2]); db.flush()

    def mkuser(nome, login, nivel, loja_id=None, rede_id=None):
        u = app_db.Usuario(nome=nome, login=login, nivel=nivel,
                           loja_id=loja_id, rede_id=rede_id, ativo=1)
        u.set_senha("senha123")
        db.add(u)

    mkuser("Diretor L1", "dir_l1", "diretor", loja_id=l1.id)
    mkuser("Diretor L2", "dir_l2", "diretor", loja_id=l2.id)
    mkuser("Super",      "super",  "super_admin")
    mkuser("Adm Rede",   "adm_rede", "admin_rede", rede_id=rede.id)

    # dados cross-loja
    c1 = app_db.Cliente(nome="Cliente L1", cpf="111.111.111-11", loja_id=l1.id)
    c2 = app_db.Cliente(nome="Cliente L2", cpf="222.222.222-22", loja_id=l2.id)
    db.add_all([c1, c2]); db.flush()

    p1 = app_db.Projeto(nome_safe="Proj_L1", cliente_id=c1.id, status="quente", loja_id=l1.id)
    p2 = app_db.Projeto(nome_safe="Proj_L2", cliente_id=c2.id, status="quente", loja_id=l2.id)
    db.add_all([p1, p2])
    db.commit()

    ctx = {
        "loja1_id": l1.id, "loja2_id": l2.id,
        "cliente_l1_id": c1.id, "cliente_l2_id": c2.id,
        "projeto_l1": "Proj_L1", "projeto_l2": "Proj_L2",
    }
    db.close()
    return ctx
```

- [ ] **Step 2: Verificar que o seed sobe junto com o servidor**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py::test_canary_login_via_http -v`
Expected: **PASS** (agora que `seed` existe, a fixture `servidor` resolve e o login funciona).

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test(f4-e2e): seed de 2 lojas, usuarios e dados cross-loja"
```

---

## Task 4: Leitura cross-loja → 404 (não vaza existência)

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes de leitura cross-loja**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    return c


def test_cliente_de_outra_loja_da_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/api/clientes/{seed['cliente_l1_id']}")
    assert status == 404


def test_projeto_de_outra_loja_da_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/projetos/{seed['projeto_l1']}")
    assert status == 404


def test_cliente_da_propria_loja_abre(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/api/clientes/{seed['cliente_l2_id']}")
    assert status == 200


def test_projeto_da_propria_loja_abre(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.get(f"/projetos/{seed['projeto_l2']}")
    assert status == 200
```

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "outra_loja or propria_loja" -v`
Expected: **PASS** nos 4. Se algum cross-loja retornar 200 → **achado** (IDOR de leitura) → Task 11.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): leitura cross-loja de cliente/projeto retorna 404"
```

---

## Task 5: Escopo das listagens (só vê a própria loja)

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes de listagem**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
def test_lista_clientes_so_da_propria_loja(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get("/api/clientes")
    assert status == 200
    clientes = body["clientes"] if isinstance(body, dict) and "clientes" in body else body
    ids = {item.get("id") for item in clientes}
    assert seed["cliente_l2_id"] in ids
    assert seed["cliente_l1_id"] not in ids


def test_lista_projetos_so_da_propria_loja(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, body = c.get("/projetos")
    assert status == 200
    projetos = body["projetos"] if isinstance(body, dict) and "projetos" in body else body
    nomes = {p.get("nome_safe") for p in projetos}
    assert seed["projeto_l1"] not in nomes
```

> **Nota de execução:** confirme a forma da resposta de `GET /api/clientes` (main.py:414) e
> `GET /projetos` (main.py:306) — o código acima cobre tanto `{"clientes": [...]}` quanto lista
> direta, e usa `nome_safe` para projetos (chave do modelo). Ajuste o nome da chave se diferir.

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "lista" -v`
Expected: **PASS**. Cliente/projeto da Loja 1 não aparece para o diretor da Loja 2.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): listagens de cliente/projeto escopadas por loja"
```

---

## Task 6: Perfis administrativos → 403 no operacional

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes de 403**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
import pytest


@pytest.mark.parametrize("who", ["super", "adm_rede"])
def test_admin_sem_acesso_operacional_lista_projetos(http_client_factory, who):
    c = _login(http_client_factory, who)
    status, _ = c.get("/projetos")
    assert status == 403


@pytest.mark.parametrize("who", ["super", "adm_rede"])
def test_admin_sem_acesso_operacional_lista_clientes(http_client_factory, who):
    c = _login(http_client_factory, who)
    status, _ = c.get("/api/clientes")
    assert status == 403
```

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "admin_sem_acesso" -v`
Expected: **PASS** (4 casos: 2 perfis × 2 endpoints). Se vier 200 → **achado** → Task 11.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): super_admin/admin_rede recebem 403 no operacional"
```

---

## Task 7: Endpoints sem-auth corrigidos → 401 para anônimo

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes de 401 anônimo**

Adicionar em `tests/test_isolamento_f4_e2e.py`. Cada caso usa um `HttpClient` **sem login**
(sem cookie). O guard de auth deve responder 401 antes de resolver o recurso:

```python
def test_status_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.patch(f"/api/projetos/{seed['projeto_l1']}/status", {"status": "morno"})
    assert status == 401


def test_descontos_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.put("/api/orcamentos/999/descontos", {"descontos": []})
    assert status == 401


def test_valor_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.patch("/orcamentos/999/valor", {"valor": 1000})
    assert status == 401


def test_parceiros_create_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.post("/api/parceiros", {"nome": "X"})
    assert status == 401


def test_parceiros_editar_sem_auth_401(http_client_factory):
    c = http_client_factory()
    status, _ = c.post("/api/parceiros/999/editar", {"nome": "X"})
    assert status == 401


def test_briefing_projeto_get_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.get(f"/api/projetos/{seed['projeto_l1']}/briefing")
    assert status == 401


def test_briefing_cliente_post_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.post(f"/api/clientes/{seed['cliente_l1_id']}/briefing", {})
    assert status == 401


def test_briefing_projeto_post_sem_auth_401(http_client_factory, seed):
    c = http_client_factory()
    status, _ = c.post(f"/api/projetos/{seed['projeto_l1']}/briefing", {})
    assert status == 401
```

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "sem_auth" -v`
Expected: **PASS** em todos. Qualquer 200/2xx/500 em vez de 401 → **achado** (endpoint sem guard) → Task 11.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): endpoints sensiveis exigem auth (401 anonimo)"
```

---

## Task 8: Escrita cross-loja autenticada → 404/403 e estado intacto

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes de escrita cross-loja**

Adicionar em `tests/test_isolamento_f4_e2e.py`. Diretor da Loja 2 tenta mexer em recurso da
Loja 1; deve tomar 404/403 e o estado da Loja 1 **não muda**:

```python
def test_status_cross_loja_nao_altera(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.patch(f"/api/projetos/{seed['projeto_l1']}/status", {"status": "perdido"})
    assert status in (403, 404)
    # estado da Loja 1 permanece "quente" (valor do seed)
    db = app_db.get_session()
    proj = db.get(app_db.Projeto, seed["projeto_l1"])
    estado = proj.status
    db.close()
    assert estado == "quente"


def test_briefing_cliente_cross_loja_bloqueado(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")
    status, _ = c.post(f"/api/clientes/{seed['cliente_l1_id']}/briefing", {})
    assert status in (403, 404)
```

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "cross_loja" -v`
Expected: **PASS**. Se o status da Loja 1 mudar para "perdido" → **achado** (IDOR de escrita) → Task 11.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): escrita cross-loja bloqueada e estado da outra loja intacto"
```

---

## Task 9: Criação carimba `loja_id` do autor

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Confirmar a forma do POST /api/clientes**

Antes de escrever, leia `main.py:1549-1618` (handler do `POST /api/clientes`) para confirmar os
campos obrigatórios e a chave do id na resposta. O corpo abaixo usa os campos do exemplo já
validado no projeto; ajuste se o handler exigir outros.

- [ ] **Step 2: Escrever o teste de carimbo**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
def test_criacao_de_cliente_carimba_loja_do_autor(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    novo = {"nome": "Cliente Novo L2", "cpf": "333.333.333-33", "telefone": "(12) 90000-0000"}
    status, body = c.post("/api/clientes", novo)
    assert status in (200, 201)
    # localiza o cliente recém-criado pelo CPF e confere loja_id == loja 2
    db = app_db.get_session()
    cli = db.query(app_db.Cliente).filter_by(cpf="333.333.333-33").first()
    loja = cli.loja_id if cli else None
    db.close()
    assert cli is not None
    assert loja == seed["loja2_id"]
```

- [ ] **Step 3: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "carimba" -v`
Expected: **PASS** (cliente criado com `loja_id` = Loja 2). Se `loja_id` vier NULL ou da Loja 1 → **achado** → Task 11.

- [ ] **Step 4: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): criacao de cliente carimba loja_id do autor"
```

---

## Task 10: Sem regressão para a loja legítima + colisão de CPF

**Files:**
- Test: `tests/test_isolamento_f4_e2e.py`

- [ ] **Step 1: Escrever os testes**

Adicionar em `tests/test_isolamento_f4_e2e.py`:

```python
def test_diretor_l1_opera_normalmente(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    # vê o próprio cliente e o próprio projeto
    s1, _ = c.get(f"/api/clientes/{seed['cliente_l1_id']}")
    s2, _ = c.get(f"/projetos/{seed['projeto_l1']}")
    assert s1 == 200 and s2 == 200


def test_colisao_cpf_nao_vaza_cliente_de_outra_loja(http_client_factory, seed, app_db):
    # diretor L2 cadastra cliente com CPF que JÁ existe na Loja 1 ("111.111.111-11")
    c = _login(http_client_factory, "dir_l2")
    status, body = c.post("/api/clientes", {"nome": "Homonimo", "cpf": "111.111.111-11"})
    # não deve devolver/abrir o cliente da Loja 1; aceitável: cria no escopo L2 OU erro de validação,
    # mas NUNCA expõe o id/dados do cliente da Loja 1.
    if status in (200, 201) and isinstance(body, dict):
        retornado_id = body.get("id") or (body.get("cliente") or {}).get("id")
        assert retornado_id != seed["cliente_l1_id"]
    # e o cliente da Loja 1 continua pertencendo à Loja 1
    db = app_db.get_session()
    original = db.get(app_db.Cliente, seed["cliente_l1_id"])
    loja_orig = original.loja_id
    db.close()
    assert loja_orig == seed["loja1_id"]
```

> **Nota:** confirme em `main.py` (handler de criação de cliente, ~1549) o comportamento esperado
> na colisão de CPF (a correção da F4 está documentada no smoke). Ajuste a asserção ao contrato
> real, mantendo a invariante: **nunca vazar o cliente da outra loja**.

- [ ] **Step 2: Rodar**

Run: `python -m pytest tests/test_isolamento_f4_e2e.py -k "diretor_l1 or colisao" -v`
Expected: **PASS**.

- [ ] **Step 3: Commit**

```bash
git add tests/test_isolamento_f4_e2e.py
git commit -m "test(f4-e2e): sem regressao na loja legitima + colisao de CPF isolada"
```

---

## Task 11: Tratamento de achados (só se algum teste falhar)

**Files:** (dependem do achado)
- Modify: o handler em `main.py` que vazou (ex.: faltou `get_usuario_sessao`/`escopo_operacional`/`_obj_da_loja`).

- [ ] **Step 1: Para cada teste que FALHOU nas Tasks 4–10**

Tratar como bug de produção (não relaxar o teste):
1. Confirmar que o teste reflete o comportamento correto (isolamento). Se sim, é IDOR real.
2. Localizar o handler pelo path (tabela "Fatos verificados").
3. Aplicar o mesmo padrão da F4 já usado nos vizinhos: 401 sem sessão → `escopo_operacional` (403 administrativo) → `_obj_da_loja`/`_projeto_da_loja` (404 cross-loja), **antes** de qualquer query que mude/exponha estado.
4. Rodar o teste alvo → agora **PASS**.

- [ ] **Step 2: Commit do fix (separado dos testes)**

```bash
git add main.py
git commit -m "fix(isolamento): <endpoint> — fechar IDOR pego pela suite E2E (F4)"
```

> Se **nenhum** teste falhou, pule esta task inteira.

---

## Task 12: Suíte completa verde + atualização do smoke doc

**Files:**
- Modify: `docs/processos/SMOKE_F4_ISOLAMENTO.md`

- [ ] **Step 1: Rodar a suíte inteira**

Run: `python -m pytest -q`
Expected: **todos verdes** (201 anteriores + os novos E2E). Anotar o total.

- [ ] **Step 2: Atualizar o status no smoke doc**

Em `docs/processos/SMOKE_F4_ISOLAMENTO.md`, trocar o bloco de status do topo para registrar que o
isolamento agora tem **suíte de regressão E2E automatizada** (`tests/test_isolamento_f4_e2e.py`,
servidor real + 2 lojas, sem depender do ambiente do usuário), e que o smoke manual com 2 lojas
fica como sanity final opcional em produção. Listar quaisquer achados corrigidos na Task 11.

- [ ] **Step 3: Commit**

```bash
git add docs/processos/SMOKE_F4_ISOLAMENTO.md
git commit -m "docs(smoke): F4 — isolamento coberto por suite de regressao E2E automatizada"
```

---

## Self-Review (preenchido pelo autor do plano)

**Cobertura do spec:** Seção 3.1 (isolamento do banco) → Task 1. 3.2/3.3 (servidor+cliente) → Task 2. Seção 4 (seed) → Task 3. Matriz seção 5: leitura cross-loja → Task 4; listagens → Task 5; 403 administrativo → Task 6; 401 sem-auth → Task 7; escrita cross-loja + estado intacto → Task 8; carimbo de loja → Task 9; sem-regressão + colisão CPF → Task 10. Seção 6 (estrutura de arquivos) → Tasks 1–3. Seção 7 (plano B) → gate na Task 1. Seção 8 (critérios) → Tasks 11–12.

**Placeholders:** nenhum "TBD/TODO"; as 3 "Notas de execução" (Tasks 5, 9, 10) são checagens de *forma de resposta* da API com fallback no código, não lacunas — o teste roda como escrito e só pede ajuste de chave se o contrato diferir.

**Consistência de tipos:** `HttpClient` (get/post/put/patch/login), fixtures `app_db`/`seed`/`servidor`/`http_client_factory`, helper `_login(factory, who)`, e chaves do `seed` (`cliente_l1_id`, `projeto_l1`, `loja2_id`, etc.) usadas com os mesmos nomes em todas as tasks.
