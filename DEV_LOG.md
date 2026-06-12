# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-12 (sessão 5)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- Projeto vinculado a cliente obrigatório
- Lista de projetos ordenada com busca
- EP-07 completo: upload, pool, orçamentos, cálculos, desconto individual, limites

### [EP-07] Estado atual do versionamento de orçamentos

**Backend — 100% funcionando:**
- Tabelas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes`
- Criar projeto → Orçamento 1 criado automaticamente ✓
- Upload XML → apenas sistema pool (EP-07); `/ambientes/adicionar` somente para modo legado ✓
- Arquivo salvo no disco SOMENTE após `db.commit()` bem-sucedido (4 endpoints) ✓
- Detecção de duplicata (Sobrescrever / Nova versão) ✓
- Painel pool com status `incluido: true/false` ✓
- Adicionar/remover ambiente com recálculo ✓
- Criar novo orçamento ✓ | Renomear: `PUT /projetos/<nome>/orcamentos/<oid>` ✓
- Cards de projeto: `n_ambientes`/`n_selecionados` lidos do pool via `_enriquecer_projetos_com_pool()` ✓

**Interface — 100% funcionando:**
- Barra de orçamentos com abas, troca de aba, renomear inline ✓
- Painel "Ambientes ▾" com checkbox incluído/disponível ✓
- Upload XML: nenhum arquivo salvo em disco antes da confirmação do usuário ✓
- Tecla Esc fecha qualquer modal ativo sem salvar ✓

**Cálculo de negociação EP-07 — 100% funcionando:**
- Parâmetros (margens, desconto, custos, impostos): compartilhados por projeto ✓
- Base de cálculo: sempre os ambientes do orçamento ativo ✓
- Sequência: `bruto` (gross-up) → `avista` (−desc_global% −desc_individual%) → `final` (÷(1−fin%))
- `neg-subtotal` = bruto gross-up | `neg-avista` = à vista | `neg-total` = com financiamento ✓
- **Desconto individual por ambiente** (EP-07): coluna "Desc.%" editável na tabela ✓
  - Chave em `_descIndividual`: `'ep07_'+pa.id` (não colide com legado por nome de arquivo)
- Modal de parâmetros EP-07: painel de apoio considera desconto individual por ambiente ✓
- Discriminação por ambiente EP-07: usa `_orcAmbientesAtivos` + desconto efetivo combinado ✓
- Cartão/VP: gross-up via `_acrescimoFin` na tabela ✓
- Aymoré/TF: `_ep07DistribuirFinanciado(totalCliente, totalAvista)` ✓
- Painéis de pagamento atualizam ao trocar aba ou alterar parâmetros ✓
- **Limite de desconto total: 35%** sobre bruto original dos XMLs ✓
  - Bloqueia save de parâmetros; reverte desconto individual em tempo real

### [PENDENTE]
- Bug toggle "incluir custos adicionais" (da sessão 2) — ainda em aberto
- Total Flex (US-14) — planejado para v0.2.0

### [DECIDIDO]
- Pool de ambientes permanente por projeto (XMLs nunca deletados)
- Upload EP-07: somente `/pool` (sem `/ambientes/adicionar`) — arquivo salvo após commit
- Pergunta Sobrescrever/Nova versão = apenas quando usuário quer ATUALIZAR o arquivo XML
- Múltiplos orçamentos paralelos, todos editáveis
- Desconto total máximo: 35% de (bruto_original − líquido) / bruto_original
- Banco: SQLite + SQLAlchemy
- Servidor DEV: `167.88.33.121:8765`
- GitHub: `https://github.com/mbnunes1972/omie_v3`

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, todas as rotas; `_enriquecer_projetos_com_pool()` enriquece listagens
- `database.py` — SQLAlchemy: `Usuario`, `Sessao`, `LogAutorizacao`, `Cliente`, `Parceiro`, `PoolAmbiente`, `Orcamento`, `OrcamentoAmbiente`
- `static/index.html` — frontend SPA completo
- `PROJETOS/*/projeto.json` — dados persistidos de cada projeto (legado; EP-07 usa banco)

**Variáveis JS chave EP-07:**
- `_orcamentos` — lista de orçamentos do projeto ativo
- `_orcamentoAtivoId` — ID do orçamento sendo visualizado
- `_orcAmbientesAtivos` — ambientes do orçamento ativo (null = modo legado)
- `_descIndividual` — `{ chave: pct }` desconto individual; EP-07 usa `'ep07_'+pa.id`
- `_margemAtual` — desconto total % atualizado por `mpAtualizarApoio()`; base do limite 35%
- `_LIMITE_DESC_TOTAL` — constante `35`
- `carregarOrcamentos()` — busca GET /projetos/<nome>/orcamentos
- `ativarOrcamento(id)` — troca aba e chama GET /orcamentos/<id>/ambientes
- `abrirPainelPool()` — abre modal com GET /projetos/<nome>/pool?orcamento_id=<oid>
- `uploadXmls()` — em modo EP-07 usa exclusivamente POST /projetos/<nome>/pool

---

## HISTÓRICO

### Sessão 2026-06-12 (sessão 5 — bugs EP-07 + desconto individual + limites + UX)
**Commits:** `5ccb96d`, `019eb6b`, `b6e8d3f`, `74a4710`, `5349427`, `f1a0c30`

**Bugs corrigidos:**
- **BUG-EP07-03:** `uploadXmls` em modo EP-07 não chama mais `/ambientes/adicionar`. Arquivo salvo no disco somente após `db.commit()` bem-sucedido (endpoints: pool/novo, sobrescrever, nova_versao, criar_forcado)
- **Cards 0 ambientes:** `_enriquecer_projetos_com_pool()` em `main.py` sobrescreve `n_ambientes`/`n_selecionados` com contagem real do banco para projetos EP-07
- **Painel de apoio modal EP-07:** `mpAtualizarApoio` agora faz loop per-ambiente e aplica `_descIndividual` antes de somar
- **Discriminação por ambiente EP-07:** `atualizarDiscriminacao` usava `projetoAtivo.ambientes` (vazio); corrigido para usar `_orcAmbientesAtivos` com desconto efetivo combinado

**Funcionalidades adicionadas:**
- **Desconto individual por ambiente (EP-07):** coluna "Desc.%" com input editável na tabela de negociação. Fórmula: `avista = bruto × (1−desc_global%) × (1−desc_individual%)`
- **Limite de 35% no desconto total:** `_margemAtual` atualizado por `mpAtualizarApoio`; bloqueia save de parâmetros; reverte desconto individual via `_onDescIndBlur`
- **Esc fecha modal ativo:** listener global percorre modais do z-index mais alto ao mais baixo e chama a função de cancelar do primeiro visível (15 modais cobertos)

---

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
