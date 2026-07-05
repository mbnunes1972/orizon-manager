# NF-e Fase 3b — Mapa Fiscal + `EmissorFocusNfe` — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. É o "coração" da guinada: transforma dado real
> (preview + PerfilFiscal) no payload da NF-e e fecha o contrato `EmissorFiscal` com a Focus.

## 1. Contexto e recorte

A Focus NFe **não calcula imposto** — nós montamos o bloco fiscal por item. Esta fase implementa o
**mapa fiscal**: dado o `preview` da Fase 1 (itens precificados) + o `PerfilFiscal` (Sub-frente I) da
loja emitente + o `Cliente` destinatário, produz o **payload JSON da Focus** e o concreto
**`EmissorFocusNfe`** que fecha o contrato `EmissorFiscal` (Fase 2).

**Recorte (aprovado):** **offline** — monta e valida o payload **sem emitir de verdade** (emissão real +
homologação = **Fase 4**, depende do token da Focus). **Regime Simples primeiro** (CNPJ de teste),
estruturado para estender a Normal/Presumido. Correção fiscal fina (CSOSN 101 crédito, CST reais) fica
para a Fase 4 com o contador.

Pipeline completo: `mod_nfe.preview` (Fase 1) → **`mapa_fiscal` (esta fase)** → `focus_client.enviar_nfe`
(Fase 2) → homologação/SEFAZ (Fase 4). O `FocusClient` é montado por loja via
`mod_fiscal.focus_client_para_loja` (Sub-frente I).

## 2. Fatos do payload Focus (confirmados na doc)

- **Topo:** `natureza_operacao`, `data_emissao` (ISO 8601), `tipo_documento` (0/1), `finalidade_emissao`
  (1-4), `items[]`; opcionais `consumidor_final` (0/1), `presenca_comprador`.
- **Emitente (vem do payload):** `cnpj_emitente`|`cpf_emitente`, `nome_emitente`,
  `regime_tributario_emitente` (1=Simples, 2=Simples excesso, 3=Normal), `inscricao_estadual_emitente`,
  `logradouro_/numero_/bairro_/municipio_/uf_/cep_emitente`.
- **Destinatário:** `nome_destinatario`, `cpf_destinatario`|`cnpj_destinatario`,
  `indicador_inscricao_estadual_destinatario` (9=não contribuinte), `logradouro_/numero_/bairro_/
  municipio_/uf_/cep_/pais_destinatario`. **Código IBGE do município NÃO é exigido.**
- **Item:** `numero_item`, `codigo_produto`, `descricao`, `cfop`, `codigo_ncm`, `unidade_comercial`,
  `quantidade_comercial`, `valor_unitario_comercial`, `valor_bruto`, `icms_origem` (0=nacional),
  `icms_situacao_tributaria` (CSOSN no Simples), `pis_situacao_tributaria`, `cofins_situacao_tributaria`.

## 3. Decisões (brainstorming)

- **Offline, Simples primeiro.** Sem emissão real (Fase 4). Regime parametrizado; Simples implementado.
- **Destinatário:** do `Cliente` do projeto — **CPF → PF consumidor final** (`consumidor_final=1`,
  `indicador_inscricao_estadual_destinatario=9`, `presenca_comprador=1`); se o Cliente tiver CNPJ, trata
  como PJ (`cnpj_destinatario`). O caso comum é PF.
- **Defaults fiscais:** `icms_situacao_tributaria = perfil.csosn_padrao`; `icms_origem = "0"`;
  **PIS/COFINS CST default `"49"`** no Simples; CFOP = `perfil.cfop_dentro_uf` se UF emitente == UF
  destinatário, senão `perfil.cfop_fora_uf`. Itens **sob-medida e padrão entram igual** (ambos são
  produto; o mapa não distingue). Refinamento fiscal real = Fase 4.
- **`data_emissao` é parâmetro** (testes determinísticos; o caller da Fase 4/5 passa `datetime.now`).
- **`EmissorFocusNfe` recebe um `FocusClient` injetado** (montado por `focus_client_para_loja`).

## 4. Componentes e interfaces

### 4.1 `mapa_fiscal.py` (puro — sem DB, sem rede)

```python
REGIME_FOCUS = {"simples": 1, "simples_excesso": 2, "mei": 1, "normal": 3}
PIS_CST_SIMPLES = "49"
COFINS_CST_SIMPLES = "49"

def montar_nota(perfil, loja, cliente, itens_preview, ref, data_emissao,
                natureza="Venda de mercadoria") -> dict:
    """Assembla o dict neutro `nota` a partir dos modelos (sem DB — recebe os objetos)."""
    # emitente: Loja (cnpj/endereço) + perfil (razao_social→nome, IE, regime)
    # destinatario: Cliente (nome, cpf|cnpj?, endereço)  → doc_tipo = "cpf" | "cnpj"
    # fiscal: perfil.csosn_padrao, cfop_dentro_uf, cfop_fora_uf, PIS_CST_SIMPLES, COFINS_CST_SIMPLES
    # itens: itens_preview (lista do preview da Fase 1)
    # retorna {ref, natureza_operacao, data_emissao, emitente{...}, destinatario{...}, fiscal{...}, itens[...]}

def montar_payload(nota: dict) -> dict:
    """Converte o `nota` neutro no payload JSON da Focus NFe (bloco fiscal por item)."""
```

**`montar_nota` — blocos:**
- `emitente`: `{cnpj: loja.cnpj, nome: (perfil.razao_social or loja.nome), regime:
  REGIME_FOCUS.get(perfil.regime_tributario, 1), ie: perfil.inscricao_estadual, logradouro: loja.logradouro,
  numero: loja.numero, bairro: loja.bairro, municipio: loja.cidade, uf: loja.estado, cep: loja.cep}`.
- `destinatario`: `{nome: cliente.nome, doc_tipo: "cnpj" if cliente_tem_cnpj else "cpf",
  doc: (cnpj|cpf), logradouro: cliente.logradouro, numero: cliente.numero, bairro: cliente.bairro,
  municipio: cliente.cidade, uf: cliente.estado, cep: cliente.cep}`. (O modelo `Cliente` tem `cpf`; se
  no futuro ganhar `cnpj`, o `doc_tipo` cobre — por ora, CPF.)
- `fiscal`: `{csosn: perfil.csosn_padrao, cfop_dentro: perfil.cfop_dentro_uf, cfop_fora:
  perfil.cfop_fora_uf, pis_cst: PIS_CST_SIMPLES, cofins_cst: COFINS_CST_SIMPLES}`.

**`montar_payload` — regras:**
- `dentro = emitente.uf == destinatario.uf`; `cfop = fiscal.cfop_dentro if dentro else fiscal.cfop_fora`.
- Cada item do preview vira:
  ```python
  {"numero_item": i (1-based), "codigo_produto": it["cProd"], "descricao": it["xProd"],
   "cfop": cfop, "codigo_ncm": it["ncm"], "unidade_comercial": it.get("uCom") or "UN",
   "quantidade_comercial": it["qCom"], "valor_unitario_comercial": it["preco_venda_unit"],
   "valor_bruto": round(it["qCom"] * it["preco_venda_unit"], 2),
   "icms_origem": "0", "icms_situacao_tributaria": fiscal["csosn"],
   "pis_situacao_tributaria": fiscal["pis_cst"], "cofins_situacao_tributaria": fiscal["cofins_cst"]}
  ```
- Emitente → `cnpj_emitente` (ou `cpf_emitente` se doc for CPF), `nome_emitente`,
  `regime_tributario_emitente`, `inscricao_estadual_emitente`, `logradouro_emitente`…`cep_emitente`.
- Destinatário → `nome_destinatario`, `cpf_destinatario`|`cnpj_destinatario` (por `doc_tipo`),
  `indicador_inscricao_estadual_destinatario: 9`, `logradouro_destinatario`…`cep_destinatario`,
  `pais_destinatario: "Brasil"`.
- Topo → `natureza_operacao`, `data_emissao`, `tipo_documento: 1` (saída), `finalidade_emissao: 1`,
  `consumidor_final: 1`, `presenca_comprador: 1`, `items: [...]`.

### 4.2 `emissor_focus.py` — `EmissorFocusNfe(EmissorFiscal)`

```python
from emissor_fiscal import EmissorFiscal, resultado_de_focus
import mapa_fiscal

class EmissorFocusNfe(EmissorFiscal):
    def __init__(self, client):            # FocusClient injetado
        self.client = client
    def emitir_nfe_produto(self, nota):     # nota = montar_nota(...)
        payload = mapa_fiscal.montar_payload(nota)
        return resultado_de_focus(self.client.enviar_nfe(nota["ref"], payload))
    def consultar_status(self, ref):
        return resultado_de_focus(self.client.consultar_nfe(ref))
    def cancelar(self, ref, justificativa):
        return resultado_de_focus(self.client.cancelar_nfe(ref, justificativa))
    # emitir_nfse_servico herda o NotImplementedError da ABC
```

## 5. Testes (offline, sem rede)

- **`tests/test_mapa_fiscal.py`:**
  - `montar_payload` (a partir de um `nota` fixo): CFOP **dentro** (UF emitente==dest) vs **fora**;
    item traz `codigo_ncm`, `icms_origem="0"`, `icms_situacao_tributaria=CSOSN`, `pis/cofins="49"`,
    `valor_bruto = round(qtd*preço,2)`, `numero_item` sequencial; emitente/dest mapeados; **CPF** →
    `cpf_destinatario` (e um caso **CNPJ** → `cnpj_destinatario`); `consumidor_final=1`,
    `indicador_inscricao_estadual_destinatario=9`; `regime_tributario_emitente=1` (Simples).
  - `montar_nota` (a partir de objetos leves com os atributos usados — pode ser um stub/`SimpleNamespace`
    ou os modelos reais): monta `emitente/destinatario/fiscal/itens` com os valores certos; escolhe
    `doc_tipo` por CPF/CNPJ; usa `data_emissao` recebido.
- **`tests/test_emissor_focus.py`:** `EmissorFocusNfe` com um `FocusClient` **fake** (grava o
  `enviar_nfe(ref, payload)` chamado): `emitir_nfe_produto(nota)` chama o client com o payload de
  `montar_payload` e devolve `ResultadoEmissao` (via `resultado_de_focus`); `consultar_status`/`cancelar`
  delegam ao client e normalizam. **Nenhuma chamada real.**

Suíte verde (`python3 -m pytest -q`, baseline 493).

## 6. Fora de escopo (fases seguintes)

- **Emissão real / homologação / polling / guarda do XML-DANFE** — **Fase 4** (precisa do token da Focus).
- **Orquestração** (buscar loja/cliente/preview de um projeto, gerar `ref`, chamar o emissor) e **UI da
  etapa 15** — **Fase 5**.
- **Regimes Normal/Presumido** (CST + alíquotas ICMS destacadas), **CSOSN 101 crédito**, PIS/COFINS reais —
  refinamento fiscal com o contador (o mapa já é parametrizado por regime; só faltam os ramos).
- **NFS-e** — depende de 2º CNPJ + município integrado.
- **Persistência do payload/resultado** e vínculo com o projeto — Fase 4/5.
