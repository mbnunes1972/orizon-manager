# EP-08 — Histórias de Usuário: Secretária Orizon

> Adicionar ao final de `docs/historias/BACKLOG.md` do Orizon Manager

---

## EP-08: Secretária Comercial — Agente de IA

**Objetivo:** Criar um agente de IA que conhece o fluxo comercial Orizon, responde
perguntas da equipe via chat e voz, e envia alertas proativos via WhatsApp quando
negociações estão paradas além do prazo.

**Versão alvo:** v0.5.0  
**Repositório:** secretaria_orizon (novo, separado do Orizon Manager)  
**Dependência:** Endpoints EP-08 no Orizon Manager (ver US-30)

---

### US-27 — Acesso ao painel via token existente

**Como** membro da equipe Orizon já autenticado no Orizon Manager,  
**Quero** acessar o painel da Secretária sem fazer login novamente,  
**Para que** o acesso seja fluido e sem atrito.

**Critérios de aceite:**
- [ ] Token JWT do Orizon Manager é aceito pelo painel da Secretária
- [ ] Perfil do usuário (nome, cargo, loja) é carregado automaticamente
- [ ] Token expirado redireciona para login do Orizon Manager
- [ ] Sem campos de login/senha na Secretária

---

### US-28 — Chat com agente sobre pendências do fluxo

**Como** Gerente ou Diretor,  
**Quero** perguntar à Secretária quais negociações estão paradas,  
**Para que** eu possa agir rapidamente sem precisar navegar pelo sistema.

**Critérios de aceite:**
- [ ] Agente lista pendências com: cliente, fase, etapa, responsável, dias parados
- [ ] Resposta em < 5 segundos
- [ ] Dados são reais (vindos do Orizon Manager), não inventados
- [ ] Agente sugere próximo passo ao final da resposta
- [ ] Se não houver pendências, agente informa claramente

---

### US-29 — Consulta por voz

**Como** Consultor usando o sistema no tablet ou celular,  
**Quero** falar com a Secretária por voz,  
**Para que** eu não precise digitar enquanto atendo um cliente.

**Critérios de aceite:**
- [ ] Botão de microfone inicia captura de voz em pt-BR
- [ ] Texto reconhecido aparece no campo antes de enviar
- [ ] Usuário pode corrigir o texto antes de enviar
- [ ] Resposta do agente é lida em voz alta (TTS) quando voz foi usada
- [ ] Funciona no Chrome e Edge (desktop e mobile)

---

### US-30 — Endpoints de leitura no Orizon Manager

**Como** desenvolvedor do EP-08,  
**Quero** que o Orizon Manager exponha endpoints de leitura do fluxo comercial,  
**Para que** a Secretária consuma dados reais sem acessar o SQLite diretamente.

**Critérios de aceite:**
- [ ] `GET /api/v1/projetos/ativos` retorna lista com fase e dias parados
- [ ] `GET /api/v1/projetos/{id}/status_fluxo` retorna etapa detalhada
- [ ] `GET /api/v1/pendencias` retorna etapas com prazo vencido
- [ ] `GET /api/v1/usuarios/responsaveis` retorna mapa consultor → projetos → telefone
- [ ] Todos os endpoints exigem JWT válido
- [ ] Nenhum endpoint permite escrita (POST/PUT/DELETE bloqueados)

---

### US-31 — Visibilidade filtrada por perfil

**Como** Consultor,  
**Quero** ver apenas minhas próprias negociações no painel,  
**Para que** informações de outros consultores não vazem.

**Critérios de aceite:**
- [ ] Consultor vê apenas projetos onde é o responsável
- [ ] Gerente vê todos os projetos de sua loja
- [ ] Diretor vê todas as lojas
- [ ] Filtro aplicado no backend (não apenas no frontend)
- [ ] Tentativa de consultar projeto de outra loja retorna 403

---

### US-32 — Alertas proativos via WhatsApp

**Como** Gerente,  
**Quero** receber uma mensagem no WhatsApp quando uma negociação da minha loja
estiver parada além do prazo,  
**Para que** eu seja avisado mesmo sem abrir o sistema.

**Critérios de aceite:**
- [ ] Scheduler verifica pendências a cada 2 horas
- [ ] Alerta enviado quando prazo da etapa atual está vencido
- [ ] Mensagem inclui: cliente, fase, etapa, responsável, dias parados
- [ ] Mesmo alerta não reenviado em menos de 24 horas
- [ ] Falha no WhatsApp registrada no log, sem derrubar o sistema
- [ ] Alertas de consultores vão para o Gerente (não direto ao consultor — configurável)

---

### US-33 — Histórico de alertas enviados

**Como** Diretor,  
**Quero** consultar o histórico de alertas enviados pela Secretária,  
**Para que** eu saiba quais problemas foram sinalizados e quando.

**Critérios de aceite:**
- [ ] Aba "Alertas" no painel mostra log de notificações
- [ ] Cada registro mostra: data, cliente, fase, responsável, canal
- [ ] Filtrável por loja e por período
- [ ] Histórico persistido no banco local da Secretária (não no Orizon Manager)

---

### US-34 — Deploy no VPS junto ao Orizon Manager

**Como** desenvolvedor,  
**Quero** que a Secretária rode no mesmo VPS do Orizon Manager na porta 8766,  
**Para que** não haja custo adicional de infraestrutura.

**Critérios de aceite:**
- [ ] Processo Python na porta 8766 sobe via `systemd` (serviço `secretaria`)
- [ ] Evolution API sobe via Docker (`docker compose up -d`)
- [ ] Variáveis de ambiente em `.env` (não commitadas)
- [ ] Logs em `/var/log/secretaria/` com rotação diária
- [ ] Reinício automático em caso de crash (`Restart=always`)
- [ ] `GET /health` retorna `{"status": "ok"}` para monitoramento
