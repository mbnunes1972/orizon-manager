# NF-e Fase 3b — Mapa Fiscal + `EmissorFocusNfe` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o `preview` da Fase 1 + o `PerfilFiscal`/`Loja`/`Cliente` no **payload JSON da NF-e da Focus** (`mapa_fiscal.py`) e fechar o contrato `EmissorFiscal` com o concreto `EmissorFocusNfe` (`emissor_focus.py`).

**Architecture:** Dois módulos: `mapa_fiscal.py` (puro — `montar_payload` monta o JSON da Focus a partir de um dict `nota`; `montar_nota` assembla esse `nota` dos modelos) e `emissor_focus.py` (`EmissorFocusNfe(EmissorFiscal)` recebe um `FocusClient` injetado, monta o payload e transmite). Sem DB, sem rede, sem emissão real (Fase 4). Regime Simples primeiro.

**Tech Stack:** Python 3 stdlib, pytest. Reusa `emissor_fiscal.py` (Fase 2: `EmissorFiscal`, `resultado_de_focus`, `StatusNota`) e `focus_client.FocusClient` (Fase 2, só como tipo injetado — mockado nos testes).

**Base para ler antes:** spec `docs/superpowers/specs/fiscal/2026-07-05-nfe-fase3b-mapa-fiscal-design.md`. Contrato/DTO da Fase 2: `emissor_fiscal.py` (`EmissorFiscal` ABC, `resultado_de_focus`, `StatusNota`, `ResultadoEmissao`). Estrutura dos itens do preview (Fase 1): `mod_nfe.preview` → itens com chaves `cProd, xProd, ncm, uCom, qCom, preco_venda_unit` (entre outras). Campos do PerfilFiscal (Sub-frente I): `razao_social, regime_tributario, inscricao_estadual, csosn_padrao, cfop_dentro_uf, cfop_fora_uf`. `Loja`: `cnpj, nome, logradouro, numero, bairro, cidade, estado, cep`. `Cliente`: `nome, cpf, logradouro, numero, bairro, cidade, estado, cep` (sem `cnpj` no modelo — o código usa `getattr` para cobrir PJ futura).

**Lembrete de ambiente:** módulos puros → **não exigem restart**. Rodar: `python3 -m pytest -q` (baseline **493 passed**). Se o `python3` do Bash for o stub WindowsApps, usar o interpretador real (nota no DEV_LOG).

---

## File Structure

- **Create** `mapa_fiscal.py` — `montar_payload(nota)` (nota → payload Focus) e `montar_nota(perfil, loja, cliente, itens_preview, ref, data_emissao, natureza)` (modelos → nota) + constantes de regime/CST. Puro.
- **Create** `emissor_focus.py` — `EmissorFocusNfe(EmissorFiscal)` (client injetado).
- **Create** `tests/test_mapa_fiscal.py`, `tests/test_emissor_focus.py`.

---

## Task 1: `mapa_fiscal.montar_payload` (nota → payload Focus)

**Files:**
- Create: `mapa_fiscal.py`
- Test: `tests/test_mapa_fiscal.py`

- [ ] **Step 1: Create the tests**

Criar `tests/test_mapa_fiscal.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mapa_fiscal as mp


def _nota(uf_emit="SP", uf_dest="SP", doc_tipo="cpf"):
    dest_doc = {"doc_tipo": doc_tipo,
                "doc": ("11111111111111" if doc_tipo == "cnpj" else "22222222222")}
    return {
        "ref": "R1", "natureza_operacao": "Venda de mercadoria",
        "data_emissao": "2026-07-05T10:00:00-03:00",
        "emitente": {"doc_tipo": "cnpj", "doc": "19152134000156", "nome": "LOJA X", "regime": 1,
                     "ie": "ISENTO", "logradouro": "Rua A", "numero": "1", "bairro": "Centro",
                     "municipio": "Sao Paulo", "uf": uf_emit, "cep": "01000-000"},
        "destinatario": {"nome": "CLIENTE Y", "logradouro": "Rua B", "numero": "2", "bairro": "Jd",
                         "municipio": "Rio", "uf": uf_dest, "cep": "20000-000", **dest_doc},
        "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102",
                   "pis_cst": "49", "cofins_cst": "49"},
        "itens": [
            {"cProd": "50079[2131748]", "xProd": "PAINEL", "ncm": "94035000", "uCom": "UN",
             "qCom": 2.0, "preco_venda_unit": 97.77},
            {"cProd": "80070", "xProd": "CORREDICA", "ncm": "83024200", "uCom": "UN",
             "qCom": 1.0, "preco_venda_unit": 13.65},
        ],
    }


def test_payload_topo_e_emitente():
    p = mp.montar_payload(_nota())
    assert p["tipo_documento"] == 1 and p["finalidade_emissao"] == 1
    assert p["consumidor_final"] == 1 and p["presenca_comprador"] == 1
    assert p["natureza_operacao"] == "Venda de mercadoria"
    assert p["data_emissao"] == "2026-07-05T10:00:00-03:00"
    assert p["cnpj_emitente"] == "19152134000156" and "cpf_emitente" not in p
    assert p["regime_tributario_emitente"] == 1 and p["nome_emitente"] == "LOJA X"
    assert p["uf_emitente"] == "SP" and p["cep_emitente"] == "01000-000"


def test_payload_destinatario_cpf_e_indicador():
    p = mp.montar_payload(_nota(doc_tipo="cpf"))
    assert p["cpf_destinatario"] == "22222222222" and "cnpj_destinatario" not in p
    assert p["indicador_inscricao_estadual_destinatario"] == 9
    assert p["pais_destinatario"] == "Brasil" and p["nome_destinatario"] == "CLIENTE Y"


def test_payload_destinatario_cnpj():
    p = mp.montar_payload(_nota(doc_tipo="cnpj"))
    assert p["cnpj_destinatario"] == "11111111111111" and "cpf_destinatario" not in p


def test_payload_cfop_dentro_uf():
    p = mp.montar_payload(_nota(uf_emit="SP", uf_dest="SP"))
    assert all(it["cfop"] == "5102" for it in p["items"])


def test_payload_cfop_fora_uf():
    p = mp.montar_payload(_nota(uf_emit="SP", uf_dest="RJ"))
    assert all(it["cfop"] == "6102" for it in p["items"])


def test_payload_itens():
    p = mp.montar_payload(_nota())
    it0 = p["items"][0]
    assert it0["numero_item"] == 1 and it0["codigo_produto"] == "50079[2131748]"
    assert it0["descricao"] == "PAINEL" and it0["codigo_ncm"] == "94035000"
    assert it0["unidade_comercial"] == "UN"
    assert it0["icms_origem"] == "0" and it0["icms_situacao_tributaria"] == "101"
    assert it0["pis_situacao_tributaria"] == "49" and it0["cofins_situacao_tributaria"] == "49"
    assert it0["quantidade_comercial"] == 2.0 and it0["valor_unitario_comercial"] == 97.77
    assert it0["valor_bruto"] == 195.54          # round(2 * 97.77, 2)
    assert p["items"][1]["numero_item"] == 2 and p["items"][1]["valor_bruto"] == 13.65
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_mapa_fiscal.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'mapa_fiscal'`).

- [ ] **Step 3: Create `mapa_fiscal.py` with `montar_payload`**

```python
"""mapa_fiscal.py — mapa fiscal: preview (Fase 1) + PerfilFiscal/Loja (emitente) + Cliente
(destinatário) -> payload da NF-e da Focus. Puro: sem DB, sem rede. Regime Simples primeiro."""


def montar_payload(nota):
    """Converte o dict neutro `nota` no payload JSON da Focus NFe (bloco fiscal por item)."""
    emit = nota["emitente"]
    dest = nota["destinatario"]
    fisc = nota["fiscal"]
    dentro = emit["uf"] == dest["uf"]
    cfop = fisc["cfop_dentro"] if dentro else fisc["cfop_fora"]

    items = []
    for i, it in enumerate(nota["itens"], start=1):
        qtd = it["qCom"]
        vun = it["preco_venda_unit"]
        items.append({
            "numero_item": i,
            "codigo_produto": it["cProd"],
            "descricao": it["xProd"],
            "cfop": cfop,
            "codigo_ncm": it["ncm"],
            "unidade_comercial": it.get("uCom") or "UN",
            "quantidade_comercial": qtd,
            "valor_unitario_comercial": vun,
            "valor_bruto": round(qtd * vun, 2),
            "icms_origem": "0",
            "icms_situacao_tributaria": fisc["csosn"],
            "pis_situacao_tributaria": fisc["pis_cst"],
            "cofins_situacao_tributaria": fisc["cofins_cst"],
        })

    payload = {
        "natureza_operacao": nota["natureza_operacao"],
        "data_emissao": nota["data_emissao"],
        "tipo_documento": 1,
        "finalidade_emissao": 1,
        "consumidor_final": 1,
        "presenca_comprador": 1,
        "nome_emitente": emit["nome"],
        "regime_tributario_emitente": emit["regime"],
        "inscricao_estadual_emitente": emit["ie"],
        "logradouro_emitente": emit["logradouro"],
        "numero_emitente": emit["numero"],
        "bairro_emitente": emit["bairro"],
        "municipio_emitente": emit["municipio"],
        "uf_emitente": emit["uf"],
        "cep_emitente": emit["cep"],
        "nome_destinatario": dest["nome"],
        "indicador_inscricao_estadual_destinatario": 9,
        "logradouro_destinatario": dest["logradouro"],
        "numero_destinatario": dest["numero"],
        "bairro_destinatario": dest["bairro"],
        "municipio_destinatario": dest["municipio"],
        "uf_destinatario": dest["uf"],
        "cep_destinatario": dest["cep"],
        "pais_destinatario": "Brasil",
        "items": items,
    }
    if emit["doc_tipo"] == "cnpj":
        payload["cnpj_emitente"] = emit["doc"]
    else:
        payload["cpf_emitente"] = emit["doc"]
    if dest["doc_tipo"] == "cnpj":
        payload["cnpj_destinatario"] = dest["doc"]
    else:
        payload["cpf_destinatario"] = dest["doc"]
    return payload
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_mapa_fiscal.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mapa_fiscal.py tests/test_mapa_fiscal.py
git commit -m "feat(nfe): mapa_fiscal.montar_payload (nota -> payload Focus, Simples)"
```

---

## Task 2: `mapa_fiscal.montar_nota` (modelos → nota)

**Files:**
- Modify: `mapa_fiscal.py`
- Modify: `tests/test_mapa_fiscal.py`

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_mapa_fiscal.py`:

```python
from types import SimpleNamespace


def test_montar_nota_from_objetos():
    perfil = SimpleNamespace(razao_social="LOJA X LTDA", regime_tributario="simples",
                             inscricao_estadual="ISENTO", csosn_padrao="101",
                             cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="19152134000156", nome="Loja X", logradouro="Rua A", numero="1",
                           bairro="Centro", cidade="Sao Paulo", estado="SP", cep="01000-000")
    cliente = SimpleNamespace(nome="Cliente Y", cpf="22222222222", logradouro="Rua B", numero="2",
                              bairro="Jd", cidade="Rio", estado="RJ", cep="20000-000")
    itens = [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN",
              "qCom": 1.0, "preco_venda_unit": 10.0}]
    nota = mp.montar_nota(perfil, loja, cliente, itens, ref="R9", data_emissao="D")
    assert nota["ref"] == "R9" and nota["data_emissao"] == "D"
    assert nota["natureza_operacao"] == "Venda de mercadoria"
    assert nota["emitente"]["doc_tipo"] == "cnpj" and nota["emitente"]["doc"] == "19152134000156"
    assert nota["emitente"]["regime"] == 1 and nota["emitente"]["nome"] == "LOJA X LTDA"
    assert nota["emitente"]["uf"] == "SP"
    assert nota["destinatario"]["doc_tipo"] == "cpf" and nota["destinatario"]["doc"] == "22222222222"
    assert nota["destinatario"]["uf"] == "RJ"
    assert nota["fiscal"]["csosn"] == "101" and nota["fiscal"]["cfop_dentro"] == "5102"
    assert nota["fiscal"]["pis_cst"] == "49" and nota["fiscal"]["cofins_cst"] == "49"
    assert nota["itens"] == itens
    # round-trip: montar_payload da nota montada escolhe CFOP fora (SP emit vs RJ dest)
    p = mp.montar_payload(nota)
    assert p["items"][0]["cfop"] == "6102"


def test_montar_nota_regime_normal_e_cliente_cnpj():
    perfil = SimpleNamespace(razao_social="L", regime_tributario="normal", inscricao_estadual="1",
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="1", nome="L", logradouro="a", numero="1", bairro="b",
                           cidade="c", estado="SP", cep="1")
    cliente = SimpleNamespace(nome="C", cnpj="99999999000199", cpf=None, logradouro="a", numero="1",
                              bairro="b", cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(perfil, loja, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["regime"] == 3          # normal -> 3
    assert nota["destinatario"]["doc_tipo"] == "cnpj" and nota["destinatario"]["doc"] == "99999999000199"


def test_montar_nota_nome_cai_para_loja_sem_razao_social():
    perfil = SimpleNamespace(razao_social=None, regime_tributario="simples", inscricao_estadual=None,
                             csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102")
    loja = SimpleNamespace(cnpj="1", nome="NOME FANTASIA", logradouro="a", numero="1", bairro="b",
                           cidade="c", estado="SP", cep="1")
    cliente = SimpleNamespace(nome="C", cpf="2", logradouro="a", numero="1", bairro="b",
                              cidade="c", estado="SP", cep="1")
    nota = mp.montar_nota(perfil, loja, cliente, [], ref="R", data_emissao="D")
    assert nota["emitente"]["nome"] == "NOME FANTASIA"   # sem razao_social -> loja.nome
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_mapa_fiscal.py -q -k "montar_nota"`
Expected: FAIL (`AttributeError: module 'mapa_fiscal' has no attribute 'montar_nota'`).

- [ ] **Step 3: Add constants + `montar_nota` to `mapa_fiscal.py`**

Adicionar no topo do módulo (após o docstring):

```python
REGIME_FOCUS = {"simples": 1, "simples_excesso": 2, "mei": 1, "normal": 3}
PIS_CST_SIMPLES = "49"
COFINS_CST_SIMPLES = "49"
```

E a função (antes de `montar_payload`):

```python
def montar_nota(perfil, loja, cliente, itens_preview, ref, data_emissao,
                natureza="Venda de mercadoria"):
    """Assembla o dict neutro `nota` a partir dos modelos (recebe objetos; sem DB).
    Emitente = Loja (cnpj/endereço) + perfil (razão social/IE/regime); destinatário = Cliente
    (CPF -> PF consumidor final; CNPJ -> PJ, via getattr para cobrir modelo futuro)."""
    cli_cnpj = getattr(cliente, "cnpj", None)
    if cli_cnpj:
        doc_tipo, doc = "cnpj", cli_cnpj
    else:
        doc_tipo, doc = "cpf", getattr(cliente, "cpf", None)
    return {
        "ref": ref,
        "natureza_operacao": natureza,
        "data_emissao": data_emissao,
        "emitente": {
            "doc_tipo": "cnpj" if getattr(loja, "cnpj", None) else "cpf",
            "doc": getattr(loja, "cnpj", None),
            "nome": getattr(perfil, "razao_social", None) or getattr(loja, "nome", None),
            "regime": REGIME_FOCUS.get(getattr(perfil, "regime_tributario", None), 1),
            "ie": getattr(perfil, "inscricao_estadual", None),
            "logradouro": loja.logradouro, "numero": loja.numero, "bairro": loja.bairro,
            "municipio": loja.cidade, "uf": loja.estado, "cep": loja.cep,
        },
        "destinatario": {
            "nome": cliente.nome, "doc_tipo": doc_tipo, "doc": doc,
            "logradouro": cliente.logradouro, "numero": cliente.numero, "bairro": cliente.bairro,
            "municipio": cliente.cidade, "uf": cliente.estado, "cep": cliente.cep,
        },
        "fiscal": {
            "csosn": perfil.csosn_padrao, "cfop_dentro": perfil.cfop_dentro_uf,
            "cfop_fora": perfil.cfop_fora_uf, "pis_cst": PIS_CST_SIMPLES,
            "cofins_cst": COFINS_CST_SIMPLES,
        },
        "itens": list(itens_preview),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_mapa_fiscal.py -q`
Expected: PASS (6 da Task 1 + 3 novos = 9).

- [ ] **Step 5: Commit**

```bash
git add mapa_fiscal.py tests/test_mapa_fiscal.py
git commit -m "feat(nfe): mapa_fiscal.montar_nota (modelos -> nota neutra)"
```

---

## Task 3: `emissor_focus.py` — `EmissorFocusNfe`

**Files:**
- Create: `emissor_focus.py`
- Test: `tests/test_emissor_focus.py`

- [ ] **Step 1: Create the tests**

Criar `tests/test_emissor_focus.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import emissor_focus
from emissor_fiscal import EmissorFiscal, StatusNota


class FakeClient:
    def __init__(self):
        self.enviado = None; self.consultado = None; self.cancelado = None
    def enviar_nfe(self, ref, payload):
        self.enviado = (ref, payload)
        return {"ref": ref, "status": "processando_autorizacao"}
    def consultar_nfe(self, ref, completa=False):
        self.consultado = ref
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH"}
    def cancelar_nfe(self, ref, justificativa):
        self.cancelado = (ref, justificativa)
        return {"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"}


def _nota():
    return {"ref": "R1", "natureza_operacao": "Venda", "data_emissao": "D",
            "emitente": {"doc_tipo": "cnpj", "doc": "1", "nome": "L", "regime": 1, "ie": "1",
                         "logradouro": "a", "numero": "1", "bairro": "b", "municipio": "c",
                         "uf": "SP", "cep": "1"},
            "destinatario": {"nome": "C", "doc_tipo": "cpf", "doc": "2", "logradouro": "a",
                             "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102",
                       "pis_cst": "49", "cofins_cst": "49"},
            "itens": [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN",
                       "qCom": 1.0, "preco_venda_unit": 10.0}]}


def test_e_um_emissor_fiscal():
    assert issubclass(emissor_focus.EmissorFocusNfe, EmissorFiscal)


def test_emitir_nfe_produto_monta_e_envia():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).emitir_nfe_produto(_nota())
    ref, payload = fc.enviado
    assert ref == "R1"
    assert payload["cnpj_emitente"] == "1" and payload["items"][0]["cfop"] == "5102"
    assert res.status == StatusNota.PROCESSANDO and res.ref == "R1"


def test_consultar_status_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).consultar_status("R1")
    assert fc.consultado == "R1"
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH"


def test_cancelar_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).cancelar("R1", "justificativa com mais de 15 chars")
    assert fc.cancelado == ("R1", "justificativa com mais de 15 chars")
    assert res.status == StatusNota.CANCELADO and res.xml_cancelamento_url == "/c.xml"


def test_nfse_ainda_notimplemented():
    with pytest.raises(NotImplementedError):
        emissor_focus.EmissorFocusNfe(FakeClient()).emitir_nfse_servico({})
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_emissor_focus.py -q`
Expected: FAIL (`No module named 'emissor_focus'`).

- [ ] **Step 3: Create `emissor_focus.py`**

```python
"""emissor_focus.py — implementação concreta de EmissorFiscal sobre a Focus NFe (Fase 3b).
Monta o payload (mapa_fiscal) e transmite via FocusClient (Fase 2). Sem regra fiscal aqui."""
import mapa_fiscal
from emissor_fiscal import EmissorFiscal, resultado_de_focus


class EmissorFocusNfe(EmissorFiscal):
    """Recebe um FocusClient injetado (montado por mod_fiscal.focus_client_para_loja)."""

    def __init__(self, client):
        self.client = client

    def emitir_nfe_produto(self, nota):
        payload = mapa_fiscal.montar_payload(nota)
        return resultado_de_focus(self.client.enviar_nfe(nota["ref"], payload))

    def consultar_status(self, ref):
        return resultado_de_focus(self.client.consultar_nfe(ref))

    def cancelar(self, ref, justificativa):
        return resultado_de_focus(self.client.cancelar_nfe(ref, justificativa))
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_emissor_focus.py -q`
Expected: PASS (5 testes). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add emissor_focus.py tests/test_emissor_focus.py
git commit -m "feat(nfe): EmissorFocusNfe (concreto EmissorFiscal sobre a Focus)"
```

---

## Task 4: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/fiscal/2026-07-05-nfe-fase3b-mapa-fiscal-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar `> Status: **APROVADO (brainstorming)** — a implementar. É o "coração"...` por
`> Status: **IMPLEMENTADO (Sessão N)** — mapa fiscal + EmissorFocusNfe com testes offline; emissão real (Fase 4) pendente do token da Focus.`

- [ ] **Step 3: DEV_LOG — nota na Sessão 47 + ESTADO ATUAL**

Registrar: **Fase 3b (mapa fiscal) implementada** — `mapa_fiscal.py` (`montar_nota` modelos→nota;
`montar_payload` nota→payload Focus: CFOP dentro/fora por UF, CSOSN do perfil, ICMS origem 0, PIS/COFINS
CST 49, `valor_bruto`, emitente Loja+perfil, destinatário Cliente PF/PJ) e `emissor_focus.py`
(`EmissorFocusNfe` fecha o contrato `EmissorFiscal` com o `FocusClient`); testes **offline** (sem emissão
real). Pendências: **Fase 4** (emissão real em homologação — token da Focus) e **Fase 5** (orquestração +
UI etapa 15); regimes Normal/Presumido e correção fiscal fina com o contador. Atualizar `⏸️ ESTADO ATUAL`.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/fiscal/2026-07-05-nfe-fase3b-mapa-fiscal-design.md
git commit -m "docs(nfe): DEV_LOG + spec Fase 3b como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §4.1 `montar_payload` (Task 1) + `montar_nota` (Task 2); §4.2 `EmissorFocusNfe`
  (Task 3); §5 testes distribuídos (payload por UF/CSOSN/CST/valor_bruto/CPF×CNPJ; montar_nota dos
  modelos; emissor com client fake). §6 fora de escopo respeitado (sem emissão real, sem orquestração/UI,
  sem regimes extras).
- **Consistência de nomes:** o dict `nota` (chaves `ref, natureza_operacao, data_emissao, emitente{doc_tipo,
  doc, nome, regime, ie, logradouro, numero, bairro, municipio, uf, cep}, destinatario{...}, fiscal{csosn,
  cfop_dentro, cfop_fora, pis_cst, cofins_cst}, itens[]`) é idêntico entre `montar_nota` (produz),
  `montar_payload` (consome) e os testes. `EmissorFocusNfe(client)` + métodos batem com o contrato
  `EmissorFiscal` da Fase 2 e usam `resultado_de_focus`. Campos do payload conferem com a doc da Focus
  (`*_emitente`, `*_destinatario`, `items[]`, `icms_situacao_tributaria`, etc.).
- **Aritmética conferida:** `valor_bruto` do 1º item = round(2 × 97.77, 2) = 195.54; 2º = 13.65.
- **Sem placeholders:** todo passo com código tem o código completo. `Sessão N` = número corrente do
  DEV_LOG na hora.
```
