# Fiscal — UI do Perfil de Emissão (US-37) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Configurar o multi-CNPJ pela tela: **painel Fiscal da rede** (Emitente central) + **Perfil de Emissão** (default da rede + override da loja: produto/serviço → emitente).

**Architecture:** Backend primeiro (endpoints da rede reusando a lógica do painel da loja via helper + endpoints de perfil-emissão com opções e upsert/delete de `PerfilEmissao`) → frontend (painel Fiscal da rede parametrizado + selects Produto/Serviço). Verde a cada tarefa. Branch `feat/fiscal-perfil-emissao-ui`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/2026-07-06-fiscal-perfil-emissao-ui-design.md`.

**Ler antes:** o spec; `main.py` handlers do painel da **loja** (US-36): `GET …/lojas/<id>/perfil-fiscal` (~1494), `PUT …/perfil-fiscal` (~4392), `PUT …/perfil-fiscal/segredos` (~4428), `PUT …/perfil-fiscal/ambiente` (~4470) — todos resolvem `db.get(Emitente, loja.emitente_id)`; `database.py` (`Rede.emitente_central_id` ~193, `PerfilEmissao` ~582, `Emitente`, `Loja.emitente_id`); `mod_fiscal.resolver_emitente` (~51, precedência loja→rede→self) + `emitente_padrao_teste`; `perfis.pode(nivel,"gerir_lojas")` + `mod_tenancy` (escopo de rede); `static/index.html` `adminFiscalCarregar/Salvar/SalvarSegredos/AtivarAmbiente` (~6988-7090) e a navegação admin rede/loja (~6686-6740). **Baseline 561 passed.** Teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

---

## Task 1: Backend — painel Fiscal da REDE (Emitente central)

**Files:** Modify `main.py`; Test: `tests/test_painel_rede_fiscal_e2e.py` (novo).

- [ ] **Step 1: Ler os 4 handlers da loja** e extrair a lógica comum. Criar um **helper** que dado o *dono*
resolve/cria o Emitente:
```python
def _emitente_do_dono(db, kind, obj):
    """kind='loja' -> obj.emitente_id; kind='rede' -> obj.emitente_central_id. Retorna (em|None, get/set)."""
    attr = "emitente_id" if kind == "loja" else "emitente_central_id"
    eid = getattr(obj, attr, None)
    em = db.get(Emitente, eid) if eid else None
    return em, attr
```
(ou inline equivalente). A criação seta `setattr(obj, attr, em.id)` após `db.flush()`.

- [ ] **Step 2: Teste primeiro** — `tests/test_painel_rede_fiscal_e2e.py` (usa `http_client_factory`, `seed`):
usuário `admin_rede`/super_admin; `PUT /api/admin/redes/<id>/perfil-fiscal` com config → cria o Emitente
central da rede (`rede.emitente_central_id` setado) + campos aplicados; `GET` não vaza token; `PUT
…/segredos` grava cifrado; `PUT …/ambiente` com guarda; **gate**: admin_rede de outra rede → 403; consultor
→ 403; não autenticado → 401. Rodar → **falha** (rotas 404).

- [ ] **Step 3: `main.py` — endpoints da rede** (espelho dos da loja, via o helper):
`GET/PUT /api/admin/redes/(\d+)/perfil-fiscal`, `PUT …/perfil-fiscal/segredos`, `PUT …/perfil-fiscal/ambiente`.
Carregam a `Rede` (`db.get(Rede, id)`), resolvem o emitente central (helper, cria no PUT), aplicam a **mesma
allowlist/segredos/ambiente** dos handlers da loja. **Gate:** `perfis.pode(nivel,"gerir_lojas")` (401/403) +
tenancy: super_admin qualquer rede; admin_rede só `ator.rede_id == id` (senão 403). Reusar a lógica da loja —
se possível, extrair as 4 rotinas (get_config/put_config/put_segredos/put_ambiente) para funções que recebem
`(em, obj_para_criar)` e chamá-las tanto na loja quanto na rede (DRY). Se o refactor for arriscado, duplicar
minimamente é aceitável desde que o comportamento e a suíte batam.

- [ ] **Step 4: Rodar** `python3 -m pytest -q` → verde (loja intacta + rede nova). **Commit:**
```
git add main.py tests/test_painel_rede_fiscal_e2e.py
git commit -m "feat(fiscal): painel Fiscal da rede (Emitente central) — GET/PUT/segredos/ambiente"
```

---

## Task 2: Backend — Perfil de Emissão (default da rede + override da loja)

**Files:** Modify `main.py`; Test: `tests/test_perfil_emissao_e2e.py` (novo).

- [ ] **Step 1: Teste primeiro** — `tests/test_perfil_emissao_e2e.py`:
- `PUT /api/admin/redes/<id>/perfil-emissao {"produto": <central_id>, "servico": null}` → cria linha
  `PerfilEmissao(owner="rede", tipo_doc="produto", emitente_id=central)`, remove a de serviço; `GET` reflete +
  `opcoes` contém o central.
- `PUT /api/admin/lojas/<id>/perfil-emissao {"produto": <self_id>}` (override) → `GET` da loja reflete +
  `opcoes` = self + central + null("Herdar").
- **Resolução ponta a ponta** (reusar helpers do `test_nfe_etapa15_e2e`/`test_resolver_emissao`): com rede
  default produto→central e **sem** override → `resolver_emitente(loja,"produto")` = central; com override
  loja produto→self → = self. (pode testar via `mod_fiscal.resolver_emitente` direto, mais barato.)
- **Gate:** rede → `gerir_lojas`+tenancy; loja → `editar_dados_loja`; consultor 403; não-auth 401.
Rodar → **falha**.

- [ ] **Step 2: `main.py` — endpoints**
`GET/PUT /api/admin/redes/(\d+)/perfil-emissao` e `GET/PUT /api/admin/lojas/(\d+)/perfil-emissao`.
Helper de opções:
```python
def _opcoes_emitente(db, kind, obj):
    from database import Emitente, Rede
    ops = []
    if kind == "loja":
        if obj.emitente_id:
            e = db.get(Emitente, obj.emitente_id); ops.append({"id": e.id, "label": "Este CNPJ — " + (e.razao_social or e.cnpj or str(e.id)), "papel": "self"})
        if obj.rede_id:
            r = db.get(Rede, obj.rede_id)
            if r and r.emitente_central_id:
                c = db.get(Emitente, r.emitente_central_id); ops.append({"id": c.id, "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)), "papel": "central"})
    else:  # rede
        if obj.emitente_central_id:
            c = db.get(Emitente, obj.emitente_central_id); ops.append({"id": c.id, "label": "Central da rede — " + (c.razao_social or c.cnpj or str(c.id)), "papel": "central"})
    return ops
```
- **GET:** lê as linhas `PerfilEmissao(owner_tipo=kind, owner_id=id)` → `{produto, servico}` (emitente_id ou
  null) + `opcoes`.
- **PUT:** para `produto`/`servico`: valida que o `emitente_id` (se não-null) está nas `opcoes`; **upsert** a
  linha (`filter_by(owner_tipo, owner_id, tipo_doc).first()` → set/ create) ou **delete** se null. `commit`.
- **Gate:** como acima.

- [ ] **Step 3: Rodar** → verde. **Commit:**
```
git add main.py tests/test_perfil_emissao_e2e.py
git commit -m "feat(fiscal): endpoints Perfil de Emissao (rede default + loja override) com opcoes e upsert"
```

---

## Task 3: Frontend — painel Fiscal da rede + selects de Perfil de Emissão

**Files:** Modify `static/index.html`.

- [ ] **Step 1: Painel Fiscal da rede** — parametrizar `adminFiscalCarregar/Salvar/SalvarSegredos/AtivarAmbiente`
por *dono* (base URL `'/api/admin/lojas/'+id` vs `'/api/admin/redes/'+id`), e exibir a config do Emitente
central quando uma **rede** está selecionada no admin (nível rede). Criar a seção "Fiscal da rede" no ponto do
nível-rede (ver `_adminNav`/nível 2). Reaproveitar o render existente do form.

- [ ] **Step 2: Perfil de Emissão (selects)** —
- **Aba Fiscal da loja:** seção "Perfil de Emissão (esta loja)" com 2 `<select>` (Produto/Serviço). Carregar
  via `GET …/lojas/<id>/perfil-emissao` (usa `opcoes` + opção **"Herdar da rede"** = value vazio/null). Salvar
  → `PUT` com `{produto, servico}` (null quando "Herdar"). `showToast` no sucesso.
- **Painel Fiscal da rede:** seção "Perfil de Emissão (default da rede)" com 2 selects (opção **"A própria
  loja (self)"** = null + "Central da rede"). Carregar/salvar via `…/redes/<id>/perfil-emissao`.
`esc()` nos labels dinâmicos.

- [ ] **Step 3: Verificação** — balanceamento do `<script>` (não piorar) + `python3 -m pytest -q` verde.
**Commit:**
```
git add static/index.html
git commit -m "feat(fiscal): UI do Perfil de Emissao (painel da rede + selects produto/servico loja e rede)"
```

---

## Task 4: Fechamento — docs

**Files:** Modify spec (Status), `DEV_LOG.md`, `docs/historias/BACKLOG.md`.

- [ ] **Step 1:** `python3 -m pytest -q` verde.
- [ ] **Step 2:** spec → **IMPLEMENTADO**; DEV_LOG (config multi-CNPJ pela tela: painel da rede + Perfil de
  Emissão 2 níveis); BACKLOG — **US-37** feita; restam US-38/US-32 (NFS-e) e refinamentos.
- [ ] **Step 3: Commit** + re-ingerir MCP no merge.

---

## Self-review do plano
- **Cobertura do spec:** §3.1 painel da rede (T1) · §3.2 perfil-emissão (T2) · §4 UI (T3) · §5 testes (T1/T2)
  · §6 fora de escopo respeitado (sem emitentes arbitrários; sem NFS-e).
- **Sem placeholders:** helpers com código; "ler os handlers" é verificação.
- **Consistência:** `_emitente_do_dono`/`_opcoes_emitente`, `PerfilEmissao(owner_tipo,owner_id,tipo_doc,emitente_id)`,
  gates (rede=`gerir_lojas`+tenancy, loja=`editar_dados_loja`), URLs `…/redes|lojas/<id>/perfil-{fiscal,emissao}`
  idênticos entre tarefas. Verde a cada tarefa (rede panel → política → UI).
```
