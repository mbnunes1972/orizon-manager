# Módulo de Autenticação — SPEC

**Status:** `[IMPLEMENTADO]`

---

## Visão geral

Sistema de autenticação com três níveis de acesso, sessões server-side e autorização delegada para descontos acima do limite do usuário.

---

## Níveis de acesso

| Nível | Limite desconto | Vê parâmetros internos | Pode autorizar |
|---|---|---|---|
| `consultor` | 10% | Não | Não |
| `gerente` | 20% | Sim | Até 20% |
| `diretor` | 50% | Sim | Até 50% |

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
