# Bloco 1 — Contrato Completo e Ciclo de Ponta a Ponta

**Data:** 2026-06-16  
**Projeto:** Omie_V3 — Dalmóbile / Orizon Soluções  
**Escopo:** Cadastro expandido + Briefing digital + Novo template de contrato + Ciclo sequencial (etapas 1–8)  
**Pré-requisito para:** Bloco 2 (XML Projeto Executivo) e Bloco 3 (NF-e)

---

## 1. Contexto

O sistema já possui um ciclo de 20 etapas (EP-10), geração de contrato via `mod_contrato.py` e cadastro de clientes. O Bloco 1 torna o fluxo comercial sequencial e completo: tudo começa pelo cadastro do cliente, passa pelo briefing obrigatório e só então cria o projeto. O contrato usa o novo modelo `modelo_contrato_final.docx` com preenchimento automático da capa.

Três subsistemas maiores (Bloco 2 — XML executivo, Bloco 3 — NF-e) dependem deste bloco e têm specs próprios.

---

## 2. Navegação e Fluxo de Criação

### 2.1 Home (page-01) — duas abas

- **Projetos** (default) — lista atual, comportamento inalterado
- **Clientes** — lista de clientes com: nome, CPF/CNPJ, telefone, data de cadastro, status do último projeto vinculado

Ambas as abas coexistem. A estrutura de HTML/CSS já prevê um futuro seletor de loja acima das abas (grupo → loja → clientes/projetos), sem implementá-lo agora.

### 2.2 Fluxo de criação de projeto

**Via aba Clientes — "Novo Cliente":**
```
Passo 1 — Cadastro          Passo 2 — Briefing             Passo 3 — Projeto
nome*, email*, fone*   →→   campos obrigatórios do    →→   nome do projeto
CPF, endereços (opt)        briefing preenchidos            projeto criado
Salva cliente no DB         Salva briefing no DB            etapas 1 + 2 + 3
                                                            marcadas no ciclo
```

**Via aba Projetos — "Novo Projeto" (botão mantido):**
- Modal abre com campo "Selecionar cliente" (busca por nome/CPF)
- Cliente não existe → link para cadastrar (abre fluxo acima)
- Cliente existe sem briefing → sistema exige preenchimento do briefing antes de salvar o projeto
- Cliente existe com briefing → cria projeto normalmente; etapas 1 e 2 marcadas automaticamente

**Regra mínima:** não é possível salvar um projeto sem um cliente cadastrado vinculado.

---

## 3. Banco de Dados

### 3.1 Alterações em tabelas existentes

**`clientes` — campos novos:**
```sql
-- Endereço residencial / cobrança
res_logradouro    TEXT,
res_numero        TEXT,
res_complemento   TEXT,
res_bairro        TEXT,
res_cidade        TEXT,
res_cep           TEXT,
res_uf            TEXT,

-- Endereço de instalação
inst_mesmo_residencial  BOOLEAN DEFAULT 1,
inst_logradouro   TEXT,
inst_numero       TEXT,
inst_complemento  TEXT,
inst_bairro       TEXT,
inst_cidade       TEXT,
inst_cep          TEXT,
inst_uf           TEXT
```

Campos obrigatórios no cadastro: `nome`, `email`, `telefone`.  
Todos os endereços são opcionais no cadastro; instalação é exigida na etapa 6 (aprovação do orçamento).

**`usuarios` — campo novo:**
```sql
telefone  TEXT  -- NULL permitido; fallback em runtime: "(12) 3341-8777"
```

**`orcamentos.forma_pagamento` — JSON enriquecido:**

O JSON existente ganha os campos necessários para preencher a tabela de pagamento do contrato:
```json
{
  "tipo": "aymore",
  "entrada_valor": 5000.00,
  "entrada_tipo": "Boleto",
  "entrada_data": "15/07/2026",
  "modalidade": "Financiamento Aymoré",
  "num_parcelas": 48,
  "data_primeira_parcela": "15/08/2026",
  "parcelas": [
    { "numero": 1, "data": "15/08/2026", "valor": 450.00 },
    { "numero": 2, "data": "15/09/2026", "valor": 450.00 }
  ]
}
```

Regras por modalidade:
- **À vista:** `parcelas` tem 1 ou 2 entradas (entrada + saldo com datas); demais células = `"—"`
- **Cartão:** datas de todas as parcelas = `"—"` (banco processa internamente)
- **Aymoré:** datas calculadas mensalmente a partir de `data_primeira_parcela`
- **Total Flex:** datas 100% livres — lidas diretamente do JSON sem cálculo automático
- **Venda Programada:** idem Aymoré

### 3.2 Nova tabela `briefings`

```sql
CREATE TABLE briefings (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id              INTEGER NOT NULL REFERENCES clientes(id),
    projeto_nome            TEXT,            -- vinculado ao criar o projeto
    criado_em               DATETIME NOT NULL,
    atualizado_em           DATETIME,

    -- Obrigatórios (gate etapa 2)
    data_atendimento        DATETIME NOT NULL,  -- preenchido pelo servidor
    consultor_id            INTEGER REFERENCES usuarios(id),
    tipo_imovel             TEXT NOT NULL,   -- apartamento|casa|escritorio|loja|outro
    budget_declarado        REAL NOT NULL,
    categoria_proposta      TEXT NOT NULL,   -- essencial|refinada|exclusiva|atelier
    data_entrega_desejada   DATE NOT NULL,
    flexibilidade_prazo     TEXT NOT NULL,   -- rigido|negociavel|flexivel

    -- Opcionais
    condicao_imovel         TEXT,            -- novo|pronto|reforma_parcial|reforma_total
    metragem_m2             REAL,
    num_ambientes           INTEGER,
    ambientes_prioritarios  TEXT,
    tem_arquiteto           TEXT,            -- sim_aprovado|sim_andamento|nao
    nome_arquiteto          TEXT,
    tem_gerente_obra        BOOLEAN,
    end_empreendimento      TEXT,
    estilo_decisao          TEXT,            -- JSON array
    estilo_vida             TEXT,            -- JSON array
    relacao_projeto         TEXT,            -- JSON array
    decisor                 TEXT,            -- cliente|casal|socio|terceiro
    referencias_visuais     TEXT,            -- JSON array
    obs_referencias         TEXT,
    experiencia_anterior    TEXT,
    obs_experiencia         TEXT,
    tem_budget              TEXT,            -- sim|nao|prefere_nao
    forma_pagamento_pref    TEXT,
    data_entrega_limite     DATE,
    motivo_prazo            TEXT,            -- JSON array
    nao_abre_mao            TEXT,
    restricoes              TEXT,
    obs_livres              TEXT
);
```

**Campos obrigatórios para gate da etapa 2** (todos devem estar preenchidos para marcar etapa 2 como concluída):
`data_atendimento`, `tipo_imovel`, `budget_declarado`, `categoria_proposta`, `data_entrega_desejada`, `flexibilidade_prazo`

---

## 4. Template e Geração do Contrato

### 4.1 Estratégia

Um script `scripts/preparar_template_contrato.py` lê `modelo_contrato_final.docx`, insere placeholders Jinja2 nas células da capa e salva como `config/contrato_template.docx`. O `mod_contrato.py` usa `docxtpl` para renderizar o contrato final — consistente com a abordagem existente.

O script é executado uma vez (ou ao atualizar o modelo). O arquivo `.docx` original fica preservado.

### 4.2 Mapa de placeholders — capa

**Linha de cabeçalho:**
```
Consultor: {{ consultor_nome }}   Telefone: {{ consultor_tel }}   e-mail: {{ consultor_email }}
```

**Tabela 1 — Identificação do cliente:**
```
{{ cliente_nome }}          {{ cliente_cpf }}
{{ cliente_email }}         {{ cliente_telefone }}
```

**Tabela 2 — Endereço residencial:**
```
{{ res_logradouro }}
{{ res_numero }}    {{ res_complemento }}    {{ res_bairro }}
{{ res_cidade }}    {{ res_cep }}            {{ res_uf }}
```

**Tabela 3 — Endereço de instalação:**
- Se `inst_mesmo_residencial = True`: exibe "Mesmo endereço residencial" em todas as células
- Caso contrário: mesmos campos com prefixo `inst_`

**Tabela 4 — Forma de pagamento:**
```
{{ pgto_entrada_valor }}   {{ pgto_entrada_tipo }}   {{ pgto_entrada_data }}
{{ pgto_modalidade }}      {{ pgto_num_parcelas }}   {{ pgto_data_primeira }}
{{ p01_data }}  {{ p02_data }}  {{ p03_data }}
...
{{ p22_data }}  {{ p23_data }}  {{ p24_data }}
```

Células não utilizadas recebem `"—"`.

### 4.3 `mod_contrato.py` — função de contexto

```python
def construir_contexto(projeto_nome: str, orcamento_id: int, usuario: dict) -> dict:
    """Monta o dict completo para docxtpl."""
    # 1. Carrega cliente + endereços (residencial e instalação)
    # 2. Carrega usuário; telefone com fallback "(12) 3341-8777"
    # 3. Parseia forma_pagamento JSON → monta p01..p24
    #    - Aymoré/VP: calcula datas mensais a partir de data_primeira
    #    - Total Flex: lê datas diretamente do JSON (sem cálculo)
    #    - Cartão: preenche p01..p24 com "—"
    #    - À vista: p01 = data do saldo; p02..p24 = "—"
    # 4. Retorna dict
```

### 4.4 Assinatura

- **Manual:** contrato gerado em PDF (ou .docx com fallback LibreOffice) → impresso e assinado fisicamente
- **Eletrônica (futuro):** integração D4Sign — estrutura preparada mas não implementada neste bloco
- Status do contrato: `rascunho` → `para_assinatura` → `assinado`
- Etapa 7 do ciclo fecha somente ao atingir status `assinado` (hoje fecha ao gerar)

---

## 5. Ciclo de Ponta a Ponta (Etapas 1–8)

### 5.1 Tabela de etapas — o que muda

| Etapa | Nome | Gatilho de conclusão | Mudança |
|---|---|---|---|
| **1** | Captação do cliente | Cliente salvo no DB | Marcada ao criar o cliente (não mais auto-complete genérico) |
| **2** | Briefing | 6 campos obrigatórios válidos | Marcada ao salvar briefing completo |
| **3** | Criação do projeto | Projeto criado com cliente vinculado | Marcada ao criar projeto; exige etapa 2 concluída |
| **4** | Primeiro orçamento | Orçamento criado | Comportamento atual mantido |
| **5** | Revisão de projeto | Manual pelo consultor | Comportamento atual mantido |
| **6** | Aprovação do orçamento | Botão "Aprovar orçamento" | Exige endereço de instalação preenchido |
| **7** | Contrato | Status contrato = `assinado` | Split: `gerado` não fecha mais a etapa; só `assinado` fecha |
| **8** | Aprovação financeira I | Manual | Comportamento atual mantido |

### 5.2 Regras de bloqueio

- Criar projeto → exige cliente com briefing (etapa 2 concluída)
- Aprovar orçamento (etapa 6) → exige `inst_logradouro` preenchido no cliente (ou `inst_mesmo_residencial = True`)
- Gerar contrato → etapa 7 entra em estado intermediário `gerado` (visível no ciclo mas não fechada)
- Assinar contrato → etapa 7 fecha; etapa 8 desbloqueada

### 5.3 Compatibilidade com projetos legados

Projetos criados antes desta migração continuam com etapas 1–5 auto-marcadas (lógica existente no backend). A nova lógica de gate aplica-se apenas a projetos criados após a migração — detectado pela presença de `cliente_id` vinculado ao projeto.

---

## 6. Novos Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/api/clientes` | Criar cliente (campos expandidos) |
| `PUT` | `/api/clientes/<id>` | Atualizar cliente (endereços + dados) |
| `POST` | `/api/clientes/<id>/briefing` | Criar/atualizar briefing |
| `GET` | `/api/clientes/<id>/briefing` | Retorna briefing do cliente |
| `GET` | `/api/clientes` | Lista clientes (com status último projeto) |
| `GET` | `/api/clientes/<id>` | Detalhe do cliente + briefing + projetos |

Endpoints existentes de contrato (`POST /api/projetos/<nome>/contrato`, `PATCH .../contrato`, `POST .../contrato/assinar`) mantidos — apenas `mod_contrato.py` é alterado internamente.

---

## 7. Critérios de Aceite

| # | Critério | Como validar |
|---|---|---|
| CA-01 | Não é possível salvar projeto sem cliente vinculado | Tentar criar projeto sem selecionar cliente |
| CA-02 | Não é possível criar projeto sem briefing com campos obrigatórios | Tentar criar projeto com briefing incompleto |
| CA-03 | Etapas 1, 2 e 3 marcadas automaticamente nos eventos corretos | Criar cliente → briefing → projeto e verificar ciclo |
| CA-04 | Contrato preenche capa com dados reais (consultor, cliente, endereços) | Gerar contrato e inspecionar PDF |
| CA-05 | Tabela de pagamento reflete modalidade correta (Aymoré com datas, Cartão com traços, TF com datas livres) | Testar cada modalidade |
| CA-06 | Etapa 7 só fecha ao assinar (não ao gerar) | Gerar contrato → verificar etapa 7 ainda aberta → assinar → etapa fecha |
| CA-07 | Endereço de instalação bloqueado na aprovação se não preenchido | Tentar aprovar sem inst_logradouro |
| CA-08 | Projetos legados não são afetados (etapas 1–5 auto-marcadas) | Abrir projeto existente e verificar ciclo |
| CA-09 | Telefone do consultor usa fallback "(12) 3341-8777" quando vazio | Gerar contrato com usuário sem telefone |

---

## 8. Fora do Escopo (Bloco 1)

- Integração D4Sign (assinatura eletrônica) — estrutura preparada, implementação no Bloco 1b
- Upload de XML do projeto executivo — Bloco 2
- Emissão de NF-e — Bloco 3
- Seletor de loja / visão de grupo — futuro
- Múltiplos briefings por cliente (revisita) — futuro
