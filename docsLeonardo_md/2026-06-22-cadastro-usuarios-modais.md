# Cadastro de usuários por modal nos 3 níveis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir as cadeias de `prompt()` de criação/edição de usuário por um modal único reutilizável e definir a criação de admin_rede (Nível 2) e super_admin (Nível 1) no console de 3 níveis.

**Architecture:** Backend continua dono da regra de permissão (`perfis.py` + `mod_tenancy`). Um novo endpoint `perfis-permitidos` alimenta o `<select>` do modal; `POST`/`PATCH` ganham os campos cadastrais novos e as travas (anti-escalonamento afrouxado para admin_rede, anti-lockout). O frontend é um único modal `modal-usuario` reutilizado nos 3 níveis.

**Tech Stack:** Python 3 (stdlib `http.server`, SQLAlchemy, sqlite3), HTML/CSS/JS vanilla em `static/index.html`, pytest.

## Global Constraints

- Migração de coluna segue o padrão idempotente de `database._migrar_colunas` (PRAGMA `table_info` + `ALTER TABLE ... ADD COLUMN` só se ausente). Verbatim do spec: colunas `email`, `cpf`, `whatsapp`, todas `nullable`.
- Fonte única da verdade de perfis/permissões: `perfis.py` + `mod_tenancy`. O frontend nunca decide permissão — só desenha o que o backend autoriza.
- Remoção é sempre **soft delete** (`ativo=0`); nenhuma exclusão física de `Usuario`.
- Funções em `mod_tenancy`/`mod_usuarios` são **puras** (sem I/O, sem ORM): recebem dicts, devolvem listas/tuplas.
- Mensagens de UI e erros em português, como no resto do app.
- Commits frequentes, um por task.

---

### Task 1: Migração e modelo — colunas `email`/`cpf`/`whatsapp` em `usuarios`

**Files:**
- Modify: `database.py:33-41` (modelo `Usuario`) e `database.py:450-457` (bloco `usuarios` em `_migrar_colunas`)
- Test: `tests/test_usuarios_colunas.py` (criar)

**Interfaces:**
- Produces: `Usuario.email`, `Usuario.cpf`, `Usuario.whatsapp` (colunas `String`, nullable) e as colunas físicas `email`/`cpf`/`whatsapp` na tabela `usuarios`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_usuarios_colunas.py
import sqlite3

def test_usuarios_tem_colunas_contato(app_db):
    conn = sqlite3.connect(app_db.DB_PATH)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(usuarios)")}
    conn.close()
    assert {"email", "cpf", "whatsapp"} <= cols

def test_usuario_persiste_contato(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Contato", login="ctt", nivel="consultor",
                       email="a@b.com", cpf="123", whatsapp="9999")
    u.set_senha("x")
    db.add(u); db.commit()
    uid = u.id; db.close()
    db2 = app_db.get_session()
    lido = db2.get(app_db.Usuario, uid); db2.close()
    assert lido.email == "a@b.com" and lido.cpf == "123" and lido.whatsapp == "9999"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios_colunas.py -v`
Expected: FAIL (`AttributeError`/coluna inexistente — modelo ainda não tem os campos).

- [ ] **Step 3: Adicionar as colunas ao modelo**

Em `database.py`, no modelo `Usuario`, logo após `telefone = Column(String(20), nullable=True)` (linha 37):

```python
    email         = Column(String(120), nullable=True)
    cpf           = Column(String(20),  nullable=True)
    whatsapp      = Column(String(20),  nullable=True)
```

- [ ] **Step 4: Adicionar a migração idempotente**

Em `database.py`, no bloco `# ── usuarios ──` de `_migrar_colunas` (após o loop de `loja_id`/`rede_id`, linha ~457):

```python
        for col, tipo in [("email", "VARCHAR(120)"), ("cpf", "VARCHAR(20)"),
                          ("whatsapp", "VARCHAR(20)")]:
            if col not in usr_cols:
                cur.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios_colunas.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_usuarios_colunas.py
git commit -m "feat(usuarios): colunas email/cpf/whatsapp + migracao idempotente"
```

---

### Task 2: `mod_tenancy` — `perfis_atribuiveis` + admin_rede gere pares

**Files:**
- Modify: `mod_tenancy.py:102-139` (`atribuir_tenant_usuario`) e fim do arquivo (nova função)
- Test: `tests/test_perfis_atribuiveis.py` (criar); atualizar `tests/test_tenancy_escopo.py:49-53`

**Interfaces:**
- Consumes: `perfis.pode`, `perfis.slugs`, `_eh_super_admin`, `_eh_admin_rede` (já em `mod_tenancy`).
- Produces: `perfis_atribuiveis(ator: dict, escopo: str) -> list[str]`; `atribuir_tenant_usuario` passa a aceitar admin_rede criando `admin_rede` (retorna `(None, ator['rede_id'], [])`).

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_perfis_atribuiveis.py
import mod_tenancy as mt

SUPER = {"nivel": "super_admin", "loja_id": None, "rede_id": None}
ADMR  = {"nivel": "admin_rede",  "loja_id": None, "rede_id": 1}
DIR   = {"nivel": "diretor",     "loja_id": 10,   "rede_id": None}
CONS  = {"nivel": "consultor",   "loja_id": 10,   "rede_id": None}

def test_loja_lista_operacionais_sem_admins():
    for ator in (DIR, ADMR, SUPER):
        lst = mt.perfis_atribuiveis(ator, "loja")
        assert "consultor" in lst and "diretor" in lst
        assert "super_admin" not in lst and "admin_rede" not in lst

def test_rede_so_admin_rede_e_so_para_super_e_admrede():
    assert mt.perfis_atribuiveis(SUPER, "rede") == ["admin_rede"]
    assert mt.perfis_atribuiveis(ADMR,  "rede") == ["admin_rede"]
    assert mt.perfis_atribuiveis(DIR,   "rede") == []

def test_plataforma_so_super_admin():
    assert mt.perfis_atribuiveis(SUPER, "plataforma") == ["super_admin"]
    assert mt.perfis_atribuiveis(ADMR,  "plataforma") == []

def test_sem_gerir_usuarios_lista_vazia():
    assert mt.perfis_atribuiveis(CONS, "loja") == []

def test_admin_rede_cria_par():
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "admin_rede"}) == (None, 1, [])

def test_admin_rede_nao_cria_super():
    _, _, erros = mt.atribuir_tenant_usuario(ADMR, {"nivel": "super_admin"})
    assert erros
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_perfis_atribuiveis.py -v`
Expected: FAIL (`AttributeError: module 'mod_tenancy' has no attribute 'perfis_atribuiveis'` e `test_admin_rede_cria_par` falha pela regra antiga).

- [ ] **Step 3: Afrouxar `atribuir_tenant_usuario` (ramo admin_rede)**

Em `mod_tenancy.py`, substituir o bloco `if _eh_admin_rede(ator):` (linhas 122-129) por:

```python
    if _eh_admin_rede(ator):
        if nivel_novo == "super_admin":
            erros.append("Sem permissão para criar esse perfil.")
            return (None, None, erros)
        if nivel_novo == "admin_rede":
            return (None, ator.get("rede_id"), erros)   # par na mesma rede
        loja_id = dados.get("loja_id")
        if not loja_id:
            erros.append("Loja é obrigatória.")
        return (loja_id, None, erros)
```

- [ ] **Step 4: Adicionar `perfis_atribuiveis` ao fim de `mod_tenancy.py`**

```python
def perfis_atribuiveis(ator, escopo):
    """Slugs que `ator` pode atribuir em `escopo` ∈ {loja, rede, plataforma}.
    Fonte única do dropdown de perfil no modal de usuário. A checagem de que a
    loja/rede concreta está no escopo do ator é feita na rota (precisa do banco)."""
    if not perfis.pode(ator.get("nivel"), "gerir_usuarios"):
        return []
    if escopo == "plataforma":
        return ["super_admin"] if _eh_super_admin(ator) else []
    if escopo == "rede":
        if _eh_super_admin(ator) or _eh_admin_rede(ator):
            return ["admin_rede"]
        return []
    if escopo == "loja":
        return [s for s in perfis.slugs() if s not in ("super_admin", "admin_rede")]
    return []
```

- [ ] **Step 5: Atualizar o teste que afirmava o contrário**

Em `tests/test_tenancy_escopo.py`, substituir `test_atribuir_tenant_admin_rede` (linhas 49-53) por:

```python
def test_atribuir_tenant_admin_rede():
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "diretor", "loja_id": 10}) == (10, None, [])
    # admin_rede agora cria PAR admin_rede (herda a própria rede); super_admin segue bloqueado
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "admin_rede"}) == (None, 1, [])
    _, _, e_super = mt.atribuir_tenant_usuario(ADMR, {"nivel": "super_admin"})
    assert e_super
```

- [ ] **Step 6: Rodar e ver passar**

Run: `python -m pytest tests/test_perfis_atribuiveis.py tests/test_tenancy_escopo.py -v`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add mod_tenancy.py tests/test_perfis_atribuiveis.py tests/test_tenancy_escopo.py
git commit -m "feat(tenancy): perfis_atribuiveis + admin_rede gere pares na rede"
```

---

### Task 3: `mod_usuarios` — validação de e-mail e CPF

**Files:**
- Modify: `mod_usuarios.py` (helper `_validar_contato` + chamadas)
- Test: `tests/test_usuarios.py` (acrescentar casos)

**Interfaces:**
- Produces: `validar_novo_usuario`/`validar_edicao_usuario` passam a acusar "E-mail inválido." quando `email` preenchido tem formato inválido; CPF não bloqueia nesta fase.

- [ ] **Step 1: Escrever os testes que falham**

Acrescentar ao fim de `tests/test_usuarios.py`:

```python
def test_email_invalido_acusa():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "1", "nivel": "consultor", "email": "errado"},
        logins_existentes=[])
    assert any("mail" in e.lower() for e in erros)

def test_email_valido_ou_vazio_passa():
    base = {"nome": "Ana", "login": "ana", "senha": "1", "nivel": "consultor"}
    assert mu.validar_novo_usuario({**base, "email": "a@b.com"}, []) == []
    assert mu.validar_novo_usuario({**base, "email": ""}, []) == []

def test_edicao_email_invalido_acusa():
    assert any("mail" in e.lower() for e in mu.validar_edicao_usuario({"email": "x"}))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios.py -v`
Expected: FAIL (e-mail inválido não é acusado hoje).

- [ ] **Step 3: Implementar a validação de contato**

Em `mod_usuarios.py`, no topo após `import perfis`:

```python
import re

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validar_contato(dados, erros):
    email = (dados.get("email") or "").strip()
    if email and not _RE_EMAIL.match(email):
        erros.append("E-mail inválido.")
    # CPF: opcional, sem dígito verificador obrigatório nesta fase.
```

Chamar em `validar_novo_usuario`, antes do `return erros`:

```python
    _validar_contato(dados, erros)
    return erros
```

Chamar em `validar_edicao_usuario`, antes do `return erros`:

```python
    _validar_contato(dados, erros)
    return erros
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add mod_usuarios.py tests/test_usuarios.py
git commit -m "feat(usuarios): validacao de e-mail no cadastro/edicao"
```

---

### Task 4: Endpoint `GET /api/admin/usuarios/perfis-permitidos`

**Files:**
- Modify: `main.py` (do_GET, logo após o bloco `elif path == "/api/admin/usuarios":` que termina na linha ~542)
- Test: `tests/test_usuarios_e2e.py` (criar)

**Interfaces:**
- Consumes: `get_usuario_sessao`, `_ator_dict`, `mod_tenancy.perfis_atribuiveis`, `perfis.rotulo`, `send_json`.
- Produces: `GET /api/admin/usuarios/perfis-permitidos?escopo=&loja_id=&rede_id=` → `{"ok":True,"perfis":[{"slug","rotulo"}]}` (403 sem `gerir_usuarios`).

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_usuarios_e2e.py
def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c

def test_perfis_permitidos_loja_para_diretor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.get(f"/api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200 and body["ok"]
    slugs = {p["slug"] for p in body["perfis"]}
    assert "consultor" in slugs and "super_admin" not in slugs and "admin_rede" not in slugs

def test_perfis_permitidos_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st == 200 and [p["slug"] for p in body["perfis"]] == ["super_admin"]
    c2 = _login(http_client_factory, "dir_l1")
    st2, body2 = c2.get("/api/admin/usuarios/perfis-permitidos?escopo=plataforma")
    assert st2 == 200 and body2["perfis"] == []
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: FAIL (rota inexistente → resposta 404/erro, asserção quebra).

- [ ] **Step 3: Implementar o endpoint**

Em `main.py`, logo após o fechamento do bloco `elif path == "/api/admin/usuarios":` (antes de `elif path == "/api/admin/redes":`, linha ~544):

```python
        elif path == "/api/admin/usuarios/perfis-permitidos":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs
            qs = parse_qs(urlparse(self.path).query)
            escopo = (qs.get("escopo") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                slugs = mod_tenancy.perfis_atribuiveis(ator, escopo)
                self.send_json({"ok": True, "perfis": [
                    {"slug": s, "rotulo": perfis.rotulo(s)} for s in slugs]})
            finally:
                db.close()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_usuarios_e2e.py
git commit -m "feat(api): GET /api/admin/usuarios/perfis-permitidos"
```

---

### Task 5: `GET /api/admin/usuarios` — filtros por escopo + retornar contato

**Files:**
- Modify: `main.py:511-542` (bloco GET `/api/admin/usuarios`)
- Test: `tests/test_usuarios_e2e.py` (acrescentar)

**Interfaces:**
- Consumes: bloco GET de usuários existente (`visiveis`, `_ator_dict`).
- Produces: `GET /api/admin/usuarios?escopo=loja|rede|plataforma&loja_id=&rede_id=` filtra a fatia; cada item passa a incluir `email`, `cpf`, `whatsapp`.

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_usuarios_e2e.py`:

```python
def test_lista_escopo_loja_so_da_loja(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    assert st == 200
    logins = {u["login"] for u in body["usuarios"]}
    assert "dir_l1" in logins and "dir_l2" not in logins and "super" not in logins

def test_lista_escopo_plataforma_so_super(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get("/api/admin/usuarios?escopo=plataforma")
    assert st == 200
    niveis = {u["nivel"] for u in body["usuarios"]}
    assert niveis == {"super_admin"}

def test_lista_inclui_campos_contato(http_client_factory, seed):
    c = _login(http_client_factory, "super")
    st, body = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    u = body["usuarios"][0]
    assert "email" in u and "cpf" in u and "whatsapp" in u
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: FAIL (sem filtro de escopo a lista traz todos; faltam `email`/`cpf`/`whatsapp`).

- [ ] **Step 3: Adicionar campos de contato à resposta**

Em `main.py`, no dict de cada usuário (linhas 537-540), acrescentar:

```python
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "whatsapp": u.whatsapp or "", "email": u.email or "", "cpf": u.cpf or "",
                     "loja_id": u.loja_id, "rede_id": u.rede_id,
                     "ativo": bool(u.ativo)} for u in visiveis]})
```

- [ ] **Step 4: Aplicar o filtro de escopo**

Em `main.py`, logo após o `for`/`if ok: visiveis.append(u)` e ANTES do `self.send_json` (linha ~536), inserir:

```python
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(self.path).query)
                escopo = (qs.get("escopo") or [""])[0].strip()
                if escopo == "loja":
                    fl = (qs.get("loja_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.loja_id is not None and str(u.loja_id) == fl]
                elif escopo == "rede":
                    fr = (qs.get("rede_id") or [""])[0]
                    visiveis = [u for u in visiveis
                                if u.nivel == "admin_rede" and str(u.rede_id) == fr]
                elif escopo == "plataforma":
                    visiveis = [u for u in visiveis
                                if u.nivel == "super_admin"
                                and u.loja_id is None and u.rede_id is None]
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_usuarios_e2e.py
git commit -m "feat(api): filtro por escopo + campos de contato na lista de usuarios"
```

---

### Task 6: `POST /api/admin/usuarios` — gravar contato (+ admin_rede cria par)

**Files:**
- Modify: `main.py:2586-2592` (construção do `Usuario` no POST)
- Test: `tests/test_usuarios_e2e.py` (acrescentar)

**Interfaces:**
- Consumes: POST de usuários existente, `atribuir_tenant_usuario` (já afrouxado na Task 2).
- Produces: `POST` persiste `email`/`cpf`/`whatsapp`; admin_rede cria par admin_rede.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_diretor_cria_usuario_loja_com_contato(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Nova Pessoa", "login": "nova1", "senha": "s1", "nivel": "consultor",
        "telefone": "1", "whatsapp": "2", "email": "n@p.com", "cpf": "000",
        "loja_id": seed["loja1_id"]})
    assert st == 200 and body["ok"]
    st2, lst = c.get(f"/api/admin/usuarios?escopo=loja&loja_id={seed['loja1_id']}")
    novo = next(u for u in lst["usuarios"] if u["login"] == "nova1")
    assert novo["email"] == "n@p.com" and novo["whatsapp"] == "2"

def test_admin_rede_cria_par(http_client_factory, seed):
    c = _login(http_client_factory, "adm_rede")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "Outro Adm", "login": "adm2", "senha": "s1", "nivel": "admin_rede"})
    assert st == 200 and body["ok"]

def test_diretor_nao_cria_super(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    st, body = c.post("/api/admin/usuarios", {
        "nome": "X", "login": "x9", "senha": "s", "nivel": "super_admin",
        "loja_id": seed["loja1_id"]})
    assert body["ok"] is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: FAIL (contato não persiste — `email`/`whatsapp` vêm vazios).

- [ ] **Step 3: Persistir os campos de contato no POST**

Em `main.py`, substituir a construção do `Usuario` (linhas 2586-2590) por:

```python
                    u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                                nivel=req["nivel"].strip(),
                                telefone=(req.get("telefone") or "").strip(),
                                whatsapp=(req.get("whatsapp") or "").strip(),
                                email=(req.get("email") or "").strip(),
                                cpf=(req.get("cpf") or "").strip(),
                                loja_id=loja_id, rede_id=rede_id)
                    u.set_senha(req["senha"])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_usuarios_e2e.py
git commit -m "feat(api): POST usuarios grava contato e admin_rede cria par"
```

---

### Task 7: `PATCH /api/admin/usuarios/<id>` — contato, escalonamento e anti-lockout

**Files:**
- Modify: `main.py:3742-3750` (bloco PATCH de usuário)
- Test: `tests/test_usuarios_e2e.py` (acrescentar)

**Interfaces:**
- Consumes: PATCH de usuário existente (`u`, `ator`, `usuario` da sessão).
- Produces: PATCH grava `nome`/`email`/`cpf`/`whatsapp`; admin_rede pode atribuir `admin_rede`; super_admin segue exclusivo para `super_admin`; ator não altera o próprio `nivel` nem se inativa.

- [ ] **Step 1: Escrever o teste que falha**

```python
def test_admin_rede_edita_par(http_client_factory, seed, app_db):
    # cria um par admin_rede para editar
    c = _login(http_client_factory, "adm_rede")
    c.post("/api/admin/usuarios", {"nome": "Par", "login": "par1", "senha": "s", "nivel": "admin_rede"})
    db = app_db.get_session()
    pid = db.query(app_db.Usuario).filter_by(login="par1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{pid}", {"telefone": "55", "email": "p@p.com"})
    assert st == 200 and body["ok"]

def test_nao_inativa_a_si_mesmo(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"ativo": False})
    assert body["ok"] is False

def test_nao_rebaixa_proprio_perfil(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    meu_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{meu_id}", {"nivel": "consultor"})
    assert body["ok"] is False

def test_diretor_nao_promove_para_admin_rede(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    db = app_db.get_session()
    alvo = db.query(app_db.Usuario).filter_by(login="dir_l2").first().id
    db.close()
    st, body = c.patch(f"/api/admin/usuarios/{alvo}", {"nivel": "admin_rede"})
    assert body["ok"] is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python -m pytest tests/test_usuarios_e2e.py -v`
Expected: FAIL (anti-lockout inexistente; admin_rede não consegue ser atribuído por admin_rede pela regra antiga).

- [ ] **Step 3: Reescrever o trecho de escalonamento + gravação**

Em `main.py`, substituir o bloco "anti-escalonamento" + gravações (linhas 3742-3750) por:

```python
                    # anti-lockout: o ator não altera o próprio perfil nem se inativa
                    eh_proprio = (u.id == usuario.get("id"))
                    if eh_proprio and "nivel" in req and req["nivel"].strip() != u.nivel:
                        self.send_json({"ok": False,
                            "erro": "Não é possível alterar o próprio perfil."}, code=403)
                        return
                    if eh_proprio and "ativo" in req and not req["ativo"]:
                        self.send_json({"ok": False,
                            "erro": "Não é possível inativar a si mesmo."}, code=403)
                        return
                    # anti-escalonamento: super_admin só por super_admin;
                    # admin_rede por super_admin ou admin_rede
                    novo_nivel = req["nivel"].strip() if "nivel" in req else None
                    if novo_nivel == "super_admin" and not mod_tenancy._eh_super_admin(ator):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if novo_nivel == "admin_rede" and not (
                            mod_tenancy._eh_super_admin(ator) or mod_tenancy._eh_admin_rede(ator)):
                        self.send_json({"ok": False,
                            "erro": "Sem permissão para atribuir esse perfil."}, code=403)
                        return
                    if "nome" in req:     u.nome     = req["nome"].strip()
                    if "nivel" in req:    u.nivel    = req["nivel"].strip()
                    if "telefone" in req: u.telefone = (req.get("telefone") or "").strip()
                    if "whatsapp" in req: u.whatsapp = (req.get("whatsapp") or "").strip()
                    if "email" in req:    u.email    = (req.get("email") or "").strip()
                    if "cpf" in req:      u.cpf      = (req.get("cpf") or "").strip()
                    if "ativo" in req:    u.ativo    = 1 if req["ativo"] else 0
                    if req.get("senha"):  u.set_senha(req["senha"])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python -m pytest tests/test_usuarios_e2e.py tests/test_perfis_tenancy.py -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte inteira (regressão)**

Run: `python -m pytest -q`
Expected: PASS (sem regressões nos testes de tenancy/isolamento existentes).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_usuarios_e2e.py
git commit -m "feat(api): PATCH usuarios com contato, escalonamento admin_rede e anti-lockout"
```

---

### Task 8: Frontend — modal `modal-usuario` + wiring do Nível 3

**Files:**
- Modify: `static/index.html` — bloco de modais (~linha 1640, junto dos outros `modal-overlay`) e funções admin (`adminUsuariosNovo`/`adminUsuariosEditar`/`adminUsuariosCarregar`, ~6452-6505)

**Interfaces:**
- Consumes: `esc`, `avisoPopup`, `showToast`, `_usuarioAtual`, `_adminNav`, endpoints das Tasks 4-7.
- Produces: `abrirModalUsuario(ctx)`, `abrirModalUsuarioEditar(u)`, `fecharModalUsuario()`, `salvarModalUsuario()`, `_escopoDeUsuario(u)`.

> **Sem harness de teste JS neste repo** — esta task usa **verificação manual** no navegador (passo final).

- [ ] **Step 1: Adicionar o HTML do modal**

Em `static/index.html`, junto aos outros modais (após `modal-novo-ambiente`, ~linha 1642), inserir:

```html
<div id="modal-usuario" class="modal-overlay" style="display:none">
  <div class="modal-box" style="max-width:460px;max-height:88vh;overflow:auto">
    <div class="modal-title" id="musr-titulo">Novo usuário</div>
    <div class="grid2" style="gap:10px;margin-top:6px">
      <div><label class="field-label">Nome</label>
        <input id="musr-nome" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">Login</label>
        <input id="musr-login" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">Senha</label>
        <input id="musr-senha" type="password" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">Perfil</label>
        <select id="musr-perfil" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></select></div>
      <div><label class="field-label">Telefone</label>
        <input id="musr-tel" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">WhatsApp</label>
        <input id="musr-wpp" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">E-mail</label>
        <input id="musr-email" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
      <div><label class="field-label">CPF</label>
        <input id="musr-cpf" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>
    </div>
    <div id="musr-ativo-wrap" style="display:none;margin-top:10px;font-size:12px">
      <label><input type="checkbox" id="musr-ativo"> Ativo</label>
    </div>
    <div id="musr-self-nota" style="display:none;margin-top:8px;font-size:11px;color:var(--muted)">
      Você não pode alterar o próprio perfil ou status.</div>
    <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:14px">
      <button class="btn btn-ghost btn-sm" onclick="fecharModalUsuario()">Cancelar</button>
      <button class="btn btn-primary btn-sm" onclick="salvarModalUsuario()">Salvar</button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Adicionar as funções do modal**

Em `static/index.html`, substituir `adminUsuariosNovo` e `adminUsuariosEditar` (linhas 6476-6505) por:

```javascript
let _modalUserCtx = null;

function _escopoDeUsuario(u){
  if (u.nivel === 'super_admin') return { escopo: 'plataforma' };
  if (u.nivel === 'admin_rede')  return { escopo: 'rede', rede_id: u.rede_id };
  return { escopo: 'loja', loja_id: u.loja_id };
}

async function abrirModalUsuario(ctx){
  _modalUserCtx = ctx;
  const q = new URLSearchParams({ escopo: ctx.escopo });
  if (ctx.loja_id) q.set('loja_id', ctx.loja_id);
  if (ctx.rede_id) q.set('rede_id', ctx.rede_id);
  const pd = await fetch('/api/admin/usuarios/perfis-permitidos?' + q.toString(),
    { credentials: 'same-origin' }).then(r => r.json()).catch(() => ({ perfis: [] }));
  const sel = document.getElementById('musr-perfil');
  sel.innerHTML = (pd.perfis || []).map(p => `<option value="${p.slug}">${esc(p.rotulo)}</option>`).join('');
  const ed = ctx.modo === 'editar';
  document.getElementById('musr-titulo').textContent = ed ? 'Editar usuário' : 'Novo usuário';
  document.getElementById('musr-nome').value  = ctx.nome  || '';
  const login = document.getElementById('musr-login');
  login.value = ctx.login || ''; login.readOnly = ed;
  const senha = document.getElementById('musr-senha');
  senha.value = ''; senha.placeholder = ed ? '(em branco mantém)' : '';
  document.getElementById('musr-tel').value   = ctx.telefone || '';
  document.getElementById('musr-wpp').value   = ctx.whatsapp || '';
  document.getElementById('musr-email').value = ctx.email || '';
  document.getElementById('musr-cpf').value   = ctx.cpf || '';
  if (ed && ctx.nivel) sel.value = ctx.nivel;
  document.getElementById('musr-ativo-wrap').style.display = ed ? '' : 'none';
  document.getElementById('musr-ativo').checked = ctx.ativo !== false;
  const ehProprio = ed && _usuarioAtual && ctx.id === _usuarioAtual.id;
  sel.disabled = ehProprio;
  document.getElementById('musr-ativo').disabled = ehProprio;
  document.getElementById('musr-self-nota').style.display = ehProprio ? '' : 'none';
  document.getElementById('modal-usuario').style.display = 'flex';
}

function abrirModalUsuarioEditar(u){
  abrirModalUsuario({ modo: 'editar', id: u.id, nome: u.nome, login: u.login,
    telefone: u.telefone, whatsapp: u.whatsapp, email: u.email, cpf: u.cpf,
    nivel: u.nivel, ativo: u.ativo, ..._escopoDeUsuario(u), onSaved: adminUsuariosCarregar });
}

function fecharModalUsuario(){
  document.getElementById('modal-usuario').style.display = 'none';
  _modalUserCtx = null;
}

async function salvarModalUsuario(){
  const ctx = _modalUserCtx; if (!ctx) return;
  const v = id => (document.getElementById(id).value || '').trim();
  const payload = {
    nome: v('musr-nome'), login: v('musr-login'),
    telefone: v('musr-tel'), whatsapp: v('musr-wpp'),
    email: v('musr-email'), cpf: v('musr-cpf'),
    nivel: document.getElementById('musr-perfil').value,
  };
  const senha = document.getElementById('musr-senha').value;
  if (senha) payload.senha = senha;
  let url, method;
  if (ctx.modo === 'editar'){
    url = '/api/admin/usuarios/' + ctx.id; method = 'PATCH';
    payload.ativo = document.getElementById('musr-ativo').checked;
  } else {
    url = '/api/admin/usuarios'; method = 'POST';
    if (ctx.loja_id) payload.loja_id = ctx.loja_id;
    if (ctx.rede_id) payload.rede_id = ctx.rede_id;
  }
  const r = await fetch(url, { method, credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  const d = await r.json();
  if (!d.ok){ await avisoPopup(d.erro || 'Erro', { titulo: 'Usuários' }); return; }
  showToast(ctx.modo === 'editar' ? 'Usuário atualizado.' : 'Usuário criado.', false);
  fecharModalUsuario();
  if (ctx.onSaved) ctx.onSaved();
}
```

- [ ] **Step 3: Repontar o botão "+ Novo usuário" do Nível 3**

Em `adminRenderLoja` (linha 6368), trocar `onclick="adminUsuariosNovo()"` por:

```html
      <button class="btn btn-ghost btn-sm" onclick="abrirModalUsuario({modo:'novo', escopo:'loja', loja_id:(_adminNav.loja&&_adminNav.loja.id)||(_usuarioAtual&&_usuarioAtual.loja_id), onSaved:adminUsuariosCarregar})" style="font-size:11px">+ Novo usuário</button>
```

- [ ] **Step 4: Repontar o botão "Editar" da lista**

Em `adminUsuariosCarregar` (linha 6470-6471), trocar o botão Editar por (passando o objeto inteiro `u`, que agora traz contato):

```javascript
              <button class="btn btn-ghost btn-sm" style="font-size:10px"
                onclick='abrirModalUsuarioEditar(${JSON.stringify(u)})'>Editar</button>
```

- [ ] **Step 5: Verificação manual no navegador**

Run: `python main.py` (servidor sobe na porta configurada).
Passos:
1. Login como Diretor (ex.: `pdm2026`), ir à página Admin (page-07), nível Loja → aba "Usuários da loja".
2. Clicar "+ Novo usuário": o modal abre; o `<select>` Perfil lista perfis operacionais **sem** super_admin/admin_rede.
3. Criar um usuário com e-mail/whatsapp/cpf; confirmar toast e que ele aparece na lista.
4. Clicar "Editar" nele: login somente-leitura, campos pré-preenchidos, senha em branco; salvar.
5. Editar o **próprio** usuário logado: Perfil e Ativo desabilitados, com a nota visível.
Expected: todos os passos OK; sem `prompt()` em momento algum.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(ui): modal de cadastro/edicao de usuario no Nivel 3 (substitui prompts)"
```

---

### Task 9: Frontend — seções de usuários nos Níveis 1 (Plataforma) e 2 (Rede)

**Files:**
- Modify: `static/index.html` — `adminRenderPlataforma` (~6281) e `adminRenderRede` (~6326)

**Interfaces:**
- Consumes: `abrirModalUsuario`, `adminRender`, endpoints das Tasks 4-7, `_usuarioAtual`, `_adminNav`.
- Produces: tabela "Gestores gerais" no Nível 1 (só super_admin) e "Administradores da rede" no Nível 2 (super_admin e admin_rede).

> Verificação manual (sem harness JS).

- [ ] **Step 1: Adicionar a seção "Gestores gerais" ao Nível 1**

Em `adminRenderPlataforma`, ao final do template (antes de fechar a última crase, após o card "Lojas avulsas"), acrescentar — só para super_admin:

```javascript
  if (_usuarioAtual && _usuarioAtual.pode_gerir_redes) {
    const g = await fetch('/api/admin/usuarios?escopo=plataforma', {credentials:'same-origin'})
      .then(r=>r.json()).catch(()=>({usuarios:[]}));
    box.insertAdjacentHTML('beforeend', `
      <div class="card" style="padding:14px 16px">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
          <strong style="color:var(--dalm-gold,#c8a84b)">👤 Gestores gerais</strong>
          <button class="btn btn-ghost btn-sm" style="font-size:11px"
            onclick="abrirModalUsuario({modo:'novo', escopo:'plataforma', onSaved:adminRender})">+ Novo gestor</button>
        </div>
        <table class="cli-table"><thead><tr><th>Nome</th><th>Login</th><th></th></tr></thead><tbody>
        ${(g.usuarios||[]).map(u=>`<tr>
          <td>${esc(u.nome)}</td><td style="color:var(--muted)">${esc(u.login)}</td>
          <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
            onclick='abrirModalUsuarioEditar(${JSON.stringify(u)})'>Editar</button></td></tr>`).join('')
          || '<tr><td colspan="3" style="color:var(--muted)">Nenhum gestor geral.</td></tr>'}
        </tbody></table>
      </div>`);
  }
```

> Nota: trocar o `onSaved` do gestor para um reload do Nível 1. Como `abrirModalUsuarioEditar` fixa `onSaved: adminUsuariosCarregar`, no Nível 1/2 reabrir via `adminRender` é aceitável; o reload acontece ao navegar. Para refletir na hora, no Step 3 ajustamos `abrirModalUsuarioEditar` a aceitar `onSaved` opcional.

- [ ] **Step 2: Adicionar a seção "Administradores da rede" ao Nível 2**

Em `adminRenderRede`, após o card "Lojas da rede", acrescentar — para super_admin e admin_rede:

```javascript
  const podeAdmins = _usuarioAtual && (_usuarioAtual.pode_gerir_redes
    || (_usuarioAtual.nivel === 'admin_rede'));
  if (podeAdmins) {
    const a = await fetch('/api/admin/usuarios?escopo=rede&rede_id='+rid, {credentials:'same-origin'})
      .then(r=>r.json()).catch(()=>({usuarios:[]}));
    box.insertAdjacentHTML('beforeend', `
      <div class="card" style="padding:14px 16px">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
          <strong style="color:var(--dalm-gold,#c8a84b)">👤 Administradores da rede</strong>
          <button class="btn btn-ghost btn-sm" style="font-size:11px"
            onclick="abrirModalUsuario({modo:'novo', escopo:'rede', rede_id:${rid}, onSaved:adminRender})">+ Novo administrador</button>
        </div>
        <table class="cli-table"><thead><tr><th>Nome</th><th>Login</th><th></th></tr></thead><tbody>
        ${(a.usuarios||[]).map(u=>`<tr>
          <td>${esc(u.nome)}</td><td style="color:var(--muted)">${esc(u.login)}</td>
          <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
            onclick='abrirModalUsuarioEditar(${JSON.stringify(u)})'>Editar</button></td></tr>`).join('')
          || '<tr><td colspan="3" style="color:var(--muted)">Nenhum administrador.</td></tr>'}
        </tbody></table>
      </div>`);
  }
```

- [ ] **Step 3: Permitir `onSaved` customizado em `abrirModalUsuarioEditar`**

Em `static/index.html`, ajustar a assinatura para receber um `onSaved` opcional (default = `adminUsuariosCarregar`) e repassar nos botões Editar dos Níveis 1/2 com `adminRender`:

```javascript
function abrirModalUsuarioEditar(u, onSaved){
  abrirModalUsuario({ modo: 'editar', id: u.id, nome: u.nome, login: u.login,
    telefone: u.telefone, whatsapp: u.whatsapp, email: u.email, cpf: u.cpf,
    nivel: u.nivel, ativo: u.ativo, ..._escopoDeUsuario(u),
    onSaved: onSaved || adminUsuariosCarregar });
}
```

Nos templates dos Steps 1 e 2, trocar `abrirModalUsuarioEditar(${JSON.stringify(u)})` por
`abrirModalUsuarioEditar(${JSON.stringify(u)}, adminRender)`.

- [ ] **Step 4: Verificação manual no navegador**

Run: `python main.py`
Passos:
1. Login como super_admin (`sad2026`): Nível 1 mostra "Gestores gerais"; criar/editar um super_admin funciona.
2. Entrar numa rede (Nível 2): mostra "Administradores da rede"; criar um admin_rede funciona.
3. Login como admin_rede: aterrissa na própria rede, vê "Administradores da rede", cria um par; **não** vê "Gestores gerais" (não navega ao Nível 1).
4. Diretor: Nível 2/1 não exibem essas seções (ou não são alcançáveis).
Expected: cada perfil só vê e cria o que lhe cabe.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(ui): secoes de usuarios nos Niveis Plataforma e Rede"
```

---

### Task 10: Documentação — `docs/USUARIOS.md`

**Files:**
- Modify: `docs/USUARIOS.md` (seção "Gestão de usuários" e perfis administrativos de tenancy)

- [ ] **Step 1: Atualizar a doc**

Em `docs/USUARIOS.md`, na seção "Gestão de usuários", acrescentar:

```markdown
- Cadastro/edição via **modal** (não há mais `prompt()`): campos nome, login, senha,
  telefone, WhatsApp, e-mail, CPF e perfil. O `<select>` de perfil é populado pelo
  endpoint `GET /api/admin/usuarios/perfis-permitidos` (fonte: `perfis.py` + `mod_tenancy`).
- **Níveis do console:** usuários de loja no Nível 3 ("Usuários da loja"); administradores
  de rede no Nível 2 ("Administradores da rede"); gestores gerais (super_admin) no Nível 1
  ("Gestores gerais").
- **admin_rede gere seus pares:** um Administrador de Rede pode criar/editar outros
  admin_rede **da própria rede** (não cria super_admin).
- **Anti-lockout:** ninguém rebaixa o próprio perfil nem se inativa pelo modal.
```

E na tabela de "Perfis administrativos de tenancy", ajustar a coluna "Gere" do `admin_rede`
para incluir "outros admin_rede da própria rede".

- [ ] **Step 2: Rodar a suíte completa uma última vez**

Run: `python -m pytest -q`
Expected: PASS (toda a suíte verde).

- [ ] **Step 3: Commit**

```bash
git add docs/USUARIOS.md
git commit -m "docs(usuarios): modal de cadastro, niveis do console e auto-gestao admin_rede"
```

---

## Self-Review (autor)

**Cobertura do spec:**
- Migração `email/cpf/whatsapp` → Task 1. ✔
- `perfis_atribuiveis` + afrouxar `atribuir_tenant_usuario` → Task 2. ✔
- Validação de e-mail/CPF → Task 3. ✔
- Endpoint `perfis-permitidos` → Task 4. ✔
- `GET` com filtros + contato → Task 5. ✔
- `POST` grava contato + admin_rede par → Task 6. ✔
- `PATCH` contato + escalonamento + anti-lockout → Task 7. ✔
- Modal `modalUsuario` + wiring Nível 3 → Task 8. ✔
- Seções Níveis 1 e 2 → Task 9. ✔
- Doc → Task 10. ✔

**Consistência de tipos/nomes:** `perfis_atribuiveis(ator, escopo)`, `abrirModalUsuario(ctx)`,
`abrirModalUsuarioEditar(u, onSaved)`, `_escopoDeUsuario(u)`, ids `musr-*` — usados de forma
consistente entre as tasks.

**Observação de teste:** as Tasks 8 e 9 não têm teste automatizado porque o repo não possui
harness de JS; são verificadas manualmente. Toda a lógica de permissão correspondente está
coberta por testes (Tasks 2, 4-7).
