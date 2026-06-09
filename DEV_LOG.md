# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-09 (sessão 2)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Botão de perfil na sidebar com foto, telefone, WhatsApp, email
- Autorização delegada: ao exceder limite, solicita credenciais de Gerente ou Diretor
- Limite autorizado = desconto específico aprovado (não o limite do perfil)
- Limite autorizado persiste durante a negociação, reseta ao trocar de projeto
- Desconto salvo no projeto vira limite autorizado ao reabrir
- Log de autorizações no banco (`log_autorizacoes`)
- Botão OK na sidebar para solicitar autorização de desconto
- Cancelar autorização restaura desconto anterior
- Modal de parâmetros: snapshot correto, restaura ao cancelar
- Toggle "Incluir custos adicionais?" no modal de parâmetros
- Valor bruto do cliente = valor original dos XMLs (parâmetros internos não afetam o cliente)
- Quando "Incluir custos adicionais?" ativo: gross-up aplicado ao valor bruto
- Desconto Total calculado sempre sobre valor bruto original dos XMLs
- Label "Desconto Total" (renomeado de "Desconto total s/ bruto")
- "A Vista" substituído por "1x" no select de parcelas
- Backend (`main.py`) salva `incluir_custos` no projeto.json
- **Módulo Clientes completo**: tabela `clientes` com endereço completo (CEP, logradouro, número, complemento, bairro, cidade, estado), busca por nome/CPF, busca automática de CEP via ViaCEP, máscara de telefone/WhatsApp, CRUD via modal
- **Duplo clique em cliente** abre modal "Cliente encontrado" com lista de projetos vinculados
- **Regras de unicidade**: nome duplicado mostra aviso "É homônimo?" com opção de ver cliente existente; CPF duplicado detectado no blur; modal "Cliente encontrado" mostra projetos e permite criar novo ou abrir existente
- **Projeto vinculado a cliente obrigatório**: `projeto.json` salva `cliente_id`; formulário exige seleção ou cadastro de cliente; botão "+ Cadastrar novo cliente" abre modal com nome pré-preenchido e auto-seleciona ao salvar
- **Módulo Parceiros completo**: tabela `parceiros` (nome, tipo, CPF/CNPJ, email, tel, wpp, comissão padrão, obs), busca por nome/CPF, CRUD via modal, verificação de homônimos, página própria no menu
- **Parceiro no projeto**: campo opcional no formulário de novo projeto (busca + chip + "+ Cadastrar novo parceiro"); `projeto.json` salva `parceiro_id`; ao abrir projeto, parceiro é carregado; ao abrir modal de parâmetros, comissão padrão do parceiro preenche automaticamente "Comissão arquiteto" se ainda não configurada
- **Lista de projetos ordenada**: projetos carregam automaticamente ao entrar na página (mais recente primeiro); botão ↑↓ inverte a ordem; campo de busca filtra/pesquisa; data de alteração exibida em cada card
- **"+ Novo ambiente" bloqueado**: botão só fica habilitado quando o usuário está na página de Negociação com um projeto aberto; ao navegar para Clientes/Parceiros/Projetos, o botão volta a ficar locked
- Documentos: DEV_RULES.md, DEV_LOG.md, REQUIREMENTS.md criados

### [PENDENTE]
- **ALTA** — Bug: toggle "Incluir custos adicionais?" não persiste corretamente entre aberturas do modal. Fluxo do bug: (1) marcar toggle → salvar → ok. (2) entrar/sair sem salvar → ok. (3) entrar novamente → toggle aparece desmarcado mesmo sem ação do usuário. Causa: `carregarMargensSalvas` recarrega do servidor após fechar o modal sem salvar, e o servidor retorna o JSON desatualizado. O `projetoAtivo.margens.incluir_custos` fica desatualizado. Arquivos relevantes: `static/index.html` funções `fecharModalParams`, `carregarMargensSalvas`, `abrirModalParams`; `main.py` rota `/projetos/<nome>/margens`.
- ~~**MÉDIA** — Implementar cadastro de Parceiros~~ **CONCLUÍDO**
- **MÉDIA** — Servidor DEV ainda sem domínio — acessível só por IP
- **BAIXA** — Criar script `deploy.sh` no servidor para automatizar git pull + sed + restart
- **BAIXA** — Projetos antigos (sem `cliente_id`) mostram cliente vazio no chip quando abertos — sem impacto funcional pois o nome ainda está em `projeto.cliente.nome`

### [PRÓXIMA TAREFA] Bug toggle incluir_custos + melhorias
**Modelo de dados (adicionar em database.py):**
```python
class Parceiro(Base):
    __tablename__ = "parceiros"
    id                  = Column(Integer, primary_key=True)
    nome                = Column(String(150), nullable=False)
    cpf_cnpj            = Column(String(18))
    tipo                = Column(String(30))  # arquiteto/designer/decorador/corretor/engenheiro/indicador
    email               = Column(String(120))
    telefone            = Column(String(20))
    whatsapp            = Column(String(20))
    comissao_padrao_pct = Column(Float, default=0.0)
    criado_em           = Column(DateTime, default=datetime.utcnow)
```

**Funcionalidades a implementar:**
- Página própria no menu ("Parceiros") — nova entrada na nav da sidebar
- Lista de parceiros com busca por nome ou CPF/CNPJ
- Formulário de cadastro/edição com todos os campos
- Ao criar/abrir projeto, vincular parceiro por nome ou CPF — se não existir, criar na hora
- `projeto.json` ganha campo `parceiro_id`
- Comissão padrão do parceiro preenche automaticamente o campo de comissão no modal de parâmetros

### [DECIDIDO]
- Banco: SQLite + SQLAlchemy (migração futura para MySQL)
- Limites: Consultor 10%, Gerente 20%, Diretor 50%
- Servidor DEV: `167.88.33.121:8765` (main.py usa 0.0.0.0 no servidor via sed -i após git pull)
- GitHub: `https://github.com/mbnunes1972/omie_v3`
- Parâmetros internos (arquiteto, fidelidade, viagem, brinde) nunca alteram valor do cliente
- Toggle "Incluir custos adicionais?" permite gross-up no valor bruto quando ativo
- Desconto Total sempre calculado sobre bruto original dos XMLs
- Foto e dados extras do perfil em localStorage (não no banco por ora)
- Autorização delegada registrada no banco mesmo quando negada
- Clientes e Parceiros são cadastros separados
- Um parceiro por projeto (pode expandir no futuro)
- Busca de cliente e parceiro por nome ou CPF

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, rotas (incluindo `/projetos/<nome>/margens` que salva `incluir_custos`)
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao` (adicionar `Cliente`, `Parceiro`)
- `auth.py` — login, logout, validação, autorização delegada
- `auth_routes.py` — rotas HTTP de autenticação
- `seed.py` — cria usuários iniciais
- `static/index.html` — frontend SPA completo
- `static/login.html` — tela de login
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto

**Variáveis JS chave:**
- `_usuarioAtual` — usuário autenticado (via `/api/auth/me`)
- `_LIMITES_NIVEL` — `{ consultor: 10, gerente: 20, diretor: 50 }`
- `_limiteAutorizado` — desconto específico autorizado (null = usa limite do perfil)
- `_mpSnapshot` — snapshot dos parâmetros ao abrir modal (restaura ao cancelar)
- `_resolveAutorizacao` — Promise resolver do modal de autorização (modal params)
- `_resolveAutorizacaoSidebar` — Promise resolver do modal de autorização (sidebar)
- `cfgGetDescontoMax()` — retorna `_limiteAutorizado` se existir, senão limite do perfil
- `calcularValorBrutoCliente(mg)` — calcula bruto com gross-up se `mg.incluir_custos`
- `mpRecalcularEstruturalModal()` — recalcula `_negBaseValues.estrutural` com toggles atuais
- `lerMargensNegociacao()` — lê margens do `projetoAtivo.margens` + toggle `incluir_custos` do modal se aberto

**Rotas de autenticação:**
- `GET /login`, `GET /logout`, `GET /api/auth/me`
- `POST /api/auth/login`, `POST /api/auth/logout`
- `POST /api/auth/verificar_desconto`, `POST /api/auth/autorizar_desconto`

---

## HISTÓRICO

### Sessão 2026-06-09
**Objetivo:** Corrigir e completar módulo de Clientes; vincular projeto a cliente obrigatório

**Realizado:**
- Diagnóstico: 34 processos Python acumulados na porta 8765 (SO_REUSEADDR) causavam 404 nas rotas de clientes — resolvido com kill de todos e reinício de instância única
- Migração do banco: tabela `clientes` não tinha colunas `cep`, `logradouro`, `numero`, `complemento`, `bairro` — `_migrar_colunas()` executada com sucesso
- Correção frontend: `numero` e `complemento` faltavam no payload de save (`cliSalvar`), na limpeza e preenchimento do modal de edição (`cliAbrirModal`)
- Máscara de telefone aplicada ao abrir modal de edição (dados já salvos no banco)
- `except Exception` adicionado à rota GET `/api/clientes/<id>` (era só `try/finally`)
- `db.query(Cliente).get()` substituído por `db.get(Cliente, ...)` (API SQLAlchemy 2.0)
- Formulário de novo projeto reformulado: chip de cliente selecionado, botão "+ Cadastrar novo cliente" que abre modal com nome pré-preenchido e auto-seleciona após salvar
- `criarProjeto()` agora exige `cliente_id` — não é mais possível criar projeto sem cliente
- Backend `/projetos/novo`: busca dados do cliente no banco pelo `cliente_id`, rejeita sem ele
- `_criar_projeto()` recebe e salva `cliente_id` no `projeto.json`
- `_listar_projetos()` expõe `cliente_id` nos resultados de busca
- DEV_LOG atualizado: próxima tarefa alterada de Clientes para Parceiros

**Arquivos modificados:**
- `main.py` — `/projetos/novo` exige `cliente_id`, busca cliente no DB
- `mod_omie.py` — `_criar_projeto` e `_listar_projetos` com `cliente_id`
- `static/index.html` — form novo projeto reformulado; funções `npBuscarCliente`, `npSelecionarCliente`, `npDeselecionarCliente`, `npAbrirCadastroCliente`, `criarProjeto`, `mostrarFormNovoProjeto`; correção `cliSalvar`, `cliAbrirModal` com `numero`/`complemento`
- `database.py` — já tinha o modelo completo (sessão anterior); `omie.db` migrado
- `DEV_LOG.md` — atualizado

### Sessão 2026-06-07 (continuação — 2026-06-08)
**Objetivo:** Implementar sistema de autenticação, perfis e controle de descontos

**Realizado:**
- Sistema de autenticação completo (database.py, auth.py, auth_routes.py, seed.py)
- Login/logout com cookie de sessão
- Botão de perfil na sidebar (foto, dados editáveis)
- Modal de autorização delegada com log
- Limites de desconto por nível aplicados no modal e na sidebar
- Botão OK na sidebar para solicitar autorização
- Toggle "Incluir custos adicionais?" no modal de parâmetros
- Correção do valor bruto (parâmetros internos não afetam cliente)
- Gross-up quando "Incluir custos adicionais?" ativo
- Desconto Total calculado sobre bruto original
- "1x" em vez de "A Vista" no select de parcelas
- DEV_RULES.md, DEV_LOG.md, REQUIREMENTS.md criados
- Bug pendente: toggle incluir_custos não persiste entre aberturas do modal
- Decisão: Clientes e Parceiros como cadastros separados

**Arquivos modificados:**
- `main.py` — autenticação integrada, bind 0.0.0.0, salva incluir_custos
- `static/index.html` — todas as features acima
- `static/login.html` — novo
- `database.py`, `auth.py`, `auth_routes.py`, `seed.py` — novos
- `DEV_RULES.md`, `DEV_LOG.md`, `REQUIREMENTS.md` — novos
- `omie.db` — banco SQLite criado

### Sessão 2026-06-07 (primeira)
- Descoberto servidor DEV com EasyPanel + ArchDecorPoints
- Criado repositório GitHub `mbnunes1972/omie_v3`
- Push do código local e clone no servidor
- App subindo via screen com `python3 main.py`
