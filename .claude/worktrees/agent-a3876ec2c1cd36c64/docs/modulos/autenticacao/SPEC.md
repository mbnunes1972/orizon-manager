# Módulo de Autenticação — SPEC

**Status:** `[IMPLEMENTADO]`

---

## Visão geral

Sistema de autenticação com quatro níveis de acesso, sessões server-side e autorização delegada para descontos acima do limite do usuário.

---

## Níveis de acesso

| Nível | Limite desconto | Vê parâmetros internos | Pode autorizar | Painel exclusivo |
|---|---|---|---|---|
| `consultor` | 10% | Não | Não | — |
| `gerente` | 20% | Sim | Até 20% | — |
| `diretor` | 50% | Sim | Até 50% | — |
| `admin` | 50% | Sim | Até 50% | Painel Admin (page-07) |

`gerente`, `diretor` e `admin` podem autorizar ações gerenciais (ex.: reabrir etapas em
cascata via `POST /api/projetos/<nome>/ciclo/<codigo>/reabrir`, `desfazer_aprovacao`, e a
**edição pontual do contrato** via `POST /api/projetos/<nome>/contrato/editar`),
validadas por login+senha e auditadas em `log_acoes_gerenciais`.

**Usuários atuais** (no banco): `pdm2026` (diretor), `lds2026` (gerente), `mds2026`
(consultor) — criados por `seed.py` — e `admin2026` (admin, nome "Administrador"),
presente no banco mas **não** no `seed.py`. (Senha de teste do admin deve ser trocada
antes de produção.)

### Papel do `admin` (atual × pretendido)

- **Hoje:** acesso total a vendas + **Painel Admin (page-07)** — fila de sincronização
  Omie (clientes com `omie_sync_status` pendente/erro, botão "Tentar" por cliente).
  Rotas exclusivas: `GET /api/admin/omie-sync`, `POST /api/admin/omie-sync/<id>/retry`.
- **Direção pretendida:** evoluir o `admin` para um papel de **configuração do sistema**
  (não apenas vendas + sync). Primeiro candidato concreto: o **painel de configuração de
  loja** que fornecerá as **testemunhas do contrato** (hoje hardcoded em `mod_contrato._TESTEMUNHAS`
  — ver `docs/modulos/contratos/SPEC.md`).

---

## Fluxo de login

1. Usuário acessa `/` → sistema verifica cookie `omie_session`
2. Se inválido ou ausente → redireciona para `/login`
3. Usuário preenche login e senha → POST `/api/auth/login`
4. Backend valida credenciais → gera token hex-32 → salva na tabela `sessoes`
5. Seta cookie `omie_session` com o token (HttpOnly, 8 horas)
6. Redireciona para `/`

---

## Autorização delegada

Quando um usuário tenta aplicar desconto acima do seu limite:

**Na sidebar (tela de negociação):**
1. Usuário digita desconto acima do limite → aparece hint vermelho + botão "✓ OK"
2. Clica "✓ OK" → abre modal de autorização (login + senha do autorizador)
3. Autorizador insere credenciais → POST `/api/auth/autorizar_desconto`
4. Se aprovado: `_limiteAutorizado` = desconto aprovado, hint some
5. Se negado: mensagem de erro, desconto volta ao valor anterior

**No modal de parâmetros:**
1. Usuário digita desconto acima do limite → hint vermelho
2. Clica "Salvar e continuar" → abre modal de autorização
3. Mesmo fluxo acima

**Regras:**
- O limite autorizado é o desconto específico aprovado (não o limite do perfil do autorizador)
- Ex: gerente autoriza 15% → `_limiteAutorizado = 15`, não 20%
- Persiste durante toda a negociação do projeto
- Reseta ao trocar de projeto
- Desconto salvo no projeto vira limite autorizado ao reabrir

---

## Perfil do usuário

Botão de avatar na sidebar abre modal com:
- Foto (upload, salva em localStorage)
- Nome (somente leitura)
- Nível (somente leitura)
- Limite de desconto (somente leitura)
- Telefone, WhatsApp, Email (editáveis, salvos em localStorage)
- Botão "Sair" (logout)

---

## Arquivos relevantes

- `database.py` — modelos `Usuario`, `Sessao`, `LogAutorizacao`
- `auth.py` — funções `fazer_login`, `fazer_logout`, `validar_sessao`, `autorizar_desconto`
- `auth_routes.py` — rotas HTTP integradas ao `main.py`
- `static/login.html` — tela de login
- `static/index.html` — funções `carregarUsuarioAutenticado`, `cfgGetDescontoMax`, `abrirModalAutorizacao`

---

## User Stories

**US-001** — Como consultor, quero fazer login com meu usuário e senha para acessar o sistema.

**US-002** — Como consultor, quero que o sistema bloqueie descontos acima de 10% e solicite autorização gerencial.

**US-003** — Como gerente, quero autorizar descontos acima do limite do consultor usando minhas credenciais, sem precisar fazer login novamente.

**US-004** — Como diretor, quero autorizar descontos acima do limite do gerente.

**US-005** — Como qualquer usuário, quero editar meu telefone, WhatsApp e email no perfil.
