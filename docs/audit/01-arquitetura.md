# Auditoria de Arquitetura — Orizon Manager / Dalmóbile

**Tipo:** Auditoria de arquitetura e estrutura, estilo Florence (rigorosa, enterprise-grade, baseada em evidências)
**Escopo:** `main.py`, `database.py`, `storage.py`, `mod_tenancy.py`, camada de configuração, acoplamento entre módulos, separação de camadas.
**Data:** 2026-07-03
**Sistema:** PRODUÇÃO — vendas de móveis planejados, multi-loja (tenancy). Backend Python `http.server` (sem framework), SQLAlchemy + SQLite.
**Ótica:** software de produção que deveria ter arquitetura enterprise-grade. Cada desvio desse padrão é reportado.

> **Observação metodológica:** investigação READ-ONLY. `.claude/worktrees/` (snapshot duplicado), `.git`, `__pycache__`, `.pytest_cache` foram ignorados conforme instrução.

---

## Sumário executivo

O sistema funciona e tem cobertura de testes razoável (55 arquivos de teste), mas a **arquitetura não é enterprise-grade**. Os problemas estruturais graves são de **quatro naturezas**:

1. **Servidor single-thread com estado global de requisição** — incapaz de atender mais de um usuário simultâneo com segurança de dados (variável global sobrescrita a cada request + `HTTPServer` não-threaded + sessão in-memory singleton).
2. **Monólito `main.py` de 4.758 linhas** que concentra HTTP + roteamento + regra de negócio + acesso a dados, sem qualquer camada de serviço/repositório.
3. **Roteamento por cadeia gigante `if/elif` + `re.match`** (≈106 ramos) num único método, com armadilhas de fluxo (`elif` intercalado com `if` isolado).
4. **Migrações de schema/dados que engolem exceções silenciosamente** (`except Exception: pass`) — falha de migração em produção passa despercebida.

Somam-se lacunas de configuração/segredos (senha default hardcoded em código, credenciais reais no working tree) e um schema com uso pesado de blobs JSON e uma chave natural frágil.

---

## Achados

### A-01 🔴 Crítico — Servidor single-thread + estado global por requisição: corrupção de dados sob concorrência

**Evidência:**
- `main.py:4981` — `server = HTTPServer((host, port), Handler)` — `HTTPServer` puro é **single-threaded** e serializa requests, mas não há `ThreadingHTTPServer` nem qualquer proteção; ao mesmo tempo o design NÃO está preparado para concorrência.
- `main.py:246` — `_REQ_LOJA_ATIVA = None   # header X-Loja-Ativa da requisição atual (HTTPServer single-thread)`
- `main.py:266-267, 1351-1352, 3699-3700, 3873-3874` — cada handler faz `global _REQ_LOJA_ATIVA; _REQ_LOJA_ATIVA = _ler_loja_ativa_header(self)`, e depois `_ator_dict` lê esse global em `main.py:4829` (`header_loja_id = _REQ_LOJA_ATIVA`).
- `storage.py:151-166` — `_session: dict = {...}` é um **singleton global de sessão** (running/logs/pedidos/confirm_pending/projeto_ativo...) explicitamente documentado como "um usuário por vez" (`storage.py:147` "Local: dicionário Python em memória (um usuário por vez)").

**Impacto:** O comentário admite que o design pressupõe um único cliente. Se o servidor for exposto (o próprio código prevê `ORIZON_HOST=0.0.0.0` em produção, `main.py:4980`) e dois usuários de lojas diferentes fizerem requests concomitantes, o `_REQ_LOJA_ATIVA` de um pode ser sobrescrito pelo outro entre o `_ler_loja_ativa_header` e o uso — **vazamento de escopo entre tenants** (usuário da loja A operando com o `loja_id` da loja B). O `_session` global de exportação/negociação é compartilhado por todos: logs, projeto ativo e confirmações de um usuário aparecem para outro. Em multi-tenant isto é uma falha de isolamento de dados de severidade máxima.

**Recomendação:** Eliminar todo estado global de requisição. Passar a loja ativa como parâmetro/objeto de contexto por request (nunca via global de módulo). Migrar o `_session` singleton para estado por-token (Redis, tabela, ou dict indexado por token de sessão). Se mantiver `http.server`, no mínimo trocar por `ThreadingHTTPServer` **somente após** remover todo estado mutável compartilhado — caso contrário a troca agrava o problema. A médio prazo, migrar para um framework WSGI/ASGI (Flask/FastAPI) com servidor de produção (gunicorn/uvicorn).

---

### A-02 🔴 Crítico — Monólito `main.py` (4.758 linhas): HTTP + roteamento + regra de negócio + acesso a dados no mesmo arquivo/métodos

**Evidência:**
- `main.py` tem 4.758 linhas. Os quatro métodos de handler são gigantescos:
  - `do_GET` — `main.py:265` → `main.py:1350` (≈1.085 linhas)
  - `do_POST` — `main.py:1350` → `main.py:3698` (≈2.348 linhas)
  - `do_PUT` — `main.py:3698` → `main.py:3872` (≈174 linhas)
  - `do_PATCH` — `main.py:3872` → `main.py:4289` (≈417 linhas)
- Regra de negócio financeira mora dentro de `main.py`, não numa camada de serviço: `_negociacao_breakdown` (`main.py:4549`), `_recalcular_orcamento` (`main.py:4617`), `_registrar_provisao_venda` (`main.py:4601`), `_ambientes_valor_para_contrato` (`main.py:4638`), `_montar_dados_projeto_para_contrato` (`main.py:4657`).
- Acesso a dados (queries SQLAlchemy cruas) espalhado inline dentro dos handlers, ex. `main.py:70-76` (query de Orçamento mais recente), `main.py:387-388`, `main.py:416-417`.

**Impacto:** Uma função de 2.348 linhas é impossível de testar unitariamente, revisar com segurança ou evoluir sem regressão. A mistura de concerns (parsing HTTP, autenticação, autorização, tenancy, regra financeira, ORM) num só lugar significa que qualquer mudança toca tudo. Não há fronteira de transação clara nem reuso — cada rota reimplementa o mesmo boilerplate de auth/escopo/`db.close()`.

**Recomendação:** Introduzir três camadas: (1) **roteamento** (tabela rota→handler, ver A-03), (2) **serviços** (`services/negociacao.py`, `services/contrato.py`, `services/tenancy.py`) com a regra de negócio pura já parcialmente existente nos `mod_*`, (3) **repositórios** encapsulando as queries ORM. Handlers HTTP devem virar finos: parse → chamar serviço → serializar resposta.

---

### A-03 🟠 Alto — Roteamento por cadeia `if/elif` + `re.match` (≈106 ramos) num único método, com armadilha de fluxo

**Evidência:**
- ≈106 ramos de rota (contagem de `elif path ==`/`re.match`/`path ==`/`startswith` em `main.py`).
- Padrão perigoso: a cadeia `if/elif` de comparação exata é **interrompida por blocos `if m:` isolados** com `re.match`. Ex.: `main.py:370` `m = re.match(...)` seguido de `if m:` logo após um bloco `elif` (`main.py:342-368`). Um `if` isolado quebra a cadeia `elif` anterior: se uma rota exata casar E cair fora do `elif`, a lógica de precedência fica implícita e frágil. A ausência de `return` em alguns ramos `elif` (que só chamam `send_json` e caem no fim do método) depende de o próximo `re.match` não casar.

**Impacto:** Adicionar/reordenar rotas é arriscado — a ordem textual determina a precedência e há mistura de dois mecanismos de match. Rotas parametrizadas (`/api/clientes/(\d+)/briefing`) exigem regex repetida a cada handler. É terreno fértil para bugs de rota-sombreada e para o esquecimento de `return`.

**Recomendação:** Substituir por uma tabela de rotas declarativa (`(metodo, regex) -> função`) e um dispatcher único que faz match, extrai params e chama o handler. Isso elimina a cadeia gigante, torna a precedência explícita e permite testar rotas isoladamente.

---

### A-04 🔴 Crítico — Migrações de schema e de dados engolem exceções silenciosamente

**Evidência:**
- `database.py:613-614` — `_migrar_colunas()` inteira envolvida em `except Exception: pass`.
- `database.py:766-769` — `_migrar_dados()` chama `_run_migracoes(conn)` dentro de `try/except Exception: pass`.
- `database.py:803-805` — `upsert_projeto_status` faz rollback e re-raise (ok), mas o padrão de "pass" domina as migrações.

**Impacto:** Se uma migração falhar em produção (coluna não adicionada, backfill não executado, seed de loja/super_admin não criado), o sistema **sobe como se estivesse tudo certo** e passa a operar com schema incompleto — potencial perda/corrupção de dados e comportamento divergente entre ambientes. Migração é exatamente o ponto onde falhas devem ser barulhentas e abortar o boot.

**Recomendação:** Remover os `except: pass`. Migração deve logar e **falhar o startup** (fail-fast) em erro inesperado. Idempotência já é buscada via `schema_migrations` (`database.py:648`); combine-a com logging estruturado e propague exceções. Adotar Alembic para migrações versionadas em vez de `ALTER TABLE` manual guardado por `PRAGMA table_info` (`_migrar_colunas`, `database.py:475-616`).

---

### A-05 🟠 Alto — Ausência total de camada de repositório/serviço: ORM cru dentro dos handlers

**Evidência:**
- Não existe pacote `services/` nem `repositories/`. Toda persistência é `get_session()` + queries inline nos handlers e helpers de `main.py`. Ex.: `main.py:63-88` (`_enriquecer_projetos_com_status` abre sessão, faz N queries de Orçamento num loop — problema N+1 em `main.py:70-74`), `main.py:95-106` (`_enriquecer_projetos_com_pool`).
- Boilerplate `db = get_session() ... finally: db.close()` repetido em dezenas de ramos (ex.: `main.py:325-340`, `main.py:347-368`, `main.py:376-396`).

**Impacto:** Regra de negócio e SQL acoplados ao transporte HTTP; impossível reusar a lógica fora do handler (ex.: num job, num teste unitário sem subir servidor). O padrão N+1 (`_enriquecer_projetos_com_status`, um `Orcamento` query por projeto) degrada performance à medida que o número de projetos cresce. Gestão manual de sessão repetida convida a vazamento de conexão quando algum ramo esquece o `finally`.

**Recomendação:** Extrair repositórios (`ProjetoRepo`, `OrcamentoRepo`, ...) e serviços. Centralizar o ciclo de sessão num context manager/decorator (`with unit_of_work() as db:`). Resolver os N+1 com `join`/`in_` agregados.

---

### A-06 🔴 Crítico — Credenciais reais da API Omie presentes no working tree (embora gitignoradas)

**Evidência:**
- `omie_config.json:2-3` — `"app_key": "7704233295759"`, `"app_secret": "05fc0d8f6098464b4ca7c29a515ac663"` — **credenciais de produção reais**.
- `.gitignore` lista `omie_config.json` (não versionado — bom), e o histórico Git não contém o arquivo (verificado). Porém o segredo está em claro num arquivo de configuração no diretório do app.

**Impacto:** O `app_secret` é um segredo de integração financeira (cria clientes/pedidos no ERP Omie). Estar em arquivo plano no servidor, sem cofre de segredos, expõe a chave a qualquer acesso ao filesystem/backup. A própria `storage.py:71` reconhece: "Para nuvem: substituir por os.environ ou serviço de segredos" — reconhecido como dívida, não resolvido.

**Recomendação:** Mover credenciais para variáveis de ambiente ou um cofre (mínimo: `.env` fora do webroot já ignorado). Rotacionar o `app_secret` atual, pois já circulou em ambiente de desenvolvimento. Nunca manter segredo em arquivo servido pelo mesmo processo HTTP.

---

### A-07 🟠 Alto — Senha default hardcoded em código-fonte e hashing de senha sem salt

**Evidência:**
- `storage.py:111` — no `PERFIS_PADRAO`, o perfil "gerente" tem `"senha_gerente": "1234"` em texto claro dentro do código.
- `database.py:636` — `_SEED_SA_SENHA = "trocar123"` (senha do super_admin de bootstrap) hardcoded; comentário `database.py:632-633` admite "TROCAR antes de produção".
- `database.py:13-15` — `_hash_senha` usa `hashlib.sha256(senha.encode()).hexdigest()` — **SHA-256 puro, sem salt, sem KDF**. Mesmo mecanismo em `Usuario.check_senha` (`database.py:52-53`).

**Impacto:** SHA-256 sem salt é vulnerável a rainbow tables e brute-force por GPU; inaceitável para armazenar senhas em produção. A senha de bootstrap "trocar123" e a "1234" do gerente, se não trocadas, são credenciais conhecidas. `perfis_config.json` versionado (é rastreado no Git) pode herdar o `senha_gerente` do default se persistido.

**Recomendação:** Trocar o hashing por `bcrypt`/`argon2`/`pbkdf2_hmac` com salt por usuário. Remover qualquer senha literal do código; gerar a senha de bootstrap aleatoriamente e forçar troca no 1º login. Auditar `perfis_config.json` para garantir que nenhum segredo seja persistido/versionado.

---

### A-08 🟠 Alto — Schema: chave natural frágil como PK e forte dependência de blobs JSON

**Evidência:**
- `database.py:247` — `Projeto.nome_safe = Column(String, primary_key=True)` — a PK é o **nome da pasta do projeto** (chave natural mutável). Todas as referências cruzadas usam essa string: `Orcamento.projeto_id` (`database.py:339`, String), `CicloEtapa.projeto_nome` (`database.py:393`), `Contrato.projeto_nome` (`database.py:432`), `Medicao.projeto_nome` (`database.py:115`), `PoolAmbiente.projeto_id` (`database.py:311`).
- Essas "FKs lógicas" **não são ForeignKey reais** — são `String` soltas sem constraint referencial (ex.: `Orcamento.projeto_id` é `String, nullable=False`, sem `ForeignKey("projetos_meta.nome_safe")`). Não há integridade referencial no banco entre projeto e seus orçamentos/etapas/contratos.
- Uso intenso de JSON-em-Text como blobs: `Projeto.parametros_json`, `Orcamento.negociacao_json`/`forma_pagamento`, `Contrato.pagamento_json`/`loja_snapshot_json`, `Loja.config_financeira_json`, `ProvisaoRegistro.itens_json`, `Medicao.ambientes_aprovados`, além de vários `contexto`/JSON em logs.

**Impacto:** PK textual mutável significa que renomear um projeto quebra todas as referências (ou é proibido implicitamente). A ausência de ForeignKey real permite órfãos (orçamento apontando para projeto inexistente) e impede `ON DELETE`/`JOIN` confiáveis. Blobs JSON impedem consulta/índice relacional, validação de schema e migração — regra de negócio financeira crítica (parâmetros, cronograma de pagamento, provisões) fica opaca ao banco.

**Recomendação:** Adotar PK inteira surrogate em `projetos_meta` e transformar as referências em `ForeignKey` inteiras reais (mantendo `nome_safe` como coluna `unique`). Para os JSON de configuração/negociação, avaliar normalizar os campos consultáveis em colunas/tabelas; manter JSON apenas para snapshots genuinamente imutáveis (ex.: `loja_snapshot_json` de contrato).

---

### A-09 🟠 Alto — Migração de schema artesanal via `ALTER TABLE` + `PRAGMA table_info` (sem ferramenta de migração)

**Evidência:**
- `database.py:475-616` — `_migrar_colunas()` é ~140 linhas de `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` manuais para clientes, usuarios, projetos_meta, contratos, orcamentos, pool_ambientes, orcamento_ambientes, briefings, parceiros.
- `database.py:744-759` — `_drop_coluna_margens_orcamentos()` faz `ALTER TABLE ... DROP COLUMN` protegido por versão do SQLite (`sqlite >= 3.35`).
- Migrações de dados em `_run_migracoes` (`database.py:644-727`) com IDs textuais numa tabela `schema_migrations` caseira.

**Impacto:** Reinventa (parcialmente) o que Alembic faz, mas sem downgrade, sem ordenação garantida, sem detecção de drift, sem geração automática a partir do modelo. O `create_all` (`database.py:471`) cria o schema do zero de um jeito e as migrações remendam de outro — os dois caminhos podem divergir. Combinado com A-04 (exceções engolidas), o estado do schema em produção é imprevisível.

**Recomendação:** Migrar para Alembic com histórico versionado. Enquanto não migra, no mínimo tornar as migrações fail-fast (A-04) e cobrir com testes que validem o schema resultante contra o modelo ORM.

---

### A-10 🟡 Médio — Configuração fragmentada em múltiplos arquivos JSON + defaults hardcoded divergentes

**Evidência:**
- Config espalhada: `omie_config.json` (credenciais/intervalo), `perfis_config.json` (perfis/limites de desconto), `config/total_flex.json`, `tabelas_financeiras/*.json` (6 arquivos), `omie_grupos_cache.json`, além de env vars (`ORIZON_HOST`).
- **Divergência entre default do código e arquivo persistido:** `storage.py:98-119` define `PERFIS_PADRAO` com consultor `desconto_max_pct: 10.0`, gerente `20.0`, diretoria `100.0`; mas `perfis_config.json:6,13,20` traz consultor `20`, gerente `30`, diretoria `40`. Ou seja, o "padrão" do código não bate com o que roda. Além disso, `perfis_config.json` usa chaves `consultor/gerente/diretoria`, enquanto o banco usa 10 níveis novos (`gerente_vendas`, `diretor`, `super_admin`, `admin_rede`, `gerente_adm_fin`...) — dois sistemas de perfil coexistindo.

**Impacto:** Fonte de verdade ambígua para limites de desconto (política financeira!). O `perfis_config.json` legado (3 perfis) parece órfão frente ao `perfis.py`/banco (10 perfis + capacidades), gerando confusão sobre qual controla o quê. Configuração dispersa dificulta auditoria e deploy consistente.

**Recomendação:** Consolidar configuração numa fonte única por domínio, com precedência clara (env > arquivo > default) e validação no boot. Decidir se `perfis_config.json` ainda é usado; se não, removê-lo para eliminar o sistema de perfis duplicado. Documentar a matriz de config em um só lugar.

---

### A-11 🟡 Médio — `init_db` acopla `create_all` + migração de coluna + migração de dados + backfill + faxina destrutiva

**Evidência:**
- `database.py:470-473` — `init_db()` chama em sequência `create_all`, `_migrar_colunas`, `_migrar_dados`.
- `database.py:762-773` — `_migrar_dados` roda `_run_migracoes`, depois `_backfill_loja_operacional()` (`UPDATE ... SET loja_id=1 WHERE loja_id IS NULL`, `database.py:730-741`) e `_drop_coluna_margens_orcamentos()` (DROP COLUMN destrutivo, `database.py:744-759`) **a cada boot**.

**Impacto:** Operações destrutivas/backfill executam em todo startup, sem gate de ambiente ou registro em `schema_migrations` (o backfill de loja e o drop de coluna não são rastreados como migração). O backfill hardcoda `loja_id=1` como "loja semente" — se a loja 1 não for a semente correta, atribui dados ao tenant errado. Misturar criação, migração e faxina no boot torna o startup uma operação de risco.

**Recomendação:** Separar `create_all` (bootstrap dev) de migrações (produção via Alembic). Backfills e drops devem ser migrações rastreadas e idempotentes, não código de boot recorrente. Parametrizar a "loja semente" em vez de `id=1` literal.

---

### A-12 🟡 Médio — Autenticação/autorização inline e repetida em cada rota (sem middleware/decorator)

**Evidência:**
- Cada ramo de rota autenticada repete o mesmo bloco: `usuario = get_usuario_sessao(self)` → `if not usuario: 401` → `db = get_session()` → `ator = _ator_dict(...)` → `loja_id, _err = mod_tenancy.escopo_operacional(ator)` → `if _err: 403`. Ex.: `main.py:320-340`, `main.py:342-368`, `main.py:370-397`, `main.py:399-426`, `main.py:428-432`.
- Não há decorator/middleware `@require_auth`/`@require_capability`.

**Impacto:** Enorme duplicação; qualquer rota que **esqueça** o bloco fica sem autenticação/escopo silenciosamente (falha por omissão — o pior tipo em segurança multi-tenant). Manter a política de acesso consistente em ≈106 rotas manualmente é insustentável.

**Recomendação:** Introduzir um decorator/middleware que exija sessão e resolva o escopo de loja antes do handler, injetando `(usuario, db, loja_id)` já validados. Rotas passam a declarar a capacidade exigida (`@require("gerir_usuarios")`), centralizando a matriz de autorização.

---

### A-13 🟡 Médio — Tratamento de erro genérico expõe `str(e)` ao cliente e mascara causas

**Evidência:**
- Diversos ramos retornam `self.send_json({"ok": False, "erro": str(e)}, code=500)` diretamente ao cliente: `main.py:337-338`, `main.py:365-366`, `main.py:393-394`, `main.py:422-423`.
- `except Exception: pass` também aparece na lógica de request (não só migração): `storage.py:196-197` (cache de grupos), `main.py:1588-1589`, `main.py:1835-1836`, `main.py:4523-4524`, `main.py:4560-4561`, `main.py:4580-4581`.

**Impacto:** Vazamento de detalhes internos (mensagens de exceção, possivelmente SQL/caminhos) para o cliente — superfície de information disclosure. E os `except: pass` em pontos de request escondem falhas de parsing de config financeira/JSON, podendo silenciosamente cair em defaults errados em cálculo financeiro.

**Recomendação:** Padronizar um handler de erro central que loga o stack internamente e retorna mensagem genérica + id de correlação ao cliente. Substituir `except: pass` por tratamento explícito com log; nunca engolir erro em caminho de cálculo financeiro.

---

### A-14 🔵 Baixo — Nível de log desligado e sem logging estruturado

**Evidência:**
- `main.py:254-255` — `def log_message(self, *a): pass` — desliga o log de acesso do `BaseHTTPRequestHandler` inteiramente.
- Não há uso do módulo `logging` no core; diagnósticos usam `print()` (ex.: `database.py:757` `print("[FAXINA] ...")`, `main.py:4969/4971` prints de boot).

**Impacto:** Em produção não há trilha de acesso nem logs estruturados para auditoria/incident response — crítico num sistema financeiro/contratual multi-tenant. Depuração depende de prints no console.

**Recomendação:** Adotar `logging` com handlers/formatters, níveis por ambiente, e correlação de request. Registrar acessos, ações de autorização (já há tabelas de log no banco — bom) e erros com stack.

---

### A-15 🔵 Baixo — Imports pesados e `import` dentro de funções (custo repetido e acoplamento oculto)

**Evidência:**
- Imports locais dentro de funções de request, repetidos por chamada: `main.py:4552` `import mod_negociacao, mod_provisoes, mod_orcamento_params` dentro de `_negociacao_breakdown` (chamada por request); `main.py:354` `from urllib.parse import parse_qs`; `main.py:314` `import mod_fin as _mf`; `main.py:4641` `from mod_contrato import ambientes_valor_contrato`.
- `main.py` importa 20+ símbolos de `mod_omie` (`main.py:32-40`) e reexporta grande parte do domínio — é o hub de acoplamento.

**Impacto:** Imports dentro de funções são frequentemente usados para contornar imports circulares (sintoma de fronteiras de módulo mal definidas) e adicionam custo por chamada. O `main.py` como hub central significa que quase toda mudança de domínio o toca.

**Recomendação:** Resolver ciclos movendo a regra de negócio para serviços (A-02/A-05), permitindo imports no topo. Reduzir a superfície de import de `main.py`.

---

### A-16 ℹ️ Info — Pontos positivos observados (para calibrar o placar)

- `mod_tenancy.py` é **funções puras** (sem I/O, sem ORM) — separação correta entre decisão e efeito (`mod_tenancy.py:1-6`). Padrão a replicar nos demais domínios.
- Os `mod_*` de cálculo (`mod_negociacao`, `mod_provisoes`, `mod_orcamento_params`, `mod_margens`, `mod_ciclo`, `mod_qualidade_xml`) são majoritariamente desacoplados entre si (matriz de import verificada) — o núcleo de regra é reutilizável; falta só a camada de serviço que o orquestre fora do `main.py`.
- `storage.py` isola I/O de disco atrás de funções `storage_*`/`config_*`/`session_*` com a intenção explícita de trocar backend para nuvem — a abstração existe (embora o `_session` global a contamine, ver A-01).
- Migrações de dados usam tabela `schema_migrations` idempotente com IDs (`database.py:648-727`) — boa intenção, minada pelos `except: pass` (A-04).
- Cobertura de testes: 55 arquivos em `tests/`, incluindo harness E2E de isolamento de tenancy — base sólida para a refatoração recomendada.

---

## Placar por severidade

| Severidade | Qtde | Achados |
|---|---|---|
| 🔴 Crítico | 4 | A-01, A-04, A-06, A-08 |
| 🟠 Alto | 5 | A-02, A-03, A-05, A-07, A-09 |
| 🟡 Médio | 4 | A-10, A-11, A-12, A-13 |
| 🔵 Baixo | 2 | A-14, A-15 |
| ℹ️ Info | 1 | A-16 |
| **Total** | **16** | |

---

## Recomendação de prioridade (roadmap sugerido)

1. **Isolamento de tenancy sob concorrência (A-01)** — remover `_REQ_LOJA_ATIVA` global e o `_session` singleton **antes** de qualquer exposição multiusuário. Bloqueia produção segura.
2. **Migrações fail-fast + Alembic (A-04, A-09, A-11)** — parar de engolir erro de schema; separar boot de migração.
3. **Segredos e senhas (A-06, A-07)** — cofre/env para credenciais Omie, KDF com salt para senhas, remover literais.
4. **Decompor o monólito (A-02, A-03, A-05, A-12)** — router declarativo, camada de serviço/repositório, decorator de auth/escopo. Os `mod_*` puros já dão o alicerce.
5. **Schema (A-08)** — PK surrogate + ForeignKeys reais; normalizar JSON consultável.
