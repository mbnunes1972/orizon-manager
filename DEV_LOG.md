# DEV_LOG.md — Diário de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## RESUMO ATUAL
> Atualizado em: 2026-06-07

### [ESTADO] O que está funcionando
- App Python rodando em `http://167.88.33.121:8765` (servidor DEV)
- Sistema de autenticação completo: login, logout, sessões via cookie
- Três níveis de usuário: Diretor (50%), Gerente (20%), Consultor (10%)
- Usuários criados: `pdm2026` (Pedro/Diretor), `lds2026` (Luiz/Gerente), `mds2026` (Marcia/Consultora)
- Botão de perfil na sidebar: foto, telefone, WhatsApp, email editáveis
- Modal de autorização delegada: ao exceder limite, solicita credenciais de Gerente ou Diretor
- Log de autorizações registrado no banco (`log_autorizacoes`)
- Restaurar valores ao cancelar modal de parâmetros: implementado via `_mpSnapshot`

### [PENDENTE]
- **ALTA** — Após autorização delegada bem-sucedida, o hint de limite não some e o sistema não reconhece o novo limite do autorizador. Solução: criar variável `_limiteAutorizado` e fazer `cfgGetDescontoMax()` retornar esse valor até o modal ser fechado.
- **MÉDIA** — Tela de negociação (`neg-desconto` na sidebar) não valida limite pelo usuário autenticado — ainda usa sistema antigo de perfis (`_perfilAtivo`)
- **MÉDIA** — Servidor DEV ainda sem domínio — acessível só por IP
- **BAIXA** — `patch_index.py` e `patch_modal_params_v2.py` podem ser removidos da pasta após validação

### [DECIDIDO]
- Banco de dados: SQLite + SQLAlchemy (migração futura para MySQL via troca de string de conexão)
- Limites de desconto: Consultor 10%, Gerente 20%, Diretor 50%
- Servidor DEV: Hostinger VPS `167.88.33.121`, EasyPanel instalado, app Omie_V3 roda fora do EasyPanel por ora
- Repositório GitHub: `https://github.com/mbnunes1972/omie_v3`
- Foto e dados extras do perfil salvos no `localStorage` do browser (não no banco por ora)
- Autorização delegada registrada no banco mesmo quando negada

### [CONTEXTO] Arquivos e variáveis chave
**Arquivos principais:**
- `main.py` — servidor HTTP, rotas, inicialização
- `database.py` — SQLAlchemy, modelos: `Usuario`, `Sessao`, `LogAutorizacao`
- `auth.py` — login, logout, validação de sessão, autorização delegada
- `auth_routes.py` — rotas HTTP de autenticação integradas ao main.py
- `seed.py` — cria usuários iniciais
- `static/index.html` — frontend completo (SPA)
- `static/login.html` — tela de login

**Variáveis JS chave no frontend:**
- `_usuarioAtual` — usuário autenticado (carregado via `/api/auth/me`)
- `_LIMITES_NIVEL` — `{ consultor: 10, gerente: 20, diretor: 50 }`
- `cfgGetDescontoMax()` — retorna limite do usuário atual
- `_mpSnapshot` — snapshot dos parâmetros ao abrir modal (para restaurar ao cancelar)
- `_resolveAutorizacao` — Promise resolver do modal de autorização delegada

**Rotas de autenticação:**
- `GET /login` — tela de login
- `GET /logout` — encerra sessão
- `GET /api/auth/me` — retorna usuário da sessão
- `POST /api/auth/login` — autentica, retorna token via cookie
- `POST /api/auth/logout` — invalida sessão
- `POST /api/auth/verificar_desconto` — verifica se desconto está dentro do limite
- `POST /api/auth/autorizar_desconto` — autorização delegada com log

---

## HISTÓRICO

### Sessão 2026-06-07
**Objetivo:** Subir Omie_V3 no servidor DEV e implementar sistema de autenticação

**Realizado:**
- Descoberto servidor DEV (167.88.33.121) com EasyPanel + ArchDecorPoints já instalados
- Criado repositório GitHub `mbnunes1972/omie_v3`
- Push do código local para GitHub e clone no servidor
- Instalado SQLAlchemy no servidor e localmente
- App subindo com `python3 main.py` dentro de `screen`
- Correção do bind para `0.0.0.0` (acesso externo)
- Implementado sistema de autenticação completo (database.py, auth.py, auth_routes.py)
- Criados 3 usuários via seed.py
- Integrado login ao main.py (proteção de rotas, cookie de sessão)
- Adicionado botão de perfil na sidebar com modal de edição
- Corrigido modal de parâmetros: snapshot, restauração ao cancelar, validação de limite
- Implementado modal de autorização delegada com log no banco
- Iniciado levantamento de requisitos para REQUIREMENTS.md

**Arquivos modificados:**
- `main.py` — autenticação integrada, bind 0.0.0.0
- `static/index.html` — login, perfil, limites, modal params, autorização delegada
- `static/login.html` — novo
- `database.py` — novo
- `auth.py` — novo
- `auth_routes.py` — novo
- `seed.py` — novo
- `omie.db` — criado automaticamente
