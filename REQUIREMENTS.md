# REQUIREMENTS.md — Requisitos do Sistema
## Orizon Manager | Dalmóbile
### Documento vivo — atualizar a cada decisão relevante

---

## 1. VISÃO GERAL

**Nome do sistema:** Orizon Manager (`Omie_V3` era o nome interno de desenvolvimento anterior; ver §1.1)
**Propósito:** Sistema de gestão comercial e operacional para redes de móveis planejados, cobrindo toda a jornada do cliente — do lead ao pós-entrega. O orçamento/negociação é feito **na própria plataforma**; a integração com o ERP Omie está sendo **repensada** e hoje mira a etapa fiscal (emissão de NFe), não mais o orçamento (ver §5.5).

**Usuários primários:** Consultores de Vendas, Gerentes, Diretores, Projetistas
**Usuários futuros:** Cliente (acompanhamento de projeto), Administrador de Rede, Financeiro de Rede

**Escopo atual (MVP):** Integração Promob → Omie com negociação de margens e controle de acesso por nível de usuário.

**Escopo futuro:** CRM completo cobrindo as 38 etapas do fluxo de processos Dalmóbile.

### 1.1 Nomenclatura
- **Marca / linha de produtos:** **Orizon**. Este produto é o **Orizon Manager** (a linha poderá ter outros produtos no futuro).
- `Omie_V3` / `omie_v3` era o nome interno de desenvolvimento; foi **substituído por Orizon Manager** em docs e código (jul/2026).

**Padrão adotado (forma por contexto):**

| Contexto | Forma | Exemplo |
|---|---|---|
| Nome do produto (texto/UI/docs) | `Orizon Manager` | títulos, banners, cláusulas |
| Diretório e repositório | `orizon-manager` (kebab) | `mbnunes1972/orizon-manager` |
| Identificador de código / screen / caminho | `orizon-manager` | `screen -S orizon-manager`, `/root/orizon-manager` |
| Banco de dados | `orizon.db` | `sqlite:///orizon.db` |
| Variáveis de ambiente | prefixo `ORIZON_` | `ORIZON_HOST`, `ORIZON_MANAGER_BASE_URL`, `ORIZON_MANAGER_JWT_SECRET` |

- **⚠️ Atenção crítica:** "Omie" **sem `_V3`** refere-se ao **ERP externo** e **NÃO** deve ser renomeado — inclui `mod_omie.py`, `OMIE_BLOQUEIO_425`, `omie_codigo`, `omie_sync_*`, `omie_config.json`, `omie_grupos_cache.json` e a "API Omie".
- **Pendente (mantenedor):** renomear o diretório local, o arquivo de banco em produção e o **repositório GitHub** (`omie_v3` → `orizon-manager`) — ver runbook em `DEV_RULES.md`.

---

## 2. ARQUITETURA

### 2.1 Implantação
- Cada loja terá sua própria instância do sistema
- Haverá uma instância superior para gestão de rede (CEO/Financeiro de Rede)
- Diretor de loja pode ter acesso a outras lojas mediante autorização do Diretor de Rede
- O sistema deve ser multi-tenant no futuro

### 2.2 Stack atual
- **Backend:** Python 3.12, HTTP server nativo (`http.server`)
- **Banco de dados:** SQLite + SQLAlchemy (migração futura para MySQL via troca de string de conexão)
- **Frontend:** HTML/CSS/JS puro (SPA), sem framework
- **Infraestrutura:** Hostinger VPS, Ubuntu 24.04, EasyPanel, Docker
- **Repositório:** GitHub (`mbnunes1972/orizon-manager` — renomeado de `omie_v3`; ver §1.1)

### 2.3 Integrações externas
- **Promob:** leitura de arquivos XML exportados pelo software
- **Omie ERP:** envio de pedidos de venda via API REST

---

## 3. PERFIS DE ACESSO

### 3.1 Perfis atuais

| Perfil | Limite desconto | Pode ver parâmetros | Observação |
|---|---|---|---|
| Consultor | 10% | Não | Acesso à negociação |
| Gerente | 20% | Sim | Pode autorizar até 20% |
| Diretor | 50% | Sim | Pode autorizar até 50% |

### 3.2 Perfis futuros (a definir)
- **Projetista** — permissões similares ao Consultor, poderá carregar Promob
- **Financeiro de Rede** — acesso amplo a todas as lojas, emissão de relatórios
- **Administrador de Rede (CEO)** — acesso total, criação de perfis administrativos
- **Cliente** — módulo de acompanhamento de projeto (fase futura)

### 3.3 Regras de acesso
- Desconto acima do limite exige autorização delegada (credenciais de Gerente ou Diretor)
- Autorização delegada é registrada em log com autorizador, solicitante, desconto e contexto
- Futuro: módulo de configuração de perfis permitirá definir acessos por módulo

---

## 4. FLUXO DE PROCESSOS (38 etapas)

Baseado no documento `1_FLUXO_DE_PROCESSOS.docx`. O sistema deve suportar e eventualmente automatizar as etapas abaixo.

### Fase 1 — Pré-venda (etapas 1–11)
| # | Atividade | Responsável | Documentos |
|---|---|---|---|
| 1 | Qualificação do lead | Marketing + Gerente | Ficha de Qualificação |
| 2 | Agendamento do briefing | Consultor | Registro de Agendamento |
| 3 | Briefing com cliente | Consultor | Roteiro de briefing |
| 4 | Briefing com arquiteto | Consultor | Projeto do Arquiteto |
| 5 | Desenvolvimento do projeto | Projetista | Arquivo Promob |
| 6 | Revisão interna | Gerente | Checklist de revisão |
| 7 | Apresentação ao cliente | Consultor | Proposta comercial |
| 8 | Ajustes de projeto | Projetista | Projeto revisado |
| 9 | Negociação e aprovação de desconto | Consultor + Gerente | Política de descontos |
| 10 | Fechamento do contrato | Consultor + Gerente | Contrato + Folha de Capa |
| 11 | Handoff para pós-venda | Consultor → Conferente | Checklist de transferência |

### Fase 2 — Medição e Projeto Executivo (etapas 12–18)
| # | Atividade | Responsável |
|---|---|---|
| 12 | Agendamento da medição | Assistente Logístico |
| 13 | Medição in loco | Medidor |
| 14 | Validação da Planta de Pontos | Projetista Executivo |
| 15 | Desenvolvimento do projeto executivo | Projetista Executivo |
| 16 | Alinhamento projeto inicial × executivo | Projetista + Conferente |
| 17 | Aprovação pelo cliente | Projetista + Gerente |
| 18 | Assinatura do Projeto Executivo | Projetista + Conferente |

### Fase 3 — Conferência e Pedido (etapas 19–22)
| # | Atividade | Responsável |
|---|---|---|
| 19 | Conferência técnica | Conferente |
| 20 | Aprovação financeira | Conferente + Ger. Adm. Fin. |
| 21 | Implantação de pedidos | Conferente |
| 22 | Transferência ao CD | Ger. Adm. Fin. |

### Fase 4 — CD: Compra e Logística (etapas 23–28)
| # | Atividade | Responsável |
|---|---|---|
| 23 | Execução dos pedidos de compra | Ger. Adm. Fin. |
| 24 | Planejamento logístico | Ger. Adm. Fin. + Assist. Logístico |
| 25 | Recebimento e produção local | Assist. Logístico |
| 26 | Processamento e separação | Assist. Logístico |
| 27 | Agendamento da entrega | Assist. Logístico |
| 28 | Entrega no local do cliente | Assist. Logístico |

### Fase 5 — Montagem e Entrega Final (etapas 29–35)
| # | Atividade | Responsável |
|---|---|---|
| 29 | Briefing de montagem | Supervisor de Montagem |
| 30 | Execução da montagem | Montadores |
| 31 | Assistências em montagem | Supervisor de Montagem |
| 32 | Vistoria técnica parcial | Supervisor de Montagem |
| 33 | Vistoria final com cliente | Supervisor + Consultor |
| 34 | Emissão NF de montagem | Ger. Adm. Fin. |
| 35 | Encerramento no CRM | Assist. Logístico |

### Fase 6 — Pós-entrega (etapas 36–38)
| # | Atividade | Responsável |
|---|---|---|
| 36 | Follow-up pós-entrega | Consultor + Marketing |
| 37 | Tratamento de ocorrências | Assist. Logístico |
| 38 | Indicação e recompra | Marketing |

---

## 5. REGRAS DE NEGÓCIO

### 5.1 Projetos e versões
- Um projeto nasce no cadastro do cliente/lead, antes do XML Promob
- Cada revisão de projeto gera uma nova versão dos ambientes, mas não um novo projeto
- Log de alterações por versão (para auditoria e resolução de disputas)
- Para efeito de negociação, apenas a última versão é relevante
- O projeto pode ser particionado — cliente pode fechar parte dos ambientes agora e parte depois

### 5.2 Status do projeto
- **Negociação** — salvar orçamento mantém neste status
- **Aprovado** — aprovar orçamento avança para emissão de contrato
- **Faturar** (Omie) — transição entre aprovação, assinatura e liquidação financeira
- Cada partição de ambientes pode ter status independente

### 5.3 Clientes e CPF
- Cliente pode ser cadastrado no Orizon Manager ou no Omie
- Ao cadastrar, verificar CPF e nome contra os dois sistemas
- Se já existir: perguntar se é novo projeto ou continuação
- Sincronização bidirecional Orizon Manager ↔ Omie via API

### 5.4 Negociação — Regras de cálculo e persistência

**Valor bruto é intocável para o cliente:**
- Arquiteto, fidelidade, viagem e brinde são custos internos da loja
- Nunca alteram o valor que o cliente vê
- O cliente vê apenas: Valor bruto → menos Desconto de venda → mais Juros de financiamento = Valor final
- Os parâmetros internos reduzem a margem da loja e são exibidos apenas no painel de apoio interno

**Isolamento entre projetos:**
- Parâmetros de um projeto nunca contaminam outro
- Cada projeto tem seu próprio estado de negociação isolado
- Ao criar novo projeto, todos os parâmetros começam zerados e desligados

**Persistência da negociação:**
- Sem salvar, a negociação volta ao último estado salvo (botão "Salvar orçamento")
- Ao salvar parâmetros do modal, ficam guardados junto com o estado da negociação
- O modal de parâmetros é um subconjunto da negociação — salvar parâmetros = salvar negociação
- A última tela salva é sempre o ponto de partida de uma nova fase de negociação

**Limites de desconto autorizados:**
- Limites autorizados por gerente/diretor são persistidos no projeto
- O limite autorizado é o desconto específico aprovado, não o limite do perfil do autorizador
- Exemplo: Gerente autoriza 15% → novo limite para aquela negociação é 15% (não 20%)
- Se diretor autorizar depois 30% → novo limite passa a ser 30% (não 50%)
- O limite autorizado persiste enquanto o projeto estiver aberto
- Reseta ao trocar de projeto

**Separação de campos:**
- Campos do cliente: `desconto_pct`, `forma_pagamento`, `custo_financeiro_pct`
- Campos internos da loja: `comissao_arq_pct`, `comissao_arq_ativa`, `fidelidade_pct`, `fidelidade_ativa`, `custo_viagem`, `fora_da_sede`, `brinde`, `brinde_ativo`
- Campos internos nunca devem ser incluídos no valor exibido ao cliente

**Motor de negociação (`mod_negociacao`) — fonte única (cutover + faxina, jun/2026):**
- Todo o cálculo da negociação vive no **backend** (`mod_negociacao` + `mod_fin`); o frontend
  **não calcula** — só edita os insumos (auto-save) e **exibe** a saída do motor.
- Nomenclatura fechada (siglas): por orçamento `VBVO, CFO, VBNO, VAVO, Com_Arq, Pro_Fid, Cust_Via,
  Bri, Cust_Ad, Val_Liq, Desc_Tot, Markup, Cust_Fin, Val_Cont, Prov_Imp`; por ambiente
  `VBVA, CFA, VBNA, VAVA`. Definição completa em `docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md`.
- Insumos salvos = fonte de verdade: `parametros_json` (projeto), `orc.desconto_pct`, descontos
  por ambiente, `forma_pagamento`. O preview (`POST /api/orcamentos/<id>/negociacao-preview`) e os
  saves devolvem o **breakdown** do motor; `_aplicarPreviewNaTela` é o único exibidor no frontend.
- Persistência autoritativa: `valor_total = Val_Cont` e `valor_liquido = Val_Liq` são gravados pelo
  backend; o frontend não os envia. `Prov_Imp = %Carga_Trib × Val_Cont` (Val_Cont = VAVO + Cust_Fin).
- O desconto é único (editado só na tela de negociação; no modal de parâmetros é read-only).

**Bloqueio dos campos de imposto (apresentação):**
- Base tributária e provisão de impostos ficam **ocultas (🔒)** por padrão; o sistema calcula mas
  só revela mediante senha de **Diretor ou Gerente Administrativo-Financeiro** (capacidade
  `aprovar_financeiro`, via `POST /api/auth/liberar_impostos`). Liberação **não persistida** (recarregar
  re-bloqueia). É bloqueio de **apresentação** (esconder da vista do cliente), não sigilo criptográfico.

### 5.5 Documentos
- Sistema deve cobrar confirmação de documentos conforme fase avança
- Documentos mais importantes devem ser anexados obrigatoriamente
- Repositório de modelos de documentos (templates)
- 45 documentos mapeados no fluxo (D1–D45)

### 5.5 Integração Promob → Omie
> 🔄 **EM REVISÃO (jul/2026).** O problema original — montar o **orçamento** enviando o pedido de venda
> ao Omie — **não se aplica mais**: orçamento e negociação agora são feitos **dentro da plataforma
> (Orizon Manager)**. O que permanece em aberto é a etapa **fiscal futura**: a **emissão de NFe**, que
> será baseada na **NFe emitida pela fábrica** e processada **dentro do Omie**. A solução ainda será
> repensada (a modelar em várias questões); o texto abaixo fica como **referência histórica** até a
> nova especificação. Ver requisito futuro P9.
>
- XML do Promob é classificado em 16 grupos de produtos padronizados
- Cada grupo tem NCM fixo e é enviado ao Omie com valor unitário R$1,00 e quantidade = subtotal do grupo
- Rate limit da API Omie deve ser respeitado
- Endpoint principal: `IncluirPedVenda`
- Ambientes agrupados por `codigo_projeto` no módulo Projetos do Omie

---

## 6. BANCO DE DADOS

### 6.1 Tabelas implementadas

**`usuarios`**
- `id`, `nome`, `login`, `senha_hash`, `nivel` (diretor/gerente/consultor), `ativo`, `criado_em`

**`sessoes`**
- `id`, `token`, `usuario_id`, `criada_em`, `expira_em`, `ativa`

**`log_autorizacoes`**
- `id`, `solicitante_id`, `autorizador_id`, `desconto_solicit`, `desconto_limite`, `autorizado`, `contexto` (JSON), `criado_em`

### 6.2 Tabelas previstas (a implementar)

**`clientes`**
- `id`, `nome`, `cpf`, `email`, `telefone`, `whatsapp`, `endereco`, `omie_codigo`, `criado_em`, `atualizado_em`

**`projetos`**
- `id`, `cliente_id`, `nome`, `status` (lead/negociacao/aprovado/faturar/entregue), `consultor_id`, `gerente_id`, `loja_id`, `criado_em`, `atualizado_em`

**`versoes_projeto`**
- `id`, `projeto_id`, `numero_versao`, `xml_path`, `criado_em`, `criado_por`

**`ambientes`**
- `id`, `versao_id`, `nome`, `arquivo_xml`, `total_bruto`, `selecionado`, `status`

**`negociacoes`**
- `id`, `projeto_id`, `versao_id`, `desconto_pct`, `forma_pagamento`, `comissao_arq_pct`, `fidelidade_pct`, `custo_viagem`, `brinde`, `total_final`, `criado_em`

**`documentos`**
- `id`, `projeto_id`, `tipo` (D1–D45), `arquivo_path`, `status` (pendente/anexado/dispensado), `criado_em`

**`lojas`**
- `id`, `nome`, `cnpj`, `cidade`, `estado`, `omie_app_key`, `omie_app_secret`

---

## 7. PENDÊNCIAS DE DEFINIÇÃO

| # | Pendência | Prioridade |
|---|---|---|
| P1 | Módulo de configuração de perfis (definir acessos por módulo) | Futura |
| P2 | Módulo de acesso do cliente (acompanhamento de projeto) | Futura |
| P3 | Instância superior para rede de lojas (multi-tenant) | Futura |
| P4 | Sincronização bidirecional Orizon Manager ↔ Omie para clientes | Média |
| P5 | Repositório de modelos de documentos (D1–D45) | Média |
| P6 | Sistema de versionamento de projetos com log de alterações | Alta |
| P7 | Particionamento de ambientes por pedido | Alta |
| P8 | Migração SQLite → MySQL quando necessário | Futura |
| P9 | Emissão de NFe baseada na NFe da fábrica, processada dentro do Omie (nova integração fiscal — substitui o antigo objetivo de orçamento da §5.5) | A definir |
