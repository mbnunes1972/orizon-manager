# Decisões de Arquitetura — Orizon Manager

Registro de decisões técnicas importantes. Antes de reverter qualquer item, leia o contexto.

---

## ADR-001 — SQLite com SQLAlchemy em vez de MySQL direto
**Data:** 2026-06-07  
**Status:** Ativo

**Decisão:** Usar SQLite + SQLAlchemy para o banco de dados inicial.

**Contexto:** O sistema é usado por uma loja por vez. O volume de acessos simultâneos é baixo. MySQL exigiria configuração adicional no servidor.

**Consequência:** Migração futura para MySQL é simples — trocar a string de conexão. O resto do código não muda.

---

## ADR-002 — Servidor HTTP nativo Python sem framework
**Data:** 2026-06-07  
**Status:** Ativo

**Decisão:** Usar `http.server` nativo do Python em vez de Flask/FastAPI.

**Contexto:** O projeto já existia com essa estrutura. Migrar para um framework quebraria muito código existente.

**Consequência:** Rotas definidas manualmente no `do_GET` e `do_POST` do `main.py`. Ao adicionar novas rotas, seguir o padrão `elif path == "/rota":`.

---

## ADR-003 — Frontend SPA sem framework JavaScript
**Data:** 2026-06-07  
**Status:** Ativo

**Decisão:** Manter o frontend em HTML/CSS/JS puro sem React, Vue ou similar.

**Contexto:** O projeto já existia assim. A adição de um framework quebraria o código existente e aumentaria a complexidade.

**Consequência:** Toda a lógica de UI está em `static/index.html`. O arquivo é grande (~3500 linhas). Ao adicionar funcionalidades, seguir os padrões existentes de navegação (`goPage()`) e modais.

---

## ADR-004 — Autenticação por cookie de sessão server-side
**Data:** 2026-06-07  
**Status:** Ativo

**Decisão:** Usar cookie `omie_session` com token gerado no servidor, em vez de JWT.

**Contexto:** Sistema interno, não exposto publicamente. Simplicidade foi priorizada.

**Consequência:** Sessões ficam na tabela `sessoes` do banco. Expiração em 8 horas. Logout invalida o token no banco.

---

## ADR-005 — Parâmetros internos não afetam valor do cliente
**Data:** 2026-06-08  
**Status:** Ativo

**Decisão:** Comissão de arquiteto, fidelidade, viagem e brinde são custos internos da loja. O cliente vê apenas: Valor bruto → Desconto → Valor à vista → Juros financiamento = Total.

**Contexto:** Esses parâmetros reduzem a margem da loja mas não são repassados ao cliente como itens de linha. Opcionalmente podem ser incluídos no valor bruto via gross-up (toggle "Incluir custos adicionais?").

**Consequência:** `_negBaseValues[i].estrutural` = valor bruto original do XML por padrão. Quando "Incluir custos adicionais?" ativo, aplica gross-up: `bruto / (1 - arq%) / (1 - fid%) + viagem + brinde`.

---

## ADR-006 — Limite autorizado = desconto específico aprovado
**Data:** 2026-06-08  
**Status:** Ativo

**Decisão:** Quando um gerente autoriza 15%, o novo limite para aquela negociação é 15% — não 20% (limite do gerente).

**Contexto:** Evita que uma autorização pontual se torne uma permissão ampla.

**Consequência:** `_limiteAutorizado` recebe o valor do desconto aprovado, não o limite do perfil do autorizador. Persiste durante a negociação, reseta ao trocar de projeto.

---

## ADR-007 — Projetos persistidos em JSON, não no banco
**Data:** Antes de 2026-06-07  
**Status:** Ativo — [VALIDAR migração futura para banco]

**Decisão:** Cada projeto é salvo como `PROJETOS/<nome_safe>/projeto.json`.

**Contexto:** Decisão anterior ao início desta documentação. Permite portabilidade e inspeção manual.

**Consequência:** Projetos não estão no SQLite. Relacionamentos (cliente_id, parceiro_id) são campos dentro do JSON. Busca de projetos é feita lendo os arquivos do sistema de arquivos.

---

## ADR-008 — Um parceiro por projeto
**Data:** 2026-06-08  
**Status:** Ativo

**Decisão:** Cada projeto tem no máximo um parceiro vinculado.

**Contexto:** Simplicidade operacional. Casos com múltiplos parceiros são raros e podem ser tratados via observações.

**Consequência:** `projeto.json` tem campo `parceiro_id` (null ou integer). A estrutura permite expandir para N parceiros no futuro sem mudança drástica.

---

## ADR-009 — Bind 0.0.0.0 no servidor via sed após git pull
**Data:** 2026-06-08  
**Status:** Ativo — [VALIDAR uso de variável de ambiente]

**Decisão:** O `main.py` no GitHub usa `127.0.0.1`. No servidor, após `git pull`, executa-se `sed -i 's/127.0.0.1/0.0.0.0/g' main.py`.

**Contexto:** Permite que o código local funcione sem expor o servidor de desenvolvimento.

**Consequência:** O `main.py` no servidor sempre diverge do GitHub após o pull. Sempre executar `git checkout main.py` antes do `git pull` no servidor.

**Alternativa considerada:** Variável de ambiente `ORIZON_HOST` — mais elegante, não implementada ainda.
