# Fiscal — NFS-e de Serviço (montagem) (US-38) — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (branch `feat/fiscal-nfse-servico`, suíte 600)** — emite a **NFS-e de serviço**
> (montagem): `focus_client /v2/nfse`, `mapa_fiscal.montar_nota_nfse`/`montar_payload_nfse`,
> `EmissorFocusNfe.emitir_nfse_servico`, `nfe_emissao` ramifica NF-e/NFS-e por `tipo_documento`, endpoint
> `…/ciclo/15/emitir-nfse` (valor manual) + estado `nfse` no GET + seção no painel. **Faturamento
> produto+serviço multi-CNPJ completo.**
>
> **Smoke real da NFS-e testado (2026-07-06):** o CNPJ **está habilitado para NFS-e** em São José dos Campos,
> o **payload foi aceito** (Focus gerou RPS nº 1/série 1, `processando_autorizacao` HTTP 202 — estrutura
> prestador/tomador/serviço OK) e a **prefeitura rejeitou por DADO**, não por código: **E70 — "Inscrição
> Municipal do prestador ... não confere"** (o `Emitente` da INSPIRIUM está com `inscricao_municipal=None`).
> ⇒ **pipeline validado ponta a ponta** (transporte → Focus → município); faltam **2 dados** (contador/loja):
> **Inscrição Municipal** e o **código do serviço no município** (item LC 116). Ambos já editáveis no painel
> Fiscal (US-36). Re-rodar o smoke após preenchê-los.

## 1. Motivação

O modelo multi-CNPJ prevê 2 documentos por venda (produto + serviço), cada um por um Emitente (o Perfil de
Emissão resolve). O produto já emite (smoke autorizado). Falta a **NFS-e de serviço**:
`EmissorFiscal.emitir_nfse_servico` = `NotImplementedError`; o `focus_client` só tem `/v2/nfe`. A NFS-e é
**municipal** (ISS, código de serviço, inscrição municipal) — o `Emitente` já tem esses campos
(`inscricao_municipal`, `cnae_servico`, `cod_servico_municipio`, `aliquota_iss`, `municipio_ibge`, `retencao_json`).

## 2. Decisões (brainstorming)

- **Valor do serviço:** **campo manual** no ato da emissão (o valor da montagem é conhecido ali).
- **Gatilho:** no **painel da etapa 15** — uma seção **"NFS-e de Serviço (montagem)"** ao lado do produto.
- **Emitente do serviço:** `resolver_emitente(loja, "servico")` (já existe; no modelo Orizon a loja emite serviço).
- **Smoke:** implementar + validar estruturalmente; a habilitação NFS-e do CNPJ no município (São José dos
  Campos p/ INSPIRIUM) é passo à parte.

## 3. Backend — caminho NFS-e (espelha o NF-e)

### 3.1 `focus_client.py` (transporte)
- `enviar_nfse(ref, payload)` → `POST /v2/nfse?ref=<ref>`.
- `consultar_nfse(ref)` → `GET /v2/nfse/<ref>`.
- `cancelar_nfse(ref, justificativa)` → `DELETE /v2/nfse/<ref>` (justificativa como no NF-e).
- `aguardar_processamento_nfse(ref, timeout, intervalo)` → polling via `consultar_nfse` (espelha o do NF-e).
`baixar(caminho)` é reusado.

### 3.2 `mapa_fiscal.py` (nota→payload NFS-e)
- `montar_nota_nfse(emitente, cliente, valor_servico, ref, data_emissao, discriminacao)` → dict neutro
  `{ref, data_emissao, prestador (do Emitente), tomador (do cliente), servico}`.
- `montar_payload_nfse(nota_nfse)` → payload Focus `/v2/nfse`:
  - `prestador`: `{cnpj: emitente (só dígitos), inscricao_municipal, codigo_municipio: municipio_ibge}`.
  - `tomador`: `{cpf|cnpj (do cliente, por tipo_dest), razao_social/nome, endereco {...}}`.
  - `servico`: `{aliquota: aliquota_iss, discriminacao, iss_retido: false, item_lista_servico:
    cod_servico_municipio, codigo_tributario_municipio: cnae_servico, valor_servicos: valor}`.
  > Os **nomes exatos dos campos** seguem a doc da Focus NFS-e; validar no smoke estrutural (como o produto
  > revelou `modalidade_frete`/só-dígitos). `_so_digitos` nos docs; `retencao_json` do Emitente (se houver) → ISS retido.

### 3.3 `emissor_focus.py` (`EmissorFocusNfe`)
Implementar (remover o `NotImplementedError` herdado):
- `emitir_nfse_servico(nota_nfse)` → `montar_payload_nfse` → `client.enviar_nfse` → `resultado_de_focus`.
- `consultar_status_nfse(ref)` → `client.consultar_nfse` → `resultado_de_focus`.
- `cancelar_nfse(ref, justificativa)` → `client.cancelar_nfse` → `resultado_de_focus`.

### 3.4 `nfe_emissao.py` — ramificar por `tipo_documento`
- `emitir(...)`: se `tipo_documento == "servico"` → `emissor.emitir_nfse_servico(nota)` e, se PROCESSANDO,
  `emissor.client.aguardar_processamento_nfse(ref)`; senão o caminho de produto atual. O carimbo de nome SEFAZ
  em homologação **não** se aplica à NFS-e (regra do NF-e); usar a regra de homologação da NFS-e se houver
  (ou nenhuma). Guardar `DocumentoFiscal(tipo_documento="servico", ...)`; XML/PDF em `CicloDocumento`
  (`nfse_loja_xml`/`nfse_loja_pdf`).
- `consultar(reg)`/`cancelar(reg)`: ramificar por `reg.tipo_documento` (nfse → `consultar_status_nfse`/`cancelar_nfse`).

## 4. Endpoint (`main.py`)

- **`POST /api/projetos/<nome>/ciclo/15/emitir-nfse`** (JSON `{valor_servico, discriminacao?}`), gated
  `editar_dados_loja` + escopo (espelha o `emitir-nfe`): resolve `loja` → `emitente =
  resolver_emitente(db, loja, "servico")` (400 claro se não resolver) → `cliente` do projeto → valida
  `valor_servico > 0` → `ref = "NFSE-" + nome_safe` (idempotente: uma NFS-e de serviço por projeto) →
  `nota = mapa_fiscal.montar_nota_nfse(emitente, cliente, valor_servico, ref, data, discriminacao)` →
  `nfe_emissao.emitir(db, loja_id, nome_safe, nota, tipo_documento="servico", emitente_id=emitente.id)`.
- **`GET /api/projetos/<nome>/ciclo/15/nfe`** passa a incluir também o estado da **NFS-e de serviço** do
  projeto (o `DocumentoFiscal tipo=servico` com ref `NFSE-<projeto>`) — além dos XMLs da fábrica/produto.
- `consultar`/`cancelar` da etapa 15 já resolvem por `ref`/`reg.tipo_documento`.

## 5. Frontend — painel etapa 15 (`static/index.html`)

No `_renderCardEmissaoNfe`, adicionar uma seção **"NFS-e de Serviço (montagem)"**: campo **Valor do serviço**
+ botão **Emitir NFS-e**; se já emitida, mostra **status/chave** + **baixar XML/PDF** + **Consultar**/**Cancelar**
(reusa `consultarNfeLoja`/`cancelarNfeLoja` por `ref`). Só para quem tem `editar_dados_loja`.

## 6. Testes

- **`mapa_fiscal`:** `montar_nota_nfse`/`montar_payload_nfse` (prestador do Emitente, tomador do cliente,
  serviço com ISS/código/valor; docs só-dígitos).
- **`focus_client`:** `enviar_nfse`/`consultar_nfse`/`cancelar_nfse` (URLs `/v2/nfse`), `aguardar_processamento_nfse`.
- **`emissor_focus`:** `emitir_nfse_servico` chama `montar_payload_nfse`+`enviar_nfse`.
- **`nfe_emissao`:** `emitir(tipo_documento="servico")` chama o caminho NFS-e e grava `DocumentoFiscal
  tipo=servico`; consultar/cancelar ramificam.
- **e2e etapa 15** (emissor mockado): `POST emitir-nfse {valor_servico}` → autoriza, `DocumentoFiscal
  tipo=servico`, `GET nfe` mostra a NFS-e; sem emitente serviço → 400; valor ≤ 0 → 400; idempotência.
- Suíte verde (baseline 578). Smoke real (Focus) fica para quando o CNPJ estiver habilitado p/ NFS-e no município.

## 7. Fora de escopo

- Múltiplas NFS-e por projeto (é 1:1 por projeto por ora).
- Valor do serviço por % / do orçamento (é manual agora).
- Ponto pós-montagem dedicado (dispara na etapa 15).
- Regras municipais além do básico (ISS retido complexo, substituição) — refinar com o contador.
