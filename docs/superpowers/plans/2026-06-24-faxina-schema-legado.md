# Faxina de Schema/Legado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`).

**Goal:** Remover o cálculo legado de margem (`mod_margens`/`/calcular_margens`/`custo_financeiro_pct`) migrando o último consumidor (discriminação por ambiente) para o motor, mantendo o líquido final inalterado.

**Architecture:** O motor (`mod_negociacao`) passa a expor, por ambiente, os componentes do waterfall (`Com_Arq`, `Pro_Fid`, `Cust_Via`, `Bri`, `Val_Liq`) — aditivo. A discriminação no frontend lê o breakdown do motor (sem `/calcular_margens`). Depois, remove-se o legado.

**Tech Stack:** Python 3 (`python3` no WSL), pytest; frontend vanilla em `static/index.html` (validação manual).

## Global Constraints

- **Aditivo no motor:** os campos atuais (`VBVA/CFA/VBNA/VAVA` e os agregados) **não mudam** — só ACRESCENTA campos por ambiente. Σ por ambiente bate com o agregado (`ΣVal_Liq_amb = Val_Liq`).
- **Líquido final inalterado:** a faxina não muda `valor_total`/`valor_liquido` (golden-master opcional: `snapshot_cutover.py` antes / `diff_cutover.py` depois).
- **Decomposição do motor:** a discriminação passa a refletir a decomposição do motor (bruto → gross-up → desconto → arq/fid/viagem/brinde → líquido). O passo "financeiro" sai do waterfall de **margem** (ele vive em `Val_Cont`, não em `Val_Liq`). Validação visual do usuário.
- **Fase C (drop da coluna `Orcamento.margens`) NÃO entra aqui** — é irreversível (DB ao vivo), fica para depois com backup + aprovação.
- `python3 -m pytest`. 301 testes a manter verdes. Commits por task; `git add` só dos arquivos da task. NÃO commitar `perfis_config.json`/`.claude/*`/`orizon.db`.

---

### Task 1: Motor expõe o waterfall por ambiente (aditivo)

**Files:**
- Modify: `mod_negociacao.py` (o `out_ambs.append(...)` no loop, ~linha 70)
- Test: `tests/test_negociacao.py`

**Interfaces:**
- Produces: cada item de `d["ambientes"]` passa a ter, além de `VBVA/CFA/VBNA/VAVA`: `Com_Arq`, `Pro_Fid`, `Cust_Via`, `Bri`, `Val_Liq` (componentes por ambiente; `Val_Liq = VAVA − Com_Arq − Pro_Fid − Cust_Via − Bri`).

- [ ] **Step 1: Teste que falha**

```python
def test_ambiente_expoe_waterfall_e_soma_bate():
    """Cada ambiente expõe Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq; a soma bate com os agregados."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0},
            {"VBVA": 20000, "CFA": 8000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10,
         "fidelidade_ativa": True, "fidelidade_pct": 5, "fora_da_sede": True,
         "custo_viagem": 600, "brinde_ativo": True, "brinde": 400}
    d = mn.calcular_orcamento(ambs, p, 5)
    aa = d["ambientes"]
    for a in aa:
        for k in ("Com_Arq", "Pro_Fid", "Cust_Via", "Bri", "Val_Liq"):
            assert k in a
        assert abs(a["Val_Liq"] - (a["VAVA"] - a["Com_Arq"] - a["Pro_Fid"] - a["Cust_Via"] - a["Bri"])) < 0.01
    assert abs(sum(a["Com_Arq"] for a in aa) - d["Com_Arq"]) < 0.02
    assert abs(sum(a["Pro_Fid"] for a in aa) - d["Pro_Fid"]) < 0.02
    assert abs(sum(a["Cust_Via"] for a in aa) - d["Cust_Via"]) < 0.02
    assert abs(sum(a["Bri"] for a in aa) - d["Bri"]) < 0.02
    assert abs(sum(a["Val_Liq"] for a in aa) - d["Val_Liq"]) < 0.02
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_negociacao.py::test_ambiente_expoe_waterfall_e_soma_bate -v`
Expected: FAIL (KeyError — campos ainda não existem).

- [ ] **Step 3: Implementar (aditivo)**

No loop, substituir o `out_ambs.append({...})` (linha ~70-71) por:

```python
        liq_amb = vava - com_amb - pro_amb - num_via - num_bri
        out_ambs.append({"VBVA": round(vbva, 2), "CFA": round(a["CFA"], 2),
                         "VBNA": round(vbna, 2), "VAVA": round(vava, 2),
                         "Com_Arq": round(com_amb, 2), "Pro_Fid": round(pro_amb, 2),
                         "Cust_Via": round(num_via, 2), "Bri": round(num_bri, 2),
                         "Val_Liq": round(liq_amb, 2)})
```

- [ ] **Step 4: Rodar e ver passar + suíte do motor**

Run: `python3 -m pytest tests/test_negociacao.py -q`
Expected: PASS (incl. âncora LELEU — campos novos não afetam os existentes).

- [ ] **Step 5: Commit**

```bash
git add mod_negociacao.py tests/test_negociacao.py
git commit -m "feat(motor): expoe waterfall por ambiente (Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq, aditivo)"
```

---

### Task 2: Discriminação lê o motor (remove `/calcular_margens` do fluxo)

**Files:**
- Modify: `static/index.html` (`atualizarDiscriminacao` ~5131; cabeçalho da tabela ~1756-1763)

> Sem teste automatizado → validação manual no navegador (painel interno, atrás do toggle "Ver discriminação").

- [ ] **Step 1: Reescrever `atualizarDiscriminacao` para usar o breakdown**

`atualizarDiscriminacao` passa a chamar `negPreview()` (ou reusar o último breakdown) e renderizar por ambiente a partir de `s.ambientes` (cada `a` tem `VBVA/VBNA/VAVA/Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq`). Colunas (decomposição do motor):
- Bruto = `a.VBVA`; Custos embutidos = `a.VBNA − a.VBVA`; − Desconto = `a.VBNA − a.VAVA`;
  À vista = `a.VAVA`; − Arq = `a.Com_Arq`; − Fid = `a.Pro_Fid`; − Viagem = `a.Cust_Via`;
  − Brinde = `a.Bri`; Líquido = `a.Val_Liq`.
- Remover a montagem de `mg`/`ratearViagem`/`fetch('/calcular_margens')`.
- Ajustar o cabeçalho (`<thead>`) e o `colspan` do placeholder para o novo conjunto de colunas.

(Implementação inline cuidadosa; preservar o toggle `toggleDiscriminacao` e o id `discriminacao-tbody`.)

- [ ] **Step 2: Validação manual + commit**

Run: `python3 main.py` → abrir um orçamento → "Ver discriminação por ambiente". Conferir: soma da coluna Líquido = Val_Liq do orçamento; bruto/desconto coerentes; sem erro no console.

```bash
git add static/index.html
git commit -m "feat(discriminacao): waterfall por ambiente vem do motor (sem /calcular_margens)"
```

---

### Task 3: Remover o legado `mod_margens` / `/calcular_margens` / `custo_financeiro_pct`

**Files:**
- Modify: `static/index.html` (`executarCalculo` path legado, `lerMargensNegociacao`, chamadas a `/calcular_margens`), `main.py` (endpoint `/calcular_margens` + import), `mod_margens.py` (remover `calcular_margens`; mover `_normalizar_faixas` p/ onde é usado, ou manter o módulo só com ela), `mod_omie.py`, `mod_orcamento_params.py`, `tests/test_margens.py`

**Interfaces:**
- Consumes: discriminação já não usa `/calcular_margens` (Task 2). `_normalizar_faixas` segue vivo em `main.py:644` (endpoint de faixas) — **manter**.

- [ ] **Step 1: Mapear usos remanescentes**

Run: `grep -n "calcular_margens\|custo_financeiro_pct\|_negBaseValues\|lerMargensNegociacao" static/index.html main.py mod_omie.py mod_orcamento_params.py`
Confirmar que, fora de `_normalizar_faixas`, nada vivo resta no caminho de exibição (o path EP-07 de `executarCalculo` já dá early-return).

- [ ] **Step 2: Remover no backend**

- `main.py`: remover o endpoint `POST /calcular_margens` (~1417-1439) e ajustar o import (`from mod_margens import _normalizar_faixas` — tirar `calcular_margens`).
- `mod_margens.py`: remover `calcular_margens` (manter `_normalizar_faixas`); ou, se preferir, mover `_normalizar_faixas` p/ `mod_fin` e apagar `mod_margens.py` (avaliar no momento).
- `mod_omie.py:114` e `mod_orcamento_params.py` (default + `_FLOAT_KEYS`): remover `custo_financeiro_pct` (campo não usado pelo motor).
- `tests/test_margens.py`: remover (testava `calcular_margens`).

- [ ] **Step 3: Remover no frontend**

`static/index.html`: remover `lerMargensNegociacao`, o path legado de `executarCalculo` que chama `/calcular_margens` (e `_negBaseValues` se virar morto), e referências a `custo_financeiro_pct`. Preservar o fluxo EP-07 (motor) intacto.

- [ ] **Step 4: Suíte + validação manual**

Run: `python3 -m pytest -q` → verde (sem `test_margens.py`). Abrir a tela: negociação, modal de parâmetros e discriminação sem regressão; console limpo.

- [ ] **Step 5: Commit**

```bash
git add -A -- static/index.html main.py mod_margens.py mod_omie.py mod_orcamento_params.py tests/test_margens.py
git commit -m "refactor(faxina): remove calculo legado de margem (mod_margens/calcular_margens/custo_financeiro_pct)"
```

---

## Self-Review (autor)

**Cobertura do spec:** Fase A (motor expõe waterfall + discriminação do motor) → Tasks 1-2. Fase B (remove legado) → Task 3. Fase C (drop `Orcamento.margens`) → fora deste plano (irreversível; backup+aprovação). ✔

**Consistência:** campos por ambiente `Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq` (mesmos nomes do agregado) usados na Task 1 (produz), Task 2 (consome). `_normalizar_faixas` preservado (vivo).

**Riscos:** Task 2 e 3 são frontend-visual → validação manual do usuário entre elas. Task 1 é aditivo+TDD (baixo risco). Golden-master opcional para garantir `valor_liquido` inalterado.
