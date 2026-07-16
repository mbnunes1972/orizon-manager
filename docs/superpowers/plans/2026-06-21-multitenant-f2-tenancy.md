# Multi-tenant F2 — Perfis e CRUD de tenancy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a tenancy **gerenciável pela interface** — perfis `super_admin`/`admin_rede`, super_admin de bootstrap, CRUD de redes/lojas/usuários com escopo, edição dos dados da loja seed (destrava a F3) e UX de abrangência do parceiro — **sem tocar em nenhuma query operacional** (isolamento é a F4).

**Architecture:** O escopo só entra nas superfícies administrativas **novas**. A lógica de permissão e escopo é extraída em **funções puras** (`perfis.py` para capacidades; `mod_tenancy.py` para validadores e decisões de escopo/atribuição), totalmente cobertas por pytest. As rotas HTTP (handler `http.server` em `main.py`) são finas: validam, chamam as funções puras, aplicam `WHERE` por `loja_id`/`rede_id` e serializam. O bootstrap do super_admin é uma migração de dados idempotente (`tenancy_v2_2026`), no mesmo padrão da F1. O frontend (SPA vanilla em `static/index.html`) reorganiza a `page-07` em 3 consoles (Plataforma → Rede → Loja) com breadcrumb + drill-down, preservando o CRUD de usuários atual como "Usuários da loja" do Nível 3.

**Tech Stack:** Python 3, `http.server.BaseHTTPRequestHandler` (sem framework), SQLAlchemy (ORM), sqlite3 (migrações raw), pytest, SPA vanilla JS (`static/index.html`), Playwright para verificação de UI.

**Spec:** `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f2-tenancy-design.md`

---

## Estrutura de arquivos

- **Modificar `perfis.py`:** perfis `super_admin`/`admin_rede`; capacidades `gerir_redes`/`gerir_lojas`/`editar_dados_loja` (e em `_DEFAULT`); `editar_dados_loja` no `diretor`.
- **Modificar `auth.py`:** `_usuario_dict` passa a expor `loja_id`/`rede_id` e os flags `pode_gerir_redes`/`pode_gerir_lojas`/`pode_editar_dados_loja` (front aterrissa e renderiza por perfil).
- **Modificar `tests/test_perfis.py`:** atualizar `test_slugs_*` para os 12 perfis (quebra ao adicionar 2 perfis).
- **Criar `mod_tenancy.py`:** validadores puros (`validar_rede`, `validar_loja`, `validar_abrangencia_parceiro`) + helpers puros de escopo/atribuição (`pode_ver_rede`, `pode_ver_loja`, `pode_editar_dados_loja`, `atribuir_tenant_usuario`).
- **Modificar `database.py`:** migração de dados `tenancy_v2_2026` (cria super_admin de bootstrap) em `_run_migracoes`.
- **Modificar `seed.py`:** cria o super_admin antes da loja seed.
- **Modificar `main.py`:** import `Rede, Loja, ParceiroLoja`; helpers `_rede_dict`/`_loja_dict`; rotas `/api/admin/redes` (GET/POST/PATCH), `/api/admin/lojas` (GET/POST/PATCH com escopo + dados da loja); extensão de `/api/admin/usuarios` (atribuição + escopo) e do cadastro de parceiros (abrangência + vínculos M:N).
- **Modificar `static/index.html`:** `page-07` reorganizada nos 3 consoles (breadcrumb + drill-down); aba "Dados da loja"; UX de abrangência no modal de parceiro.
- **Modificar `docs/USUARIOS.md`:** documentar os 2 perfis novos.
- **Criar testes:** `tests/test_perfis_tenancy.py`, `tests/test_tenancy_validadores.py`, `tests/test_tenancy_escopo.py`, `tests/test_tenancy_bootstrap.py`.

**Não tocar:** nenhuma query de clientes/projetos/orçamentos/contratos/pool/medição; `mod_contrato.py` permanece nas constantes.

---

## Task 1: Perfis `super_admin`/`admin_rede` + capacidades + sessão expõe tenant

**Files:**
- Modify: `perfis.py`
- Modify: `auth.py` (`_usuario_dict`, ≈ linhas 167-177)
- Modify: `tests/test_perfis.py` (`test_slugs_sao_os_dez_perfis`)
- Test: `tests/test_perfis_tenancy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_perfis_tenancy.py
import perfis


def test_perfis_novos_existem():
    assert perfis.existe("super_admin") is True
    assert perfis.existe("admin_rede") is True
    assert perfis.rotulo("super_admin") == "Administrador da Plataforma"
    assert perfis.rotulo("admin_rede")  == "Administrador de Rede"


def test_capacidades_administrativas():
    assert perfis.pode("super_admin", "gerir_redes")        is True
    assert perfis.pode("super_admin", "gerir_lojas")        is True
    assert perfis.pode("super_admin", "editar_dados_loja")  is True
    assert perfis.pode("super_admin", "gerir_usuarios")     is True

    assert perfis.pode("admin_rede", "gerir_redes")         is False
    assert perfis.pode("admin_rede", "gerir_lojas")         is True
    assert perfis.pode("admin_rede", "editar_dados_loja")   is True
    assert perfis.pode("admin_rede", "gerir_usuarios")      is True

    # diretor ganha editar_dados_loja (a própria), mas NÃO gerir_redes/lojas
    assert perfis.pode("diretor", "editar_dados_loja")      is True
    assert perfis.pode("diretor", "gerir_lojas")            is False
    assert perfis.pode("diretor", "gerir_redes")            is False

    # demais perfis: tudo administrativo novo é False (default seguro)
    assert perfis.pode("consultor", "gerir_redes")          is False
    assert perfis.pode("consultor", "gerir_lojas")          is False
    assert perfis.pode("consultor", "editar_dados_loja")    is False


def test_perfis_novos_sem_poder_operacional():
    for slug in ("super_admin", "admin_rede"):
        assert perfis.desconto_max(slug) == 0.0
        assert perfis.pode(slug, "autorizar")                 is False
        assert perfis.pode(slug, "aprovar_financeiro")        is False
        assert perfis.pode(slug, "registrar_medicao")         is False
        assert perfis.pode(slug, "aprovar_medicao_reprovada") is False
        assert perfis.pode(slug, "ver_parametros")            is False


def test_usuario_dict_expoe_tenant_e_flags():
    from auth import _usuario_dict
    from database import Usuario
    u = Usuario(id=9, nome="SA", login="sad2026", nivel="super_admin",
                loja_id=None, rede_id=None)
    d = _usuario_dict(u)
    assert d["loja_id"] is None
    assert d["rede_id"] is None
    assert d["pode_gerir_redes"]       is True
    assert d["pode_gerir_lojas"]       is True
    assert d["pode_editar_dados_loja"] is True

    ar = Usuario(id=10, nome="AR", login="ar1", nivel="admin_rede",
                 loja_id=None, rede_id=3)
    da = _usuario_dict(ar)
    assert da["rede_id"] == 3
    assert da["pode_gerir_redes"] is False
    assert da["pode_gerir_lojas"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_perfis_tenancy.py -v`
Expected: FAIL — perfis `super_admin`/`admin_rede` inexistentes; `_usuario_dict` sem `loja_id`.

- [ ] **Step 3: Add the two profiles and capabilities to `perfis.py`**

Em `perfis.py`, dentro do dict `PERFIS`, adicionar as duas linhas no **fim** (após `"medidor": {...}`), e adicionar `editar_dados_loja` ao `diretor`:

```python
    "super_admin":               {"rotulo": "Administrador da Plataforma",       "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": False, "registrar_medicao": False, "aprovar_medicao_reprovada": False, "gerir_redes": True,  "gerir_lojas": True,  "editar_dados_loja": True},
    "admin_rede":                {"rotulo": "Administrador de Rede",             "desconto_max": 0.0,  "ver_parametros": False, "autorizar": False, "gerir_usuarios": True,  "aprovar_financeiro": False, "registrar_medicao": False, "aprovar_medicao_reprovada": False, "gerir_redes": False, "gerir_lojas": True,  "editar_dados_loja": True},
```

Na linha do `diretor` (linha 8), acrescentar a capacidade `editar_dados_loja` ao final do dict (antes do `}`):

```python
    "diretor":                   {"rotulo": "Diretor",                           "desconto_max": 50.0, "ver_parametros": True,  "autorizar": True,  "gerir_usuarios": True,  "aprovar_financeiro": True,  "registrar_medicao": True,  "aprovar_medicao_reprovada": True, "editar_dados_loja": True},
```

E no `_DEFAULT` (linhas 20-22), acrescentar as três capacidades novas para que o default seguro seja `False`:

```python
_DEFAULT = {"rotulo": "—", "desconto_max": 0.0, "ver_parametros": False,
            "autorizar": False, "gerir_usuarios": False, "aprovar_financeiro": False,
            "registrar_medicao": False, "aprovar_medicao_reprovada": False,
            "gerir_redes": False, "gerir_lojas": False, "editar_dados_loja": False}
```

- [ ] **Step 4: Expose tenant + flags in `auth._usuario_dict`**

Em `auth.py`, substituir o corpo de `_usuario_dict` (linhas 167-177) por:

```python
def _usuario_dict(u: Usuario) -> dict:
    return {
        "id":                u.id,
        "nome":              u.nome,
        "login":             u.login,
        "nivel":             u.nivel,
        "loja_id":           u.loja_id,
        "rede_id":           u.rede_id,
        "limite_desconto":   u.limite_desconto,
        "pode_ver_parametros": u.pode_ver_parametros,
        "rotulo":              perfis.rotulo(u.nivel),
        "pode_gerir_usuarios": perfis.pode(u.nivel, "gerir_usuarios"),
        "pode_gerir_redes":       perfis.pode(u.nivel, "gerir_redes"),
        "pode_gerir_lojas":       perfis.pode(u.nivel, "gerir_lojas"),
        "pode_editar_dados_loja": perfis.pode(u.nivel, "editar_dados_loja"),
    }
```

- [ ] **Step 5: Update the existing slugs test (now 12 profiles)**

Em `tests/test_perfis.py`, substituir `test_slugs_sao_os_dez_perfis` (linhas 4-10) por:

```python
def test_slugs_sao_os_doze_perfis():
    esperado = {
        "diretor", "gerente_vendas", "consultor", "gerente_adm_fin",
        "assistente_logistico", "conferente", "supervisor_montagem",
        "assistente_administrativo", "projetista_executivo", "medidor",
        "super_admin", "admin_rede",
    }
    assert set(perfis.slugs()) == esperado
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_perfis_tenancy.py tests/test_perfis.py -v`
Expected: PASS (todos, incluindo `test_slugs_sao_os_doze_perfis`).

- [ ] **Step 7: Commit**

```bash
git add perfis.py auth.py tests/test_perfis_tenancy.py tests/test_perfis.py
git commit -m "feat(perfis): super_admin/admin_rede + capacidades de tenancy; sessao expoe loja_id/rede_id"
```

---

## Task 2: `mod_tenancy.py` — validadores puros (rede, loja, abrangência)

**Files:**
- Create: `mod_tenancy.py`
- Test: `tests/test_tenancy_validadores.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_validadores.py
import mod_tenancy as mt


def test_validar_rede():
    assert mt.validar_rede({"nome": "Rede A"}) == []
    erros = mt.validar_rede({"nome": "   "})
    assert any("nome" in e.lower() for e in erros)


def test_validar_loja_ok():
    assert mt.validar_loja({"nome": "Loja A1", "codigo": "AAA"}, codigos_existentes=["INS"]) == []


def test_validar_loja_campos_obrigatorios():
    erros = mt.validar_loja({"nome": "", "codigo": ""}, codigos_existentes=[])
    j = " ".join(erros).lower()
    assert "nome" in j and "código" in j


def test_validar_loja_codigo_3_letras():
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "AB"}, []))
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "AB12"}, []))
    assert any("3 letras" in e.lower() for e in
               mt.validar_loja({"nome": "X", "codigo": "12"}, []))


def test_validar_loja_codigo_unico_case_insensitive():
    erros = mt.validar_loja({"nome": "X", "codigo": "ins"}, codigos_existentes=["INS"])
    assert any("existe" in e.lower() for e in erros)


def test_validar_abrangencia_parceiro():
    assert mt.validar_abrangencia_parceiro({"abrangencia": "loja", "lojas": [1]}) == []
    assert mt.validar_abrangencia_parceiro({"abrangencia": "rede", "rede_id": 3}) == []
    # loja sem nenhuma loja selecionada
    assert any("loja" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "loja", "lojas": []}))
    # rede sem rede_id
    assert any("rede" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "rede"}))
    # abrangência inválida
    assert any("abrang" in e.lower() for e in
               mt.validar_abrangencia_parceiro({"abrangencia": "mundo"}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_validadores.py -v`
Expected: FAIL — `mod_tenancy` não existe.

- [ ] **Step 3: Create `mod_tenancy.py` with the pure validators**

```python
# -*- coding: utf-8 -*-
"""mod_tenancy.py — Validações e decisões de escopo (PURAS) da tenancy (F2 multi-tenant).

Sem I/O e sem ORM: recebe dicts simples e devolve listas de erro / tuplas de decisão.
As rotas em main.py fazem o I/O (consultas, gravação) e chamam estas funções.
"""

import re

import perfis

_RE_CODIGO = re.compile(r"^[A-Za-z]{3}$")   # código de loja = exatamente 3 letras


def validar_rede(dados):
    """Erros (lista, vazia se válido) para criar/editar uma rede."""
    erros = []
    if not (dados.get("nome") or "").strip():
        erros.append("Nome da rede é obrigatório.")
    return erros


def validar_loja(dados, codigos_existentes):
    """Erros para criar/editar uma loja. `codigos_existentes` = códigos de OUTRAS lojas
    (na edição, exclua o código da própria loja para não acusar duplicidade)."""
    erros = []
    nome   = (dados.get("nome")   or "").strip()
    codigo = (dados.get("codigo") or "").strip()
    if not nome:
        erros.append("Nome da loja é obrigatório.")
    if not codigo:
        erros.append("Código da loja é obrigatório.")
    elif not _RE_CODIGO.match(codigo):
        erros.append("Código deve ter exatamente 3 letras.")
    existentes = {c.strip().upper() for c in (codigos_existentes or [])}
    if codigo and codigo.upper() in existentes:
        erros.append("Código já existe.")
    return erros


def validar_abrangencia_parceiro(dados):
    """Erros para a abrangência de um parceiro.
    abrangencia ∈ {loja, rede}; 'loja' exige >=1 loja em `dados['lojas']`;
    'rede' exige `dados['rede_id']`."""
    erros = []
    abr = (dados.get("abrangencia") or "loja").strip()
    if abr not in ("loja", "rede"):
        erros.append("Abrangência inválida (use 'loja' ou 'rede').")
        return erros
    if abr == "loja" and not (dados.get("lojas") or []):
        erros.append("Selecione ao menos uma loja.")
    if abr == "rede" and not dados.get("rede_id"):
        erros.append("Rede é obrigatória para abrangência de rede.")
    return erros
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_validadores.py -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_tenancy.py tests/test_tenancy_validadores.py
git commit -m "feat(tenancy): mod_tenancy validadores puros (rede, loja 3-letras, abrangencia)"
```

---

## Task 3: `mod_tenancy.py` — escopo e atribuição de tenant (puros)

**Files:**
- Modify: `mod_tenancy.py` (append)
- Test: `tests/test_tenancy_escopo.py`

> Convenção: **ator** e **loja** são dicts simples. ator = `{"nivel", "loja_id", "rede_id"}`; loja = `{"id", "rede_id"}`. Isso mantém as funções puras e testáveis sem ORM.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_escopo.py
import mod_tenancy as mt

SUPER = {"nivel": "super_admin", "loja_id": None, "rede_id": None}
ADMR  = {"nivel": "admin_rede",  "loja_id": None, "rede_id": 1}
DIR   = {"nivel": "diretor",     "loja_id": 10,   "rede_id": None}

LOJA_R1 = {"id": 10, "rede_id": 1}
LOJA_R2 = {"id": 20, "rede_id": 2}
LOJA_AVULSA = {"id": 30, "rede_id": None}


def test_pode_ver_rede():
    assert mt.pode_ver_rede(SUPER, 1) is True
    assert mt.pode_ver_rede(SUPER, 99) is True
    assert mt.pode_ver_rede(ADMR, 1) is True
    assert mt.pode_ver_rede(ADMR, 2) is False
    assert mt.pode_ver_rede(DIR, 1) is False


def test_pode_ver_loja():
    assert mt.pode_ver_loja(SUPER, LOJA_R2) is True
    assert mt.pode_ver_loja(SUPER, LOJA_AVULSA) is True
    assert mt.pode_ver_loja(ADMR, LOJA_R1) is True       # mesma rede
    assert mt.pode_ver_loja(ADMR, LOJA_R2) is False      # outra rede
    assert mt.pode_ver_loja(ADMR, LOJA_AVULSA) is False  # avulsa não é da rede
    assert mt.pode_ver_loja(DIR, LOJA_R1) is True        # a própria loja (id 10)
    assert mt.pode_ver_loja(DIR, LOJA_R2) is False


def test_pode_editar_dados_loja():
    assert mt.pode_editar_dados_loja(SUPER, LOJA_R2) is True
    assert mt.pode_editar_dados_loja(ADMR, LOJA_R1) is True
    assert mt.pode_editar_dados_loja(ADMR, LOJA_R2) is False
    assert mt.pode_editar_dados_loja(DIR, LOJA_R1) is True    # própria loja
    assert mt.pode_editar_dados_loja(DIR, LOJA_R2) is False
    # consultor não edita dados de loja nenhuma
    consultor = {"nivel": "consultor", "loja_id": 10, "rede_id": None}
    assert mt.pode_editar_dados_loja(consultor, LOJA_R1) is False


def test_atribuir_tenant_super_admin():
    # super_admin cria outro super_admin → ambos NULL
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "super_admin"}) == (None, None, [])
    # super_admin cria admin_rede → rede_id setado, loja_id NULL
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "admin_rede", "rede_id": 5}) == (None, 5, [])
    # admin_rede sem rede → erro
    loja_id, rede_id, erros = mt.atribuir_tenant_usuario(SUPER, {"nivel": "admin_rede"})
    assert erros and rede_id is None
    # super_admin cria usuário de loja → loja_id setado
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "diretor", "loja_id": 30}) == (30, None, [])


def test_atribuir_tenant_admin_rede():
    # admin_rede cria diretor numa loja (validação de "loja é da rede" fica na rota)
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "diretor", "loja_id": 10}) == (10, None, [])
    # admin_rede NÃO cria admin_rede nem super_admin
    _, _, e1 = mt.atribuir_tenant_usuario(ADMR, {"nivel": "admin_rede", "rede_id": 1})
    _, _, e2 = mt.atribuir_tenant_usuario(ADMR, {"nivel": "super_admin"})
    assert e1 and e2


def test_atribuir_tenant_diretor_herda_propria_loja():
    # diretor cria usuário → herda a própria loja, ignora loja_id do payload
    assert mt.atribuir_tenant_usuario(DIR, {"nivel": "consultor", "loja_id": 999}) == (10, None, [])
    # diretor NÃO cria admin_rede/super_admin
    _, _, e = mt.atribuir_tenant_usuario(DIR, {"nivel": "super_admin"})
    assert e
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_escopo.py -v`
Expected: FAIL — funções de escopo não existem em `mod_tenancy`.

- [ ] **Step 3: Append the scope/attribution helpers to `mod_tenancy.py`**

Adicionar ao final de `mod_tenancy.py`:

```python
# ── Escopo e atribuição (puros) ───────────────────────────────────────────────
# ator = {"nivel", "loja_id", "rede_id"}; loja = {"id", "rede_id"}.

def _eh_super_admin(ator):
    return perfis.pode(ator.get("nivel"), "gerir_redes")          # só super_admin tem gerir_redes


def _eh_admin_rede(ator):
    return (perfis.pode(ator.get("nivel"), "gerir_lojas")
            and not _eh_super_admin(ator)
            and ator.get("rede_id") is not None)


def pode_ver_rede(ator, rede_id):
    """super_admin vê qualquer rede; admin_rede só a própria; demais, nenhuma."""
    if _eh_super_admin(ator):
        return True
    if _eh_admin_rede(ator):
        return ator.get("rede_id") == rede_id
    return False


def pode_ver_loja(ator, loja):
    """super_admin vê qualquer loja; admin_rede só lojas da sua rede;
    usuário de loja só a própria."""
    if _eh_super_admin(ator):
        return True
    if _eh_admin_rede(ator):
        return loja.get("rede_id") == ator.get("rede_id")
    if ator.get("loja_id") is not None:
        return loja.get("id") == ator.get("loja_id")
    return False


def pode_editar_dados_loja(ator, loja):
    """Precisa da capacidade editar_dados_loja E enxergar a loja no seu escopo."""
    if not perfis.pode(ator.get("nivel"), "editar_dados_loja"):
        return False
    return pode_ver_loja(ator, loja)


def atribuir_tenant_usuario(ator, dados):
    """Decide (loja_id, rede_id) do NOVO usuário conforme quem cria.
    Retorna (loja_id, rede_id, erros). A checagem de que a loja escolhida pertence
    ao escopo do ator é feita na rota (precisa consultar o banco)."""
    erros = []
    nivel_novo = (dados.get("nivel") or "").strip()

    if _eh_super_admin(ator):
        if nivel_novo == "super_admin":
            return (None, None, erros)
        if nivel_novo == "admin_rede":
            rede_id = dados.get("rede_id")
            if not rede_id:
                erros.append("Rede é obrigatória para admin de rede.")
            return (None, rede_id, erros)
        loja_id = dados.get("loja_id")
        if not loja_id:
            erros.append("Loja é obrigatória.")
        return (loja_id, None, erros)

    if _eh_admin_rede(ator):
        if nivel_novo in ("super_admin", "admin_rede"):
            erros.append("Sem permissão para criar esse perfil.")
            return (None, None, erros)
        loja_id = dados.get("loja_id")
        if not loja_id:
            erros.append("Loja é obrigatória.")
        return (loja_id, None, erros)

    # usuário de loja com gerir_usuarios (diretor / gerente_adm_fin): herda a própria loja
    if perfis.pode(ator.get("nivel"), "gerir_usuarios") and ator.get("loja_id") is not None:
        if nivel_novo in ("super_admin", "admin_rede"):
            erros.append("Sem permissão para criar esse perfil.")
            return (None, None, erros)
        return (ator.get("loja_id"), None, erros)

    erros.append("Sem permissão.")
    return (None, None, erros)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_escopo.py -v`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_tenancy.py tests/test_tenancy_escopo.py
git commit -m "feat(tenancy): helpers puros de escopo e atribuicao de tenant"
```

---

## Task 4: Bootstrap do super_admin — migração `tenancy_v2_2026` + `seed.py`

**Files:**
- Modify: `database.py` (constantes `_SEED_SA_*` + bloco em `_run_migracoes`, ≈ linhas 597)
- Modify: `seed.py`
- Test: `tests/test_tenancy_bootstrap.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tenancy_bootstrap.py
import sqlite3
import database


def _conn_usuarios():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE usuarios (
        id INTEGER PRIMARY KEY, nome TEXT, login TEXT, senha_hash TEXT,
        nivel TEXT, ativo INTEGER, loja_id INTEGER, rede_id INTEGER)""")
    # 'lojas' precisa existir para a migração F1 não barrar; vazia aqui.
    cur.execute("CREATE TABLE lojas (id INTEGER PRIMARY KEY, codigo TEXT)")
    conn.commit()
    return conn


def test_cria_super_admin_bootstrap():
    conn = _conn_usuarios()
    database._run_migracoes(conn)
    rows = conn.execute(
        "SELECT login, nivel, loja_id, rede_id, senha_hash FROM usuarios "
        "WHERE nivel='super_admin'").fetchall()
    assert len(rows) == 1
    login, nivel, loja_id, rede_id, senha_hash = rows[0]
    assert login == database._SEED_SA_LOGIN
    assert loja_id is None and rede_id is None
    assert senha_hash                      # senha gravada (hash não vazio)


def test_bootstrap_idempotente():
    conn = _conn_usuarios()
    database._run_migracoes(conn)
    database._run_migracoes(conn)          # 2ª vez não duplica
    n = conn.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'").fetchone()[0]
    assert n == 1


def test_bootstrap_respeita_super_admin_existente():
    conn = _conn_usuarios()
    conn.execute("INSERT INTO usuarios(nome, login, senha_hash, nivel, ativo) "
                 "VALUES ('Já', 'outro_sa', 'h', 'super_admin', 1)")
    conn.commit()
    database._run_migracoes(conn)
    n = conn.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'").fetchone()[0]
    assert n == 1                          # não cria um segundo
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tenancy_bootstrap.py -v`
Expected: FAIL — nenhum super_admin criado; `_SEED_SA_LOGIN` inexistente.

- [ ] **Step 3: Add bootstrap constants to `database.py`**

Em `database.py`, logo após o bloco de constantes `_SEED_TEST2_CPF` (≈ linha 529), adicionar:

```python
# ── super_admin de bootstrap (F2 multi-tenant) ────────────────────────────────
# Hash SHA-256 do mesmo esquema de Usuario.set_senha (ver abaixo). Senha de exemplo
# ("trocar123") — TROCAR antes de produção. loja_id/rede_id NULL = plataforma.
import hashlib as _hashlib
_SEED_SA_NOME  = "Administrador da Plataforma"
_SEED_SA_LOGIN = "sad2026"
_SEED_SA_SENHA = "trocar123"


def _hash_senha_seed(senha):
    """Mesmo algoritmo de database.Usuario.set_senha (SHA-256 hex)."""
    return _hashlib.sha256(senha.encode("utf-8")).hexdigest()
```

> **Verificar o algoritmo real de `Usuario.set_senha`** antes de aceitar este `_hash_senha_seed`. Abra `database.py` e confirme como `set_senha` deriva o hash (provável `hashlib.sha256(senha.encode()).hexdigest()`, já que `senha_hash = Column(String(64))` cabe um SHA-256 hex). Se houver salt/prefixo, replique-o aqui — o objetivo é que o super_admin consiga logar com `_SEED_SA_SENHA`.

- [ ] **Step 4: Add the migration block to `_run_migracoes`**

Em `database.py`, dentro de `_run_migracoes`, logo após o bloco `tenancy_v1_2026` (após a linha `cur.execute("INSERT INTO schema_migrations(id) VALUES('tenancy_v1_2026')")`, ≈ linha 597) e **antes** de `conn.commit()`:

```python
    # 2026-06-21: F2 multi-tenant — super_admin de bootstrap (plataforma).
    if "tenancy_v2_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        cur.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'")
        if cur.fetchone()[0] == 0:
            cur.execute(
                """INSERT INTO usuarios (nome, login, senha_hash, nivel, ativo, loja_id, rede_id)
                   VALUES (?,?,?, 'super_admin', 1, NULL, NULL)""",
                (_SEED_SA_NOME, _SEED_SA_LOGIN, _hash_senha_seed(_SEED_SA_SENHA)))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('tenancy_v2_2026')")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_tenancy_bootstrap.py -v`
Expected: PASS (3 testes).

- [ ] **Step 6: Make `seed.py` create the super_admin before the loja seed**

Em `seed.py`, na função `seed()` (linhas 42-54), garantir que o super_admin exista após `init_db()` (a migração já o cria em banco novo, mas mantemos explícito e idempotente). Substituir o corpo de `seed()` por:

```python
def seed():
    init_db()                         # cria schema + tenancy_v1 (loja seed) + tenancy_v2 (super_admin)
    db = get_session()
    try:
        from database import Usuario
        import database
        if not db.query(Usuario).filter_by(nivel="super_admin").first():
            sa = Usuario(nome=database._SEED_SA_NOME, login=database._SEED_SA_LOGIN,
                         nivel="super_admin", loja_id=None, rede_id=None)
            sa.set_senha(database._SEED_SA_SENHA)
            db.add(sa); db.commit()
            print(f"  [criado]    {database._SEED_SA_LOGIN} (super_admin)")

        loja_id = loja_seed_id(db)    # a loja seed já existe pela migração
        if loja_id is None:
            print("  [aviso] loja seed nao encontrada; usuarios serao criados sem loja_id.")
        criados = criar_usuarios_seed(db, USUARIOS, loja_id)
        existentes = len(USUARIOS) - criados
        print(f"\n  OK: {criados} usuario(s) criado(s), {existentes} ja existia(m); "
              f"loja seed id={loja_id}.")
    finally:
        db.close()
```

- [ ] **Step 7: Run seed smoke + full bootstrap test**

Run:
```bash
python -m pytest tests/test_tenancy_bootstrap.py tests/test_tenancy_seed.py -v
```
Expected: PASS. (Os testes da F1 em `test_tenancy_seed.py` continuam verdes — o super_admin é criado em separado e não conta como usuário de loja.)

- [ ] **Step 8: Commit**

```bash
git add database.py seed.py tests/test_tenancy_bootstrap.py
git commit -m "feat(tenancy): bootstrap super_admin (migracao tenancy_v2_2026 + seed)"
```

---

## Task 5: Endpoints de redes — `/api/admin/redes` (GET/POST/PATCH)

**Files:**
- Modify: `main.py` (import de `database`; helper `_rede_dict`; rotas em `do_GET`/`do_POST`/`do_PATCH`)
- Verificação: API real (curl) — a lógica pura já está coberta nas Tasks 2-3.

> **Padrão de gate** (copie do `/api/admin/usuarios`): obtém `usuario = get_usuario_sessao(self)`, checa `perfis.pode(usuario.get("nivel"), <capacidade>)`, senão `self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)`.

- [ ] **Step 1: Add `Rede, Loja, ParceiroLoja` to the database import**

Em `main.py`, no import de `database` (linhas 12-15), acrescentar `Rede, Loja, ParceiroLoja`:

```python
from database import (init_db, get_session, Cliente, Parceiro, Orcamento,
                       PoolAmbiente, OrcamentoAmbiente, Projeto, upsert_projeto_status,
                       CicloEtapa, Contrato, ContratoAssinatura, Usuario, Briefing,
                       LogAcaoGerencial, Medicao, Rede, Loja, ParceiroLoja)
```

Confirmar que `import mod_tenancy` está disponível; se `main.py` ainda não importa, adicionar junto aos demais imports de módulos `mod_*` no topo:

```python
import mod_tenancy
```

- [ ] **Step 2: Add the `_rede_dict` serializer**

Em `main.py`, junto aos serializadores (após `_parceiro_dict`, ≈ linha 3329), adicionar:

```python
def _rede_dict(r) -> dict:
    return {
        "id":        r.id,
        "nome":      r.nome,
        "cnpj":      r.cnpj or "",
        "ativo":     bool(r.ativo),
        "criado_em": r.criado_em.strftime("%Y-%m-%d") if r.criado_em else "",
    }
```

- [ ] **Step 3: Add `GET /api/admin/redes` in `do_GET`**

Em `main.py`, dentro de `do_GET`, logo após o bloco `elif path == "/api/admin/usuarios":` (≈ linha 446), adicionar:

```python
        elif path == "/api/admin/redes":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                redes = db.query(Rede).order_by(Rede.nome).all()
                self.send_json({"ok": True, "redes": [_rede_dict(r) for r in redes]})
            finally:
                db.close()
```

- [ ] **Step 4: Add `POST /api/admin/redes` in `do_POST`**

Em `main.py`, dentro de `do_POST`, logo após o bloco `if path == "/api/admin/usuarios":` (≈ linha 2115), adicionar:

```python
        if path == "/api/admin/redes":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            erros = mod_tenancy.validar_rede(req)
            if erros:
                self.send_json({"ok": False, "erro": " ".join(erros)})
                return
            db = get_session()
            try:
                r = Rede(nome=req["nome"].strip(),
                         cnpj=(req.get("cnpj") or "").strip() or None)
                db.add(r); db.commit()
                self.send_json({"ok": True, "rede": _rede_dict(r)})
            finally:
                db.close()
            return
```

- [ ] **Step 5: Add `PATCH /api/admin/redes/{id}` in `do_PATCH`**

Em `main.py`, dentro de `do_PATCH` (≈ linha 2814), junto aos demais `re.match` de PATCH, adicionar:

```python
        m_rede = re.match(r"^/api/admin/redes/(\d+)$", path)
        if m_rede:
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_redes"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                r = db.get(Rede, int(m_rede.group(1)))
                if not r:
                    self.send_json({"ok": False, "erro": "Rede não encontrada"}, code=404)
                    return
                if "nome" in req:
                    nome = (req["nome"] or "").strip()
                    if not nome:
                        self.send_json({"ok": False, "erro": "Nome da rede é obrigatório."})
                        return
                    r.nome = nome
                if "cnpj" in req:  r.cnpj  = (req["cnpj"] or "").strip() or None
                if "ativo" in req: r.ativo = 1 if req["ativo"] else 0
                db.commit()
                self.send_json({"ok": True, "rede": _rede_dict(r)})
            finally:
                db.close()
            return
```

> Confirme, ao abrir `do_PATCH`, o **estilo de indentação e despacho** já usado (ex.: `m_user = re.match(r"^/api/admin/usuarios/(\d+)$", path)`); replique exatamente o mesmo padrão para evitar quebrar o roteamento.

- [ ] **Step 6: Verify with the real API (curl)**

Run (servidor reiniciado, autenticado como super_admin via cookie — ver Task 10 para login):
```bash
# criar
curl -s -X POST localhost:8000/api/admin/redes -H 'Content-Type: application/json' \
  -b cookies.txt -d '{"nome":"Rede Teste","cnpj":"00.000.000/0001-00"}'
# listar
curl -s localhost:8000/api/admin/redes -b cookies.txt
```
Expected: POST devolve `{"ok": true, "rede": {...}}`; GET lista a rede criada. Sem cookie de super_admin → `403 Acesso negado`.

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat(api): /api/admin/redes (GET/POST/PATCH) com gate gerir_redes"
```

---

## Task 6: Endpoints de lojas — `/api/admin/lojas` (GET/POST/PATCH) com escopo + dados da loja

**Files:**
- Modify: `main.py` (helper `_loja_dict`; rotas em `do_GET`/`do_POST`/`do_PATCH`)
- Verificação: API real (curl).

> **Escopo:** super_admin vê/edita qualquer loja; admin_rede só lojas da sua `rede_id`; diretor/adm-fin só PATCH dos dados da **própria** loja. Use `mod_tenancy.pode_ver_loja` / `mod_tenancy.pode_editar_dados_loja`, montando os dicts a partir do ator (re-consultado no banco) e da loja.

- [ ] **Step 1: Add the `_loja_dict` serializer and an `_ator_dict` helper**

Em `main.py`, após `_rede_dict`, adicionar:

```python
def _loja_dict(l) -> dict:
    return {
        "id":          l.id,
        "rede_id":     l.rede_id,
        "nome":        l.nome,
        "cnpj":        l.cnpj        or "",
        "codigo":      l.codigo      or "",
        "telefone":    l.telefone    or "",
        "email":       l.email       or "",
        "cep":         l.cep         or "",
        "logradouro":  l.logradouro  or "",
        "numero":      l.numero      or "",
        "complemento": l.complemento or "",
        "bairro":      l.bairro      or "",
        "cidade":      l.cidade      or "",
        "estado":      l.estado      or "",
        "testemunha1_nome": l.testemunha1_nome or "",
        "testemunha1_cpf":  l.testemunha1_cpf  or "",
        "testemunha2_nome": l.testemunha2_nome or "",
        "testemunha2_cpf":  l.testemunha2_cpf  or "",
        "ativo":       bool(l.ativo),
        "criado_em":   l.criado_em.strftime("%Y-%m-%d") if l.criado_em else "",
    }


def _ator_dict(db, usuario_sessao):
    """Re-consulta o usuário logado no banco para obter nivel/loja_id/rede_id frescos
    (a sessão pode ter sido emitida antes de uma mudança). Retorna dict p/ mod_tenancy."""
    u = db.get(Usuario, usuario_sessao.get("id"))
    if not u:
        return {"nivel": usuario_sessao.get("nivel"), "loja_id": None, "rede_id": None}
    return {"nivel": u.nivel, "loja_id": u.loja_id, "rede_id": u.rede_id}
```

- [ ] **Step 2: Add `GET /api/admin/lojas` (scoped) in `do_GET`**

Em `main.py`, em `do_GET`, logo após o bloco `elif path == "/api/admin/redes":` (Task 5), adicionar:

```python
        elif path == "/api/admin/lojas":
            usuario = get_usuario_sessao(self)
            if not usuario or not (perfis.pode(usuario.get("nivel"), "gerir_lojas")
                                   or perfis.pode(usuario.get("nivel"), "editar_dados_loja")):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            from urllib.parse import parse_qs   # urlparse já é importado no topo do main.py
            rede_q = (parse_qs(urlparse(self.path).query).get("rede_id") or [""])[0].strip()
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                q = db.query(Loja)
                if rede_q == "avulsas":
                    q = q.filter(Loja.rede_id.is_(None))
                elif rede_q:
                    if not rede_q.isdigit():
                        self.send_json({"ok": False, "erro": "rede_id inválido"}, code=400)
                        return
                    q = q.filter(Loja.rede_id == int(rede_q))
                lojas = [l for l in q.order_by(Loja.nome).all()
                         if mod_tenancy.pode_ver_loja(
                             ator, {"id": l.id, "rede_id": l.rede_id})]
                self.send_json({"ok": True, "lojas": [_loja_dict(l) for l in lojas]})
            finally:
                db.close()
```

- [ ] **Step 3: Add `POST /api/admin/lojas` (create, gate gerir_lojas) in `do_POST`**

Em `main.py`, em `do_POST`, após o bloco `POST /api/admin/redes` (Task 5), adicionar:

```python
        if path == "/api/admin/lojas":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_lojas"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                codigos = [c for (c,) in db.query(Loja.codigo).all() if c]
                erros = mod_tenancy.validar_loja(req, codigos)
                # admin_rede só cria loja na própria rede; super_admin escolhe a rede (ou avulsa)
                rede_id = req.get("rede_id")
                if not mod_tenancy._eh_super_admin(ator):
                    rede_id = ator.get("rede_id")          # admin_rede: força a própria rede
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                l = Loja(
                    nome=req["nome"].strip(),
                    codigo=req["codigo"].strip().upper(),
                    rede_id=rede_id,
                    cnpj=(req.get("cnpj") or "").strip() or None,
                    telefone=(req.get("telefone") or "").strip() or None,
                    email=(req.get("email") or "").strip() or None,
                )
                db.add(l); db.commit()
                self.send_json({"ok": True, "loja": _loja_dict(l)})
            finally:
                db.close()
            return
```

- [ ] **Step 4: Add `PATCH /api/admin/lojas/{id}` (scoped edit of loja data) in `do_PATCH`**

Em `main.py`, em `do_PATCH`, junto aos demais `re.match`, adicionar:

```python
        m_loja = re.match(r"^/api/admin/lojas/(\d+)$", path)
        if m_loja:
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            db = get_session()
            try:
                l = db.get(Loja, int(m_loja.group(1)))
                if not l:
                    self.send_json({"ok": False, "erro": "Loja não encontrada"}, code=404)
                    return
                ator = _ator_dict(db, usuario)
                loja_d = {"id": l.id, "rede_id": l.rede_id}
                if not mod_tenancy.pode_editar_dados_loja(ator, loja_d):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                # código (se enviado) é validado e precisa ser único entre OUTRAS lojas
                if "codigo" in req:
                    outros = [c for (c,) in db.query(Loja.codigo)
                                            .filter(Loja.id != l.id).all() if c]
                    erros = mod_tenancy.validar_loja(
                        {"nome": req.get("nome", l.nome), "codigo": req["codigo"]}, outros)
                    if erros:
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                    l.codigo = req["codigo"].strip().upper()
                for campo in ("nome", "cnpj", "telefone", "email", "cep", "logradouro",
                              "numero", "complemento", "bairro", "cidade", "estado",
                              "testemunha1_nome", "testemunha1_cpf",
                              "testemunha2_nome", "testemunha2_cpf"):
                    if campo in req:
                        val = (req[campo] or "").strip() or None
                        if campo == "nome" and not val:
                            self.send_json({"ok": False, "erro": "Nome da loja é obrigatório."})
                            return
                        setattr(l, campo, val)
                # rede_id e ativo só super_admin/admin_rede (gerir_lojas) mexem
                if perfis.pode(ator.get("nivel"), "gerir_lojas"):
                    if "ativo" in req:   l.ativo = 1 if req["ativo"] else 0
                    if "rede_id" in req and mod_tenancy._eh_super_admin(ator):
                        l.rede_id = req["rede_id"]
                db.commit()
                self.send_json({"ok": True, "loja": _loja_dict(l)})
            finally:
                db.close()
            return
```

- [ ] **Step 5: Verify with the real API (curl)**

Run:
```bash
# super_admin: editar dados da loja seed (id 1), incluindo CPF de testemunha
curl -s -X PATCH localhost:8000/api/admin/lojas/1 -H 'Content-Type: application/json' \
  -b cookies.txt -d '{"testemunha1_cpf":"123.456.789-00"}'
# listar lojas avulsas
curl -s 'localhost:8000/api/admin/lojas?rede_id=avulsas' -b cookies.txt
```
Expected: PATCH devolve `{"ok": true, "loja": {... "testemunha1_cpf":"123.456.789-00"}}`; a loja seed (INS) aparece em `rede_id=avulsas`. Diretor de outra loja → `403` ao tentar PATCH na loja 1.

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat(api): /api/admin/lojas (GET/POST/PATCH) com escopo + edicao dos dados da loja"
```

---

## Task 7: Usuários — atribuição de tenant na criação + escopo na listagem

**Files:**
- Modify: `main.py` (`GET /api/admin/usuarios` ≈ 433-446; `POST /api/admin/usuarios` ≈ 2094-2115)
- Verificação: API real (curl).

- [ ] **Step 1: Scope the user listing (`GET /api/admin/usuarios`)**

Em `main.py`, substituir o corpo do `elif path == "/api/admin/usuarios":` em `do_GET` (≈ linhas 433-446) por uma versão com escopo, mantendo o shape de resposta atual e adicionando `loja_id`/`rede_id`:

```python
        elif path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                us = db.query(Usuario).order_by(Usuario.nome).all()
                # pré-carrega rede_id de cada loja referenciada (evita N+1 no loop de escopo)
                loja_ids = {u.loja_id for u in us if u.loja_id is not None}
                rede_de_loja = {l.id: l.rede_id for l in
                                db.query(Loja).filter(Loja.id.in_(loja_ids)).all()} if loja_ids else {}
                visiveis = []
                for u in us:
                    if mod_tenancy._eh_super_admin(ator):
                        ok = True
                    elif mod_tenancy._eh_admin_rede(ator):
                        # usuários da rede do ator: por loja da rede, ou admin_rede da mesma rede
                        ok = (u.rede_id == ator["rede_id"]) or (
                            u.loja_id is not None and mod_tenancy.pode_ver_loja(
                                ator, {"id": u.loja_id, "rede_id": rede_de_loja.get(u.loja_id)}))
                    else:
                        ok = (u.loja_id is not None and u.loja_id == ator.get("loja_id"))
                    if ok:
                        visiveis.append(u)
                self.send_json({"ok": True, "usuarios": [
                    {"id": u.id, "nome": u.nome, "login": u.login, "nivel": u.nivel,
                     "rotulo": perfis.rotulo(u.nivel), "telefone": u.telefone or "",
                     "loja_id": u.loja_id, "rede_id": u.rede_id,
                     "ativo": bool(u.ativo)} for u in visiveis]})
            finally:
                db.close()
```

- [ ] **Step 2: Apply tenant attribution on user creation (`POST /api/admin/usuarios`)**

Em `main.py`, substituir o corpo do `if path == "/api/admin/usuarios":` em `do_POST` (≈ linhas 2094-2115) por:

```python
        if path == "/api/admin/usuarios":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                return
            req = json.loads(body) if body else {}
            db  = get_session()
            try:
                logins = [u.login for u in db.query(Usuario.login).all()]
                erros  = mod_usuarios.validar_novo_usuario(req, logins)
                ator   = _ator_dict(db, usuario)
                loja_id, rede_id, erros_tenant = mod_tenancy.atribuir_tenant_usuario(ator, req)
                erros = erros + erros_tenant
                # admin_rede/diretor: a loja escolhida precisa estar no escopo do ator
                if not erros and loja_id is not None and not mod_tenancy._eh_super_admin(ator):
                    loja = db.get(Loja, loja_id)
                    if not loja or not mod_tenancy.pode_ver_loja(
                            ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        erros = erros + ["Loja fora do seu escopo."]
                if erros:
                    self.send_json({"ok": False, "erro": " ".join(erros)})
                    return
                u = Usuario(nome=req["nome"].strip(), login=req["login"].strip(),
                            nivel=req["nivel"].strip(),
                            telefone=(req.get("telefone") or "").strip(),
                            loja_id=loja_id, rede_id=rede_id)
                u.set_senha(req["senha"])
                db.add(u); db.commit()
                self.send_json({"ok": True, "id": u.id})
            finally:
                db.close()
            return
```

> **Segurança (achado no review final):** o `PATCH /api/admin/usuarios/{id}` **precisa** carregar escopo + anti-escalonamento, senão um diretor pode promover qualquer usuário a `super_admin`/`admin_rede` (takeover) ou editar usuários de outras lojas/redes. O handler agora: (1) re-consulta o alvo e exige que o ator o enxergue (mesma regra da listagem — `_eh_super_admin`/`_eh_admin_rede`/`loja_id`); (2) rejeita atribuir `nivel ∈ {super_admin, admin_rede}` para quem não é super_admin. Atribuição de loja/rede de um usuário existente segue fora do escopo F2 (a atribuição acontece na criação).

- [ ] **Step 3: Verify with the real API (curl)**

Run:
```bash
# super_admin cria um admin_rede para a Rede Teste (id da rede criada na Task 5)
curl -s -X POST localhost:8000/api/admin/usuarios -H 'Content-Type: application/json' \
  -b cookies.txt -d '{"nome":"Admin Rede","login":"ar2026","senha":"x","nivel":"admin_rede","rede_id":1}'
# listar (super_admin vê todos)
curl -s localhost:8000/api/admin/usuarios -b cookies.txt
```
Expected: cria com `rede_id=1`, `loja_id=null`. Como **diretor** (cookie da loja seed), criar usuário → herda `loja_id` da loja seed e ignora `rede_id`/`loja_id` do payload; listagem do diretor mostra só usuários da própria loja.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(api): /api/admin/usuarios com atribuicao de tenant + escopo na listagem"
```

---

## Task 8: Parceiros — abrangência (loja × rede) + vínculos M:N

**Files:**
- Modify: `main.py` (`POST /api/parceiros` ≈ 1470-1496; `POST /api/parceiros/{id}/editar` ≈ 1498-1522; `_parceiro_dict` ≈ 3317-3329)
- Verificação: API real (curl).

> **Regra (spec):** abrangência `'loja'` → grava `parceiros.abrangencia='loja'` e cria N vínculos em `parceiro_lojas` (um por loja escolhida, com `comissao_padrao_pct` por loja). Abrangência `'rede'` → grava `abrangencia='rede'` + `rede_id` + `comissao_padrao_pct` padrão. **Diretor pode criar ambos.** Escopo: só lojas visíveis ao ator.

- [ ] **Step 1: Extend `_parceiro_dict` with abrangência + vínculos**

Em `main.py`, substituir `_parceiro_dict` (≈ linhas 3317-3329) por uma versão que aceita a sessão `db` para listar os vínculos:

```python
def _parceiro_dict(p, db=None) -> dict:
    d = {
        "id":                  p.id,
        "nome":                p.nome,
        "cpf_cnpj":            p.cpf_cnpj            or "",
        "tipo":                p.tipo                 or "",
        "email":               p.email                or "",
        "telefone":            p.telefone             or "",
        "whatsapp":            p.whatsapp             or "",
        "comissao_padrao_pct": p.comissao_padrao_pct  if p.comissao_padrao_pct is not None else 0.0,
        "observacoes":         p.observacoes          or "",
        "abrangencia":         p.abrangencia          or "loja",
        "rede_id":             p.rede_id,
        "criado_em":           p.criado_em.strftime("%Y-%m-%d") if p.criado_em else "",
        "lojas":               [],
    }
    if db is not None:
        vincs = db.query(ParceiroLoja).filter_by(parceiro_id=p.id).all()
        d["lojas"] = [{"loja_id": v.loja_id,
                       "comissao_padrao_pct": v.comissao_padrao_pct or 0.0}
                      for v in vincs]
    return d
```

> **Atenção (consistência):** todas as chamadas existentes a `_parceiro_dict(p)` continuam válidas (o `db` é opcional). Para incluir os vínculos na resposta, passe `db`: `_parceiro_dict(p, db)`. Atualize as chamadas de `POST /api/parceiros`, `POST /api/parceiros/{id}/editar`, `GET /api/parceiros/{id}` e a listagem `GET /api/parceiros` para passarem `db`.

- [ ] **Step 2: Helper to persist abrangência + M:N links**

Em `main.py`, junto aos serializadores, adicionar um helper que grava abrangência e sincroniza `parceiro_lojas` (filtrando lojas pelo escopo do ator):

```python
def _aplicar_abrangencia_parceiro(db, p, req, ator):
    """Grava abrangencia/rede_id no parceiro e sincroniza os vínculos parceiro_lojas.
    Retorna lista de erros (vazia se ok). Só vincula lojas visíveis ao ator."""
    erros = mod_tenancy.validar_abrangencia_parceiro(req)
    if erros:
        return erros
    abr = (req.get("abrangencia") or "loja").strip()
    p.abrangencia = abr
    if abr == "rede":
        rede_id = req.get("rede_id")
        p.rede_id = rede_id
        # super_admin/admin_rede via política pura; o diretor pode a rede da PRÓPRIA loja
        # (spec decisão #4: o diretor também cria parceiro de abrangência 'rede').
        permitido = mod_tenancy.pode_ver_rede(ator, rede_id)
        if not permitido and ator.get("loja_id") is not None and rede_id is not None:
            loja_ator = db.get(Loja, ator.get("loja_id"))
            permitido = bool(loja_ator and loja_ator.rede_id == rede_id)
        if not permitido:
            return ["Rede fora do seu escopo."]
        # abrangência de rede não usa vínculos por loja: limpa os antigos
        db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
        return []
    # abrangência de loja: substitui vínculos pelos enviados (só lojas visíveis)
    p.rede_id = None
    lojas_req = req.get("lojas") or []   # [{"loja_id": int, "comissao_padrao_pct": float}]
    db.query(ParceiroLoja).filter_by(parceiro_id=p.id).delete()
    for item in lojas_req:
        lid = item.get("loja_id")
        loja = db.get(Loja, lid) if lid else None
        if not loja or not mod_tenancy.pode_ver_loja(
                ator, {"id": loja.id, "rede_id": loja.rede_id}):
            return [f"Loja {lid} fora do seu escopo."]
        db.add(ParceiroLoja(parceiro_id=p.id, loja_id=lid,
                            comissao_padrao_pct=float(item.get("comissao_padrao_pct") or 0),
                            ativo=1))
    return []
```

- [ ] **Step 3: Wire abrangência into `POST /api/parceiros` (create)**

Em `main.py`, no bloco `elif path == "/api/parceiros":` do `do_POST` (≈ 1470-1496), após `db.add(p); db.commit(); db.refresh(p)` e **antes** de serializar, aplicar a abrangência (precisa do `id` já gravado):

```python
        elif path == "/api/parceiros":
            usuario = get_usuario_sessao(self)
            req  = json.loads(body) if body else {}
            nome = (req.get("nome") or "").strip()
            if not nome:
                self.send_json({"ok": False, "erro": "Nome é obrigatório"})
                return
            db = get_session()
            try:
                p = Parceiro(
                    nome                =nome,
                    cpf_cnpj            =(req.get("cpf_cnpj")            or "").strip() or None,
                    tipo                =(req.get("tipo")                or "").strip() or None,
                    email               =(req.get("email")               or "").strip() or None,
                    telefone            =(req.get("telefone")            or "").strip() or None,
                    whatsapp            =(req.get("whatsapp")            or "").strip() or None,
                    comissao_padrao_pct =float(req.get("comissao_padrao_pct") or 0),
                    observacoes         =(req.get("observacoes")         or "").strip() or None,
                )
                db.add(p)
                db.flush()        # atribui p.id sem efetivar — transação única e atômica
                if "abrangencia" in req:
                    ator = _ator_dict(db, usuario) if usuario else {"nivel": "", "loja_id": None, "rede_id": None}
                    erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                    if erros:
                        db.rollback()    # desfaz tudo, inclusive o INSERT do parceiro
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
            except Exception as e:
                db.rollback()
                self.send_json({"ok": False, "erro": str(e)})
            finally:
                db.close()
```

> Se `req` não trouxer `abrangencia`/`lojas` (ex.: cadastro rápido legado), `validar_abrangencia_parceiro` exige ao menos uma loja para `'loja'`. Para **não quebrar** o cadastro rápido existente do front (que ainda não envia abrangência), o front passará a enviar sempre `abrangencia` + `lojas` (Task 9). Confirme no front que o payload novo é enviado antes de mergear esta task; alternativamente, defaulte `lojas` para a loja do ator quando ausente — decida no review com o estado real do front.

- [ ] **Step 4: Wire abrangência into `POST /api/parceiros/{id}/editar`**

Em `main.py`, no bloco de edição (≈ 1498-1522), após atualizar os campos simples e antes do `db.commit()` final, aplicar a abrangência se enviada:

```python
                if "abrangencia" in req:
                    ator = _ator_dict(db, usuario) if usuario else {"nivel": "", "loja_id": None, "rede_id": None}
                    erros = _aplicar_abrangencia_parceiro(db, p, req, ator)
                    if erros:
                        db.rollback()
                        self.send_json({"ok": False, "erro": " ".join(erros)})
                        return
                db.commit()
                db.refresh(p)
                self.send_json({"ok": True, "parceiro": _parceiro_dict(p, db)})
```

> Garanta que `usuario = get_usuario_sessao(self)` seja obtido no topo do bloco de edição (hoje ele não usa sessão). Adicione a linha logo após o `req = json.loads(...)`.

- [ ] **Step 5: Verify with the real API (curl)**

Run:
```bash
# parceiro de abrangência loja, vinculado à loja seed (id 1) com comissão 7%
curl -s -X POST localhost:8000/api/parceiros -H 'Content-Type: application/json' -b cookies.txt \
  -d '{"nome":"Arq X","abrangencia":"loja","lojas":[{"loja_id":1,"comissao_padrao_pct":7}]}'
# parceiro de abrangência rede (como diretor — permitido)
curl -s -X POST localhost:8000/api/parceiros -H 'Content-Type: application/json' -b cookies.txt \
  -d '{"nome":"Designer Y","abrangencia":"rede","rede_id":1,"comissao_padrao_pct":5}'
```
Expected: 1º devolve `parceiro` com `abrangencia="loja"` e `lojas=[{"loja_id":1,"comissao_padrao_pct":7.0}]`; 2º com `abrangencia="rede"`, `rede_id=1`. Vincular loja fora do escopo → erro "fora do seu escopo".

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat(api): cadastro de parceiro com abrangencia loja/rede + vinculos M:N escopados"
```

---

## Task 9: Frontend — `page-07` em 3 consoles (Plataforma/Rede/Loja) + dados da loja + abrangência

**Files:**
- Modify: `static/index.html` (`page-07` HTML ≈ 1219-1240; navegação `goPage` ≈ 2125-2143; bloco `<script>` de admin ≈ 6199-6252; modal de parceiro ≈ 1243-1311; `parSalvar` ≈ 6121-6162)
- Verificação: Playwright na Task 10.

> **Princípio:** preservar o caminho atual do diretor/adm-fin para "Usuários da loja". O console renderiza o nível conforme `_usuarioAtual` (já traz `nivel`/`loja_id`/`rede_id`/`pode_*` após a Task 1) + um estado de navegação (`_adminNav`). Reaproveitar `goPage`, `fetch`, `showToast`, `avisoPopup` e as classes `.cli-table`/`.card`/`.btn` existentes.

- [ ] **Step 1: Replace the `page-07` HTML with a console shell (breadcrumb + level container)**

Em `static/index.html`, substituir o conteúdo de `<div class="page" id="page-07"> … </div>` (≈ linhas 1219-1240) por:

```html
<div class="page" id="page-07">
  <div class="page-title">⚙️ Administração</div>
  <!-- breadcrumb: preenchido por adminRender() conforme o nível atual -->
  <div id="admin-breadcrumb" style="font-size:12px;color:var(--muted);margin-bottom:14px"></div>
  <!-- container único; adminRender() injeta o nível N1/N2/N3 -->
  <div id="admin-console"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
  <!-- mantém a fila Omie existente (não mexer) -->
  <div class="page-sub" style="margin-top:24px">Monitoramento e sincronização Omie</div>
  <div id="admin-omie-fila"></div>
</div>
```

> Se a "fila Omie" original tinha markup/ids específicos entre as linhas 1228-1240, **preserve-os** dentro deste `page-07` (mova-os para baixo do `#admin-console`). Confira o trecho real antes de substituir e mantenha `adminCarregar()` (a função da fila Omie) funcionando.

- [ ] **Step 2: Add the admin console state + router JS**

Em `static/index.html`, dentro do bloco `<script>` (junto às funções `adminUsuarios*`, ≈ linha 6199), adicionar o estado e o roteador de nível:

```javascript
// ── Console administrativo (F2 multi-tenant) ──────────────────────────────────
let _adminNav = { nivel: 1, rede: null, loja: null };   // rede/loja = {id, nome}

function adminCarregarConsole(){
  // aterrissagem por perfil
  const u = _usuarioAtual || {};
  if (u.pode_gerir_redes)            _adminNav = { nivel: 1, rede: null, loja: null };
  else if (u.pode_gerir_lojas && u.rede_id)
                                     _adminNav = { nivel: 2, rede: { id: u.rede_id, nome: '' }, loja: null };
  else if (u.loja_id)               _adminNav = { nivel: 3, rede: null, loja: { id: u.loja_id, nome: '' } };
  else                              _adminNav = { nivel: 3, rede: null, loja: null };
  adminRender();
}

function adminBreadcrumb(){
  const parts = ['<span onclick="adminIrNivel(1)" style="cursor:pointer">Plataforma</span>'];
  if (_adminNav.rede) parts.push(`<span onclick="adminIrNivel(2)" style="cursor:pointer">Rede ${esc(_adminNav.rede.nome||_adminNav.rede.id)}</span>`);
  if (_adminNav.loja) parts.push(`<span>Loja ${esc(_adminNav.loja.nome||_adminNav.loja.id)}</span>`);
  document.getElementById('admin-breadcrumb').innerHTML = parts.join(' › ');
}

function adminIrNivel(n){
  if (n === 1) { _adminNav.rede = null; _adminNav.loja = null; }
  if (n === 2) { _adminNav.loja = null; }
  _adminNav.nivel = n;
  adminRender();
}

function adminEntrarRede(id, nome){ _adminNav.rede = { id, nome }; _adminNav.nivel = 2; _adminNav.loja = null; adminRender(); }
function adminEntrarLoja(id, nome){ _adminNav.loja = { id, nome }; _adminNav.nivel = 3; adminRender(); }

function adminRender(){
  adminBreadcrumb();
  const box = document.getElementById('admin-console');
  if (_adminNav.nivel === 1)      adminRenderPlataforma(box);
  else if (_adminNav.nivel === 2) adminRenderRede(box);
  else                            adminRenderLoja(box);
}
```

- [ ] **Step 3: Nível 1 (Plataforma) — redes, lojas avulsas, admins de rede**

Adicionar:

```javascript
async function adminRenderPlataforma(box){
  box.innerHTML = '<em style="color:var(--muted);font-size:12px">Carregando…</em>';
  const [redes, avulsas] = await Promise.all([
    fetch('/api/admin/redes', {credentials:'same-origin'}).then(r=>r.json()).catch(()=>({redes:[]})),
    fetch('/api/admin/lojas?rede_id=avulsas', {credentials:'same-origin'}).then(r=>r.json()).catch(()=>({lojas:[]})),
  ]);
  box.innerHTML = `
    <div class="card" style="padding:14px 16px">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
        <strong style="color:var(--dalm-gold,#c8a84b)">🏢 Redes</strong>
        <button class="btn btn-ghost btn-sm" onclick="adminRedeNova()" style="font-size:11px">+ Nova rede</button>
      </div>
      <table class="cli-table"><thead><tr><th>Nome</th><th>CNPJ</th><th></th></tr></thead><tbody>
      ${(redes.redes||[]).map(r=>`<tr>
        <td>${esc(r.nome)}</td><td style="color:var(--muted)">${esc(r.cnpj||'—')}</td>
        <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
          onclick="adminEntrarRede(${r.id}, ${JSON.stringify(r.nome)})">Entrar ›</button></td></tr>`).join('')
        || '<tr><td colspan="3" style="color:var(--muted)">Nenhuma rede.</td></tr>'}
      </tbody></table>
    </div>
    <div class="card" style="padding:14px 16px">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
        <strong style="color:var(--dalm-gold,#c8a84b)">🏪 Lojas avulsas</strong>
        <button class="btn btn-ghost btn-sm" onclick="adminLojaNova(null)" style="font-size:11px">+ Nova loja avulsa</button>
      </div>
      <table class="cli-table"><thead><tr><th>Nome</th><th>Código</th><th></th></tr></thead><tbody>
      ${(avulsas.lojas||[]).map(l=>`<tr>
        <td>${esc(l.nome)}</td><td style="color:var(--muted)">${esc(l.codigo||'—')}</td>
        <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
          onclick="adminEntrarLoja(${l.id}, ${JSON.stringify(l.nome)})">Entrar ›</button></td></tr>`).join('')
        || '<tr><td colspan="3" style="color:var(--muted)">Nenhuma loja avulsa.</td></tr>'}
      </tbody></table>
    </div>`;
}

async function adminRedeNova(){
  const nome = prompt('Nome da rede:'); if(!nome) return;
  const cnpj = prompt('CNPJ (opcional):') || '';
  const r = await fetch('/api/admin/redes', {method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify({nome, cnpj})});
  const d = await r.json();
  if(!d.ok){ await avisoPopup(d.erro||'Erro', {titulo:'Redes'}); return; }
  showToast('Rede criada.', false); adminRender();
}
```

- [ ] **Step 4: Nível 2 (Rede) — dados da rede, lojas da rede, diretores**

Adicionar:

```javascript
async function adminRenderRede(box){
  const rid = _adminNav.rede?.id;
  box.innerHTML = '<em style="color:var(--muted);font-size:12px">Carregando…</em>';
  const lojas = await fetch('/api/admin/lojas?rede_id='+rid, {credentials:'same-origin'})
    .then(r=>r.json()).catch(()=>({lojas:[]}));
  box.innerHTML = `
    <div class="card" style="padding:14px 16px">
      <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px">
        <strong style="color:var(--dalm-gold,#c8a84b)">🏪 Lojas da rede</strong>
        <button class="btn btn-ghost btn-sm" onclick="adminLojaNova(${rid})" style="font-size:11px">+ Nova loja</button>
      </div>
      <table class="cli-table"><thead><tr><th>Nome</th><th>Código</th><th></th></tr></thead><tbody>
      ${(lojas.lojas||[]).map(l=>`<tr>
        <td>${esc(l.nome)}</td><td style="color:var(--muted)">${esc(l.codigo||'—')}</td>
        <td style="text-align:right"><button class="btn btn-ghost btn-sm" style="font-size:10px"
          onclick="adminEntrarLoja(${l.id}, ${JSON.stringify(l.nome)})">Entrar ›</button></td></tr>`).join('')
        || '<tr><td colspan="3" style="color:var(--muted)">Nenhuma loja nesta rede.</td></tr>'}
      </tbody></table>
    </div>`;
}

async function adminLojaNova(redeId){
  const nome   = prompt('Nome da loja:'); if(!nome) return;
  const codigo = prompt('Código (3 letras, único — usado na numeração do contrato):'); if(!codigo) return;
  const body = { nome, codigo };
  if (redeId) body.rede_id = redeId;
  const r = await fetch('/api/admin/lojas', {method:'POST', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  if(!d.ok){ await avisoPopup(d.erro||'Erro', {titulo:'Lojas'}); return; }
  showToast('Loja criada.', false); adminRender();
}
```

- [ ] **Step 5: Nível 3 (Loja) — dados da loja, usuários da loja (CRUD atual), parceiros**

Adicionar (a sub-aba "Usuários da loja" reusa `adminUsuariosCarregar()`/`adminUsuariosNovo()` já existentes; a sub-aba "Dados da loja" usa um form que faz PATCH em `/api/admin/lojas/{id}`):

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
      <button class="btn btn-ghost btn-sm" onclick="adminUsuariosNovo()" style="font-size:11px">+ Novo usuário</button>
      <div id="admin-usuarios-lista" style="margin-top:10px"><em style="color:var(--muted);font-size:12px">Carregando…</em></div>
    </div>`;
  adminLojaCarregarDados(lid);
  adminUsuariosCarregar();   // popula #admin-usuarios-lista (função já existente)
}

function adminLojaTab(qual){
  document.getElementById('loja-tab-dados').classList.toggle('ativo', qual==='dados');
  document.getElementById('loja-tab-usuarios').classList.toggle('ativo', qual==='usuarios');
  document.getElementById('loja-panel-dados').style.display    = qual==='dados' ? '' : 'none';
  document.getElementById('loja-panel-usuarios').style.display = qual==='usuarios' ? '' : 'none';
}

async function adminLojaCarregarDados(lid){
  const panel = document.getElementById('loja-panel-dados');
  if (!lid){ panel.innerHTML = '<em style="color:var(--muted)">Loja não identificada.</em>'; return; }
  const d = await fetch('/api/admin/lojas?'+ '', {credentials:'same-origin'}).then(r=>r.json()).catch(()=>({lojas:[]}));
  const loja = (d.lojas||[]).find(l=>l.id===lid) || {id:lid};
  const f = (id,label,val)=>`<div><label class="field-label">${label}</label>
    <input id="${id}" value="${esc(val||'')}" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></div>`;
  panel.innerHTML = `
    <div class="grid2" style="gap:14px;margin-bottom:14px">
      ${f('loja-nome','Nome',loja.nome)}
      ${f('loja-codigo','Código (3 letras)',loja.codigo)}
      ${f('loja-cnpj','CNPJ',loja.cnpj)}
      ${f('loja-tel','Telefone',loja.telefone)}
      ${f('loja-email','E-mail',loja.email)}
      ${f('loja-t1n','Testemunha 1 — nome',loja.testemunha1_nome)}
      ${f('loja-t1c','Testemunha 1 — CPF',loja.testemunha1_cpf)}
      ${f('loja-t2n','Testemunha 2 — nome',loja.testemunha2_nome)}
      ${f('loja-t2c','Testemunha 2 — CPF',loja.testemunha2_cpf)}
    </div>
    <button class="btn btn-primary btn-sm" onclick="adminLojaSalvar(${lid})">Salvar dados da loja</button>`;
}

async function adminLojaSalvar(lid){
  const v = id => document.getElementById(id).value.trim();
  const payload = {
    nome: v('loja-nome'), codigo: v('loja-codigo'), cnpj: v('loja-cnpj'),
    telefone: v('loja-tel'), email: v('loja-email'),
    testemunha1_nome: v('loja-t1n'), testemunha1_cpf: v('loja-t1c'),
    testemunha2_nome: v('loja-t2n'), testemunha2_cpf: v('loja-t2c'),
  };
  const r = await fetch('/api/admin/lojas/'+lid, {method:'PATCH', credentials:'same-origin',
    headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json();
  if(!d.ok){ await avisoPopup(d.erro||'Erro', {titulo:'Dados da loja'}); return; }
  showToast('Dados da loja salvos.', false);
}
```

- [ ] **Step 6: Point `goPage(7)` to the console; show nav for the new profiles**

Em `static/index.html`, no `goPage` (≈ linhas 2125-2143), trocar a linha do `n===7`:

```javascript
  if(n===7){ adminCarregarConsole(); adminCarregar(); } // page-07: console + fila Omie
```

E em `carregarUsuarioAutenticado` (≈ linha 1884), garantir que o nav Admin apareça também para super_admin/admin_rede (que têm `pode_gerir_usuarios=true`, então a condição atual já cobre — confirmar):

```javascript
    if (_navAdmin) _navAdmin.style.display =
      (_usuarioAtual && (_usuarioAtual.pode_gerir_usuarios
        || _usuarioAtual.pode_gerir_redes || _usuarioAtual.pode_gerir_lojas)) ? '' : 'none';
```

- [ ] **Step 7: Add abrangência UX to the partner modal**

Em `static/index.html`, no `#modal-parceiro` (≈ linhas 1243-1311), adicionar — após o campo "Comissão padrão (%)" — um seletor de abrangência e um container de lojas:

```html
      <div>
        <label class="field-label">Abrangência</label>
        <select id="par-abrangencia" onchange="parAbrangenciaMudou()"
                style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px">
          <option value="loja">Por loja (vincula a lojas específicas)</option>
          <option value="rede">Por rede (toda a rede)</option>
        </select>
      </div>
      <div id="par-rede-wrap" style="display:none">
        <label class="field-label">Rede</label>
        <select id="par-rede" style="width:100%;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:9px 13px;color:var(--text);font-size:12px"></select>
      </div>
      <div id="par-lojas-wrap" style="grid-column:1/-1">
        <label class="field-label">Lojas vinculadas</label>
        <div id="par-lojas-lista" style="font-size:12px;color:var(--muted)">Carregando…</div>
      </div>
```

E o JS (junto às funções de parceiro, ≈ linha 6000):

```javascript
function parAbrangenciaMudou(){
  const abr = document.getElementById('par-abrangencia').value;
  document.getElementById('par-rede-wrap').style.display  = abr==='rede' ? '' : 'none';
  document.getElementById('par-lojas-wrap').style.display = abr==='loja' ? '' : 'none';
}

async function parCarregarOpcoesTenant(){
  // popula select de redes (se houver) e checkboxes de lojas visíveis ao usuário
  try {
    const lojas = await fetch('/api/admin/lojas', {credentials:'same-origin'}).then(r=>r.json());
    const box = document.getElementById('par-lojas-lista');
    box.innerHTML = (lojas.lojas||[]).map(l=>`
      <label style="display:flex;gap:8px;align-items:center;margin:4px 0">
        <input type="checkbox" class="par-loja-chk" value="${l.id}">
        <span>${esc(l.nome)} (${esc(l.codigo||'—')})</span>
        <input type="number" class="par-loja-com" data-loja="${l.id}" min="0" max="30" step="0.5" value="0"
               style="width:64px;margin-left:auto;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:4px 6px;color:var(--text);font-size:11px"> %
      </label>`).join('') || '<em>Nenhuma loja disponível.</em>';
  } catch(e){ document.getElementById('par-lojas-lista').innerHTML = '<em>Erro ao carregar lojas.</em>'; }
  // redes (opcional; só super_admin/admin_rede enxergam)
  try {
    const redes = await fetch('/api/admin/redes', {credentials:'same-origin'}).then(r=>r.json());
    const sel = document.getElementById('par-rede');
    sel.innerHTML = (redes.redes||[]).map(r=>`<option value="${r.id}">${esc(r.nome)}</option>`).join('');
  } catch(e){ /* diretor não tem /api/admin/redes — ok, fica vazio */ }
}
```

> Chame `parCarregarOpcoesTenant()` e `parAbrangenciaMudou()` em `parAbrirModal()` (a função que abre o modal), após resetar o form.

- [ ] **Step 8: Send abrangência in `parSalvar`**

Em `static/index.html`, no `parSalvar` (≈ linhas 6121-6162), montar `abrangencia`/`lojas`/`rede_id` no `payload`:

```javascript
  const abrangencia = document.getElementById('par-abrangencia').value;
  payload.abrangencia = abrangencia;
  if (abrangencia === 'rede') {
    payload.rede_id = parseInt(document.getElementById('par-rede').value) || null;
  } else {
    const lojas = [];
    document.querySelectorAll('.par-loja-chk:checked').forEach(chk => {
      const lid = parseInt(chk.value);
      const com = document.querySelector(`.par-loja-com[data-loja="${lid}"]`);
      lojas.push({ loja_id: lid, comissao_padrao_pct: parseFloat(com?.value) || 0 });
    });
    payload.lojas = lojas;
  }
```

(Inserir essas linhas após a montagem do `payload` existente e antes do `fetch`.)

- [ ] **Step 9: Manual smoke in the browser (anon tab)**

Reiniciar o servidor (mudou `.py`) e abrir em aba anônima. Como super_admin (`sad2026`/`trocar123`): page-07 mostra Nível 1 (Redes + Lojas avulsas). Criar rede → entrar → criar loja → entrar → editar "Dados da loja". Como diretor (`pdm2026`): page-07 aterrissa direto no Nível 3 da loja seed, abas "Dados da loja" + "Usuários da loja" (CRUD idêntico ao de hoje). Abrir modal de parceiro → alternar abrangência loja/rede. 0 erros de console.

- [ ] **Step 10: Commit**

```bash
git add static/index.html
git commit -m "feat(ui): console admin em 3 niveis (Plataforma/Rede/Loja) + dados da loja + abrangencia de parceiro"
```

---

## Task 10: Docs + suíte completa + verificação fim-a-fim (Playwright)

**Files:**
- Modify: `docs/USUARIOS.md`
- Modify: `DEV_LOG.md`

- [ ] **Step 1: Document the two new profiles in `docs/USUARIOS.md`**

Adicionar uma seção descrevendo `super_admin` (Administrador da Plataforma — gerir_redes/lojas/usuarios, editar_dados_loja, **sem** capacidades operacionais) e `admin_rede` (Administrador de Rede — gerir_lojas/usuarios e editar_dados_loja dentro da própria rede, **sem** operacional), e a observação de que o super_admin de bootstrap é `sad2026` com **senha de exemplo a trocar**.

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS em tudo — 167 anteriores (com `test_slugs` atualizado) + os novos das Tasks 1-4 (`test_perfis_tenancy`, `test_tenancy_validadores`, `test_tenancy_escopo`, `test_tenancy_bootstrap`). Nenhum teste operacional pré-existente quebrado (F2 não toca query operacional).

- [ ] **Step 3: Schema/bootstrap smoke num DB de descarte**

Run:
```bash
python -c "import database; database.init_db(); db=database.get_session(); \
import database as d; from database import Usuario; \
print('super_admins=', db.query(Usuario).filter_by(nivel='super_admin').count()); db.close()"
```
Expected: `super_admins= 1`.

- [ ] **Step 4: Playwright — os 3 consoles, escopo e regressão**

Subir o servidor real e, em aba anônima:
1. Login `sad2026` → page-07 no Nível 1; criar rede → loja → diretor; drill-down + breadcrumb funcionam.
2. Editar "Dados da loja" da loja seed (testemunha + CPF) → persiste (recarregar confirma).
3. Login `pdm2026` (diretor) → aterrissa no Nível 3; "Usuários da loja" idêntico ao de hoje; consegue editar dados da própria loja; **não** vê Nível 1/2.
4. Cadastro de parceiro com abrangência loja (vínculo + comissão por loja) e rede.
5. **Regressão operacional:** lista de projetos, negociação, contrato (ainda das constantes — F3 não feita), clientes e parceiros carregam idênticos; 0 erros de console.

Expected: tudo acima verde; nenhuma diferença nas telas operacionais.

- [ ] **Step 5: Update the DEV_LOG and commit**

Adicionar entrada no `DEV_LOG.md` resumindo a F2 (perfis super_admin/admin_rede, bootstrap `tenancy_v2_2026`, `mod_tenancy`, endpoints redes/lojas/usuários escopados, abrangência de parceiro, console em 3 níveis, dados da loja editáveis destravando a F3). Commit:

```bash
git add docs/USUARIOS.md DEV_LOG.md
git commit -m "docs: USUARIOS + DEV_LOG — F2 perfis e CRUD de tenancy"
```

---

## Self-review (cobertura do spec)

- **Perfis `super_admin`/`admin_rede` + matriz de capacidades + sem operacional** → Task 1 (`test_perfis_tenancy` afirma operacional = False). ✓
- **Capacidades `gerir_redes`/`gerir_lojas`/`editar_dados_loja`; diretor edita a própria** → Task 1 (perfis) + Task 3 (`pode_editar_dados_loja`). ✓
- **Bootstrap do super_admin (migração `tenancy_v2_2026`, idempotente, respeita existente; seed antes da loja)** → Task 4. ✓
- **Validadores puros (`validar_rede`, `validar_loja` 3-letras único, `validar_abrangencia_parceiro`)** → Task 2. ✓
- **Helpers de escopo/atribuição (comparar rede_id/loja_id ator×alvo)** → Task 3. ✓
- **Endpoints `/api/admin/redes` (gate gerir_redes)** → Task 5. ✓
- **Endpoints `/api/admin/lojas` (escopo + editar dados da loja, código 3-letras único)** → Task 6. ✓
- **`/api/admin/usuarios` (atribuição loja/rede conforme ator + escopo na listagem)** → Task 7. ✓
- **Parceiros (abrangência loja×rede, vínculos M:N, diretor cria ambos, escopo)** → Task 8. ✓
- **Navegação: 3 consoles, aterrissagem por perfil, breadcrumb + drill-down, loja avulsa pula N2** → Task 9. ✓
- **Aba "Dados da loja" editável (destrava F3)** → Task 6 (API) + Task 9 (UI). ✓
- **Não-objetivos: sem isolamento operacional; `mod_contrato.py` intacto; perfis novos sem operacional** → garantido: nenhuma task toca query operacional nem `mod_contrato.py`; Task 1 afirma operacional=False; Task 10 verifica regressão. ✓
- **Verificação (pytest + API real + Playwright)** → Tasks 5-8 (curl) + Task 10 (suíte + Playwright). ✓

**Consistência de nomes verificada entre tasks:** `mod_tenancy.validar_rede`/`validar_loja`/`validar_abrangencia_parceiro`, `pode_ver_rede`/`pode_ver_loja`/`pode_editar_dados_loja`/`atribuir_tenant_usuario`/`_eh_super_admin`/`_eh_admin_rede`; `_rede_dict`/`_loja_dict`/`_ator_dict`/`_rede_da_loja`/`_aplicar_abrangencia_parceiro`; migração `tenancy_v2_2026`; `_SEED_SA_NOME`/`_SEED_SA_LOGIN`/`_SEED_SA_SENHA`/`_hash_senha_seed`; front `_adminNav`/`adminCarregarConsole`/`adminRender`/`adminEntrarRede`/`adminEntrarLoja`/`adminIrNivel`/`adminRenderPlataforma`/`adminRenderRede`/`adminRenderLoja`/`adminLojaCarregarDados`/`adminLojaSalvar`/`parAbrangenciaMudou`/`parCarregarOpcoesTenant`. Usados de forma idêntica onde se cruzam.

## Pontos a confirmar no review (assunções a validar com o código real durante a execução)

1. **`Usuario.set_senha`** — confirmar o algoritmo de hash para o `_hash_senha_seed` da migração (Task 4, Step 3) bater com o login real.
2. **`do_PATCH`** — confirmar o estilo de despacho/indentação real (`m_user = re.match(...)`) antes de inserir `m_rede`/`m_loja` (Tasks 5-6).
3. **Cadastro rápido de parceiro** no front (fluxo `_npCadastrandoParceiro`) — garantir que sempre envie `abrangencia`+`lojas` ou defaultar no backend (Task 8, Step 3).
4. **Fila Omie** dentro da antiga `page-07` — preservar markup/ids ao reescrever o container (Task 9, Step 1).
