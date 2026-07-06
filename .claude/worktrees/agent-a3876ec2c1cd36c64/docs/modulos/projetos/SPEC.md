# Módulo de Projetos — SPEC

**Status:** `[IMPLEMENTADO]` (parcial — ver [TODO])

---

## Visão geral

Gestão do ciclo de vida dos projetos, desde a criação até a aprovação e exportação para o Omie. Cada projeto está obrigatoriamente vinculado a um cliente.

---

## Ciclo de vida do projeto

```
Lead/Cliente cadastrado (Captação)
    → Projeto criado (vinculado ao cliente)
    → Briefing (obrigatório por projeto — ver "Briefing (por projeto)")
    → Ambientes carregados (XMLs do Promob)
    → Primeiro orçamento salvo (pode iterar)
    → Revisão de projeto
    → Orçamento aprovado pelo cliente (bloqueado) — conclui Revisão + Aprovação juntas
    → Contrato (geração + assinatura)
    → Aprovação financeira → Medição → Executivo → Produção → Logística → Pós-venda
```

> A ordem acima espelha o **ciclo de 20 etapas** (ver seção abaixo). Atenção: a
> ordem foi corrigida — hoje a **Criação do projeto vem antes do Briefing**
> (antes era o inverso).

---

## Ciclo de 20 etapas + gating sequencial

O projeto percorre um ciclo de **20 etapas principais** (algumas com sub-etapas),
persistido em `ciclo_etapas`. A ordem canônica, os nomes e as regras de gating
ficam centralizados no módulo **`mod_ciclo.py`** (fonte única da verdade no
backend; o `ETAPAS_CICLO` do frontend é alinhado a ela).

### Ordem das etapas

| Código | Etapa |
|---|---|
| 1 | Captação do cliente |
| 2 | Criação do projeto |
| 3 | Briefing |
| 4 | Primeiro orçamento |
| 5 | Revisão de projeto |
| 6 | Aprovação do orçamento pelo cliente |
| 7 | Contrato |
| 8 | Aprovação financeira I |
| 9 | Solicitação de medição |
| 10 | Planta de pontos medidos |
| 11 | Projeto executivo (sub-etapas 11a–11e) |
| 12 | Implantação do pedido |
| 13 | Produção |
| 14 | Entrega no depósito |
| 15 | Emissão da NFe do cliente |
| 16 | Entrega no cliente |
| 17 | Montagem (sub-etapa 17a) |
| 18 | Assistência pós Montagem |
| 19 | Vistoria final |
| 20 | Aprovação final |

> **Correção de ordem:** anteriormente a etapa 2 era *Briefing* e a 3 era
> *Criação do projeto*. A ordem foi **invertida** — agora 2 = Criação do projeto,
> 3 = Briefing. Os códigos acompanharam a posição (renumeração real, com
> migração de banco que troca `etapa_codigo` 2↔3 nas linhas existentes).

### Gating sequencial

Uma etapa **principal** só pode ser iniciada (`em_andamento`) ou concluída se a
principal **imediatamente anterior** estiver concluída:

- **Backend (camada rígida):** `PATCH /api/projetos/<nome>/ciclo/<codigo>`
  rejeita com **HTTP 400** qualquer tentativa de avançar uma etapa fora de
  ordem (mensagem: "Conclua a etapa anterior (<nome>) antes de iniciar esta.").
  Os endpoints de ação que avançam etapas (ex.: geração de contrato = etapa 7)
  também validam o gating antes de executar.
- **Frontend (camada visual):** etapas bloqueadas exibem 🔒, ficam não-expansíveis
  e têm ações/toggle desabilitados. Só a "etapa corrente" (primeira principal não
  concluída) mostra ações ativas.
- **Sub-etapas** (`11a–11e`, `17a`) **não** entram na cadeia de gating — são
  livres dentro do pai (etapa 11 / 17).
- **Etapa 1** (Captação) não tem anterior → sempre liberada.

Status que **contam como "concluída"** para fins de gating (`STATUS_CONCLUSIVOS`
em `mod_ciclo.py`): `concluido`, `aprovado`, `assinado`, `vigente`, `implantado`,
`realizado`, `entregue`, `emitida`.

### Marcação automática na criação do projeto

Ao criar um projeto:

- Etapa **1 (Captação)** e etapa **2 (Criação do projeto)** são marcadas
  **concluídas**.
- Etapa **3 (Briefing)** fica **pendente** e vira a "etapa corrente" (o Briefing
  é obrigatório por projeto — ver "Briefing (por projeto)"; **não** nasce
  concluído).

### Conclusões automáticas

- **Etapa 4 (Primeiro orçamento):** concluída automaticamente ao **salvar um
  orçamento com ≥1 ambiente** (vindo de XML do Promob).
- **Etapa 5 (Revisão de projeto):** **não tem toggle manual**. É concluída
  automaticamente pela aprovação do orçamento, junto com a etapa 6.
- **"Aprovar Orçamento"** conclui as etapas **5 e 6 juntas** e entra na **etapa 7
  (Contrato em `em_andamento`)**. O botão pós-aprovação leva ao card de
  assinatura do contrato (etapa 7).

### Reabertura em cascata (gerencial)

`POST /api/projetos/<nome>/ciclo/<codigo>/reabrir` (com `login` + `senha` de um
usuário de nível `gerente`, `diretor` ou `admin`) reabre a etapa-alvo **e todas
as posteriores** (voltam a `pendente`; sub-etapas dos pais afetados também são
resetadas). Características:

- **Auditado** na tabela `log_acoes_gerenciais`.
- **Bloqueado** se a cascata fosse desfazer um **contrato assinado/vigente**
  (etapa 7).
- Helpers de cascata em `mod_ciclo.py`: `codigos_a_resetar` e
  `reabertura_bloqueada_por_contrato`.

Existe ainda `POST /api/projetos/<nome>/ciclo/desfazer_aprovacao` (gerencial),
que **reseta as etapas 5/6/7** e devolve o contrato a rascunho — mantendo o
invariante "aprovação concluiu 5+6 → desfazer reabre 5+6+7".

### Helpers centrais (`mod_ciclo.py`)

- `ETAPAS_PRINCIPAIS` — ordem canônica das 20 etapas principais.
- `ETAPA_NOME` — nome de cada etapa por código.
- `etapa_anterior(codigo)` — código da principal anterior (ou `None`).
- `pode_avancar(codigo, status_por_codigo)` — regra de gating (sub-etapas sempre
  livres).
- `codigos_a_resetar(codigo_alvo, codigos_existentes)` — alvo + posteriores
  (para a cascata).

---

## Briefing (por projeto)

O **briefing é por-projeto** (não por-cliente). Cada projeto tem o seu próprio
briefing, mesmo quando vários projetos pertencem ao mesmo cliente.

### Modelo de dados
- A tabela `briefings` tem a coluna **`projeto_nome`** (`TEXT`, nullable). Um
  briefing pertence a **(cliente_id, projeto_nome)**.
- Briefings **legados** (criados antes da mudança) têm `projeto_nome IS NULL` e
  são ignorados pelo fluxo de projeto (viram informativos/legado).

### Campos obrigatórios
"Briefing OK" = os **5 campos obrigatórios** preenchidos
(`_BRIEFING_OBRIGATORIOS` em `main.py`); os demais campos são opcionais:

- `tipo_imovel`
- `budget_declarado`
- `categoria_proposta`
- `data_entrega_desejada`
- `flexibilidade_prazo`

### Endpoints
| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/projetos/<nome>/briefing` | Retorna o briefing daquele projeto (ou vazio/`completo:false`) |
| POST | `/api/projetos/<nome>/briefing` | Upsert do briefing daquele projeto; ao salvar com os obrigatórios preenchidos, marca a **etapa 3 (Briefing) só desse projeto** |

- O endpoint **legado** `GET/POST /api/clientes/<id>/briefing` permanece para a aba
  Clientes, mas **não marca mais a etapa 3** (a etapa 3 é responsabilidade do
  endpoint por-projeto).
- Helper testável: `_briefing_projeto_completo(nome_safe, db)` — `True` se o
  projeto tem briefing por-projeto com todos os obrigatórios preenchidos.

### Fluxo obrigatório
Depois de **criar o projeto**, o consultor é **obrigado a preencher o briefing
daquele projeto** antes de negociar. A criação do projeto **não** exige mais o
briefing antes (a ordem é 2 Criação → 3 Briefing); ao criar, o sistema abre o
briefing do projeto.

### Gate de negociação (backend)
Enquanto o briefing do projeto não estiver completo, o backend **bloqueia a
negociação** com **HTTP 400**:

- `POST /projetos/<nome>/orcamentos`
- `POST /projetos/<nome>/pool` (upload de XML)

Defesa em profundidade: o frontend também guia, mas o backend é a autoridade.
A aprovação do orçamento também exige o briefing **do projeto** completo (ver
módulo de Negociação — "Aprovação do orçamento").

---

## Status do projeto

| Status | Descrição | Transição |
|---|---|---|
| `negociacao` | Em negociação ativa | Salvar orçamento mantém aqui |
| `aprovado` | Orçamento aprovado e bloqueado | Aprovar orçamento |
| `exportado` | Enviado ao Omie | Exportar para Omie |
| `em_producao` | Em produção no CD | `[TODO]` |
| `entregue` | Entregue ao cliente | `[TODO]` |
| `concluido` | Pós-venda encerrado | `[TODO]` |

---

## Estrutura do projeto.json

```json
{
  "nome_safe": "apartamento_silva",
  "nome_projeto": "Apartamento Silva",
  "cliente": {
    "nome": "João Silva",
    "cpf": "123.456.789-00",
    "email": "joao@email.com",
    "telefone": "(12) 99999-9999"
  },
  "cliente_id": 1,
  "parceiro_id": null,
  "criado_em": "2026-06-07T10:00:00",
  "atualizado_em": "2026-06-08T15:30:00",
  "codigo_projeto_omie": null,
  "bloqueado": false,
  "margens": { ... },
  "forma_pagamento": null,
  "ambientes": [
    {
      "arquivo": "Cozinha.xml",
      "ambiente": "Cozinha",
      "total": 129328.40,
      "selecionado": true
    }
  ],
  "orcamentos": []
}
```

---

## Versões e revisões `[TODO]`

**Regras:**
- Cada revisão de projeto gera uma nova versão dos ambientes, mas não cria um novo projeto
- Log de alterações por versão (para auditoria)
- Para efeito de negociação, apenas a última versão é relevante
- O projeto pode ser particionado — cliente pode fechar parte dos ambientes agora e parte depois

---

## Particionamento de ambientes `[TODO]`

- Cliente pode selecionar quais ambientes fechar em cada orçamento
- Ambientes não fechados ficam disponíveis para negociações futuras
- Cada partição tem seu próprio status (aprovado, em produção etc.)

---

## Tela de Projetos (page-00)

**Implementado:**
- Lista de projetos com busca
- Formulário de novo projeto com seleção obrigatória de cliente
- Botão "+ Cadastrar novo cliente" com auto-seleção após cadastro

**[TODO]:**
- Ordenação por data de alteração (mais recente primeiro)
- Botão para inverter ordem
- Exibir data de última alteração em cada projeto
- Duplo clique no cliente abre projetos vinculados
- Botão "Novo ambiente" desabilitado nas telas de Clientes e Projetos

---

## Projetos antigos (sem cliente_id)

Projetos criados antes da implementação do vínculo com cliente têm `cliente_id = null`. O nome do cliente ainda está em `projeto.cliente.nome`. Não há impacto funcional — apenas o chip de cliente aparece vazio.

---

## Arquivos relevantes

- `mod_omie.py` — `_criar_projeto`, `_listar_projetos`, `_carregar_projeto`
- `mod_ciclo.py` — ordem canônica das etapas + helpers de gating (`ETAPAS_PRINCIPAIS`, `ETAPA_NOME`, `etapa_anterior`, `pode_avancar`, `codigos_a_resetar`, `reabertura_bloqueada_por_contrato`)
- `storage.py` — funções de persistência
- `main.py` — rotas `/projetos/*`, `PATCH /ciclo/<codigo>` (gating), `ciclo/<codigo>/reabrir` (cascata gerencial), `ciclo/desfazer_aprovacao`
- `static/index.html` — page-00 e funções `mostrarFormNovoProjeto`, `criarProjeto`; `ETAPAS_CICLO`/`ETAPAS_PRINCIPAIS`, `renderCiclo` (estado `bloqueado` + 🔒)

---

## User Stories

**US-PRJ-001** — Como consultor, quero criar um projeto vinculado a um cliente existente.

**US-PRJ-002** — Como consultor, quero carregar XMLs do Promob para adicionar ambientes ao projeto.

**US-PRJ-003** — Como consultor, quero salvar o orçamento e continuar editando depois.

**US-PRJ-004** — Como consultor, quero aprovar o orçamento para avançar para a exportação no Omie.

**US-PRJ-005** — Como consultor, quero ver a lista de projetos ordenada do mais recente para o mais antigo.

**US-PRJ-006** — Como consultor, quero fechar apenas parte dos ambientes de um projeto (particionamento). `[TODO]`
