# Fiscal — Plano de Faturamento por Venda (multi-CNPJ) — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Corrige, na base, a premissa embutida "1 venda =
> 1 CNPJ = 1 documento". Escopo: estrutura (Emitente + Perfil de Emissão + Plano/documento_fiscal) +
> **re-plataforma a emissão de NF-e de produto** atual. NFS-e = slot modelado (emissão fica na US-32).

## 1. Motivação (auditoria)

Auditoria do fluxo fiscal (2026-07-06) confirmou a premissa **embutida**: quem vende é sempre quem emite,
e só existe NF-e de produto. Pontos exatos:
- **Resolução colada no vendedor:** `nfe_emissao._emissor_para(db, loja_id)` → `mod_fiscal.focus_client_para_loja(db, loja_id)` →
  `PerfilFiscal.filter_by(loja_id=loja_id)`; `mapa_fiscal.montar_nota(perfil, loja, …)` usa a **Loja vendedora**
  como emitente; endpoint `…/ciclo/15/emitir-nfe` deriva `loja_id` do `escopo_operacional(ator)`.
- **Modelo conflaciona venda↔emitente:** `NfeEmissao.loja_id` é a única referência de loja (serve de venda
  **e** emitente); **sem `tipo_documento`** e **sem emitente distinto**. Só `nfe_loja_xml` (produto).
- **Semente dormente:** `PerfilFiscal.papel_cnpj` existe mas **nunca é lido** pela emissão.
- **Não vazou** para Estoque (inexistente) nem Financeiro (`ProvisaoRegistro` não é fiscal). ⇒ o momento
  mais barato de corrigir é **agora**, antes de Comercial/Estoque reforçarem a premissa.

**Modelo de negócio real:** uma venda gera **0, 1 ou 2** documentos (NF-e produto e/ou NFS-e serviço), e
cada documento pode ser emitido por um **CNPJ diferente** do da loja vendedora (avulsa self-self; Rede Orizon
produto→central/serviço→loja; parceira produto→rede/serviço→self; etc.).

## 2. Decisões (brainstorming)

1. **Emitente de 1ª classe** — desacopla `PerfilFiscal` da Loja.
2. **Perfil de Emissão por loja, com default herdado da rede e override** — resolução `loja → rede → self`.
3. **Plano de Faturamento computado por venda** (não vira tabela pesada); as emissões persistem em
   **`documento_fiscal`** (generaliza `NfeEmissao`, com `tipo_documento` + `emitente_id`).
4. **Escopo:** estrutura + **re-plataforma o produto**; NFS-e = slot modelado, emissão adiada (US-32).

## 3. Modelo de dados

### 3.1 `Emitente` (nova — absorve `PerfilFiscal`)
Uma linha por **CNPJ que emite**. Contém tudo o que a emissão precisa, **auto-contido** (inclui o endereço
do emitente, que hoje vem da `Loja`):
```
Emitente(
  id, cnpj (unique), razao_social, nome_fantasia?, inscricao_estadual, inscricao_municipal,
  regime_tributario, csosn_padrao, cfop_dentro_uf, cfop_fora_uf, serie_nfe, discrimina_impostos,
  cnae_servico, cod_servico_municipio, aliquota_iss, retencao_json, municipio_ibge,
  logradouro, numero, bairro, cidade, uf, cep,                          # endereço do EMITENTE
  cert_validade, cert_cnpj, papel_cnpj,                                 # central_produto|loja_servico|…
  focus_token_homolog_enc, focus_token_prod_enc, ambiente_ativo, placeholders_json,
  rede_id? (opcional — a que rede este emitente pertence, p/ a central), criado_em, atualizado_em )
```
`PerfilFiscal` é **renomeada/migrada** para `Emitente` (ver §6). A tabela `perfil_fiscal` deixa de existir
logicamente (ou vira view/alias durante a transição, se necessário para não quebrar).

### 3.2 Vínculos em `Loja` e `Rede`
- **`Loja.emitente_id`** (FK Emitente, nullable) — a identidade fiscal **própria** da loja ("self").
- **`Rede.emitente_central_id`** (FK Emitente, nullable) — a distribuidora central da rede.

### 3.3 `perfil_emissao` (a política)
```
PerfilEmissao(
  id, owner_tipo ("loja"|"rede"), owner_id, tipo_doc ("produto"|"servico"),
  emitente_id (FK Emitente), criado_em )
```
- Uma linha por (owner, tipo_doc). Ausência de linha = herdar/self (ver resolução).
- Exemplos: loja INSPIRIUM → (loja, INSPIRIUM, "servico", Emitente_Inspirium); rede Orizon →
  (rede, Orizon, "produto", Emitente_Central).

### 3.4 `documento_fiscal` (generaliza `NfeEmissao`)
```
DocumentoFiscal(
  id, ref (unique, idempotência), venda_ref (= projeto_nome), etapa_codigo,
  tipo_documento ("produto"|"servico"),          # NOVO
  emitente_id (FK Emitente),                       # NOVO — o emitente resolvido (≠ loja da venda)
  loja_id (FK Loja),                               # escopo/tenancy da venda (mantido, decoplado)
  status, chave_nfe, numero, serie, mensagem_sefaz, erros_json,
  xml_doc_id, danfe_doc_id, fabrica_doc_id, emitido_em, atualizado_em )
```
`NfeEmissao` é **renomeada/migrada** para `documento_fiscal` (ver §6). `ref` do produto continua
`NFE-<projeto>-<fabrica_doc_id>`; serviço terá seu próprio padrão (ex.: `NFSE-<projeto>-<...>`) na US-32.

## 4. Resolução (funções puras/serviço em `mod_fiscal`)

- **`resolver_emitente(db, loja, tipo_doc) → Emitente`** — precedência:
  1. `perfil_emissao(owner=loja, tipo_doc)` → esse emitente;
  2. senão, se a loja tem rede: `perfil_emissao(owner=rede, tipo_doc)` → esse emitente;
  3. senão (avulsa / sem política): **self** = `Emitente(loja.emitente_id)`.
  `ValueError` claro se não resolver nenhum (loja sem emitente e sem política).
- **`resolver_plano(db, projeto) → [{tipo_doc, emitente}]`** — 0/1/2 itens conforme a venda tem
  **mercadoria** (→ produto) e/ou **serviço de montagem** (→ serviço). Para cada tipo presente, chama
  `resolver_emitente`. *(A detecção "tem serviço?" começa simples — flag/derivação do ciclo — e refina depois.)*
- **`focus_client_para_emitente(db, emitente_id) → FocusClient`** — substitui `focus_client_para_loja`;
  lê o `Emitente`, escolhe o token pelo `ambiente_ativo`, decripta, monta o `FocusClient`.

## 5. Re-plataforma da emissão de produto (mantendo a suíte verde)

- `nfe_emissao._emissor_para(db, emitente_id)` — passa a receber **emitente_id** (não loja_id).
- `nfe_emissao.emitir(db, venda_ref, nota, tipo_documento="produto", emitente_id, …)` — grava
  `documento_fiscal` com `tipo_documento` + `emitente_id`; guarda de produção lê `Emitente.ambiente_ativo`.
- `mapa_fiscal.montar_nota(emitente, cliente, itens, ref, data)` — **emitente vem do `Emitente`** (cnpj,
  razão, IE, regime, endereço próprios) — não mais de `(perfil, loja)`.
- Endpoint `POST …/ciclo/15/emitir-nfe`: após o escopo/tenancy (a `loja` da venda), chama
  `emitente = resolver_emitente(db, loja, "produto")` (400 claro se não resolver), monta a nota com o
  `emitente`, e emite. `consultar`/`cancelar` resolvem o emitente por `documento_fiscal.emitente_id`.
- **Painel etapa 15:** mostra o **emitente** de cada documento (CNPJ/razão) além do status — deixa explícito
  quando o emitente ≠ loja vendedora.

## 6. Migração de dados (idempotente, em `_migrar_dados`/script)

1. Para cada `perfil_fiscal` existente: criar um `Emitente` com o CNPJ (da loja ou do `cert_cnpj`/`cnpj`) e
   todos os campos fiscais + tokens; **preencher o endereço do emitente** a partir da `Loja` correspondente.
2. `Loja.emitente_id` ← o Emitente criado (self).
3. `NfeEmissao` → `documento_fiscal`: `tipo_documento="produto"`, `emitente_id` = o Emitente da `loja_id`.
4. **INSPIRIUM (loja 1):** o `Emitente` recebe o **token de homologação já provisionado** (não reprovisionar)
   e o `Loja 1.emitente_id` aponta pra ele — o setup do smoke continua válido.
5. Guardas: só cria Emitente se ainda não existe para o CNPJ; renomeações via `ALTER TABLE RENAME`/cópia
   conforme o padrão de `_migrar_colunas`.

## 7. Testes

- **Unit `mod_fiscal`:** `resolver_emitente` cobre as 3 precedências (loja override, rede default, self) e o
  erro sem resolução; `resolver_plano` retorna 0/1/2 conforme mercadoria/serviço.
- **Unit `mapa_fiscal`:** `montar_nota` monta o emitente a partir de um `Emitente` (não da Loja) — atualizar
  os testes atuais (`test_mapa_fiscal`) para o novo contrato.
- **Modelo:** `Emitente`, `PerfilEmissao`, `documento_fiscal` (tipo+emitente) persistem; migração idempotente.
- **E2e etapa 15 (adaptar `test_nfe_etapa15_e2e`):** o seed cria um `Emitente` e liga `loja.emitente_id`;
  emitir resolve o emitente por `resolver_emitente(loja,"produto")`; **caso multi-CNPJ:** loja com
  `perfil_emissao(produto→Emitente_central)` emite sob o **CNPJ da central**, não o da loja (assertar
  `documento_fiscal.emitente_id` = central e o `cnpj_emitente` do payload).
- **Regressão:** `nfe_emissao`/`emissor_focus`/`focus_config` verdes; suíte total verde (baseline 532).

## 8. Fora de escopo

- **Emissão real da NFS-e de serviço (US-32)** — `EmissorFiscal.emitir_nfse_servico` segue
  `NotImplementedError`; o slot "serviço" já existe no plano/documento_fiscal.
- **UI de configuração do Perfil de Emissão** (associar loja/rede ↔ emitentes na tela) — frente própria.
- **Estoque/Financeiro** — não modelados aqui; apenas a diretriz de **não** rechavear por loja-vendedora
  (movimento/conciliação devem referenciar o emitente/documento, não presumir vendedor=emitente).
- Consolidar múltiplos documentos numa transação única de "faturar a venda" — o Plano é política; cada
  documento emite no seu momento do ciclo.
