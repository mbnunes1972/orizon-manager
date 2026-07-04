# CLAUDE.md — Orizon Manager | Dalmóbile

Instruções carregadas automaticamente pelo Claude Code. Regras completas de processo estão em
`DEV_RULES.md`; **estado atual e histórico** em `DEV_LOG.md` (comece pela seção `## ⏸️ ESTADO ATUAL`,
no fim); requisitos em `REQUIREMENTS.md`; specs de design em `docs/superpowers/specs/`.

## O que é
Sistema de vendas de móveis planejados (loja Dalmóbile). **Backend** Python puro com `http.server`
(sem framework), SQLAlchemy + SQLite (`orizon.db`). **Frontend** é um único arquivo `static/index.html`
(HTML+CSS+JS inline). Multi-loja/rede (tenancy). Ciclo do projeto em etapas.

## Ambiente e execução
- Use **`python3`** (nunca `python`). WSL/Ubuntu.
- Servidor local: `python3 main.py` → `http://localhost:8765` (bind `127.0.0.1`; em produção
  `ORIZON_HOST=0.0.0.0`). A mensagem `gio: ... Operation not supported` no start é inofensiva.
- **`static/index.html` é lido do disco a cada request** → mudança de frontend = só **Ctrl+F5**, sem
  restart. Mudança em **Python** (`main.py`/módulos) **exige restart** do servidor.

## Testes (rodar ANTES de commitar/mergear)
- Backend: **`python3 -m pytest -q`** (deve ficar tudo verde). Siga TDD nos módulos Python.
- Frontend: **não há teste JS** → verificação manual no navegador. Para sintaxe, extrair o
  `<script>` e rodar `node --check`.

## Git — o que commitar
- Branch `main`. Commits descritivos (pt-BR): `feat(...)`, `fix(...)`, `docs: ...`.
- **NÃO commitar ruído** (já modificado no working tree desde o início, ignorar sempre):
  `orizon.db`/`*.bak*`, `perfis_config.json`, `.gitignore`, `XML/…`, `.claude/…`, `~$*.docx`, `*.tmp`.
  **Sempre `git add` só os arquivos da mudança** (nunca `git add .`).
- Push: as credenciais do GitHub estão no Git Credential Manager (do usuário) — o push funciona; se
  falhar por credencial, peça ao usuário rodar `!git push origin main`.

## Fechar uma frente (padrão do projeto)
1. Suíte verde. 2. Atualizar **DEV_LOG** (nova `## Sessão N`) e o spec em `docs/superpowers/specs/`.
3. `git add <arquivos> && git commit`. 4. Merge na `main` (ou já está, se commitou direto). 5. `git
push origin main` (atualiza o "servidor web" = GitHub). 6. **Re-ingerir o grafo MCP** (`ingerir`
com `fonte: "all"`, ou `POST http://localhost:8767/ingest/all`) para o grafo refletir o código novo.
Deploy no VPS: runbook em `DEV_RULES.md`.

## MCP `orizon` (grafo Neo4j) — camada de consulta, NÃO substitui o DEV_LOG
Grafo Neo4j que ingere código + requisitos + banco + decisões (projeto `../mcp-orizon`; container
docker-compose já de pé, config em `.mcp.json`). Responde consultas estruturais: `cobertura`
(requisitos/etapas sem uso), `rastrear_requisito`, `impacto_de`, `decisoes_de`, `buscar`,
`entidades_do_arquivo`. **É derivado do código e local (fora do git)** → fica obsoleto se não
re-ingerir, e some com `docker compose down -v`. Por isso o **DEV_LOG continua sendo a fonte
narrativa** (estado, backlog, decisões+porquê, histórico) — o grafo complementa, não aposenta.
Controle de versão segue 100% no **git**. Após mergear mudança relevante, **re-ingerir** (passo 6
acima). Antes de fechar frente, vale rodar `cobertura`/`rastrear_requisito` para pegar requisito sem
implementação.

## Áreas sensíveis (contexto que evita retrabalho)
- **Contrato:** HTML (capa) + Markdown (cláusulas) → **PDF via WeasyPrint** (assets em
  `contrato_template/`). `weasyprint` 69 no user-site do `python3.14`. O caminho `.docx`/LibreOffice do
  contrato foi **aposentado**; a **proposta** ainda usa docx/LibreOffice.
- **Negociação/motor:** cálculo puro em `mod_negociacao.py` / `mod_provisoes.py`; a tela lê do motor via
  `negPreview`/`_aplicarPreviewNaTela`. Dois caminhos de ambientes: **EP07** (`_orcAmbientesAtivos !=
  null`, orçamento moderno, valores do motor) vs **legado**. **`_negBaseValues` nunca é populado**
  (sempre `[]`) — não confie nele; use o motor/preview (`_previewNeg.VBNO`, `neg-subtotal`).
- **Ciclo:** etapas em `mod_ciclo.py` (frontend `ETAPAS_CICLO`). Etapas 5/6 foram eliminadas
  (Orçamento 4 → Contrato 7). `_contrato_assinado` (1ª assinatura) vs `_contrato_totalmente_assinado`
  (ambas).
- **Escopo por projetista:** Consultor vê só os projetos que criou (`projetos_meta.criado_por_id`);
  gerente+ veem todos.

## Dicas de modelo
Para **lógica financeira intrincada** (ex.: cálculo reverso da negociação), o **Fable 5** rende — pode
ser chamado pontualmente via subagente sem trocar o modelo da sessão. Opus/Sonnet dão conta do resto.
