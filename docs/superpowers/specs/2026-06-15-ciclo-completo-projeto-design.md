# Ciclo Completo do Projeto — Design Spec

**Status:** Aprovado para implementação — 2026-06-15  
**Prioridades imediatas:** Módulo de Contrato (etapa 7) + Emissão de NFe do Cliente (etapa 15)

---

## 1. Visão geral

O sistema implementa um pipeline linear de 20 etapas cobrindo toda a jornada do projeto, desde a captação do cliente até a aprovação final pós-montagem. Cada etapa é um card expansível na aba **"Ciclo"** da tela do projeto (page-02). O sistema impede avançar para a próxima etapa sem completar a anterior.

### Abordagem futura documentada (fase C)

Quando o sistema tiver múltiplos usuários operando simultaneamente, implementar uma **fila de tarefas por papel** na home: o gerente vê "3 contratos aguardando aprovação financeira", o projetista vê "2 projetos aguardando conferência do executivo". Essa camada se apoia no mesmo modelo de dados do pipeline — não requer mudança de estrutura, apenas uma nova view.

---

## 2. Pipeline completo — 20 etapas

| # | Etapa | Responsável | Status possíveis | Implementado |
|---|-------|-------------|-----------------|--------------|
| 1 | Captação do cliente | Consultor | — | ✓ |
| 2 | Briefing | Consultor | pendente / realizado | — |
| 3 | Criação do projeto | Consultor | — | ✓ |
| 4 | Primeiro orçamento | Consultor | — | ✓ |
| 5 | Revisão de projeto | Projetista | índice de revisão (v1, v2…) | parcial (EP-07) |
| 6 | Aprovação do projeto | Gerente/Diretor | pendente / aprovado | parcial |
| 7 | **Contrato** | Consultor | rascunho / gerado / assinado loja / assinado cliente / vigente | — |
| 8 | **Aprovação financeira I** | Gerente | pendente / aprovada / rejeitada | — |
| 9 | Solicitação de medição | Assist. Logístico | aprovada / reprovada / venda programada | — |
| 10 | Planta de pontos medidos | Medidor | pendente / entregue | — |
| 11 | Projeto executivo | Projetista Executivo | *subfases abaixo* | — |
| 11a | — Planta de pontos de PE | Projetista | pendente / entregue | — |
| 11b | — Reunião de alinhamento | Projetista + Conferente | acordo / desacordo | — |
| 11c | — Revisão de PE | Projetista | pendente / entregue | — |
| 11d | — Aprovação financeira II | Gerente/Diretor | pendente / aprovada | — |
| 11e | — Aprovação do PE pelo cliente | Cliente | pendente / aprovado / reprovado | — |
| 12 | Implantação do pedido | Conferente → Omie | pendente / implantado | parcial |
| 13 | Produção | Fábrica | aguardando / em produção / concluída | — |
| 14 | Entrega no depósito | Logística | aguardando / recebido | — |
| 15 | **Emissão da NFe do cliente** | Financeiro → Omie | pendente / emitida | — |
| 16 | Entrega no cliente | Logística | agendada / realizada | — |
| 17 | Montagem | Montadores | agendada / em execução / concluída | — |
| 17a | — Pendências de montagem | Supervisor | sem pendências / com pendências ⚑ | — |
| 18 | Assistência pós Montagem | Supervisor | sem ocorrências / com ocorrências | — |
| 19 | Vistoria final | Supervisor + Consultor | pendente / aprovada | — |
| 20 | Aprovação final | Cliente | pendente / aprovado | — |

> **Etapa 8 (Aprovação financeira I):** é nesse momento que as provisões pós-fechamento são calculadas e registradas. Ver detalhamento na seção de Provisões financeiras abaixo.

### Regras de sequenciamento

- Cada etapa numerada (1–20) só fica disponível após a anterior estar em status final positivo.
- Etapas com subfases (11a–11e) seguem sequência interna própria; a etapa 11 avança para 12 apenas quando 11e está aprovado.
- A flag `⚑` em Pendências de montagem (17a) é visível na lista de projetos e na aba Ciclo, independente do status geral da etapa 17. Pendências resolvidas antes da vistoria final podem ser desmarcadas sem bloquear o avanço.
- Etapas 13 e 14 (produção e entrega no depósito) podem ser atualizadas por qualquer usuário logado; não exigem perfil específico.

### Provisões financeiras

Calculadas e registradas em dois momentos:

**No ato da venda (etapas 1–6 — parte já implementada):**
- Comissão de parceiro / programa de fidelidade / custo viagem / brinde
- Custo financeiro (juros repassados ou absorvidos)
- Provisão de impostos

**Após fechamento (etapa 8 — Aprovação financeira I):**
- Comissão de vendas: consultor + gerente
- Comissão administrativa: gerente + diretor
- Custo fábrica
- Montagem
- Comissão de projeto executivo
- Comissão de medidor
- Frete fábrica → loja
- Frete local
- Custo médio de assistências
- Consumo médio de insumos locais

As provisões pós-fechamento alimentam o painel de margem real do projeto, complementando o painel de apoio interno já existente na negociação.

---

## 3. Módulo de Contrato (etapa 7) — PRIORIDADE 1

### 3.1 Fluxo

1. Etapa 6 (Aprovação do projeto) concluída → card "Contrato" fica disponível na aba Ciclo.
2. Consultor clica em "Gerar Contrato" → sistema preenche o template `.docx` com as variáveis do projeto e converte para PDF via LibreOffice headless no servidor.
3. PDF gerado é exibido no browser via `<iframe>` para revisão antes de qualquer assinatura.
4. Consultor pode adicionar um **adendo textual** (campo livre) que é inserido no final do contrato como seção "Adendo". Alterações estruturais exigem novo template `.docx`.
5. Botão **"Baixar / Imprimir PDF"** disponível a qualquer momento após geração.
6. **Fluxo de assinatura interna (MVP):**
   - Modal com campos: Nome completo + CPF + checkbox "Li e aceito os termos do contrato"
   - Sistema calcula `hash_sha256(nome + cpf + contrato_id + timestamp)`
   - Grava em `contratos_assinaturas` com IP de origem
   - Duas assinaturas necessárias: parte **loja** (consultor) e parte **cliente**
   - Status avança para `vigente` quando ambas estão registradas
7. **Fluxo D4Sign (fase futura):**
   - Substituir etapa de assinatura interna pelo envio do PDF à API D4Sign
   - Sistema recebe webhook de confirmação e atualiza status automaticamente
   - Nenhuma mudança de modelo de dados necessária — apenas novo campo `d4sign_uuid` em `contratos`

### 3.2 Template e variáveis

O template é um arquivo `.docx` com marcadores no formato `{{variavel}}`. Variáveis disponíveis:

| Marcador | Fonte |
|----------|-------|
| `{{cliente_nome}}` | `clientes.nome` |
| `{{cliente_cpf}}` | `clientes.cpf` |
| `{{cliente_endereco}}` | `clientes.endereco` |
| `{{cliente_telefone}}` | `clientes.telefone` |
| `{{projeto_nome}}` | `projeto.nome_projeto` |
| `{{projeto_data}}` | `projeto.criado_em` |
| `{{orcamento_nome}}` | `orcamentos.nome` |
| `{{valor_total}}` | valor final do orçamento aprovado |
| `{{forma_pagamento}}` | forma de pagamento registrada |
| `{{entrada_valor}}` | valor da entrada |
| `{{parcelas_descricao}}` | descrição textual do parcelamento |
| `{{ambientes_lista}}` | lista dos ambientes incluídos |
| `{{consultor_nome}}` | `usuarios.nome` (consultor do projeto) |
| `{{data_contrato}}` | data de geração do PDF |
| `{{adendo}}` | texto livre adicionado pelo consultor (vazio se não houver) |

O template `.docx` fica em `config/contrato_template.docx`. Para atualizar o modelo, substituir o arquivo — sem necessidade de alteração de código.

### 3.3 Modelo de dados

```sql
-- Tabela contratos
id              INTEGER PRIMARY KEY
projeto_id      INTEGER FK → projetos (futuro) / nome_safe TEXT
orcamento_id    INTEGER FK → orcamentos
template_path   TEXT        -- caminho do .docx usado
pdf_path        TEXT        -- caminho do PDF gerado
status          TEXT        -- rascunho | gerado | assinado_loja | assinado_cliente | vigente
adendo          TEXT        -- texto do adendo (nullable)
gerado_em       DATETIME
gerado_por_id   INTEGER FK → usuarios
d4sign_uuid     TEXT        -- preenchido apenas na integração D4Sign (fase futura)

-- Tabela contratos_assinaturas
id              INTEGER PRIMARY KEY
contrato_id     INTEGER FK → contratos
parte           TEXT        -- loja | cliente
nome            TEXT
cpf             TEXT
assinado_em     DATETIME
ip_origem       TEXT
hash_sha256     TEXT
```

### 3.4 Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/projetos/<nome>/contrato` | Gera PDF a partir do template; retorna URL do PDF |
| `GET` | `/api/projetos/<nome>/contrato` | Retorna metadados + URL do PDF atual |
| `PATCH` | `/api/projetos/<nome>/contrato` | Atualiza adendo; regenera PDF |
| `POST` | `/api/projetos/<nome>/contrato/assinar` | Registra assinatura (parte loja ou cliente) |

### 3.5 Critérios de aceite

- [ ] PDF gerado com todas as variáveis preenchidas corretamente
- [ ] Adendo aparece como seção no final do PDF quando preenchido
- [ ] PDF visualizável no browser via iframe antes da assinatura
- [ ] Download/impressão do PDF funcionando
- [ ] Assinatura da loja registra hash + timestamp + IP
- [ ] Assinatura do cliente registra hash + timestamp + IP
- [ ] Status avança para `vigente` apenas com ambas as assinaturas
- [ ] Contrato em status `vigente` avança o pipeline para etapa 8

---

## 4. Emissão da NFe do Cliente (etapa 15) — PRIORIDADE 2

### 4.1 Contexto

A distribuidora (loja Dalmóbile) recebe mercadoria da fábrica acompanhada de uma NFe. Com base nessa NFe, emite sua própria NFe para o cliente final. A emissão é delegada ao Omie ERP via API; o Omie_V3 orquestra o fluxo e registra os dados.

### 4.2 Fluxo

1. Etapa 14 (Entrega no depósito) marcada como `recebido`.
2. Usuário faz upload do XML da NFe da fábrica **ou** informa a chave de acesso (44 dígitos).
3. Sistema parseia o XML e extrai: número NF, série, CNPJ emitente, itens, valores, CFOP.
4. Sistema exibe resumo dos dados da NFe da fábrica para conferência.
5. Sistema monta o payload para o Omie com: dados do cliente, itens mapeados pelos 16 grupos de produtos, valores com margem aplicada, CFOP de revenda.
6. Chamada à API Omie (`IncluirNFe` ou endpoint equivalente) → retorna chave de acesso da NFe emitida.
7. Sistema grava chave + número NF + PDF (DANFE) e avança o pipeline para etapa 16.
8. DANFE disponível para download na aba Ciclo.

### 4.3 Modelo de dados

```sql
-- Tabela nfes_projeto
id              INTEGER PRIMARY KEY
projeto_id      TEXT        -- nome_safe do projeto
tipo            TEXT        -- fabrica | cliente
numero_nf       TEXT
serie           TEXT
chave_acesso    TEXT        -- 44 dígitos
xml_path        TEXT        -- XML da NF (local)
danfe_path      TEXT        -- PDF do DANFE (local)
emitida_em      DATETIME
omie_status     TEXT        -- pendente | emitida | erro
omie_erro       TEXT        -- mensagem de erro se houver
```

### 4.4 Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/api/projetos/<nome>/nfe/fabrica` | Registra XML/chave da NFe da fábrica; retorna dados extraídos |
| `POST` | `/api/projetos/<nome>/nfe/cliente` | Monta payload e envia para Omie; salva retorno |
| `GET` | `/api/projetos/<nome>/nfe/cliente` | Retorna status + chave + link do DANFE |

### 4.5 Critérios de aceite

- [ ] Upload do XML da fábrica extrai dados corretamente
- [ ] Resumo dos dados da NFe fábrica exibido antes de emitir
- [ ] Payload enviado ao Omie com dados do cliente e itens mapeados pelos 16 grupos
- [ ] Chave de acesso e DANFE gravados após sucesso no Omie
- [ ] Erro retornado pelo Omie exibido como toast + gravado em `omie_erro`
- [ ] Etapa 15 avança para 16 apenas após NFe emitida com sucesso

---

## 5. Modelo de dados — tabela `ciclo_etapas`

Armazena o estado atual de cada etapa do pipeline por projeto.

```sql
id              INTEGER PRIMARY KEY
projeto_nome    TEXT        -- nome_safe do projeto
etapa_codigo    TEXT        -- ex: "7", "11b", "17a"
status          TEXT        -- depende da etapa (ver pipeline)
responsavel_id  INTEGER FK → usuarios (nullable)
iniciado_em     DATETIME
concluido_em    DATETIME    -- nullable
observacoes     TEXT        -- nullable
```

A tabela é genérica o suficiente para suportar todas as 20 etapas e subfases sem alteração de esquema ao adicionar novas etapas.

---

## 6. UX — Aba "Ciclo" na tela do projeto

- Nova aba **"Ciclo"** ao lado das abas de orçamentos em page-02.
- Lista vertical de cards por etapa, com ícone de status (⏳ pendente / ✓ concluída / 🔒 bloqueada / ⚑ com pendência).
- Card da etapa atual fica expandido automaticamente ao abrir a aba.
- Etapas futuras mostram apenas o título e ícone de cadeado — não expansíveis.
- Etapas concluídas são colapsáveis e exibem data de conclusão + responsável.
- Subfases (11a–11e, 17a) aparecem recuadas dentro do card da etapa pai.

---

## 7. Dependências técnicas novas

| Dependência | Uso | Instalação |
|-------------|-----|------------|
| `python-docx` | Preencher template `.docx` | `pip install python-docx` |
| LibreOffice headless | Converter `.docx` → PDF | já disponível no Ubuntu 24.04 via `apt` |
| `lxml` | Parsear XML da NFe da fábrica | `pip install lxml` (provavelmente já instalado) |

---

*Spec criada em 2026-06-15. Atualizar a cada decisão relevante sobre o pipeline ou módulos prioritários.*
