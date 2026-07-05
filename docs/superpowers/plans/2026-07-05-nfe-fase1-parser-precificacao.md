# NF-e Fase 1 — Parser + Precificação (`mod_nfe.py`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um módulo puro `mod_nfe.py` que lê o XML da NF-e da fábrica, consolida itens duplicados, classifica padrão/sob-medida, calcula custo (`vUnCom + IPI proporcional`) e aplica um markup percentual único, produzindo uma estrutura de *preview* — mais um CLI para conferir qualquer XML offline.

**Architecture:** Um único módulo `mod_nfe.py` na raiz, sem I/O de rede e sem SQLAlchemy. Funções pequenas e isoladas: `split_cprod`, `parse_infadprod`, `parse_nfe`, `consolidar`, `precificar`, `preview`, e um `__main__` (CLI). Namespace da NF-e tratado por *strip* do `xmlns` antes do parse (padrão de `xml.etree.ElementTree`, como `promob_grupos.py`). Fixtures de teste **anonimizados** (sem CNPJ/CPF/endereço reais).

**Tech Stack:** Python 3 stdlib (`re`, `xml.etree.ElementTree`), pytest. Sem dependências novas.

**Base para ler antes:** spec `docs/superpowers/specs/2026-07-05-nfe-fase1-parser-precificacao-design.md`. Padrão de parse XML: `promob_grupos.py` (usa `xml.etree.ElementTree`). Os 5 XMLs reais estão em `E:/2026/desenvolvimento/nfe-dalmobile` (**fora do git** — só para conferência manual; **não** usar como fixture de teste).

**Estrutura real confirmada (de uma NF-e real):** `nfeProc versao="3.10"` com namespace `http://www.portalfiscal.inf.br/nfe`; `infNFe/ide/{nNF,serie,dhEmi,natOp}`, `infNFe/emit/{CNPJ,xNome,CRT}`, `infNFe/dest/{xNome,CNPJ|CPF}`; cada `infNFe/det[@nItem]/prod/{cProd,xProd,NCM,CFOP,uCom,qCom,vUnCom,vProd}`, `det/imposto/IPI/IPITrib/vIPI` (pode faltar → IPI 0), `det/infAdProd`.

**Lembrete de ambiente:** módulo puro → **não exige restart de servidor**. Rodar: `python3 -m pytest -q` (baseline atual **457 passed**). Se `python3` do Bash falhar (stub WindowsApps), usar o interpretador real (nota no DEV_LOG).

---

## File Structure

- **Create** `mod_nfe.py` — todas as funções + CLI. Uma responsabilidade: transformar XML de NF-e da fábrica em itens precificados (preview). Sem rede, sem DB.
- **Create** `tests/test_nfe.py` — testes unitários das funções puras + end-to-end do `preview` sobre fixtures.
- **Create** `tests/fixtures/nfe/nfe_basica.xml`, `tests/fixtures/nfe/nfe_sem_ipi.xml` — fixtures anonimizados.

> **Desvio consciente da spec §5:** o fixture `nfe_infadprod_variado.xml` foi **omitido** — as 4 variações de `infAdProd` (COR-L-A / só-cor / número-solto / ausente) são cobertas diretamente pelos testes de string de `parse_infadprod` (Task 1) + o caso "ausente" via `nfe_basica.xml`. Criar um XML só para isso seria redundante (YAGNI).

---

## Task 1: `split_cprod` + `parse_infadprod` (helpers de string puros)

**Files:**
- Create: `mod_nfe.py`
- Create: `tests/test_nfe.py`

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_nfe.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_nfe as mn


def test_split_cprod_sob_medida():
    assert mn.split_cprod("50079[2131748]") == ("50079", "2131748", "sob_medida")
    assert mn.split_cprod("50057[2131751]") == ("50057", "2131751", "sob_medida")


def test_split_cprod_padrao():
    assert mn.split_cprod("80070") == ("80070", None, "padrao")
    assert mn.split_cprod("") == ("", None, "padrao")


def test_parse_infadprod_valido():
    assert mn.parse_infadprod("EBANO 622 600") == {"cor": "EBANO", "largura": 622, "altura": 600}
    assert mn.parse_infadprod("METROPOLITAN 2406 185") == {"cor": "METROPOLITAN", "largura": 2406, "altura": 185}


def test_parse_infadprod_nao_confiavel():
    # só-cor, cor+1-número, número-solto, vazio/None → None (não confiável)
    assert mn.parse_infadprod("MDF BP BRANCO") is None
    assert mn.parse_infadprod("FOSCO 2420") is None
    assert mn.parse_infadprod("970") is None
    assert mn.parse_infadprod("") is None
    assert mn.parse_infadprod(None) is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'mod_nfe'`).

- [ ] **Step 3: Create `mod_nfe.py` with these helpers**

```python
"""mod_nfe.py — parser + precificação do XML da NF-e da fábrica (Fase 1).
Puro: sem rede, sem banco. Produz a estrutura de preview consumida pelas fases seguintes."""
import re

MARKUP_TESTE_PADRAO = 30.0   # % — valor de teste do CLI; a origem real do markup é config (fases 2+)

_RE_CPROD = re.compile(r'^(.+?)\[([^\]]+)\]$')


def split_cprod(cprod):
    """'50079[2131748]' -> ('50079','2131748','sob_medida'); '80070' -> ('80070', None, 'padrao')."""
    m = _RE_CPROD.match(cprod or "")
    if m:
        return (m.group(1), m.group(2), "sob_medida")
    return (cprod or "", None, "padrao")


def parse_infadprod(texto):
    """'COR LARGURA ALTURA' -> {cor,largura,altura} SÓ quando os 2 últimos tokens são inteiros.
    Caso contrário None (o campo é não-confiável na prática). Nunca levanta."""
    if not texto:
        return None
    toks = texto.split()
    if len(toks) >= 3 and toks[-1].isdigit() and toks[-2].isdigit():
        return {"cor": " ".join(toks[:-2]), "largura": int(toks[-2]), "altura": int(toks[-1])}
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_nfe.py tests/test_nfe.py
git commit -m "feat(nfe): split_cprod + parse_infadprod (helpers puros, Fase 1)"
```

---

## Task 2: `parse_nfe` + fixtures anonimizados

**Files:**
- Modify: `mod_nfe.py`
- Create: `tests/fixtures/nfe/nfe_basica.xml`, `tests/fixtures/nfe/nfe_sem_ipi.xml`
- Modify: `tests/test_nfe.py`

- [ ] **Step 1: Create the fixtures**

Criar `tests/fixtures/nfe/nfe_basica.xml` (2 itens sob-medida idênticos → duplicata + 1 item padrão; emit/dest fictícios; namespace real):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<nfeProc versao="3.10" xmlns="http://www.portalfiscal.inf.br/nfe">
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
<infNFe versao="3.10" Id="NFe00000000000000000000000000000000000000000000">
<ide><nNF>170942</nNF><serie>1</serie><dhEmi>2016-03-03T10:26:09-03:00</dhEmi><natOp>VENDA DE PRODUCAO</natOp></ide>
<emit><CNPJ>00000000000000</CNPJ><xNome>FABRICA TESTE LTDA</xNome><CRT>3</CRT></emit>
<dest><CNPJ>11111111111111</CNPJ><xNome>LOJA TESTE LTDA</xNome></dest>
<det nItem="1"><prod><cProd>50079[2131748]</cProd><xProd>PAINEL EDITAVEL 50</xProd><NCM>94035000</NCM><CFOP>6101</CFOP><uCom>UN</uCom><qCom>1.00</qCom><vUnCom>71.63</vUnCom><vProd>71.63</vProd></prod><imposto><ICMS><ICMS00><CST>00</CST></ICMS00></ICMS><IPI><IPITrib><vIPI>3.58</vIPI></IPITrib></IPI></imposto><infAdProd>METROPOLITAN 2406 185</infAdProd></det>
<det nItem="2"><prod><cProd>50079[2131748]</cProd><xProd>PAINEL EDITAVEL 50</xProd><NCM>94035000</NCM><CFOP>6101</CFOP><uCom>UN</uCom><qCom>1.00</qCom><vUnCom>71.63</vUnCom><vProd>71.63</vProd></prod><imposto><IPI><IPITrib><vIPI>3.58</vIPI></IPITrib></IPI></imposto><infAdProd>METROPOLITAN 2406 185</infAdProd></det>
<det nItem="3"><prod><cProd>80070</cProd><xProd>CORREDICA TELESCOPICA</xProd><NCM>83024200</NCM><CFOP>6101</CFOP><uCom>UN</uCom><qCom>2.00</qCom><vUnCom>10.00</vUnCom><vProd>20.00</vProd></prod><imposto><IPI><IPITrib><vIPI>1.00</vIPI></IPITrib></IPI></imposto></det>
</infNFe>
</NFe>
</nfeProc>
```

Criar `tests/fixtures/nfe/nfe_sem_ipi.xml` (1 item com IPI **não tributado** — sem `vIPI` → IPI 0):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
<infNFe versao="3.10" Id="NFe00000000000000000000000000000000000000000001">
<ide><nNF>170999</nNF><serie>1</serie><dhEmi>2016-03-03T11:00:00-03:00</dhEmi><natOp>VENDA</natOp></ide>
<emit><CNPJ>00000000000000</CNPJ><xNome>FABRICA TESTE LTDA</xNome><CRT>1</CRT></emit>
<dest><CPF>00000000000</CPF><xNome>CLIENTE FINAL</xNome></dest>
<det nItem="1"><prod><cProd>50100[9]</cProd><xProd>PORTA</xProd><NCM>94035000</NCM><CFOP>6101</CFOP><uCom>UN</uCom><qCom>1.00</qCom><vUnCom>50.00</vUnCom><vProd>50.00</vProd></prod><imposto><IPI><IPINT><CST>53</CST></IPINT></IPI></imposto></det>
</infNFe>
</NFe>
```

Note: `nfe_basica.xml` usa o wrapper `nfeProc`; `nfe_sem_ipi.xml` usa `NFe` puro (sem `nfeProc`) e destinatário por `CPF` — ambos devem parsear igual (o parser localiza `infNFe` independentemente do wrapper e aceita CNPJ **ou** CPF no dest).

- [ ] **Step 2: Write the failing tests**

Adicionar em `tests/test_nfe.py`:

```python
import os as _os
_FIX = _os.path.join(_os.path.dirname(__file__), "fixtures", "nfe")

def _ler(nome):
    with open(_os.path.join(_FIX, nome), encoding="utf-8") as f:
        return f.read()


def test_parse_nfe_cabecalho():
    nfe = mn.parse_nfe(_ler("nfe_basica.xml"))
    cab = nfe["cabecalho"]
    assert cab["nNF"] == "170942" and cab["serie"] == "1"
    assert cab["emit"]["cnpj"] == "00000000000000" and cab["emit"]["crt"] == "3"
    assert cab["emit"]["nome"] == "FABRICA TESTE LTDA"
    assert cab["dest"]["nome"] == "LOJA TESTE LTDA" and cab["dest"]["doc"] == "11111111111111"


def test_parse_nfe_itens():
    itens = mn.parse_nfe(_ler("nfe_basica.xml"))["itens"]
    assert len(itens) == 3   # ainda NÃO consolidado
    i0 = itens[0]
    assert i0["cProd"] == "50079[2131748]" and i0["ncm"] == "94035000" and i0["cfop"] == "6101"
    assert i0["qCom"] == 1.0 and i0["vUnCom"] == 71.63 and i0["vProd"] == 71.63
    assert i0["vIPI"] == 3.58 and i0["infAdProd"] == "METROPOLITAN 2406 185"
    # item padrão sem infAdProd
    assert itens[2]["cProd"] == "80070" and itens[2]["infAdProd"] is None


def test_parse_nfe_aceita_bytes():
    itens = mn.parse_nfe(_ler("nfe_basica.xml").encode("utf-8"))["itens"]
    assert len(itens) == 3


def test_parse_nfe_sem_ipi_e_cpf_e_nfe_puro():
    nfe = mn.parse_nfe(_ler("nfe_sem_ipi.xml"))
    assert nfe["cabecalho"]["dest"]["doc"] == "00000000000"   # CPF
    it = nfe["itens"][0]
    assert it["vIPI"] == 0.0 and it["vProd"] == 50.0
```

- [ ] **Step 3: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe.py -q -k "parse_nfe"`
Expected: FAIL (`AttributeError: module 'mod_nfe' has no attribute 'parse_nfe'`).

- [ ] **Step 4: Implement `parse_nfe` in `mod_nfe.py`**

Adicionar o import do ElementTree no topo (junto do `import re`):

```python
import xml.etree.ElementTree as ET
```

E as funções:

```python
def _strip_ns(xml_text):
    """Remove os atributos xmlns (default e prefixados) — a NF-e usa um único namespace
    default; sem ele os finds ficam simples (mesma tática usada ao inspecionar o XML real)."""
    return re.sub(r'\sxmlns(:\w+)?="[^"]+"', '', xml_text)


def _txt(el, path, default=None):
    if el is None:
        return default
    x = el.find(path)
    return x.text if (x is not None and x.text is not None) else default


def parse_nfe(xml):
    """XML (str|bytes) da NF-e da fábrica -> {'cabecalho': {...}, 'itens': [...]}.
    Namespace-aware (localiza infNFe sob nfeProc OU NFe puro). vIPI ausente -> 0.0."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8")
    root = ET.fromstring(_strip_ns(xml))
    inf = root if root.tag == "infNFe" else root.find(".//infNFe")
    ide, emit, dest = inf.find("ide"), inf.find("emit"), inf.find("dest")
    cabecalho = {
        "nNF": _txt(ide, "nNF"), "serie": _txt(ide, "serie"),
        "dhEmi": _txt(ide, "dhEmi"), "natOp": _txt(ide, "natOp"),
        "emit": {"cnpj": _txt(emit, "CNPJ"), "nome": _txt(emit, "xNome"), "crt": _txt(emit, "CRT")},
        "dest": {"nome": _txt(dest, "xNome"), "doc": _txt(dest, "CNPJ") or _txt(dest, "CPF")},
    }
    itens = []
    for det in inf.findall("det"):
        prod, imp = det.find("prod"), det.find("imposto")
        vipi = imp.find(".//vIPI") if imp is not None else None
        infad = det.find("infAdProd")
        itens.append({
            "nItem": det.get("nItem"),
            "cProd": _txt(prod, "cProd"),
            "xProd": _txt(prod, "xProd"),
            "ncm": _txt(prod, "NCM"),
            "cfop": _txt(prod, "CFOP"),
            "uCom": _txt(prod, "uCom"),
            "qCom": float(_txt(prod, "qCom", "0") or 0),
            "vUnCom": float(_txt(prod, "vUnCom", "0") or 0),
            "vProd": float(_txt(prod, "vProd", "0") or 0),
            "vIPI": float(vipi.text) if (vipi is not None and vipi.text) else 0.0,
            "infAdProd": infad.text if infad is not None else None,
        })
    return {"cabecalho": cabecalho, "itens": itens}
```

- [ ] **Step 5: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe.py -q`
Expected: PASS (4 da Task 1 + 4 novos = 8).

- [ ] **Step 6: Commit**

```bash
git add mod_nfe.py tests/test_nfe.py tests/fixtures/nfe/nfe_basica.xml tests/fixtures/nfe/nfe_sem_ipi.xml
git commit -m "feat(nfe): parse_nfe (namespace-aware) + fixtures anonimizados"
```

---

## Task 3: `consolidar` + `precificar`

**Files:**
- Modify: `mod_nfe.py`
- Modify: `tests/test_nfe.py`

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_nfe.py`:

```python
def test_consolidar_soma_duplicados():
    itens = [
        {"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 71.63, "vProd": 71.63, "vIPI": 3.58, "infAdProd": "METROPOLITAN 2406 185"},
        {"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 71.63, "vProd": 71.63, "vIPI": 3.58, "infAdProd": "METROPOLITAN 2406 185"},
        {"cProd": "50057[2131751]", "xProd": "Y", "ncm": "9403", "cfop": "6101", "uCom": "UN",
         "qCom": 1.0, "vUnCom": 29.83, "vProd": 29.83, "vIPI": 1.49, "infAdProd": None},
    ]
    out = mn.consolidar(itens)
    assert len(out) == 2                       # duplicata somada; BASE igual mas [ID] diferente NÃO junta
    assert out[0]["cProd"] == "50079[2131748]" and out[0]["qCom"] == 2.0
    assert round(out[0]["vProd"], 2) == 143.26 and round(out[0]["vIPI"], 2) == 7.16
    assert out[1]["cProd"] == "50057[2131751]" and out[1]["qCom"] == 1.0


def test_precificar_custo_e_markup():
    consol = [{"cProd": "50079[2131748]", "xProd": "X", "ncm": "9403", "cfop": "6101", "uCom": "UN",
               "qCom": 2.0, "vUnCom": 71.63, "vProd": 143.26, "vIPI": 7.16, "infAdProd": "METROPOLITAN 2406 185"}]
    out = mn.precificar(consol, 30.0)
    p = out[0]
    assert p["tipo"] == "sob_medida" and p["base"] == "50079" and p["id_peca"] == "2131748"
    assert p["custo_unit"] == 75.21                      # (143.26+7.16)/2
    assert p["preco_venda_unit"] == 97.77                # round(75.21*1.30, 2)
    assert p["cor"] == "METROPOLITAN" and p["largura"] == 2406 and p["altura"] == 185


def test_precificar_sem_ipi_e_padrao():
    consol = [{"cProd": "80070", "xProd": "C", "ncm": "8302", "cfop": "6101", "uCom": "UN",
               "qCom": 1.0, "vUnCom": 50.0, "vProd": 50.0, "vIPI": 0.0, "infAdProd": None}]
    p = mn.precificar(consol, 30.0)[0]
    assert p["tipo"] == "padrao" and p["id_peca"] is None
    assert p["custo_unit"] == 50.0 and p["preco_venda_unit"] == 65.0
    assert p["cor"] is None and p["largura"] is None
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe.py -q -k "consolidar or precificar"`
Expected: FAIL (`AttributeError: ... has no attribute 'consolidar'`).

- [ ] **Step 3: Implement `consolidar` + `precificar` in `mod_nfe.py`**

```python
def consolidar(itens):
    """Agrupa por cProd (na mesma NF-e), somando qCom/vProd/vIPI. Mantém os campos estáticos
    (xProd, ncm, cfop, uCom, vUnCom, infAdProd) da 1ª ocorrência. Preserva a ordem de aparição."""
    ordem, por_cod = [], {}
    for it in itens:
        cod = it["cProd"]
        if cod not in por_cod:
            por_cod[cod] = dict(it)
            ordem.append(cod)
        else:
            ac = por_cod[cod]
            ac["qCom"] += it["qCom"]
            ac["vProd"] += it["vProd"]
            ac["vIPI"] += it["vIPI"]
    return [por_cod[c] for c in ordem]


def precificar(itens_consolidados, markup_pct):
    """Custo unitário = (vProd + vIPI) / qCom; preco_venda_unit = round(custo * (1+pct/100), 2).
    Anexa base/id_peca/tipo (split_cprod) e cor/largura/altura (parse_infadprod)."""
    fator = 1 + (markup_pct / 100.0)
    out = []
    for it in itens_consolidados:
        base, id_peca, tipo = split_cprod(it["cProd"])
        q = it["qCom"] or 0
        custo = (it["vProd"] + it["vIPI"]) / q if q else 0.0
        dim = parse_infadprod(it.get("infAdProd"))
        out.append({
            "cProd": it["cProd"], "base": base, "id_peca": id_peca, "tipo": tipo,
            "xProd": it.get("xProd"), "ncm": it.get("ncm"), "cfop": it.get("cfop"), "uCom": it.get("uCom"),
            "qCom": it["qCom"], "vUnCom": it.get("vUnCom"), "vProd": it["vProd"], "vIPI": it["vIPI"],
            "custo_unit": round(custo, 2), "preco_venda_unit": round(custo * fator, 2),
            "cor": dim["cor"] if dim else None,
            "largura": dim["largura"] if dim else None,
            "altura": dim["altura"] if dim else None,
            "infAdProd": it.get("infAdProd"),
        })
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe.py -q`
Expected: PASS (8 + 3 = 11).

- [ ] **Step 5: Commit**

```bash
git add mod_nfe.py tests/test_nfe.py
git commit -m "feat(nfe): consolidar (soma duplicados) + precificar (custo+IPI, markup)"
```

---

## Task 4: `preview` + CLI

**Files:**
- Modify: `mod_nfe.py`
- Modify: `tests/test_nfe.py`

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_nfe.py`:

```python
def test_preview_end_to_end():
    pv = mn.preview(_ler("nfe_basica.xml"), 30.0)
    t = pv["totais"]
    assert t["n_linhas"] == 3 and t["n_distintos"] == 2
    assert t["n_padrao"] == 1 and t["n_sob_medida"] == 1
    assert t["custo_total"] == 171.42     # 75.21*2 + 10.50*2
    assert t["venda_total"] == 222.84     # 97.77*2 + 13.65*2
    assert pv["markup_pct"] == 30.0
    assert pv["cabecalho"]["nNF"] == "170942"
    # item consolidado sob-medida com dimensão parseada
    sob = [i for i in pv["itens"] if i["tipo"] == "sob_medida"][0]
    assert sob["qCom"] == 2.0 and sob["preco_venda_unit"] == 97.77 and sob["altura"] == 185


def test_preview_infadprod_ausente_nao_quebra():
    pv = mn.preview(_ler("nfe_basica.xml"), 10.0)
    padrao = [i for i in pv["itens"] if i["tipo"] == "padrao"][0]
    assert padrao["cor"] is None and padrao["largura"] is None   # sem infAdProd → dim None, sem erro
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe.py -q -k "preview"`
Expected: FAIL (`AttributeError: ... has no attribute 'preview'`).

- [ ] **Step 3: Implement `preview` + CLI in `mod_nfe.py`**

```python
def preview(xml, markup_pct):
    """Pipeline completo: parse -> consolida -> precifica. Estrutura de handoff + totais."""
    nfe = parse_nfe(xml)
    itens = nfe["itens"]
    consol = consolidar(itens)
    precificados = precificar(consol, markup_pct)
    return {
        "cabecalho": nfe["cabecalho"],
        "markup_pct": markup_pct,
        "itens": precificados,
        "totais": {
            "n_linhas": len(itens),
            "n_distintos": len(consol),
            "n_padrao": sum(1 for p in precificados if p["tipo"] == "padrao"),
            "n_sob_medida": sum(1 for p in precificados if p["tipo"] == "sob_medida"),
            "custo_total": round(sum(p["custo_unit"] * p["qCom"] for p in precificados), 2),
            "venda_total": round(sum(p["preco_venda_unit"] * p["qCom"] for p in precificados), 2),
        },
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("uso: python3 mod_nfe.py <arquivo.xml> [markup_pct]")
        sys.exit(1)
    _pct = float(sys.argv[2]) if len(sys.argv) > 2 else MARKUP_TESTE_PADRAO
    with open(sys.argv[1], encoding="utf-8") as _f:
        _pv = preview(_f.read(), _pct)
    _cab = _pv["cabecalho"]
    print("NF-e %s serie %s | emit %s (CRT %s) | markup %.1f%%"
          % (_cab.get("nNF"), _cab.get("serie"), _cab["emit"].get("nome"), _cab["emit"].get("crt"), _pct))
    print("%-22s %-11s %7s %10s %10s  %s" % ("cProd", "tipo", "qtd", "custo_un", "venda_un", "xProd"))
    for _it in _pv["itens"]:
        print("%-22s %-11s %7.2f %10.2f %10.2f  %s"
              % (_it["cProd"], _it["tipo"], _it["qCom"], _it["custo_unit"],
                 _it["preco_venda_unit"], (_it["xProd"] or "")[:30]))
    _t = _pv["totais"]
    print("-" * 78)
    print("linhas=%d distintos=%d padrao=%d sob_medida=%d | custo_total=%.2f venda_total=%.2f"
          % (_t["n_linhas"], _t["n_distintos"], _t["n_padrao"], _t["n_sob_medida"],
             _t["custo_total"], _t["venda_total"]))
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe.py -q`
Expected: PASS (11 + 2 = 13).

- [ ] **Step 5: Smoke do CLI num XML real (conferência manual, offline)**

Run: `python3 mod_nfe.py "E:/2026/desenvolvimento/nfe-dalmobile/NFe-170942.xml" 30`
Expected: imprime a tabela precificada + a linha de totais (para NFe-170942: `linhas=21 distintos=12`). Não faz parte da suíte; é só conferência.

- [ ] **Step 6: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde (baseline 457 + os novos de `mod_nfe`).

- [ ] **Step 7: Commit**

```bash
git add mod_nfe.py tests/test_nfe.py
git commit -m "feat(nfe): preview (pipeline + totais) + CLI de eyeball"
```

---

## Task 5: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/2026-07-05-nfe-fase1-parser-precificacao-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar a linha `> Status: **APROVADO (brainstorming)** — a implementar. Primeira das 5 fases...` por
`> Status: **IMPLEMENTADO (Sessão N)** — `mod_nfe.py` com testes + CLI; conferido nos 5 XMLs reais via CLI.`

- [ ] **Step 3: DEV_LOG — nota na Sessão 47 / ESTADO ATUAL**

Registrar (na Sessão 47 do NF-e ou nova sub-seção): **Fase 1 implementada** — `mod_nfe.py` (`parse_nfe`
namespace-aware, `consolidar`, `split_cprod`, `precificar` custo+IPI+markup, `preview`, CLI de eyeball),
`tests/test_nfe.py` com fixtures anonimizados; suíte verde. Atualizar o `⏸️ ESTADO ATUAL` (Fase 1
mergeável; falta Fase 3, que depende do perfil fiscal do contador + token da Focus).

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/2026-07-05-nfe-fase1-parser-precificacao-design.md
git commit -m "docs(nfe): DEV_LOG + spec Fase 1 como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §4 interface — `parse_nfe`/`split_cprod`/`parse_infadprod` (Tasks 1-2),
  `consolidar`/`precificar` (Task 3), `preview` + CLI (Task 4); §5 testes distribuídos, fixtures
  anonimizados criados na Task 2 (o `nfe_infadprod_variado.xml` foi conscientemente omitido — coberto por
  string tests). §3 decisões respeitadas (markup % único como parâmetro; infAdProd tolerante; custo
  `(vProd+vIPI)/qCom`); §6 fora de escopo respeitado (sem Omie/Focus, sem UI, sem persistência).
- **Consistência de tipos/chaves:** as chaves dos dicts (`cProd,xProd,ncm,cfop,uCom,qCom,vUnCom,vProd,
  vIPI,infAdProd` em `parse_nfe`; `base,id_peca,tipo,custo_unit,preco_venda_unit,cor,largura,altura` em
  `precificar`; `cabecalho,markup_pct,itens,totais` + `n_linhas,n_distintos,n_padrao,n_sob_medida,
  custo_total,venda_total` em `preview`) idênticas entre implementação e testes. `split_cprod` retorna
  `(base,id_peca,tipo)` com `tipo∈{padrao,sob_medida}` de forma consistente.
- **Aritmética dos fixtures conferida:** `nfe_basica.xml` → consolidado `50079` custo 75.21 / venda 97.77;
  padrão `80070` custo 10.50 / venda 13.65; totais custo 171.42 / venda 222.84 (usados nos asserts).
- **Sem placeholders:** todo passo com código tem o código completo. `Sessão N` = número da sessão
  corrente do DEV_LOG, único símbolo a resolver na hora.
```
