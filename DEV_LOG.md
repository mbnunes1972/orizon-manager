# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-10 (sessão 4)

### [ESTADO] O que está funcionando
- App rodando em `http://167.88.33.121:8765` (servidor DEV) e `http://127.0.0.1:8765` (local)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Módulo Clientes completo com ViaCEP, máscaras, CRUD, unicidade
- Módulo Parceiros completo com tipos, comissão padrão, CRUD
- Projeto vinculado a cliente obrigatório
- Lista de projetos ordenada com busca
- EP-07 Passos 1-10 implementados (backend completo + interface parcial)

### [EP-07] Estado atual do versionamento de orçamentos

**Backend — 100% funcionando (validado via curl):**
- Tabelas criadas: `pool_ambientes`, `orcamentos`, `orcamento_ambientes`
- Criar projeto → Orçamento 1 criado automaticamente ✓
- Upload XML → ambiente vai para o pool ✓
- Detecção de duplicata (Sobrescrever / Nova versão) ✓
- Painel GET pool com status `incluido: true/false` ✓
- Adicionar ambiente ao orçamento ✓
- Remover ambiente com recálculo automático ✓
- Criar novo orçamento ✓
- Navegação entre orçamentos (barra de tabs) ✓

**Interface — parcialmente funcionando:**
- Barra de orçamentos com abas aparece ✓
- Barra oculta para projetos sem EP-07 ✓
- Trocar de aba carrega ambientes do orçamento ✓
- Botão "Ambientes ▾" abre painel do pool ✓
- Painel mostra ambientes com checkbox incluído/disponível ✓
- Remoção de ambiente com modal de confirmação ✓

### [PENDENTE — ALTA PRIORIDADE]

**BUG-EP07-01 — Upload de XML não vincula ao orçamento quando ambiente já existe no pool**

Fluxo com problema:
1. Cozinha.xml carregada no Orçamento 1 → OK
2. No Orçamento 2, tentar carregar Cozinha.xml novamente → sistema detecta duplicata mas NÃO vincula ao Orçamento 2

Comportamento correto:
- Se XML já está no pool → vincular automaticamente ao orçamento ativo (sem perguntar)
- A pergunta Sobrescrever/Nova versão só aparece quando o usuário quer ATUALIZAR o arquivo
- Upload de XML já existente no pool = "adicionar este ambiente ao orçamento atual"

**BUG-EP07-02 — Ambiente removido não pode ser re-adicionado via upload**

Fluxo com problema:
1. Carregar Cozinha.xml → vincula ao orçamento ✓
2. Remover Cozinha do orçamento ✓
3. Tentar carregar Cozinha.xml novamente → não vincula de volta

Causa provável: `uploadXmls` checa duplicata e para, sem tentar vincular ao orçamento atual.

**Correção necessária em `uploadXmls` (static/index.html):**
```javascript
if (dPool.ok && dPool.acao === 'criado') {
  // Novo ambiente → vincular ao orçamento ativo
  await fetch('/orcamentos/' + _orcamentoAtivoId + '/ambientes/' + dPool.ambiente.id, {method:'POST'});
} else if (dPool.ok && dPool.acao === 'duplicata') {
  // Já existe no pool → vincular ao orçamento ativo diretamente (sem modal)
  const rLink = await fetch('/orcamentos/' + _orcamentoAtivoId + '/ambientes/' + dPool.ambiente_existente.id, {method:'POST'});
  const dLink = await rLink.json();
  if (dLink.ok) {
    showToast('"' + dPool.ambiente_existente.nome_exibicao + '" adicionado ao orçamento.');
  } else if (dLink.erro === 'Ambiente já está neste orçamento') {
    showToast('"' + dPool.ambiente_existente.nome_exibicao + '" já está neste orçamento.', true);
  }
}
```

**BUG-EP07-03 (menor) — Passo 11 ainda não implementado**
Renomear orçamento inline (clique no nome → campo de texto → salvo ao perder foco)
Rota necessária: `PUT /projetos/<nome>/orcamentos/<oid>` com body `{"nome": "novo nome"}`

### [PRÓXIMA TAREFA] Corrigir BUG-EP07-01 e BUG-EP07-02, depois implementar Passo 11

**Sequência:**
1. Corrigir `uploadXmls` conforme correção acima
2. Testar: carregar XML já no pool → deve vincular ao orçamento ativo
3. Testar: remover ambiente → carregar XML novamente → deve vincular de volta
4. Implementar Passo 11: renomear orçamento inline

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

### Sessão 2026-06-10 (sessão 4 — EP-07 interface)
**Objetivo:** Implementar interface do EP-07 (Passos 10 e 11)

**Realizado:**
- Passos 1-9 validados via curl (backend completo)
- Passo 10: barra de orçamentos, troca de abas, painel de ambientes implementados
- Refatoração de renderTabelaNeg para aceitar ambientes direto do banco
- Bug FileList corrigido
- Painel "Ambientes ▾" implementado com checkboxes
- Remoção de ambiente com modal de confirmação funcionando
- Banco limpo de dados de teste (reset_ep07.py criado)
- Identificados BUG-EP07-01 e BUG-EP07-02 no upload de XML

**Pendente:**
- BUG-EP07-01 e BUG-EP07-02 (upload não vincula quando ambiente já no pool)
- Passo 11: renomear orçamento inline

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
