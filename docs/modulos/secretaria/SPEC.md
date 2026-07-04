# SPEC — Módulo Secretária Orizon

**Épico:** EP-08  
**Status:** PLANEJADO  
**Versão alvo:** v0.5.0  
**Porta:** 8766 (separada do Orizon Manager — porta 8765)  
**Repositório:** github.com/mbnunes1972/secretaria_orizon (novo repo)  
**VPS:** Hostinger — 167.88.33.121 (mesmo servidor do Orizon Manager)

---

## 1. Visão geral

A Secretária Orizon é um agente de IA operacional que conhece o fluxo comercial de 38 etapas documentado em `docs/processos/FLUXO_38_ETAPAS.md` do Orizon Manager. Ela atua como guardiã do processo comercial, com duas responsabilidades centrais:

1. **Modo reativo** — responde a perguntas da equipe via chat ou voz sobre pendências, próximos passos e status de negociações
2. **Modo proativo** — monitora o banco de dados do Orizon Manager e dispara alertas via WhatsApp quando detecta etapas paradas além do prazo

A interface é um painel web com suporte a voz (Web Speech API) e chat, acessível por Diretor, Gerentes e Consultores com visibilidade filtrada por perfil.

---

## 2. Premissas arquiteturais

| Item | Decisão | Justificativa |
|---|---|---|
| Banco de dados | Leitura via endpoints REST do Orizon Manager | Evita acesso direto ao SQLite; protege integridade do DB |
| Escrita no banco | **Proibida** — agente é somente leitura | Separação de responsabilidades |
| LLM | Claude API (claude-sonnet-4-6) | Consistência com stack de IA do ecossistema |
| Canal de alertas | WhatsApp via Evolution API (self-hosted no VPS) | Zero custo adicional; controle total |
| Voz | Web Speech API (browser nativo) | Sem dependência externa; funciona no Chrome/Edge |
| Autenticação | Token JWT compartilhado com Orizon Manager | Usuário loga uma vez; mesma sessão |
| Idioma | Português formal | Padrão da Orizon Soluções |

---

## 3. Estrutura de arquivos

```
secretaria_orizon/
├── main.py                  # Servidor HTTP (porta 8766)
├── agent_core.py            # Integração Claude API + system prompt
├── db_reader.py             # Consumidor dos endpoints do Orizon Manager
├── scheduler.py             # APScheduler — varredura periódica do fluxo
├── notifier.py              # Envio de alertas via Evolution API (WhatsApp)
├── auth.py                  # Validação JWT compartilhado com Orizon Manager
├── config.py                # Variáveis de ambiente (sem secrets em código)
├── static/
│   ├── index.html           # SPA — painel principal
│   ├── css/style.css        # Identidade visual Orizon
│   └── js/
│       ├── app.js           # Orquestrador do frontend
│       ├── chat.js          # Módulo de chat
│       ├── voice.js         # Web Speech API (entrada + síntese)
│       └── alerts.js        # Exibição de pendências e alertas
├── prompts/
│   └── system_prompt.txt    # System prompt da secretária (versionado)
├── docs/                    # Esta documentação
├── .env.example
├── requirements.txt
└── DEV_LOG.md
```

---

## 4. Módulos do backend

### 4.1 `agent_core.py`

Responsável pela conversa com a Claude API.

**Responsabilidades:**
- Montar o system prompt com contexto do processo Orizon
- Injetar dados reais do Orizon Manager no contexto de cada requisição
- Gerenciar histórico de conversa por sessão (em memória, até 20 turnos)
- Retornar resposta em texto para o frontend

**Entradas:**
```python
def chat(user_message: str, session_id: str, user_profile: dict) -> str
```

**Contexto injetado por chamada:**
- Lista de negociações ativas com status e fase atual
- Pendências críticas (etapas paradas > prazo configurado)
- Perfil do usuário (loja, cargo, negociações sob sua responsabilidade)

**Regra de segurança:** O agente nunca recebe a chave da API diretamente — lida com variável de ambiente `ANTHROPIC_API_KEY`.

---

### 4.2 `db_reader.py`

Consome os endpoints de leitura do Orizon Manager.

**Endpoints consumidos (todos GET, sem escrita):**

| Endpoint Orizon Manager | Dado obtido |
|---|---|
| `GET /api/projetos` | Lista de projetos/negociações ativos |
| `GET /api/projetos/{id}` | Detalhe de um projeto |
| `GET /api/projetos/{id}/status` | Fase e etapa atual no fluxo de 38 passos |
| `GET /api/usuarios` | Lista de consultores/gerentes por loja |
| `GET /api/clientes/{id}` | Dados do cliente da negociação |

**Nota:** Estes endpoints precisam ser criados no Orizon Manager como parte do EP-08. Ver seção 7.

---

### 4.3 `scheduler.py`

Varredura periódica do banco via `db_reader.py`.

**Frequência:** A cada 2 horas (configurável via `.env`)

**Lógica de detecção de atraso:**

```
Para cada negociação ativa:
  Se (data_atual - data_ultima_atualizacao) > prazo_etapa_atual:
    Gerar alerta com: cliente, fase, etapa, responsável, dias parados
    Enviar via notifier.py
    Registrar no log de alertas (SQLite local)
```

**Prazos por fase (configuráveis em `config.py`):**

| Fase | Prazo padrão |
|---|---|
| Fase 1 — Captação | 1 dia |
| Fase 2 — Orçamento | 2 dias |
| Fase 3 — Projeto | 3 dias |
| Fase 4 — Aprovação | 2 dias |
| Fase 5 — Contrato | 2 dias |
| Fase 6 — Pós-venda | Conforme sub-etapa |

**Regra anti-spam:** Mesmo alerta não é reenviado em menos de 24 horas.

---

### 4.4 `notifier.py`

Envia mensagens WhatsApp via Evolution API.

**Método:**
```python
def enviar_alerta(telefone: str, mensagem: str) -> bool
```

**Formato padrão da mensagem:**
```
🔔 *Orizon — Alerta de Processo*

Negociação: [Nome do Cliente]
Fase: [Fase atual]
Etapa: [Etapa atual]
Responsável: [Nome do consultor]
Parado há: [N] dias

Acesse o sistema para atualizar o status.
```

**Configuração Evolution API:**
- URL base: `http://localhost:8080` (self-hosted no VPS)
- Autenticação: API Key via `.env`
- Instância WhatsApp: uma por loja ou uma central

---

### 4.5 `auth.py`

Valida o JWT emitido pelo Orizon Manager.

**Fluxo:**
1. Usuário já autenticado no Orizon Manager possui token JWT
2. Frontend da Secretária envia o mesmo token no header `Authorization: Bearer {token}`
3. `auth.py` valida assinatura com a mesma `SECRET_KEY` do Orizon Manager
4. Retorna perfil do usuário (nome, cargo, loja, limite de desconto)

**Perfis e visibilidade:**

| Perfil | Vê no painel |
|---|---|
| Diretor | Todas as lojas, todas as negociações |
| Gerente | Apenas sua loja |
| Consultor | Apenas suas próprias negociações |

---

## 5. Frontend — painel web

### 5.1 Estrutura da SPA

```
Sidebar (navegação)
├── Chat (tela principal)
├── Fluxo (kanban de pendências)
├── Alertas (histórico de notificações)
└── [Lojas] (filtro por unidade — apenas Diretor e Gerente)

Topbar
├── Status do agente (ativo / monitorando N negociações)
└── Botões: configurações, histórico

Barra de alertas críticos (aparece quando há pendências)

Área de chat
├── Mensagens do agente e do usuário
└── Cards de pendências inline

Input
├── Campo de texto
├── Botão de voz (microfone)
└── Botão enviar
```

### 5.2 Identidade visual

Seguir a paleta Orizon já estabelecida no Orizon Manager:

| Token | Cor | Uso |
|---|---|---|
| `--dalm-brown` | `#2C1F0E` | Sidebar, cabeçalhos, botão de voz |
| `--dalm-gold` | `#9C7A3C` | Ícones ativos, bordas de destaque, botão enviar |
| `--dalm-gold-light` | `#C4A265` | Texto na sidebar, labels |
| `--dalm-beige` | `#FAF6F0` | Background principal, texto sobre fundo escuro |

### 5.3 Módulo de voz (`voice.js`)

**Entrada (Speech-to-Text):**
- API: `window.SpeechRecognition` (nativo Chrome/Edge)
- Idioma: `pt-BR`
- Modo: contínuo enquanto botão ativo
- Resultado enviado ao campo de texto antes de enviar

**Saída (Text-to-Speech):**
- API: `window.speechSynthesis`
- Voz preferida: `pt-BR` feminina (se disponível no sistema)
- Ativado automaticamente para respostas quando usuário usou voz

---

## 6. Sistema prompt da secretária

O system prompt é o elemento central de comportamento do agente. Ele é versionado em `prompts/system_prompt.txt`.

**Estrutura do system prompt:**

```
Você é a Secretária Comercial da Orizon Soluções, uma assistente operacional
especializada no processo comercial da empresa.

[IDENTIDADE]
- Tom: formal, objetivo, prestativo
- Idioma: português formal brasileiro
- Nunca use gírias ou linguagem informal
- Trate os usuários pelo cargo: "Sr. Diretor", "Gerente [Nome]", "Consultor(a) [Nome]"

[CONHECIMENTO DO PROCESSO]
O processo comercial Orizon tem 6 fases e 38 etapas:
[...conteúdo do FLUXO_38_ETAPAS.md injetado aqui...]

[DADOS ATUAIS DO SISTEMA]
{dados_injetados_em_tempo_real}
- Negociações ativas: {lista}
- Pendências críticas: {lista}
- Usuário atual: {perfil}

[REGRAS DE COMPORTAMENTO]
1. Sempre cite a fase e etapa específica ao falar de uma negociação
2. Se um prazo está vencido, sinalize com urgência, mas sem alarmismo
3. Nunca invente dados — se não tiver informação, diga que não tem acesso
4. Não execute ações — apenas informe e oriente
5. Sugira o próximo passo concreto ao final de cada resposta
```

---

## 7. Endpoints a criar no Orizon Manager (EP-08 backend)

Estes endpoints precisam ser adicionados ao `main.py` do Orizon Manager como parte desta fase:

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/api/v1/projetos/ativos` | Lista projetos com fase e dias parados |
| `GET` | `/api/v1/projetos/{id}/status_fluxo` | Status detalhado no fluxo de 38 etapas |
| `GET` | `/api/v1/pendencias` | Lista de etapas atrasadas (para o scheduler) |
| `GET` | `/api/v1/usuarios/responsaveis` | Mapa consultor → projetos → telefone WhatsApp |

**Regras para estes endpoints:**
- Somente leitura (SELECT)
- Autenticação JWT obrigatória
- Retorno JSON
- Prefixo `/api/v1/` para diferenciar dos endpoints internos do Orizon Manager

---

## 8. Banco de dados local da Secretária

SQLite separado (`secretaria.db`) — apenas para dados próprios da Secretária:

```sql
CREATE TABLE log_alertas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id  INTEGER NOT NULL,
    fase        TEXT NOT NULL,
    etapa       TEXT NOT NULL,
    responsavel TEXT NOT NULL,
    telefone    TEXT NOT NULL,
    enviado_em  DATETIME NOT NULL,
    canal       TEXT DEFAULT 'whatsapp'
);

CREATE TABLE sessoes_chat (
    session_id  TEXT PRIMARY KEY,
    usuario_id  INTEGER NOT NULL,
    iniciado_em DATETIME NOT NULL,
    historico   TEXT NOT NULL  -- JSON: lista de mensagens
);
```

---

## 9. Variáveis de ambiente (`.env`)

```env
# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Orizon Manager — leitura
ORIZON_MANAGER_BASE_URL=http://localhost:8765
ORIZON_MANAGER_JWT_SECRET=<mesma secret do Orizon Manager>

# Evolution API — WhatsApp
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_KEY=...
EVOLUTION_INSTANCE=orizon-central

# Scheduler
SCHEDULER_INTERVAL_HOURS=2

# Secretária
PORT=8766
DEBUG=false
```

---

## 10. Critérios de aceite do MVP

| # | Critério | Como validar |
|---|---|---|
| CA-01 | Usuário autenticado no Orizon Manager acessa o painel sem novo login | Abrir 167.88.33.121:8766 com token válido |
| CA-02 | Chat responde em < 5 segundos com dados reais do Orizon Manager | curl + cronômetro |
| CA-03 | Voz é reconhecida corretamente em pt-BR | Teste manual com 5 frases distintas |
| CA-04 | Scheduler detecta etapa parada e envia WhatsApp | Criar projeto parado artificialmente |
| CA-05 | Consultor vê apenas suas negociações | Login com perfil de consultor |
| CA-06 | Gerente vê apenas sua loja | Login com perfil de gerente |
| CA-07 | Mesmo alerta não reenviado em < 24h | Verificar `log_alertas` após segunda varredura |
| CA-08 | Agente nunca inventa dados ausentes | Perguntar sobre projeto inexistente |
