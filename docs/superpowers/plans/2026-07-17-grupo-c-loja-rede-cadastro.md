# Grupo C — Cadastro de Loja completo + seletor buscável + troca de senha no 1º login — Plano

> **For agentic workers:** TDD no backend (pytest verde antes de commitar); frontend com `node --check` + verificação manual. Steps com checkbox.

**Goal:** Itens 7, 8, 9 dos 9 tópicos. (7) seletor de empresa no canto sup. esquerdo de Admin/Config, buscável por nome/CNPJ. (8) "Cadastro de Loja" completo (identidade/endereço/contato/responsável + 1º usuário diretor com senha provisória + módulos de uso), edição associa a uma rede. (9) segundo caminho: adicionar loja pela aba Redes, mesmo modal/destino.

**Decisões:** dados no nível da loja (fiscal segue no Painel Fiscal); diretor = perfil `master` com **senha provisória** trocada no 1º login; módulos = matriz `modulos_ativos` existente; rede associável na criação e edição. Base: `main` (Fase 1 + Grupo A).

**Tech Stack:** Python puro + SQLAlchemy/SQLite; `python3 -m pytest` (SQLite default). Frontend `static/index.html` (`node --check` via WSL + navegador).

---

## Task C1: `cnpj` no `GET /api/admin/empresas` (base da busca do item 7)

**Files:** Modify `main.py` (ramo `/api/admin/empresas`); Test `tests/test_admin_empresas.py`.

- [ ] **Step 1 (teste que falha):** acrescentar a `tests/test_admin_empresas.py`:
```python
def test_empresas_incluem_cnpj(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.get("/api/admin/empresas")
    assert st == 200 and out["ok"]
    assert all("cnpj" in e for e in out["empresas"])
```
- [ ] **Step 2:** `python3 -m pytest tests/test_admin_empresas.py::test_empresas_incluem_cnpj -q` → FAIL (sem chave cnpj).
- [ ] **Step 3 (implementar):** no ramo `/api/admin/empresas` de `main.py`, no dict do append, acrescentar `"cnpj": lo.cnpj or "",`:
```python
                    empresas.append({"loja_id": lo.id, "nome": lo.nome,
                                     "cnpj": lo.cnpj or "",
                                     "rede_id": lo.rede_id,
                                     "rede_nome": redes.get(lo.rede_id, "") if lo.rede_id else ""})
```
- [ ] **Step 4:** `python3 -m pytest tests/test_admin_empresas.py -q` → todos passam.
- [ ] **Step 5 (commit):** `git add main.py tests/test_admin_empresas.py && git commit -m "feat(admin): cnpj no GET /api/admin/empresas (base da busca do seletor)"`

## Task C2: Seletor de empresa no canto sup. esquerdo + busca por nome/CNPJ (item 7)

**Files:** Modify `static/index.html` (`empresaSeletorHTML`, containers em Admin/Config, `empresaTrocar`).

- [ ] **Step 1:** trocar o `empresaSeletorHTML` (hoje um `<select>` agrupado) por um **combobox buscável**: um `<input>` de busca (placeholder "Buscar por nome ou CNPJ…") + lista filtrada (nome + cnpj, agrupada por rede). Estado `_empBusca`. Ao clicar num item → `empresaTrocar(loja_id)`. Posicionar o contêiner no **canto superior esquerdo** do painel (Admin: antes das abas, alinhado à esquerda; Config: idem, abaixo do subtítulo).
- [ ] **Step 2:** filtro: casa `nome` (case-insensitive) OU dígitos do `cnpj`. Reusa `esc`, e um `_digitos()` local se necessário.
- [ ] **Step 3:** `node --check` (extrair `<script>` + `node --check` via WSL) → `JS_OK`.
- [ ] **Step 4 (commit):** só `static/index.html`.

## Task C3: `Usuario.senha_provisoria` + troca no 1º login (backend) (item 8b)

**Files:** Modify `database.py` (coluna + migração idempotente), `auth/auth.py`/`auth_routes.py` (login sinaliza; endpoint trocar-senha); Test `tests/test_troca_senha.py`.

- [ ] **Step 1 (teste que falha):** `tests/test_troca_senha.py`:
```python
"""Senha provisória: usuário criado com senha_provisoria=1 é sinalizado no login e troca a senha."""
def test_login_sinaliza_e_troca(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    u = app_db.Usuario(nome="Novo Dir", login="novodir@l1.com", nivel="master",
                       loja_id=l1, ativo=1, senha_provisoria=1)
    u.set_senha("provisoria123"); db.add(u); db.commit(); db.close()
    c = http_client_factory()
    st, out = c.login("novodir@l1.com", "provisoria123")
    assert st == 200 and out.get("precisa_trocar_senha") is True
    st2, o2 = c.post("/api/auth/trocar-senha", {"nova_senha": "definitiva456"})
    assert st2 == 200 and o2["ok"]
    # relogar com a nova senha, sem flag
    c2 = http_client_factory()
    st3, o3 = c2.login("novodir@l1.com", "definitiva456")
    assert st3 == 200 and not o3.get("precisa_trocar_senha")
```
- [ ] **Step 2:** rodar → FAIL (coluna/campo/endpoint inexistentes).
- [ ] **Step 3 (implementar):**
  - `database.py`: `Usuario.senha_provisoria = Column(Integer, default=0)` (0/1); migração idempotente em `_run_migracoes` (ADD COLUMN se ausente, como as demais colunas novas).
  - Login (`auth_routes`/`auth`): incluir `precisa_trocar_senha: bool(u.senha_provisoria)` na resposta do login e no `/auth/me`.
  - `POST /api/auth/trocar-senha` (autenticado): valida `nova_senha` (mín. tamanho), `u.set_senha(nova)`, `u.senha_provisoria = 0`, commit; retorna `{ok:True}`.
  - `set_senha` NÃO zera a flag sozinho (a troca é explícita pelo endpoint).
- [ ] **Step 4:** rodar → passa.
- [ ] **Step 5 (regressão):** `python3 -m pytest tests/test_usuarios_e2e.py tests/test_acesso_perfil.py -q` verde.
- [ ] **Step 6 (commit).**

## Task C4: Tela de troca de senha obrigatória no 1º login (frontend) (item 8b)

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** após o login bem-sucedido, se `precisa_trocar_senha` → abrir modal **bloqueante** "Defina sua senha" (nova + confirmar) que chama `POST /api/auth/trocar-senha`; só libera a UI após sucesso. Também tratar no `/auth/me` (se a sessão retomar com a flag).
- [ ] **Step 2:** `node --check` → `JS_OK`.
- [ ] **Step 3 (commit).**

## Task C5: `POST /api/admin/lojas` completo + diretor + módulos; `PATCH` editar/associar rede (item 8a)

**Files:** Modify `main.py` (POST + novo PATCH); Test `tests/test_loja_cadastro.py`.

- [ ] **Step 1 (teste que falha):** `tests/test_loja_cadastro.py`:
```python
"""Cadastro completo de loja: cria loja + diretor (senha provisória) + módulos; edita associa rede."""
def test_super_admin_cadastra_loja_completa(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas", {
        "nome": "Loja Nova", "codigo": "LNV", "cnpj": "12.345.678/0001-95",
        "telefone": "1133330000", "email": "loja@nova.com", "responsavel": "Fulano",
        "logradouro": "Rua X", "numero": "10", "bairro": "Centro", "cidade": "SP", "uf": "SP", "cep": "01000-000",
        "diretor": {"nome": "Diretor Novo", "login": "dir@nova.com"},
        "modulos": ["cadastro", "comercial", "fiscal"],
    })
    assert st in (200, 201) and out["ok"], out
    lid = out["loja"]["id"]
    db = app_db.get_session()
    lo = db.get(app_db.Loja, lid)
    diru = db.query(app_db.Usuario).filter_by(login="dir@nova.com").first()
    db.close()
    assert lo.cnpj and lo.responsavel == "Fulano"
    assert diru is not None and diru.nivel == "master" and diru.loja_id == lid and diru.senha_provisoria == 1

def test_patch_associa_rede(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    rede = db.query(app_db.Rede).first(); rid = rede.id if rede else None
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    st, out = c.patch(f"/api/admin/lojas/{l1}", {"rede_id": rid})
    assert st == 200 and out["ok"]
```
- [ ] **Step 2:** rodar → FAIL. (Confirmar se `Loja` tem `responsavel`; se não, adicionar coluna + migração — checar no `database.py` ao implementar.)
- [ ] **Step 3 (implementar):**
  - Estender o handler `POST /api/admin/lojas`: aceitar a allowlist de campos da loja (cnpj, telefone, email, responsavel, endereço) além de nome/codigo/rede_id; criar a `Loja`; se veio `modulos`, gravar `modulos_ativos` (JSON); se veio `diretor`, criar `Usuario(nivel="master", loja_id=nova, senha_provisoria=1)` com senha padrão (dígitos do CNPJ ou "orizon123") vinculado à loja. Retornar `{ok, loja:{id,...}}`.
  - Novo `PATCH /api/admin/lojas/<id>` (gate `gerir_lojas`/escopo via `pode_ver_loja`): aplica allowlist de campos + `rede_id` (associa/desassocia rede). Retorna `{ok, loja}`.
  - Se `Loja.responsavel` não existir: `Column(String)` + migração idempotente.
- [ ] **Step 4:** rodar → passa.
- [ ] **Step 5 (regressão):** `python3 -m pytest tests/test_multi_loja_e2e.py tests/test_admin_empresas.py -q` verde.
- [ ] **Step 6 (commit).**

## Task C6: Modal "Cadastro de Loja" (form completo) no Orizon › Lojas + edição (item 8a)

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** modal `#modal-loja` com abas/seções: Identidade (nome, código, CNPJ), Endereço, Contato (telefone/email/responsável), Diretor (nome, login), Módulos (checkboxes das opções de domínio), Rede (seletor). "+ Nova loja" (Orizon › Lojas) abre o modal (POST); "Editar" numa linha da tabela abre em modo edição (PATCH, sem os campos de diretor/senha, com a rede associável). Módulos: reusa as opções de domínio (`mod_perfis_opcoes`/`/api/admin/...`); salvar módulos via o payload da criação ou `PUT .../modulos` já existente.
- [ ] **Step 2:** remove/aposenta o mini-form inline de "nova loja" da Task anterior (Fase 1 Lojas) em favor do modal.
- [ ] **Step 3:** `node --check` → `JS_OK`.
- [ ] **Step 4 (commit).**

## Task C7: Redes › "+ Loja nesta rede" abre o mesmo modal (item 9)

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** na aba Redes do Painel Orizon, cada rede ganha um botão "+ Loja nesta rede" que abre `#modal-loja` com a rede **pré-selecionada** (mesmo modal/endpoint da C6). Mesmo destino de dados.
- [ ] **Step 2:** `node --check` → `JS_OK`.
- [ ] **Step 3 (commit).**

## Task C8: Verificação + fecho do grupo

- [ ] Suíte completa `python3 -m pytest -q` verde.
- [ ] Verificação manual por perfil (super_admin cria loja completa → diretor loga → força troca de senha → loja aparece no seletor buscável por nome/CNPJ; editar loja associa rede; criar loja pela aba Redes).
- [ ] FF na `main`; DEV_LOG (nova sessão).

## Notas
- **Ordem sugerida:** C1 → C2 (item 7 fecha cedo) → C3 → C4 (senha provisória) → C5 → C6 → C7.
- **Senha padrão do diretor:** dígitos do CNPJ (ou "orizon123" se vazio), como o `func_sync_acesso` faz p/ funcionário — coerência com o projeto.
- **Fiscal fora de escopo:** o cadastro não coleta dados fiscais; identidade fiscal segue no Painel Fiscal.
