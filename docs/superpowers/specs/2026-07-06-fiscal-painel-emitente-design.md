# Fiscal — Painel de Config → Emitente (US-36) — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (branch `feat/fiscal-painel-emitente`, suíte 561)** — o Painel Fiscal passou a
> operar o **Emitente da loja** (`loja.emitente_id`, cria se faltar), com **endereço + CSOSN contribuinte**
> editáveis; `PerfilFiscal` (modelo + `focus_client_para_loja`) **removido** (tabela `perfil_fiscal` mantida
> como legado). **Gap de config divergente FECHADO** — editar o painel agora afeta a emissão.

## 1. Motivação

Depois do multi-CNPJ, a emissão resolve/lê o **`Emitente`** (via `loja.emitente_id`), mas os endpoints e a
aba **Fiscal** do admin (`GET/PUT …/perfil-fiscal`, `/segredos`, `/ambiente`) continuam em `PerfilFiscal(loja_id)`
— **divergentes**. Configurar pela tela não muda a emissão. US-36 retargeta o painel para o Emitente da loja.

## 2. Decisões (brainstorming)

- O painel edita o **Emitente próprio da loja** (`loja.emitente_id`); **cria um se a loja não tiver**.
- **Expor no painel os campos novos do Emitente:** **endereço** (logradouro/número/bairro/cidade/UF/CEP —
  fecha o gap do bairro vazio da INSPIRIUM) + **CSOSN contribuinte** (o não-contribuinte é `csosn_padrao`).
- **Aposentar `PerfilFiscal`:** remover o **modelo** + `focus_client_para_loja` + refs (código morto);
  **manter a tabela `perfil_fiscal`** no banco como legado (não dropar — dados já migrados para `emitente`).

## 3. Endpoints (`main.py`) — retarget `PerfilFiscal → Emitente`

URLs **mantidas** (mínimo churn no front): `GET/PUT /api/admin/lojas/<id>/perfil-fiscal`,
`PUT …/perfil-fiscal/segredos`, `PUT …/perfil-fiscal/ambiente`. Todos gated por `editar_dados_loja` + tenancy
(como hoje). A fonte passa a ser o Emitente da loja:

- **Resolver o emitente:** `em = db.get(Emitente, loja.emitente_id) if loja.emitente_id else None`.
- **GET:** se `em` existe → devolve seus campos (config + `token_homolog_definido`/`token_prod_definido`
  bools, **nunca** os tokens) + `placeholders_json` + `ambiente_ativo`. Se não existe → devolve os **defaults**
  (de `mod_fiscal.emitente_padrao_teste`) sem criar (igual ao comportamento atual).
- **PUT config:** se `em` é None → **cria** um `Emitente` (defaults) e seta `loja.emitente_id`. Aplica a
  **allowlist** de campos ao Emitente. Allowlist = a atual + **novos**: `logradouro, numero, bairro, cidade,
  uf, cep, csosn_contribuinte` (e incluir `cert_validade`/`cert_cnpj`, hoje fora da allowlist — mini-gap).
- **PUT segredos:** cria o Emitente se necessário; grava `focus_token_homolog_enc`/`prod_enc` (cifrados
  `fiscal_cripto.encrypt`, write-only — mantém se vier vazio).
- **PUT ambiente:** troca `Emitente.ambiente_ativo`; a guarda de produção (`mod_fiscal.pode_ativar_producao`:
  placeholders vazios **e** token de produção definido) permanece.

## 4. Painel (aba Fiscal — `static/index.html`)

`adminFiscalCarregar/Salvar/SalvarSegredos/AtivarAmbiente` **mantêm as URLs**; o form ganha os campos novos:
- **Seção Endereço do Emitente:** logradouro, número, bairro, cidade, UF, CEP.
- **CSOSN contribuinte** (junto do `csosn_padrao`, rotulado como "CSOSN não-contribuinte").
Os placeholders/badges de confirmação continuam funcionando (o `placeholders_json` do Emitente dirige os badges).

## 5. `mod_fiscal.py` + limpeza do `PerfilFiscal`

- **Remover** `focus_client_para_loja` (morto — a emissão usa `focus_client_para_emitente`).
- **`perfil_padrao_teste` → `emitente_padrao_teste`** (ou reaproveitar): retorna os defaults de um Emitente
  novo — `regime_tributario="simples"`, `csosn_padrao="102"` (não-contrib), `csosn_contribuinte="101"`,
  `cfop 5102/6102`, `cnae`/`iss` placeholders, `ambiente_ativo="homologacao"`, `placeholders` (lista de campos
  defaultados p/ os badges). `pode_ativar_producao`/`validar_config`/`REGIMES`/`PAPEIS`/`AMBIENTES` **ficam**.
- **`database.py`:** remover a classe `PerfilFiscal` (e do import em `main.py`). **NÃO** dropar a tabela
  `perfil_fiscal` (fica legado; `create_all` não a recria nem remove).
- **`emissor_focus.py`:** só um docstring cita `focus_client_para_loja` — atualizar para `_para_emitente`.

## 6. Testes

- **`tests/test_perfil_fiscal_e2e.py` / `test_perfil_fiscal_model.py`:** migrar para o **Emitente** — o painel
  cria/edita o Emitente da loja; GET nunca vaza token; PUT config aplica os campos (incl. endereço +
  csosn_contribuinte); segredos write-only; ambiente com a guarda de produção. (Renomear os arquivos para
  `test_painel_emitente_*` se fizer sentido.)
- **`tests/test_mod_fiscal.py`:** ajustar para `emitente_padrao_teste` (defaults) + remover o teste de
  `focus_client_para_loja`.
- Demais testes fiscais que citam `PerfilFiscal` (nos `_perfil` helpers) já usam o Emitente do seed
  (frentes anteriores) — confirmar que nada quebra ao remover o modelo.
- Suíte verde (baseline 562).

## 7. Fora de escopo

- **UI do Perfil de Emissão** (associar loja/rede ↔ emitentes; produto→X, serviço→Y) — é a **US-37**, própria.
- Dropar a tabela `perfil_fiscal` (fica legado).
- Edição do Emitente **central da rede** por um admin de rede (o painel aqui é o Emitente **da loja**).
