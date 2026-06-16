# EP-08 — Sequência de Implementação

**Módulo:** Secretária Orizon  
**Status:** PLANEJADO  
**Versão alvo:** v0.5.0

---

## Visão geral

O EP-08 é desenvolvido em **dois repositórios em paralelo**:

- **Omie_V3** — adição dos endpoints de leitura (Bloco A)
- **secretaria_orizon** — novo repositório com o agente (Blocos B a E)

Cada passo deve ser validado antes de avançar. Não pular etapas.

---

## Bloco A — Endpoints no Omie_V3 (pré-requisito)

> Fazer no repositório `omie_v3` antes de qualquer coisa.

### Passo 1 — Criar endpoints de leitura no main.py

**Arquivo:** `main.py` do Omie_V3  
**O que fazer:** Adicionar 4 rotas GET em `/api/v1/`:

```
GET /api/v1/projetos/ativos
GET /api/v1/projetos/{id}/status_fluxo
GET /api/v1/pendencias
GET /api/v1/usuarios/responsaveis
```

**Validação:**
```bash
# Deve retornar lista de projetos com fase e dias_parados
curl -H "Authorization: Bearer {token}" http://167.88.33.121:8765/api/v1/projetos/ativos

# Deve retornar {"status": "ok"} para endpoint de saúde
curl http://167.88.33.121:8765/health
```

**Commit:** `feat(ep08): endpoints de leitura para secretaria`

---

## Bloco B — Setup do repositório da Secretária

### Passo 2 — Criar repositório e estrutura base

```bash
mkdir secretaria_orizon && cd secretaria_orizon
git init
git remote add origin https://github.com/mbnunes1972/secretaria_orizon.git

# Criar estrutura
mkdir -p static/css static/js prompts docs
touch main.py agent_core.py db_reader.py scheduler.py notifier.py auth.py config.py
touch .env.example requirements.txt DEV_LOG.md .gitignore
```

**`requirements.txt`:**
```
anthropic>=0.25.0
apscheduler>=3.10.0
requests>=2.31.0
pyjwt>=2.8.0
```

**Validação:**
```bash
pip install -r requirements.txt
python -c "import anthropic; print('OK')"
```

**Commit:** `chore: estrutura inicial do repositório`

---

### Passo 3 — Configuração e variáveis de ambiente

**Arquivo:** `config.py`

```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
OMIE_V3_BASE_URL     = os.getenv("OMIE_V3_BASE_URL", "http://localhost:8765")
OMIE_V3_JWT_SECRET   = os.getenv("OMIE_V3_JWT_SECRET")
EVOLUTION_API_URL    = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY    = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_INSTANCE   = os.getenv("EVOLUTION_INSTANCE", "orizon-central")
SCHEDULER_INTERVAL_H = int(os.getenv("SCHEDULER_INTERVAL_HOURS", "2"))
PORT                 = int(os.getenv("PORT", "8766"))
DEBUG                = os.getenv("DEBUG", "false").lower() == "true"
```

**Validação:**
```bash
cp .env.example .env
# Preencher .env com valores reais
python -c "from config import ANTHROPIC_API_KEY; print('Config OK')"
```

---

## Bloco C — Backend do agente

### Passo 4 — Módulo db_reader.py

Consome os endpoints do Omie_V3. Nenhuma escrita, apenas GET.

**Validação:**
```bash
python -c "
from db_reader import get_pendencias
p = get_pendencias()
print(f'Pendências encontradas: {len(p)}')
"
```

---

### Passo 5 — Módulo auth.py

Valida JWT do Omie_V3 e retorna perfil do usuário.

**Validação:**
```bash
# Obter token válido do Omie_V3 e testar:
python -c "
from auth import validar_token
perfil = validar_token('{token_do_omie_v3}')
print(perfil)
"
```

---

### Passo 6 — System prompt e agent_core.py

Criar `prompts/system_prompt.txt` com o prompt base da secretária.
Implementar `agent_core.py` com a função `chat(user_message, session_id, user_profile)`.

**Validação:**
```bash
python -c "
from agent_core import chat
resposta = chat(
    'Quais negociações estão paradas?',
    session_id='teste',
    user_profile={'nome': 'Marcelo', 'cargo': 'Diretor', 'loja': 'todas'}
)
print(resposta)
"
```

**Critério:** Resposta deve citar dados reais do Omie_V3, não dados inventados.

---

### Passo 7 — Servidor HTTP (main.py)

Implementar servidor na porta 8766 com rotas:

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/` | Serve `static/index.html` |
| `GET` | `/health` | `{"status": "ok"}` |
| `POST` | `/api/chat` | Recebe mensagem, retorna resposta do agente |
| `GET` | `/api/pendencias` | Lista pendências para o painel |

**Validação:**
```bash
python main.py &
curl http://localhost:8766/health
curl -X POST http://localhost:8766/api/chat \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"message": "Bom dia, quais são as pendências de hoje?"}'
```

**Commit:** `feat(ep08): backend do agente — chat e leitura de dados`

---

## Bloco D — Frontend

### Passo 8 — HTML base e sidebar

Criar `static/index.html` com a estrutura do painel:
- Sidebar com navegação e lojas
- Topbar com status do agente
- Área de chat
- Input com botão de voz e enviar

Paleta obrigatória: `#2C1F0E`, `#9C7A3C`, `#C4A265`, `#FAF6F0`

**Validação:** Abrir `http://localhost:8766` no browser. Layout deve corresponder ao protótipo aprovado.

---

### Passo 9 — Módulo de chat (chat.js)

Implementar envio de mensagens, renderização de bolhas e cards de pendências.

**Validação manual:**
1. Digitar "Quais negociações estão paradas?" → Agente responde com dados reais
2. Clicar em "Ver detalhes" na barra de alertas → Lista de pendências aparece

---

### Passo 10 — Módulo de voz (voice.js)

Implementar Web Speech API (entrada) e Speech Synthesis (saída).

**Validação manual:**
1. Clicar no microfone → Falar "quais são as pendências hoje" → Texto aparece no campo
2. Enviar → Resposta do agente é lida em voz alta em pt-BR

**Atenção:** Testar no Chrome — Firefox tem suporte limitado à SpeechRecognition.

**Commit:** `feat(ep08): frontend — chat e voz`

---

## Bloco E — Alertas proativos

### Passo 11 — Evolution API no VPS

Instalar e configurar Evolution API via Docker:

```bash
# No VPS
docker compose up -d evolution-api
# Escanear QR Code para conectar WhatsApp
curl http://localhost:8080/instance/connect/orizon-central
```

**Validação:**
```bash
# Enviar mensagem de teste
curl -X POST http://localhost:8080/message/sendText/orizon-central \
  -H "apikey: {sua_api_key}" \
  -H "Content-Type: application/json" \
  -d '{"number": "5512999999999", "text": "Teste de conectividade Orizon ✓"}'
```

---

### Passo 12 — notifier.py

Implementar envio de alertas via Evolution API.

**Validação:**
```bash
python -c "
from notifier import enviar_alerta
ok = enviar_alerta('5512999999999', 'Teste de alerta Orizon')
print('Enviado:', ok)
"
```

---

### Passo 13 — scheduler.py

Implementar varredura periódica com APScheduler.

**Validação:**
```bash
# Forçar execução manual da varredura
python -c "
from scheduler import verificar_pendencias
verificar_pendencias()
print('Varredura concluída — verifique o WhatsApp e o log_alertas')
"
```

**Regra anti-spam:** Verificar que a tabela `log_alertas` registra o envio e bloqueia reenvio em < 24h.

**Commit:** `feat(ep08): scheduler e alertas WhatsApp`

---

## Bloco F — Deploy no VPS

### Passo 14 — Serviço systemd

```bash
# /etc/systemd/system/secretaria.service
[Unit]
Description=Secretaria Orizon
After=network.target omie_v3.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/secretaria_orizon
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
EnvironmentFile=/home/ubuntu/secretaria_orizon/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable secretaria
sudo systemctl start secretaria
sudo systemctl status secretaria
```

**Validação final:**
```bash
curl http://167.88.33.121:8766/health
# {"status": "ok"}
```

**Commit:** `chore: deploy systemd no VPS — v0.5.0`

---

## Checklist final antes de considerar MVP concluído

- [ ] Passo 1 — Endpoints Omie_V3 funcionando
- [ ] Passo 3 — .env configurado no VPS
- [ ] Passo 6 — Agente respondendo com dados reais
- [ ] Passo 7 — Servidor HTTP na porta 8766
- [ ] Passo 9 — Chat funcionando no browser
- [ ] Passo 10 — Voz funcionando no Chrome
- [ ] Passo 11 — Evolution API conectada ao WhatsApp
- [ ] Passo 13 — Scheduler rodando e enviando alertas
- [ ] Passo 14 — Serviço systemd ativo no VPS
- [ ] Todos os critérios de aceite (CA-01 a CA-08) validados

---

## Notas para o Claude Code

- Usar Python 3.12 (mesmo do Omie_V3)
- Não instalar dependências globais sem `--break-system-packages`
- Nunca commitar o arquivo `.env`
- Validar cada passo via curl antes de avançar
- Um problema por vez — não tentar corrigir múltiplos bugs simultaneamente
- Registrar bugs abertos no DEV_LOG.md com identificador `BUG-EP08-XX`
