# Fiscal — UI do Perfil de Emissão (US-37) — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Fecha a configuração multi-CNPJ pela tela:
> **painel Fiscal da rede** (Emitente central) + **Perfil de Emissão em 2 níveis** (default da rede + override
> da loja). O motor (`Emitente`, `PerfilEmissao`, `resolver_emitente`) já existe; falta a UI/config.

## 1. Motivação

O multi-CNPJ resolve o emitente por documento (`resolver_emitente`: **override loja → default rede → self**),
mas **não há tela** para (a) configurar o **Emitente central da rede** e (b) definir **qual Emitente assina
produto e qual assina serviço**. Hoje só dá para editar o Emitente *self* da loja (US-36). US-37 entrega a
config que realiza a topologia (avulsa self-self; Orizon produto→central/serviço→loja; parceira produto→rede).

## 2. Decisões (brainstorming)

- **Painel Fiscal da REDE**: configura o `rede.emitente_central_id` (cria se faltar), **reusando** a lógica
  do painel Fiscal da loja (US-36), retargetada para a rede.
- **Perfil de Emissão em 2 níveis**: **default da rede** (`PerfilEmissao owner="rede"`) que as lojas herdam +
  **override da loja** (`owner="loja"`). Reflete o resolver (loja → rede → self).

## 3. Backend

### 3.1 Painel Fiscal da rede (Emitente central) — espelho da loja
Generalizar a lógica do painel da US-36 num **helper** que recebe o *dono* e resolve o Emitente:
`_emitente_do_dono(db, kind, obj)` → `db.get(Emitente, obj.emitente_id)` (loja) ou
`db.get(Emitente, obj.emitente_central_id)` (rede); cria+linka se faltar.
Novos endpoints (mesma semântica dos da loja — GET nunca vaza token; PUT allowlist; segredos write-only;
ambiente com guarda de produção):
- `GET/PUT /api/admin/redes/<id>/perfil-fiscal`
- `PUT /api/admin/redes/<id>/perfil-fiscal/segredos`
- `PUT /api/admin/redes/<id>/perfil-fiscal/ambiente`
**Gate:** `perfis.pode(nivel, "gerir_lojas")` + tenancy (super_admin: qualquer rede; admin_rede: só a sua
`ator.rede_id == id`). Os endpoints da **loja** seguem gated por `editar_dados_loja` (US-36, inalterados).

### 3.2 Perfil de Emissão (política doc→emitente)
- `GET/PUT /api/admin/redes/<id>/perfil-emissao` — **default da rede**.
- `GET/PUT /api/admin/lojas/<id>/perfil-emissao` — **override da loja**.
- **PUT** corpo `{ "produto": <emitente_id|null>, "servico": <emitente_id|null> }`: para cada tipo, faz
  **upsert** de `PerfilEmissao(owner_tipo, owner_id, tipo_doc, emitente_id)` quando `emitente_id` != null, ou
  **delete** da linha quando `null` (= sem regra → herda/self). Valida que `emitente_id` é uma opção válida
  (self/central).
- **GET** retorna `{ "produto": <emitente_id|null>, "servico": <emitente_id|null>, "opcoes": [ {id, label,
  papel} ] }` — as **opções de emitente** para popular os selects:
  - **loja:** `self` (`loja.emitente_id`, label "Este CNPJ — <razão/cnpj>") + `central` (se `loja.rede_id` e
    `rede.emitente_central_id`, label "Central da rede — <razão/cnpj>"). `null` = "Herdar da rede".
  - **rede:** `central` (o próprio `emitente_central_id`). `null` no default = "A própria loja (self)".
- **Gate:** rede → `gerir_lojas` + tenancy; loja → `editar_dados_loja`.

## 4. Frontend (`static/index.html`)

### 4.1 Painel Fiscal da rede
Reusar `adminFiscalCarregar/Salvar/SalvarSegredos/AtivarAmbiente` **parametrizando** o *dono* (base URL
`…/lojas/<id>` vs `…/redes/<id>`), para exibir a config do Emitente central quando uma **rede** está
selecionada no admin (nível rede). Se não houver um "detalhe de rede" com abas, criar uma seção **Fiscal da
rede** no cabeçalho/painel do nível rede.

### 4.2 Perfil de Emissão
- **Na aba Fiscal da loja:** seção **"Perfil de Emissão (esta loja)"** — 2 selects **Produto**/**Serviço**,
  opções `[Herdar da rede · Este CNPJ (self) · Central da rede]` (das `opcoes` do GET). Salvar → PUT
  `…/lojas/<id>/perfil-emissao`.
- **No painel Fiscal da rede:** seção **"Perfil de Emissão (default da rede)"** — 2 selects, opções
  `[A própria loja (self) · Central da rede]`. Salvar → PUT `…/redes/<id>/perfil-emissao`.
`esc()` no dinâmico; feedback com `showToast`.

## 5. Testes

- **e2e** (`tests/`): PUT `redes/<id>/perfil-emissao {produto: central}` → GET reflete + `opcoes` presentes;
  PUT `lojas/<id>/perfil-emissao {produto: self}` (override) → GET reflete; **resolução ponta a ponta**:
  reusar/estender o multi-CNPJ e2e para provar que **override da loja vence default da rede vence self**
  (emitir e conferir `DocumentoFiscal.emitente_id`). Painel Fiscal da rede: e2e do GET/PUT (cria o central,
  não vaza token) — reaproveitar os testes de painel da loja parametrizados.
- **Gate:** admin_rede só a sua rede (403 em rede alheia); consultor 403; não autenticado 401.
- Suíte verde (baseline 561).

## 6. Fora de escopo

- **Emitentes arbitrários** além de self/central (um gerenciador/lista geral de CNPJs emitentes) — futuro.
- **NFS-e de serviço** (emissão real — US-38).
- Edição de qual loja pertence a qual rede (tenancy existente).
