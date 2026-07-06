# Auditoria de Performance e Escalabilidade — Orizon Manager / Dalmóbile

**Escopo:** backend Python (`http.server`), SQLAlchemy + SQLite, frontend `static/index.html`.
**Método:** análise estática de código (read-only, sem profiling em runtime).
**Data:** 2026-07-03.
**Contexto de porte atual:** `orizon.db` ≈ 1,2 MB, ~20 projetos em `PROJETOS/`, `static/index.html` ≈ 507 KB / 9.195 linhas.

> Nota de calibração: o sistema hoje roda em porte pequeno (uma loja, poucos usuários). Vários achados
> são **latentes** — inofensivos com 1 usuário e 20 projetos, mas graves quando a base crescer para
> centenas de projetos e múltiplos usuários simultâneos (multi-tenant é o rumo declarado do produto).
> As severidades refletem o risco em produção com crescimento, não o desconforto de hoje.

---

## 🔴 Crítico

### C1 — Servidor single-threaded: uma requisição lenta congela TODOS os usuários

**Evidência:** `main.py:10` / `main.py:4981`
```python
from http.server import HTTPServer, BaseHTTPRequestHandler
...
server = HTTPServer((host, port), Handler)
...
server.serve_forever()
```
`HTTPServer` (de `socketserver.TCPServer`) processa **uma conexão por vez, serializada**. Não há
`ThreadingHTTPServer` nem `ThreadingMixIn`. Enquanto um handler está ocupado, todas as outras
requisições (inclusive o simples GET de `/` e `/logs` de polling) ficam **enfileiradas no backlog do
socket** e podem sofrer timeout.

**Impacto:** com 2+ usuários simultâneos (cenário multi-loja real), qualquer operação pesada de um
usuário **trava a aplicação inteira** para os demais. Combinado com C2/C3/C4 (PDF WeasyPrint inline,
chamadas à API Omie, leitura de 500 KB por request), a serialização vira gargalo de disponibilidade,
não só de latência. Escalabilidade horizontal nula.

**Recomendação:** trocar para `ThreadingHTTPServer` (mudança de 1 linha) e, em seguida, endurecer o
que ficar concorrente: sessão SQLAlchemy por-thread (já é criada por request — OK), **eliminar estado
global mutável** (ver C6), e habilitar WAL no SQLite (ver A2). Para produção séria, colocar atrás de um
WSGI/ASGI (gunicorn/uvicorn + framework fino) é o caminho definitivo, mas `ThreadingHTTPServer` já
remove o pior da serialização.

---

### C2 — Geração de PDF (WeasyPrint) roda inline dentro do handler HTTP

**Evidência:** `main.py:3540` e `main.py:4107` chamam `gerar_pdf_contrato(...)` de forma síncrona
dentro do `do_POST`; a função renderiza HTML→PDF via WeasyPrint em `mod_contrato.py:806`:
```python
def gerar_pdf_contrato(contrato_id: int, ctx: dict, destino: str = None) -> str:
    from weasyprint import HTML
    ...
    HTML(string=html, base_url=CONTRATO_TEMPLATE_DIR).write_pdf(pdf_path)
```
WeasyPrint é notoriamente pesado (parse de CSS, layout, rasterização de fontes) — centenas de ms a
vários segundos por contrato.

**Impacto:** somado a C1, gerar um contrato **bloqueia o servidor inteiro** durante toda a renderização.
O usuário que gera vê latência; todos os outros veem a app "pendurada". `import weasyprint` também é
custoso — feito aqui lazy (bom), mas o primeiro contrato paga o custo do import dentro do handler.

**Recomendação:** executar a geração de PDF em thread de trabalho (padrão já usado no projeto para
export — `threading.Thread(target=run, daemon=True)` em `main.py:1503`), retornando 202/“processando”
e expondo o resultado por polling ou download posterior. No mínimo, com `ThreadingHTTPServer` (C1) o
bloqueio deixa de ser global.

---

### C3 — Chamadas à API Omie (rede + `time.sleep` de rate-limit) dentro do request

**Evidência:** `mod_omie.py:26-70` — `omie_post` faz `requests.post(..., timeout=10..60)` com **até 3
tentativas** e `time.sleep(espera)` (onde `espera` vem do texto de rate-limit da Omie, podendo chegar a
~300 s antes de abortar em `main.py:56`):
```python
for tentativa in range(3):
    resp = requests.post(url, json=payload, timeout=timeout)
    ...
        time.sleep(espera); continue
```
`/projetos/buscar` (`main.py:361`) chama `_buscar_projetos_omie(q)` → `omie_post` **sincronamente
dentro do GET handler**.

**Impacto:** uma busca de projeto que caia em rate-limit da Omie pode segurar o handler por dezenas de
segundos, e — por C1 — congelar todos os usuários. `time.sleep` dentro de um servidor single-thread é
especialmente danoso.

**Recomendação:** mover integrações Omie para fora do caminho síncrono do request (fila/worker) ou, no
mínimo, para thread + `ThreadingHTTPServer`. Reduzir o teto de espera e nunca dormir no thread que
atende o request.

---

## 🟠 Alto

### A1 — Zero índices no banco: todo filtro por `loja_id`/`criado_por_id`/FK é full table scan

**Evidência:** `database.py` inteiro — nenhuma coluna declara `index=True` e não há `Index(...)` nem
`CREATE INDEX`. Grep por `index=True|Index(|create_index` em `database.py` retorna **zero**
correspondências (só nomes de tabela `pool_ambientes`). Colunas usadas intensivamente em filtros:
- `Orcamento.projeto_id` (filtrado em `main.py:71`, `4569`, `4582`);
- `projetos_meta.loja_id` / `criado_por_id` (`main.py:4934-4938`);
- `Sessao.token` — validado em **toda requisição autenticada** (`auth_routes.py:42`);
- `OrcamentoAmbiente.orcamento_id`, `PoolAmbiente.projeto_id`, todas as FKs.

Apenas as `UNIQUE`/PK ganham índice implícito (`Sessao.token` é `unique=True` → tem índice; bom). Mas
`projeto_id`, `loja_id`, `criado_por_id` e a maioria das FKs **não**.

**Impacto:** cada consulta vira scan sequencial da tabela. Hoje (1,2 MB) é imperceptível; com dezenas de
milhares de orçamentos/ambientes, o custo cresce linearmente por consulta — e como várias consultas
rodam em loop (ver A3), o efeito multiplica.

**Recomendação:** adicionar índices em `Orcamento.projeto_id`, `Orcamento.loja_id`,
`OrcamentoAmbiente.orcamento_id`, `PoolAmbiente.projeto_id`, `projetos_meta.loja_id`,
`projetos_meta.criado_por_id`, `CicloEtapa.projeto_nome`, `Cliente.loja_id`, `Contrato.projeto_nome`.
Como já existe `_migrar_colunas()`, criar os índices via `CREATE INDEX IF NOT EXISTS` no mesmo caminho
de migração é trivial e não-destrutivo.

---

### A2 — SQLite sem WAL nem tuning: risco de `database is locked` sob concorrência

**Evidência:** `database.py:21`
```python
ENGINE = create_engine(f"sqlite:///{DB_PATH}", echo=False)
```
Sem `connect_args`, sem `PRAGMA journal_mode=WAL`, sem `busy_timeout`, sem `synchronous` ajustado. O
modo padrão (`journal_mode=DELETE`) usa lock exclusivo no arquivo inteiro durante escrita.

**Impacto:** hoje C1 (single-thread) mascara o problema — só há um writer por vez. Assim que se
adotar `ThreadingHTTPServer` (recomendado em C1) **sem** WAL, escritas concorrentes (dois usuários
salvando negociação/contrato) causarão `sqlite3.OperationalError: database is locked`. Sem
`busy_timeout`, o erro é imediato em vez de aguardar.

**Recomendação:** no `create_engine`, aplicar via listener de conexão: `PRAGMA journal_mode=WAL;`,
`PRAGMA busy_timeout=5000;`, `PRAGMA synchronous=NORMAL;`. WAL permite 1 writer + N readers concorrentes
— pré-requisito para qualquer threading.

---

### A3 — N+1 de queries: `_negociacao_breakdown` e enriquecimento de projetos

**Evidência 1 — `main.py:4569-4570` (dentro de `_negociacao_breakdown`):**
```python
for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
    pa = db.get(PoolAmbiente, lk.pool_ambiente_id)   # 1 SELECT por ambiente
```
Um `SELECT` por ambiente do orçamento. Além disso a função também roda uma segunda query
(`pool_proj`, linha 4582) e **calcula o motor duas vezes** (`calcular_orcamento` em 4585 e 4588). Pior:
`_negociacao_breakdown` é chamada **em loop** ao montar listas — `main.py:2196` a executa por orçamento
dentro de um laço de orçamentos.

**Evidência 2 — `main.py:71-76` (`_enriquecer_projetos_com_status`):**
```python
for nome in nomes:
    orc = (db.query(Orcamento).filter(Orcamento.projeto_id == nome)
             .order_by(...).first())   # 1 query por projeto
```
Uma query por projeto para pegar o último orçamento (N+1 na listagem de projetos).

**Evidência 3 — lazy-load N+1 em `main.py:4647` e `4677`:** `oa.pool_ambiente.nome_exibicao` acessado em
compreensão sobre `db.query(OrcamentoAmbiente)...join(PoolAmbiente).all()`. O `.join()` filtra mas
**não** carrega a relação — cada `oa.pool_ambiente` dispara um SELECT lazy adicional.

**Impacto:** a listagem `/projetos` e a tela de negociação escalam em O(nº de projetos × nº de
orçamentos × nº de ambientes) em número de round-trips ao banco. Com o porte atual é rápido; com
crescimento vira latência perceptível e carga de CPU repetida.

**Recomendação:** (1) trocar o `db.get` em loop por um único `WHERE pool_ambiente_id IN (...)` e mapear
em memória; (2) em `_enriquecer_projetos_com_status`, obter o último orçamento por projeto com uma só
query (subquery de `MAX(id)`/`row_number` ou `GROUP BY`); (3) usar `joinedload`/`contains_eager` nos
`.join(PoolAmbiente)` para evitar o lazy-load; (4) cachear o resultado de `_negociacao_breakdown` por
orçamento dentro do request quando chamado repetidamente.

---

### A4 — Listagem de projetos lê e faz parse de todos os `projeto.json` do disco a cada request

**Evidência:** `mod_omie.py:132-156` (`_listar_projetos`) itera `storage_listar(PROJETOS_DIR)` e chama
`_carregar_projeto(nome_safe)` → `storage_ler_json` (`mod_omie.py:83-88`, `storage.py:28-30`) para
**cada** projeto, a cada chamada de `/projetos` e `/projetos/buscar`. `_buscar_projetos`
(`mod_omie.py:158-167`) chama `_listar_projetos()` inteiro e filtra em Python (não no banco).

**Impacto:** cada carregamento da tela principal faz N leituras de disco + N parses de JSON. Com 20
projetos é barato; com centenas/milhares (cada `projeto.json` pode ter muitos ambientes), o custo de
I/O + parse por request cresce linear e não há cache. A busca também não aproveita índice — é scan de
arquivos + substring em Python.

**Recomendação:** cachear o índice de projetos em memória (invalidar em escrita), ou migrar a listagem
para o banco (os metadados já existem em `projetos_meta`). Paginar a listagem.

---

### A5 — `/` reenvia 500 KB de HTML sem cache/gzip/ETag, lido do disco a cada request

**Evidência:** `main.py:111-114` lê `index.html` do disco a cada request; `main.py:277-283` envia com
**cache desabilitado explicitamente**:
```python
self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
self.send_header("Pragma", "no-cache"); self.send_header("Expires", "0")
```
Sem `Content-Encoding: gzip`, sem `ETag`/`Last-Modified` → sem 304. Arquivo = 507 KB.

**Impacto:** cada navegação/refresh transfere ~500 KB não comprimidos (≈100–120 KB se gzipado) e relê
o arquivo do disco. Em rede móvel (o produto tem uso mobile via Termius/celular) isso é latência de
carregamento inicial significativa e desperdício de banda. O `no-store` foi adicionado
deliberadamente para combater "versão antiga após deploy" (memória do projeto), mas é um martelo:
mata todo o cache do HTML.

**Recomendação:** servir com gzip (`gzip.compress` + `Content-Encoding`), e usar cache validado por
`ETag` (hash do conteúdo) respondendo 304 quando o `If-None-Match` bate — isso resolve o "cache velho"
sem re-baixar 500 KB toda vez. Assets estáticos (login.html) podem ter cache longo com fingerprint.

---

### A6 — Frontend monolítico: 507 KB / 9.195 linhas em um único `<script>` inline

**Evidência:** `static/index.html` — 507.423 caracteres, **1 único `<script>`**, 118 chamadas `fetch(`,
126 referências a `innerHTML`. Todo HTML+CSS+JS num arquivo, sem minificação, sem split, sem
`defer`/módulos.

**Impacto:** o parser do browser precisa baixar e compilar o script inteiro antes do app ficar
interativo (não há code-splitting nem lazy-loading de telas). Uso intensivo de `innerHTML =` (126x) para
render tende a forçar reflows/reparse de HTML no cliente. Em mobile mais fraco, o time-to-interactive
sofre. Sem minificação, o payload é maior que o necessário (agrava A5).

**Recomendação:** ao menos minificar o bundle no deploy e habilitar gzip (A5). A médio prazo, separar
CSS/JS em arquivos com cache próprio e considerar carregar telas sob demanda. Preferir construção de DOM
/`textContent` a `innerHTML` em caminhos quentes.

---

## 🟡 Médio

### M1 — Estado de sessão global compartilhado entre todos os usuários

**Evidência:** `storage.py:151-166` — `_session` é **um único dict global** de processo
(`running`, `logs`, `pedidos`, `confirm_pending`, `cliente_selecionado`, `projeto_ativo`...). E
`main.py:246`:
```python
_REQ_LOJA_ATIVA = None   # header X-Loja-Ativa da requisição atual (HTTPServer single-thread)
```
O próprio comentário assume single-thread. O fluxo de export usa `session_set("confirm_event", evt)` +
`evt.wait(timeout=120)` (`main.py:1476`) sobre esse estado global.

**Impacto:** não é bug de latência, mas **bloqueador de escalabilidade e correção**: dois usuários
exportando/negociando ao mesmo tempo sobrescrevem o estado um do outro (logs, confirm, projeto ativo).
Ao adotar threading (C1), `_REQ_LOJA_ATIVA` global vira **race condition** — a loja ativa de um request
vaza para outro. Hoje, single-thread + um usuário, funciona; multi-usuário, não.

**Recomendação:** mover estado por-request para o próprio handler/thread-local; estado por-usuário para
o banco ou um store keyed por sessão. `_REQ_LOJA_ATIVA` deve ser variável local propagada por argumento,
não global — obrigatório antes de qualquer threading.

---

### M2 — Motor de negociação recalculado do zero (2×) sem memoização

**Evidência:** `main.py:4585` e `4588` — `mod_negociacao.calcular_orcamento(...)` é chamado duas vezes
seguidas (uma para achar `cust_fin`, outra final). `_negociacao_breakdown` é reexecutada em vários
endpoints (`main.py:871, 923, 2151, 2196, 2227, 3819, 3860, 4603, 4621`) e às vezes em loop.

**Impacto:** trabalho de CPU duplicado por chamada e repetido por orçamento. Barato por unidade, mas
some com A3 (N+1) para inflar a latência das telas de negociação/listagem.

**Recomendação:** calcular `cust_fin` sem refazer a cadeia inteira quando possível, ou memoizar o
breakdown por `orcamento_id` durante o request. Não recomputar em loops quando o resultado não muda.

---

### M3 — Parse repetido de blobs JSON (`negociacao_json`, `parametros_json`, `ambientes_json`)

**Evidência:** `json.loads` sobre colunas TEXT grandes em vários pontos por request:
`main.py:820, 825, 1108, 2142, 4565, 4577`, e `json.loads(pa_c.ambientes_json)` em `main.py:2438`.
`ambientes_json` (em `pool_ambientes`) guarda o breakdown completo do ambiente — pode ser volumoso.

**Impacto:** parsing repetido de JSON grande a cada request/loop consome CPU e aloca objetos
desnecessariamente. Escala com o tamanho do projeto (nº de ambientes/grupos por XML).

**Recomendação:** parsear uma vez por request e reutilizar; evitar reparsear o mesmo blob em iterações.
Para dados consultados por filtro, considerar colunas normalizadas em vez de varrer JSON em Python.

---

### M4 — Config/perfis lidos do disco a cada request que os usa

**Evidência:** `storage.py:74-80` (`config_carregar`) e `storage.py:123-132` (`perfis_carregar`) leem e
parseiam `omie_config.json`/`perfis_config.json` do disco em cada chamada. `GET /config` e `GET /perfis`
(`main.py:288, 291`) fazem isso; `perfil_ativo_get()` também. `_buscar_projetos_omie` chama
`config_carregar()` a cada busca (`mod_omie.py:174`).

**Impacto:** I/O de disco + parse de JSON por request para dados que quase nunca mudam. Pequeno
individualmente, mas é overhead evitável em caminhos quentes.

**Recomendação:** cachear em memória com invalidação na escrita (`config_salvar`/`perfis_salvar`).

---

## 🔵 Baixo

### B1 — Migração completa de schema (PRAGMA em toda tabela) roda a cada startup

**Evidência:** `database.py:475-616` (`_migrar_colunas`) executa dezenas de `PRAGMA table_info(...)` +
`ALTER TABLE ... ADD COLUMN` condicionais a **todo** `init_db()` (startup). Idempotente, mas percorre
todas as tabelas sempre.

**Impacto:** só afeta tempo de boot (segundos), não o request. Aceitável, mas cresce com o schema.

**Recomendação:** gatear por versão de schema (a tabela `schema_migrations` já existe para migrações de
dados) para pular a varredura quando nada mudou.

### B2 — `except Exception: pass` amplo pode mascarar lentidão/erros de migração

**Evidência:** `database.py:613-616` e `database.py:768-769` engolem exceções silenciosamente. Não é
performance direta, mas esconde falhas (ex.: migração que não aplicou índice) que se manifestam como
lentidão inexplicável depois.

**Recomendação:** ao menos logar a exceção.

---

## ℹ️ Informativo

- **Export em thread (bom padrão):** `main.py:1503` (`threading.Thread(target=run, daemon=True).start()`)
  e o sync Omie em `main.py:1840` já rodam fora do handler — é o padrão a estender para PDF (C2) e busca
  Omie (C3).
- **Sessão SQLAlchemy por-request (bom):** `get_session()` cria uma sessão nova por request e há
  `db.close()` em `finally` na maioria dos handlers — não há sessão global compartilhada (correto para
  quando o servidor virar threaded). `Sessao.token` é `unique=True` (tem índice) — a validação de sessão
  por request não é scan.
- **Timeouts de rede presentes:** `omie_post` usa `timeout` explícito (10–60 s) e LibreOffice usa
  `timeout=120` (`mod_contrato.py:848`) — evita travar indefinidamente, embora ainda bloqueie o
  single-thread durante a espera.
- **Caminho `.docx`/LibreOffice do contrato aposentado:** o subprocess pesado do LibreOffice
  (`mod_contrato.py:845`) ainda existe no código mas, conforme CLAUDE.md, o contrato migrou para
  WeasyPrint; a proposta ainda usa docx. Se `subprocess.run(soffice)` for acionado inline, aplica-se o
  mesmo risco de C2/C3.

---

## Placar por severidade

| Severidade      | Qtd | Achados |
|-----------------|-----|---------|
| 🔴 Crítico      | 3   | C1 (server single-thread), C2 (PDF inline), C3 (Omie inline + sleep) |
| 🟠 Alto         | 6   | A1 (sem índices), A2 (SQLite sem WAL), A3 (N+1), A4 (scan de projeto.json), A5 (500 KB sem cache/gzip), A6 (frontend monolítico) |
| 🟡 Médio        | 4   | M1 (estado global), M2 (motor 2×), M3 (JSON reparse), M4 (config/perfis do disco) |
| 🔵 Baixo        | 2   | B1 (migração a cada boot), B2 (except pass) |
| ℹ️ Informativo  | —   | 4 observações (pontos positivos + contexto) |
| **Total**       | **15** | |

---

## Sequência recomendada (maior ganho / menor risco primeiro)

1. **A1 + A2** — criar índices e habilitar WAL/busy_timeout (baixo risco, alto ganho, via caminho de
   migração já existente). Pré-requisito para escalar.
2. **C1** — `ThreadingHTTPServer`. **Só depois de A2 e M1**, pois threading sem WAL causa lock e sem
   remover globais causa race.
3. **M1** — eliminar `_REQ_LOJA_ATIVA` global e estado de sessão compartilhado (obrigatório junto de C1).
4. **C2 + C3** — mover PDF e integrações Omie para fora do request síncrono.
5. **A3 + M2 + M3** — corrigir N+1, memoizar breakdown, parsear JSON uma vez.
6. **A5 + A6 + A4** — gzip + ETag/304 no HTML, minificação, cache/índice da listagem de projetos.
