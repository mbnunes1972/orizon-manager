# Validação de CPF/CNPJ nos cadastros — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Rejeitar CPF/CNPJ **falso** (dígito verificador) em todos os cadastros (Cliente, Parceiro, Usuário, Rede, Loja) — **só se o documento for informado** (segue opcional). Backend autoritativo (400) + inline no modal de cliente.

**Architecture:** Util puro `validacao_doc.py` → aplicar nos handlers de create/edit (`main.py`) → frontend inline no cliente. Verde a cada tarefa. Branch `feat/validacao-cpf-cnpj`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/2026-07-06-validacao-cpf-cnpj-design.md`.

**Ler antes:** o spec (tem o código do util pronto); `main.py` handlers de create/edit — Cliente `POST /api/clientes` (~2024) + `POST /api/clientes/<id>/editar` (~2196); Parceiro (~2304 create + editar); Usuário (create/edit — grep `Usuario(`); Rede (~3266); Loja (~3291); `static/index.html` modal de cliente (`cli-cpf`/`cli-cnpj`/`cli-aviso-cpf` ~1297). **Baseline 601 passed.** Teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

**CPF/CNPJ válidos para testes:** CPF `111.444.777-35` (`11144477735`), `390.533.447-05`; CNPJ `11.222.333/0001-81`, `19.152.134/0001-56` (INSPIRIUM). Inválidos: `111.111.111-11` (repetido), `123.123.123-00`, `111.444.777-00` (DV errado); CNPJ `11.222.333/0001-00`.

---

## Task 1: `validacao_doc.py` (util puro) + testes

**Files:** Create `validacao_doc.py`, `tests/test_validacao_doc.py`.

- [ ] **Step 1: Teste primeiro** — `tests/test_validacao_doc.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import validacao_doc as vd

def test_cpf_valido():
    assert vd.valida_cpf("111.444.777-35") and vd.valida_cpf("11144477735")
def test_cpf_invalido():
    assert not vd.valida_cpf("111.444.777-00")   # DV errado
    assert not vd.valida_cpf("111.111.111-11")   # repetido
    assert not vd.valida_cpf("123")              # tamanho
    assert not vd.valida_cpf("")                 # vazio
def test_cnpj_valido():
    assert vd.valida_cnpj("11.222.333/0001-81") and vd.valida_cnpj("19152134000156")
def test_cnpj_invalido():
    assert not vd.valida_cnpj("11.222.333/0001-00")
    assert not vd.valida_cnpj("00000000000000")
def test_doc_valido_por_tamanho():
    assert vd.doc_valido("11144477735") and vd.doc_valido("11222333000181")
    assert not vd.doc_valido("123456")           # nem 11 nem 14
def test_erro_doc():
    assert vd.erro_doc("", "CPF") is None                    # vazio -> ok
    assert vd.erro_doc("111.444.777-35", "CPF", "cpf") is None
    assert vd.erro_doc("111.444.777-00", "CPF", "cpf")       # msg
    assert vd.erro_doc("11.222.333/0001-00", "CNPJ", "cnpj")
    assert vd.erro_doc("123456", "Documento")                # auto -> inválido
```

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: `validacao_doc.py`** — copiar o bloco do spec §3 (`_digitos`, `valida_cpf`, `valida_cnpj`, `doc_valido`, `erro_doc`; `import re` no topo).

- [ ] **Step 4: Rodar** `python3 -m pytest tests/test_validacao_doc.py -q` → verde; suíte inteira → verde (601, aditivo). **Commit:**
```
git add validacao_doc.py tests/test_validacao_doc.py
git commit -m "feat: validacao_doc (digito verificador de CPF/CNPJ)"
```

---

## Task 2: Validação no cadastro de **Cliente** (create + edit)

**Files:** Modify `main.py`; Test: `tests/test_validacao_cadastro_e2e.py` (novo); **corrigir** testes que quebrarem.

- [ ] **Step 1: Teste primeiro** — `tests/test_validacao_cadastro_e2e.py` (usa `http_client_factory`, `seed`; login `dir_l1`):
```python
def _cli(c, **extra):
    body = {"nome": "X", "email": "x@x.com", "telefone": "(12) 90000-0000"}; body.update(extra)
    return c.post("/api/clientes", body)

def test_cliente_cpf_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.444.777-00")
    assert st == 400 and "cpf" in (d.get("erro","")).lower()

def test_cliente_cpf_valido_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, cpf="111.444.777-35")
    assert st == 200 and d["ok"]

def test_cliente_sem_cpf_200(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c)   # sem cpf -> permitido
    assert st == 200 and d["ok"]

def test_cliente_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = _cli(c, tipo_dest="contribuinte", cnpj="11.222.333/0001-00")
    assert st == 400 and "cnpj" in (d.get("erro","")).lower()
```

- [ ] **Step 2: Rodar → falha** (hoje aceita inválido).

- [ ] **Step 3: `main.py` — Cliente create + edit**
No `POST /api/clientes` (~2036, após ler `cpf`/`cnpj`, antes de criar) e no `POST /api/clientes/<id>/editar`:
```python
    import validacao_doc
    for valor, rot, tipo in ((req.get("cpf"), "CPF", "cpf"), (req.get("cnpj"), "CNPJ", "cnpj")):
        e = validacao_doc.erro_doc(valor, rot, tipo)
        if e:
            self.send_json({"ok": False, "erro": e}, code=400); return
```
Manter a checagem de unicidade de CPF existente (depois da validação). No editar, validar os campos que vierem no req.

- [ ] **Step 4: Corrigir testes existentes que quebrem** — `grep -rn "/api/clientes" tests/` e rodar a suíte; qualquer teste que **cria/edita cliente via endpoint com CPF/CNPJ inválido** vai virar 400 → trocar por um **CPF/CNPJ válido** (ex.: `111.444.777-35`) ou omitir o doc. **Atenção:** cadastros feitos direto via `app_db.Cliente(...)` (seed) **não** passam pelo endpoint → não quebram (não precisa mexer).

- [ ] **Step 5: Rodar** `python3 -m pytest -q` → verde. **Commit:**
```
git add main.py tests/
git commit -m "feat(cadastro): valida CPF/CNPJ do cliente (rejeita falso) no create/edit"
```

---

## Task 3: Validação em **Parceiro, Usuário, Rede, Loja**

**Files:** Modify `main.py`; Test: `tests/test_validacao_cadastro_e2e.py` (adicionar); corrigir testes que quebrem.

- [ ] **Step 1: Testes primeiro** — adicionar casos (um por cadastro): inválido→400, válido→200. Ex.:
```python
def test_parceiro_cpf_cnpj_invalido_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/parceiros", {"nome":"P","tipo":"arquiteto","cpf_cnpj":"111.111.111-11"})
    assert st == 400
```
(Adapte ao payload/endpoint real de cada cadastro — leia os handlers. Rede/Loja podem exigir super_admin/gerir_lojas: use o usuário certo do seed.)

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: `main.py`** — inserir a validação nos create/edit:
  - **Parceiro**: `validacao_doc.erro_doc(req.get("cpf_cnpj"), "CPF/CNPJ")` (tipo None → auto por tamanho).
  - **Usuário**: `erro_doc(req.get("cpf"), "CPF", "cpf")`.
  - **Rede**: `erro_doc(req.get("cnpj"), "CNPJ", "cnpj")`.
  - **Loja**: `erro_doc(req.get("cnpj"), "CNPJ", "cnpj")`.
  Sempre antes de persistir; 400 com a mensagem. Só valida se informado (o `erro_doc` já cuida do vazio).

- [ ] **Step 4: Corrigir testes existentes** que criem esses cadastros via endpoint com doc inválido (grep `/api/parceiros`, `/api/usuarios`, `/api/admin/redes`, `/api/admin/lojas` em `tests/`). Trocar por doc válido/omitir.

- [ ] **Step 5: Rodar** `python3 -m pytest -q` → verde. **Commit:**
```
git add main.py tests/
git commit -m "feat(cadastro): valida CPF/CNPJ em parceiro, usuario, rede e loja"
```

---

## Task 4: Frontend — validação inline no modal de cliente

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** no modal de cliente, no `blur`/save dos campos `cli-cpf` e `cli-cnpj`, validar (uma função JS
`_docValidoCPF`/`_docValidoCNPJ` — mesma lógica de DV) e mostrar o aviso (`cli-aviso-cpf` já existe; criar
`cli-aviso-cnpj` análogo). No `cliSalvar`, **bloquear** com aviso se o doc informado for inválido (o backend
também barra — isto é UX). `esc()` no dinâmico.
- [ ] **Step 2:** balanceamento do `<script>` (não piorar) + `python3 -m pytest -q` verde. **Commit:**
```
git add static/index.html
git commit -m "feat(cadastro): validacao inline de CPF/CNPJ no modal de cliente"
```

---

## Task 5: Fechamento — docs

- [ ] **Step 1:** `pytest -q` verde. **Step 2:** spec → **IMPLEMENTADO**; DEV_LOG (validação de CPF/CNPJ nos
cadastros; placeholders antigos só somem via edição). **Step 3:** commit + re-ingerir MCP no merge.

---

## Self-review do plano
- **Cobertura do spec:** §3 util (T1) · §4 backend nos 5 cadastros (T2 Cliente, T3 demais) · §5 frontend (T4)
  · §6 testes (T1–T3) · §7 fora de escopo respeitado.
- **Sem placeholders:** util com código; "ler os handlers" e "corrigir testes que quebrem" são verificações.
- **Consistência:** `validacao_doc.erro_doc(valor, rotulo, tipo)`, `valida_cpf`/`valida_cnpj`/`doc_valido`
  idênticos entre tarefas; 400 com mensagem; valida-se só se informado. Verde a cada tarefa.
```
