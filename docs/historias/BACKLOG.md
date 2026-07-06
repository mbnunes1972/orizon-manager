# Histórias de Usuário — Orizon Manager

> Versão de referência: **v0.2.0** | Junho 2026 — atualizado 2026-07-06
> Repositório: [github.com/mbnunes1972/orizon-manager](https://github.com/mbnunes1972/orizon-manager)

**Convenções de status:**
- `[IMPLEMENTADO]` — funcionalidade concluída e testada
- `[BUG CONHECIDO]` — implementada mas com comportamento incorreto documentado
- `[PLANEJADO]` — especificada, ainda não implementada

---

## Índice

- [EP-01 — Autenticação e Controle de Acesso](#ep-01--autenticação-e-controle-de-acesso)
- [EP-02 — Integração Promob → Omie](#ep-02--integração-promob--omie)
- [EP-03 — Negociação e Cálculo de Margens](#ep-03--negociação-e-cálculo-de-margens)
- [EP-04 — Módulos Financeiros](#ep-04--módulos-financeiros)
- [EP-05 — Cadastro de Clientes e Parceiros](#ep-05--cadastro-de-clientes-e-parceiros)
- [EP-06 — Infraestrutura e Deploy](#ep-06--infraestrutura-e-deploy)
- [EP-07 — Versionamento de Orçamentos](#ep-07--versionamento-de-orçamentos)
- [EP-08 — Sincronização Omie e Painel Admin](#ep-08--sincronização-omie-e-painel-admin)
- [EP-09 — Lista de Projetos e Pipeline de Vendas](#ep-09--lista-de-projetos-e-pipeline-de-vendas)
- [EP-10 — Reconciliação do Ciclo (lacunas 38 etapas ↔ implementado)](#ep-10--reconciliação-do-ciclo-lacunas-38-etapas--implementado)

---

## EP-01 — Autenticação e Controle de Acesso

> Sistema de login, perfis de usuário e hierarquia de permissões.

---

### US-01 — Login no sistema `[IMPLEMENTADO]`

**Como** consultor, gerente ou diretor,  
**quero** acessar o sistema com usuário e senha,  
**para que** apenas usuários autorizados utilizem a plataforma.

**Critérios de aceite:**
- Tela de login com campos de usuário e senha
- Autenticação via cookie de sessão (token hex-32, server-side)
- Redirecionamento automático ao sistema após login bem-sucedido
- Mensagem de erro clara em caso de credenciais inválidas
- Sessão mantida entre recarregamentos de página

---

### US-02 — Logout seguro `[IMPLEMENTADO]`

**Como** usuário autenticado,  
**quero** encerrar minha sessão,  
**para que** nenhum acesso não autorizado ocorra ao deixar o computador.

**Critérios de aceite:**
- Botão de logout visível na interface
- Sessão invalidada no servidor ao fazer logout
- Redirecionamento para a tela de login após logout

---

### US-03 — Perfil de usuário com foto `[IMPLEMENTADO]`

**Como** usuário autenticado,  
**quero** visualizar meu nome, perfil e foto na sidebar,  
**para que** tenha uma experiência personalizada e identifique rapidamente meu nível de acesso.

**Critérios de aceite:**
- Botão de perfil na sidebar exibindo nome e nível (Consultor / Gerente / Diretor)
- Upload de foto de perfil suportado
- Foto exibida na sidebar após upload
- Informações atualizadas sem necessidade de relogin

---

### US-04 — Limites de desconto por perfil `[IMPLEMENTADO]`

**Como** sistema,  
**quero** aplicar limites de desconto diferentes por nível de usuário,  
**para que** descontos excessivos não sejam concedidos sem autorização.

**Critérios de aceite:**
- Consultor: limite máximo de **10%** de desconto
- Gerente: limite máximo de **20%** de desconto
- Diretor: limite máximo de **50%** de desconto
- Limite visível e aplicado tanto na sidebar quanto no modal de parâmetros
- Campo de desconto bloqueado ao atingir o limite do perfil

---

### US-05 — Autorização delegada de desconto `[IMPLEMENTADO]`

**Como** consultor ou gerente,  
**quero** solicitar autorização de um superior para aplicar desconto acima do meu limite,  
**para que** possa fechar negociações com flexibilidade sem burlar o controle de margens.

**Critérios de aceite:**
- Modal de autorização delegada ativado ao tentar exceder o limite
- Modal solicita login do superior (gerente ou diretor)
- Aprovação registrada no banco com: quem aprovou, quem solicitou, desconto aprovado, timestamp
- Desconto aprovado aplicado automaticamente após autorização
- Histórico de autorizações acessível para auditoria

---

## EP-02 — Integração Promob → Omie

> Importação de projetos do Promob via XML e exportação para o ERP Omie.

---

### US-06 — Importação de XML do Promob `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** carregar o arquivo XML exportado pelo Promob,  
**para que** os ambientes e valores do projeto estejam disponíveis para negociação.

**Critérios de aceite:**
- Upload de arquivo XML via interface
- Parsing correto usando `BUDGET/@TOTAL` como preço de venda ao cliente
- Todos os 4 níveis de preço armazenados: `price_table`, `price_total`, `order_total`, `budget_total`
- Ambientes listados com seus respectivos valores
- Classificação dos itens em 16 grupos de produtos padronizados

---

### US-07 — Exportação de pedido para o Omie `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** exportar o pedido negociado diretamente para o Omie ERP,  
**para que** elimine retrabalho de digitação e garanta consistência dos dados.

**Critérios de aceite:**
- Cada grupo de produtos registrado no Omie com valor unitário R$1,00 e quantidade = subtotal do grupo
- Respeito ao limite de 240 requisições/minuto da API Omie
- Tratamento do HTTP 425 (rate-limit) com retentativa automática
- NCMs enviados sem pontuação (exigência da API)
- Endpoint correto: `IncluirPedVenda`

---

## EP-03 — Negociação e Cálculo de Margens

> Tela de negociação com cálculo de margens, descontos e custos internos.

---

### US-08 — Tela de negociação com ambientes `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** visualizar todos os ambientes do projeto com seus valores,  
**para que** conduza a negociação com o cliente de forma clara e organizada.

**Critérios de aceite:**
- Listagem de ambientes com valor final por ambiente
- Visual de terminal escuro (`bg #111d11`, `sidebar #0d160d`)
- Três rampas de cor: teal (valor líquido loja), âmbar (valor contratual cliente), coral (custos/taxas)
- Campo de desconto global aplicável a todos os ambientes
- Desconto individual por ambiente (coluna "Desc.%" editável na tabela) — EP-07 e legado
- Fórmula: `à vista = bruto × (1 − desc_global%) × (1 − desc_individual%)`
- Limite de desconto total de **35%** sobre o valor bruto original dos XMLs
  - Bloqueio no save de parâmetros; reversão automática no desconto individual

---

### US-09 — Toggle de custos adicionais `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** ativar ou desativar a inclusão de custos internos no preço ao cliente,  
**para que** controle se comissão de arquiteto, fidelidade, deslocamentos e brindes compõem o preço final.

**Critérios de aceite:**
- Toggle "Incluir custos adicionais?" visível na tela de negociação
- Quando ativado: custos internos fazem gross-up no preço ao cliente
- Quando desativado: custos internos não afetam o preço visível ao cliente
- Estado do toggle persistido corretamente entre aberturas do modal

---

### US-10 — Modal de parâmetros com snapshot/restore `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** ajustar parâmetros de margem e cancelar sem perder a configuração anterior,  
**para que** explore cenários de negociação sem comprometer os valores já definidos.

**Critérios de aceite:**
- Modal abre com snapshot dos valores atuais
- Botão Cancelar restaura o snapshot sem salvar alterações
- Botão Salvar persiste os novos valores
- Parâmetros incluem: margens por tipo, comissão arquiteto, programa fidelidade, custos de deslocamento, brindes

---

### US-11 — Custos internos não afetam preço ao cliente `[IMPLEMENTADO]`

**Como** sistema,  
**quero** garantir que custos internos nunca alterem o valor visível ao cliente,  
**para que** o preço de venda seja calculado apenas sobre as margens comerciais declaradas.

**Critérios de aceite:**
- Valor bruto calculado exclusivamente a partir da margem comercial
- Custos internos (comissão arquiteto, fidelidade, brindes, deslocamento) registrados separadamente como absorção da loja
- Tela exibe claramente: valor líquido da loja vs. valor contratual do cliente

---

## EP-04 — Módulos Financeiros

> Cálculo de condições de pagamento: Aymoré, Cartão de Crédito e Total Flex.

---

### US-12 — Financiamento Aymoré `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** calcular o valor ao cliente em financiamentos via Aymoré,  
**para que** ofereça condições parceladas precisas sem erro de margem.

**Critérios de aceite:**
- Input: `valor_avista` (o que a loja quer receber líquido)
- Fórmula: `financiado = (valor_avista - entrada) / (1 - taxa_retencao)`
- Entrada reduz o valor financiado (e portanto o custo ao cliente)
- Caso validado: 8x/20d/R$100k avista → total cliente **R$110.223,82**
- Com entrada R$20k → total cliente **R$108.179,05**

---

### US-13 — Cartão de Crédito `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** calcular o repasse ao cliente das taxas de cartão de crédito,  
**para que** preserve a margem líquida da loja em vendas parceladas no cartão.

**Critérios de aceite:**
- Input: `valor_avista` (o que a loja quer receber líquido)
- Taxa de retenção aplicada sobre o valor financiado
- Caso validado: 6x/R$10k → taxa 5,65%, total cliente **R$10.598,83**

---

### US-14 — Total Flex `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** oferecer um plano de parcelas flexíveis com juros compostos sobre saldo devedor,  
**para que** atenda clientes com necessidade de datas e valores personalizados.

**Critérios de aceite:**
- Parcelas com datas e valores editáveis livremente
- Juros compostos calculados sobre dias reais entre vencimentos
- Última parcela calculada automaticamente para zerar o saldo (campo de valor travado, data editável)
- Taxa mensal lida **exclusivamente pelo backend** (nunca exposta no frontend, variáveis JS, logs ou DevTools)
- Configuração da taxa em `config/total_flex.json` no servidor

---

## EP-05 — Cadastro de Clientes e Parceiros

> Módulos de registro e gestão de clientes e parceiros comerciais.

---

### US-15 — Cadastro de cliente `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** registrar os dados de um novo cliente,  
**para que** mantenha um banco de dados centralizado de prospects e clientes ativos.

**Critérios de aceite:**
- Campos: nome, CPF/RG, endereço (bairro, cidade), telefone, e-mail
- Campos agrupados na mesma linha onde fizer sentido (CPF+RG, Bairro+Cidade, Tel+Email)
- Validação de CPF
- Busca de cliente existente antes de criar novo registro
- Associação do cliente a projetos e negociações

> **📌 Nota:** Módulo iniciado via Claude Code; suspenso por erros de rota no backend e limite de contexto. Retomar na v0.2.0.

---

### US-16 — Cadastro de parceiro `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** registrar parceiros que indicam ou especificam projetos,  
**para que** rastreie a origem dos projetos e calcule comissões corretamente.

**Critérios de aceite:**
- Tipos: arquiteto, designer, decorador, corretor, engenheiro, indicador
- Campos específicos por tipo (ex: CAU/CREA para arquitetos e engenheiros)
- Associação de parceiro a projetos e pedidos
- Base para cálculo de comissionamento futuro

---

## EP-06 — Infraestrutura e Deploy

> Configuração do servidor, repositório e pipeline de deploy.

---

### US-17 — Deploy no VPS Hostinger `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** ter o Orizon Manager rodando em servidor acessível remotamente,  
**para que** a equipe da loja acesse o sistema sem depender da máquina local.

**Critérios de aceite:**
- Aplicação rodando no VPS Ubuntu 24.04 (IP `167.88.33.121`, porta `8765`)
- Servidor isolado do ArchDecorPoints (produção em servidor separado)
- Processo mantido via `screen` session
- Binding em `0.0.0.0` para acesso externo
- Credenciais Omie externalizadas (não hardcoded)

---

### US-18 — Workflow Git para deploy `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** um fluxo padronizado de push e deploy,  
**para que** atualizações cheguem ao servidor de forma controlada e rastreável.

**Critérios de aceite:**
- Repositório: `github.com/mbnunes1972/orizon-manager`
- Fluxo: `desenvolver local → testar local → git push → SSH servidor → git pull → restart`
- Tag `v0.1.0` criada como marco do estado atual
- Convenção: `v0.x.0` em desenvolvimento, `v1.0.0` na primeira loja em produção

---

### US-19 — Documentação de sessão contínua `[IMPLEMENTADO]`

**Como** desenvolvedor,  
**quero** manter documentação atualizada entre sessões de desenvolvimento com IA,  
**para que** retome o trabalho sem perder contexto e decisões anteriores.

**Critérios de aceite:**
- `DEV_RULES.md` — regras de desenvolvimento e convenções
- `DEV_LOG.md` — log cronológico de decisões e mudanças
- `REQUIREMENTS.md` — backlog de funcionalidades
- `docs/modulos/<modulo>/SPEC.md` — especificação por módulo
- Convenções aplicadas: `[IMPLEMENTADO]`, `[TODO]`, `[BUG]`, `[VALIDAR]`

---

## EP-07 — Versionamento de Orçamentos

> Pool de ambientes permanente por projeto, múltiplos orçamentos paralelos e editáveis para apresentação comercial.

---

### US-20 — Criar projeto com orçamento inicial `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** que ao criar um projeto o sistema já crie um orçamento vazio automaticamente,  
**para que** eu possa começar a adicionar ambientes imediatamente sem etapas extras.

**Critérios de aceite:**
- Ao criar projeto → Orçamento 1 criado automaticamente com nome padrão
- Pool de ambientes começa vazio
- Tela do projeto exibe o orçamento recém-criado pronto para uso

> **📌 Referência:** `docs/modulos/negociacao/VERSIONAMENTO.md`

---

### US-21 — Carregar XML com detecção de duplicata `[IMPLEMENTADO]`

**Como** consultor de vendas,  
**quero** que ao carregar um XML com nome já existente o sistema me pergunte se quero sobrescrever ou criar nova versão,  
**para que** eu controle qual versão do projeto do Promob está em cada orçamento.

**Critérios de aceite:**
- Se nome novo → ambiente entra direto no pool do projeto
- Se nome duplicado → modal com três opções: Sobrescrever, Nova versão, Cancelar
- Sobrescrever → atualiza pool e recalcula automaticamente todos os orçamentos que usam esse ambiente
- Nova versão → cria `Ambiente_v1` no pool; orçamentos existentes não são alterados
- Novo ambiente disponível no painel de Ambientes para adição manual
- **Upload EP-07 usa exclusivamente `/pool`** — arquivo salvo em disco somente após confirmação e commit no banco
- Se conteúdo igual com nome diferente → modal "Alterar nome" ou "Carregar assim mesmo"

---

### US-22 — Painel de ambientes no orçamento `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** um botão "Ambientes" na tela de negociação que exiba todos os ambientes disponíveis no pool do projeto,  
**para que** eu adicione ou remova ambientes do orçamento atual durante a negociação.

**Critérios de aceite:**
- Painel exibe todos os ambientes do pool com status: ✅ incluído / ⬜ disponível
- Marcar ambiente → adicionado ao orçamento, totais recalculados imediatamente
- Botão "Carregar XML" disponível dentro do painel
- Ambiente carregado via painel entra no pool e pode ser adicionado ao orçamento na mesma ação

---

### US-23 — Remover ambiente com confirmação `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** que ao desmarcar um ambiente o sistema me peça confirmação,  
**para que** eu não retire um ambiente por engano durante a apresentação ao cliente.

**Critérios de aceite:**
- Modal: *"Retirar 'X' deste orçamento?"* com botões Sim / Não
- Sim → remove do orçamento, totais recalculados
- Não → nenhuma ação, ambiente permanece incluído
- Ambiente removido do orçamento permanece disponível no pool

---

### US-24 — Criar orçamento paralelo `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** criar múltiplos orçamentos dentro de um projeto,  
**para que** apresente cenários diferentes ao cliente (completo, intermediário, entrada).

**Critérios de aceite:**
- Botão "Novo orçamento" na tela do projeto
- Modal solicita nome do orçamento antes de criar
- Novo orçamento criado vazio (sem ambientes), disponível imediatamente
- Todos os orçamentos editáveis em paralelo — sem bloqueio entre eles
- Orçamentos não podem ser deletados

---

### US-25 — Renomear orçamento `[PLANEJADO]`

**Como** consultor de vendas,  
**quero** dar nome a cada orçamento e editá-lo quando quiser,  
**para que** eu e o cliente identifiquemos facilmente cada cenário durante a negociação.

**Critérios de aceite:**
- Clique no nome do orçamento → campo de texto editável inline
- Salvo automaticamente ao perder o foco
- Nome visível na tela do projeto e no cabeçalho da tela de negociação

---

### US-26 — Sobrescrever ambiente atualiza todos os orçamentos `[PLANEJADO]`

**Como** sistema,  
**quero** que ao confirmar sobrescrita de um ambiente todos os orçamentos que o contêm sejam recalculados automaticamente,  
**para que** nenhum orçamento fique com dados desatualizados após revisão do projeto no Promob.

**Critérios de aceite:**
- Após sobrescrita: `budget_total` e `order_total` atualizados no pool
- Todos os orçamentos que referenciam o ambiente recalculados no mesmo request
- Resposta da API informa quantos orçamentos foram atualizados
- Nenhuma intervenção manual necessária pelo consultor

---

---

## EP-08 — Sincronização Omie e Painel Admin

> Registro automático de clientes no Omie ao cadastrar, painel de monitoramento e reprocessamento de falhas, e perfil de administrador do sistema.

---

### US-27 — Perfil Administrador `[IMPLEMENTADO]`

**Como** administrador do sistema,
**quero** acessar o sistema com um perfil separado dos perfis de vendas,
**para que** possa monitorar integrações, corrigir erros e gerenciar o sistema sem interferir nos fluxos comerciais.

**Critérios de aceite:**
- Nível `admin` no banco com acesso completo a vendas (limite de desconto 50%) e ao painel de administração
- Item `⚙ Admin` na sidebar visível apenas para usuários admin
- Page-07 (Painel Admin) acessível exclusivamente para role `admin`
- Criação de usuários admin diretamente no banco (sem interface de vendas)

---

### US-28 — Registro automático de cliente no Omie `[IMPLEMENTADO]`

**Como** sistema,
**quero** registrar o cliente no Omie automaticamente ao criar o cadastro local,
**para que** o cliente já exista no Omie quando o orçamento for aprovado, sem intervenção manual.

**Critérios de aceite:**
- Ao salvar cliente via `POST /api/clientes` → tenta `criar_cliente()` no Omie em background thread (não bloqueia a resposta HTTP)
- Sucesso → grava `omie_codigo` e `omie_sync_status = 'ok'`
- Sem CPF → `omie_sync_status = 'pendente'` com mensagem explicativa
- Sem credenciais Omie → `omie_sync_status = 'pendente'`
- Erro de API → `omie_sync_status = 'erro'` com mensagem do erro gravada em `omie_sync_erro`

---

### US-29 — Painel Admin: fila Omie e reprocessamento `[IMPLEMENTADO]`

**Como** administrador,
**quero** visualizar todos os clientes com falha ou pendência na sincronização com o Omie e reprocessá-los,
**para que** nenhum cliente fique sem registro no Omie sem que eu saiba.

**Critérios de aceite:**
- Painel exibe clientes com `omie_sync_status` = `erro` ou `pendente` (incluindo `null`)
- Cada entrada mostra: nome, CPF, status, mensagem de erro e timestamp
- Botão "Tentar" por entrada → chama `POST /api/admin/omie-sync/<id>/retry` (síncrono)
- Sucesso → linha removida da fila
- Erro → toast com mensagem, linha permanece para nova tentativa
- Botão "Atualizar" recarrega a fila

---

## EP-09 — Lista de Projetos e Pipeline de Vendas

> Visualização e gestão dos projetos em formato de tabela com pipeline de status comercial.

---

### US-30 — Lista de projetos em tabela `[IMPLEMENTADO]`

**Como** consultor de vendas,
**quero** ver todos os projetos em uma tabela com informações relevantes,
**para que** encontre rapidamente o projeto que preciso e tenha uma visão do portfólio.

**Critérios de aceite:**
- Tabela com colunas: Status | Data (última alteração) | Projeto | Cliente | Último Orçamento (valor)
- Filtro de texto único busca simultaneamente em nome do projeto, nome do cliente e CPF do cliente
- Ordenação padrão: data decrescente (mais recente primeiro)
- Duplo clique na linha ou botão "Abrir →" entra no projeto
- Ao abrir projeto: vai direto para o orçamento ativo na última visita (localStorage por projeto)

---

### US-31 — Pipeline de status por projeto `[IMPLEMENTADO]`

**Como** gerente de vendas,
**quero** classificar cada projeto com um status de pipeline,
**para que** acompanhe o avanço das negociações e identifique projetos em risco.

**Critérios de aceite:**
- Status disponíveis: `quente` / `morno` / `frio` / `perdido` (selecionáveis via dropdown inline na lista)
- `convertido`: setado automaticamente ao aprovar orçamento — não editável via dropdown
- `perdido`: grava `perdido_em` automaticamente; ao sair de "perdido", `perdido_em` é zerado
- Dropdown de status também disponível no cabeçalho da tela de negociação (page-02)
- Filtro multi-seleção por status na lista (OR lógico): pode selecionar 1, 2, 3 ou todos os status
- Botão do filtro exibe contagem dos status ativos quando não está "todos"

---

## EP-10 — Reconciliação do Ciclo (lacunas 38 etapas ↔ implementado)

> Lacunas identificadas na reconciliação entre o fluxo **canônico de 38 etapas**
> (`docs/referencia/01-fluxo-de-processos.md`) e o **ciclo implementado** (18 principais + 6 sub).
> Mapa completo em `docs/processos/FLUXO_38_ETAPAS.md`. Governança/faixas em
> `docs/ARQUITETURA-MODULOS.md`. São micro-etapas do canônico **sem casa** no ciclo atual.

---

### US-32 — Emissão da NFS-e de serviço de montagem `[PLANEJADO]`

**Como** Gerente Adm/Fin,  
**quero** emitir a **NF de serviço de montagem (NFS-e)** quando aplicável,  
**para que** a montagem/instalação seja faturada conforme o modelo fiscal da loja.

**Critérios de aceite:**
- Cobre a etapa canônica **34** (doc **D43** — NF de montagem por estado: SP/RJ/CE).
- Distinta da **NF-e de produto** (ciclo etapa 15); usa o contrato `EmissorFiscal.emitir_nfse_servico`
  (hoje `NotImplementedError`) — módulo **Fiscal**.
- Definir onde encaixa no ciclo (sub-etapa na Montagem/17 ou etapa própria pós-19).
- **Referência:** lacuna #1 da reconciliação. Entra no fechamento do módulo Fiscal.

---

### US-33 — Pós-entrega: follow-up, ocorrências e recompra `[PLANEJADO]`

**Como** Consultor / Marketing,  
**quero** registrar follow-up pós-entrega, ocorrências e indicações/recompra,  
**para que** o relacionamento pós-venda seja acompanhado e gere novas oportunidades.

**Critérios de aceite:**
- Cobre as etapas canônicas **36** (follow-up 7–15 dias) e **38** (indicação/recompra) — hoje **sem etapa**;
  a **37** (ocorrências) já é aproximada pela etapa 18 (Assistência pós Montagem).
- Definir se vira **etapa(s) do ciclo** (pós-20) ou funcionalidade do módulo **Pós-venda / CRM**.
- **Referência:** lacuna #2 da reconciliação.

---

### US-34 — Definir a posição da Aprovação Financeira (11d × Fase 3) `[PLANEJADO]`

**Como** Financeiro,  
**quero** que a aprovação financeira ocorra no ponto correto do fluxo,  
**para que** eu aprove a lista final consolidada no momento certo (antes de comprar).

**Critérios de aceite:**
- Decidir entre **manter no PE (11d — "antes de detalhar o PE")** ou **mover para pós-PE** (canônico
  **etapa 20 — "aprovar a lista consolidada antes da compra"**).
- Documentar a decisão; ajustar `ETAPAS_APROVACAO_FINANCEIRA` / gating em `mod_ciclo.py` se mudar.
- **Referência:** lacuna #3 (descompasso de posição). Decisão de negócio, não só de código.

---

### US-35 — Marcos de Conferência técnica e Transferência ao CD `[PLANEJADO]`

**Como** Conferente / Gerente Adm-Fin,  
**quero** marcos próprios para **Conferência técnica (19)** e **Transferência ao CD (22)**,  
**para que** esses controles — hoje achatados na etapa 12 (Implantação) — sejam rastreáveis.

**Critérios de aceite:**
- Avaliar **sub-etapas na 12** (ex.: 12a Conferência, 12b Transferência ao CD) **ou** manter achatado com
  checklist de documentos (D23/D24/D25/D26/D27).
- Não quebrar o gating sequencial (`mod_ciclo.py`).
- **Referência:** lacuna #4 da reconciliação.

---

*Documento mantido em `docs/historias/BACKLOG.md`*
*Atualizar a cada funcionalidade concluída ou nova história identificada.*
