# Design — Aterrissagem por papel + árvore estrutural do super_admin

**Data:** 2026-06-24
**Slice:** #1 + #2 do pedido de arquitetura multi-tenant (super_admin/redes/lojas)
**Status:** ✅ Implementado e mergeado na `main` (2026-06-28). Ver DEV_LOG (frente super_admin aterrissagem + árvore).

## Contexto

O sistema já tem o essencial da arquitetura multi-tenant:

- Papéis `super_admin` e `admin_rede` (`perfis.py`), com escopo em `mod_tenancy.py` (funções puras).
- Tabelas `redes` e `lojas` (`database.py`); lojas avulsas = `rede_id NULL`, já vinculadas à plataforma.
- Painel Admin de 3 níveis no `static/index.html` (page 7): Plataforma → Rede → Loja, com drill
  via `adminEntrarRede` / `adminEntrarLoja`, breadcrumb e abas "Dados da loja" / "Usuários da loja".
- Os botões **"+ Nova rede"** e **"+ Nova loja"** já existem no Painel Admin
  (`index.html` ~6414/6427/6477).

### Problema real (reconciliado com o pedido)

1. **#1 "super_admin sem botão de criar rede/loja":** os botões existem, mas o super_admin
   **não aterrissa no Painel Admin** — após login todos caem na page 0 (Projetos). Só o item de
   menu "Admin" é desescondido (`carregarUsuarioAutenticado`, `index.html:1950-1953`).
   → Lacuna real = **roteamento de aterrissagem por papel**.
2. **#2 "super_admin não precisa ver projetos/clientes na abertura; árvore rede→loja→projeto→docs":**
   ele cai em Projetos e o menu mostra Projetos/Clientes/Parceiros; a árvore de drill hoje para no
   nível Loja. → Lacuna real = **abertura/menu por papel + estender a árvore até projeto→etapas**.

Itens já satisfeitos hoje: #3 (avulsas → plataforma). Itens de outros slices: #4 (busca LGPD),
#6 (seed Orizon + multi-papel), #7 (config de rede), #8 (config de loja).

## Decisões de produto (definidas no brainstorming)

- **Profundidade da árvore:** estrutural, **sem PII**. Mostra estrutura/indicadores
  (rede → loja → projeto → etapas do ciclo). Não expõe dados pessoais de cliente, conteúdo de
  documento, nem valores comerciais. PII/conteúdo fica isolado no painel ultra-restrito da LGPD (#4).
- **Nível projeto:** mostra **apenas as etapas do ciclo** (o "processo"). O nível "documentos"
  (D1–D45) fica fora deste slice — será adicionado quando o banco de documentos existir (#8).
- **Aterrissagem:** super_admin → Painel Admin (nível Plataforma); admin_rede → Painel Admin
  (nível Rede); papéis operacionais → inalterado (page 0, Projetos).
- **Menu lateral:** esconder Projetos/Clientes/Parceiros **somente para super_admin**.
  `admin_rede` mantém o menu operacional visível (decisão do usuário), ainda que esses endpoints
  retornem 403 para quem não tem `loja_id`.

## Abordagem escolhida

**Abordagem A — estender o Painel Admin existente.** Reaproveita breadcrumb, drill e `_adminNav`.
Alternativas descartadas: página "Governança" dedicada (duplica navegação, mais código) e
rota SPA/SSR separada (exagero para a stack vanilla + `http.server`).

**Princípio de modularização:** toda a lógica nova (escopo + montagem dos dados estruturais) vai
para um **módulo puro novo `mod_arvore.py`** (recebe session + ator, devolve dicts), com as rotas
em `main.py` atuando como **cola fina**. Mantém o núcleo reutilizável/testável sem subir HTTP,
seguindo o padrão de `mod_tenancy`, `mod_negociacao`, etc.

## Backend

### Novo módulo `mod_arvore.py` (funções puras)

```python
def projetos_estruturais(db, ator, loja_id) -> list[dict]
def etapas_do_projeto(db, ator, nome_safe) -> list[dict]
```

- **`projetos_estruturais(db, ator, loja_id)`**
  - Valida escopo: super_admin → qualquer loja; admin_rede → apenas `loja.rede_id == ator.rede_id`;
    operacional → `PermissionError`.
  - Retorna por projeto (de `projetos_meta` + agregação de `ciclo_etapas`):
    `{ nome_safe, status, etapa_atual_codigo, etapa_atual_nome, total_etapas, etapas_concluidas }`.
  - `etapa_atual` = maior etapa principal não concluída (usa `mod_ciclo.ETAPAS_PRINCIPAIS`,
    `ETAPA_NOME`, `STATUS_CONCLUSIVOS`). `etapas_concluidas` conta status em `STATUS_CONCLUSIVOS`.
  - **Sem PII:** não seleciona `cliente_id`/dados de cliente, não retorna `parametros_json`,
    não retorna valores de orçamento.
- **`etapas_do_projeto(db, ator, nome_safe)`**
  - Resolve a loja do projeto e revalida o escopo do ator (mesma regra). `PermissionError` fora do
    escopo; retorno vazio/`None` → rota traduz em 404 se o projeto não existir.
  - Retorna por etapa (de `ciclo_etapas`, ordenado por `mod_ciclo.chave_ordenacao`):
    `{ etapa_codigo, etapa_nome, status, concluido_em }`. `etapa_nome` via `mod_ciclo.ETAPA_NOME`.
  - **Sem PII:** não retorna `responsavel_id` resolvido a nome, `observacoes`, nem anexos.

> Garantia de PII no módulo: a montagem do dict só inclui as chaves listadas acima — o filtro não
> depende da UI.
>
> **Nota sobre `nome_safe`:** é o identificador do projeto e é exibido na árvore por ser
> necessário para a navegação. Pode coincidir com o nome do cliente. Decisão: tratamos o
> identificador do projeto como dado de navegação aceitável (não expomos cpf/contato/endereço/
> valores). Se mesmo o nome for considerado sensível demais, vira refinamento (ex.: rótulo
> anonimizado), mas não bloqueia este slice.

### Novos endpoints (cola fina em `main.py`, dentro de `do_GET`)

| Rota | Auth | Chama | Sucesso | Erros |
|------|------|-------|---------|-------|
| `GET /api/admin/lojas/<id>/projetos` | sessão com `pode_gerir_redes` **ou** `pode_gerir_lojas` | `mod_arvore.projetos_estruturais` | `{ok:true, projetos:[...]}` | 401 sem sessão; 403 fora de escopo/operacional; 404 loja inexistente |
| `GET /api/admin/projetos/<nome_safe>/etapas` | idem | `mod_arvore.etapas_do_projeto` | `{ok:true, etapas:[...]}` | 401; 403 fora de escopo; 404 projeto inexistente |

- São **endpoints administrativos novos**, distintos dos operacionais (que continuam 403 para
  papéis admin). Diferença: nunca retornam PII nem valores — só estrutura/status.
- `PermissionError` do módulo → resposta **403** (sem vazar existência de dados).

## Frontend (`static/index.html`)

### Aterrissagem por papel

Em `carregarUsuarioAutenticado`, após `_usuarioAtual` carregar:
- `pode_gerir_redes` (super_admin) → `goPage(7)` + `adminCarregarConsole()` (aterrissa em Plataforma).
- `admin_rede` → `goPage(7)` + `adminCarregarConsole()` (aterrissa em Rede via lógica existente
  `index.html:6372-6373`).
- Operacional → inalterado (page 0).

### Visibilidade do menu (só super_admin)

Quando `pode_gerir_redes && !loja_id`, esconder `nav-00` (Projetos), `nav-05` (Clientes),
`nav-06` (Parceiros) via `style.display='none'` — mesmo padrão já usado para `nav-07`.
`admin_rede` mantém o menu.

### Árvore — novo nível 4 "Projeto"

- `_adminNav` ganha `projeto: {nome, status}` e suporta `nivel: 4`.
- `adminBreadcrumb()` ganha o segmento `Plataforma › Rede › Loja › Projeto`.
- `adminIrNivel(n)` limpa `projeto` ao subir para níveis ≤ 3.
- `adminRenderLoja` ganha **3ª aba "Projetos"** (ao lado de "Dados da loja" / "Usuários da loja"),
  que chama `GET /api/admin/lojas/<id>/projetos` e renderiza tabela:
  Projeto · Status · Etapa atual · Progresso (`concluidas/total`) · "Abrir ›".
- `adminEntrarProjeto(nome, status)` → `nivel 4` → `adminRenderProjeto()`: chama
  `GET /api/admin/projetos/<nome_safe>/etapas` e lista as etapas com status, destacando a etapa
  atual. **Read-only, sem ações.**

### Fluxo de dados

```
login → /api/auth/me → aterrissagem por papel
super_admin → Painel Admin (Plataforma)
  └ Entrar rede → Rede (lojas + admins)
      └ Entrar loja → Loja [Dados | Usuários | Projetos]
          └ aba Projetos → GET /api/admin/lojas/<id>/projetos
              └ Abrir projeto → nível 4 → GET /api/admin/projetos/<nome_safe>/etapas
```

### Tratamento de erros (UI)

- **403** (fora de escopo) → "Sem acesso a esta loja/projeto." e volta um nível. Não vaza existência.
- **404** (loja/projeto inexistente) → "Não encontrado."
- **Falha de rede** → padrão atual (`avisoPopup` / estado "Erro de conexão").
- **Lista vazia** → "Nenhum projeto nesta loja." / "Nenhuma etapa registrada."

## Testes

### Backend (pytest) — garantia principal

- `projetos_estruturais`:
  - super_admin vê qualquer loja; admin_rede só lojas da própria rede (`PermissionError` fora);
    operacional bloqueado.
  - **Assert explícito das chaves do dict** — nenhum campo de PII/valor presente.
  - Agregação correta de `etapa_atual` / `etapas_concluidas` / `total_etapas`.
- `etapas_do_projeto`:
  - escopo pela loja do projeto; projeto inexistente; retorno só com chaves liberadas; ordenação.
- Endpoints: 200 no escopo, 403 fora, 404 inexistente, 403 para papel operacional, 401 sem sessão.

### Frontend — verificação manual (sem teste JS no projeto)

- super_admin: cai no Painel Admin (Plataforma), sem Projetos/Clientes/Parceiros no menu;
  navega rede → loja → aba Projetos → projeto → etapas.
- admin_rede: cai no nível Rede; menu operacional visível.
- operacional: inalterado (page 0).

## Fora deste slice (registrado)

- Nível "documentos" (D1–D45) da árvore — depende do banco de documentos (#8).
- Multi-papel / multi-loja do mesmo usuário (ex.: Marcelo no seed Orizon) — tratar em #6.
- Painel de busca global LGPD (#4); painel de config de rede (#7); painel de config de loja (#8).

## Arquivos afetados

- **Novo:** `mod_arvore.py`
- **Novo:** `tests/test_arvore.py` (ou nome equivalente do harness)
- **Editado:** `main.py` (2 rotas GET novas em `do_GET`)
- **Editado:** `static/index.html` (aterrissagem, visibilidade de menu, nível 4 da árvore)
