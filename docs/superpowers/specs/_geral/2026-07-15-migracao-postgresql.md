# ADR — Migração do banco de dados: SQLite → PostgreSQL

**Data:** 2026-07-15 · **Status:** decisão aceita; implementação pendente (banco de produção continua
SQLite até o cutover).

## Contexto

Pedido do usuário: levar o Orizon para uma "fase mais profissional", com um banco de dados mais eficiente.
Hoje o app roda **SQLite** puro (`orizon.db`, ~960KB) via SQLAlchemy, atrás de um `HTTPServer` single-thread
numa única VPS (`167.88.33.121`). Levantamento do código encontrou três pontos concretos:

- `database.py` tem **~30 chamadas** `sqlite3.connect`/`PRAGMA table_info`/`sqlite_master` (linhas
  985–1536) formando um sistema de migração de schema **ad-hoc, específico do SQLite** — sem
  versionamento real (tipo Alembic).
- Só **2 colunas** têm `index=True` (`parcela_projeto.projeto_nome`, `arquivo_pe.projeto_nome`); FKs e
  filtros frequentes (`loja_id`, `rede_id`, `projeto_nome`, `status`) não são indexados.
- Uma dúzia de colunas guardam JSON como `Text` puro (`parametros_json`, `negociacao_json`,
  `config_financeira_json`, `itens_json`, `dados_json`, `ia_sugestao`...) — não consultável/indexável.

## Decisão

**Migrar de SQLite para PostgreSQL**, autohospedado na mesma VPS que já roda o app — sem custo mensal
adicional. (Alternativa avaliada: Postgres gerenciado tipo DigitalOcean, a partir de **$15/mês** com
backup/PITR prontos — fica em standby caso o time queira tirar ops de cima de si depois. Opções
serverless tipo Neon/Supabase foram descartadas para produção por causa do cold-start/pause por
inatividade, incompatível com uma VPS única sempre no ar.)

Plano de execução em 5 etapas (não é urgente, não bloqueia outras frentes):

1. Instalar Postgres + `psycopg2-binary`; connection string via variável de ambiente (dev continua
   podendo usar SQLite local se quiser).
2. Aposentar os ~30 guards `PRAGMA`/`sqlite3.connect` de `database.py`; adotar **Alembic** com baseline
   no schema atual (não precisa fazer replay do histórico — schema novo nasce limpo via
   `Base.metadata.create_all()` uma vez).
3. Script de migração de dados: copiar o conteúdo do `orizon.db` atual para o Postgres, tabela por
   tabela, via os próprios modelos SQLAlchemy.
4. Validar a suíte pytest contra o novo banco (hoje `tests/conftest.py` recria SQLite por módulo de
   teste — decidir se mantém SQLite nos testes por velocidade ou roda também contra Postgres para
   fidelidade).
5. Cutover na VPS com janela de manutenção; atualizar o runbook de deploy em `DEV_RULES.md`.

Estimativa: **2–3 dias de trabalho focado**.

## Porquê

- **Rigor transacional para o motor contábil.** O ciclo de partida dobrada (`Lancamento`/`Conta`,
  fechamento contábil FASE D2) se beneficia das constraints/transações mais estritas do Postgres — falha
  alto em vez de mascarar inconsistência, o que importa mais aqui do que num CRUD comum.
- **JSONB.** Os campos `*_json` hoje em `Text` passam a ser consultáveis/indexáveis nativamente (`->>`,
  índices GIN) — não é feito nesta frente, mas é o caminho de evolução natural depois da migração.
- **`ALTER TABLE` sem lock.** `ADD COLUMN` no Postgres é metadata-only (não reescreve a tabela); o padrão
  de "ir adicionando coluna aos poucos" que o projeto já usa fica mais barato.
- **Custo zero agora.** Autohospedar na VPS existente não adiciona gasto mensal; gerenciado fica como
  upgrade futuro se/quando ops pesar.

## Consequência

Fecha a lacuna de eficiência levantada, sem mexer na concorrência do servidor (`HTTPServer` single-thread
segue como está — frente separada, não é pré-requisito desta). JSON vira `JSONB` só numa frente futura
opcional. **Enquanto a migração não for executada, o banco de produção continua SQLite** — não assumir
Postgres em código novo até o cutover.
