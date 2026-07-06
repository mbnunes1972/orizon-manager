# Cadastro de usuários por modal nos 3 níveis do console — Design

**Data:** 2026-06-22
**Status:** Aprovado (aguardando plano de implementação)
**Contexto:** F2 multi-tenant (console de 3 níveis Plataforma → Rede → Loja) já existe.
Esta entrega troca os `prompt()` de criação/edição de usuário por modais e **define**
como administradores de rede (`admin_rede`) e gestores gerais (`super_admin`) são criados.

---

## 1. Problema

O CRUD de usuários existe no backend (`POST/PATCH/GET /api/admin/usuarios`, com escopo de
tenancy em `mod_tenancy.atribuir_tenant_usuario`), mas o frontend usa **cadeias de
`prompt()`** (`adminUsuariosNovo` / `adminUsuariosEditar` em `static/index.html` ~6476),
inclusive pedindo o *slug* do perfil digitado à mão. Além disso há duas lacunas:

1. Só o **Nível 3** (aba "Usuários da loja") cria usuários. Não há UI para criar
   **admin_rede** (Nível 2) nem **super_admin / "gestor geral"** (Nível 1).
2. Quando super_admin/admin_rede entra numa loja por drill-down, o `POST` atual **não
   envia `loja_id`** — a criação quebraria para eles (o backend só herda a loja para
   usuário de loja).

## 2. Objetivo

Um **modal único reutilizável** de cadastro/edição de usuário, servindo os 3 níveis do
console, com o `<select>` de perfil populado pelo backend (única fonte da verdade =
`perfis.py` + `mod_tenancy`). Diretor e Gerente Administrativo/Financeiro criam e alteram
qualquer usuário **da própria loja**; admin_rede gere usuários das lojas da rede **e seus
pares admin_rede**; super_admin gere todos os níveis.

### Não-objetivos (YAGNI)
- Recuperação de senha por e-mail (o campo e-mail é só cadastral por ora).
- Exclusão física de usuários — mantém-se soft delete (`ativo=0`).
- Auto-geração de login — login continua texto livre digitado pelo admin.

## 3. Decisões (confirmadas no brainstorming)

| Tema | Decisão |
|---|---|
| Arquitetura do modal | **Modal único reutilizável**, dropdown de perfil vindo do backend |
| Campos cadastrais | nome, login, senha, **telefone, whatsapp, e-mail, CPF**, perfil |
| admin_rede gere pares | **Sim** — admin_rede cria/edita outro admin_rede na própria rede (não super_admin) |
| Remoção | **Soft delete** (`ativo=0`); usuário nunca é excluído (preserva histórico) |
| Trava anti-lockout | Usuário logado **não** pode rebaixar o próprio perfil nem se inativar |
| Terminologia | "usuários de rede" = `admin_rede`; "gestor geral" = `super_admin` |

## 4. Arquitetura

### 4.1 Modelo de dados — migração `usuarios_contato_2026`
Adiciona ao `usuarios` (todas `nullable`, no padrão idempotente das migrações de
`database.py`): `email`, `cpf`, `whatsapp`. (`nome`, `login`, `telefone` já existem.)

### 4.2 Regras puras (sem I/O)

**`mod_tenancy.atribuir_tenant_usuario(ator, dados)`** — afrouxar o ramo `admin_rede`:
- `nivel_novo == 'super_admin'` → continua bloqueado (`"Sem permissão para criar esse perfil."`).
- `nivel_novo == 'admin_rede'` → permitido; retorna `(None, ator['rede_id'], [])` (par na mesma rede).
- demais → comportamento atual (exige `loja_id` da rede).

**`mod_tenancy.perfis_atribuiveis(ator, escopo)`** — nova função pura, fonte do dropdown.
Retorna lista de slugs que `ator` pode atribuir em `escopo`:
- `escopo == 'loja'` → todos os slugs de `perfis.py` **exceto** `super_admin` e `admin_rede`.
  Disponível a diretor/gerente_adm_fin (própria loja), admin_rede (lojas da rede), super_admin.
- `escopo == 'rede'` → `['admin_rede']`. Disponível a super_admin e admin_rede.
- `escopo == 'plataforma'` → `['super_admin']`. Disponível só a super_admin.
- Ator sem permissão no escopo → lista vazia.

**`mod_usuarios`** — validar `email` (formato simples, só se preenchido) e `cpf` (opcional,
sem dígito verificador obrigatório nesta fase). `nome`/`login`/`senha`/`nivel` seguem
obrigatórios na criação; edição mantém campos opcionais.

### 4.3 Endpoints (`main.py`)

- **`GET /api/admin/usuarios/perfis-permitidos?escopo=&loja_id=&rede_id=`** — novo.
  Resolve o ator, chama `perfis_atribuiveis`, devolve `{"ok":True, "perfis":[{slug,rotulo}]}`.
  Alimenta o `<select>` do modal. 403 se o ator não tem `gerir_usuarios`.
- **`GET /api/admin/usuarios`** — aceitar filtros opcionais `escopo`/`loja_id`/`rede_id`
  para cada nível mostrar só a sua fatia:
  - `escopo=loja&loja_id=X` → usuários da loja X (loja_id == X).
  - `escopo=rede&rede_id=Y` → admins da rede Y (nivel admin_rede, rede_id == Y).
  - `escopo=plataforma` → gestores gerais (nivel super_admin, loja_id e rede_id NULL).
  - sem filtro → comportamento atual (todos os visíveis no escopo do ator).
  O escopo do ator continua aplicado por cima do filtro (não amplia visibilidade).
- **`POST /api/admin/usuarios`** — gravar `email/cpf/whatsapp` além dos atuais. Frontend
  envia `loja_id` (Nível 3) ou `rede_id` (Nível 2) ou nada (Nível 1) conforme o contexto;
  a lógica de escopo existente (`atribuir_tenant_usuario` + `pode_ver_loja`) cobre.
- **`PATCH /api/admin/usuarios/<id>`** — três mudanças:
  1. gravar `nome/email/cpf/whatsapp` também (hoje só nivel/telefone/ativo/senha);
  2. afrouxar anti-escalonamento (atual linha ~3743): `admin_rede` pode atribuir
     `nivel=admin_rede`; só `super_admin` continua exigido para atribuir `super_admin`;
  3. **trava anti-lockout**: se `alvo.id == ator.id`, recusar mudança do próprio `nivel`
     e auto-inativação (`ativo=0`) com 403/erro claro.

### 4.4 Frontend (`static/index.html`) — substitui os `prompt()`

**Componente `modalUsuario`** (HTML + funções abrir/fechar/salvar):
- Campos: **nome, login, senha** (hint "em branco mantém" na edição), **telefone,
  whatsapp, e-mail, CPF, perfil** (`<select>`), e **toggle Ativo** (só na edição).
- Título dinâmico "Novo usuário" / "Editar usuário".
- Na **edição**: `login` somente-leitura; senha em branco = mantém. Se o alvo for o
  próprio usuário logado, `perfil` e `Ativo` ficam **desabilitados** (com nota explicativa).
- `<select>` de perfil preenchido por `GET .../perfis-permitidos` para o contexto atual.
- Erro do backend mantém o modal aberto; mensagem via `avisoPopup`/`showToast`.

**Wiring por nível:**
- **Nível 3 "Usuários da loja"**: `+ Novo` e `Editar` abrem o modal com
  `{escopo:'loja', loja_id: _adminNav.loja?.id || _usuarioAtual.loja_id}` — corrige o
  caso de super_admin/admin_rede drilando numa loja.
- **Nível 2 "Rede"**: nova seção **"Administradores da rede"** (tabela + `+ Novo
  administrador`), contexto `{escopo:'rede', rede_id: _adminNav.rede.id}`. Visível a
  super_admin e admin_rede.
- **Nível 1 "Plataforma"**: nova seção **"Gestores gerais"** (tabela + `+ Novo gestor`),
  contexto `{escopo:'plataforma'}`. Visível só a super_admin.

As tabelas de cada nível usam `GET /api/admin/usuarios` com o filtro de escopo
correspondente.

## 5. Fluxo de dados (criação no Nível 3)

1. Modal abre com `{escopo:'loja', loja_id:X}`.
2. `GET /api/admin/usuarios/perfis-permitidos?escopo=loja&loja_id=X` → preenche o `<select>`.
3. Salvar → `POST /api/admin/usuarios` com `{nome, login, senha, nivel, telefone,
   whatsapp, email, cpf, loja_id:X}`.
4. Backend: `validar_novo_usuario` + `atribuir_tenant_usuario(ator, {nivel, loja_id:X})`
   → resolve escopo e checa `pode_ver_loja`.
5. Tabela do nível recarrega.

## 6. Tratamento de erros
- Validação do backend devolve `{"ok":False,"erro":"..."}`; o modal exibe e permanece aberto.
- Escopo/permissão inválidos → 403 com mensagem ("Loja fora do seu escopo.", "Sem permissão
  para atribuir esse perfil.", "Não é possível alterar o próprio perfil/status.").
- Login duplicado → erro de validação (regra atual preservada).

## 7. Testes

**Unitários (puros):**
- `perfis_atribuiveis` — matriz ator × escopo (diretor/gerente_adm_fin, admin_rede,
  super_admin × loja/rede/plataforma), incluindo listas vazias para atores sem permissão.
- `atribuir_tenant_usuario` — admin_rede cria par admin_rede (rede herdada) e **não** cria
  super_admin.
- `mod_usuarios` — validação de e-mail e CPF; obrigatórios na criação.

**E2E (harness 2 lojas / 2 redes, padrão F4):**
- diretor cria usuário da própria loja; dropdown **não** contém super_admin/admin_rede.
- admin_rede cria usuário em loja da rede **e** cria par admin_rede; **não** cria super_admin.
- super_admin cria usuário de loja, admin_rede e super_admin.
- anti-lockout: auto-inativação e auto-rebaixamento bloqueados (403).
- soft delete: `ativo` alterna; histórico (LogAutorizacao) intacto.
- isolamento: admin_rede não edita usuário de outra rede (403); diretor não vê/edita
  usuário de outra loja.
- campos `email/cpf/whatsapp` persistem na criação e na edição.

## 8. Arquivos afetados
- `database.py` — migração `usuarios_contato_2026` + colunas no modelo `Usuario`.
- `mod_tenancy.py` — `atribuir_tenant_usuario` (afrouxar), `perfis_atribuiveis` (nova).
- `mod_usuarios.py` — validação dos novos campos.
- `main.py` — endpoint `perfis-permitidos`; filtros no `GET`; `POST`/`PATCH` com novos
  campos; afrouxar anti-escalonamento; trava anti-lockout no `PATCH`.
- `static/index.html` — `modalUsuario`; seções de usuários nos Níveis 1 e 2; wiring do
  Nível 3; remoção das cadeias de `prompt()`.
- `docs/USUARIOS.md` — documentar campos cadastrais e a regra de auto-gestão de admin_rede.
- `tests/` — unitários + E2E acima.
