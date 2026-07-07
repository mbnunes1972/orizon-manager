# Fiscal — NFS-e de Serviço (US-38) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recomendado) ou executing-plans. Passos com checkbox (`- [ ]`).

**Goal:** Emitir a **NFS-e de serviço** (montagem) — espelha o caminho do NF-e de produto: transporte `/v2/nfse`, nota→payload NFS-e, emissor, ramificação por `tipo_documento`, endpoint `…/ciclo/15/emitir-nfse` (valor manual) e seção no painel da etapa 15.

**Architecture:** Backend puro primeiro (client + mapa NFS-e) → serviço (emissor + `nfe_emissao` ramifica) → endpoint + estado → frontend. Verde a cada tarefa. Branch `feat/fiscal-nfse-servico`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/2026-07-06-fiscal-nfse-servico-design.md`.

**Ler antes:** o spec; `focus_client.py` (`enviar_nfe`/`consultar_nfe`/`cancelar_nfe`/`aguardar_processamento` — espelhar p/ nfse); `mapa_fiscal.py` (`montar_nota`/`montar_payload`, `_so_digitos`, `_dest_fiscal`); `emissor_fiscal.py` (`EmissorFiscal.emitir_nfse_servico` = NotImplementedError; `resultado_de_focus` normalizer; `ResultadoEmissao`); `emissor_focus.py` (`EmissorFocusNfe`); `nfe_emissao.py` (`emitir`/`consultar`/`cancelar`, `_guardar_docs_autorizado`, `_TIPO_*`); `main.py` (`…/ciclo/15/emitir-nfe`, `GET …/ciclo/15/nfe`); `Emitente` (campos serviço: inscricao_municipal, cnae_servico, cod_servico_municipio, aliquota_iss, municipio_ibge). **Baseline 578 passed.** Teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`). `git add` só os arquivos da mudança.

> **Nota sobre a Focus NFS-e:** os nomes exatos de campos do payload `/v2/nfse` e das URLs de retorno
> (xml/pdf) seguem a doc da Focus — construa um payload razoável (abaixo) e deixe explícito; o smoke
> estrutural revelará ajustes (como o produto revelou `modalidade_frete`). Não bloquear por isso.

---

## Task 1: `focus_client` NFS-e + `mapa_fiscal` NFS-e (transporte + payload)

**Files:** Modify `focus_client.py`, `mapa_fiscal.py`; Test: `tests/test_focus_client.py`, `tests/test_mapa_fiscal_nfse.py` (novo).

- [ ] **Step 1: Testes falhando** — em `test_focus_client.py`, `enviar_nfse`/`consultar_nfse`/`cancelar_nfse`
usam `/v2/nfse` (monkeypatch de `requests.request` como os testes de nfe). Novo `tests/test_mapa_fiscal_nfse.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mapa_fiscal as mp
from types import SimpleNamespace

def _emit():
    return SimpleNamespace(cnpj="19.152.134/0001-56", razao_social="L", inscricao_municipal="IM123",
                           cnae_servico="4330404", cod_servico_municipio="0701", aliquota_iss=5.0,
                           municipio_ibge="3549904", retencao_json=None)

def _cli():
    return SimpleNamespace(nome="C", tipo_dest="nao_contribuinte", cpf="111.444.777-35", cnpj=None,
                           inscricao_estadual=None, logradouro="R", numero="1", bairro="b",
                           cidade="SJC", estado="SP", cep="12242-800")

def test_montar_nota_nfse():
    nota = mp.montar_nota_nfse(_emit(), _cli(), 500.0, "NFSE-P", "2026-07-06T10:00:00-03:00", "Montagem de moveis")
    assert nota["servico"]["valor_servicos"] == 500.0 and nota["servico"]["aliquota"] == 5.0
    assert nota["prestador"]["cnpj"] == "19152134000156" and nota["prestador"]["codigo_municipio"] == "3549904"
    assert nota["tomador"]["doc"] == "11144477735"

def test_montar_payload_nfse():
    nota = mp.montar_nota_nfse(_emit(), _cli(), 500.0, "NFSE-P", "D", "Montagem")
    p = mp.montar_payload_nfse(nota)
    assert p["prestador"]["cnpj"] == "19152134000156" and p["prestador"]["codigo_municipio"] == "3549904"
    assert p["servico"]["valor_servicos"] == 500.0 and p["servico"]["aliquota"] == 5.0
    assert p["servico"]["iss_retido"] is False and p["servico"]["discriminacao"] == "Montagem"
    assert p["cpf_tomador"] == "11144477735" or p["tomador"]["cpf"] == "11144477735"  # conforme o formato Focus
```

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: `focus_client.py`** — adicionar (espelhando os de nfe):
```python
    def enviar_nfse(self, ref, payload):
        return self._request("POST", "/v2/nfse", params={"ref": ref}, json_body=payload)
    def consultar_nfse(self, ref, completa=False):
        return self._request("GET", "/v2/nfse/%s" % ref, params={"completa": 1 if completa else 0})
    def cancelar_nfse(self, ref, justificativa):
        # (validar 15-255 como o cancelar_nfe, se a Focus exigir p/ NFS-e; senão sem validação)
        return self._request("DELETE", "/v2/nfse/%s" % ref, json_body={"justificativa": justificativa})
    def aguardar_processamento_nfse(self, ref, timeout=60, intervalo=3):
        # espelha aguardar_processamento, mas usando consultar_nfse
        ...
```

- [ ] **Step 4: `mapa_fiscal.py`** — `montar_nota_nfse(emitente, cliente, valor_servico, ref, data_emissao, discriminacao)`:
```python
def montar_nota_nfse(emitente, cliente, valor_servico, ref, data_emissao, discriminacao):
    doc_tipo, doc, indicador_ie, ie, consumidor_final = _dest_fiscal(cliente)
    return {
        "ref": ref, "data_emissao": data_emissao,
        "prestador": {"cnpj": _so_digitos(emitente.cnpj), "inscricao_municipal": emitente.inscricao_municipal,
                      "codigo_municipio": emitente.municipio_ibge},
        "tomador": {"nome": cliente.nome, "doc_tipo": doc_tipo, "doc": _so_digitos(doc),
                    "logradouro": cliente.logradouro, "numero": cliente.numero, "bairro": cliente.bairro,
                    "municipio": cliente.cidade, "uf": cliente.estado, "cep": _so_digitos(cliente.cep)},
        "servico": {"valor_servicos": round(float(valor_servico), 2), "aliquota": emitente.aliquota_iss,
                    "discriminacao": discriminacao, "iss_retido": False,
                    "item_lista_servico": emitente.cod_servico_municipio,
                    "codigo_tributario_municipio": emitente.cnae_servico},
    }
```
E `montar_payload_nfse(nota)` → payload Focus (achatar prestador/tomador/servico conforme a doc Focus; `cpf_tomador`/`cnpj_tomador` por doc_tipo). Mantenha os nomes de campo próximos da doc Focus NFS-e.

- [ ] **Step 5: Rodar** → verde. **Commit:**
```
git add focus_client.py mapa_fiscal.py tests/test_focus_client.py tests/test_mapa_fiscal_nfse.py
git commit -m "feat(fiscal): focus_client /v2/nfse + mapa_fiscal montar_nota_nfse/payload_nfse"
```

---

## Task 2: `emissor_focus.emitir_nfse_servico` + `nfe_emissao` ramifica por tipo_documento

**Files:** Modify `emissor_focus.py`, `nfe_emissao.py`, `emissor_fiscal.py` (se o normalizer precisar de URLs NFS-e); Test: `tests/test_emissor_focus.py`, `tests/test_nfe_emissao.py`.

- [ ] **Step 1: Testes falhando** — `test_emissor_focus.py`: `emitir_nfse_servico(nota_nfse)` chama
`montar_payload_nfse`+`client.enviar_nfse` (client fake captura). `test_nfe_emissao.py`: `emitir(...,
tipo_documento="servico", ...)` com emissor fake chama o caminho NFS-e e grava `DocumentoFiscal
tipo_documento="servico"`.

- [ ] **Step 2: `emissor_focus.py`** — implementar (na classe `EmissorFocusNfe`):
```python
    def emitir_nfse_servico(self, nota):
        from mapa_fiscal import montar_payload_nfse
        return resultado_de_focus(self.client.enviar_nfse(nota["ref"], montar_payload_nfse(nota)))
    def consultar_status_nfse(self, ref):
        return resultado_de_focus(self.client.consultar_nfse(ref))
    def cancelar_nfse(self, ref, justificativa):
        return resultado_de_focus(self.client.cancelar_nfse(ref, justificativa))
```
Se `resultado_de_focus` (em `emissor_fiscal.py`) não mapear as URLs de xml/pdf da NFS-e, estender o
normalizer para cobrir os campos NFS-e (ex.: `caminho_xml`/`url`/`caminho_nfse`) → `xml_url`/`danfe_url`.

- [ ] **Step 3: `nfe_emissao.py` — ramificar**
- `emitir(...)`: onde hoje chama `emissor.emitir_nfe_produto(nota)` + `aguardar_processamento(ref)`, ramificar:
  `if tipo_documento == "servico": res = emissor.emitir_nfse_servico(nota)` e polling via
  `emissor.client.aguardar_processamento_nfse(ref)`; senão o caminho de produto. **O carimbo de nome SEFAZ
  em homologação (`_NOME_DEST_HOMOLOG`) é só do NF-e/destinatário — NÃO aplicar à NFS-e.**
- `_guardar_docs_autorizado`: para servico, usar tipos `nfse_loja_xml`/`nfse_loja_pdf` (constantes novas).
- `consultar(reg)`/`cancelar(reg)`: ramificar por `reg.tipo_documento` (servico → `consultar_status_nfse`/`cancelar_nfse`).

- [ ] **Step 4: Rodar** → verde. **Commit:**
```
git add emissor_focus.py nfe_emissao.py emissor_fiscal.py tests/test_emissor_focus.py tests/test_nfe_emissao.py
git commit -m "feat(fiscal): emitir_nfse_servico + nfe_emissao ramifica NF-e/NFS-e por tipo_documento"
```

---

## Task 3: Endpoint `emitir-nfse` + estado da NFS-e no `GET …/ciclo/15/nfe`

**Files:** Modify `main.py`; Test: `tests/test_nfe_etapa15_e2e.py`.

- [ ] **Step 1: Testes falhando** — e2e (emissor mockado via `nfe_emissao._emissor_para`):
`POST /api/projetos/<nome>/ciclo/15/emitir-nfse {"valor_servico": 500}` → 200 autorizado; `DocumentoFiscal
tipo="servico"` com `ref="NFSE-<projeto>"`; `GET …/ciclo/15/nfe` inclui o estado da NFS-e; **sem emitente
serviço** (loja sem self/política) → 400; **valor ≤ 0** → 400; idempotência (2º emitir mesmo ref).

- [ ] **Step 2: `main.py`** — `POST /api/projetos/(\d?...)/ciclo/15/emitir-nfse` (espelha `emitir-nfe`):
gate `editar_dados_loja`+escopo; `emitente = mod_fiscal.resolver_emitente(db, loja, "servico")` (ValueError→400);
`cliente` do projeto (400 se sem cliente); `valor = float(req.get("valor_servico") or 0)`; se `valor <= 0` →
400; `ref = "NFSE-" + nome_safe`; `nota = mapa_fiscal.montar_nota_nfse(emitente, cliente, valor, ref,
data_emissao, req.get("discriminacao") or "Serviço de montagem/instalação de móveis planejados")`;
`res = nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="servico", emitente_id=emitente.id)`.
Resposta como o emitir-nfe (ref/status/chave/…).
- `GET …/ciclo/15/nfe`: além dos `fabrica_xmls`, incluir `nfse`: o `DocumentoFiscal(projeto_nome, tipo="servico")`
  (ref, status, chave, emitente_cnpj/razao, xml_doc_id, danfe_doc_id) ou null.

- [ ] **Step 3: Rodar** → verde. **Commit:**
```
git add main.py tests/test_nfe_etapa15_e2e.py
git commit -m "feat(fiscal): endpoint emitir-nfse (valor manual) + estado da NFS-e no GET da etapa 15"
```

---

## Task 4: Frontend — seção NFS-e de Serviço no painel da etapa 15

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** No `_renderCardEmissaoNfe`, após a lista de produtos, adicionar a seção **"NFS-e de Serviço
(montagem)"**: input **Valor do serviço** + botão **Emitir NFS-e** (`emitirNfseServico()`); se `_nfe15.nfse`
existe, mostrar status/chave + baixar XML/PDF + Consultar/Cancelar (reusa `consultarNfeLoja`/`cancelarNfeLoja`
pelo `ref`). Só para `_podeEmitirNfe()`.
- [ ] **Step 2:** `emitirNfseServico()` — lê o valor, `POST …/ciclo/15/emitir-nfse {valor_servico}`, `showToast`
+ `carregarCiclo`. `esc()` no dinâmico. `nfe15Carregar` já traz `_nfe15` (que passa a ter `.nfse`).
- [ ] **Step 3:** balanceamento do `<script>` (não piorar) + `pytest -q` verde. **Commit:**
```
git add static/index.html
git commit -m "feat(fiscal): painel etapa 15 emite NFS-e de servico (valor manual)"
```

---

## Task 5: Fechamento — docs

- [ ] **Step 1:** `pytest -q` verde. **Step 2:** spec → **IMPLEMENTADO**; DEV_LOG (NFS-e de serviço emite —
faturamento produto+serviço multi-CNPJ completo; smoke NFS-e pendente da habilitação municipal); BACKLOG —
**US-38/US-32** feita. **Step 3:** commit + re-ingerir MCP no merge.

---

## Self-review do plano
- **Cobertura do spec:** §3.1 client (T1) · §3.2 mapa (T1) · §3.3 emissor (T2) · §3.4 nfe_emissao (T2) · §4
  endpoint+estado (T3) · §5 UI (T4) · §6 testes distribuídos · §7 fora de escopo respeitado.
- **Sem placeholders:** helpers com código; os nomes de campo Focus NFS-e ficam explicitados como "verificar
  no smoke" (known unknown), não como lacuna.
- **Consistência:** `montar_nota_nfse`/`montar_payload_nfse`, `enviar/consultar/cancelar_nfse`,
  `emitir_nfse_servico`, `tipo_documento="servico"`, `ref="NFSE-<projeto>"`, tipos `nfse_loja_xml/pdf`
  idênticos entre tarefas. Verde a cada tarefa (transporte → serviço → endpoint → UI).
```
