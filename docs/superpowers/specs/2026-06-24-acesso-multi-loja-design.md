# Design — Acesso multi-loja por usuário (loja ativa)

**Data:** 2026-06-24
**Slice:** Acesso multi-loja (item (b) do pedido pós-#1/#2)
**Status:** proposto (aguardando revisão)

## Contexto

Hoje o isolamento operacional inteiro depende de **um** `loja_id` por usuário:

- `usuarios.loja_id` (FK única, `database.py:43`); `usuarios.rede_id` para admin_rede.
- `mod_tenancy.escopo_operacional(ator)` (`mod_tenancy.py:161`) retorna `(loja_id, None)` para usuário de loja, ou `(None, motivo)` para papéis administrativos.
- ~51 call sites em `main.py` chamam `escopo_operacional` e filtram/carimbam dados operacionais (clientes, projetos, orçamentos, contratos, ciclo) por `loja_id`; helpers `_obj_da_loja`/`_projeto_da_loja`/`_filtrar_projetos_por_loja` reforçam o escopo. ~156 referências a `loja_id` em `main.py`.
- Já existe um precedente de M:N loja↔entidade: `ParceiroLoja` (`database.py:220`, tabela `parceiro_lojas`).

### Problema

Pessoas como o diretor que atua em mais de uma loja (no seed Orizon, Marcelo dirige Loja 1 e Loja 4) não cabem no modelo 1-usuário→1-loja. É preciso permitir que um usuário acesse várias lojas, e que o **admin de rede defina quais lojas cada usuário acessa**.

## Decisões de produto (do brainstorming)

- **Modelo de acesso = loja ativa (troca de contexto).** O usuário opera em UMA loja por vez (um seletor para trocar). Dentro da loja ativa, tudo funciona como hoje (isolamento de loja única). **Sem** visão agregada cross-loja.
- **Quem pode ser multi-loja:** qualquer usuário; quem atribui (super_admin/admin_rede) decide dentro do seu escopo. Sem regra especial por papel.
- **Papel:** um `nivel` por usuário, válido em todas as lojas acessíveis. Multi-loja multiplica a **loja**, não o **papel**. Multi-papel (mesmo login com papéis distintos) fica **fora deste slice**.
- **Abordagem técnica = loja ativa por requisição** (header `X-Loja-Ativa`), por ser segura para múltiplas abas (cada aba descreve sua loja; evita gravar na loja errada).

## Abordagem escolhida

**Loja ativa por requisição.** O header viaja em cada chamada operacional e é lido **um único ponto** (`_ator_dict`), validado contra a membership; `escopo_operacional` (o funil único já existente) passa a devolver a loja ativa. Isso localiza a mudança apesar dos ~51 call sites.

Alternativas descartadas: loja ativa só na sessão do servidor (insegura com múltiplas abas — uma aba muda o contexto da outra); refatorar cada call site para receber `loja_id` explícito (invasivo, sem ganho sobre a escolhida).

## Parte 1 — Modelo de dados & migração

- **Nova tabela `usuario_lojas`** (M:N), espelhando `parceiro_lojas`:
  - `id` (PK, autoincrement), `usuario_id` (FK `usuarios.id`, not null), `loja_id` (FK `lojas.id`, not null), `UNIQUE(usuario_id, loja_id)`.
  - É a fonte das **lojas acessíveis** de um usuário.
- **`usuarios.loja_id` permanece** como a **loja primária/default** (definida pelo admin; loja ativa inicial no login). A coluna NÃO é removida — evita mexer nas ~156 referências e reduz risco.
- **Migração idempotente no startup** (mesmo padrão das migrações em `database.py`): cria a tabela se não existir; **backfill** — para cada usuário com `loja_id` não-nulo e sem linhas em `usuario_lojas`, insere uma linha `(usuario_id, loja_id)`. Usuários de loja única passam a ter "1 membership = sua loja" → comportamento idêntico ao atual. super_admin/admin_rede (loja_id nulo) não recebem linhas.

## Parte 2 — Backend: fluxo da loja ativa

- **Função pura em `mod_tenancy`:**
  - `resolver_loja_ativa(memberships, header_loja_id, default_loja_id) -> int | None`:
    - se `header_loja_id` ∈ `memberships` → retorna `header_loja_id`;
    - senão se `default_loja_id` ∈ `memberships` → retorna `default_loja_id`;
    - senão se `len(memberships) == 1` → retorna o único;
    - senão `None`.
- **`_ator_dict(db, usuario_sessao, header_loja_id=None)`** passa a:
  - carregar as memberships de `usuario_lojas` para o usuário (lista de `loja_id`);
  - resolver `active_loja_id = resolver_loja_ativa(memberships, header_loja_id, usuario.loja_id)`;
  - retornar o ator com `active_loja_id`, `lojas_ids`, além de `nivel`/`loja_id`/`rede_id` (compat).
  - O header `X-Loja-Ativa` é lido nos 3 pontos de dispatch (`do_GET`/`do_POST`/`do_PATCH`) e disponibilizado a `_ator_dict` (cada request é uma instância própria do `Handler` → seguro por requisição).
- **`escopo_operacional(ator)`** passa a retornar `(ator["active_loja_id"], None)` quando há loja ativa, senão `(None, motivo)`. **Funil único:** os ~51 call sites seguem chamando `escopo_operacional(ator)` sem mudança.
- **Pontos que leem `ator.loja_id` direto** (ex.: criação de contrato, `main.py:~3283`) trocam para a loja ativa (`escopo_operacional` ou `active_loja_id`).
- **`/api/auth/me`** (payload de `auth._usuario_dict`) passa a expor `lojas: [{id, nome, codigo}, …]` (acessíveis, via `usuario_lojas`) e `loja_ativa_id` (a default = `usuarios.loja_id`). Sem novo endpoint de "definir ativa" — o frontend manda o header da loja escolhida (lembrada em `localStorage`); o login começa na default.

### Segurança
- A loja ativa só pode ser uma loja da membership (validada na resolução do header). Header com loja fora da membership não resolve para ela → `escopo_operacional` retorna None → endpoint operacional responde 403.
- Membership revogada no meio da sessão → próxima requisição não resolve aquela loja → 403.

## Parte 3 — Atribuição de lojas (modal de usuário)

- **Modal de usuário (`abrirModalUsuario`, `static/index.html`)**: no escopo operacional, mostra uma **lista multi-seleção de lojas** (checkboxes) dentro do escopo de quem atribui:
  - admin_rede → lojas da própria rede; super_admin → lojas da rede escolhida (ou avulsas).
  - Criação de papéis admin (super_admin/admin_rede) não tem seleção de loja (como hoje).
- **Backend (rota criar/editar usuário + `mod_tenancy.atribuir_tenant_usuario`)**: aceita `loja_ids: [...]`. Valida que **todas** ∈ escopo de quem atribui (estende a checagem de escopo já existente na rota). Grava as linhas em `usuario_lojas`; define `usuarios.loja_id = loja_ids[0]` (primária). Na edição, faz o diff das memberships (adiciona/remove). Validação: ≥1 loja para papéis operacionais.
- `mod_tenancy.perfis_atribuiveis` inalterado.

## Parte 4 — Frontend (seletor), contrato, erros e testes

**Seletor de loja ativa:**
- Dropdown no topo/sidebar, exibido só quando `_usuarioAtual.lojas.length > 1`. Seleção inicial = `loja_ativa_id`. Ao trocar: grava em `localStorage`, atualiza um global `_lojaAtiva` e **recarrega as views operacionais** (re-roda os loaders de Projetos/Clientes/etc.).
- O header `X-Loja-Ativa` é injetado de forma central por **interceptação de `window.fetch`**: um wrapper instalado no boot adiciona o header em toda requisição same-origin para `/api/...` (quando há `_lojaAtiva`). Enviar o header em rotas admin é inócuo (elas ignoram). Evita editar cada `fetch` individual.
- **Usuário de loja única** (`lojas.length === 1`): sem seletor; idêntico ao comportamento atual.
- **admin_rede/super_admin**: sem membership → sem loja ativa → endpoints operacionais seguem 403 (usam a árvore admin).

**Contrato:** usa a **loja ativa** (já é o escopo operacional) para código e `loja_snapshot_json`. O projeto pertence à loja ativa (garantido pelo isolamento operacional).

**Erros:**
- Header com loja fora da membership → 403 ("loja inválida/sem acesso").
- Multi-loja sem header e sem default resolvível → frontend força escolher a loja antes de operar.
- Membership revogada no meio da sessão → 403 na próxima ação → frontend atualiza a lista de lojas.

**Testes:**
- **Backend puro:** `resolver_loja_ativa` — header válido; header inválido cai no default; default inválido cai em membership única; nenhuma resolvível → None.
- **Backend e2e:** usuário multi-loja; `GET /api/projetos…` com `X-Loja-Ativa=lojaA` → só lojaA; com `lojaB` → lojaB; com loja **não-membro** → 403; `POST` cria na loja ativa; contrato usa o código da loja ativa. **Migração:** usuário single-loja existente ganha exatamente 1 membership. **Não-regressão:** usuário single-loja sem header funciona igual a hoje. **Atribuição:** admin_rede cria usuário com `loja_ids` da própria rede (ok) e é barrado ao incluir loja de outra rede (403).
- **Frontend:** verificação manual (trocar loja muda o contexto; reload mostra dados da nova loja) — sem teste JS no projeto.

## Fora deste slice (registrado)
- Multi-papel (mesmo login com papéis distintos).
- Visão agregada cross-loja (todas as lojas numa tela).
- Modais "Nova rede"/"Nova loja" (slice (a) separado — hoje usam `prompt()`).

## Arquivos afetados
- **Editado:** `database.py` (modelo `UsuarioLoja` + migração/backfill), `mod_tenancy.py` (`resolver_loja_ativa`, `escopo_operacional`, `atribuir_tenant_usuario`), `main.py` (`_ator_dict`, leitura do header nos dispatch, rota criar/editar usuário, criação de contrato), `auth.py` (payload `_usuario_dict`), `static/index.html` (seletor + `apiFetch`/header + modal multi-loja).
- **Novo:** testes (`tests/test_multi_loja.py` puro + `tests/test_multi_loja_e2e.py` HTTP).
