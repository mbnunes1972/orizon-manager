# NF-e Fase 4 — Emissão real + acompanhamento (`nfe_emissao`) — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (Sessão 47)** — branch `feat/nfe-emissao`, `NfeEmissao` + `nfe_emissao.py` +
> endpoint `emitir-teste` com testes offline (suíte 518). **Smoke real em homologação pendente do token
> da Focus** (salvar no perfil da loja → painel Fiscal → Credenciais Focus). Emite a NF-e da loja em
> homologação, acompanha o status e guarda o XML/DANFE.

## 1. Contexto e recorte

As Fases 1-3b montaram o pipeline em código: `mod_nfe.preview` → `mapa_fiscal` (nota→payload) →
`EmissorFocusNfe` → `FocusClient`. Falta **emitir de verdade e persistir o resultado**. Esta fase entrega
o **serviço de emissão + acompanhamento + persistência**, testável offline (emissor mockado), e um
**endpoint mínimo de teste** para disparar uma emissão real em homologação assim que o token da Focus
estiver no `PerfilFiscal` da loja.

**Recorte (aprovado):**
- **Nesta fase:** modelo `NfeEmissao`, serviço `nfe_emissao.py` (`emitir`/`consultar`/`cancelar`,
  idempotente, **recusa produção por padrão**), e o endpoint `POST …/nfe/emitir-teste`. Testes offline
  com emissor mockado (nenhuma chamada real na suíte).
- **Fora (Fase 5):** UI da etapa 15 + orquestração puxando os XMLs já carregados na etapa 12 + UX
  completa. O endpoint de teste desta fase recebe o XML da fábrica direto (upload), como harness manual.

## 2. Decisões (brainstorming)

- **Persistência:** nova tabela **`NfeEmissao`** (rastreia `ref`→status→chave) + o XML/DANFE retornados
  guardados como **`CicloDocumento`** na etapa 15 (`tipo` `nfe_loja_xml`/`nfe_loja_danfe`), reusando o
  storage existente (`storage_salvar_binario` + `PROJETOS_DIR`, ambos em `storage.py`).
- **Gatilho do teste real:** **endpoint mínimo** `POST /api/admin/lojas/<id>/nfe/emitir-teste` (gated),
  que recebe o XML da fábrica + `projeto_nome` + `markup_pct`, monta a nota e emite.
- **Guarda de produção:** `emitir(...)` **recusa** emitir se o `ambiente_ativo` da loja for `producao`,
  a menos que receba `permitir_producao=True`. Dupla trava (além do painel).
- **Idempotência:** `ref` é único em `NfeEmissao`; se já existe `ref` **autorizada**, `emitir` devolve a
  guardada sem re-emitir.
- **Polling:** síncrono e limitado (`FocusClient.aguardar_processamento`, já da Fase 2). Webhook = futuro.

## 3. Modelo de dados — `NfeEmissao` (`database.py`)

Tabela nova (auto-criada por `create_all`).

```python
class NfeEmissao(Base):
    __tablename__ = "nfe_emissao"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    ref            = Column(Text, nullable=False, unique=True)   # idempotência (chave do cliente na Focus)
    projeto_nome   = Column(Text, nullable=True)                 # nome_safe (pode ser teste avulso)
    etapa_codigo   = Column(Text, default="15")
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    status         = Column(Text, nullable=True)                 # processando|autorizado|erro|cancelado|desconhecido
    chave_nfe      = Column(Text, nullable=True)
    numero         = Column(Text, nullable=True)
    serie          = Column(Text, nullable=True)
    mensagem_sefaz = Column(Text, nullable=True)
    erros_json     = Column(Text, nullable=True)                 # JSON dos erros da Focus (se houver)
    xml_doc_id     = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    danfe_doc_id   = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    emitido_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## 4. Serviço — `nfe_emissao.py`

Importa `EmissorFocusNfe` (Fase 3b), `mod_fiscal.focus_client_para_loja` (Sub-frente I),
`emissor_fiscal.StatusNota`, e `storage`/models. **Sem UI, sem rota** (o endpoint fica em `main.py`).

```python
def emitir(db, loja_id, projeto_nome, nota, permitir_producao=False, emissor=None) -> ResultadoEmissao:
    """Emite (ou devolve a emissão idempotente), acompanha até o status final e guarda XML/DANFE.
    - `nota`: dict de mapa_fiscal.montar_nota (tem `ref`).
    - Recusa produção (ambiente_ativo=='producao') salvo permitir_producao=True.
    - `emissor` injetável (testes); em produção usa focus_client_para_loja + EmissorFocusNfe."""

def consultar(db, ref, emissor=None) -> ResultadoEmissao:
    """Reconsulta o status na Focus e atualiza o NfeEmissao (baixa XML/DANFE se recém-autorizado)."""

def cancelar(db, ref, justificativa, emissor=None) -> ResultadoEmissao:
    """Cancela na Focus e atualiza o registro (status cancelado + guarda XML de cancelamento)."""
```

**Fluxo de `emitir`:**
1. `ref = nota["ref"]`. Se existe `NfeEmissao(ref)` com `status=="autorizado"` → devolve `_resultado(reg)`
   (idempotente, sem re-emitir).
2. Guarda de produção: lê `PerfilFiscal(loja_id).ambiente_ativo`; se `producao` e não `permitir_producao`
   → `raise ValueError("Emissão em produção bloqueada")`.
3. Se `emissor is None`: `emissor = EmissorFocusNfe(focus_client_para_loja(db, loja_id))`.
4. `res = emissor.emitir_nfe_produto(nota)`. Se `res.status == PROCESSANDO`:
   `res = resultado_de_focus(emissor.client.aguardar_processamento(ref))`.
5. Upsert `NfeEmissao` (ref, projeto_nome, loja_id, status, chave, numero, serie, mensagem_sefaz,
   erros_json). Se `AUTORIZADO`: baixa `res.xml_url`/`res.danfe_url` via `emissor.client.baixar(...)` e
   grava dois `CicloDocumento` (etapa 15), setando `xml_doc_id`/`danfe_doc_id`. `db.commit()`. Retorna `res`.

**Guardar documento** (helper interno):
`_guardar_doc(db, projeto_nome, tipo, caminho_focus, client)` → baixa bytes, gera nome único
(`AAAAMMDDHHMMSS_<uuid8>_<basename>`), `rel=ciclo/15/<unico>`, cria `CicloDocumento`, `db.flush()` (id),
`storage_salvar_binario(os.path.join(storage.PROJETOS_DIR, projeto_nome, rel), bytes)`; retorna o doc.
(Sem `projeto_nome` → não guarda documento, só o `NfeEmissao`.)

## 5. Endpoint de teste — `main.py`

`POST /api/admin/lojas/<id>/nfe/emitir-teste` (multipart), gated por `editar_dados_loja` + tenancy:
- Campos: `arquivo` (XML da fábrica), `projeto_nome` (da loja — para anexar os docs e o cliente),
  `markup_pct`.
- Fluxo: carrega `Loja` + `PerfilFiscal` (perfil) + `Projeto`(projeto_nome)→`Cliente`. Parseia o XML →
  `mod_nfe.preview(xml, markup_pct)`. `ref = "TESTE-" + <timestamp>_<uuid8>`.
  `nota = mapa_fiscal.montar_nota(perfil, loja, cliente, preview["itens"], ref, data_emissao=<now ISO>)`.
  `res = nfe_emissao.emitir(db, loja.id, projeto_nome, nota)` (permitir_producao=False → só homologação).
- Resposta: `{ok, ref, status, chave, numero, serie, mensagem_sefaz, xml_doc_id, danfe_doc_id, erros}`.
- Erros: sem token no perfil → `focus_client_para_loja` levanta `ValueError` → 400 com a mensagem;
  produção bloqueada → 400; falha de rede/Focus → 502/500 com mensagem (sem vazar segredo).

## 6. Segurança / cuidados

- Emissão só em **homologação** por padrão (guarda no serviço + o painel já barra ativar produção).
- Token nunca aparece (o serviço usa `focus_client_para_loja`, que decripta internamente; nada é logado).
- `esc()`/sanitização não se aplica (backend JSON); mensagens de erro genéricas em falhas de segredo.

## 7. Testes (offline — nenhuma chamada real)

- **`tests/test_nfe_emissao.py`** (emissor **fake** injetado, com `.client` fake que devolve
  processando→autorizado e bytes fake em `baixar`; `app_db` + fixtures):
  - `emitir` cria `NfeEmissao` com status `autorizado`, chave, e **dois `CicloDocumento`** (xml+danfe) na
    etapa 15 do projeto; os `*_doc_id` apontam para eles.
  - **Idempotência:** 2ª chamada com o mesmo `ref` (já autorizado) **não** re-emite (o fake não é chamado
    de novo) e devolve a guardada.
  - **Guarda de produção:** perfil com `ambiente_ativo="producao"` → `emitir` levanta `ValueError`;
    com `permitir_producao=True` → emite.
  - **Erro de autorização:** fake devolve `erro_autorizacao` → `NfeEmissao.status="erro"`, `erros_json`
    preenchido, **sem** documentos.
  - `consultar`/`cancelar` atualizam o registro.
- **`tests/test_nfe_emitir_teste_e2e.py`** (endpoint, com `nfe_emissao.focus_client_para_loja` ou o
  emissor **monkeypatched** para o fake): upload de um XML fixture (reusa `tests/fixtures/nfe/`) +
  projeto_nome do seed → 200 com `status` e `xml_doc_id`; sem perfil/token → erro claro; perm 403/401.

Suíte verde (`python3 -m pytest -q`, baseline 507).

- **Smoke real (manual, fora da suíte):** com o **token de homologação** salvo no perfil da loja (painel →
  Credenciais Focus) e um projeto com cliente, `POST …/nfe/emitir-teste` com um XML real da fábrica deve
  autorizar em homologação e guardar XML+DANFE. É o teste ponta-a-ponta que valida payload/fiscal.

## 8. Fora de escopo

- UI da etapa 15 + orquestração puxando os XMLs da etapa 12 + UX (Fase 5).
- Webhook de status (agora é polling síncrono).
- Regimes Normal/Presumido no `mapa_fiscal` (marcado `# TODO Fase 4` — refinar com o contador quando as
  notas de homologação apontarem os ajustes).
- Correção do gap `cert_validade`/`cert_cnpj` read-only (Sub-frente II) — independente.
