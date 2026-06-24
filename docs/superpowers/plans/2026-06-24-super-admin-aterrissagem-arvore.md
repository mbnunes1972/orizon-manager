# Aterrissagem por papel + árvore estrutural do super_admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer super_admin/admin_rede aterrissarem no Painel Admin e estender a árvore de drill até `projeto → etapas do ciclo`, com dados estruturais sem PII.

**Architecture:** Lógica nova num módulo `mod_arvore.py` (recebe a session + o `ator`, devolve dicts — testável sem HTTP); `main.py` ganha 2 rotas GET finas que traduzem `PermissionError→403` e `LookupError→404`; o frontend (`static/index.html`) roteia a aterrissagem por papel, esconde o menu operacional do super_admin e adiciona o nível 4 da árvore.

**Tech Stack:** Python 3 (`python3` no WSL), SQLAlchemy + SQLite, `http.server` (classe `main.Handler`), frontend SPA vanilla em arquivo único, testes com `pytest` (frontend é verificação manual).

## Global Constraints

- Rodar Python/pytest com `python3`/`python3 -m pytest` (não `python`) — ambiente WSL.
- **Sem PII na árvore:** as funções de `mod_arvore` só montam as chaves listadas neste plano — nunca `cliente_id`/cpf/contato/endereço, nunca `parametros_json`, nunca valores de orçamento, nunca `responsavel_id`/`observacoes`.
- Autorização das rotas novas: sessão com capacidade `gerir_redes` **OU** `gerir_lojas` (exclui papéis operacionais, que recebem 403). Usar `perfis.pode(nivel, "gerir_redes")` / `perfis.pode(nivel, "gerir_lojas")`.
- Escopo validado via `mod_tenancy.pode_ver_loja(ator, {"id", "rede_id"})` — super_admin vê qualquer loja; admin_rede só lojas da própria rede.
- Frontend sem teste JS automatizado (memória do projeto): cada tarefa de frontend termina com verificação manual + commit.
- Seguir o padrão dos `mod_*` (núcleo reutilizável) e manter as rotas em `main.py` como cola fina.

---

### Task 1: `mod_arvore.projetos_estruturais` (módulo + testes puros)

**Files:**
- Create: `mod_arvore.py`
- Test: `tests/test_arvore.py`

**Interfaces:**
- Consumes: `mod_tenancy.pode_ver_loja(ator, loja_dict)`; `mod_ciclo.ETAPAS_PRINCIPAIS`, `mod_ciclo.ETAPA_NOME`, `mod_ciclo.STATUS_CONCLUSIVOS`; modelos `database.Loja`, `database.Projeto`, `database.CicloEtapa`.
- Produces: `projetos_estruturais(db, ator, loja_id) -> list[dict]` onde cada dict tem exatamente as chaves `{"nome_safe", "status", "etapa_atual_codigo", "etapa_atual_nome", "total_etapas", "etapas_concluidas"}`. Levanta `LookupError` se a loja não existe e `PermissionError` se fora do escopo do ator. Também define o helper `_loja_no_escopo(db, ator, loja_id) -> Loja`.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_arvore.py`:

```python
import pytest
from datetime import datetime

import mod_arvore


@pytest.fixture
def ator_super():
    return {"nivel": "super_admin", "loja_id": None, "rede_id": None}


@pytest.fixture(scope="module")
def rede_id(app_db, seed):
    db = app_db.get_session()
    try:
        return db.get(app_db.Loja, seed["loja1_id"]).rede_id
    finally:
        db.close()


@pytest.fixture(scope="module")
def com_etapas(app_db, seed):
    """Proj_L1 ganha etapas 1,2,3 concluídas e 4 pendente (etapa atual = 4)."""
    from database import CicloEtapa
    db = app_db.get_session()
    try:
        db.add_all([
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                       status="concluido", concluido_em=datetime(2026, 1, 1)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="2",
                       status="concluido", concluido_em=datetime(2026, 1, 2)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="3",
                       status="concluido", concluido_em=datetime(2026, 1, 3)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="4",
                       status="pendente"),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def test_super_ve_projetos_com_agregacao(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator_super, seed["loja1_id"])
    finally:
        db.close()
    p = next(x for x in out if x["nome_safe"] == "Proj_L1")
    assert p["etapas_concluidas"] == 3
    assert p["etapa_atual_codigo"] == "4"
    assert p["etapa_atual_nome"] == "Primeiro orçamento"
    assert p["total_etapas"] == 20


def test_projetos_sem_pii(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator_super, seed["loja1_id"])
    finally:
        db.close()
    assert out, "esperava ao menos um projeto"
    assert set(out[0].keys()) == {
        "nome_safe", "status", "etapa_atual_codigo",
        "etapa_atual_nome", "total_etapas", "etapas_concluidas"}


def test_admin_rede_ve_loja_da_propria_rede(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id}
    db = app_db.get_session()
    try:
        out = mod_arvore.projetos_estruturais(db, ator, seed["loja1_id"])
    finally:
        db.close()
    assert any(x["nome_safe"] == "Proj_L1" for x in out)


def test_loja_inexistente_levanta_lookuperror(app_db, ator_super):
    db = app_db.get_session()
    try:
        with pytest.raises(LookupError):
            mod_arvore.projetos_estruturais(db, ator_super, 999999)
    finally:
        db.close()


def test_fora_de_escopo_levanta_permissionerror(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id + 999}
    db = app_db.get_session()
    try:
        with pytest.raises(PermissionError):
            mod_arvore.projetos_estruturais(db, ator, seed["loja1_id"])
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_arvore.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'mod_arvore'` (ou `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

Criar `mod_arvore.py`:

```python
# -*- coding: utf-8 -*-
"""mod_arvore.py — Visão estrutural (árvore) para papéis administrativos.

Leitura SEM PII: recebe (db, ator, ...) e devolve listas de dicts com
estrutura/indicadores (nunca cliente/cpf/contato/valores). Escopo validado via
mod_tenancy.pode_ver_loja. Erros viram exceções que a rota traduz em HTTP:
  PermissionError -> 403   |   LookupError -> 404
"""

import mod_ciclo
import mod_tenancy
from database import Loja, Projeto, CicloEtapa


def _loja_no_escopo(db, ator, loja_id):
    loja = db.get(Loja, loja_id)
    if loja is None:
        raise LookupError("Loja não encontrada.")
    if not mod_tenancy.pode_ver_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
        raise PermissionError("Sem acesso a esta loja.")
    return loja


def projetos_estruturais(db, ator, loja_id):
    """Lista estrutural dos projetos de uma loja (sem PII)."""
    _loja_no_escopo(db, ator, loja_id)
    projetos = (db.query(Projeto)
                  .filter(Projeto.loja_id == loja_id)
                  .order_by(Projeto.nome_safe)
                  .all())
    nomes = [p.nome_safe for p in projetos]
    etapas = (db.query(CicloEtapa)
                .filter(CicloEtapa.projeto_nome.in_(nomes)).all()) if nomes else []
    status_por_projeto = {}
    for e in etapas:
        status_por_projeto.setdefault(e.projeto_nome, {})[e.etapa_codigo] = e.status

    out = []
    for p in projetos:
        por_codigo = status_por_projeto.get(p.nome_safe, {})
        concluidas = sum(
            1 for cod in mod_ciclo.ETAPAS_PRINCIPAIS
            if por_codigo.get(cod) in mod_ciclo.STATUS_CONCLUSIVOS)
        atual = next(
            (cod for cod in mod_ciclo.ETAPAS_PRINCIPAIS
             if por_codigo.get(cod) not in mod_ciclo.STATUS_CONCLUSIVOS), None)
        out.append({
            "nome_safe": p.nome_safe,
            "status": p.status,
            "etapa_atual_codigo": atual,
            "etapa_atual_nome": mod_ciclo.ETAPA_NOME.get(atual) if atual else None,
            "total_etapas": len(mod_ciclo.ETAPAS_PRINCIPAIS),
            "etapas_concluidas": concluidas,
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_arvore.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_arvore.py tests/test_arvore.py
git commit -m "feat(arvore): projetos_estruturais (sem PII, escopo por tenancy)"
```

---

### Task 2: `mod_arvore.etapas_do_projeto` (módulo + testes puros)

**Files:**
- Modify: `mod_arvore.py`
- Test: `tests/test_arvore.py`

**Interfaces:**
- Consumes: o que a Task 1 já importa; `mod_ciclo.chave_ordenacao(codigo)` para ordenar etapas.
- Produces: `etapas_do_projeto(db, ator, nome_safe) -> list[dict]` onde cada dict tem exatamente `{"etapa_codigo", "etapa_nome", "status", "concluido_em"}` (este último ISO-string ou `None`). `LookupError` se o projeto não existe; `PermissionError` se fora do escopo.

- [ ] **Step 1: Write the failing test**

Acrescentar ao final de `tests/test_arvore.py`:

```python
def test_etapas_super_ordenadas_com_nome(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.etapas_do_projeto(db, ator_super, "Proj_L1")
    finally:
        db.close()
    assert [e["etapa_codigo"] for e in out] == ["1", "2", "3", "4"]
    assert out[0]["etapa_nome"] == "Cadastro do Cliente"
    assert out[3]["status"] == "pendente"
    assert out[0]["concluido_em"].startswith("2026-01-01")


def test_etapas_sem_pii(app_db, seed, com_etapas, ator_super):
    db = app_db.get_session()
    try:
        out = mod_arvore.etapas_do_projeto(db, ator_super, "Proj_L1")
    finally:
        db.close()
    assert out, "esperava etapas"
    assert set(out[0].keys()) == {"etapa_codigo", "etapa_nome", "status", "concluido_em"}


def test_etapas_projeto_inexistente(app_db, ator_super):
    db = app_db.get_session()
    try:
        with pytest.raises(LookupError):
            mod_arvore.etapas_do_projeto(db, ator_super, "NaoExiste")
    finally:
        db.close()


def test_etapas_fora_de_escopo(app_db, seed, rede_id):
    ator = {"nivel": "admin_rede", "loja_id": None, "rede_id": rede_id + 999}
    db = app_db.get_session()
    try:
        with pytest.raises(PermissionError):
            mod_arvore.etapas_do_projeto(db, ator, "Proj_L1")
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_arvore.py::test_etapas_super_ordenadas_com_nome -v`
Expected: FAIL com `AttributeError: module 'mod_arvore' has no attribute 'etapas_do_projeto'`.

- [ ] **Step 3: Write minimal implementation**

Acrescentar ao final de `mod_arvore.py`:

```python
def etapas_do_projeto(db, ator, nome_safe):
    """Etapas do ciclo de um projeto (sem PII)."""
    proj = db.get(Projeto, nome_safe)
    if proj is None:
        raise LookupError("Projeto não encontrado.")
    loja = db.get(Loja, proj.loja_id) if proj.loja_id is not None else None
    rede_id = loja.rede_id if loja is not None else None
    if not mod_tenancy.pode_ver_loja(ator, {"id": proj.loja_id, "rede_id": rede_id}):
        raise PermissionError("Sem acesso a este projeto.")
    etapas = (db.query(CicloEtapa)
                .filter(CicloEtapa.projeto_nome == nome_safe).all())
    etapas.sort(key=lambda e: mod_ciclo.chave_ordenacao(e.etapa_codigo))
    return [{
        "etapa_codigo": e.etapa_codigo,
        "etapa_nome": mod_ciclo.ETAPA_NOME.get(e.etapa_codigo, e.etapa_codigo),
        "status": e.status,
        "concluido_em": e.concluido_em.isoformat() if e.concluido_em else None,
    } for e in etapas]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_arvore.py -v`
Expected: PASS (9 testes no total).

- [ ] **Step 5: Commit**

```bash
git add mod_arvore.py tests/test_arvore.py
git commit -m "feat(arvore): etapas_do_projeto (ordenadas, sem PII)"
```

---

### Task 3: Rotas GET em `main.py` + testes HTTP e2e

**Files:**
- Modify: `main.py` (import perto da linha 49; 2 `elif` novos em `do_GET`, logo após o bloco `elif path == "/api/admin/lojas":` que termina ~linha 613, antes de `elif path.endswith(".html")`)
- Test: `tests/test_arvore_e2e.py`

**Interfaces:**
- Consumes: `mod_arvore.projetos_estruturais`, `mod_arvore.etapas_do_projeto`; helpers existentes `get_usuario_sessao(self)`, `_ator_dict(db, usuario)`, `self.send_json(data, code)`; fixtures de teste `servidor`, `http_client_factory`, `seed`.
- Produces: `GET /api/admin/lojas/<id>/projetos` → `{"ok": true, "projetos": [...]}`; `GET /api/admin/projetos/<nome_safe>/etapas` → `{"ok": true, "etapas": [...]}`. Erros: 401 sem sessão, 403 sem capacidade/fora de escopo, 404 inexistente.

- [ ] **Step 1: Write the failing test**

Criar `tests/test_arvore_e2e.py`:

```python
import pytest
from datetime import datetime


@pytest.fixture(scope="module")
def com_etapas_http(app_db, seed):
    from database import CicloEtapa
    db = app_db.get_session()
    try:
        db.add_all([
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="1",
                       status="concluido", concluido_em=datetime(2026, 1, 1)),
            CicloEtapa(projeto_nome=seed["projeto_l1"], etapa_codigo="2",
                       status="pendente"),
        ])
        db.commit()
    finally:
        db.close()
    return seed


def test_super_lista_projetos_da_loja(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, body = c.get("/api/admin/lojas/%d/projetos" % seed["loja1_id"])
    assert st == 200
    assert body["ok"] is True
    assert any(p["nome_safe"] == "Proj_L1" for p in body["projetos"])


def test_super_lista_etapas_do_projeto(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, body = c.get("/api/admin/projetos/Proj_L1/etapas")
    assert st == 200
    assert body["ok"] is True
    assert [e["etapa_codigo"] for e in body["etapas"]] == ["1", "2"]


def test_operacional_recebe_403(http_client_factory, seed, com_etapas_http):
    c = http_client_factory()
    c.login("dir_l1", "senha123")
    st, _ = c.get("/api/admin/lojas/%d/projetos" % seed["loja1_id"])
    assert st == 403


def test_loja_inexistente_404(http_client_factory, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, _ = c.get("/api/admin/lojas/999999/projetos")
    assert st == 404


def test_projeto_inexistente_404(http_client_factory, com_etapas_http):
    c = http_client_factory()
    c.login("super", "senha123")
    st, _ = c.get("/api/admin/projetos/NaoExiste/etapas")
    assert st == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_arvore_e2e.py -v`
Expected: FAIL — as rotas ainda não existem (provável 404 com corpo de outra rota, ou `KeyError`/`TypeError` ao acessar `body["ok"]`).

- [ ] **Step 3: Write minimal implementation**

3a. Adicionar o import perto da linha 49 de `main.py` (junto dos outros `import mod_*`):

```python
import mod_arvore
```

3b. Inserir os dois `elif` logo após o bloco `elif path == "/api/admin/lojas":` (após a linha que fecha com `db.close()` ~613) e antes de `elif path.endswith(".html") and path != "/":`:

```python
        elif path.startswith("/api/admin/lojas/") and path.endswith("/projetos"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            m = _re.match(r"^/api/admin/lojas/(\d+)/projetos$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                projetos = mod_arvore.projetos_estruturais(db, ator, int(m.group(1)))
                self.send_json({"ok": True, "projetos": projetos})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()

        elif path.startswith("/api/admin/projetos/") and path.endswith("/etapas"):
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_redes")
                                   or perfis.pode(usuario.get("nivel"), "gerir_lojas")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            import re as _re
            from urllib.parse import unquote
            m = _re.match(r"^/api/admin/projetos/(.+)/etapas$", path)
            if not m:
                self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                etapas = mod_arvore.etapas_do_projeto(db, ator, unquote(m.group(1)))
                self.send_json({"ok": True, "etapas": etapas})
            except PermissionError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=403)
            except LookupError as e:
                self.send_json({"ok": False, "erro": str(e)}, code=404)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_arvore_e2e.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Run the full suite (regression guard)**

Run: `python3 -m pytest -q`
Expected: tudo verde (nenhuma regressão nas rotas/admin existentes).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_arvore_e2e.py
git commit -m "feat(arvore): rotas GET /api/admin/lojas/<id>/projetos e /api/admin/projetos/<nome>/etapas"
```

---

### Task 4: Frontend — aterrissagem por papel + esconder menu operacional do super_admin

**Files:**
- Modify: `static/index.html` (função `carregarUsuarioAutenticado` ~1943-1957; nova função `_aterrissarPorPapel`)

**Interfaces:**
- Consumes: `_usuarioAtual` (`{nivel, loja_id, rede_id, pode_gerir_redes, ...}`); `goPage(7)` (já chama `adminCarregarConsole()` + `adminCarregar()`, ver `index.html:2210`); ids de menu `nav-00`/`nav-05`/`nav-06`.
- Produces: função global `_aterrissarPorPapel()` chamada ao fim do boot autenticado.

- [ ] **Step 1: Adicionar a chamada no fim do boot autenticado**

Em `carregarUsuarioAutenticado`, localizar:

```javascript
    _atualizarUIUsuario();
    _carregarDadosExtrasUsuario();
  } catch(e){ console.warn('[AUTH] Erro ao carregar usuário:', e); }
```

e substituir por:

```javascript
    _atualizarUIUsuario();
    _carregarDadosExtrasUsuario();
    _aterrissarPorPapel();
  } catch(e){ console.warn('[AUTH] Erro ao carregar usuário:', e); }
```

- [ ] **Step 2: Definir `_aterrissarPorPapel`**

Logo após a função `_atualizarUIUsuario` (ou em qualquer ponto do mesmo bloco de funções de usuário), adicionar:

```javascript
function _aterrissarPorPapel(){
  const u = _usuarioAtual || {};
  // super_admin: esconde o menu operacional (Projetos/Clientes/Parceiros)
  if (u.pode_gerir_redes && !u.loja_id) {
    ['nav-00','nav-05','nav-06'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.style.display = 'none';
    });
  }
  // super_admin e admin_rede aterrissam no Painel Admin (page 7);
  // goPage(7) já dispara adminCarregarConsole(), que aterrissa no nível certo por papel.
  if (u.pode_gerir_redes || u.nivel === 'admin_rede') {
    goPage(7);
  }
}
```

- [ ] **Step 3: Verificação manual**

```bash
python3 main.py    # subir o servidor local
```

No navegador:
- Logar como **super_admin**: deve cair no **Painel Admin (nível Plataforma)**; o menu lateral **não** mostra Projetos/Clientes/Parceiros; mostra Admin.
- Logar como **admin_rede**: deve cair no **Painel Admin (nível Rede)**; o menu **mantém** Projetos/Clientes/Parceiros.
- Logar como **operacional** (ex.: diretor): comportamento inalterado — cai em **Projetos**.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(arvore): aterrissagem por papel + esconde menu operacional do super_admin"
```

---

### Task 5: Frontend — árvore nível 4 (aba "Projetos" + etapas do projeto)

**Files:**
- Modify: `static/index.html` (`_adminNav` ~6366; `adminBreadcrumb` ~6379; `adminIrNivel` ~6386; `adminRender` ~6396; `adminRenderLoja` ~6522; `adminLojaTab` ~6538; novas funções `adminEntrarProjeto`, `adminLojaProjetosCarregar`, `adminRenderProjeto`)

**Interfaces:**
- Consumes: rotas da Task 3 (`/api/admin/lojas/<id>/projetos`, `/api/admin/projetos/<nome>/etapas`); helpers de UI existentes `esc()`, classes `cli-table`/`card`/`btn`; estado `_adminNav` e funções `adminRender`/`adminEntrarLoja`.
- Produces: nível 4 navegável `Plataforma › Rede › Loja › Projeto` com listagem de etapas (read-only).

- [ ] **Step 1: Adicionar `projeto` ao estado e ao breadcrumb**

Trocar a linha de declaração (`index.html:6366`):

```javascript
let _adminNav = { nivel: 1, rede: null, loja: null };   // rede/loja = {id, nome}
```

por:

```javascript
let _adminNav = { nivel: 1, rede: null, loja: null, projeto: null };   // rede/loja={id,nome}; projeto={nome,status}
```

Em `adminBreadcrumb`, trocar o trecho que monta o segmento da loja:

```javascript
  if (_adminNav.loja) parts.push(`<span>Loja ${esc(_adminNav.loja.nome||_adminNav.loja.id)}</span>`);
  document.getElementById('admin-breadcrumb').innerHTML = parts.join(' › ');
```

por:

```javascript
  if (_adminNav.loja) {
    const lojaTxt = `Loja ${esc(_adminNav.loja.nome||_adminNav.loja.id)}`;
    parts.push(_adminNav.projeto
      ? `<span onclick="adminIrNivel(3)" style="cursor:pointer">${lojaTxt}</span>`
      : `<span>${lojaTxt}</span>`);
  }
  if (_adminNav.projeto) parts.push(`<span>Projeto ${esc(_adminNav.projeto.nome)}</span>`);
  document.getElementById('admin-breadcrumb').innerHTML = parts.join(' › ');
```

- [ ] **Step 2: Tratar o nível 4 na navegação e no render**

Substituir `adminIrNivel` (6386-6391):

```javascript
function adminIrNivel(n){
  if (n === 1) { _adminNav.rede = null; _adminNav.loja = null; }
  if (n === 2) { _adminNav.loja = null; }
  _adminNav.nivel = n;
  adminRender();
}
```

por:

```javascript
function adminIrNivel(n){
  if (n === 1) { _adminNav.rede = null; _adminNav.loja = null; _adminNav.projeto = null; }
  if (n === 2) { _adminNav.loja = null; _adminNav.projeto = null; }
  if (n === 3) { _adminNav.projeto = null; }
  _adminNav.nivel = n;
  adminRender();
}
```

Substituir `adminRender` (6396-6402):

```javascript
function adminRender(){
  adminBreadcrumb();
  const box = document.getElementById('admin-console');
  if (_adminNav.nivel === 1)      adminRenderPlataforma(box);
  else if (_adminNav.nivel === 2) adminRenderRede(box);
  else                            adminRenderLoja(box);
}
```

por:

```javascript
function adminRender(){
  adminBreadcrumb();
  const box = document.getElementById('admin-console');
  if (_adminNav.nivel === 1)      adminRenderPlataforma(box);
  else if (_adminNav.nivel === 2) adminRenderRede(box);
  else if (_adminNav.nivel === 4) adminRenderProjeto(box);
  else                            adminRenderLoja(box);
}

function adminEntrarProjeto(nome, status){
  _adminNav.projeto = { nome, status };
  _adminNav.nivel = 4;
  adminRender();
}
```

- [ ] **Step 3: Adicionar a aba "Projetos" no nível Loja**

Substituir `adminRenderLoja` (6522-6536):

```javascript
async function adminRenderLoja(box){
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  box.innerHTML = `
    <div style="display:flex;gap:0;border-bottom:2px solid var(--dalm-gold);margin-bottom:12px">
      <button class="home-tab ativo" id="loja-tab-dados" onclick="adminLojaTab('dados')">Dados da loja</button>
      <button class="home-tab" id="loja-tab-usuarios" onclick="adminLojaTab('usuarios')">Usuários da loja</button>
    </div>
    <div id="loja-panel-dados"></div>
    <div id="loja-panel-usuarios" style="display:none">
      <button class="btn btn-ghost btn-sm" onclick="abrirModalUsuario({modo:'novo', escopo:'loja', loja_id:(_adminNav.loja&&_adminNav.loja.id)||(_usuarioAtual&&_usuarioAtual.loja_id), onSaved:adminUsuariosCarregar})" style="font-size:11px">+ Novo usuário</button>
      <div id="admin-usuarios-lista" style="margin-top:10px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
    </div>`;
  adminLojaCarregarDados(lid);
  adminUsuariosCarregar();   // popula #admin-usuarios-lista (função já existente)
}
```

por:

```javascript
async function adminRenderLoja(box){
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  box.innerHTML = `
    <div style="display:flex;gap:0;border-bottom:2px solid var(--dalm-gold);margin-bottom:12px">
      <button class="home-tab ativo" id="loja-tab-dados" onclick="adminLojaTab('dados')">Dados da loja</button>
      <button class="home-tab" id="loja-tab-usuarios" onclick="adminLojaTab('usuarios')">Usuários da loja</button>
      <button class="home-tab" id="loja-tab-projetos" onclick="adminLojaTab('projetos')">Projetos</button>
    </div>
    <div id="loja-panel-dados"></div>
    <div id="loja-panel-usuarios" style="display:none">
      <button class="btn btn-ghost btn-sm" onclick="abrirModalUsuario({modo:'novo', escopo:'loja', loja_id:(_adminNav.loja&&_adminNav.loja.id)||(_usuarioAtual&&_usuarioAtual.loja_id), onSaved:adminUsuariosCarregar})" style="font-size:11px">+ Novo usuário</button>
      <div id="admin-usuarios-lista" style="margin-top:10px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
    </div>
    <div id="loja-panel-projetos" style="display:none"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>`;
  adminLojaCarregarDados(lid);
  adminUsuariosCarregar();   // popula #admin-usuarios-lista (função já existente)
}
```

Substituir `adminLojaTab` (6538-6543):

```javascript
function adminLojaTab(qual){
  document.getElementById('loja-tab-dados').classList.toggle('ativo', qual==='dados');
  document.getElementById('loja-tab-usuarios').classList.toggle('ativo', qual==='usuarios');
  document.getElementById('loja-panel-dados').style.display    = qual==='dados' ? '' : 'none';
  document.getElementById('loja-panel-usuarios').style.display = qual==='usuarios' ? '' : 'none';
}
```

por:

```javascript
function adminLojaTab(qual){
  ['dados','usuarios','projetos'].forEach(q => {
    const tab   = document.getElementById('loja-tab-'+q);
    const panel = document.getElementById('loja-panel-'+q);
    if (tab)   tab.classList.toggle('ativo', q===qual);
    if (panel) panel.style.display = q===qual ? '' : 'none';
  });
  if (qual==='projetos') adminLojaProjetosCarregar();
}
```

- [ ] **Step 4: Loaders da aba Projetos e do nível Projeto**

Adicionar (logo após `adminLojaTab`):

```javascript
async function adminLojaProjetosCarregar(){
  const panel = document.getElementById('loja-panel-projetos');
  if (!panel) return;
  const lid = _adminNav.loja?.id || (_usuarioAtual && _usuarioAtual.loja_id);
  if (!lid){ panel.innerHTML = '<em style="color:var(--muted)">Loja não identificada.</em>'; return; }
  const r = await fetch('/api/admin/lojas/'+lid+'/projetos', {credentials:'same-origin'});
  if (r.status === 403){ panel.innerHTML = '<em style="color:var(--muted)">Sem acesso a esta loja.</em>'; return; }
  if (r.status === 404){ panel.innerHTML = '<em style="color:var(--muted)">Não encontrado.</em>'; return; }
  const d = await r.json().catch(()=>({projetos:[]}));
  const ps = d.projetos || [];
  panel.innerHTML = `
    <table class="cli-table"><thead><tr>
      <th>Projeto</th><th>Status</th><th>Etapa atual</th><th>Progresso</th><th></th>
    </tr></thead><tbody>
    ${ps.map(p=>`<tr>
      <td>${esc(p.nome_safe)}</td>
      <td style="color:var(--muted)">${esc(p.status||'—')}</td>
      <td style="color:var(--muted)">${esc(p.etapa_atual_nome||'—')}</td>
      <td style="color:var(--muted)">${p.etapas_concluidas}/${p.total_etapas}</td>
      <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
        onclick='adminEntrarProjeto(${JSON.stringify(p.nome_safe)}, ${JSON.stringify(p.status||"")})'>Abrir ›</button></td>
    </tr>`).join('') || '<tr><td colspan="5" style="color:var(--muted)">Nenhum projeto nesta loja.</td></tr>'}
    </tbody></table>`;
}

async function adminRenderProjeto(box){
  box.innerHTML = '<em style="color:var(--muted);font-size:12px">Carregando…</em>';
  const nome = _adminNav.projeto?.nome;
  const r = await fetch('/api/admin/projetos/'+encodeURIComponent(nome)+'/etapas', {credentials:'same-origin'});
  if (r.status === 403){ box.innerHTML = '<em style="color:var(--muted)">Sem acesso a este projeto.</em>'; return; }
  if (r.status === 404){ box.innerHTML = '<em style="color:var(--muted)">Não encontrado.</em>'; return; }
  const d = await r.json().catch(()=>({etapas:[]}));
  const es = d.etapas || [];
  box.innerHTML = `
    <div class="card" style="padding:14px 16px">
      <strong style="color:var(--dalm-gold,#c8a84b)">&#x1F4CB; Etapas do projeto ${esc(nome)}</strong>
      <table class="cli-table" style="margin-top:10px"><thead><tr>
        <th>#</th><th>Etapa</th><th>Status</th><th>Concluída em</th>
      </tr></thead><tbody>
      ${es.map(e=>`<tr>
        <td style="color:var(--muted)">${esc(e.etapa_codigo)}</td>
        <td>${esc(e.etapa_nome)}</td>
        <td>${esc(e.status)}</td>
        <td style="color:var(--muted)">${e.concluido_em ? esc(e.concluido_em.substring(0,10)) : '—'}</td>
      </tr>`).join('') || '<tr><td colspan="4" style="color:var(--muted)">Nenhuma etapa registrada.</td></tr>'}
      </tbody></table>
    </div>`;
}
```

- [ ] **Step 5: Verificação manual**

```bash
python3 main.py
```

Logado como **super_admin**:
- Painel Admin → Entrar numa rede → Entrar numa loja → aba **"Projetos"** lista projetos com Status / Etapa atual / Progresso.
- Clicar **"Abrir ›"** num projeto → breadcrumb vira `Plataforma › Rede › Loja › Projeto`; lista as **etapas do ciclo** com status e data.
- Clicar em **"Loja …"** no breadcrumb volta para o nível Loja.
- Loja sem projetos mostra "Nenhum projeto nesta loja."; projeto sem etapas mostra "Nenhuma etapa registrada."

Logado como **admin_rede**: mesmo fluxo, restrito às lojas da própria rede.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(arvore): nivel 4 (aba Projetos + etapas do projeto) no Painel Admin"
```

---

## Notas de implementação

- **Ordem:** Tasks 1→2→3 são backend testável (TDD). Tasks 4→5 são frontend (verificação manual). 4 e 5 dependem da Task 3 já mergeada (as telas consomem as rotas).
- **Fora deste plano (slices futuros):** nível "documentos" (D1–D45) da árvore; multi-papel/multi-loja do mesmo usuário (seed Orizon, #6); painel LGPD (#4); config de rede (#7); config de loja (#8).
