# Auditoria de Segurança (AppSec) — Orizon Manager / Dalmóbile

**Tipo:** Auditoria estilo *Florence* (rigorosa, enterprise-grade, orientada a evidências)
**Alvo:** Sistema de PRODUÇÃO real, multi-loja. Backend Python puro (`http.server`, SEM framework), SQLAlchemy + SQLite, frontend `static/index.html`.
**Data:** 2026-07-03
**Metodologia:** Mapeamento dos endpoints (`do_GET`/`do_POST`/`do_PUT`/`do_PATCH` em `main.py`), inspeção de autenticação e autorização/tenancy por rota, revisão de `auth.py`/`auth_routes.py`/`perfis.py`/`mod_tenancy.py`/`storage.py`/`database.py`, e verificação das classes OWASP (AuthN, AuthZ/IDOR, Injection, Secrets, Exposição HTTP, Upload).
**Escopo de arquivos:** raiz do projeto. Excluídos: `.claude\worktrees\`, `.git`, `__pycache__`.
**Restrição:** READ-ONLY — nenhum exploit executado; achados provados por leitura de código e evidência de caminho/linha.

---

## Sumário executivo

O sistema tem uma **camada de autorização de tenancy bem construída** para as rotas "de negócio" (projetos, clientes, orçamentos, contratos, medição, usuários/lojas/redes): há um padrão consistente `get_usuario_sessao` → `_ator_dict` → `mod_tenancy.escopo_operacional` → `_obj_da_loja`/`_projeto_da_loja`, e as rotas de gestão de usuários têm anti-escalonamento e anti-lockout. **Esse é o ponto forte da aplicação.**

Contudo, há **falhas graves fora dessa camada**, concentradas em: (1) endpoints de configuração/perfil/exportação **sem qualquer autenticação**, incluindo um **`GET /config` que vaza as credenciais da API Omie**; (2) **hashing de senha com SHA-256 puro, sem salt e sem iterações**; (3) **credencial padrão de super_admin (`sad2026`/`trocar123`) semeada automaticamente**; (4) **sessão de exportação global compartilhada entre todos os usuários** (vazamento cross-usuário de dados de cliente/projeto); (5) **ausência total de rate limiting / proteção a brute force / CSRF**; e (6) **path traversal na escrita de XML** e no *serving* de `.html`. Como o backend não usa framework, **não há defesa embutida** (sem CSRF token, sem cabeçalhos de segurança, sem escaping automático) — tudo depende do código, e várias defesas simplesmente não existem.

---

## Achados

### 🔴 A-01 — `GET /config` vaza credenciais da API Omie sem autenticação

**Severidade:** 🔴 Crítico
**Evidência:**
- `main.py:287-288`
  ```python
  elif path == "/config":
      self.send_json(config_carregar())
  ```
- `storage.py:74-80` — `config_carregar()` retorna o conteúdo de `omie_config.json`, que contém `app_key` e `app_secret`.
- `omie_config.json` (em disco):
  ```json
  { "app_key": "7704233295759", "app_secret": "05fc0d8f6098464b4ca7c29a515ac663", "intervalo": 0.5 }
  ```
- `docs/arquitetura/ROTAS.md:60` documenta explicitamente: *"GET /config | Retorna configuração Omie (app_key, app_secret)"*.
- Confirmação: o bloco `do_GET` para `/config` **não chama** `get_usuario_sessao` nem qualquer checagem de perfil (contraste com `/projetos` em `main.py:320-336`).

**Vetor de ataque:** Qualquer pessoa com acesso de rede ao servidor (em produção, `ORIZON_HOST=0.0.0.0` — vide `main.py:4979-4981`) faz `GET /config` **sem cookie de sessão** e recebe o `app_secret` da conta Omie da empresa. Nenhuma sessão, nenhum perfil.

**Impacto:** Comprometimento total das credenciais do ERP Omie (dados fiscais, cadastros, pedidos). Um invasor pode operar a API Omie da Dalmóbile como se fosse a empresa. Crítico para um sistema de produção.

**Recomendação:**
1. Exigir sessão **e** perfil administrativo (`ver_parametros`/`gerir_lojas`) em `GET /config`.
2. **Nunca** retornar `app_secret` ao cliente — retornar apenas um booleano "configurado: true/false" ou uma máscara (`****663`).
3. **Rotacionar imediatamente** `app_key`/`app_secret` na Omie (o segredo está exposto neste relatório e em disco de produção).
4. Migrar segredos para variáveis de ambiente / cofre (a própria `storage.py:71` sugere `os.environ`).

---

### 🔴 A-02 — Endpoints de mutação sem autenticação: `POST /config`, `/perfis`, `/perfis/ativo`, `/exportar`, `/carregar`, `/cancel`, `/confirm`

**Severidade:** 🔴 Crítico
**Evidência:** `main.py:1357-1408` (bloco inicial de `do_POST`, antes de qualquer verificação de sessão):
```python
if path == "/config":
    config_salvar(json.loads(body)); self.send_json({"ok": True})
elif path == "/perfis":
    perfis_salvar(dados); self.send_json({"ok": True})
elif path == "/perfis/ativo":
    ... perfis_salvar(cfg) ...
elif path == "/carregar":
    arquivos, campos = _parse_multipart(body, ct); ... carregar_xmls(arquivos) ...
elif path == "/exportar":
    ... exporta ambientes para a Omie usando app_key/app_secret ...
```
Nenhuma dessas rotas chama `get_usuario_sessao`. As GET equivalentes (`/perfis`, `/perfis/ativo`, `/logs`, `/pagamentos` em `main.py:290-318`) também não autenticam.

**Vetor de ataque:**
- `POST /config` sem sessão → **grava** `omie_config.json` (invasor injeta credenciais próprias, ou zera as da empresa → DoS).
- `POST /perfis` sem sessão → **reescreve o arquivo global de perfis/limites** (`perfis_config.json`), inclusive `desconto_max_pct` e a `senha_gerente` (vide A-09).
- `POST /exportar` sem sessão → dispara exportação de ambientes para a Omie usando o segredo do servidor.
- `POST /carregar` sem sessão → faz upload/parsing de XML arbitrário no estado global (vide A-05).

**Impacto:** Alteração de configuração crítica e disparo de operações sensíveis por um anônimo. Combinado com A-01, permite tanto ler quanto sobrescrever os segredos.

**Recomendação:** Adicionar guarda de sessão no topo de `do_GET`/`do_POST` (allow-list de rotas públicas: só `/login`, `/api/auth/login`, `/api/auth/me`, estáticos de login). Para `/config` e `/perfis`, exigir perfil administrativo. Idealmente centralizar num único ponto de *dispatch* que rejeita 401 por padrão.

---

### 🔴 A-03 — Hashing de senha inseguro: SHA-256 puro, sem salt e sem iterações

**Severidade:** 🔴 Crítico
**Evidência:** `database.py:13-15, 49-53`
```python
def _hash_senha(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()
...
def check_senha(self, senha):
    return self.senha_hash == _hash_senha(senha)
```

**Vetor de ataque:** Se o `orizon.db` vazar (backup, acesso ao disco, outra falha — e há vários `omie.db.bak-*` na raiz), o atacante quebra as senhas offline: SHA-256 é rápido (bilhões de tentativas/s em GPU) e **sem salt** permite *rainbow tables* e detecção de senhas iguais entre usuários. As senhas seed (`teste123` etc., `seed.py:11-22`) caem instantaneamente. A comparação `==` também **não é *constant-time*** (vetor de *timing* teórico).

**Impacto:** Comprometimento de todas as credenciais em caso de vazamento do banco; reuso de senha compromete outros sistemas dos funcionários.

**Recomendação:** Migrar para um KDF lento com salt: `hashlib.scrypt`, PBKDF2-HMAC (`hashlib.pbkdf2_hmac`, ≥ 600k iterações) ou, preferível, `bcrypt`/`argon2-cffi`. Guardar `algoritmo$salt$hash`, suportar re-hash transparente no login. Usar `hmac.compare_digest` para comparação. Forçar troca de todas as senhas após a migração.

---

### 🔴 A-04 — Credencial padrão de super_admin semeada automaticamente (`sad2026` / `trocar123`)

**Severidade:** 🔴 Crítico
**Evidência:**
- `database.py:632-636` — `_SEED_SA_LOGIN = "sad2026"`, `_SEED_SA_SENHA = "trocar123"`.
- `database.py:710-720` — a migração `tenancy_v2_2026` **cria automaticamente** o super_admin com essa senha se não houver nenhum:
  ```python
  cur.execute("SELECT COUNT(*) FROM usuarios WHERE nivel='super_admin'")
  if ... == 0:
      cur.execute("INSERT INTO usuarios (... senha_hash ...) VALUES (..., ?)",
                  (..., _hash_senha(_SEED_SA_SENHA)))
  ```
- `seed.py:47-52` repete a criação com a mesma senha.

**Vetor de ataque:** O login/senha do administrador de plataforma é **conhecido publicamente** (está no código-fonte e neste relatório). Se essa senha não foi trocada em produção, qualquer um faz login como super_admin (acesso a **todas** as lojas/redes) via `POST /api/auth/login`.

**Impacto:** Controle total da plataforma multi-tenant — bypass completo do isolamento de lojas.

**Recomendação:** Nunca embutir senha padrão de conta privilegiada. Gerar senha aleatória no bootstrap e exibi-la uma única vez no console/log de instalação, forçando troca no primeiro login (flag `senha_provisoria`). Verificar **agora** se `sad2026` ainda usa `trocar123` em produção e trocar.

---

### 🟠 A-05 — Sessão de exportação/estado global compartilhada entre todos os usuários (vazamento cross-usuário)

**Severidade:** 🟠 Alto
**Evidência:** `storage.py:151-172` — `_session` é **um único dicionário de módulo**, global ao processo:
```python
_session: dict = { "dados_carregados": None, "xmls_carregados": None,
                   "nome_cliente": None, "projeto_ativo": None, ... }
def session_get(chave, padrao=None): return _session.get(chave, padrao)
def session_set(chave, valor):       _session[chave] = valor
```
Usado por `/carregar`, `/exportar`, `/logs`, `/confirm` (`main.py:299-309, 1387-1450`). Não há vínculo com o token de sessão do usuário.

**Vetor de ataque:** O usuário A carrega XMLs de um cliente (`session_set("dados_carregados", ...)`, `session_set("nome_cliente", ...)`). O usuário B, em outra loja, faz `GET /logs` (`main.py:299-309`) e recebe `nome_cliente`/`pedidos` do cliente de A; um `POST /exportar` de B opera sobre os `dados_carregados` de A. É um **furo de isolamento multi-tenant** por design (estado por-processo, não por-sessão). O comentário em `storage.py:147` ("um usuário por vez") confirma que a premissa single-user não vale mais no cenário multi-loja em produção.

**Impacto:** Vazamento de dados de cliente entre lojas concorrentes e corrupção/troca de dados de exportação entre operadores simultâneos.

**Recomendação:** Chavear o estado de exportação por `usuario_id` (ou token de sessão): `_session[token][chave]`. Migrar para armazenamento por-sessão (o próprio comentário de `storage.py:148` sugere Redis/cookies assinados).

---

### 🟠 A-06 — Ausência de rate limiting / proteção a brute force no login

**Severidade:** 🟠 Alto
**Evidência:** `auth.py:19-45` (`fazer_login`) e `auth_routes.py:98-120` (`POST /api/auth/login`) — não há contador de tentativas, atraso progressivo, bloqueio de conta nem CAPTCHA. `fazer_login` retorna imediatamente para usuário inexistente vs. senha errada (mesma mensagem, o que é bom), mas nada limita a frequência.

**Vetor de ataque:** *Password spraying* / brute force ilimitado contra `POST /api/auth/login`. Combinado com senhas fracas (seed `teste123`, `trocar123`) e SHA-256 rápido, credenciais caem rápido. Também não há limite de tamanho de corpo (vide A-11) → possível abuso.

**Impacto:** Comprometimento de contas por força bruta; ausência de detecção.

**Recomendação:** Rate limit por IP e por login (ex.: 5 tentativas/5 min, backoff exponencial, bloqueio temporário). Registrar tentativas falhas (já há `LogAutorizacao` para descontos — criar análogo para login). Considerar 2FA para perfis administrativos.

---

### 🟠 A-07 — Path traversal na escrita de XML enviado por upload

**Severidade:** 🟠 Alto
**Evidência:** `main.py:2394` e `main.py:2504-2525`
```python
arq_nome, arq_conteudo = arquivos[0]           # nome do arquivo controlado pelo cliente
...
pasta_xmls = os.path.join(_projeto_path(nome_safe), "xmls")
...
xml_path=  os.path.join("xmls", arq_nome),
...
storage_salvar_texto(os.path.join(pasta_xmls, arq_nome), arq_conteudo)
```
`arq_nome` vem direto do `filename` do multipart (`_parse_multipart`, `main.py:171-172`) — **sem `os.path.basename` nem validação**. Contraste com as rotas de medição, que corretamente aplicam `os.path.basename(fname)` (`main.py:3591, 3634, 3680`).

**Vetor de ataque:** Um usuário autenticado (de qualquer loja) envia um XML com `filename` como `..\..\..\algum_arquivo` (Windows) ou `../../x`. `os.path.join(pasta_xmls, "..\\..\\x")` resolve para fora de `PROJETOS/<projeto>/xmls/`, permitindo **escrever/sobrescrever arquivos** fora da pasta do projeto (ex.: sobrescrever `omie_config.json`, `perfis_config.json`, ou o `projeto.json` de outra loja).

**Impacto:** Escrita arbitrária de arquivo → corrupção de dados, sobrescrita de config, potencial escalonamento (gravar sobre arquivos que o servidor lê).

**Recomendação:** Aplicar `arq_nome = os.path.basename(arq_nome)` e validar extensão `.xml` e nome (`^[\w.\-]+$`) antes de qualquer `os.path.join`. Após montar o caminho, verificar `os.path.realpath(destino).startswith(os.path.realpath(pasta_xmls))`.

---

### 🟠 A-08 — Path traversal / serving de arquivos arbitrários na rota `.html`

**Severidade:** 🟠 Alto
**Evidência:** `main.py:705-722`
```python
elif path.endswith(".html") and path != "/":
    nome    = path.lstrip("/")
    caminho = os.path.join(_BASE_DIR, nome)
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f: body = f.read().encode()
        ...
        self.send_header("Access-Control-Allow-Origin", "*")   # CORS wildcard
```
`path` vem de `urlparse(self.path).path`; `unquote` do servidor pode reintroduzir `%2e%2e%2f` → `../`. Só há o filtro `endswith(".html")`. **Sem autenticação** e **sem confinamento** a `_BASE_DIR`.

**Vetor de ataque:** `GET /../../<algo>.html` ou payloads codificados para ler arquivos `.html` fora do diretório base sem sessão. O `Access-Control-Allow-Origin: *` ainda permite que qualquer origem web leia essas respostas via `fetch`. Embora limitado à extensão `.html`, é leitura de arquivo não autenticada + confinamento ausente.

**Impacto:** Divulgação de conteúdo de arquivos `.html` fora do escopo; superfície de CORS aberta.

**Recomendação:** Confinar: `full = os.path.realpath(os.path.join(_STATIC_DIR, nome))` e rejeitar se `not full.startswith(os.path.realpath(_STATIC_DIR))`. Exigir sessão para páginas de app. Remover `Access-Control-Allow-Origin: *` (não é necessário para conteúdo same-origin).

---

### 🟠 A-09 — Senha de gerente em texto plano no arquivo de perfis (`senha_gerente: "1234"`)

**Severidade:** 🟠 Alto
**Evidência:** `storage.py:105-112`
```python
"gerente": { ..., "senha_gerente": "1234" }
```
Esse `PERFIS_PADRAO` é escrito em `perfis_config.json` (`storage.py:131`) e é lido/escrito pelas rotas `GET/POST /perfis` **sem autenticação** (A-02). O `perfis_config.json` também está listado como "ruído" que fica sempre modificado no working tree.

**Vetor de ataque:** `GET /perfis` (anônimo) revela `senha_gerente`. Se essa senha for usada em algum fluxo de autorização legado do frontend, é bypass direto de aprovação gerencial.

**Impacto:** Bypass de autorização gerencial / vazamento de segredo compartilhado.

**Recomendação:** Remover segredos de `perfis_config.json`; qualquer autorização deve passar por `auth.autorizar_desconto` (que valida usuário+senha no banco). Autenticar `GET/POST /perfis`.

---

### 🟡 A-10 — Cookie de sessão sem `Secure` e sem `SameSite`; ausência de proteção CSRF

**Severidade:** 🟡 Médio
**Evidência:**
- `auth_routes.py:110-113` — `Set-Cookie: {COOKIE_NAME}={token}; Max-Age=28800; Path=/; HttpOnly`. **Falta `Secure`** (cookie trafega em HTTP puro) e **falta `SameSite`** (padrão de navegador ajuda, mas explicitar `Lax`/`Strict` é a boa prática).
- Nenhuma rota valida token anti-CSRF; todas as mutações confiam apenas no cookie. Não há verificação de `Origin`/`Referer`.

**Vetor de ataque:** Sem `SameSite` explícito e sem token CSRF, um site malicioso pode disparar requisições autenticadas *cross-site* (POST/PUT) reaproveitando o cookie da vítima (as mutações usam JSON/multipart; alguns navegadores/versões e formulários simples permitem CSRF). Sem `Secure`, o token pode vazar por MITM em HTTP.

**Impacto:** Ações não autorizadas em nome do usuário logado; roubo de token em rede insegura.

**Recomendação:** `Set-Cookie: ...; HttpOnly; Secure; SameSite=Strict; Path=/`. Servir sempre por HTTPS em produção. Adicionar token CSRF (double-submit cookie ou header custom exigido, ex.: `X-Requested-With`) e validar `Origin` nas mutações.

---

### 🟡 A-11 — Vazamento de detalhes de erro (`str(e)`) e ausência de cabeçalhos de segurança

**Severidade:** 🟡 Médio
**Evidência:**
- Dezenas de rotas retornam `self.send_json({"ok": False, "erro": str(e)}, code=500)` (ex.: `main.py:338, 366, 474, 701, 944, 974, 1285, 2532, 2942`), expondo mensagens internas (caminhos, SQL, detalhes de exceção) ao cliente.
- Nenhuma resposta define `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Referrer-Policy` ou `Strict-Transport-Security` (busca em `send_header` só encontra `Content-Type`, `Cache-Control`, `Access-Control-Allow-Origin`).

**Vetor de ataque:** Erros revelam estrutura interna (nomes de tabela/coluna, caminhos de disco Windows/WSL) úteis para escalar outros ataques. Ausência de CSP/`X-Frame-Options` facilita XSS/clickjacking no SPA (`index.html` monta HTML com dados do servidor via JS inline).

**Impacto:** Reconhecimento facilitado; superfície de XSS/clickjacking maior.

**Recomendação:** Mensagem genérica ao cliente (`"Erro interno"`) + log server-side com o detalhe. Adicionar cabeçalhos de segurança padrão em `send_json`/respostas HTML (CSP restritiva, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, HSTS em HTTPS).

---

### 🟡 A-12 — Ausência de limite de tamanho de corpo / upload (DoS de memória)

**Severidade:** 🟡 Médio
**Evidência:** `main.py:1354-1355, 3702-3703` — `length = int(self.headers.get("Content-Length", 0)); body = self.rfile.read(length)` lê o corpo inteiro em memória sem teto. `_parse_multipart` (`main.py:153-175`) idem. Não há validação de tamanho nos uploads de XML/medição.

**Vetor de ataque:** `Content-Length` grande → o servidor **single-thread** (`HTTPServer`, `main.py:4981`) aloca tudo em memória e bloqueia; um único request grande derruba/trava o serviço para todos.

**Impacto:** Negação de serviço trivial.

**Recomendação:** Rejeitar `Content-Length` acima de um limite (ex.: 10 MB) com 413; validar tamanho por tipo de upload. Considerar `ThreadingHTTPServer` **com** correção do estado global (vide A-05/A-13) para não travar todos os clientes.

---

### 🔵 A-13 — Estado por-requisição em global de módulo (`_REQ_LOJA_ATIVA`) — frágil se o servidor virar multi-thread

**Severidade:** 🔵 Baixo (condicional)
**Evidência:** `main.py:246-250` — `_REQ_LOJA_ATIVA` é global de módulo, setado no início de cada handler (`do_GET`/`do_POST`/`do_PUT`/`do_PATCH`) e lido depois por `_ator_dict` (`main.py:4828-4829`). Funciona hoje só porque `HTTPServer` é single-thread.

**Vetor de ataque:** Se alguém trocar para `ThreadingHTTPServer` (recomendado por A-12), duas requisições concorrentes de lojas diferentes podem sobrescrever `_REQ_LOJA_ATIVA` uma da outra → **um usuário opera sob a loja ativa de outro** (quebra de tenancy por race). Mesmo problema estrutural de A-05.

**Impacto:** Potencial quebra de isolamento de loja sob concorrência (latente).

**Recomendação:** Passar `header_loja_id` como parâmetro (já é aceito por `_ator_dict`) em vez de global; ou usar `threading.local`. Eliminar todo estado por-requisição em globais de módulo antes de habilitar threads.

---

### 🔵 A-14 — XML parsing sem proteção a *entity expansion* (billion laughs)

**Severidade:** 🔵 Baixo
**Evidência:** `mod_omie.py:5,201` e `promob_grupos.py:8,267,273` usam `xml.etree.ElementTree` (`ET.fromstring`, `ET.parse`) sobre XML enviado por upload. O `ElementTree` do CPython **não resolve entidades externas** (XXE clássico mitigado por padrão), mas **não protege** contra bombas de expansão de entidades internas (billion laughs) em versões mais antigas do expat.

**Vetor de ataque:** Upload de XML com entidades aninhadas (`<!ENTITY lol "lololol...">`) para consumir CPU/memória → DoS (agravado pelo servidor single-thread e falta de limite de tamanho, A-12).

**Impacto:** DoS por expansão de entidades (baixo, dado que XXE está mitigado).

**Recomendação:** Usar `defusedxml` (`defusedxml.ElementTree`) para o parsing de XML de upload, ou validar/limitar tamanho e rejeitar `<!DOCTYPE`/`<!ENTITY`. Manter limite de tamanho (A-12).

---

### ℹ️ A-15 — Observações positivas e itens informativos

- **AuthZ de negócio sólida:** o padrão `_ator_dict` → `escopo_operacional` → `_obj_da_loja`/`_projeto_da_loja` (`main.py:4855-4940`) é aplicado de forma consistente e correta nas rotas de projeto/cliente/orçamento/contrato/medição, incluindo escopo por projetista (`criado_por_id`, `_projeto_visivel_ao_ator`, `main.py:4916-4924`). **IDOR entre lojas não foi encontrado** nessas rotas — `_obj_da_loja` retorna `None` quando o objeto é de outra loja.
- **Gestão de usuários bem protegida:** rotas `/api/admin/usuarios` (`main.py:2947-2993`, `4121-4207`) têm anti-escalonamento (super_admin/admin_rede só por quem tem o poder), anti-lockout (não altera o próprio perfil / não se inativa), e validação de que a loja-alvo está no escopo do ator. Bom trabalho.
- **Segredo Omie NÃO está no histórico do Git:** `git rev-list --all | git grep <secret>` retornou vazio (exit 1) e `omie_config.json` não é rastreado (está no `.gitignore`). O risco é o **runtime** (A-01), não o versionamento.
- **`orizon.db` e `*.bak` na raiz:** vários backups de banco (`omie.db.bak-*`) e `.docx.bak-*` no diretório do app. Estão fora do Git, mas em produção representam superfície de vazamento de dados/hashes (reforça A-03). Recomenda-se movê-los para fora do diretório servido e cifrá-los.
- **Login com mensagem única** ("Usuário ou senha inválidos", `auth.py:28`) — bom, evita enumeração de usuários. Porém `check_senha` não é *constant-time* (vide A-03).
- **Gap menor de AuthZ na edição de usuário:** um admin de loja (diretor/gerente_adm_fin) pode alterar o `nivel` de um usuário da própria loja para qualquer perfil não-admin (`main.py:4155-4181`) — impacto contido ao escopo da loja, mas idealmente restringir a lista de perfis atribuíveis (já existe `mod_tenancy.perfis_atribuiveis`, que não é reaplicada na edição).

---

## Placar por severidade

| Severidade | Qtde | Achados |
|---|---|---|
| 🔴 Crítico | 4 | A-01, A-02, A-03, A-04 |
| 🟠 Alto | 5 | A-05, A-06, A-07, A-08, A-09 |
| 🟡 Médio | 3 | A-10, A-11, A-12 |
| 🔵 Baixo | 3 | A-13, A-14 (+ gap menor em A-15) |
| ℹ️ Info | 1 | A-15 (positivos/observações) |
| **Total** | **15** | |

---

## Top riscos (priorizado)

1. **A-01 — `GET /config` vaza `app_secret` da Omie sem auth.** Rotacionar o segredo **hoje**, autenticar a rota e nunca devolver o secret ao cliente. É o risco mais explorável e de maior impacto.
2. **A-04 — Super_admin padrão `sad2026`/`trocar123`.** Verificar e trocar em produção imediatamente; remover a senha padrão do bootstrap.
3. **A-02 — Endpoints de config/perfis/exportação sem autenticação.** Adicionar guarda de sessão global com allow-list; exigir perfil admin em `/config` e `/perfis`.
4. **A-03 — Senhas em SHA-256 sem salt.** Migrar para bcrypt/scrypt/argon2 com re-hash no login; forçar troca de senhas seed/fracas.
5. **A-05 — Sessão de exportação global compartilhada entre usuários.** Chavear estado por usuário/token para fechar o vazamento cross-loja (e habilitar concorrência com segurança).

**Ações de curto prazo adicionais:** aplicar `basename`+confinamento nos uploads/serving (A-07/A-08), rate limiting no login (A-06), cookie `Secure`+`SameSite`+CSRF (A-10), limite de corpo (A-12) e cabeçalhos de segurança + erros genéricos (A-11).
