# Fiscal — Painel de Config → Emitente (US-36) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** O Painel Fiscal (aba Fiscal do admin) passa a **configurar o `Emitente` da loja** (não mais `PerfilFiscal`), expõe **endereço + CSOSN contribuinte**, e o modelo `PerfilFiscal` é aposentado (tabela mantida como legado).

**Architecture:** Retarget dos 3 endpoints `…/perfil-fiscal[/segredos|/ambiente]` de `PerfilFiscal → Emitente` (via `loja.emitente_id`, cria se faltar) → campos novos no form → remoção do modelo `PerfilFiscal` morto. Verde a cada tarefa. Branch `feat/fiscal-painel-emitente`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/2026-07-06-fiscal-painel-emitente-design.md`.

**Ler antes:** o spec; `main.py` handlers `GET/PUT /api/admin/lojas/<id>/perfil-fiscal` (~1494-1530), `PUT …/perfil-fiscal/segredos` (~4377), `PUT …/perfil-fiscal/ambiente` (~4413/4455); `mod_fiscal.py` (`perfil_padrao_teste`, `validar_config`, `pode_ativar_producao`, `focus_client_para_loja` a remover, `focus_client_para_emitente` a manter); `database.py` (`PerfilFiscal` ~500 a remover, `Emitente` ~544, `Loja.emitente_id`); `static/index.html` (`adminFiscalCarregar/Salvar/SalvarSegredos/AtivarAmbiente` ~6988-7090); `fiscal_cripto` (encrypt/token_definido). **Baseline 562 passed.** Teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

---

## Task 1: Retarget dos endpoints `perfil-fiscal` → `Emitente` (+ campos novos)

**Files:** Modify `main.py`, `mod_fiscal.py`; Test: `tests/test_perfil_fiscal_e2e.py`.

- [ ] **Step 1: Ler os 3 handlers atuais** (`GET/PUT perfil-fiscal`, `/segredos`, `/ambiente`) e entender: allowlist de config, escrita write-only de tokens, guarda de produção. Hoje usam `db.query(PerfilFiscal).filter_by(loja_id=loja.id)`.

- [ ] **Step 2: `mod_fiscal.emitente_padrao_teste()`** — novo (ao lado de `perfil_padrao_teste`, que fica por ora): retorna os defaults de um Emitente novo:
```python
def emitente_padrao_teste():
    return {
        "razao_social": None, "inscricao_estadual": None, "inscricao_municipal": None,
        "regime_tributario": "simples", "csosn_padrao": "102", "csosn_contribuinte": "101",
        "cfop_dentro_uf": "5102", "cfop_fora_uf": "6102",
        "serie_nfe": None, "discrimina_impostos": 1, "cnae_servico": _CNAE_PLACEHOLDER,
        "cod_servico_municipio": None, "aliquota_iss": 5.0, "retencao_json": None,
        "municipio_ibge": None, "papel_cnpj": "loja_produto_servico",
        "placeholders": list(_CAMPOS_PADRAO),
    }
```

- [ ] **Step 3: Adaptar o teste e2e** — em `tests/test_perfil_fiscal_e2e.py`, apontar as asserções ao **Emitente**: o setup passa a garantir/criar o Emitente da loja; após `PUT perfil-fiscal`, ler `Emitente` (via `loja.emitente_id`) e conferir os campos aplicados (incl. **endereço** e **csosn_contribuinte**); GET nunca retorna token; segredos write-only; ambiente com guarda. Rodar → **falha** (endpoints ainda em PerfilFiscal).

- [ ] **Step 4: `main.py` — retarget dos 3 handlers**
Substituir `db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()` por resolução do Emitente da loja:
```python
    em = db.get(Emitente, loja.emitente_id) if loja.emitente_id else None
```
- **GET:** se `em` → devolve os campos do Emitente (incl. `logradouro/numero/bairro/cidade/uf/cep`, `csosn_contribuinte`) + `token_homolog_definido`/`token_prod_definido` (via `fiscal_cripto.token_definido`) + `placeholders` (de `em.placeholders_json`) + `ambiente_ativo`. **Nunca** os tokens. Se `em` None → devolve `mod_fiscal.emitente_padrao_teste()` + `token_*_definido=False`, `ambiente_ativo="homologacao"` (sem criar).
- **PUT config:** se `em` None → `em = Emitente(**<defaults mínimos>)`, `db.add(em)`, `db.flush()`, `loja.emitente_id = em.id`. Aplicar a **allowlist** ao `em`: a allowlist atual **+** `logradouro, numero, bairro, cidade, uf, cep, csosn_contribuinte, cert_validade, cert_cnpj`. Persistir `placeholders_json`. `db.commit()`.
- **PUT segredos:** resolver/criar `em`; gravar `focus_token_homolog_enc`/`prod_enc` = `fiscal_cripto.encrypt(valor)` **só** quando o valor vier não-vazio (mantém o existente se vazio).
- **PUT ambiente:** `em.ambiente_ativo = novo`; manter a guarda: produção só se `mod_fiscal.pode_ativar_producao(placeholders)` **e** `token_prod_definido`.
> Confira o import de `Emitente` no topo do `main.py` (já existe). Mantenha `PerfilFiscal` importado por ora (removido na Task 3).

- [ ] **Step 5: Rodar** `python3 -m pytest -q` → verde (o e2e adaptado passa; nada mais quebra — a emissão já usava Emitente). **Commit:**
```
git add main.py mod_fiscal.py tests/test_perfil_fiscal_e2e.py
git commit -m "feat(fiscal): painel de config passa a operar o Emitente da loja (+ endereco + csosn_contribuinte)"
```

---

## Task 2: Painel (aba Fiscal) — campos endereço + CSOSN contribuinte

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** em `adminFiscalCarregar` (render do form) adicionar uma **seção "Endereço do Emitente"**
(inputs para `logradouro, numero, bairro, cidade, uf, cep`) e o campo **CSOSN contribuinte** (ao lado do
`csosn_padrao`, rotulado "CSOSN não-contribuinte"). Preencher com os valores do GET (`d.logradouro` etc.,
`d.csosn_contribuinte`). `esc()` nos valores.

- [ ] **Step 2:** em `adminFiscalSalvar` incluir os novos campos no `payload` do PUT (`logradouro`, `numero`,
`bairro`, `cidade`, `uf`, `cep`, `csosn_contribuinte`). Manter a lógica de placeholders/badges.

- [ ] **Step 3:** checagem estrutural do `<script>` (balanceamento — não piorar) + `python3 -m pytest -q`
verde. **Commit:**
```
git add static/index.html
git commit -m "feat(fiscal): painel fiscal edita endereco do emitente + CSOSN contribuinte"
```

---

## Task 3: Aposentar `PerfilFiscal` (modelo + focus_client_para_loja); manter a tabela

**Files:** Modify `database.py`, `mod_fiscal.py`, `main.py`, `emissor_focus.py`, `tests/`.

- [ ] **Step 1:** `grep -rn "PerfilFiscal\|focus_client_para_loja\|perfil_padrao_teste" --include=*.py .`
(fora de `.claude/`/`docs/`) para inventariar as refs.

- [ ] **Step 2:** Remover:
- `database.py`: a classe `PerfilFiscal` (e do import em `main.py`). **NÃO** dropar a tabela `perfil_fiscal`
  (não adicionar migração de drop; `create_all` a ignora).
- `mod_fiscal.py`: `focus_client_para_loja` (morto) e `perfil_padrao_teste` (substituído por
  `emitente_padrao_teste`). Manter `validar_config`, `pode_ativar_producao`, `focus_client_para_emitente`, `REGIMES/PAPEIS/AMBIENTES`.
- `emissor_focus.py`: docstring `focus_client_para_loja` → `focus_client_para_emitente`.

- [ ] **Step 3:** Testes: `tests/test_perfil_fiscal_model.py` (testava o modelo removido) → **remover** ou
migrar para um teste do Emitente (já há `tests/test_emitente_model.py`); `tests/test_mod_fiscal.py` → ajustar
para `emitente_padrao_teste` e remover o teste de `focus_client_para_loja`. Rodar `grep` até **zerar** refs a
`PerfilFiscal`/`focus_client_para_loja`/`perfil_padrao_teste` no código (fora de docs/legado).

- [ ] **Step 4: Rodar** `python3 -m pytest -q` → verde. **Commit:**
```
git add database.py mod_fiscal.py main.py emissor_focus.py tests/
git commit -m "refactor(fiscal): remove PerfilFiscal (modelo morto) + focus_client_para_loja; tabela fica legado"
```

---

## Task 4: Fechamento — docs

**Files:** Modify spec (Status), `DEV_LOG.md`, `docs/historias/BACKLOG.md`.

- [ ] **Step 1:** `python3 -m pytest -q` verde.
- [ ] **Step 2:** spec → **IMPLEMENTADO**; DEV_LOG (gap do painel de config **fechado**: painel opera o
Emitente; PerfilFiscal aposentado, tabela legado; endereço/CSOSN contribuinte editáveis); BACKLOG — marcar
**US-36** feita; US-37 (UI do Perfil de Emissão) segue aberta.
- [ ] **Step 3: Commit** + re-ingerir MCP no merge.

---

## Self-review do plano
- **Cobertura do spec:** §3 endpoints (T1) · §4 painel (T2) · §5 limpeza (T3) · §6 testes (T1/T3) · §2
  campos novos (T1 backend + T2 UI) · §7 fora de escopo respeitado (US-37; não dropar tabela).
- **Sem placeholders:** cada passo com rotina concreta; "ler os handlers"/"grep" são verificações.
- **Consistência:** `Emitente`/`loja.emitente_id`, `emitente_padrao_teste`, allowlist (endereço +
  `csosn_contribuinte`), `token_*_definido`, `pode_ativar_producao` — idênticos entre tarefas. Verde a cada
  tarefa (retarget → UI → remove morto).
```
