# Subfases do Projeto Executivo (etapa 11) — Design

> Spec de design · 2026-07-04 · Orizon Manager | Dalmóbile
> Status: **IMPLEMENTADO (Sessão 45)** — branch `feat/pe-subfases`, backend com testes; frontend com verificação manual pendente no navegador.
> Frente: **A** (subfases de PE + monitoramento local). Dashboard entre projetos = frente futura.

## 1. Objetivo

Enriquecer as sub-etapas do **Projeto Executivo** (etapa `11`, sub-etapas `11a`–`11e`) para que
cumpram requisitos de **evolução, acompanhamento e monitoramento** do projeto: carregar documentos por
subfase, transições de fase nomeadas, um mecanismo de **revisão** com reabertura em cascata, e
visibilidade de status/histórico/documentos por subfase.

As sub-etapas já existem no `ETAPAS_CICLO` do frontend; esta frente **não renumera nada** — apenas
adiciona comportamento. O status e as datas de cada subfase já são gravados pelo `EtapaCiclo`
(`etapa_codigo` = `"11a"`…`"11e"`); esta frente **não duplica** status.

### Mapa das subfases

| Código | Nome | Carregar documento | Fechar (botão) | Revisão |
|---|---|---|---|---|
| `11a` | Planta de pontos de PE | "Carregar arquivo de medição" (`pe_planta_pontos`) | **"Encaminhar para PE"** | — |
| `11b` | Reunião de alinhamento | "Carregar relatório da reunião" (`pe_relatorio_alinhamento`) | **"Projeto Alinhado"** | ✔ |
| `11c` | Revisão de PE | "Carregar Projeto Executivo" (`pe_projeto_executivo`) | **"Concluído"** | ✔ |
| `11d` | Aprovação financeira II | *(inalterada — aprovação financeira existente)* | *(existente)* | — |
| `11e` | Aprovação do PE pelo cliente | "Carregar PE Assinado" (`pe_pe_assinado`) | **"Concluir Projeto Executivo"** | — |

## 2. Decisões (brainstorming)

- **Modelo de dados:** abordagem **B** — genérico, ancorado no ciclo (2 tabelas chaveadas por
  `(projeto, etapa_codigo)`), reusando o `EtapaCiclo` para status/datas. Estruturado e consultável
  (serve o monitoramento e o kanban futuro), reutilizável por outras fases.
- **Revisão:** **reabre em cascata** (subfase-alvo + posteriores do PE), via `codigos_a_resetar` já
  existente. Grava quem abriu + relatório complementar **obrigatório**. Autoridade: **senha gerencial**
  (Gerente de Vendas / Adm-Financeiro / Diretor) — a mesma do "reabrir em cascata" existente.
- **Executores das subfases** (uploads + fechar fase): capability **`executar_pe`** →
  **Projetista Executivo, Conferente, Gerente de Vendas, Gerente Adm/Financeiro** (Diretor herda por
  cima). Cada ação exige login+senha (padrão do Medidor na Medição). *(Assumi ambos os gerentes a partir
  de "Gerente"; confirmar na revisão se deve ser só um deles.)*
- **Ordem entre subfases:** mínima — todas destravam juntas (com a etapa 10 concluída); a guarda forte
  fica só no `11e` (exige `11a`–`11d` concluídas). Sem ordem estrita entre as intermediárias.
- **11a — fonte do arquivo:** upload **novo** e **separado** da planta de medição; a UI mostra um
  **link read-only** para a planta da etapa 10 por conveniência.
- **Integridade / registro evolutivo:** documentos **append-only** (cada upload = nova versão, nunca
  sobrescreve); arquivo de **medição inviolável** (o PE só lê/linka).
- **Escopo desta frente:** subfases + monitoramento **local** (por projeto). Dashboard entre projetos
  fica para depois.

## 3. Modelo de dados

Status e datas por subfase permanecem no **`EtapaCiclo`** existente. Duas tabelas novas:

### `ciclo_documentos` — documentos carregados numa subfase (append-only)
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | |
| `projeto_nome` | Text | escopo do projeto (`nome_safe`) |
| `etapa_codigo` | Text | `"11a"`, `"11b"`, `"11c"`, `"11e"` |
| `tipo` | Text | `pe_planta_pontos`, `pe_relatorio_alinhamento`, `pe_projeto_executivo`, `pe_pe_assinado`, `pe_relatorio_complementar` |
| `arquivo_path` | Text | caminho em `PROJETOS/<nome_safe>/ciclo/<etapa_codigo>/` |
| `nome_original` | Text | nome do arquivo enviado |
| `enviado_por_id` | Int | usuário que carregou |
| `enviado_em` | DateTime | quando |

Nunca há UPDATE/DELETE de linha: reenvio do mesmo `tipo` cria **nova linha** (versão). A "versão atual"
de um `tipo` é a de `enviado_em` mais recente.

### `ciclo_revisoes` — histórico de revisões (genérica; usada por 11b/11c)
| Campo | Tipo | Descrição |
|---|---|---|
| `id` | PK | |
| `projeto_nome` | Text | escopo |
| `etapa_codigo` | Text | subfase onde a revisão foi aberta |
| `aberta_por_id` | Int | gerente que abriu (senha gerencial) |
| `aberta_em` | DateTime | quando |
| `relatorio_doc_id` | Int (FK) | aponta para a linha em `ciclo_documentos` (`tipo=pe_relatorio_complementar`) |
| `motivo` | Text (nullable) | motivo opcional |

### Armazenamento em disco
- PE grava em `PROJETOS/<nome_safe>/ciclo/<etapa_codigo>/<uuid>_<nome_original>` — nome único garante
  append-only (nenhum overwrite).
- Medição permanece em `PROJETOS/<nome_safe>/medicao/` — **nenhum endpoint do PE escreve lá**.
- Arquivo gravado em disco **somente após** `db.commit()` bem-sucedido (padrão EP-07).

### Migração
`create_all` cria as duas tabelas novas. Aditivo, sem alterar tabelas existentes.

## 4. Backend — endpoints

Multipart, espelhando o `mod_medicao`. Toda ação audita em `log_acoes_gerenciais`.

| Ação | Endpoint | Valida | Efeito |
|---|---|---|---|
| Carregar documento | `POST /api/projetos/<nome>/ciclo/<codigo>/documento` | `executar_pe` + `arquivo` + `tipo` válido p/ o código | grava arquivo (uuid) + linha em `ciclo_documentos` |
| Concluir subfase | `POST /api/projetos/<nome>/ciclo/<codigo>/concluir` | `executar_pe` + **guarda de documento** (+ guarda 11e) | `EtapaCiclo` da subfase → concluído; no `11e`, conclui também a etapa `11` |
| Revisão | `POST /api/projetos/<nome>/ciclo/<codigo>/revisao` | **senha gerencial** + `arquivo` (relatório) | grava `ciclo_revisoes` + relatório; **reabertura em cascata** |
| Listar (GET) | `GET /api/projetos/<nome>/ciclo/pe` | logado + escopo do projeto | documentos (todas versões) + revisões + status por subfase |
| Baixar arquivo | `GET /api/projetos/<nome>/ciclo/documento/<id>` | logado + escopo do projeto | stream do arquivo (read-only) |

Lógica de negócio pura (guardas, "versão atual", cascade) fica em **`mod_ciclo.py`** (testável sem HTTP),
seguindo o padrão do projeto. A capability `executar_pe` entra em `perfis.py` (fonte única).

### Guardas de conclusão
- `11a` "Encaminhar para PE": exige documento `pe_planta_pontos`.
- `11b` "Projeto Alinhado": exige `pe_relatorio_alinhamento`.
- `11c` "Concluído": exige `pe_projeto_executivo`.
- `11e` "Concluir Projeto Executivo": exige `pe_pe_assinado` **e** `11a`–`11d` concluídas → conclui a
  subfase **e a etapa `11`**.

### Fluxo da Revisão (11b / 11c)
1. Gerente aciona "Revisão" → modal: senha gerencial + relatório complementar (obrigatório) + motivo.
2. Backend valida autoridade + arquivo → grava `ciclo_revisoes` + o relatório em `ciclo_documentos`.
3. **Reabertura em cascata** via `mod_ciclo.codigos_a_resetar(<codigo>, codigos_existentes)` — reabre a
   subfase-alvo e as posteriores do PE (`11d`/`11e` → pendente). Protegido por
   `reabertura_bloqueada_por_contrato` (não toca a etapa `7`).
4. Audita. O histórico de revisões passa a aparecer na subfase.

## 5. Frontend (`static/index.html`)

Painel por subfase na aba **Ciclo** (etapa 11): badge de status, lista de documentos (todas as versões
com download + data + quem), lista de revisões (quem/quando/relatório) para 11b/11c, e os botões
conforme capability (`executar_pe` para carregar/concluir; **Revisão** só gerente+).

Esboço do 11c:

```
┌ 11c · Revisão de PE ───────────────────── [em andamento] ┐
│ 📎 Projeto Executivo:  PE_v2.pdf  ·  12/07 14:20 · L.Dias │
│                        PE_v1.pdf  ·  10/07 09:05 · L.Dias │  ← versões (evolutivo)
│ 🔎 Revisões: 1 · aberta 11/07 por Ger. Marcelo (relatório)│
│ [ Carregar Projeto Executivo ]  [ Concluído ]  [ Revisão ]│
└──────────────────────────────────────────────────────────┘
```

**Indicador de progresso** no cabeçalho da etapa 11: `Projeto Executivo — 2/4 subfases concluídas` +
barra (conta 11a/11b/11c/11e). Em 11a, exibir link read-only para a planta da Medição (etapa 10).

## 6. Tratamento de erros

Mensagens claras, sem derrubar o app:

- Carregar sem arquivo → `400 "Anexe o arquivo."`
- Concluir sem o documento exigido → `400 "Carregue o [documento] antes de [ação]."`
- "Concluir Projeto Executivo" com 11a–11d pendentes → `400` listando o que falta.
- Revisão sem senha gerencial → `403`; sem relatório complementar → `400`.
- Capability incorreta → `403`; anônimo → `401`; projeto de outra loja → `404` (reusa escopo por projeto).
- Falha de gravação → nenhum arquivo órfão (commit antes do disco).

## 7. Testes

**Backend (pytest, TDD) — `tests/test_ciclo_pe.py`:**
- upload cria linha + arquivo; **append-only** (2 uploads do mesmo tipo → 2 versões, nenhuma sobrescrita);
- conclusão barrada sem o documento exigido;
- `11e` exige `11a`–`11d` concluídas **e** conclui a etapa `11`;
- **revisão reabre em cascata** (`11d`/`11e` → pendente) e exige gerente + relatório;
- **medição intocada** após o fluxo de PE (arquivo da etapa 10 inalterado);
- gates de capability (`403`/`401`) e isolamento cross-loja (`404`).
- Lógica pura de `mod_ciclo` (guardas, versão atual, cascade) testada sem HTTP.

**Frontend (manual — sem teste JS):** por perfil (Projetista/Conferente/Gerente veem os botões certos),
upload/conclusão/revisão, indicador de progresso; `node --check` no `<script>`.

## 8. Fora de escopo (frentes futuras)

- **Árvore de cada projeto** — visão hierárquica de documentos/fases por projeto. Consome
  `ciclo_documentos` + `EtapaCiclo`.
- **Dashboard por loja (kanban de fases)** — todos os projetos da loja distribuídos por colunas de fase,
  para monitoramento de carteira pelo gerente. Consome o status por etapa + agregações. Terá spec próprio.

O modelo B já nasce estruturado para alimentar ambas sem retrabalho.
