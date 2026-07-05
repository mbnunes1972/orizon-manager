# Etapas operacionais 12/13/14 (Implantação · Produção · Entrega no depósito) — Design

> Spec de design · 2026-07-05 · Orizon Manager | Dalmóbile
> Status: **APROVADO (brainstorming)** — a implementar. Segue o padrão das subfases do PE (Sessão 45).
> Frente: enriquecer as etapas operacionais pós-PE com ações/botões próprios.

## 1. Objetivo

Dar às etapas principais **12 (Implantação do pedido)**, **13 (Produção)** e **14 (Entrega no
depósito)** ações concretas no lugar do card genérico (que hoje só tem textarea de observações +
"Marcar como Concluída"). Nenhuma renumeração de etapa; o status/datas continuam no `CicloEtapa`.

A integração real com a fábrica é **frente futura** — por ora "Encaminhar Pedidos à Fábrica" apenas
fecha a etapa 12. Os números dos pedidos são **resultado da implantação na fábrica** e por isso são
registrados na etapa **13 (Produção)**, não na 12.

### Mapa das ações

| Código | Nome | Ações | Fecha a etapa (botão) | Guarda de conclusão |
|---|---|---|---|---|
| `12` | Implantação do pedido | **"Carregar Pedidos"** (upload de XMLs, append-only) | **"Encaminhar Pedidos à Fábrica"** | exige **≥ 1 XML** carregado |
| `13` | Produção | **"Inserir Números dos Pedidos"** (lista, texto) | **"Produção Concluída"** | exige **≥ 1 número** informado |
| `14` | Entrega no depósito | **"Carregar Relatório de Entrega"** (texto livre, faltas/avarias) | **"Concluir Relatório de Entrega"** | exige **relatório não-vazio** |

## 2. Decisões (brainstorming)

- **Arquitetura:** abordagem **C** — máximo reúso, superfície nova mínima, **PE intocado**. Reusa o
  `PATCH /ciclo/<codigo>` existente para conclusão e para gravar texto (`observacoes`); um único
  endpoint novo para o upload dos XMLs; guardas específicas em `mod_ciclo`.
- **Carregar Pedidos (12):** **upload de arquivos** `.xml` (append-only), sem parsing/validação de
  conteúdo por ora — apenas armazenar para o envio futuro à fábrica. Reusa `CicloDocumento`.
- **Números dos Pedidos (13):** **lista** de números (um por linha) informada na etapa **Produção**,
  pois são devolvidos pela fábrica após a implantação. Gravados em `CicloEtapa("13").observacoes`.
- **Relatório de Entrega (14):** **campo de texto livre** editado no sistema (faltas e avarias).
  Gravado em `CicloEtapa("14").observacoes`. Concluir exige o relatório preenchido (não-vazio).
- **Permissões:** **reusar o gating atual do ciclo** — qualquer usuário autenticado no escopo
  operacional da loja que já pode avançar o ciclo executa essas ações. **Sem nova capability** (ao
  contrário do PE, que exige `executar_pe`/`revisar_pe`).
- **Dados:** **nenhuma tabela nova.** XMLs em `CicloDocumento`; números e relatório em
  `CicloEtapa.observacoes` (uma etapa = um blob de texto, semanticamente próprio de cada etapa).

## 3. Modelo de dados

Sem migração de schema. Reúso:

- **`CicloDocumento`** (já existe, append-only) para os XMLs da etapa 12:
  - `etapa_codigo = "12"`, `tipo = "implantacao_pedido_xml"`.
  - `arquivo_path = ciclo/12/<AAAAMMDDHHMMSS>_<uuid8>_<nome_original>` (mesmo padrão do PE).
- **`CicloEtapa.observacoes`**:
  - etapa `"13"`: números dos pedidos (texto, um número por linha).
  - etapa `"14"`: relatório de entrega (texto livre).

> Nota: o card genérico usa `observacoes` como "observações" livres. As etapas 13/14 passam a ter
> **painel dedicado** (deixam de usar o card genérico), então `observacoes` dessas etapas fica com o
> significado específico acima — sem conflito de UI.

## 4. Backend

### 4.1 `mod_ciclo.py`

- Registro das etapas operacionais enriquecidas:

  ```python
  ETAPAS_OPERACIONAIS = {
      "12": {"nome": "Implantação do pedido", "exige": "xml",
             "tipo_doc": "implantacao_pedido_xml", "botao": "Encaminhar Pedidos à Fábrica"},
      "13": {"nome": "Produção",              "exige": "numeros",
             "botao": "Produção Concluída"},
      "14": {"nome": "Entrega no depósito",   "exige": "relatorio",
             "botao": "Concluir Relatório de Entrega"},
  }
  ```

- `tipo_doc_operacional(codigo)` → `"implantacao_pedido_xml"` para `"12"`, senão `None`.
- `guarda_conclusao_operacional(codigo, tem_xml, numeros_txt, relatorio_txt)` → `(ok, erro)`:
  - `"12"`: `tem_xml` verdadeiro, senão *"Carregue pelo menos um pedido (XML) antes de encaminhar à
    fábrica."*
  - `"13"`: `numeros_txt` com ao menos uma linha não-vazia, senão *"Informe os números dos pedidos
    antes de concluir a produção."*
  - `"14"`: `relatorio_txt` não-vazio (após `strip`), senão *"Preencha o Relatório de Entrega antes de
    concluí-lo."*
  - código fora do registro → `(False, "Etapa operacional desconhecida.")`.

Testável puro, sem I/O (mesma filosofia de `guarda_conclusao` do PE).

### 4.2 `main.py`

- **`POST /api/projetos/<nome>/ciclo/12/pedido-xml`** (multipart, append-only, **cycle-gated**):
  - autenticação + `escopo_operacional` + `_projeto_da_loja` (mesmo preâmbulo do upload do PE), **mas
    sem** `_usuario_com_capacidade("executar_pe")` — usa o usuário da sessão.
  - aceita o campo `arquivo` (um por request; o frontend envia múltiplos sequencialmente para manter
    o append-only e reusar a mesma rota).
  - grava `CicloDocumento(tipo="implantacao_pedido_xml", etapa_codigo="12", …)`; ao 1º arquivo, se a
    etapa está `pendente`, marca `em_andamento`; `LogAcaoGerencial(acao="implantacao_pedido_xml")`;
    persiste no disco via `storage_salvar_binario` (commit-antes-do-disco, padrão EP-07).
  - responde `{ok, documento_id}`.
- **`GET /api/projetos/<nome>/ciclo/12/pedido-xml`** → lista os `CicloDocumento` da etapa 12
  (`id`, `nome_original`, `enviado_em`, `enviado_por`) para o painel. Download reusa o
  **`GET /ciclo/documento/<id>`** já existente.
- **Conclusão e salvar texto reusam o `PATCH /ciclo/<codigo>` existente**, com um acréscimo:
  - Ao concluir (`status ∈ STATUS_CONCLUSIVOS`) uma etapa em `ETAPAS_OPERACIONAIS`, antes de gravar,
    aplicar `guarda_conclusao_operacional` — carregando `tem_xml` (existe `CicloDocumento` da 12),
    `numeros_txt` (`CicloEtapa("13").observacoes`) e `relatorio_txt` (`CicloEtapa("14").observacoes`).
    Se a guarda falhar → `400` com a mensagem.
  - Salvar números (13) / relatório (14) usa o mesmo `PATCH` com `{observacoes: "..."}` **sem**
    `status` (o handler já grava `observacoes` quando presente e não força conclusão).
  - O gating sequencial (`pode_avancar`) e a reabertura em cascata **permanecem intactos**.

## 5. Frontend (`static/index.html`)

No laço de render das etapas (`for etapa of ETAPAS_CICLO`), rotear 12/13/14 para painéis dedicados
(análogo ao `PE_SUBFASES[...] ? _renderCardPE(...)`), antes do `_renderCardGenerico`:

- **`_renderCardImplantacao("12", dados, bloqueada)`** — lista de XMLs carregados (nome + data +
  link de download), botão **"Carregar Pedidos"** (`<input type=file accept=".xml" multiple>` →
  `enviarPedidosXml`, upload sequencial + refresh), e botão **"Encaminhar Pedidos à Fábrica"**
  (desabilitado sem XML; `PATCH status=concluido`; se `!ok`, `avisoPopup`). Estado concluído mostra
  ✓ + data e o botão "Reabrir (gerente)" já existente para principais.
- **`_renderCardProducao("13", dados, bloqueada)`** — textarea dos números (carrega de
  `dados.observacoes`), botão **"Salvar Números dos Pedidos"** (`PATCH observacoes`), e botão
  **"Produção Concluída"** (desabilitado sem números; `PATCH status=concluido`).
- **`_renderCardEntrega("14", dados, bloqueada)`** — textarea do relatório de faltas/avarias
  (carrega de `dados.observacoes`), botão **"Salvar Relatório de Entrega"** (`PATCH observacoes`), e
  botão **"Concluir Relatório de Entrega"** (desabilitado sem texto; `PATCH status=concluido`).

Handlers reusam `fetch` com `credentials:'same-origin'`, `showToast`/`avisoPopup` e `carregarCiclo()`
para atualizar. `esc()` em todo conteúdo dinâmico (nome de arquivo, texto) — já endurecido na Sessão 45.

Observação: a etapa 14 tinha `toggleavel:true` no `ETAPAS_CICLO`; com o painel dedicado ela deixa de
usar o toggle genérico (a conclusão passa pelo botão nomeado). Remover `toggleavel` da 14 ou apenas
não renderizar o card genérico para ela (o roteamento já garante isso).

## 6. Testes

- **Lógica pura** (`tests/test_ciclo.py`): `guarda_conclusao_operacional` para 12/13/14 (casos ok e
  falha de cada guarda) + `tipo_doc_operacional`.
- **E2E HTTP** (`tests/test_ciclo_operacional_e2e.py`):
  - upload de XML na 12 (append-only: 2 uploads → 2 documentos; download OK).
  - **12** não conclui sem XML (`400`); conclui com XML.
  - **13** não conclui sem números (`400`); salvar números via `PATCH observacoes`; conclui com números.
  - **14** não conclui com relatório vazio (`400`); salvar relatório; conclui.
  - **gating sequencial preservado:** 13 não avança sem 12 concluída; 14 sem 13.
  - **permissão cycle-gated:** usuário operacional comum consegue (sem exigir `executar_pe`); não
    autenticado → `401`.
  - **PE intocado:** as rotas/guardas do PE seguem inalteradas (smoke de uma conclusão de subfase PE).

Suíte deve seguir verde (`python3 -m pytest -q`).

## 7. Fora de escopo (YAGNI)

- Integração real com a fábrica (envio dos XMLs, retorno automático dos números) — frente futura; o
  botão "Encaminhar à Fábrica" só fecha a etapa por ora.
- Parsing/validação do conteúdo dos XMLs.
- Relatório de entrega estruturado (itens falta/avaria com quantidade) — decidido texto livre.
- Nova capability/perfil para as etapas operacionais — decidido reusar o gating do ciclo.
