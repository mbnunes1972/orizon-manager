# Super Admin — Acesso Pleno (god-mode) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao perfil `super_admin` acesso pleno e irrestrito — todos os módulos/painéis, todas as capacidades — e permitir que ele opere DENTRO de qualquer loja (criar usuários, criar perfis de acesso, abrir o Cadastro), removendo os três bloqueios estruturais atuais.

**Architecture:** `super_admin` é perfil de PLATAFORMA (fora da tabela `perfil_acesso`, sem `loja_id`, sem membership). Três causas somadas o travam hoje: (1) `pode()`/`acessa_modulo()`/`acessa_painel()` em `auth/perfis.py` negam capacidades que ele não tem no dict hardcoded — inclusive `acesso_operacional=False`; (2) `mod_tenancy.resolver_loja_ativa` nunca resolve loja ativa para quem não é membro de nenhuma loja, então ele não tem escopo operacional nem passando o header `X-Loja-Ativa`; (3) os endpoints de Perfis de Usuário (`/api/admin/perfis*`) escopam pela `usuario.loja_id` (None p/ super_admin), quebrando leitura e criação. A solução: bypass explícito de `super_admin` nas três funções de `perfis.py`; deixar `super_admin` adotar a loja do header como loja ativa; e trocar a resolução de loja dos endpoints de Perfis por um alvo que honra a loja selecionada no console Admin. No frontend, `adminEntrarLoja` passa a setar `_lojaAtiva` para que o interceptor já existente envie `X-Loja-Ativa` nas chamadas subsequentes.

**Tech Stack:** Python puro (`http.server` + SQLAlchemy/SQLite), pytest/TDD no backend; frontend em `static/index.html` (verificação manual + `node --check`).

---

## File Structure

- **`auth/perfis.py`** (Modify) — bypass de `super_admin` em `pode`, `acessa_modulo`, `acessa_painel`; flags `acesso_*` do dict `PERFIS["super_admin"]` para refletir god-mode na matriz read-only.
- **`mod_tenancy.py`** (Modify) — `resolver_loja_ativa` ganha parâmetro `is_super`: super_admin adota a loja do header como ativa.
- **`main.py`** (Modify) — `_ator_dict` passa `is_super` ao resolver; novo helper `_loja_admin_alvo(usuario)`; três endpoints de Perfis passam a usá-lo.
- **`static/index.html`** (Modify) — `adminEntrarLoja` seta `_lojaAtiva=id`; navegação de volta (níveis 1/2) limpa `_lojaAtiva`.
- **`tests/conftest.py`** (Modify) — `HttpClient` aceita header `X-Loja-Ativa` opcional (necessário p/ e2e do super_admin operando numa loja).
- **`tests/test_super_admin_god_mode.py`** (Create) — unit de `perfis.py` (bypass) + `mod_tenancy` (loja ativa) + e2e HTTP (criar perfil/ler matriz numa loja escolhida).

---

## Task 1: `perfis.py` — bypass god-mode do super_admin

**Files:**
- Modify: `auth/perfis.py` (funções `pode`, `acessa_modulo`, `acessa_painel`; dict `PERFIS["super_admin"]`)
- Test: `tests/test_super_admin_god_mode.py`

- [ ] **Step 1: Escrever o teste que falha**

Criar `tests/test_super_admin_god_mode.py` com:

```python
"""super_admin = acesso pleno e irrestrito (god-mode): ignora todos os gates de
capacidade e de módulo/painel; opera dentro de qualquer loja (loja do header)."""
from auth import perfis
import mod_tenancy


def test_super_admin_pode_qualquer_capacidade():
    # capacidades reais e uma inexistente — super_admin nunca é barrado
    for cap in ("gerir_usuarios", "gerir_perfis", "acesso_operacional",
                "acesso_financeiro", "acesso_fiscal", "autorizar",
                "ver_parametros", "editar_dados_loja", "capacidade_que_nao_existe"):
        assert perfis.pode("super_admin", cap) is True, cap


def test_super_admin_acessa_todo_modulo_e_painel():
    for mod in ("cadastro", "comercial", "financeiro", "folha", "fiscal",
                "estoque", "expedicao", "montagem", "assistencias"):
        assert perfis.acessa_modulo("super_admin", mod) is True, mod
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.acessa_painel("super_admin", "config") is True


def test_bypass_nao_vaza_para_outros_perfis():
    # operador continua barrado onde já era barrado (não abre buraco lateral)
    assert perfis.pode("operador", "gerir_perfis") is False
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_painel("operador", "admin") is False
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py::test_super_admin_pode_qualquer_capacidade tests/test_super_admin_god_mode.py::test_super_admin_acessa_todo_modulo_e_painel -q`
Expected: FAIL — `acessa_modulo("super_admin","cadastro")` hoje é True por acaso (módulo operacional cai no `pode(acesso_operacional)`=False → na verdade False), e `pode("super_admin","acesso_operacional")` é False.

- [ ] **Step 3: Implementar o bypass**

Em `auth/perfis.py`, primeira linha de cada função:

`pode` (após a docstring, antes de `info = _reg().get(slug)`):
```python
def pode(slug, capacidade):
    """Override do perfil (capacidades_json) manda; senão cai na base PERFIS[base].
    super_admin é irrestrito (god-mode): sempre True."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    if info and capacidade in info["caps"]:
        return bool(info["caps"][capacidade])
    return bool(PERFIS.get(_base(slug), _DEFAULT).get(capacidade, False))
```

`acessa_modulo` (primeira instrução do corpo):
```python
def acessa_modulo(slug, modulo_id):
    """...docstring existente..."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    ...
```

`acessa_painel` (primeira instrução do corpo):
```python
def acessa_painel(slug, painel):
    """...docstring existente..."""
    if slug == "super_admin":
        return True
    info = _reg().get(slug)
    ...
```

E no dict `PERFIS["super_admin"]`, virar as flags de acesso p/ a matriz read-only ficar honesta (o bypass já cobre o enforcement; isto é só apresentação/defesa em profundidade):
```python
    "super_admin": {"rotulo": "Administrador da Plataforma", "desconto_max": 0.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "gerir_perfis": True, "editar_dados_loja": True,
        "gerir_redes": True, "gerir_lojas": True},
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py -q`
Expected: PASS (os 3 testes desta task).

- [ ] **Step 5: Suíte de perfis não regride**

Run: `python3 -m pytest tests/test_perfis.py tests/test_acesso_perfil.py tests/test_perfis_matriz.py -q`
Expected: PASS (verde). `_eh_super_admin`/`_eh_admin_rede` seguem corretos: `super_admin` tem `gerir_redes`→True; `admin_rede` tem `gerir_lojas`→True e `gerir_redes`→False (o bypass é só p/ o slug `super_admin`).

- [ ] **Step 6: Commit**

```bash
git add auth/perfis.py tests/test_super_admin_god_mode.py
git commit -m "feat(perfis): super_admin irrestrito (bypass em pode/acessa_modulo/acessa_painel)"
```

---

## Task 2: `mod_tenancy` — super_admin adota a loja do header como ativa

**Files:**
- Modify: `mod_tenancy.py` (`resolver_loja_ativa`)
- Modify: `main.py` (`_ator_dict`)
- Test: `tests/test_super_admin_god_mode.py`

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar a `tests/test_super_admin_god_mode.py`:

```python
def test_super_admin_adota_loja_do_header():
    # sem membership e sem loja própria, mas com header → loja ativa = header
    assert mod_tenancy.resolver_loja_ativa([], 5, None, is_super=True) == 5
    # sem header → sem loja ativa (precisa escolher uma loja no console)
    assert mod_tenancy.resolver_loja_ativa([], None, None, is_super=True) is None


def test_resolver_loja_ativa_nao_super_inalterado():
    # comportamento pré-existente preservado p/ usuário de loja
    assert mod_tenancy.resolver_loja_ativa([], 5, None) is None          # header sem acesso → None
    assert mod_tenancy.resolver_loja_ativa([7], None, 7) == 7            # default acessível
    assert mod_tenancy.resolver_loja_ativa([7], 7, None) == 7           # header acessível
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py::test_super_admin_adota_loja_do_header -q`
Expected: FAIL — `resolver_loja_ativa` ainda não aceita `is_super`.

- [ ] **Step 3: Implementar**

Em `mod_tenancy.py`, `resolver_loja_ativa`:

```python
def resolver_loja_ativa(memberships, header_loja_id, default_loja_id, is_super=False):
    """Decide a loja ativa de uma requisição operacional.

    super_admin (is_super) é irrestrito: adota a loja do header como ativa (ou None
    se nenhuma escolhida). Demais: acessíveis = memberships ∪ {default}; header só
    vale se acessível (senão None → 403); sem header → default acessível; senão
    membership única; senão None.
    """
    if is_super:
        return header_loja_id
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

Em `main.py`, `_ator_dict` (linha ~8611-8612):

```python
    membership = membership_loja_ids(db, u.id)
    is_super = (u.nivel == "super_admin")
    active = mod_tenancy.resolver_loja_ativa(membership, header_loja_id, u.loja_id, is_super=is_super)
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py -q`
Expected: PASS.

- [ ] **Step 5: Tenancy não regride**

Run: `python3 -m pytest tests/test_tenancy_escopo.py tests/test_perfis_tenancy.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mod_tenancy.py main.py tests/test_super_admin_god_mode.py
git commit -m "feat(tenancy): super_admin adota a loja do header como loja ativa"
```

---

## Task 3: Endpoints de Perfis escopam pela loja selecionada (não pela loja do ator)

**Files:**
- Modify: `main.py` (helper `_loja_admin_alvo`; endpoints GET `/api/admin/perfis-matriz` ~1409, GET `/api/admin/perfis` ~1421, POST `/api/admin/perfis` ~5405)
- Modify: `tests/conftest.py` (`HttpClient` aceita header)
- Test: `tests/test_super_admin_god_mode.py`

- [ ] **Step 1: Dar suporte a header no `HttpClient`**

Em `tests/conftest.py`, `HttpClient._req` — aceitar header opcional:

```python
    def __init__(self, base):
        self.base = base
        self.cookie = None
        self.loja_ativa = None          # X-Loja-Ativa opcional (super_admin operando numa loja)

    def _req(self, method, path, body=None):
        data = _json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        if self.loja_ativa is not None:
            req.add_header("X-Loja-Ativa", str(self.loja_ativa))
        ...
```

- [ ] **Step 2: Escrever o teste e2e que falha**

Acrescentar a `tests/test_super_admin_god_mode.py`:

```python
def test_super_admin_cria_e_le_perfil_na_loja_escolhida(http_client_factory, seed, app_db):
    db = app_db.get_session()
    l1 = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    db.close()
    c = http_client_factory(); c.login("super", "senha123")
    c.loja_ativa = l1                                   # "entra" na loja L1
    # cria um perfil de acesso NA loja L1
    st, out = c.post("/api/admin/perfis", {"nome": "Vendas Plus", "base": "operador",
                                           "modulos": ["cadastro", "comercial"]})
    assert st == 201 and out["ok"], (st, out)
    # a matriz da loja L1 agora inclui o perfil recém-criado
    st, m = c.get("/api/admin/perfis")
    assert st == 200 and m["ok"]
    nomes = {p["nome"] for p in m["perfis"]}
    assert "Vendas Plus" in nomes, nomes


def test_super_admin_sem_loja_selecionada_erro_ao_criar_perfil(http_client_factory, seed):
    c = http_client_factory(); c.login("super", "senha123")   # sem c.loja_ativa
    st, out = c.post("/api/admin/perfis", {"nome": "X", "base": "operador", "modulos": []})
    assert out["ok"] is False and "loja" in (out.get("erro", "").lower())
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py::test_super_admin_cria_e_le_perfil_na_loja_escolhida -q`
Expected: FAIL — hoje o endpoint usa `usuario.get("loja_id")` (None) → cria perfil órfão e a matriz vem vazia.

- [ ] **Step 4: Implementar helper + trocar a resolução de loja**

Em `main.py`, junto de `_ler_loja_ativa_header` (~linha 573), adicionar:

```python
def _loja_admin_alvo(usuario):
    """Loja-alvo de uma operação de Admin escopada por LOJA (Perfis de Usuário).
    super_admin opera na loja selecionada no console (header X-Loja-Ativa); demais
    perfis usam a própria loja."""
    if usuario.get("nivel") == "super_admin":
        return _REQ_LOJA_ATIVA or usuario.get("loja_id")
    return usuario.get("loja_id")
```

GET `/api/admin/perfis-matriz` (~1409): trocar
`lid = usuario.get("loja_id")` → `lid = _loja_admin_alvo(usuario)`.

GET `/api/admin/perfis` (~1421): trocar
`_m = perfis.matriz_loja(usuario.get("loja_id"))` → `_m = perfis.matriz_loja(_loja_admin_alvo(usuario))`.

POST `/api/admin/perfis` (~5405): antes do `criar_perfil`, resolver e validar a loja:
```python
                try:
                    from auth import perfil_store
                    lid = _loja_admin_alvo(usuario)
                    if lid is None:
                        self.send_json({"ok": False, "erro": "Selecione uma loja para criar o perfil."}); return
                    p, err = perfil_store.criar_perfil(db, lid,
                                req.get("nome", ""), req.get("base", ""), req.get("modulos", []),
                                capacidades=req.get("capacidades"))
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_super_admin_god_mode.py -q`
Expected: PASS.

- [ ] **Step 6: E2E de perfis não regride**

Run: `python3 -m pytest tests/test_perfis_api_e2e.py -q`
Expected: PASS (usuário de loja continua escopado à própria loja — `_loja_admin_alvo` devolve `usuario.loja_id` p/ não-super).

- [ ] **Step 7: Commit**

```bash
git add main.py tests/conftest.py tests/test_super_admin_god_mode.py
git commit -m "feat(admin): Perfis de Usuário escopam pela loja selecionada (super_admin opera em qualquer loja)"
```

---

## Task 4: Frontend — `adminEntrarLoja` seta a loja ativa; navegação de volta limpa

**Files:**
- Modify: `static/index.html` (`adminEntrarLoja` ~8929; resets de `_adminNav.loja` ~8921-8925 e `adminEntrarRede` ~8928)

- [ ] **Step 1: Setar `_lojaAtiva` ao entrar numa loja**

Em `adminEntrarLoja(id, nome)` (~8929), após `_adminNav.loja = { id, nome };`:
```javascript
async function adminEntrarLoja(id, nome){
  _adminNav.loja = { id, nome };
  _adminNav.nivel = 3;
  _lojaAtiva = id;               // super_admin passa a operar DENTRO desta loja (header X-Loja-Ativa)
  try {
    ...
```

- [ ] **Step 2: Limpar `_lojaAtiva` ao voltar para plataforma/rede**

Na função de navegação por nível (`adminNav`/breadcrumb, ~8921-8925) onde `_adminNav.loja = null` é setado para os níveis 1 e 2, acrescentar `_lojaAtiva = null;` no mesmo ponto:
```javascript
  if (n === 1) { _adminNav.rede = null; _adminNav.loja = null; _adminNav.projeto = null; _lojaAtiva = null; }
  if (n === 2) { _adminNav.loja = null; _adminNav.projeto = null; _lojaAtiva = null; }
```
E em `adminEntrarRede(id, nome)` (~8928): acrescentar `_lojaAtiva = null;` (entrar numa rede sai da loja).

- [ ] **Step 3: Checar sintaxe do JS**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"
python3 - <<'PY'
import re
html = open("static/index.html", encoding="utf-8").read()
m = re.search(r"<script>(.*)</script>", html, re.S)
open("/tmp/orizon_app.js", "w", encoding="utf-8").write(m.group(1))
print("extraído", len(m.group(1)), "chars")
PY
node --check /tmp/orizon_app.js && echo "JS OK"
```
Expected: `JS OK`.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat(admin-ui): entrar numa loja define a loja ativa do super_admin"
```

---

## Task 5: Verificação ponta-a-ponta + suíte + DEV_LOG

**Files:**
- Modify: `DEV_LOG.md` (nova `## Sessão N`)

- [ ] **Step 1: Suíte completa verde**

Run: `python3 -m pytest -q`
Expected: tudo verde (contagem ≥ a de antes + os novos testes de `test_super_admin_god_mode.py`).

- [ ] **Step 2: Verificação manual no navegador (super_admin)**

`python3 main.py` → `http://localhost:8765`. Logar como super_admin. Confirmar (Ctrl+F5):
1. Admin › Plataforma → entrar numa rede → entrar numa loja.
2. Dentro da loja: **criar um usuário** (loja) → salva sem erro.
3. Aba **Perfis de Usuário**: a matriz carrega os perfis DAQUELA loja; **criar um perfil novo** → aparece na lista.
4. Módulo **Cadastro** abre e permite cadastrar Funcionário/Fornecedor/Terceiro na loja ativa (sem 403 de escopo).
5. Sair da loja (breadcrumb → Plataforma) e confirmar que o contexto operacional volta ao normal.

- [ ] **Step 3: Atualizar DEV_LOG**

Acrescentar `## Sessão N — super_admin acesso pleno (god-mode)` no fim do `DEV_LOG.md`, resumindo: as 3 causas-raiz (sem loja ativa; `acesso_operacional=False`+caps; endpoints de Perfis usando `usuario.loja_id`=None), a solução (bypass em `perfis.py`; `resolver_loja_ativa(is_super)`; `_loja_admin_alvo`; `adminEntrarLoja` seta `_lojaAtiva`), e a decisão do usuário ("liberdade plena e irrestrita por enquanto; revisitar limites/segundo perfil de admin depois"). Registrar a nova contagem da suíte.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs: DEV_LOG — super_admin acesso pleno (god-mode)"
```

---

## Notas de decisão / escopo

- **"Por enquanto irrestrito":** o bypass é intencionalmente amplo (decisão do usuário). Um eventual segundo perfil de administração mais limitado, ou reintroduzir limites no super_admin, é frente futura — não faz parte deste plano.
- **`admin_rede` NÃO é alvo aqui.** O helper `_loja_admin_alvo` só dá tratamento especial ao slug `super_admin`; `admin_rede` segue com o comportamento atual (fora do escopo do pedido).
- **Reuso de `_lojaAtiva`:** o super_admin "entrar numa loja" passa a definir a loja operacional ativa (mesmo canal do seletor multi-loja). É o caminho mais simples e reaproveita o interceptor de fetch existente; para o super_admin isso é o comportamento desejado ("operar como esta loja").
- **Segurança:** o bypass vale só para o slug exato `super_admin`; `_eh_super_admin` continua derivando de `gerir_redes`, que só o super_admin possui. Testes garantem que operador/gerencial não ganham acesso lateral.
