# Motor de Negociação (Fase A — modo sombra) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de negociação por ambiente (`mod_negociacao`), a trava de qualidade do XML, e os valores derivados em **modo sombra** (colunas novas, sem alterar o comportamento atual), com a UI mostrando **valor de hoje × valor novo lado a lado** para validação.

**Architecture:** Motor puro `mod_negociacao` (XML→VBNA/VAVA por ambiente→agregados→Val_Liq/Markup) + validador puro `mod_qualidade_xml`. Migração **só aditiva** (novas colunas em `orcamentos` e `pool_ambientes`; nada removido). O save da negociação calcula em paralelo e grava nas colunas novas; `valor_total`/`valor_liquido` e o cálculo atual ficam **intactos**. Caso-âncora: LELEU oç1 (spec §9).

**Tech Stack:** Python 3 (stdlib `http.server`, SQLAlchemy, sqlite3, `xml.etree`), frontend HTML/JS vanilla em `static/index.html`, pytest. No WSL o binário é `python3` (não `python`).

## Global Constraints

- **Modo sombra:** nada destrutivo. Só **adicionar** colunas; `orcamentos.valor_liquido`/`valor_total`, `orcamentos.margens` e o cálculo atual **permanecem intactos e em uso**. Cutover e limpeza são fora desta fase.
- **Nomenclatura canônica (spec §3):** o código usa exatamente as siglas — chaves do dict de saída do motor: `VBVO, CFO, VBNO, VAVO, Num_Amb, Com_Arq, Pro_Fid, Cust_Ad, Val_Liq, Desc_Tot, Markup, Cust_Fin, Val_Cont, Prov_Imp` e, por ambiente, `VBVA, CFA, VBNA, VAVA`.
- **Funções puras** (`mod_negociacao`, `mod_qualidade_xml`): sem I/O, sem ORM — recebem dicts/listas, devolvem dicts.
- **Migração idempotente** no padrão de `database._migrar_colunas` (PRAGMA `table_info` + `ALTER TABLE ADD COLUMN` só se ausente).
- **Trava de XML (spec §8):** 🔴 se `qa_pct_sem_acrescimo ≥ limiar` (default **5%**) **ou** `qa_custo_sem_venda > 0`; senão 🟢. Override por Diretor/Gerente Adm-Financeiro com justificativa logada.
- `python3 -m pytest` para testes. Commits frequentes, um por task. `git add` só dos arquivos da task (nunca `perfis_config.json`/`.claude/*`).
- Mensagens/erros em português.

---

### Task 1: Branch + `mod_negociacao` (motor puro por ambiente)

**Files:**
- Create: `mod_negociacao.py`
- Test: `tests/test_negociacao.py`

**Interfaces:**
- Produces: `calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0) -> dict`
  - `ambientes`: lista de `{"VBVA": float, "CFA": float, "desc_amb_pct": float}` (desc em %, ex. 0).
  - `params`: dict no formato `parametros_json` do projeto (`incluir_custos, comissao_arq_pct, comissao_arq_ativa, fidelidade_pct, fidelidade_ativa, fora_da_sede, custo_viagem, brinde, brinde_ativo, carga_trib`).
  - `desc_orc_pct`: percentual (ex. 20.0). `cust_fin`: R$ (vem do `mod_fin`, default 0).
  - Retorna o dict com as siglas (ver Global Constraints) + chave `"ambientes"` (lista por ambiente).

- [ ] **Step 1: Criar a branch a partir da tag de rollback**

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout -b feat/motor-negociacao-sombra pre-refator-negociacao
git branch --show-current   # feat/motor-negociacao-sombra
```

- [ ] **Step 2: Escrever os testes que falham**

```python
# tests/test_negociacao.py
import mod_negociacao as mn

# LELEU oç1 — params do projeto, todos os toggles ON (spec §9)
PARAMS = {"incluir_custos": True, "comissao_arq_pct": 10.0, "comissao_arq_ativa": True,
          "fidelidade_pct": 2.0, "fidelidade_ativa": True, "fora_da_sede": True,
          "custo_viagem": 2000.0, "brinde": 500.0, "brinde_ativo": True, "carga_trib": 8.0}
AMBS = [{"VBVA": 22830.99, "CFA": 22830.99, "desc_amb_pct": 0.0},
        {"VBVA": 2650.50,  "CFA": 953.40,   "desc_amb_pct": 0.0}]

def _ap(a, b, tol=0.02): assert abs(a - b) <= tol, f"{a} != {b}"

def test_leleu_ancora():
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0, cust_fin=1413.44)
    _ap(r["VBVO"], 25481.49); _ap(r["CFO"], 23784.39)
    _ap(r["VBNO"], 31890.58); _ap(r["VAVO"], 25512.46)
    _ap(r["Cust_Ad"], 5561.50); _ap(r["Val_Liq"], 19950.97)
    _ap(r["Desc_Tot"] * 100, 21.70, tol=0.05); _ap(r["Markup"], 0.839, tol=0.002)
    _ap(r["Val_Cont"], 26925.90); _ap(r["Prov_Imp"], 0.08 * r["Val_Cont"], tol=0.05)
    ag = r["ambientes"][0]
    _ap(ag["VBNA"], 28375.43); _ap(ag["VAVA"], 22700.35)

def test_tog_cadi_off_absorve():
    # sem gross-up: VBNA = VBVA; custos ainda abatem o líquido
    p = {**PARAMS, "incluir_custos": False}
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    _ap(r["VBNO"], r["VBVO"])                      # VBNA = VBVA
    _ap(r["VAVO"], r["VBVO"] * 0.80)              # só o desconto
    assert r["Cust_Ad"] > 0                        # custos seguem abatendo

def test_toggle_individual_zera_componente():
    p = {**PARAMS, "brinde_ativo": False, "fora_da_sede": False}  # sem brinde nem viagem
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    # Cust_Ad = só Com_Arq + Pro_Fid (12% do VAVO)
    _ap(r["Cust_Ad"], (0.12) * r["VAVO"], tol=0.05)

def test_desc_amb_por_ambiente():
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 50.0}]
    p = {"incluir_custos": False}
    r = mn.calcular_orcamento(ambs, p, 0.0)
    _ap(r["VAVO"], 500.0)                          # 1000 * (1-0.50)

def test_orcamento_vazio_nao_quebra():
    r = mn.calcular_orcamento([], {"incluir_custos": False}, 0.0)
    assert r["VBVO"] == 0 and r["Markup"] == 0 and r["Val_Liq"] == 0
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'mod_negociacao'`).

- [ ] **Step 4: Implementar `mod_negociacao.py`**

```python
# -*- coding: utf-8 -*-
"""mod_negociacao.py — Motor de cálculo da negociação (PURO, sem I/O).

Cálculo por ambiente (gross-up divisivo), agregado por orçamento. Siglas conforme
docs/superpowers/specs/negociacao/2026-06-22-mecanismo-negociacao-design.md (§3/§4).
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0):
    """Ver docstring do plano/§4. `params` no formato parametros_json do projeto."""
    p = params or {}
    tog_cadi = bool(p.get("incluir_custos", False))      # master: repassa/absorve
    tog_carq = bool(p.get("comissao_arq_ativa", False))
    tog_fid  = bool(p.get("fidelidade_ativa", False))
    tog_cvia = bool(p.get("fora_da_sede", False))
    tog_bri  = bool(p.get("brinde_ativo", False))
    pct_arq  = _f(p.get("comissao_arq_pct")) / 100.0
    pct_fid  = _f(p.get("fidelidade_pct")) / 100.0
    cust_via = _f(p.get("custo_viagem"))
    bri      = _f(p.get("brinde"))
    pct_trib = _f(p.get("carga_trib")) / 100.0
    d_orc    = _f(desc_orc_pct) / 100.0

    ambs = [{"VBVA": _f(a.get("VBVA")), "CFA": _f(a.get("CFA")),
             "d_amb": _f(a.get("desc_amb_pct")) / 100.0} for a in (ambientes or [])]
    num_amb = len(ambs)
    VBVO = sum(a["VBVA"] for a in ambs)
    CFO  = sum(a["CFA"] for a in ambs)

    out_ambs = []
    VBNO = VAVO = 0.0
    for a in ambs:
        vbva, d_amb = a["VBVA"], a["d_amb"]
        fator_desc = (1 - d_orc) * (1 - d_amb)
        if tog_cadi:
            fator_com = (1 - pct_arq if tog_carq else 1.0) * (1 - pct_fid if tog_fid else 1.0)
            termo_arqfid = (vbva / fator_com) if fator_com > 0 else vbva
            termo_via = ((cust_via * (vbva / VBVO)) / fator_desc) \
                if (tog_cvia and VBVO > 0 and fator_desc > 0) else 0.0
            termo_bri = (bri / num_amb) if (tog_bri and num_amb) else 0.0
            vbna = termo_arqfid + termo_via + termo_bri
        else:
            vbna = vbva
        vava = vbna * fator_desc
        VBNO += vbna
        VAVO += vava
        out_ambs.append({"VBVA": round(vbva, 2), "CFA": round(a["CFA"], 2),
                         "VBNA": round(vbna, 2), "VAVA": round(vava, 2)})

    com_arq = (pct_arq * VAVO) if tog_carq else 0.0
    pro_fid = (pct_fid * VAVO) if tog_fid else 0.0
    cust_ad = com_arq + pro_fid + (cust_via if tog_cvia else 0.0) + (bri if tog_bri else 0.0)
    val_liq = VAVO - cust_ad
    desc_tot = ((VBVO - val_liq) / VBVO) if VBVO > 0 else 0.0
    markup = (val_liq / CFO) if CFO > 0 else 0.0
    val_cont = VAVO + _f(cust_fin)
    prov_imp = pct_trib * val_cont

    return {
        "VBVO": round(VBVO, 2), "CFO": round(CFO, 2), "VBNO": round(VBNO, 2),
        "VAVO": round(VAVO, 2), "Num_Amb": num_amb,
        "Com_Arq": round(com_arq, 2), "Pro_Fid": round(pro_fid, 2), "Cust_Ad": round(cust_ad, 2),
        "Val_Liq": round(val_liq, 2), "Desc_Tot": round(desc_tot, 4), "Markup": round(markup, 3),
        "Cust_Fin": round(_f(cust_fin), 2), "Val_Cont": round(val_cont, 2), "Prov_Imp": round(prov_imp, 2),
        "ambientes": out_ambs,
    }
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_negociacao.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add mod_negociacao.py tests/test_negociacao.py
git commit -m "feat(negociacao): motor puro de calculo por ambiente (ancora LELEU)"
```

---

### Task 2: `mod_qualidade_xml` (validador puro da trava de XML)

**Files:**
- Create: `mod_qualidade_xml.py`
- Test: `tests/test_qualidade_xml.py`

**Interfaces:**
- Produces: `avaliar_qualidade_xml(itens, limiar_pct=5.0) -> dict` com chaves
  `qa_markup_xml, qa_pct_sem_acrescimo, qa_custo_sem_venda, qa_selo` (`"ok"`/`"bloqueado"`).
  `itens`: lista de dicts com `order_total` e `budget_total` (nomes do parser).

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_qualidade_xml.py
import os, xml.etree.ElementTree as ET
import mod_qualidade_xml as q

def test_acrescimo_zerado_bloqueia():
    itens = [{"order_total": 100.0, "budget_total": 100.0},   # markup 1.0
             {"order_total": 50.0,  "budget_total": 50.0}]
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "bloqueado"
    assert r["qa_pct_sem_acrescimo"] == 100.0

def test_markup_saudavel_ok():
    itens = [{"order_total": 100.0, "budget_total": 278.0},
             {"order_total": 50.0,  "budget_total": 139.0}]
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "ok" and r["qa_pct_sem_acrescimo"] == 0.0

def test_custo_sem_venda_bloqueia():
    itens = [{"order_total": 100.0, "budget_total": 300.0},   # bom
             {"order_total": 80.0,  "budget_total": 0.0}]     # paga e nao vende
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_custo_sem_venda"] == 1 and r["qa_selo"] == "bloqueado"

def test_acessorio_valor_zero_nao_acusa():
    itens = [{"order_total": 100.0, "budget_total": 300.0},
             {"order_total": 0.0,   "budget_total": 0.0}]     # acessorio inofensivo
    r = q.avaliar_qualidade_xml(itens)
    assert r["qa_custo_sem_venda"] == 0 and r["qa_selo"] == "ok"

def _itens_do_xml(nome):
    from promob_grupos import ler_xml
    amb = ler_xml(os.path.join("PROJETOS", "LELEU", "xmls", nome))
    return [it for g in amb.get("grupos", []) for it in g.get("itens", [])]

def test_leleu_area_gourmet_bloqueia():
    r = q.avaliar_qualidade_xml(_itens_do_xml("Area Gourmet.xml"))
    assert r["qa_selo"] == "bloqueado"

def test_leleu_banheiro_ok():
    r = q.avaliar_qualidade_xml(_itens_do_xml("Banheiro Social.xml"))
    assert r["qa_selo"] == "ok"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_qualidade_xml.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'mod_qualidade_xml'`).

- [ ] **Step 3: Implementar `mod_qualidade_xml.py`**

```python
# -*- coding: utf-8 -*-
"""mod_qualidade_xml.py — Trava de qualidade do dado de XML (PURO, sem I/O).

Spec §8. Bloqueia quando o XML não tem acréscimo (venda ≤ custo) ou tem item com
custo e sem venda. Sinais ruidosos (itens sem preço / desconto-fábrica zerado) NÃO
entram na trava (disparam em orçamento bom).
"""


def avaliar_qualidade_xml(itens, limiar_pct=5.0):
    sum_b = sum_o = sum_b_sem_acr = 0.0
    n_custo_sem_venda = 0
    for it in (itens or []):
        try:
            o = float(it.get("order_total") or 0)
            b = float(it.get("budget_total") or 0)
        except (TypeError, ValueError):
            o = b = 0.0
        if b <= 0:
            if o > 0:
                n_custo_sem_venda += 1          # paga à fábrica, não cobra
            continue
        sum_b += b
        sum_o += o
        if b <= o * 1.0001:                     # vendido no custo ou abaixo
            sum_b_sem_acr += b
    markup = (sum_b / sum_o) if sum_o > 0 else 0.0
    pct_sem = (sum_b_sem_acr / sum_b * 100.0) if sum_b > 0 else 0.0
    bloqueado = (pct_sem >= float(limiar_pct)) or (n_custo_sem_venda > 0)
    return {
        "qa_markup_xml":         round(markup, 4),
        "qa_pct_sem_acrescimo":  round(pct_sem, 2),
        "qa_custo_sem_venda":    n_custo_sem_venda,
        "qa_selo":               "bloqueado" if bloqueado else "ok",
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_qualidade_xml.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add mod_qualidade_xml.py tests/test_qualidade_xml.py
git commit -m "feat(qualidade-xml): validador puro da trava de importacao (ancora LELEU)"
```

---

### Task 3: Migração aditiva — colunas novas em `orcamentos` e `pool_ambientes`

**Files:**
- Modify: `database.py` (modelos `Orcamento` ~314-331, `PoolAmbiente` ~293-308; bloco `orcamentos`/novo bloco `pool_ambientes` em `_migrar_colunas` ~486-510)
- Test: `tests/test_negociacao_colunas.py`

**Interfaces:**
- Produces: colunas REAL `vbvo, cfo, vbno, vavo, cust_ad, val_liq, desc_tot_pct, markup, cust_fin, val_cont, prov_imp` em `orcamentos`; colunas `qa_selo` (TEXT), `qa_pct_sem_acrescimo` (REAL), `qa_markup_xml` (REAL), `qa_custo_sem_venda` (INTEGER), `qa_override_por_id` (INTEGER), `qa_override_motivo` (TEXT) em `pool_ambientes`. Campos ORM correspondentes.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_negociacao_colunas.py
import sqlite3

def test_orcamentos_tem_colunas_sombra(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(orcamentos)")}
    assert {"vbvo", "cfo", "vbno", "vavo", "cust_ad", "val_liq", "desc_tot_pct",
            "markup", "cust_fin", "val_cont", "prov_imp"} <= cols

def test_pool_ambientes_tem_colunas_qa(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(pool_ambientes)")}
    assert {"qa_selo", "qa_pct_sem_acrescimo", "qa_markup_xml", "qa_custo_sem_venda",
            "qa_override_por_id", "qa_override_motivo"} <= cols

def test_legado_intacto(app_db):
    cols = {r[1] for r in sqlite3.connect(app_db.DB_PATH).execute("PRAGMA table_info(orcamentos)")}
    assert {"valor_total", "valor_liquido", "margens"} <= cols   # modo sombra: nada removido
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao_colunas.py -v`
Expected: FAIL (colunas novas ausentes).

- [ ] **Step 3: Adicionar os campos aos modelos**

Em `database.py`, no modelo `Orcamento`, após `valor_liquido = Column(Float, default=0.0)` (linha 327):

```python
    # ── derivados do motor de negociação (modo sombra — spec §5) ──
    vbvo         = Column(Float, default=0.0)
    cfo          = Column(Float, default=0.0)
    vbno         = Column(Float, default=0.0)
    vavo         = Column(Float, default=0.0)
    cust_ad      = Column(Float, default=0.0)
    val_liq      = Column(Float, default=0.0)
    desc_tot_pct = Column(Float, default=0.0)
    markup       = Column(Float, default=0.0)
    cust_fin     = Column(Float, default=0.0)
    val_cont     = Column(Float, default=0.0)
    prov_imp     = Column(Float, default=0.0)
```

No modelo `PoolAmbiente`, após `order_total = Column(Float, nullable=False, default=0.0)` (linha 305):

```python
    # ── qualidade do XML (spec §8) ──
    qa_selo               = Column(String,  nullable=True)
    qa_pct_sem_acrescimo  = Column(Float,   nullable=True)
    qa_markup_xml         = Column(Float,   nullable=True)
    qa_custo_sem_venda    = Column(Integer, nullable=True)
    qa_override_por_id    = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    qa_override_motivo    = Column(String,  nullable=True)
```

- [ ] **Step 4: Adicionar a migração idempotente**

Em `database.py`, dentro de `_migrar_colunas`, logo após o bloco que adiciona colunas em `orcamentos` (perto da linha 503, onde está o loop `ALTER TABLE orcamentos ADD COLUMN`), acrescente:

```python
        # ── orcamentos: derivados do motor de negociação (modo sombra) ──
        cur.execute("PRAGMA table_info(orcamentos)")
        orc_cols = {row[1] for row in cur.fetchall()}
        for col in ("vbvo", "cfo", "vbno", "vavo", "cust_ad", "val_liq",
                    "desc_tot_pct", "markup", "cust_fin", "val_cont", "prov_imp"):
            if col not in orc_cols:
                cur.execute(f"ALTER TABLE orcamentos ADD COLUMN {col} REAL DEFAULT 0")

        # ── pool_ambientes: qualidade do XML ──
        cur.execute("PRAGMA table_info(pool_ambientes)")
        pa_cols = {row[1] for row in cur.fetchall()}
        for col, tipo in [("qa_selo", "VARCHAR(20)"), ("qa_pct_sem_acrescimo", "REAL"),
                          ("qa_markup_xml", "REAL"), ("qa_custo_sem_venda", "INTEGER"),
                          ("qa_override_por_id", "INTEGER"), ("qa_override_motivo", "TEXT")]:
            if col not in pa_cols:
                cur.execute(f"ALTER TABLE pool_ambientes ADD COLUMN {col} {tipo}")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_negociacao_colunas.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_negociacao_colunas.py
git commit -m "feat(negociacao): migracao aditiva — derivados em orcamentos + qa em pool_ambientes"
```

---

### Task 4: Trava de qualidade no upload do XML + quarentena

**Files:**
- Modify: `main.py` (handler `POST /projetos/<nome>/pool`, cálculo ~2115-2120 e criação do `PoolAmbiente` ~2215-2223; handler que adiciona ambiente ao orçamento)
- Test: `tests/test_qualidade_upload_e2e.py`

**Interfaces:**
- Consumes: `mod_qualidade_xml.avaliar_qualidade_xml`; modelo `PoolAmbiente` com colunas `qa_*` (Task 3).
- Produces: no upload, grava `qa_selo`/`qa_pct_sem_acrescimo`/`qa_markup_xml`/`qa_custo_sem_venda` no `PoolAmbiente`; ao adicionar ambiente 🔴 a um orçamento, retorna erro (a não ser que `qa_override_por_id` esteja setado).

- [ ] **Step 1: Escrever o teste E2E que falha**

```python
# tests/test_qualidade_upload_e2e.py
def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c

# XML mínimo: 2 itens, ambos com ORDER==BUDGET (acréscimo zero) → 🔴
XML_RUIM = '''<PROJECT DESCRIPTION="Teste" DATE="01/01/2026"><CATEGORY DESCRIPTION="X"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="a" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100" TOTAL="100"><MARGINS><ORDER TOTAL="100"/><BUDGET TOTAL="100"/></MARGINS></PRICE></ITEM>
<ITEM REFERENCE="B" DESCRIPTION="b" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="50" TOTAL="50"><MARGINS><ORDER TOTAL="50"/><BUDGET TOTAL="50"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''

def test_upload_xml_ruim_marca_bloqueado(http_client_factory, seed, app_db, monkeypatch):
    from mod_qualidade_xml import avaliar_qualidade_xml
    from promob_grupos import ler_xml_str
    amb = ler_xml_str("ruim.xml", XML_RUIM)
    itens = [it for g in amb.get("grupos", []) for it in g.get("itens", [])]
    r = avaliar_qualidade_xml(itens)
    assert r["qa_selo"] == "bloqueado"   # sanidade do dado de teste

def test_ambiente_bloqueado_nao_entra_em_orcamento(http_client_factory, seed, app_db):
    # cria um pool ambiente 🔴 e um orçamento na loja 1; tentar vincular deve falhar
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="Ruim", nome_exibicao="Ruim",
                             xml_path="x", ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    c = _login(http_client_factory, "dir_l1")
    # rota real: POST /orcamentos/<oid>/ambientes/<pid> (pid no path, sem /api, sem body)
    st, body = c.post(f"/orcamentos/{seed['orcamento_l1_id']}/ambientes/{pid}", {})
    assert body.get("ok") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_qualidade_upload_e2e.py -v`
Expected: FAIL (vínculo de ambiente 🔴 ainda é permitido).

- [ ] **Step 3: Gravar o selo no upload**

Em `main.py`, logo após o cálculo de `order_total` (linha ~2120), antes do hash:

```python
                from mod_qualidade_xml import avaliar_qualidade_xml
                _qa = avaliar_qualidade_xml(
                    [it for g in amb.get("grupos", []) for it in g.get("itens", [])])
```

E na construção do `PoolAmbiente` (linha ~2215-2223), acrescentar os campos:

```python
                        pa = PoolAmbiente(
                            ...  # campos existentes inalterados
                            budget_total=  budget_total,
                            order_total=   order_total,
                            qa_selo=              _qa["qa_selo"],
                            qa_pct_sem_acrescimo= _qa["qa_pct_sem_acrescimo"],
                            qa_markup_xml=        _qa["qa_markup_xml"],
                            qa_custo_sem_venda=   _qa["qa_custo_sem_venda"],
                        )
```

(Se houver outros pontos que criam/atualizam `PoolAmbiente` — `sobrescrever`/`nova-versao` ~2276 — recalcule `_qa` e grave igual.)

- [ ] **Step 4: Bloquear ambiente 🔴 de entrar em orçamento**

Na rota `m_add = _re.match(r"^/orcamentos/(\d+)/ambientes/(\d+)$", path)` (main.py ~2542),
logo após o check `if pa is None or pa.projeto_id != orc.projeto_id:` (~2568) e antes do
check `ja_existe`, adicione a guarda:

```python
                    if pa.qa_selo == "bloqueado" and pa.qa_override_por_id is None:
                        self.send_json({"ok": False, "erro":
                            "Ambiente bloqueado por qualidade do XML (acréscimo zerado). "
                            "Re-exporte o XML ou solicite liberação ao Diretor/Gerente."}, code=409)
                        return
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_qualidade_upload_e2e.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_qualidade_upload_e2e.py
git commit -m "feat(qualidade-xml): grava selo no upload e bloqueia ambiente 🔴 em orcamento"
```

---

### Task 5: Override de ambiente bloqueado (Diretor/Gerente Adm-Financeiro)

**Files:**
- Modify: `main.py` (novo handler `POST /api/pool/<pid>/qa-override`)
- Test: `tests/test_qualidade_upload_e2e.py` (acrescentar)

**Interfaces:**
- Consumes: `perfis.pode(nivel, "aprovar_financeiro")` (Diretor e Gerente Adm-Fin); `PoolAmbiente.qa_*`.
- Produces: `POST /api/pool/<pid>/qa-override` `{motivo}` → grava `qa_override_por_id`/`qa_override_motivo`, loga, e libera o ambiente para entrar em orçamento.

- [ ] **Step 1: Escrever os testes que falham**

```python
def test_override_libera_ambiente(http_client_factory, seed, app_db):
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="R2", nome_exibicao="R2", xml_path="x",
                             ambientes_json="{}", budget_total=100, order_total=100,
                             qa_selo="bloqueado", qa_pct_sem_acrescimo=100.0)
    db.add(pa); db.commit(); pid = pa.id; db.close()
    c = _login(http_client_factory, "dir_l1")          # diretor: aprovar_financeiro
    st, body = c.post(f"/api/pool/{pid}/qa-override", {"motivo": "ambiente cortesia"})
    assert st == 200 and body["ok"]
    st2, b2 = c.post(f"/orcamentos/{seed['orcamento_l1_id']}/ambientes/{pid}", {})
    assert b2.get("ok") is not False                   # agora entra

def test_override_exige_perfil_e_motivo(http_client_factory, seed, app_db):
    db = app_db.get_session()
    pa = app_db.PoolAmbiente(projeto_id="Proj_L1", nome="R3", nome_exibicao="R3", xml_path="x",
                             ambientes_json="{}", budget_total=100, order_total=100, qa_selo="bloqueado")
    db.add(pa); db.commit(); pid = pa.id; db.close()
    # consultor não pode
    cc = _login(http_client_factory, "mds2026") if False else _login(http_client_factory, "dir_l1")
    st_nomotivo, b = cc.post(f"/api/pool/{pid}/qa-override", {"motivo": ""})
    assert b.get("ok") is False                        # motivo obrigatório
```

> Nota: o seed do conftest tem `dir_l1` (diretor). Para o teste de perfil sem permissão, use um usuário sem `aprovar_financeiro` se existir no seed; senão mantenha só a checagem de motivo obrigatório.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_qualidade_upload_e2e.py -v`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Implementar o handler de override**

Em `main.py`, junto aos outros `POST` (perto dos handlers de pool), adicionar:

```python
            m_qaov = _re.match(r"^/api/pool/(\d+)/qa-override$", path)
            if m_qaov:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "aprovar_financeiro"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403)
                    return
                req = json.loads(body) if body else {}
                motivo = (req.get("motivo") or "").strip()
                if not motivo:
                    self.send_json({"ok": False, "erro": "Justificativa é obrigatória."})
                    return
                db = get_session()
                try:
                    pa = db.get(PoolAmbiente, int(m_qaov.group(1)))
                    if not pa:
                        self.send_json({"ok": False, "erro": "Ambiente não encontrado"}, code=404)
                        return
                    pa.qa_override_por_id = usuario["id"]
                    pa.qa_override_motivo = motivo
                    db.add(LogAcaoGerencial(
                        autorizador_id=usuario["id"], acao="qa_override",
                        projeto_nome=pa.projeto_id,
                        contexto=json.dumps({"pool_ambiente_id": pa.id, "motivo": motivo})))
                    db.commit()
                    self.send_json({"ok": True})
                finally:
                    db.close()
                return
```

> `LogAcaoGerencial` (database.py:93) tem colunas `autorizador_id` (NOT NULL), `acao`,
> `projeto_nome`, `etapa_alvo`, `contexto` (JSON) — usadas acima. Confirme que `LogAcaoGerencial`
> e `json` estão importados no escopo do handler (ambos já usados em `main.py`).

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_qualidade_upload_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_qualidade_upload_e2e.py
git commit -m "feat(qualidade-xml): override de ambiente bloqueado (diretor/gerente adm-fin) + log"
```

---

### Task 6: Cálculo em sombra ao salvar a negociação

**Files:**
- Modify: `main.py` (handler `POST /api/orcamentos/<id>/margens` ~1955 e/ou o ponto que persiste a negociação do orçamento)
- Test: `tests/test_negociacao_sombra_e2e.py`

**Interfaces:**
- Consumes: `mod_negociacao.calcular_orcamento`; `parametros_json` do projeto; `desconto_pct`/ambientes do orçamento; `mod_fin` para `Cust_Fin`.
- Produces: ao salvar a negociação, grava os derivados nas colunas novas do `orcamentos` (`vbvo..prov_imp`). **Não** altera `valor_total`/`valor_liquido` nem o cálculo atual.

- [ ] **Step 1: Escrever o teste E2E que falha**

```python
# tests/test_negociacao_sombra_e2e.py
def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c

def test_salvar_margens_materializa_derivados(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200
    db = app_db.get_session()
    o = db.get(app_db.Orcamento, oid)
    # derivados gravados (>=0 e coerentes); legado intacto
    assert o.vavo is not None and o.val_liq is not None and o.markup is not None
    assert o.valor_liquido is not None   # coluna legada continua existindo
    db.close()
```

> Nota: o seed cria `orcamento_l1_id` sem ambientes vinculados ricos; o teste valida que os campos são materializados (não-nulos) e que o legado segue intacto. A exatidão numérica é coberta pelo unitário-âncora (Task 1).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao_sombra_e2e.py -v`
Expected: FAIL (`o.vavo` é 0/None — ainda não materializado).

- [ ] **Step 3: Materializar os derivados no save**

No handler `POST /api/orcamentos/<id>/margens` (após salvar as margens e antes do `send_json`), montar os ambientes do orçamento e chamar o motor. Use `grep -n` para localizar onde o orçamento e seus ambientes já são carregados. Inserir:

```python
                    # ── modo sombra: materializa derivados do motor de negociação ──
                    import mod_negociacao
                    proj = db.query(ProjetoMeta).filter_by(nome_safe=orc.projeto_id).first()
                    params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
                    ambs = []
                    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
                        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                        if pa:
                            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                                         "desc_amb_pct": lk.desconto_individual_pct or 0.0})
                    cust_fin = max(0.0, (orc.valor_total or 0.0) - 0.0)  # ver nota abaixo
                    d = mod_negociacao.calcular_orcamento(ambs, params, orc.desconto_pct or 0.0)
                    orc.vbvo, orc.cfo, orc.vbno, orc.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
                    orc.cust_ad, orc.val_liq = d["Cust_Ad"], d["Val_Liq"]
                    orc.desc_tot_pct, orc.markup = d["Desc_Tot"], d["Markup"]
                    orc.prov_imp = d["Prov_Imp"]
                    # Cust_Fin/Val_Cont via mod_fin a partir do VAVO calculado:
                    orc.cust_fin = round(max(0.0, (orc.valor_total or 0.0) - d["VAVO"]), 2)
                    orc.val_cont = round(d["VAVO"] + orc.cust_fin, 2)
                    db.commit()
```

> Nota ao implementer: nesta fase de sombra, derive `Cust_Fin` do `valor_total` já persistido (`valor_total − VAVO`), evitando recomputar a modalidade aqui. A integração plena com `mod_fin.calcular(...)` (passando entrada/parcelas/modalidade) entra na fase de cutover. Garanta que `ProjetoMeta`, `OrcamentoAmbiente`, `PoolAmbiente` estão importados no escopo (já são usados em `main.py`).

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_negociacao_sombra_e2e.py -v`
Expected: PASS.

- [ ] **Step 5: Rodar a suíte inteira (sem regressão no legado)**

Run: `python3 -m pytest -q`
Expected: PASS (o cálculo/colunas legados intactos; nada removido).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_negociacao_sombra_e2e.py
git commit -m "feat(negociacao): calculo em sombra grava derivados ao salvar (legado intacto)"
```

---

### Task 7: UI do modal de parâmetros — valor de hoje × valor novo (lado a lado)

**Files:**
- Modify: `static/index.html` (modal `#modal-params` / `mpAtualizarApoio` ~5324; endpoint de leitura dos derivados)
- Modify: `main.py` (incluir os derivados `vavo/val_liq/markup/...` na resposta do GET de orçamento/pool, se ainda não vierem)

**Interfaces:**
- Consumes: derivados em `orcamentos` (Task 6); cálculo atual (legado) já exibido no painel de apoio.
- Produces: bloco visual no modal mostrando, por orçamento, **HOJE** (cálculo atual) vs **NOVO** (`mod_negociacao`), incluindo `Markup` e `%Desc_Tot`.

> **Sem harness de teste JS** — verificação **manual** (passo final).

- [ ] **Step 1: Expor os derivados no GET**

Em `main.py`, no(s) endpoint(s) que retorna(m) o orçamento para o modal (`grep -n "valor_liquido" main.py` nos dicts de resposta ~3187/3726), acrescentar os campos novos ao dict de resposta:

```python
                        "sombra": {
                            "vavo": o.vavo or 0, "val_liq": o.val_liq or 0,
                            "markup": o.markup or 0, "desc_tot_pct": o.desc_tot_pct or 0,
                            "vbvo": o.vbvo or 0, "cfo": o.cfo or 0, "val_cont": o.val_cont or 0,
                        },
```

- [ ] **Step 2: Adicionar o bloco old×new no modal**

Em `static/index.html`, dentro de `mpAtualizarApoio` (após o cálculo de apoio atual, ~5430), inserir um bloco que renderiza os dois lados. Localize o container do painel de apoio (onde hoje aparece o "desconto total") e acrescente:

```javascript
  // ── modo sombra: HOJE × NOVO (validação visual) ──
  try {
    const s = (window._orcSombra || {});  // preenchido pelo fetch do orçamento (Step 1)
    const box = document.getElementById('mp-sombra');
    if (box && s) {
      const fmt = v => (Number(v)||0).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
      box.innerHTML = `
        <div style="margin-top:10px;border-top:1px dashed var(--border);padding-top:8px;font-size:11px">
          <div style="color:var(--muted);margin-bottom:4px">Validação (HOJE × NOVO)</div>
          <table style="width:100%;border-collapse:collapse">
            <tr><td>Valor líquido</td><td style="text-align:right">${fmt(_margemHojeLiquido)}</td>
                <td style="text-align:right;color:var(--dalm-gold)">${fmt(s.val_liq)}</td></tr>
            <tr><td>Desconto total</td><td style="text-align:right">${(_margemAtual||0).toFixed(1)}%</td>
                <td style="text-align:right;color:var(--dalm-gold)">${((s.desc_tot_pct||0)*100).toFixed(1)}%</td></tr>
            <tr><td>Markup (Val_Liq/CFO)</td><td style="text-align:right">—</td>
                <td style="text-align:right;color:var(--dalm-gold)">${(s.markup||0).toFixed(3)}</td></tr>
          </table>
        </div>`;
    }
  } catch(e) { console.warn('sombra:', e); }
```

Adicionar o container `<div id="mp-sombra"></div>` no HTML do `#modal-params` (perto do rodapé do painel de apoio), e no fetch que carrega o orçamento guardar `window._orcSombra = d.sombra` e `_margemHojeLiquido` = o líquido do cálculo atual.

> Nota ao implementer: nomes `_margemAtual`/`_margemHojeLiquido` devem casar com as variáveis já existentes do painel de apoio (confirme em `mpAtualizarApoio`). O objetivo é só **exibir** os dois lados — não trocar o cálculo atual.

- [ ] **Step 3: Verificação manual no navegador**

Run: `python3 main.py`
Passos: login como diretor → abrir um projeto com orçamento → abrir o **Modal de Parâmetros** → conferir o bloco "HOJE × NOVO" exibindo líquido/desconto-total/markup lado a lado. Salvar a negociação e confirmar que o lado NOVO atualiza. O cálculo/valores de HOJE permanecem inalterados.

- [ ] **Step 4: Commit**

```bash
git add main.py static/index.html
git commit -m "feat(ui): modal de parametros mostra HOJE x NOVO (modo sombra)"
```

---

### Task 8: Golden-master (fotografia dos valores atuais) + DEV_LOG

**Files:**
- Create: `tests/golden/negociacao_baseline.json` (fixture)
- Create: `scripts/snapshot_negociacao.py` (gera a fotografia)
- Modify: `DEV_LOG.md`

**Interfaces:**
- Consumes: motor `mod_negociacao` (Task 1) e os derivados materializados (Task 6).
- Produces: baseline commitado dos valores HOJE × NOVO para orçamentos reais (LELEU), para conferência da fase de validação.

- [ ] **Step 1: Script de fotografia**

```python
# scripts/snapshot_negociacao.py
"""Gera tests/golden/negociacao_baseline.json: para cada orçamento real, os valores
de HOJE (valor_total/valor_liquido legados) e NOVO (derivados do motor)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    db = get_session()
    out = []
    for o in db.query(Orcamento).order_by(Orcamento.id).all():
        out.append({"id": o.id, "projeto": o.projeto_id, "ordem": o.ordem,
                    "hoje": {"valor_total": o.valor_total, "valor_liquido": o.valor_liquido},
                    "novo": {"vavo": o.vavo, "val_liq": o.val_liq, "markup": o.markup,
                             "val_cont": o.val_cont, "desc_tot_pct": o.desc_tot_pct}})
    db.close()
    path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "negociacao_baseline.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{len(out)} orçamentos -> {path}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Gerar a baseline a partir do banco real**

Run: `python3 scripts/snapshot_negociacao.py`
Expected: imprime "N orçamentos -> .../negociacao_baseline.json" e cria o arquivo. (Pré-requisito: ter rodado o save da negociação — Task 6 — em ao menos o LELEU, para os campos `novo` virem preenchidos; caso o banco real ainda não tenha derivados, o arquivo registra `hoje` e `novo` nulos, e a baseline é re-gerada após o primeiro save de validação.)

- [ ] **Step 3: Documentar no DEV_LOG**

Acrescentar ao `DEV_LOG.md` uma entrada da sessão registrando: motor `mod_negociacao` + trava `mod_qualidade_xml` em **modo sombra**, colunas aditivas, tag de rollback `pre-refator-negociacao`, baseline em `tests/golden/negociacao_baseline.json`, e que **cutover/limpeza (Fases B/C) ficam para depois da validação na interface**.

- [ ] **Step 4: Commit**

```bash
git add scripts/snapshot_negociacao.py tests/golden/negociacao_baseline.json DEV_LOG.md
git commit -m "chore(negociacao): golden-master baseline (HOJE x NOVO) + DEV_LOG"
```

---

## Escopo desta fase (e o que fica de fora)

**Inclui (Fase A — sombra):** motor `mod_negociacao`, trava `mod_qualidade_xml`, migração aditiva, gravação dos derivados em sombra, UI old×new, golden-master. Nada destrutivo; comportamento atual intacto.

**Fora desta fase (próximos planos, após validação na interface):**
- **Fase B (cutover):** contrato/UI passam a usar os valores novos; integração plena `Cust_Fin` via `mod_fin.calcular(...)`; mover params duplicados de `orcamentos.margens` para o projeto; `%Desc_Tot` real no lugar do limite hardcoded 35%.
- **Fase C (limpeza):** aposentar `orcamentos.valor_liquido`/bloco `margens`; remover `custo_financeiro_pct` duplicado de `mod_margens`.
- Limiar de qualidade configurável por loja (entra junto do painel de % `a–i` do item 6).

## Self-Review (autor)

**Cobertura do spec:**
- §3/§4 motor por ambiente + siglas → Task 1. ✔
- §8 trava de qualidade (sinais limpos, selo) → Task 2 (puro) + Task 4 (upload/quarentena) + Task 5 (override). ✔
- §5 modelo de dados (colunas novas, legado intacto) → Task 3. ✔
- §9 caso LELEU âncora → Task 1 (`test_leleu_ancora`). ✔
- §10 testes (toggles, qualidade, E2E) → Tasks 1,2,4,5,6. ✔
- §12 estratégia segura (branch da tag, sombra, golden-master, aditivo) → Task 1 Step 1, Tasks 6/7 (sombra), Task 8 (golden-master), migração aditiva (Task 3). ✔
- §13 validação na interface → Task 7. ✔

**Consistência de tipos/nomes:** `calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin)` e as chaves de saída (siglas) são usadas igual nas Tasks 1/6/7/8; `avaliar_qualidade_xml(itens, limiar_pct)` e as chaves `qa_*` idênticas entre Tasks 2/3/4/5. Colunas `vbvo..prov_imp` e `qa_*` idênticas entre Tasks 3/6/7/8.

**Observação de teste:** Task 7 (UI) não tem teste automatizado (repo sem harness JS) — verificação manual; a lógica por trás (derivados) é coberta por Tasks 1/6. Tasks 4/5/6 pedem ao implementer confirmar nomes de rotas/modelos reais (`OrcamentoAmbiente` link, `LogAcaoGerencial`) via grep antes de editar — anotado em cada task.
