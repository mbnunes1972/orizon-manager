# F4 — Suíte de regressão E2E de isolamento (multi-tenant)

> **Status:** IMPLEMENTADO e mergeado na `main` (2026-06-22). Matriz completa coberta por
> `tests/test_isolamento_f4_e2e.py` (33 testes; 234 no total). Harness real adotado (Plano B não
> foi necessário — canário passou). Achado extra corrigido: `UnboundLocalError` por `import
> threading` redundante em `do_POST`. Plano: `docs/superpowers/plans/2026-06-21-f4-isolamento-regressao-e2e.md`.
> _Histórico:_ spec aprovado (desenho) em 2026-06-21; branch `feat/multitenant-f4-isolamento`
> (já deletada após o merge); pré-requisito era a F4 implementada (201 testes verdes na época).

## 1. Problema

A F4 isola dados por loja em ~30 endpoints operacionais. A revisão de segurança por subagente
encontrou e corrigiu **vários IDORs reais** (endpoints sem auth, escrita/leitura cross-loja). Mas:

- A cobertura de testes da F4 é quase toda **unitária com fakes** (`escopo_operacional`,
  `_obj_da_loja`, `_projeto_da_loja`, backfill). Ninguém exercita o caminho real
  **HTTP → auth → escopo → handler** onde os IDORs viviam.
- As **correções de IDOR não têm teste de regressão a nível de endpoint** — podem voltar a quebrar
  sem nenhum teste ficar vermelho.
- O **smoke funcional com 2 lojas** nunca rodou (o banco de dev só tem a loja 1; a sessão travou
  antes). Hoje a confiança no isolamento vem de uma revisão única, não de prova automatizada.

**Objetivo:** converter "revisamos uma vez" em "está provado e protegido" — uma suíte automatizada
que exercita a fronteira de isolamento ponta-a-ponta, **sem depender do ambiente real do usuário**.

## 2. Não-objetivos

- Não cobrir features funcionais novas (cálculo, contrato, etc.) — só a fronteira de isolamento.
- Não substituir o smoke manual em produção como sanity final; complementá-lo/automatizá-lo.
- Não mexer no código de produção da F4 (a menos que a suíte revele um IDOR aberto — aí vira fix
  com seu próprio commit). Sem mudança de UI.
- Não fazer a varredura exaustiva de *todos* os ~30 endpoints (abordagem C do brainstorming) —
  fica como follow-up se o harness se mostrar barato.

## 3. Arquitetura do harness

**Abordagem: servidor real em thread + banco temporário isolado + login real.** Réplica fiel do
smoke manual — mesma pilha que os IDORs exploravam.

### 3.1 Isolamento do banco (ponto técnico crítico)

`database.py` liga a engine no nível de módulo no import:
```python
DB_PATH = os.path.join(BASE_DIR, "orizon.db")
ENGINE  = create_engine(f"sqlite:///{DB_PATH}", echo=False)
```
A fixture precisa redirecionar isso para um sqlite temporário **antes** de o app abrir sessões.
Como o servidor roda na **mesma process** da suíte, monkeypatch da engine/session factory de
`database` afeta o `get_session()` usado pelos handlers. Estratégia (a confirmar no plano):

1. Criar arquivo de banco temp (`tmp_path` / `tempfile`).
2. Monkeypatch `database.DB_PATH`, `database.ENGINE` e o session factory para o temp **antes** de
   importar `main` (ou recriar a engine e reapontar o factory se `main` já tiver importado).
3. Rodar o bootstrap de schema/seed de tenancy que o app usa (criar tabelas + lojas + perfis).

> Risco conhecido: se algum módulo capturar `ENGINE`/`SessionLocal` por valor no import, o
> monkeypatch pode não pegar. Mitigação: validar com um teste-canário (criar via API, ler no banco
> temp) como **primeiro** item do plano. Se inviável, plano B na seção 7.

### 3.2 Servidor

- Subir o `HTTPServer(Handler)` em `127.0.0.1:0` (porta efêmera) numa thread daemon.
- Fixture com **escopo de módulo** (sobe 1x, derruba no teardown).
- Esperar o servidor responder antes de liberar os testes (poll rápido em `/login` ou `/config`).

### 3.3 Cliente / login

- Helper `login(usuario, senha) -> session` que faz `POST /api/auth/login`, captura o cookie
  `omie_session` e o reusa nas chamadas seguintes (client com cookie jar).
- Helpers finos: `get(session, path)`, `post(session, path, json)`, `patch`, `put` → retornam
  `(status_code, body)`.

## 4. Seed do banco de teste (fixture)

| Entidade | Quantidade | Observação |
|---|---|---|
| Lojas | 2 (Loja 1, Loja 2) | ids reais distintos |
| Usuário operacional | 1 por loja (`diretor_l1`, `diretor_l2`) | perfil com poder operacional |
| super_admin | 1 | perfil administrativo (deve tomar 403 no operacional) |
| admin_rede | 1 | perfil administrativo (deve tomar 403 no operacional) |
| Dados por loja | 1 cliente, 1 projeto, 1 orçamento, 1 contrato em **cada** loja | para ter ids/nomes cross-loja reais |

Senhas fixas conhecidas para o login nos testes. O seed reusa os bootstraps de tenancy/perfis já
existentes no código (não reimplementar).

## 5. Matriz de asserções (cada linha → um teste)

**Leitura cross-loja (IDOR de leitura → 404, não vaza existência):**
- `diretor_l2` abre cliente/projeto/orçamento/contrato **da Loja 1** por id/nome → **404**.
- `diretor_l2` lista clientes/projetos/orçamentos → vê **só** os da Loja 2 (nenhum id da Loja 1).

**Perfis administrativos no operacional → 403:**
- `super_admin` e `admin_rede` em endpoint operacional (ex.: `GET /projetos`, abrir cliente) → **403**.

**Endpoints que estavam sem auth (regressão dos IDORs fechados):**
Para cada um — `PATCH /api/projetos/<nome>/status`, `PUT /api/orcamentos/<id>/descontos`,
`PATCH /api/orcamentos/<id>/valor`, `POST /api/parceiros`, `POST /api/parceiros/<id>/editar`,
`GET /api/projetos/<nome>/briefing`, `POST /api/clientes/<id>/briefing`,
`POST /api/projetos/<nome>/briefing`, `POST /projetos/<nome>/ambientes/...`:
- **anônimo** (sem cookie) → **401**.
- autenticado como **loja errada** (recurso da outra loja) → **404/403** e o dado da outra loja
  **não muda** (conferir no banco que o estado permaneceu).

**Carimbo na criação:**
- `diretor_l2` cria cliente/projeto/orçamento → linha gravada com **`loja_id = 2`** (conferir no banco).

**Sem regressão para loja legítima:**
- `diretor_l1` lista/abre/cria na Loja 1 → funciona normalmente (espelho do estado de hoje).

**Colisão de CPF (IDOR específico já corrigido):**
- `diretor_l2` cadastra cliente com CPF que já existe na Loja 1 → não vaza o cliente da Loja 1
  (cria/trata no escopo da Loja 2, conforme correção registrada).

## 6. Estrutura de arquivos

- `tests/test_isolamento_f4_e2e.py` — os testes da matriz (seção 5), agrupados por categoria.
- `tests/conftest.py` — fixtures reutilizáveis:
  - `app_db_isolado` (monkeypatch da engine p/ temp + bootstrap schema) — escopo de módulo.
  - `servidor` (HTTPServer em thread, porta efêmera) — escopo de módulo, depende de `app_db_isolado`.
  - `seed_duas_lojas` (cria lojas/usuários/dados) — escopo de módulo.
  - `cliente_http` / helper `login()` — sessão com cookie jar.

## 7. Plano B (se o monkeypatch da engine não pegar)

Instanciar o `Handler` diretamente com `rfile`/`wfile`/`headers` fakes (BytesIO) e chamar
`do_GET`/`do_POST`, simulando o cookie de sessão no header `Cookie`. Mais rápido (sem thread/socket),
um pouco mais artificial (não passa pelo parsing real de request line). Mesma matriz de asserções.
Decisão tomada no **primeiro item do plano** via teste-canário (seção 3.1).

## 8. Critérios de sucesso

1. `python -m pytest tests/test_isolamento_f4_e2e.py` passa, **sem** depender do `orizon.db` real
   (banco temp descartável; `orizon.db` de dev intocado).
2. Toda linha da matriz da seção 5 tem ao menos um teste correspondente.
3. A suíte completa (`python -m pytest`) segue verde (201 + N).
4. Se algum teste revelar um IDOR ainda aberto: documentar, corrigir no código de produção com
   commit próprio, e o teste passa a guardá-lo.

## 9. Referências

- Spec F4: `docs/superpowers/specs/multitenant/2026-06-21-multitenant-f4-isolamento-design.md`
- Plano F4: `docs/superpowers/plans/2026-06-21-multitenant-f4-isolamento.md`
- Smoke manual (matriz origem): `docs/processos/SMOKE_F4_ISOLAMENTO.md`
- Peças: `mod_tenancy.escopo_operacional`, `main._obj_da_loja`, `main._projeto_da_loja`,
  `auth.fazer_login`/`validar_sessao` (cookie `omie_session`), `database.ENGINE`/`DB_PATH`.
