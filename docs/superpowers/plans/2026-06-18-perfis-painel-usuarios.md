# Perfis + Painel Admin de Usuários (Sub-projeto 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estabelecer os 10 perfis oficiais com permissões centralizadas, criar o CRUD de usuários no painel admin (gate Diretor/Ger.Adm-Fin) e a documentação de perfis/usuários.

**Architecture:** Um módulo `perfis.py` vira a fonte única das permissões; `database.py`/`auth.py`/`main.py` passam a consultá-lo. Validações de usuário ficam em `mod_usuarios.py` (funções puras, testáveis no estilo do projeto); os handlers HTTP em `main.py` fazem a escrita no banco. Migração idempotente renomeia os níveis antigos.

**Tech Stack:** Python (stdlib http.server, SQLAlchemy/sqlite3, pytest); HTML/JS vanilla + verificação Playwright.

---

## File Structure

- **Criar** `perfis.py` — `PERFIS` (matriz) + helpers (`rotulo`, `desconto_max`, `pode`, `existe`, `slugs`).
- **Criar** `mod_usuarios.py` — validadores puros (`validar_novo_usuario`, `validar_edicao_usuario`).
- **Criar** `docs/USUARIOS.md` — documentação dos perfis.
- **Modificar** `database.py` — `Usuario.limite_desconto`/`pode_ver_parametros` delegam a `perfis`; migração `perfis_v2` em `_run_migracoes`.
- **Modificar** `auth.py` — `_usuario_dict` inclui `rotulo` e `pode_gerir_usuarios`.
- **Modificar** `main.py` — gates de admin/autorizar via `perfis`; endpoints CRUD de usuários.
- **Modificar** `seed.py` — renomeia `gerente`→`gerente_vendas`; um usuário-exemplo por perfil.
- **Modificar** `static/index.html` — seção "Usuários" no painel admin; gate do `nav-07`; remover `_LIMITES_NIVEL` hardcode.

> Backend = TDD (pytest, funções puras). Frontend e endpoints de escrita = implementar → verificar com Playwright (dados reais). Rodar `python -m pytest -q` ao fim de cada tarefa de backend.

---

## Task 1: `perfis.py` — fonte única de perfis

**Files:**
- Create: `perfis.py`
- Test: `tests/test_perfis.py`

- [ ] **Step 1: Escrever os testes (TDD)**

Criar `tests/test_perfis.py`:

```python
import perfis


def test_slugs_sao_os_dez_perfis():
    esperado = {
        "diretor", "gerente_vendas", "consultor", "gerente_adm_fin",
        "assistente_logistico", "conferente", "supervisor_montagem",
        "assistente_administrativo", "projetista_executivo", "medidor",
    }
    assert set(perfis.slugs()) == esperado


def test_desconto_max():
    assert perfis.desconto_max("diretor") == 50.0
    assert perfis.desconto_max("gerente_vendas") == 20.0
    assert perfis.desconto_max("consultor") == 10.0
    assert perfis.desconto_max("medidor") == 0.0
    assert perfis.desconto_max("gerente_adm_fin") == 0.0
    assert perfis.desconto_max("inexistente") == 0.0      # default seguro


def test_capacidades():
    assert perfis.pode("diretor", "gerir_usuarios") is True
    assert perfis.pode("gerente_adm_fin", "gerir_usuarios") is True
    assert perfis.pode("gerente_vendas", "gerir_usuarios") is False
    assert perfis.pode("diretor", "autorizar") is True
    assert perfis.pode("gerente_vendas", "autorizar") is True
    assert perfis.pode("gerente_adm_fin", "autorizar") is False
    assert perfis.pode("consultor", "autorizar") is False
    assert perfis.pode("gerente_adm_fin", "ver_parametros") is True
    assert perfis.pode("consultor", "ver_parametros") is False
    assert perfis.pode("inexistente", "gerir_usuarios") is False   # default seguro


def test_rotulo_e_existe():
    assert perfis.rotulo("gerente_adm_fin") == "Gerente Administrativo/Financeiro"
    assert perfis.existe("medidor") is True
    assert perfis.existe("admin") is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_perfis.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'perfis'`).

- [ ] **Step 3: Implementar `perfis.py`**

```python
"""perfis.py — Fonte única dos perfis de usuário e suas permissões.

Ao adicionar/alterar um perfil, atualize TAMBÉM docs/USUARIOS.md.
"""

PERFIS = {
    "diretor":                   {"rotulo": "Diretor",                           "desconto_max": 50.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": True},
    "gerente_vendas":            {"rotulo": "Gerente de Vendas",                 "desconto_max": 20.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": False},
    "consultor":                 {"rotulo": "Consultor",                         "desconto_max": 10.0, "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "gerente_adm_fin":           {"rotulo": "Gerente Administrativo/Financeiro", "desconto_max": 0.0,  "ver_parametros": True,  "autorizar": False, "gerir_usuarios": True},
    "assistente_logistico":      {"rotulo": "Assistente Logístico",              "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "conferente":                {"rotulo": "Conferente",                        "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "supervisor_montagem":       {"rotulo": "Supervisor de Montagem",            "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "assistente_administrativo": {"rotulo": "Assistente Administrativo",         "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "projetista_executivo":      {"rotulo": "Projetista Executivo",             "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
    "medidor":                   {"rotulo": "Medidor",                           "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": False},
}

_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False}


def existe(slug):
    return slug in PERFIS


def slugs():
    return list(PERFIS.keys())


def rotulo(slug):
    return PERFIS.get(slug, _DEFAULT)["rotulo"]


def desconto_max(slug):
    return PERFIS.get(slug, _DEFAULT)["desconto_max"]


def pode(slug, capacidade):
    return bool(PERFIS.get(slug, _DEFAULT).get(capacidade, False))
```

- [ ] **Step 4: Rodar testes**

Run: `python -m pytest tests/test_perfis.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add perfis.py tests/test_perfis.py
git commit -m "feat(perfis): modulo central de perfis e permissoes (10 perfis)"
```

---

## Task 2: `database.py` — delegar a `perfis` + migração de níveis

**Files:**
- Modify: `database.py` (`Usuario.limite_desconto`, `Usuario.pode_ver_parametros`, `_run_migracoes`)
- Test: `tests/test_perfis.py` (acrescentar) e `tests/test_migracao_perfis.py` (novo)

- [ ] **Step 1: Escrever os testes (TDD)**

Criar `tests/test_migracao_perfis.py`:

```python
import sqlite3
import database


def _conn_com_usuarios(niveis):
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT)")
    for i, nv in enumerate(niveis, start=1):
        cur.execute("INSERT INTO usuarios(id, nivel) VALUES (?,?)", (i, nv))
    conn.commit()
    return conn


def test_migracao_renomeia_niveis_antigos():
    conn = _conn_com_usuarios(["gerente", "admin", "diretor", "consultor"])
    database._run_migracoes(conn)
    niveis = [r[0] for r in conn.execute("SELECT nivel FROM usuarios ORDER BY id")]
    assert niveis == ["gerente_vendas", "diretor", "diretor", "consultor"]


def test_migracao_perfis_idempotente():
    conn = _conn_com_usuarios(["gerente"])
    database._run_migracoes(conn)
    database._run_migracoes(conn)   # 2ª vez não deve quebrar nem re-alterar
    niveis = [r[0] for r in conn.execute("SELECT nivel FROM usuarios ORDER BY id")]
    assert niveis == ["gerente_vendas"]
```

Adicionar a `tests/test_perfis.py`:

```python
def test_usuario_limite_desconto_delega_perfis():
    from database import Usuario
    assert Usuario(nome="X", login="x", nivel="gerente_vendas").limite_desconto == 20.0
    assert Usuario(nome="X", login="x", nivel="medidor").limite_desconto == 0.0
    assert Usuario(nome="X", login="x", nivel="diretor").pode_ver_parametros is True
    assert Usuario(nome="X", login="x", nivel="consultor").pode_ver_parametros is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_migracao_perfis.py tests/test_perfis.py::test_usuario_limite_desconto_delega_perfis -v`
Expected: FAIL (migração ainda não existe; `limite_desconto` ainda usa dict antigo sem `gerente_vendas`).

- [ ] **Step 3: Delegar `limite_desconto`/`pode_ver_parametros` a `perfis`**

Em `database.py`, adicionar `import perfis` no topo (junto aos imports). Substituir as duas properties em `Usuario`:

```python
    @property
    def limite_desconto(self) -> float:
        return perfis.desconto_max(self.nivel)

    @property
    def pode_ver_parametros(self) -> bool:
        return perfis.pode(self.nivel, "ver_parametros")
```

- [ ] **Step 4: Adicionar a migração `perfis_v2` em `_run_migracoes`**

Em `database.py`, dentro de `_run_migracoes`, antes do `conn.commit()` final, adicionar:

```python
    # 2026-06-18: 10 perfis — renomeia níveis antigos.
    if "perfis_v2_2026" not in aplicadas:
        cur.execute("UPDATE usuarios SET nivel='gerente_vendas' WHERE nivel='gerente'")
        cur.execute("UPDATE usuarios SET nivel='diretor'        WHERE nivel='admin'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfis_v2_2026')")
```

- [ ] **Step 5: Rodar testes + suíte**

Run: `python -m pytest tests/test_migracao_perfis.py tests/test_perfis.py -q`
Expected: PASS.
Run: `python -m pytest -q`
Expected: PASS (sem regressões).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_migracao_perfis.py tests/test_perfis.py
git commit -m "feat(perfis): Usuario delega a perfis.py + migracao de niveis antigos"
```

---

## Task 3: `auth.py` + `main.py` — usar `perfis` nos gates e no `/me`

**Files:**
- Modify: `auth.py` (`_usuario_dict`)
- Modify: `main.py` (gates de admin e de autorizar)
- Test: `tests/test_perfis.py` (acrescentar)

- [ ] **Step 1: Teste do `_usuario_dict` (TDD)**

Adicionar a `tests/test_perfis.py`:

```python
def test_usuario_dict_inclui_rotulo_e_gerir():
    from auth import _usuario_dict
    from database import Usuario
    d = _usuario_dict(Usuario(id=1, nome="Ana", login="ana", nivel="gerente_adm_fin"))
    assert d["rotulo"] == "Gerente Administrativo/Financeiro"
    assert d["pode_gerir_usuarios"] is True
    assert d["limite_desconto"] == 0.0
    d2 = _usuario_dict(Usuario(id=2, nome="C", login="c", nivel="consultor"))
    assert d2["pode_gerir_usuarios"] is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_perfis.py::test_usuario_dict_inclui_rotulo_e_gerir -v`
Expected: FAIL (`KeyError: 'rotulo'`).

- [ ] **Step 3: Atualizar `_usuario_dict`**

Em `auth.py`, adicionar `import perfis` no topo. No `_usuario_dict`, acrescentar duas chaves ao dict retornado:

```python
        "rotulo":              perfis.rotulo(u.nivel),
        "pode_gerir_usuarios": perfis.pode(u.nivel, "gerir_usuarios"),
```

- [ ] **Step 4: Trocar os gates em `main.py` por `perfis`**

Em `main.py`, adicionar `import perfis` no topo (junto aos imports). Substituir:
- Os 2 gates de painel admin (procurar `usuario.get("nivel") != "admin"`):
  ```python
  if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
  ```
- Os 2 checks de autorizar (procurar `autorizador.nivel not in ("gerente", "diretor", "admin")`):
  ```python
  if not perfis.pode(autorizador.nivel, "autorizar"):
  ```

- [ ] **Step 5: Rodar suíte completa**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add auth.py main.py tests/test_perfis.py
git commit -m "feat(perfis): /me expoe rotulo+gerir_usuarios; gates admin/autorizar via perfis"
```

---

## Task 4: `mod_usuarios.py` — validadores puros

**Files:**
- Create: `mod_usuarios.py`
- Test: `tests/test_usuarios.py`

- [ ] **Step 1: Escrever os testes (TDD)**

Criar `tests/test_usuarios.py`:

```python
import mod_usuarios as mu


def test_validar_novo_usuario_ok():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "12345", "nivel": "consultor"},
        logins_existentes=["pedro"])
    assert erros == []


def test_validar_novo_usuario_campos_obrigatorios():
    erros = mu.validar_novo_usuario({"nome": "", "login": "", "senha": "", "nivel": ""},
                                    logins_existentes=[])
    j = " ".join(erros).lower()
    assert "nome" in j and "login" in j and "senha" in j and "perfil" in j


def test_validar_novo_usuario_login_duplicado():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "Ana", "senha": "123", "nivel": "consultor"},
        logins_existentes=["ana"])           # case-insensitive
    assert any("login" in e.lower() and "exist" in e.lower() for e in erros)


def test_validar_novo_usuario_perfil_invalido():
    erros = mu.validar_novo_usuario(
        {"nome": "Ana", "login": "ana", "senha": "123", "nivel": "rei"},
        logins_existentes=[])
    assert any("perfil" in e.lower() for e in erros)


def test_validar_edicao_usuario():
    assert mu.validar_edicao_usuario({"nivel": "medidor"}) == []
    assert mu.validar_edicao_usuario({}) == []                 # nada a validar
    erros = mu.validar_edicao_usuario({"nivel": "rei"})
    assert any("perfil" in e.lower() for e in erros)
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `python -m pytest tests/test_usuarios.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'mod_usuarios'`).

- [ ] **Step 3: Implementar `mod_usuarios.py`**

```python
"""mod_usuarios.py — Validações (puras) para o CRUD de usuários do painel admin."""

import perfis


def validar_novo_usuario(dados, logins_existentes):
    """Retorna lista de erros (vazia se válido) para criação de usuário."""
    erros = []
    nome  = (dados.get("nome")  or "").strip()
    login = (dados.get("login") or "").strip()
    senha = (dados.get("senha") or "")
    nivel = (dados.get("nivel") or "").strip()
    if not nome:
        erros.append("Nome é obrigatório.")
    if not login:
        erros.append("Login é obrigatório.")
    if not senha:
        erros.append("Senha é obrigatória.")
    if not perfis.existe(nivel):
        erros.append("Perfil inválido.")
    existentes = {l.strip().lower() for l in (logins_existentes or [])}
    if login and login.lower() in existentes:
        erros.append("Login já existe.")
    return erros


def validar_edicao_usuario(dados):
    """Valida campos opcionais de edição (perfil, telefone, ativo, senha)."""
    erros = []
    if "nivel" in dados and not perfis.existe((dados.get("nivel") or "").strip()):
        erros.append("Perfil inválido.")
    return erros
```

- [ ] **Step 4: Rodar testes**

Run: `python -m pytest tests/test_usuarios.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_usuarios.py tests/test_usuarios.py
git commit -m "feat(usuarios): validadores puros para criacao/edicao de usuario"
```

---

## Task 5: `main.py` — endpoints CRUD de usuários

**Files:**
- Modify: `main.py` (`do_GET`, `do_POST`, `do_PATCH`)

> Verificação destes endpoints é feita via Playwright na Task 9 (estilo do projeto: handlers HTTP não têm unit test de DB).

- [ ] **Step 1: GET — listar usuários**

Em `do_GET`, junto das outras rotas `/api/admin/...`, adicionar:

```python
        elif path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                us = db.query(Usuario).order_by(Usuario.nome).all()
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "ativo": bool(u.ativo)} for u in us]})
            finally:
                db.close()
```

- [ ] **Step 2: POST — criar usuário**

Em `do_POST` (que já lê `body`), adicionar a rota:

```python
        elif path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            db  = get_session()
            try:
                logins = [u.login for u in db.query(Usuario.login).all()]
                erros  = mod_usuarios.validar_novo_usuario(req, logins)
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                            nivel=req["nivel"].strip(), telefone=(req.get("telefone") or "").strip())
                u.set_senha(req["senha"])
                db.add(u); db.commit()
                self.send_json({"ok": True, "id": u.id})
            finally:
                db.close()
```

Adicionar `import mod_usuarios` (e garantir `Usuario` importado — já está) no topo de `main.py`.

- [ ] **Step 3: PATCH — editar/desativar/resetar senha**

Em `do_PATCH` (seguir o padrão de leitura de `body` já existente lá — `length`/`rfile.read`), adicionar:

```python
        m_user = _re.match(r"^/api/admin/usuarios/(\d+)$", path)
        if m_user:
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            erros = mod_usuarios.validar_edicao_usuario(req)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)})
                return
            db = get_session()
            try:
                u = db.query(Usuario).filter_by(id=int(m_user.group(1))).first()
                if not u:
                    self.send_json({"ok": False, "erro": "Usuário não encontrado"})
                    return
                if "nivel" in req:    u.nivel    = req["nivel"].strip()
                if "telefone" in req: u.telefone = (req.get("telefone") or "").strip()
                if "ativo" in req:    u.ativo    = 1 if req["ativo"] else 0
                if req.get("senha"):  u.set_senha(req["senha"])
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return
```

> Use o mesmo mecanismo de leitura de `body`/`_re` já presente em `do_PATCH`. Se `do_PATCH` ainda não importa `_re`/`json`, eles já estão no escopo do módulo `main.py`.

- [ ] **Step 4: Sanity de import/rotas**

Run: `python -c "import main; print('main importa OK')"`
Expected: `main importa OK`.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(usuarios): endpoints CRUD /api/admin/usuarios (gate gerir_usuarios)"
```

---

## Task 6: `seed.py` — 10 usuários-exemplo

**Files:**
- Modify: `seed.py`

- [ ] **Step 1: Atualizar a lista `USUARIOS`**

Substituir a lista `USUARIOS` em `seed.py` por:

```python
USUARIOS = [
    {"nome": "Pedro da Mota",       "login": "pdm2026", "senha": "teste123", "nivel": "diretor"},
    {"nome": "Luiz da Silva",       "login": "lds2026", "senha": "teste234", "nivel": "gerente_vendas"},
    {"nome": "Marcia dos Santos",   "login": "mds2026", "senha": "teste345", "nivel": "consultor"},
    {"nome": "Gabriela Adm/Fin",    "login": "gaf2026", "senha": "teste456", "nivel": "gerente_adm_fin"},
    {"nome": "Alex Logística",       "login": "alg2026", "senha": "teste567", "nivel": "assistente_logistico"},
    {"nome": "Carla Conferente",    "login": "ccf2026", "senha": "teste678", "nivel": "conferente"},
    {"nome": "Sergio Montagem",     "login": "smt2026", "senha": "teste789", "nivel": "supervisor_montagem"},
    {"nome": "Aline Administrativo","login": "aad2026", "senha": "teste890", "nivel": "assistente_administrativo"},
    {"nome": "Paulo Projetista",    "login": "ppe2026", "senha": "teste901", "nivel": "projetista_executivo"},
    {"nome": "Marcos Medidor",      "login": "med2026", "senha": "teste012", "nivel": "medidor"},
]
```

(O laço de criação idempotente existente — pula `login` já existente — permanece inalterado.)

- [ ] **Step 2: Verificar que roda (ambiente isolado)**

Run: `python -c "import seed; print('seed importa OK'); print(len(seed.USUARIOS), 'usuarios definidos')"`
Expected: `seed importa OK` e `10 usuarios definidos`.

> Não rodar `seed.py` contra o `orizon.db` local agora (escrita em banco); a verificação real é na Task 9.

- [ ] **Step 3: Commit**

```bash
git add seed.py
git commit -m "feat(seed): usuario-exemplo por perfil (10 perfis); gerente->gerente_vendas"
```

---

## Task 7: Frontend — painel de usuários + gate + remover hardcode

**Files:**
- Modify: `static/index.html` (page-07; `carregarUsuarioAutenticado`; `_LIMITES_NIVEL` usages)

- [ ] **Step 1: Gate do nav-07 por `pode_gerir_usuarios`**

Localizar (Grep `nav-07`) a linha em `carregarUsuarioAutenticado` que faz:
```javascript
    if (_navAdmin) _navAdmin.style.display = (_usuarioAtual && _usuarioAtual.nivel === 'admin') ? '' : 'none';
```
Substituir por:
```javascript
    if (_navAdmin) _navAdmin.style.display = (_usuarioAtual && _usuarioAtual.pode_gerir_usuarios) ? '' : 'none';
```

- [ ] **Step 2: Remover o hardcode `_LIMITES_NIVEL`**

Localizar (Grep `_LIMITES_NIVEL`). Remover a linha de definição:
```javascript
const _LIMITES_NIVEL = { consultor: 10, gerente: 20, diretor: 50, admin: 50 };
```
E substituir as 2 leituras `_LIMITES_NIVEL[_usuarioAtual.nivel] || 10` (em `getLimiteDesconto`/cálculo de limite e no outro ponto) por:
```javascript
(_usuarioAtual?.limite_desconto ?? 10)
```
(O `/api/auth/me` já retorna `limite_desconto`.)

- [ ] **Step 3: Adicionar a seção "Usuários" no painel admin (page-07)**

Localizar (Grep `id="page-07"`) e, logo após o `<div class="page-title">… Painel Admin</div>`, inserir o container:

```html
    <div style="border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:18px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
        <strong style="color:var(--dalm-gold,#c8a84b)">&#x1F465; Usu&aacute;rios</strong>
        <button class="btn btn-ghost btn-sm" onclick="adminUsuariosNovo()" style="font-size:11px">+ Novo usu&aacute;rio</button>
        <button class="btn btn-ghost btn-sm" onclick="adminUsuariosCarregar()" style="font-size:11px;margin-left:auto">&#x21BA; Atualizar</button>
      </div>
      <div id="admin-usuarios-lista"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
    </div>
```

- [ ] **Step 4: JS do CRUD de usuários**

Adicionar (perto de `adminCarregar`) as funções:

```javascript
async function adminUsuariosCarregar() {
  const box = document.getElementById('admin-usuarios-lista');
  if (!box) return;
  try {
    const r = await fetch('/api/admin/usuarios', { credentials: 'same-origin' });
    const d = await r.json();
    if (!d.ok) { box.innerHTML = '<em style="color:var(--err)">' + esc(d.erro || 'Erro') + '</em>'; return; }
    box.innerHTML = `
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead><tr style="text-align:left;color:var(--muted)">
          <th style="padding:4px 6px">Nome</th><th>Login</th><th>Perfil</th><th>Ativo</th><th></th></tr></thead>
        <tbody>${d.usuarios.map(u => `
          <tr style="border-top:1px solid var(--border)">
            <td style="padding:4px 6px">${esc(u.nome)}</td>
            <td>${esc(u.login)}</td>
            <td>${esc(u.rotulo)}</td>
            <td>${u.ativo ? '✓' : '—'}</td>
            <td style="text-align:right">
              <button class="btn btn-ghost btn-sm" style="font-size:10px"
                onclick='adminUsuariosEditar(${u.id}, ${JSON.stringify(u.nivel)}, ${JSON.stringify(u.telefone)}, ${u.ativo ? 1 : 0})'>Editar</button>
            </td></tr>`).join('')}</tbody></table>`;
  } catch(e) { box.innerHTML = '<em style="color:var(--err)">Erro de rede</em>'; }
}

function _perfilOptions(sel) {
  const ops = [
    ['diretor','Diretor'],['gerente_vendas','Gerente de Vendas'],['consultor','Consultor'],
    ['gerente_adm_fin','Gerente Administrativo/Financeiro'],['assistente_logistico','Assistente Logístico'],
    ['conferente','Conferente'],['supervisor_montagem','Supervisor de Montagem'],
    ['assistente_administrativo','Assistente Administrativo'],['projetista_executivo','Projetista Executivo'],
    ['medidor','Medidor'],
  ];
  return ops.map(([v,l]) => `<option value="${v}"${v===sel?' selected':''}>${l}</option>`).join('');
}

async function adminUsuariosNovo() {
  const nome  = prompt('Nome do usuário:'); if (!nome) return;
  const login = prompt('Login:'); if (!login) return;
  const senha = prompt('Senha inicial:'); if (!senha) return;
  const nivel = prompt('Perfil (slug): diretor, gerente_vendas, consultor, gerente_adm_fin, assistente_logistico, conferente, supervisor_montagem, assistente_administrativo, projetista_executivo, medidor', 'consultor');
  if (!nivel) return;
  const telefone = prompt('Telefone (opcional):') || '';
  const r = await fetch('/api/admin/usuarios', { method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ nome, login, senha, nivel, telefone }) });
  const d = await r.json();
  if (!d.ok) { await avisoPopup(d.erro || 'Erro ao criar usuário', {titulo:'Usuários'}); return; }
  showToast('Usuário criado.', false);
  adminUsuariosCarregar();
}

async function adminUsuariosEditar(id, nivelAtual, telAtual, ativoAtual) {
  const nivel = prompt('Perfil (slug):', nivelAtual); if (nivel === null) return;
  const telefone = prompt('Telefone:', telAtual || ''); if (telefone === null) return;
  const ativo = confirm('Usuário ATIVO? (Cancelar = inativar)');
  const senha = prompt('Nova senha (deixe em branco para manter):', '') || '';
  const payload = { nivel, telefone, ativo };
  if (senha) payload.senha = senha;
  const r = await fetch('/api/admin/usuarios/' + id, { method:'PATCH', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
  const d = await r.json();
  if (!d.ok) { await avisoPopup(d.erro || 'Erro ao editar', {titulo:'Usuários'}); return; }
  showToast('Usuário atualizado.', false);
  adminUsuariosCarregar();
}
```

> NOTA: este painel reutiliza `prompt`/`confirm` por simplicidade do CRUD interno (acesso restrito a Diretor/Adm-Fin). Se quiser, num passo futuro trocamos por um modal de formulário estilizado — fora do escopo deste sub-projeto.

- [ ] **Step 5: Carregar a lista ao abrir o painel**

Localizar (Grep `if(n===7) adminCarregar();`) e adicionar a chamada da lista de usuários:
```javascript
  if(n===7){ adminCarregar(); adminUsuariosCarregar(); }
```

- [ ] **Step 6: Sanity**

Run: `python -c "h=open('static/index.html',encoding='utf-8').read(); print('adminUsuariosCarregar:', h.count('function adminUsuariosCarregar')); print('_LIMITES_NIVEL restante:', h.count('_LIMITES_NIVEL')); print('pode_gerir_usuarios gate:', 'pode_gerir_usuarios' in h)"`
Expected: `1`, `0`, `True`.

- [ ] **Step 7: Commit**

```bash
git add static/index.html
git commit -m "feat(admin): painel de usuarios (CRUD) + gate por perfil + remove hardcode de limites"
```

---

## Task 8: Documentação — `docs/USUARIOS.md`

**Files:**
- Create: `docs/USUARIOS.md`

- [ ] **Step 1: Criar o documento**

Criar `docs/USUARIOS.md`:

```markdown
# Perfis de Usuário — Orizon Manager

> Fonte da verdade do código: `perfis.py`. Ao adicionar/alterar um perfil, atualize
> `perfis.py` **e** este documento. Usuários são criados no Painel Admin (Diretor ou
> Gerente Administrativo/Financeiro) ou via `seed.py`.

## Perfis e permissões

| Perfil | Desc. máx | Ver parâmetros | Autorizar desconto | Gerir usuários |
|---|---|---|---|---|
| Diretor | 50% | sim | sim | sim |
| Gerente de Vendas | 20% | sim | sim | não |
| Consultor | 10% | não | não | não |
| Gerente Administrativo/Financeiro | 0% | sim | não | sim |
| Assistente Logístico | 0% | não | não | não |
| Conferente | 0% | não | não | não |
| Supervisor de Montagem | 0% | não | não | não |
| Assistente Administrativo | 0% | não | não | não |
| Projetista Executivo | 0% | não | não | não |
| Medidor | 0% | não | não | não |

## Responsabilidades no ciclo (resumo)

- **Diretor / Gerente de Vendas / Consultor:** negociação, orçamento, desconto.
- **Gerente Administrativo/Financeiro:** aprovação financeira (Sub-projeto 3); gestão de usuários.
- **Medidor:** confirma/registra a medição (Sub-projeto 4).
- **Projetista Executivo:** projeto executivo e suas sub-etapas.
- **Supervisor de Montagem / Conferente / Assistente Logístico / Assistente Administrativo:** etapas operacionais do ciclo (montagem, conferência, logística, apoio administrativo).

## Gestão de usuários

- Painel Admin → seção **Usuários**: criar, editar perfil/telefone, ativar/desativar, resetar senha.
- Acesso restrito a perfis com `gerir_usuarios` (Diretor, Gerente Adm/Financeiro).
- Usuários são **desativados** (não excluídos) para preservar histórico.
```

- [ ] **Step 2: Commit**

```bash
git add docs/USUARIOS.md
git commit -m "docs: documentacao dos 10 perfis de usuario (USUARIOS.md)"
```

---

## Task 9: Verificação integrada (dados reais) + DEV_LOG

**Files:** nenhuma alteração de código; corrigir inline se algo falhar.

- [ ] **Step 1: Suíte completa**

Run: `python -m pytest -q`
Expected: PASS (todos verdes).

- [ ] **Step 2: Atualizar o banco local e seed (ambiente de teste)**

Run: `python seed.py`
Expected: cria os novos usuários-exemplo; renomeia o `gerente` antigo via migração (`lds2026` vira `gerente_vendas`). Conferir a saída.

- [ ] **Step 3: Verificação Playwright (servidor real)**

Reiniciar o servidor; logar como **Diretor** (`pdm2026`/`teste123`):
1. Abre a aba **Admin** (visível), seção **Usuários** lista os usuários com o rótulo do perfil.
2. **Novo usuário** → cria; aparece na lista.
3. **Editar** → troca perfil/telefone, reseta senha, inativa/reativa.
4. Logar como **Consultor** (`mds2026`) → a aba **Admin** **não** aparece (sem `gerir_usuarios`).
5. Logar como **Gerente Adm/Fin** (`gaf2026`) → vê o painel de usuários.
6. Confirmar via `/api/auth/me` (DevTools) que `limite_desconto`, `rotulo` e `pode_gerir_usuarios` vêm corretos.

- [ ] **Step 4: Atualizar DEV_LOG.md**

Adicionar entrada da sessão (sub-projeto 2): `perfis.py`, migração de níveis, CRUD de usuários no painel, `docs/USUARIOS.md`.

- [ ] **Step 5: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: atualiza DEV_LOG (sub-projeto 2 — perfis + painel de usuarios)"
```

---

## Self-Review (cobertura do spec)

- **Modelo central `perfis.py` (10 perfis, matriz)** → Task 1. ✓
- **`database.py` delega + migração de níveis** → Task 2. ✓
- **`/me` expõe rótulo/gerir; gates admin/autorizar via perfis** → Task 3. ✓
- **Validadores de usuário** → Task 4; **endpoints CRUD** → Task 5. ✓
- **seed (10 perfis; gerente→gerente_vendas)** → Task 6. ✓
- **Painel de usuários + gate + remover hardcode frontend** → Task 7. ✓
- **Documentação `docs/USUARIOS.md` + lista viva no painel** → Task 8 (+ Task 7). ✓
- **Verificação pytest + Playwright** → Task 9. ✓
- **Consistência de nomes:** `perfis.pode/desconto_max/rotulo/existe/slugs`, `pode_gerir_usuarios`, `validar_novo_usuario`/`validar_edicao_usuario`, `/api/admin/usuarios`, `adminUsuariosCarregar/Novo/Editar` — idênticos entre tarefas.
- **Sem placeholders.** Premissas do spec (autorizar = diretor+gerente_vendas; ver_parametros inclui adm_fin) refletidas na matriz de `perfis.py`.
