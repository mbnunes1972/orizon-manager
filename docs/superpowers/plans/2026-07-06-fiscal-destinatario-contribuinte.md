# Fiscal — Destinatário Contribuinte/Isento/Não Contribuinte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Emitir corretamente para os **3 tipos de destinatário** (contribuinte/isento/não contribuinte): `Cliente` ganha tipo+CNPJ+IE; `mapa_fiscal` ramifica indicador de IE, envio de IE, CSOSN e `consumidor_final`; contrato exige o documento certo; IE preenchida na emissão.

**Architecture:** Aditivo no modelo (Cliente/Emitente) → ramificação pura no `mapa_fiscal` (montar_nota já recebe o `cliente`, sem mudar assinatura) → UI do cadastro → validação do contrato → IE na emissão. Verde a cada tarefa. Branch `feat/fiscal-destinatario-contribuinte`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/fiscal/2026-07-06-fiscal-destinatario-contribuinte-design.md`.

**Ler antes:** o spec; `database.py` (`Cliente` ~132-161, `Emitente`, `_migrar_colunas`); `mapa_fiscal.py` (`montar_nota` 15-49, `montar_payload` 55-115, `_so_digitos`); `main.py` (POST/PUT `/api/clientes`; fluxo de contrato com o branch `sem_cpf` ~1583/1648; endpoint `…/ciclo/15/emitir-nfe`); `static/index.html` (modal cliente `cli-*` ~1276-1310). **Baseline 546 passed.** Teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

---

## Task 1: `Cliente` — tipo_dest + cnpj + inscricao_estadual (+ migração)

**Files:** Modify `database.py`; Test: `tests/test_cliente_fiscal_model.py` (novo).

- [ ] **Step 1: Teste falhando** (usa `app_db`):
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_cliente_campos_fiscais(app_db):
    s = app_db.get_session()
    c = app_db.Cliente(nome="ACME", tipo_dest="contribuinte", cnpj="11.222.333/0001-44",
                       inscricao_estadual="123456")
    s.add(c); s.commit()
    lido = s.query(app_db.Cliente).filter_by(nome="ACME").first()
    assert lido.tipo_dest == "contribuinte" and lido.cnpj == "11.222.333/0001-44" and lido.inscricao_estadual == "123456"
    s.close()

def test_cliente_default_nao_contribuinte(app_db):
    s = app_db.get_session()
    c = app_db.Cliente(nome="PF", cpf="1"); s.add(c); s.commit()
    assert s.query(app_db.Cliente).filter_by(nome="PF").first().tipo_dest == "nao_contribuinte"
    s.close()
```

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: `database.py` — colunas em `Cliente`** (após `cpf`):
```python
    tipo_dest          = Column(Text, default="nao_contribuinte")  # contribuinte|isento|nao_contribuinte
    cnpj               = Column(String(18), nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
```

- [ ] **Step 4: Migração** em `_migrar_colunas` (bloco `clientes`, padrão existente): adicionar
`tipo_dest` (`VARCHAR DEFAULT 'nao_contribuinte'`), `cnpj` (`VARCHAR(18)`), `inscricao_estadual` (`TEXT`),
cada um guardado por `PRAGMA table_info`.

- [ ] **Step 5: Rodar** `python3 -m pytest -q` → verde (aditivo). **Commit:**
```
git add database.py tests/test_cliente_fiscal_model.py
git commit -m "feat(fiscal): Cliente ganha tipo_dest + cnpj + inscricao_estadual (+ migracao)"
```

---

## Task 2: `mapa_fiscal` ramifica por tipo de destinatário + `Emitente.csosn_contribuinte`

**Files:** Modify `database.py` (Emitente), `mapa_fiscal.py`; Test: `tests/test_mapa_fiscal.py`.

- [ ] **Step 1: Testes falhando** — em `tests/test_mapa_fiscal.py`, adicionar (usam `SimpleNamespace`):
```python
def _cli(tipo, **kw):
    from types import SimpleNamespace
    base = dict(nome="C", tipo_dest=tipo, cpf="111.444.777-35", cnpj="11.222.333/0001-44",
                inscricao_estadual="ISE123", logradouro="R", numero="1", bairro="b",
                cidade="c", estado="SP", cep="20000-000")
    base.update(kw); return SimpleNamespace(**base)

def test_ramo_contribuinte():
    emit = _emitente(uf="SP", csosn_contribuinte="101", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("contribuinte"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cnpj" and d["doc"] == "11222333000144"
    assert d["indicador_ie"] == 1 and d["ie"] == "ISE123" and d["consumidor_final"] == 0
    assert nota["fiscal"]["csosn"] == "101"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 1
    assert p["inscricao_estadual_destinatario"] == "ISE123" and p["consumidor_final"] == 0
    assert p["items"] == [] or all(it["icms_situacao_tributaria"] == "101" for it in p["items"])

def test_ramo_isento():
    emit = _emitente(uf="SP", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("isento"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cnpj" and d["indicador_ie"] == 2 and d["consumidor_final"] == 1
    assert nota["fiscal"]["csosn"] == "102"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 2 and "inscricao_estadual_destinatario" not in p

def test_ramo_nao_contribuinte():
    emit = _emitente(uf="SP", csosn_padrao="102")
    nota = mp.montar_nota(emit, _cli("nao_contribuinte"), [], "R", "D")
    d = nota["destinatario"]
    assert d["doc_tipo"] == "cpf" and d["doc"] == "11144477735" and d["indicador_ie"] == 9 and d["consumidor_final"] == 1
    assert nota["fiscal"]["csosn"] == "102"
    p = mp.montar_payload(nota)
    assert p["indicador_inscricao_estadual_destinatario"] == 9 and "inscricao_estadual_destinatario" not in p

def test_csosn_default_no_codigo_quando_emitente_null():
    emit = _emitente(uf="SP", csosn_contribuinte=None, csosn_padrao=None)
    assert mp.montar_nota(emit, _cli("contribuinte"), [], "R", "D")["fiscal"]["csosn"] == "101"
    assert mp.montar_nota(emit, _cli("nao_contribuinte"), [], "R", "D")["fiscal"]["csosn"] == "102"
```
> `_emitente` (helper existente) precisa aceitar `csosn_contribuinte`; adicione ao `dict base` do helper
> (default None) para os testes.

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: `database.py` — `Emitente.csosn_contribuinte`** (nullable) + migração (`_migrar_colunas`,
tabela `emitente`, guardado por PRAGMA): `ALTER TABLE emitente ADD COLUMN csosn_contribuinte TEXT`.

- [ ] **Step 4: `mapa_fiscal.py` — ramificação**
No topo: `CSOSN_CONTRIBUINTE = "101"` e `CSOSN_SEM_CREDITO = "102"`.
Helper: 
```python
_INDICADOR_IE = {"contribuinte": 1, "isento": 2, "nao_contribuinte": 9}

def _dest_fiscal(cliente):
    tipo = getattr(cliente, "tipo_dest", None) or "nao_contribuinte"
    indicador = _INDICADOR_IE.get(tipo, 9)
    if indicador == 9:                       # não contribuinte -> CPF
        doc_tipo, doc = "cpf", getattr(cliente, "cpf", None)
    else:                                     # contribuinte/isento -> CNPJ
        doc_tipo, doc = "cnpj", getattr(cliente, "cnpj", None)
    ie = getattr(cliente, "inscricao_estadual", None) if indicador == 1 else None
    consumidor_final = 0 if indicador == 1 else 1
    return doc_tipo, doc, indicador, ie, consumidor_final
```
Em `montar_nota`: usar `_dest_fiscal(cliente)` para preencher `destinatario` com `doc_tipo`, `doc`
(`_so_digitos`), `indicador_ie`, `ie`, `consumidor_final`. E o `fiscal.csosn`:
```python
    csosn = (getattr(emitente, "csosn_contribuinte", None) or CSOSN_CONTRIBUINTE) if indicador == 1 \
            else (getattr(emitente, "csosn_padrao", None) or CSOSN_SEM_CREDITO)
```
Em `montar_payload`: 
- `"indicador_inscricao_estadual_destinatario": dest["indicador_ie"]` (não mais fixo 9);
- `"consumidor_final": dest["consumidor_final"]` (não mais CPF×CNPJ);
- enviar `payload["inscricao_estadual_destinatario"] = dest["ie"]` **só** quando `dest["indicador_ie"] == 1` e `dest["ie"]`.

- [ ] **Step 5: Rodar** os testes de mapa_fiscal + suíte → verde. **Commit:**
```
git add database.py mapa_fiscal.py tests/test_mapa_fiscal.py
git commit -m "feat(fiscal): ramifica destinatario (contribuinte/isento/nao) — indicador IE, IE, CSOSN, consumidor_final"
```

---

## Task 3: Cadastro de cliente (UI 3 estados) + backend aceita os campos

**Files:** Modify `static/index.html`, `main.py`.

- [ ] **Step 1: Backend `POST`/`PUT /api/clientes`** — aceitar `tipo_dest`, `cnpj`, `inscricao_estadual`
no payload e gravar no `Cliente` (localizar o handler que cria/edita cliente e adicionar os 3 campos ao
`Cliente(...)`/update). Não tornar obrigatórios.

- [ ] **Step 2: Frontend — modal do cliente** (`cli-*`, ~1276-1310):
- Adicionar um **seletor "Tipo de destinatário"** (Não contribuinte [padrão] / Contribuinte / Isento).
- Um handler `cliTipoDestMudou()` que mostra/oculta: **CPF** (não contribuinte) vs **CNPJ**+**IE** (contribuinte)
  vs **CNPJ** (isento).
- `cliSalvar`/`cliCriar` enviam `tipo_dest`, `cnpj`, `inscricao_estadual` conforme o seletor; ao abrir para
  editar, pré-selecionar o tipo e preencher os campos. `esc()` no conteúdo dinâmico.

- [ ] **Step 3: Verificação** — checagem estrutural do `<script>` (balanceamento) + `python3 -m pytest -q`
verde (frontend não afeta backend; se adicionar teste e2e de POST cliente com os campos, melhor). **Commit:**
```
git add static/index.html main.py
git commit -m "feat(fiscal): cadastro de cliente com tipo de destinatario (CPF/CNPJ/IE condicionais)"
```

---

## Task 4: Contrato exige o documento certo (`sem_cpf` → `sem_doc`)

**Files:** Modify `main.py` (fluxo de contrato); Test: e2e/unit do contrato.

- [ ] **Step 1: Teste falhando** — cliente `contribuinte` **sem CNPJ** → geração de contrato barra com o
aviso de documento faltante (adaptar o teste existente do branch `sem_cpf`, se houver, ou criar um).

- [ ] **Step 2: `main.py`** — no ponto onde hoje valida `sem_cpf` (~1648): generalizar para **`sem_doc`**:
exigir **CNPJ** quando `cliente.tipo_dest in ("contribuinte","isento")`, **CPF** quando `nao_contribuinte`.
Mensagem clara ("Informe o CNPJ do cliente antes de gerar o contrato" / CPF). **NÃO** exigir IE aqui.

- [ ] **Step 3: Rodar** → verde. **Commit:**
```
git add main.py tests/
git commit -m "feat(fiscal): contrato exige CPF ou CNPJ conforme o tipo do destinatario (IE nao bloqueia)"
```

---

## Task 5: IE no ato da emissão (etapa 15) — pede e persiste no Cliente

**Files:** Modify `main.py` (endpoint `…/ciclo/15/emitir-nfe`), `static/index.html`; Test: `tests/test_nfe_etapa15_e2e.py`.

- [ ] **Step 1: Teste falhando** — cliente `contribuinte` **sem IE**: `POST …/emitir-nfe` sem `ie` no body →
**400** pedindo a IE; com `ie` no body → emite (emissor mockado) e a **IE fica salva no Cliente**.

- [ ] **Step 2: `main.py` endpoint `emitir-nfe`** — antes de montar a nota: se
`cliente.tipo_dest == "contribuinte"` e **sem `inscricao_estadual`**: ler `req.get("ie")`; se vazio → 400
("Informe a Inscrição Estadual do cliente para emitir"); se informado → `cliente.inscricao_estadual = ie`
(persistir) antes de `montar_nota`. Isento/não-contribuinte: sem exigência.

- [ ] **Step 3: `static/index.html` painel etapa 15** — no `emitirNfeLoja`, se o cliente for contribuinte
e sem IE (o GET de estado pode expor isso, ou o 400 do backend guia): abrir um prompt/campo de **IE** e
reenviar com `ie`. (Mínimo: tratar o 400 do backend pedindo a IE via `promptPopup`/`window.prompt` e reenviar.)

- [ ] **Step 4: Rodar** `python3 -m pytest -q` → verde. **Commit:**
```
git add main.py static/index.html tests/test_nfe_etapa15_e2e.py
git commit -m "feat(fiscal): etapa 15 pede a IE do contribuinte na emissao e persiste no Cliente"
```

---

## Task 6: Fechamento — docs

**Files:** Modify spec (Status), `DEV_LOG.md`, `docs/historias/BACKLOG.md`.

- [ ] **Step 1:** `python3 -m pytest -q` verde.
- [ ] **Step 2:** spec → **IMPLEMENTADO**; `DEV_LOG` nota (destinatário 3 tipos correto; CSOSN override;
IE na emissão); BACKLOG — marcar o refinamento como feito (parte do EP-11/fiscal). Registrar como pendência:
CSOSN por operação (ST/devolução) e não-contribuinte PJ.
- [ ] **Step 3: Commit** + re-ingerir MCP após o merge.

---

## Self-review do plano
- **Cobertura do spec:** §3 Cliente (T1) · §4 Emitente CSOSN (T2) · §5 UI (T3) · §6 obrigatoriedade
  (contrato T4 / emissão T5) · §7 mapa_fiscal (T2) · §8 testes distribuídos · §9 fora de escopo respeitado.
- **Sem placeholders:** cada passo com código/rotina concreta; pontos "localizar o handler" são verificações.
- **Consistência:** `tipo_dest` (contribuinte|isento|nao_contribuinte), `_INDICADOR_IE` 1/2/9,
  `csosn_contribuinte`/`csosn_padrao` + defaults `CSOSN_CONTRIBUINTE`/`CSOSN_SEM_CREDITO`,
  `indicador_inscricao_estadual_destinatario`/`inscricao_estadual_destinatario` idênticos entre tarefas.
