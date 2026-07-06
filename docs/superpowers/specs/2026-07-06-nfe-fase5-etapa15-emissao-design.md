# NF-e Fase 5 — Etapa 15 (Emissão da NF-e do cliente) — Design

> Spec de design · 2026-07-06 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Última peça: liga o pipeline (Fases 1-4) à etapa
> 15 do ciclo, por projeto, com painel no frontend. Backend e2e-testável (emissor mockado); painel manual.

## 1. Contexto e recorte

As Fases 1-4 montaram todo o pipeline (`mod_nfe.preview` → `mapa_fiscal` → `EmissorFocusNfe` →
`focus_client`, com `PerfilFiscal` e `nfe_emissao`), validado contra a Focus em homologação (payload
aceito; falta só habilitar o certificado do CNPJ). Esta fase entrega a **operação por projeto na etapa
15**: carregar a **NF-e da fábrica**, emitir a **NF-e da loja** (markup), acompanhar e baixar XML/DANFE —
com painel dedicado na etapa 15 do ciclo.

## 2. Decisões (brainstorming)

- **NF-e da fábrica entra na própria etapa 15** (upload append-only). A etapa 12 segue sendo os *pedidos
  enviados à fábrica* (`implantacao_pedido_xml`), sem relação com esta.
- **Markup por emissão** — campo no painel (com default), enviado no request. Não é config fixa.
- **Emissão restrita** a `editar_dados_loja` (fiscal: Gerente Adm/Fin, Diretor, admin_rede, super_admin) —
  mais restrito que as etapas operacionais 12-14 (cycle-gated). Vale para todos os endpoints fiscais da 15.
- **1:1** — uma NF-e da loja por XML da fábrica. `ref` **estável** `NFE-<projeto>-<fabrica_doc_id>` →
  idempotência (re-clicar "Emitir" numa nota autorizada devolve a guardada).
- **Conclusão automática:** ao **autorizar**, a etapa 15 fica `emitida` (status conclusivo).
- **Homologação:** o destinatário vai com o nome exigido pela SEFAZ — **"NF-E EMITIDA EM AMBIENTE DE
  HOMOLOGACAO - SEM VALOR FISCAL"** — aplicado automaticamente quando `ambiente_ativo == "homologacao"`
  (centralizado no `nfe_emissao.emitir`, beneficia também o `emitir-teste` da Fase 4).

## 3. Modelo de dados

- **`NfeEmissao.fabrica_doc_id`** (nova coluna, `Integer FK ciclo_documentos.id`, nullable) — liga a
  emissão ao XML da fábrica que a originou. Adicionada ao modelo (`create_all` cobre bancos novos) **+
  migração idempotente** em `database._run_migracoes` (`ALTER TABLE nfe_emissao ADD COLUMN fabrica_doc_id
  INTEGER` guardada por "coluna ausente", no padrão das migrações existentes) para o banco local/prod.

## 4. Backend — `nfe_emissao.py` (ajustes) + endpoints (`main.py`)

### 4.1 `nfe_emissao.emitir` — 2 ajustes
- Novo parâmetro `fabrica_doc_id=None`; gravado em `NfeEmissao.fabrica_doc_id` no upsert.
- **Regra de homologação:** após ler `ambiente`, se `ambiente == "homologacao"`, força
  `nota["destinatario"]["nome"] = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"` antes de
  emitir. (Não afeta produção.)

### 4.2 Endpoints (`/api/projetos/<nome>/ciclo/15/…`)
Gating comum: autenticado (401) → **`perfis.pode(nivel,"editar_dados_loja")`** (403) → escopo
(`escopo_operacional(ator)` + `_projeto_da_loja(db, nome, loja_id)` → 403/404).

- **`POST …/ciclo/15/nfe-fabrica`** (multipart) — upload append-only da NF-e da fábrica:
  `CicloDocumento(etapa_codigo="15", tipo="nfe_fabrica_xml", …)`; commit-antes-do-disco (padrão etapa 12).
  Resposta `{ok, documento_id}`.
- **`GET …/ciclo/15/nfe`** — estado do painel: `{ok, fabrica_xmls: [{id, nome_original, enviado_em,
  emissao: {ref,status,chave,numero,serie,mensagem_sefaz,erros,xml_doc_id,danfe_doc_id} | null}]}`.
  Junta `CicloDocumento(tipo=nfe_fabrica_xml)` com `NfeEmissao(fabrica_doc_id)`.
- **`POST …/ciclo/15/emitir-nfe`** (JSON `{fabrica_doc_id, markup_pct}`):
  carrega projeto→loja→`PerfilFiscal` (400 se ausente)→cliente (400 se ausente)→doc da fábrica (por id,
  escopado ao projeto/etapa/tipo; 400 se inválido). Lê o XML (`storage_ler_binario`) →
  `mod_nfe.preview(xml, markup_pct)`. `ref = "NFE-" + nome_safe + "-" + fabrica_doc_id`. `data_emissao`
  = agora ISO. `nota = mapa_fiscal.montar_nota(perfil, loja, cliente, preview["itens"], ref, data_emissao)`.
  `res = nfe_emissao.emitir(db, loja.id, nome_safe, nota, fabrica_doc_id=fabrica_doc_id)` (permitir_producao
  padrão False → só homologação por ora). Se `res.status == AUTORIZADO` →
  `_set_etapa_status(db, nome_safe, "15", "emitida", usuario_id)`. Resposta com `ref, status, chave,
  numero, serie, mensagem_sefaz, erros, xml_doc_id, danfe_doc_id`.
- **`POST …/ciclo/15/nfe/consultar`** (JSON `{ref}`) → `nfe_emissao.consultar` → resposta normalizada;
  se autorizar, também conclui a etapa 15.
- **`POST …/ciclo/15/nfe/cancelar`** (JSON `{ref, justificativa}`) → `nfe_emissao.cancelar`.

Erros: sem token no perfil / produção bloqueada / preview inválido → `ValueError` → 400; falha Focus →
500 (mensagem genérica, sem vazar segredo). Download do XML/DANFE reusa `GET …/ciclo/documento/<id>`.

## 5. Frontend — painel da etapa 15 (`static/index.html`)

Rotear a etapa 15 para um painel dedicado (como 12/13/14), via `GET …/ciclo/15/nfe`:
- **`_renderCardEmissaoNfe("15", dados, bloqueada)`**:
  - "Carregar NF-e da Fábrica" (`<input type=file accept=".xml">` → `enviarNfeFabrica`).
  - Lista dos XMLs da fábrica; por linha: nome + **markup %** (input, default) + botão **"Emitir NF-e da
    Loja"** (`emitirNfeLoja`). Se já emitida: badge de **status** (autorizado/processando/erro/cancelado)
    + **chave** + **baixar XML/DANFE** (links para `…/ciclo/documento/<id>`) + **Consultar**/**Cancelar**.
  - Botão de emitir/consultar/cancelar só aparece para quem tem `editar_dados_loja` (checagem UX-only via
    `_usuarioAtual.nivel`, como o `_podePE`; o backend é a trava real).
- Handlers: `enviarNfeFabrica`, `emitirNfeLoja`, `consultarNfeLoja`, `cancelarNfeLoja` (padrão `fetch` +
  `showToast`/`avisoPopup` + `carregarCiclo`). `esc()` em todo conteúdo dinâmico.

## 6. Testes

- **`tests/test_nfe_etapa15_e2e.py`** (emissor mockado via `monkeypatch.setattr(nfe_emissao,"_emissor_para",…)`
  → `FakeEmissor` que captura a `nota`; fixtures `app_db`/`seed`/`projetos_dir`; XML fixture
  `tests/fixtures/nfe/nfe_basica.xml`; usuário `gaf_l2`/diretor com `editar_dados_loja`, `cons_l1` sem):
  - upload `nfe-fabrica` → 200, aparece no `GET nfe` com `emissao: null`.
  - `emitir-nfe` → 200 `autorizado`; `NfeEmissao` com `fabrica_doc_id`; etapa 15 vira `emitida`; XML/DANFE
    gravados; `GET nfe` passa a mostrar a emissão. **Idempotência:** 2º `emitir-nfe` do mesmo doc não
    re-emite (mesmo `ref`).
  - **Homologação:** a `nota` capturada pelo fake tem `destinatario.nome ==` string SEFAZ.
  - `consultar`/`cancelar` atualizam.
  - **Permissão:** consultor → 403; sem perfil fiscal → 400; não autenticado → 401.
- **Modelo:** `NfeEmissao.fabrica_doc_id` persiste (estender o teste de modelo existente ou um novo).
- **Frontend:** sem teste JS — checagem estrutural (`node`/balanceamento) + **verificação manual no
  navegador** (pendente do usuário): upload da NF-e da fábrica, emitir, ver status/chave, baixar XML/DANFE,
  consultar/cancelar; etapa 15 conclui ao autorizar; botão de emitir só para perfil fiscal.

Suíte verde (`python3 -m pytest -q`, baseline 519).

## 7. Fora de escopo

- Emissão real em produção (permanece bloqueada; `permitir_producao` não é exposto na etapa 15 por ora).
- Refino fiscal por regime normal/presumido no `mapa_fiscal` (marcado `# TODO Fase 4`, com o contador).
- Correção do gap `cert_validade`/`cert_cnpj` read-only (Painel II) — independente.
- Consolidar vários XMLs da fábrica numa só NF-e (é 1:1 por decisão).
