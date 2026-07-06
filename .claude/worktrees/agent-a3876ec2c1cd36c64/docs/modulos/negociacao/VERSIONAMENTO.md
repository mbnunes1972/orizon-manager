# SPEC — Versionamento de Orçamentos

> Status: `[PLANEJADO]` — implementar na v0.2.0  
> Módulo: Negociação  
> Histórias: US-20 a US-26  
> Arquivos impactados: `database.py`, `main.py`, `mod_omie.py`, `static/index.html`

---

## 1. Modelo de dados

### Visão geral das entidades

```
projetos
 └── pool_ambientes        (todos os XMLs carregados — permanente)
 └── orcamentos            (versões paralelas de negociação)
      └── orcamento_ambientes  (quais ambientes estão em cada orçamento)
```

---

### Schema — tabela `pool_ambientes`

```sql
CREATE TABLE pool_ambientes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id      TEXT NOT NULL REFERENCES projetos(id),
    nome            TEXT NOT NULL,
    versao          INTEGER DEFAULT 1,
    nome_exibicao   TEXT NOT NULL,
    xml_path        TEXT NOT NULL,
    ambientes_json  TEXT NOT NULL,
    budget_total    REAL NOT NULL,
    order_total     REAL NOT NULL,
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

> Um ambiente do pool nunca é deletado. Ao sobrescrever, o registro existente é atualizado. Ao criar nova versão, um novo registro é inserido com `versao + 1`.

---

### Schema — tabela `orcamentos`

```sql
CREATE TABLE orcamentos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id      TEXT NOT NULL REFERENCES projetos(id),
    nome            TEXT NOT NULL DEFAULT 'Orçamento 1',
    ordem           INTEGER NOT NULL DEFAULT 1,
    margens         TEXT,
    desconto_pct    REAL DEFAULT 0.0,
    forma_pagamento TEXT,
    valor_total     REAL DEFAULT 0.0,
    valor_liquido   REAL DEFAULT 0.0,
    created_by      INTEGER REFERENCES users(id),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME
);
```

---

### Schema — tabela `orcamento_ambientes`

```sql
CREATE TABLE orcamento_ambientes (
    orcamento_id        INTEGER NOT NULL REFERENCES orcamentos(id),
    pool_ambiente_id    INTEGER NOT NULL REFERENCES pool_ambientes(id),
    ordem               INTEGER DEFAULT 1,
    added_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (orcamento_id, pool_ambiente_id)
);
```

---

## 2. Regras de negócio

### Criação de projeto
- Ao criar um projeto → sistema cria automaticamente **Orçamento 1** (nome padrão, sem ambientes)
- Pool de ambientes começa vazio

### Carregamento de XML

```
1. Extrair nome base do arquivo (sem extensão)
2. Buscar no pool_ambientes do projeto por nome = nome_base
3. Se NÃO existe → inserir no pool (versao=1, nome_exibicao=nome_base)
4. Se JÁ existe → perguntar:
     [Sobrescrever]  [Nova versão]  [Cancelar]
```

**Se Sobrescrever:**
- Atualiza registro existente no pool (xml_path, ambientes_json, budget_total, order_total)
- Todos os orçamentos que referenciam esse ambiente são recalculados automaticamente

**Se Nova versão:**
- Insere novo registro com `versao = versao_atual + 1`
- `nome_exibicao = "Cozinha_v1"`, `"Cozinha_v2"`, etc.
- Orçamentos existentes não são alterados
- Novo ambiente fica disponível no painel para adição manual

### Painel de Ambientes

Botão **"Ambientes"** na tela de negociação abre painel com todos os ambientes do pool:

- ✅ **Incluído** — está neste orçamento (desmarcável com confirmação)
- ⬜ **Disponível** — no pool mas não neste orçamento (marcável)

**Ao marcar:** insere em `orcamento_ambientes`, recalcula totais  
**Ao desmarcar:** modal *"Retirar 'X' deste orçamento?"* → Sim remove, Não cancela

### Múltiplos orçamentos
- Botão **"Novo orçamento"** na tela do projeto → modal pedindo nome → orçamento vazio criado
- Todos os orçamentos editáveis em paralelo
- Orçamentos não podem ser deletados

### Renomear orçamento
- Clique no nome → campo de texto inline → salvo ao perder o foco

---

## 3. Rotas HTTP

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/projetos` | Criar projeto (já cria Orçamento 1) |
| `GET` | `/projetos/<id>/orcamentos` | Listar orçamentos do projeto |
| `POST` | `/projetos/<id>/orcamentos` | Criar novo orçamento |
| `PUT` | `/projetos/<id>/orcamentos/<oid>` | Atualizar nome, margens, desconto, forma pagamento |
| `GET` | `/projetos/<id>/pool` | Listar ambientes do pool |
| `POST` | `/projetos/<id>/pool` | Carregar XML (com detecção de duplicata) |
| `POST` | `/projetos/<id>/pool/<pid>/sobrescrever` | Confirmar sobrescrita |
| `POST` | `/projetos/<id>/pool/<pid>/nova-versao` | Confirmar nova versão |
| `GET` | `/orcamentos/<oid>/ambientes` | Listar ambientes do orçamento |
| `POST` | `/orcamentos/<oid>/ambientes/<pid>` | Adicionar ambiente |
| `DELETE` | `/orcamentos/<oid>/ambientes/<pid>` | Remover ambiente |

---

## 4. Payloads principais

### POST `/projetos/<id>/pool` — duplicata detectada

```json
// Response 200
{
  "ok": true,
  "acao": "duplicata",
  "ambiente_existente": {
    "id": 2,
    "nome_exibicao": "Cozinha",
    "versao": 1,
    "orcamentos_afetados": 2
  },
  "mensagem": "O ambiente 'Cozinha' já existe neste projeto."
}
```

### GET `/projetos/<id>/orcamentos`

```json
{
  "ok": true,
  "orcamentos": [
    {
      "id": 1, "nome": "Completo", "ordem": 1,
      "desconto_pct": 5.0, "valor_total": 58000.00, "valor_liquido": 44000.00,
      "ambientes": [
        { "id": 1, "nome_exibicao": "Quarto Master", "budget_total": 22000.00 },
        { "id": 2, "nome_exibicao": "Cozinha",       "budget_total": 32500.00 }
      ]
    },
    {
      "id": 2, "nome": "Entrada", "ordem": 2,
      "desconto_pct": 10.0, "valor_total": 32000.00, "valor_liquido": 23000.00,
      "ambientes": [
        { "id": 2, "nome_exibicao": "Cozinha",    "budget_total": 32500.00 },
        { "id": 3, "nome_exibicao": "Lavanderia", "budget_total": 8200.00  }
      ]
    }
  ]
}
```

---

## 5. Interface

### Tela do projeto

```
┌─────────────────────────────────────────────┐
│ Projeto: Casa dos Rodrigues                  │
│                                              │
│  [Completo   R$58.000  3 ambientes] [Abrir] │
│  [Entrada    R$32.000  2 ambientes] [Abrir] │
│                                              │
│             [+ Novo orçamento]               │
└─────────────────────────────────────────────┘
```

### Tela de negociação

```
┌──────────────────────────────────────────────────────┐
│ Casa dos Rodrigues  >  Completo ✏                     │
│                                                       │
│  [Ambientes ▾]  [Parâmetros ⚙]  [Exportar →]         │
│                                                       │
│  Quarto Master ............. R$ 20.900               │
│  Cozinha ................... R$ 30.875               │
│  Lavanderia ................ R$ 7.790                │
│  ────────────────────────────────────                │
│  Total contratual .......... R$ 55.100               │
│  Valor líquido loja ........ R$ 42.800               │
│                                                       │
│  Desconto: [5%]                                      │
└──────────────────────────────────────────────────────┘
```

### Painel "Ambientes" (drawer lateral)

```
┌─────────────────────────────────┐
│ Ambientes do projeto            │
│                                 │
│ ✅ Quarto Master   R$ 22.000   │
│ ✅ Cozinha         R$ 32.500   │
│ ⬜ Cozinha_v1      R$ 35.000   │
│ ✅ Lavanderia      R$ 8.200    │
│ ⬜ Closet          R$ 18.500   │
│                                 │
│       [+ Carregar XML]          │
└─────────────────────────────────┘
```

### Modal de duplicata

```
┌──────────────────────────────────────────┐
│ "Cozinha" já existe neste projeto         │
│ (usado em 2 orçamentos)                   │
│                                           │
│ [Sobrescrever]  [Nova versão]  [Cancelar] │
└──────────────────────────────────────────┘
```

### Modal de remoção

```
┌──────────────────────────────────────────┐
│ Retirar "Cozinha" do orçamento "Completo"?│
│                                           │
│              [Sim]  [Não]                 │
└──────────────────────────────────────────┘
```

---

## 6. Lógica de recálculo

```python
def recalcular_orcamento(orcamento_id):
    orcamento = db.get(Orcamento, orcamento_id)
    links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=orcamento_id).all()

    budget_total = sum(l.pool_ambiente.budget_total for l in links)
    order_total  = sum(l.pool_ambiente.order_total  for l in links)
    margens      = json.loads(orcamento.margens or '{}')

    resultado = calcular_negociacao(
        budget_total=budget_total,
        order_total=order_total,
        margens=margens,
        desconto_pct=orcamento.desconto_pct
    )

    orcamento.valor_total   = resultado["valor_contratual"]
    orcamento.valor_liquido = resultado["valor_liquido_loja"]
    orcamento.updated_at    = datetime.now()
    db.commit()
```

---

## 7. Decisões de arquitetura

- **Pool permanente** — XMLs nunca deletados; garante rastreabilidade
- **Sobrescrever atualiza o pool** — `orcamento_ambientes` aponta para o ID do pool; atualizar o pool reflete em todos os orçamentos automaticamente
- **Nova versão = novo registro** — preserva versão anterior intacta
- **Recálculo síncrono** — totais recalculados no mesmo request, antes de retornar ao frontend
- **Orçamentos sem delete** — preserva histórico de negociação para auditoria

---

## 8. Impacto em módulos existentes

| Módulo | Impacto |
|---|---|
| `database.py` | 3 novas tabelas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes` |
| `main.py` | 11 novas rotas; rota de upload XML modificada |
| `mod_omie.py` | Exportação usa ambientes do orçamento (não mais do projeto diretamente) |
| `mod_margens.py` | Recebe totais agregados do orçamento — sem mudança de lógica |
| `static/index.html` | Tela de projeto, painel de Ambientes, modais, navegação entre orçamentos |

---

## 9. Sequência de implementação

| Ordem | Tarefa | Dependência |
|---|---|---|
| 1 | Criar tabelas no `database.py` | — |
| 2 | Criar projeto → Orçamento 1 automático | Tabelas |
| 3 | Upload XML com detecção de duplicata | Tabelas |
| 4 | Modal de duplicata (Sobrescrever / Nova versão) | Upload |
| 5 | Painel "Ambientes" — listar pool com status | Tabelas |
| 6 | Adicionar ambiente ao orçamento | Painel |
| 7 | Remover ambiente com confirmação | Painel |
| 8 | Recálculo automático de totais | Add/remove |
| 9 | Botão "Novo orçamento" + nome | Tabelas |
| 10 | Navegação entre orçamentos | Novo orçamento |
| 11 | Renomear orçamento inline | Navegação |
| 12 | Sobrescrever → atualizar todos os orçamentos | Upload + recálculo |

---

## 10. Histórias de usuário

### US-20 — Criar projeto com orçamento inicial `[PLANEJADO]`
**Como** consultor, **quero** que ao criar um projeto o sistema já crie um orçamento vazio automaticamente, **para que** eu possa começar a adicionar ambientes imediatamente.

**Critérios de aceite:**
- Ao criar projeto → Orçamento 1 criado automaticamente com nome padrão
- Pool de ambientes começa vazio
- Tela do projeto exibe o orçamento recém-criado

---

### US-21 — Carregar XML com detecção de duplicata `[PLANEJADO]`
**Como** consultor, **quero** que ao carregar um XML com nome já existente o sistema me pergunte se quero sobrescrever ou criar nova versão, **para que** eu controle qual versão do Promob está em cada orçamento.

**Critérios de aceite:**
- Se nome novo → entra direto no pool
- Se nome duplicado → modal com três opções: Sobrescrever, Nova versão, Cancelar
- Sobrescrever → atualiza pool e recalcula todos os orçamentos afetados
- Nova versão → cria `Ambiente_v1` no pool; orçamentos existentes intactos

---

### US-22 — Painel de ambientes no orçamento `[PLANEJADO]`
**Como** consultor, **quero** um botão "Ambientes" na tela de negociação que exiba todos os ambientes do pool, **para que** eu adicione ou remova ambientes do orçamento atual.

**Critérios de aceite:**
- Painel exibe todos os ambientes do pool com status (incluído / disponível)
- Marcar ambiente → adicionado ao orçamento, totais recalculados
- Botão "Carregar XML" disponível dentro do painel

---

### US-23 — Remover ambiente com confirmação `[PLANEJADO]`
**Como** consultor, **quero** que ao desmarcar um ambiente o sistema me peça confirmação, **para que** eu não retire um ambiente por engano durante a apresentação.

**Critérios de aceite:**
- Modal: "Retirar 'X' deste orçamento?" com Sim/Não
- Sim → remove do orçamento, recalcula totais
- Não → nenhuma ação, ambiente permanece incluído

---

### US-24 — Criar orçamento paralelo `[PLANEJADO]`
**Como** consultor, **quero** criar múltiplos orçamentos dentro de um projeto, **para que** apresente cenários diferentes ao cliente (completo, intermediário, entrada).

**Critérios de aceite:**
- Botão "Novo orçamento" na tela do projeto
- Modal solicita nome do orçamento
- Novo orçamento criado vazio, disponível imediatamente
- Todos os orçamentos editáveis em paralelo

---

### US-25 — Renomear orçamento `[PLANEJADO]`
**Como** consultor, **quero** dar nome a cada orçamento e editá-lo quando quiser, **para que** eu e o cliente identifiquemos facilmente cada cenário.

**Critérios de aceite:**
- Clique no nome do orçamento → campo de texto editável inline
- Salvo automaticamente ao perder o foco
- Nome visível na tela do projeto e na tela de negociação

---

### US-26 — Sobrescrever ambiente atualiza todos os orçamentos `[PLANEJADO]`
**Como** sistema, **quero** que ao confirmar sobrescrita de um ambiente todos os orçamentos que o contêm sejam recalculados automaticamente, **para que** nenhum orçamento fique com dados desatualizados.

**Critérios de aceite:**
- Após sobrescrita, `budget_total` e `order_total` atualizados no pool
- Todos os orçamentos que referenciam o ambiente recalculados no mesmo request
- Resposta da API informa quantos orçamentos foram atualizados

---

*Documento: `docs/modulos/negociacao/VERSIONAMENTO.md`*  
*Atualizar `docs/historias/BACKLOG.md` com US-20 a US-26*
