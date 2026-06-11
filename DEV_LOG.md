# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-10 (sessão 6)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- Projeto vinculado a cliente obrigatório
- Lista de projetos ordenada com busca
- EP-07 completo: Passos 1-11 + cálculos de negociação 100% funcionando

### [EP-07] Estado atual do versionamento de orçamentos

**Backend — 100% funcionando:**
- Tabelas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes`
- Criar projeto → Orçamento 1 criado automaticamente ✓
- Upload XML → pool ✓ | Duplicata → vincula ao orçamento ativo ✓
- Detecção de duplicata (Sobrescrever / Nova versão) ✓
- Painel pool com status `incluido: true/false` ✓
- Adicionar/remover ambiente com recálculo ✓
- Criar novo orçamento ✓ | Renomear: `PUT /projetos/<nome>/orcamentos/<oid>` ✓

**Interface — 100% funcionando:**
- Barra de orçamentos com abas, troca de aba, renomear inline ✓
- Painel "Ambientes ▾" com checkbox incluído/disponível ✓
- Upload XML: duplicata vincula com toast / remoção re-vincula ✓

**Cálculo de negociação EP-07 — 100% funcionando:**
- Parâmetros (margens, desconto, custos, impostos): compartilhados por projeto ✓
- Base de cálculo: sempre os ambientes do orçamento ativo ✓
- Sequência: `bruto` (gross-up) → `avista` (−desc%) → `final` (÷(1−fin%))
- `neg-subtotal` = bruto gross-up | `neg-avista` = à vista | `neg-total` = com financiamento ✓
- Modal de parâmetros: total e custos adicionais do orçamento ativo ✓
- Cartão/VP: gross-up via `_acrescimoFin` na tabela ✓
- Aymoré/TF: `_acrescimoFin = 0` + distribuição proporcional pós-cálculo ✓
  - `_ep07DistribuirFinanciado(totalCliente, totalAvista)` atualiza células + `neg-total` + `neg-total-final`
- Painéis de pagamento atualizam ao trocar aba ou alterar parâmetros ✓

### [PENDENTE]

Nenhum bug crítico conhecido. Próximos passos do EP-07 a definir (Passo 12+).

### [DECIDIDO]
- Pool de ambientes permanente por projeto (XMLs nunca deletados)
- Upload de XML já no pool = vincular ao orçamento ativo (não pergunta duplicata)
- Pergunta Sobrescrever/Nova versão = apenas quando usuário quer ATUALIZAR o arquivo XML
- Múltiplos orçamentos paralelos, todos editáveis
- Banco: SQLite + SQLAlchemy
- Servidor DEV: `167.88.33.121:8765`
- GitHub: `https://github.com/mbnunes1972/omie_v3`

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, todas as rotas
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`, `Cliente`, `Parceiro`, `PoolAmbiente`, `Orcamento`, `OrcamentoAmbiente`
- `static/index.html` — frontend SPA completo
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto

**Variáveis JS chave EP-07:**
- `_orcamentos` — lista de orçamentos do projeto ativo
- `_orcamentoAtivoId` — ID do orçamento sendo visualizado
- `_orcAmbientesAtivos` — ambientes do orçamento ativo (null = projeto sem EP-07)
- `carregarOrcamentos()` — busca GET /projetos/<nome>/orcamentos
- `ativarOrcamento(id)` — troca aba e chama GET /orcamentos/<id>/ambientes
- `abrirPainelPool()` — abre modal com GET /projetos/<nome>/pool?orcamento_id=<oid>
- `uploadXmls()` — faz POST /projetos/<nome>/pool com o XML

---

## HISTÓRICO

### Sessão 2026-06-10 (sessão 4 — EP-07 completo)
**Commit:** `79cec86` — feat: EP-07 versionamento de orcamentos completo (passos 1-12)

**Realizado:**
- EP-07 Versionamento de Orçamentos completo — todos os 12 passos implementados sem bugs
- Passos 1-8: backend (tabelas, rotas, pool, orçamentos, recálculo)
- Passos 9-12: interface (barra de orçamentos, painel Ambientes, novo orçamento, renomear)
- Modal de parâmetros corrigido para calcular sobre ambientes do orçamento ativo
- Upload de XML vincula automaticamente ao orçamento ativo quando ambiente já existe no pool
- Servidor DEV atualizado: `167.88.33.121:8765` rodando com screen

**Documento criado:**
- `docs/modulos/financeiro/FUTURO_CALCULO_FINANCEIRO.md`

**Pendente:**
- Bug toggle "incluir custos adicionais" (da sessão 2) — ainda em aberto
- Total Flex (US-14) — planejado para v0.2.0
- Módulo Clientes e Parceiros vinculados a orçamentos — planejado

### Sessão 2026-06-09 (sessão 3 — documentação)
- BACKLOG.md com 26 histórias (EP-01 a EP-07)
- 7 SPEC.md de módulos
- VERSIONAMENTO.md com spec completo do EP-07

### Sessão 2026-06-09 (sessão 2)
- Módulo Clientes completo
- Projeto vinculado a cliente obrigatório

### Sessão 2026-06-07/08 (sessão 1)
- Sistema de autenticação completo
- Módulo Parceiros
- Toggle custos adicionais
