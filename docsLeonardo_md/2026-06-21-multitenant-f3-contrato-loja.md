# F3 Multi-tenant — Contrato puxa da loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o contrato ler nome/CNPJ/código/telefone/e-mail e testemunhas (nome+CPF) da loja do consultor — removendo as constantes de `mod_contrato.py` — e gravar um snapshot da loja em cada contrato.

**Architecture:** `mod_contrato.py` continua **puro** (sem banco): recebe um dict `loja` do `main.py`. O `main.py` resolve a loja do consultor, valida (avisa mas deixa gerar), grava `Contrato.loja_snapshot_json` a cada geração e passa a loja para `construir_contexto`/`gerar_num_contrato`. O front trata a confirmação "loja incompleta". Spec: `docs/superpowers/specs/2026-06-21-multitenant-f3-contrato-loja-design.md`.

**Tech Stack:** Python 3 (stdlib http.server), SQLAlchemy + sqlite3, python-docx, pytest, HTML/JS vanilla.

---

## File Structure

- **`mod_contrato.py`** (modify): remove constantes de loja; novo `validar_loja_para_contrato`; `loja` em `construir_contexto`/`_montar_mapping`; `gerar_num_contrato(existing, loja_codigo, data)`.
- **`database.py`** (modify): coluna `Contrato.loja_snapshot_json` (model + `_migrar_colunas`).
- **`main.py`** (modify): helper `_loja_dict_para_contrato`; resolução de loja + validação/confirmação + snapshot + passagem nos 2 pontos de geração.
- **`static/index.html`** (modify): `gerarContrato()` trata `precisa_confirmar_loja`.
- **`tests/test_contrato_loja.py`** (create): testes puros do validador, do helper (db stub), da migração e da injeção da loja no mapping.
- **`tests/test_contrato.py`** (modify): atualizar testes que dependiam das constantes/assinaturas antigas.
- **`DEV_LOG.md`** (modify): registrar a sessão F3.

---

## Task 1: `validar_loja_para_contrato` (função pura, sem quebra)

**Files:**
- Create: `tests/test_contrato_loja.py`
- Modify: `mod_contrato.py` (adicionar função; nada removido ainda)

- [ ] **Step 1: Write the failing test**

Criar `tests/test_contrato_loja.py`:

```python
# tests/test_contrato_loja.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _loja_completa():
    return {
        "nome": "INSPIRIUM MOVEIS LTDA", "cnpj": "19.152.134/0001-56", "codigo": "INS",
        "telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br",
        "cep": "12200-000", "logradouro": "Rua A", "numero": "100",
        "complemento": "", "bairro": "Centro", "cidade": "SJC", "estado": "SP",
        "testemunha1_nome": "Jaime Perinazzo", "testemunha1_cpf": "123.456.789-00",
        "testemunha2_nome": "Felipe Guizalberte", "testemunha2_cpf": "987.654.321-00",
    }


def test_validar_loja_completa():
    from mod_contrato import validar_loja_para_contrato
    assert validar_loja_para_contrato(_loja_completa()) == []


def test_validar_loja_complemento_opcional():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa(); loja["complemento"] = ""
    assert validar_loja_para_contrato(loja) == []


def test_validar_loja_cpf_placeholder_conta_como_faltando():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    loja["testemunha1_cpf"] = "xxx.xxx.xxx-xx"
    loja["testemunha2_cpf"] = "yyy.yyy.yyy-yy"
    faltando = validar_loja_para_contrato(loja)
    j = " ".join(faltando).lower()
    assert "testemunha 1" in j and "testemunha 2" in j


def test_validar_loja_telefone_email_endereco_obrigatorios():
    from mod_contrato import validar_loja_para_contrato
    loja = _loja_completa()
    for c in ("telefone", "email", "cep", "logradouro", "numero", "bairro", "cidade", "estado"):
        loja[c] = ""
    faltando = " ".join(validar_loja_para_contrato(loja)).lower()
    for termo in ("telefone", "e-mail", "cep", "logradouro", "número", "bairro", "cidade", "estado"):
        assert termo in faltando


def test_validar_loja_vazia_acusa_tudo():
    from mod_contrato import validar_loja_para_contrato
    assert len(validar_loja_para_contrato({})) >= 13
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_contrato_loja.py -v`
Expected: FAIL — `ImportError: cannot import name 'validar_loja_para_contrato'`.

- [ ] **Step 3: Write minimal implementation**

Em `mod_contrato.py`, logo após `validar_cliente_para_contrato` (após a linha 411), adicionar:

```python
import re as _re_cpf
_TEM_DIGITO = _re_cpf.compile(r"\d")   # CPF real tem ao menos um dígito


def validar_loja_para_contrato(loja: dict) -> list:
    """Rótulos dos campos obrigatórios da loja que estão vazios para gerar o contrato.

    Lista vazia → loja completa. O CPF de testemunha sem nenhum dígito
    (placeholder 'xxx.xxx.xxx-xx') conta como faltando. `complemento` é opcional.
    """
    loja = loja or {}
    obrigatorios = [
        ("nome",             "Nome da empresa"),
        ("cnpj",             "CNPJ"),
        ("codigo",           "Código da loja"),
        ("telefone",         "Telefone"),
        ("email",            "E-mail"),
        ("cep",              "CEP"),
        ("logradouro",       "Logradouro"),
        ("numero",           "Número"),
        ("bairro",           "Bairro"),
        ("cidade",           "Cidade"),
        ("estado",           "Estado/UF"),
        ("testemunha1_nome", "Nome da Testemunha 1"),
        ("testemunha2_nome", "Nome da Testemunha 2"),
    ]
    faltando = []
    for campo, rotulo in obrigatorios:
        v = loja.get(campo)
        if not (v and str(v).strip()):
            faltando.append(rotulo)
    for campo, rotulo in [("testemunha1_cpf", "CPF da Testemunha 1"),
                          ("testemunha2_cpf", "CPF da Testemunha 2")]:
        v = (loja.get(campo) or "").strip()
        if not _TEM_DIGITO.search(v):
            faltando.append(rotulo)
    return faltando
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_contrato_loja.py -v`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_contrato.py tests/test_contrato_loja.py
git commit -m "feat(contrato): validar_loja_para_contrato (F3)"
```

---

## Task 2: Loja como fonte no `mod_contrato` (remove constantes)

**Files:**
- Modify: `mod_contrato.py` (remove constantes; `loja` em `construir_contexto`/`_montar_mapping`; `gerar_num_contrato`)
- Modify: `tests/test_contrato.py` (atualizar testes acoplados às constantes)

- [ ] **Step 1: Update the tests to express the new behavior (they will fail first)**

Em `tests/test_contrato.py`:

(a) **`test_montar_mapping_inclui_empresa_e_cpfs`** (linhas ~835-843) — trocar import de constantes por uma loja passada via `ctx["loja"]`:

```python
def test_montar_mapping_inclui_empresa_e_cpfs():
    from mod_contrato import _montar_mapping
    loja = {"nome": "INSPIRIUM MOVEIS LTDA", "cnpj": "19.152.134/0001-56",
            "testemunha1_nome": "Jaime", "testemunha1_cpf": "123.456.789-00",
            "testemunha2_nome": "Felipe", "testemunha2_cpf": "987.654.321-00"}
    ctx = {"cliente_cpf": "111.222.333-44", "loja": loja}
    m = _montar_mapping(ctx, {})
    assert m["NOME_EMPRESA"] == "INSPIRIUM MOVEIS LTDA"
    assert m["CNPJ_EMPRESA"] == "19.152.134/0001-56"
    assert m["CPF_CLIENTE"] == "111.222.333-44"
    assert m["CPF_TESTEMUNHA_1"] == "123.456.789-00"
    assert m["CPF_TESTEMUNHA_2"] == "987.654.321-00"
    assert m["NOME_TESTEMUNHA_1"] == "Jaime"
    assert m["NOME_TESTEMUNHA_2"] == "Felipe"
```

(b) **`test_gerar_num_contrato_formato`** (~331-336):

```python
def test_gerar_num_contrato_formato():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    n = gerar_num_contrato([], "INS", data=datetime(2026, 6, 17))
    assert n == "INS-2026-06-17-001"
```

(c) **`test_gerar_num_contrato_sequencia_continua`** (~338-344):

```python
def test_gerar_num_contrato_sequencia_continua():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    existentes = ["INS-2026-06-15-001", "INS-2026-06-16-002", "ORZ-2026-06-16-009"]
    n = gerar_num_contrato(existentes, "INS", data=datetime(2026, 6, 17))
    assert n == "INS-2026-06-17-003"
```

(d) **`test_gerar_num_contrato_loja_customizada`** (~347-351):

```python
def test_gerar_num_contrato_loja_customizada():
    from datetime import datetime
    from mod_contrato import gerar_num_contrato
    n = gerar_num_contrato([], "ORZ", data=datetime(2026, 1, 5))
    assert n == "ORZ-2026-01-05-001"
```

(e) **Testes de fallback telefone/email** — agora a fonte é a loja, não a constante. Atualizar para passar `loja=`:

`test_email_fallback_consultor` (~245-254):
```python
def test_email_fallback_consultor():
    from mod_contrato import construir_contexto
    cliente = {"nome": "X", "cpf": "", "email": "", "telefone": "",
               "logradouro": "", "numero": "", "complemento": "", "bairro": "",
               "cidade": "", "cep": "", "estado": "",
               "inst_mesmo_residencial": True,
               "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
               "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""}
    loja = {"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"}
    ctx = construir_contexto(cliente, {"nome": "X", "telefone": "", "email": ""}, "", loja)
    assert ctx["consultor_email"] == "sac@dalmobilesjc.com.br"
    assert ctx["consultor_tel"]   == "(12) 3341-8777"
```

Para os outros três (linhas ~108, ~140-141, ~171), localizar a chamada `construir_contexto(cliente, usuario, forma)` correspondente e acrescentar o 4º argumento `loja={"telefone": "(12) 3341-8777", "email": "sac@dalmobilesjc.com.br"}`. As asserções (`== "(12) 3341-8777"` / `== "sac@dalmobilesjc.com.br"`) permanecem iguais — só a fonte muda.

- [ ] **Step 2: Run the updated tests to verify they fail**

Run: `python3 -m pytest tests/test_contrato.py -v -k "num_contrato or empresa or fallback"`
Expected: FAIL — `gerar_num_contrato()` ainda tem default; `_montar_mapping` ainda usa constantes; `construir_contexto` ainda não aceita `loja`.

- [ ] **Step 3: Implement — remove constantes e injetar loja**

Em `mod_contrato.py`:

3a. **Remover** as linhas 21-32 (constantes `_TELEFONE_LOJA`, `_EMAIL_LOJA`, `_NOME_EMPRESA`, `_CNPJ_EMPRESA`, `_TESTEMUNHAS`, `_CODIGO_LOJA`). **Manter** `_TRACO`. Substituir o bloco por apenas:

```python
_TRACO = "--------"  # preenche slots de parcela inexistentes
```

3b. **`gerar_num_contrato`** — código obrigatório (substituir a def atual, ex-linha 39):

```python
def gerar_num_contrato(existing_nums, loja_codigo: str, data=None) -> str:
    """Próximo número de contrato no formato 'LOJA-AAAA-MM-DD-SEQ'.

    `existing_nums`: iterável com os num_contrato já existentes (qualquer loja).
    `loja_codigo`: código (3 letras) da loja — vem da tabela `lojas` (F3).
    A sequência (SEQ) é CONTÍNUA por código (máximo existente + 1).
    """
    data = data or datetime.now()
    cod = (loja_codigo or "").strip()
    pref = f"{cod}-"
    maxseq = 0
    for n in (existing_nums or []):
        if n and n.startswith(pref):
            tail = n.rsplit("-", 1)[-1]
            if tail.isdigit():
                maxseq = max(maxseq, int(tail))
    return f"{cod}-{data:%Y-%m-%d}-{maxseq + 1:03d}"
```

3c. **`_montar_mapping`** — ler a loja de `ctx["loja"]` (substituir as chaves de empresa/testemunha, ex-linhas 453-464):

```python
def _montar_mapping(ctx, pag):
    """Monta {MARCADOR: valor}. Os dados da loja vêm de ctx['loja'] (F3)."""
    loja = ctx.get("loja") or {}
    t1n = loja.get("testemunha1_nome", "") or ""
    t1c = loja.get("testemunha1_cpf", "") or ""
    t2n = loja.get("testemunha2_nome", "") or ""
    t2c = loja.get("testemunha2_cpf", "") or ""
    return {
        "NUM_CONTRATO":     str(ctx.get("num_contrato", "") or ""),
        "DATA_CONTRATO":    str(ctx.get("data_contrato", "") or ""),
        "NOME_CLIENTE":     ctx.get("cliente_nome", "") or "",
        "CPF":              ctx.get("cliente_cpf", "") or "",
        "EMAIL":            ctx.get("cliente_email", "") or "",
        "TELEFONE":         ctx.get("cliente_telefone", "") or "",
        "RES_LOGRADOURO":   ctx.get("res_logradouro", "") or "",
        "RES_NUMERO":       ctx.get("res_numero", "") or "",
        "RES_COMPLEMENTO":  ctx.get("res_complemento", "") or "",
        "RES_BAIRRO":       ctx.get("res_bairro", "") or "",
        "RES_CIDADE":       ctx.get("res_cidade", "") or "",
        "RES_CEP":          ctx.get("res_cep", "") or "",
        "RES_UF":           ctx.get("res_uf", "") or "",
        "INST_LOGRADOURO":  ctx.get("inst_logradouro", "") or "",
        "INST_NUMERO":      ctx.get("inst_numero", "") or "",
        "INST_COMPLEMENTO": ctx.get("inst_complemento", "") or "",
        "INST_BAIRRO":      ctx.get("inst_bairro", "") or "",
        "INST_CIDADE":      ctx.get("inst_cidade", "") or "",
        "INST_CEP":         ctx.get("inst_cep", "") or "",
        "INST_UF":          ctx.get("inst_uf", "") or "",
        "VALOR_ENTRADA":    pag.get("entrada_valor", "") or "",
        "FORMA_ENTRADA":    pag.get("entrada_tipo", "") or "",
        "DATA_ENTRADA":     pag.get("entrada_data", "") or "",
        "MODALIDADE":       pag.get("nome_forma", "") or "",
        "NUM_PARCELAS":     pag.get("num_parcelas", "") or "",
        "TIPO":             pag.get("forma_parcela", "") or "",
        "TOTAL_CONTRATO":   pag.get("valor_contrato", "") or "",
        "CONSULTOR_NOME":     ctx.get("consultor_nome", "") or "",
        "CONSULTOR_TELEFONE": ctx.get("consultor_tel", "") or "",
        "TESTEMUNHA_1_NOME": t1n,
        "TESTEMUNHA_1_DOC":  t1c,
        "TESTEMUNHA_2_NOME": t2n,
        "TESTEMUNHA_2_DOC":  t2c,
        "NOME_TESTEMUNHA_1": t1n,
        "NOME_TESTEMUNHA2":  t2n,
        "NOME_TESTEMUNHA_2": t2n,
        "NOME_EMPRESA":      loja.get("nome", "") or "",
        "CNPJ_EMPRESA":      loja.get("cnpj", "") or "",
        "CPF_CLIENTE":       ctx.get("cliente_cpf", "") or "",
        "CPF_TESTEMUNHA_1":  t1c,
        "CPF_TESTEMUNHA_2":  t2c,
    }
```

3d. **`construir_contexto`** — novo parâmetro `loja=None`; fallback de telefone/e-mail usa a loja; injeta `loja` no ctx (alterar a assinatura na ex-linha 500 e o dict `ctx`):

```python
def construir_contexto(cliente: dict, usuario: dict, forma_pagamento_json: str,
                       loja: dict = None) -> dict:
    """Monta o dicionário completo para preencher o contrato.

    `loja` (F3): dict com os dados da loja (nome/cnpj/codigo/telefone/email/testemunhas).
    Os marcadores de empresa/testemunha e o fallback de telefone/e-mail do consultor
    saem daqui. Sem loja → campos em branco.
    """
    loja = loja or {}
```

Dentro do `ctx = {...}`, trocar as duas linhas de fallback e acrescentar `loja`:

```python
        "consultor_tel":   (usuario.get("telefone") or "").strip() or (loja.get("telefone") or ""),
        "consultor_email": (usuario.get("email")    or "").strip() or (loja.get("email")    or ""),
```

e, junto de `"_pag": pag,`, adicionar:

```python
        "loja":            loja,   # dados da loja para _montar_mapping (F3)
```

- [ ] **Step 4: Run the full contrato suite**

Run: `python3 -m pytest tests/test_contrato.py tests/test_contrato_loja.py -v`
Expected: PASS (todos). Se algum outro teste de `construir_contexto` falhar por esperar a constante antiga, corrigir passando `loja=` com os valores esperados (mesma técnica do passo 1e).

- [ ] **Step 5: Verify no constant remains**

Run: `grep -nE "_NOME_EMPRESA|_CNPJ_EMPRESA|_TESTEMUNHAS|_CODIGO_LOJA|_TELEFONE_LOJA|_EMAIL_LOJA" mod_contrato.py`
Expected: nenhuma linha (saída vazia).

- [ ] **Step 6: Commit**

```bash
git add mod_contrato.py tests/test_contrato.py
git commit -m "feat(contrato): loja vira fonte unica (remove constantes) — F3"
```

---

## Task 3: Coluna `Contrato.loja_snapshot_json`

**Files:**
- Modify: `database.py:369-392` (model) e `database.py:471-481` (migração)
- Modify: `tests/test_contrato_loja.py` (teste de migração)

- [ ] **Step 1: Write the failing test**

Acrescentar em `tests/test_contrato_loja.py`:

```python
import sqlite3
import database

_TABELAS_LEGADO = ["clientes", "usuarios", "projetos_meta", "contratos",
                   "orcamentos", "orcamento_ambientes", "briefings", "parceiros"]


def _db_legado(path):
    conn = sqlite3.connect(path)
    for t in _TABELAS_LEGADO:
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY)")
    conn.commit(); conn.close()


def test_migracao_cria_loja_snapshot_json(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(contratos)")}
    conn.close()
    assert "loja_snapshot_json" in cols


def test_migracao_loja_snapshot_idempotente(tmp_path, monkeypatch):
    db = str(tmp_path / "legado.db")
    _db_legado(db)
    monkeypatch.setattr(database, "DB_PATH", db)
    database._migrar_colunas()
    database._migrar_colunas()   # 2ª vez não quebra
    conn = sqlite3.connect(db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(contratos)")]
    conn.close()
    assert cols.count("loja_snapshot_json") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_contrato_loja.py -k snapshot -v`
Expected: FAIL — `loja_snapshot_json` ausente.

- [ ] **Step 3: Implement — model + migração**

3a. Em `database.py`, no model `Contrato` (após a linha 387 `loja_id ...`):

```python
    loja_snapshot_json   = Column(Text,     nullable=True)   # snapshot dos dados da loja (F3)
```

3b. Em `_migrar_colunas`, na lista de colunas de `contratos` (linhas 471-479), acrescentar uma entrada:

```python
        ("loja_snapshot_json", "TEXT"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_contrato_loja.py -k snapshot -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_contrato_loja.py
git commit -m "feat(db): coluna contratos.loja_snapshot_json (F3)"
```

---

## Task 4: `main.py` — helper, snapshot, validação/confirmação e passagem da loja

**Files:**
- Modify: `main.py` (helper `_loja_dict_para_contrato`; 2 pontos de geração ~2662-2704 e ~3104-3128)
- Modify: `tests/test_contrato_loja.py` (teste do helper com db stub)

- [ ] **Step 1: Write the failing test (helper com stub de db)**

Acrescentar em `tests/test_contrato_loja.py`:

```python
def test_loja_dict_para_contrato_mapeia_campos():
    import main

    class _FakeLoja:
        id = 1; nome = "INSPIRIUM"; cnpj = "19.152.134/0001-56"; codigo = "INS"
        telefone = "(12) 3341-8777"; email = "sac@x.com"; cep = "12200-000"
        logradouro = "Rua A"; numero = "100"; complemento = ""; bairro = "Centro"
        cidade = "SJC"; estado = "SP"
        testemunha1_nome = "Jaime"; testemunha1_cpf = "123.456.789-00"
        testemunha2_nome = "Felipe"; testemunha2_cpf = "987.654.321-00"

    class _FakeDB:
        def get(self, model, pk):
            return _FakeLoja() if pk == 1 else None

    d = main._loja_dict_para_contrato(_FakeDB(), 1)
    assert d["codigo"] == "INS"
    assert d["nome"] == "INSPIRIUM"
    assert d["testemunha1_cpf"] == "123.456.789-00"
    assert d["cidade"] == "SJC"


def test_loja_dict_para_contrato_sem_loja():
    import main
    class _FakeDB:
        def get(self, model, pk): return None
    assert main._loja_dict_para_contrato(_FakeDB(), None) == {}
    assert main._loja_dict_para_contrato(_FakeDB(), 999) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_contrato_loja.py -k loja_dict -v`
Expected: FAIL — `module 'main' has no attribute '_loja_dict_para_contrato'`.

- [ ] **Step 3: Implement the helper**

Em `main.py`, junto de `_ator_dict` (perto da linha 3640), adicionar:

```python
def _loja_dict_para_contrato(db, loja_id):
    """Dict plano dos dados da loja para alimentar/snapshotar o contrato (F3).
    Retorna {} se não houver loja resolvível."""
    if not loja_id:
        return {}
    loja = db.get(Loja, loja_id)
    if not loja:
        return {}
    return {
        "id": loja.id,
        "nome": loja.nome or "", "cnpj": loja.cnpj or "", "codigo": loja.codigo or "",
        "telefone": loja.telefone or "", "email": loja.email or "",
        "cep": loja.cep or "", "logradouro": loja.logradouro or "",
        "numero": loja.numero or "", "complemento": loja.complemento or "",
        "bairro": loja.bairro or "", "cidade": loja.cidade or "", "estado": loja.estado or "",
        "testemunha1_nome": loja.testemunha1_nome or "", "testemunha1_cpf": loja.testemunha1_cpf or "",
        "testemunha2_nome": loja.testemunha2_nome or "", "testemunha2_cpf": loja.testemunha2_cpf or "",
    }
```

- [ ] **Step 4: Run helper test to verify it passes**

Run: `python3 -m pytest tests/test_contrato_loja.py -k loja_dict -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Wire site #1 (geração principal, ~2648-2704)**

Confirmar que `json` já está importado no topo de `main.py` (`grep -n "^import json" main.py`); se não, adicionar `import json`.

5a. Logo após o bloco de validação do cliente (o `if faltando:` que termina em ~2661), **antes** de montar `usuario_ctx`, inserir a resolução + validação da loja:

```python
                    from mod_contrato import validar_loja_para_contrato
                    ator = _ator_dict(db, usuario)
                    loja_dict = _loja_dict_para_contrato(db, ator.get("loja_id"))
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
```

5b. Passar a loja para `construir_contexto` (linha ~2670):

```python
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
```

5c. Após obter/criar o `contrato` e antes de `db.commit()` (perto da linha 2697), fixar a loja e gravar o snapshot:

```python
                    if not contrato.loja_id:
                        contrato.loja_id = ator.get("loja_id")
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
```

5d. Trocar a geração do número (linha ~2703) para usar o código da loja:

```python
                        contrato.num_contrato = gerar_num_contrato(_existing, loja_dict.get("codigo", ""))
```

- [ ] **Step 6: Wire site #2 (regeração, ~3102-3128)**

Replicar o mesmo padrão neste segundo ponto. Após `_montar_dados_projeto_para_contrato(...)` (linha ~3103) e antes de `construir_contexto`:

```python
                    from mod_contrato import validar_loja_para_contrato
                    ator = _ator_dict(db, usuario)
                    loja_dict = _loja_dict_para_contrato(db, contrato.loja_id or ator.get("loja_id"))
                    faltando_loja = validar_loja_para_contrato(loja_dict)
                    if faltando_loja and not req.get("confirmar_loja_incompleta"):
                        self.send_json({
                            "ok": False,
                            "precisa_confirmar_loja": True,
                            "campos_loja_faltando": faltando_loja,
                            "erro": "Dados da loja incompletos.",
                        }, code=400)
                        return
```

Passar a loja para `construir_contexto` (linha ~3112):

```python
                    variaveis = construir_contexto(
                        cliente_dict,
                        usuario_ctx,
                        pag_json,
                        loja_dict,
                    )
```

E antes de `db.commit()` (após a linha ~3129 `contrato.pdf_path = pdf_path`):

```python
                    if not contrato.loja_id:
                        contrato.loja_id = ator.get("loja_id")
                    contrato.loja_snapshot_json = json.dumps(loja_dict, ensure_ascii=False)
```

- [ ] **Step 7: Run the full suite + API smoke**

Run: `python3 -m pytest -q`
Expected: PASS (167 antigos + novos da F3).

API smoke (servidor real, loja seed ainda com CPF placeholder → deve pedir confirmação):

```bash
python3 main.py &   # sobe o servidor (porta padrão do projeto)
# autenticar e POSTar /api/projetos/<nome>/contrato sem confirmar_loja_incompleta
# Esperado no JSON: {"ok": false, "precisa_confirmar_loja": true, "campos_loja_faltando": [...]}
# Repetir com "confirmar_loja_incompleta": true → contrato gerado; conferir no banco:
#   SELECT num_contrato, loja_id, substr(loja_snapshot_json,1,60) FROM contratos ORDER BY id DESC LIMIT 1;
```

- [ ] **Step 8: Commit**

```bash
git add main.py tests/test_contrato_loja.py
git commit -m "feat(contrato): main resolve loja, snapshot e aviso de loja incompleta — F3"
```

---

## Task 5: Front — confirmação "loja incompleta" em `gerarContrato()`

**Files:**
- Modify: `static/index.html` (`gerarContrato`, ~8019-8097)

- [ ] **Step 1: Add the `confirmarLojaIncompleta` param + signatário reaproveitado**

Trocar a assinatura e a coleta do signatário no início de `gerarContrato` (linhas ~8019 e ~8037-8046):

```javascript
async function gerarContrato(confirmarLojaIncompleta = false, signatarioPre = undefined) {
```

```javascript
  // É o próprio cliente cadastrado que vai assinar? (não repergunta numa reconfirmação)
  let signatarioOverride = signatarioPre;
  if (signatarioPre === undefined) {
    const ehCliente = await confirmarPopup('O signatário do contrato é o próprio cliente cadastrado?',
      {titulo:'Signatário do contrato', okLabel:'Sim, é o cliente', cancelLabel:'Não'});
    if (!ehCliente) {
      signatarioOverride = await coletarSignatarioOverride();
      if (!signatarioOverride) {  // cancelou
        if (btn) { btn.disabled = false; btn.textContent = 'Gerar Contrato'; }
        return;
      }
    } else {
      signatarioOverride = null;
    }
  }
```

- [ ] **Step 2: Send the flag in the request body**

No `body: JSON.stringify({...})` (linha ~8052), acrescentar:

```javascript
        confirmar_loja_incompleta: confirmarLojaIncompleta,
```

- [ ] **Step 3: Handle `precisa_confirmar_loja` in the response**

No bloco `if (!d.ok) {` (linha ~8064), logo após reabilitar o botão e **antes** do `if (Array.isArray(d.campos_faltando)...)`, inserir:

```javascript
      if (d.precisa_confirmar_loja) {
        const ok = await confirmarPopup(
          'Dados da loja incompletos:\n\n• ' + (d.campos_loja_faltando || []).join('\n• ') +
          '\n\nGerar o contrato assim mesmo?',
          {titulo:'Loja incompleta', okLabel:'Gerar assim', cancelLabel:'Cancelar'});
        if (ok) return gerarContrato(true, signatarioOverride ?? null);
        return;
      }
```

- [ ] **Step 4: Manual verification (Playwright/servidor real)**

Run: subir o servidor, abrir o app, gerar contrato com a loja seed (CPF de testemunha ainda placeholder).
Expected: aparece o diálogo "Loja incompleta — Gerar assim? / Cancelar"; "Cancelar" não gera; "Gerar assim" gera. Depois, preencher os CPFs em "Dados da loja" (console da F2) e gerar de novo → sai sem aviso. 0 erros de console.

- [ ] **Step 5: Commit**

```bash
git add static/index.html
git commit -m "feat(ui): confirmar geracao com loja incompleta — F3"
```

---

## Task 6: DEV_LOG + suíte completa + fechamento

**Files:**
- Modify: `DEV_LOG.md`

- [ ] **Step 1: Run the whole suite**

Run: `python3 -m pytest -q`
Expected: PASS (167 antigos + novos da F3), 0 falhas.

- [ ] **Step 2: Registrar a sessão no DEV_LOG**

Acrescentar uma entrada em `DEV_LOG.md` resumindo a F3: loja vira fonte do contrato; constantes removidas; `loja_snapshot_json`; aviso de loja incompleta (avisa e deixa gerar); arquivos tocados; suíte verde.

- [ ] **Step 3: Commit**

```bash
git add DEV_LOG.md
git commit -m "docs(dev-log): F3 — contrato puxa da loja (sessao)"
```

---

## Self-Review

**1. Spec coverage:**
- Snapshot (decisão 1) → Task 3 (coluna) + Task 4 passos 5c/6 (grava a cada geração). ✓
- Avisar mas deixar gerar (decisão 2) → Task 1 (validador) + Task 4 (handshake `precisa_confirmar_loja`) + Task 5 (UI). ✓
- Remover constantes (decisão 3) → Task 2 passos 3a + Step 5 (grep garante remoção). ✓
- Refoto a cada geração (decisão 4) → Task 4 grava `loja_snapshot_json` em toda geração; congela pela trava pós-assinatura existente. ✓
- Telefone/e-mail/endereço obrigatórios (revisão do usuário) → Task 1 validador + teste. ✓
- `gerar_num_contrato` usa o código da loja → Task 2 (3b) + Task 4 (5d). ✓
- Loja = consultor, fixada na 1ª geração → Task 4 (5c/6: `if not contrato.loja_id`). ✓
- Dois pontos de geração via mesmo padrão → Task 4 passos 5 e 6. ✓

**2. Placeholder scan:** nenhum "TBD/TODO/implement later" — todo passo traz código/contagem/comando reais.

**3. Type consistency:** `validar_loja_para_contrato(loja)->list`, `_loja_dict_para_contrato(db, loja_id)->dict`, `construir_contexto(cliente, usuario, forma, loja=None)`, `gerar_num_contrato(existing, loja_codigo, data=None)`, chave `ctx["loja"]` consumida por `_montar_mapping` — nomes idênticos entre as tasks. Campo `loja_snapshot_json` igual no model, migração e gravação.

---

## Execution Handoff

(ver fim do brainstorm — o autor oferece subagent-driven vs inline após aprovação do plano.)
