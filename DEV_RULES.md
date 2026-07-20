# DEV_RULES.md — Regras de Sessão de Desenvolvimento
## Orizon Manager | Dalmóbile

---

## OBJETIVO
Garantir continuidade total entre sessões de desenvolvimento, sem perda de contexto, independente do tempo entre sessões ou da ferramenta usada (Claude Chat ou Claude Code).

---

## DOCUMENTOS DO PROJETO

| Arquivo | Propósito |
|---|---|
| `CLAUDE.md` | Resumo carregado automaticamente pelo Claude Code (aponta para estes docs) |
| `DEV_RULES.md` | Este arquivo — regras do processo |
| `DEV_LOG.md` | Diário de desenvolvimento — estado atual e histórico |
| `REQUIREMENTS.md` | Requisitos do sistema — referência permanente |
| `docs/superpowers/specs/` | Specs de design por frente |
| MCP `orizon` (grafo Neo4j) | Camada de **consulta** estrutural (cobertura, impacto, rastreabilidade). **Não** substitui o DEV_LOG — ver seção própria abaixo |

---

## AO ABRIR UMA NOVA SESSÃO

### No Claude Chat
Cole no início da conversa:
> "Leia os arquivos DEV_LOG.md e REQUIREMENTS.md do projeto Orizon Manager e me ajude a continuar de onde paramos."

Cole o conteúdo da seção `## RESUMO ATUAL` do `DEV_LOG.md`.

### No Claude Code
Digite no terminal dentro da pasta do projeto:
```
claude
```
Depois diga:
> "Leia DEV_LOG.md e REQUIREMENTS.md e continue de onde paramos."

O Claude Code lê os arquivos diretamente — não precisa colar o conteúdo.

---

## AO ENCERRAR UMA SESSÃO

### Checklist obrigatório antes de fechar

- [ ] Todos os arquivos modificados foram salvos
- [ ] O servidor local foi testado (`python3 main.py`)
- [ ] A suíte passou (`python3 -m pytest -q`) e os testes manuais foram feitos (login, funcionalidade alterada)
- [ ] `git add . && git commit -m "descrição"` foi executado
- [ ] `git push` foi executado
- [ ] **Re-ingestão do grafo MCP** (`ingerir` com `fonte: "all"`, ou `POST http://localhost:8767/ingest/all`) — para o grafo refletir o código mergeado
- [ ] Se houver mudanças no servidor: `git pull` + restart do app

### Pedir ao Claude para atualizar o log
> "Atualize o DEV_LOG.md com o resumo do que fizemos hoje. Mantenha o RESUMO ATUAL no topo e adicione ao HISTÓRICO."

### Verificar que o DEV_LOG contém
- [ ] [ESTADO] — o que está funcionando agora
- [ ] [PENDENTE] — bugs e tarefas abertas com prioridade
- [ ] [DECIDIDO] — decisões tomadas hoje que não devem ser revertidas
- [ ] [ARQUIVOS] — arquivos modificados na sessão

---

## REGRAS GERAIS

### Git
- Fazer commit ao final de cada sessão, **sempre**
- Mensagens de commit em português, descritivas: `"feat: modal de autorização delegada"`, `"fix: limite de desconto no modal de parâmetros"`
- Nunca editar arquivos diretamente no servidor — sempre via git pull
- Branch padrão: `main`

### Servidor de DEV
- IP: `167.88.33.121` | Porta: `8765` | URL: `http://167.88.33.121:8765`
- Acesso: `ssh root@167.88.33.121` | Projeto em `/root/orizon-manager`
- App roda em screen `orizon-manager` (Detached), iniciado com `ORIZON_HOST=0.0.0.0` (bind externo)
  e log em `app.log`. Ver: `screen -r orizon-manager` (sair sem matar: `Ctrl+A` depois `D`).
- **Bind:** `main.py` lê `ORIZON_HOST` (padrão `127.0.0.1` no dev local). Em produção
  é obrigatório `ORIZON_HOST=0.0.0.0`, senão o app fica acessível só por localhost.
- **Firewall:** a porta 8765/TCP precisa estar liberada (`ufw allow 8765/tcp` e,
  se houver, no painel do provedor do VPS).

#### Runbook de deploy (rodar no servidor via ssh)
> ⚠️ **Rodar numa sessão SSH interativa** (`ssh root@...` e depois colar), OU salvar num arquivo no VPS e
> executar (`bash deploy_once.sh`). **NÃO** cole o script inteiro como comando único do `ssh host '<script>'`:
> o argv da shell passa a conter `main.py`, e o `pkill -f main.py` casa com a própria shell do deploy e a
> **auto-mata** (o script para logo no primeiro passo). Rodando via arquivo, o argv é `bash deploy_once.sh`
> (sem `main.py`) e o `pkill` só atinge o app real.
```bash
cd /root/orizon-manager
pkill -f main.py; sleep 1
for s in $(screen -ls | grep -oE '[0-9]+\.orizon-manager'); do screen -S "$s" -X quit; done
screen -wipe
git fetch origin && git reset --hard origin/main
# Dependências (Ubuntu 24.04 / PEP 668 — usar apt, não pip):
apt install -y python3-docx python3-openpyxl python3-requests python3-sqlalchemy python3-psycopg2
ufw allow 8765/tcp 2>/dev/null
# Banco: POSTGRES (SQLite APOSENTADO — o app se recusa a subir sem DATABASE_URL). A DATABASE_URL fica
# em /root/orizon-A.env (fora do git; user orizon / db orizon). Só na 1ª vez cria schema + usuários:
#   . /root/orizon-A.env && python3 seed.py
# Sobe em screen (a env traz ORIZON_HOST=0.0.0.0 + DATABASE_URL do Postgres):
screen -S orizon-manager -dm bash -c 'cd /root/orizon-manager && . /root/orizon-A.env && python3 main.py > app.log 2>&1'
sleep 3; ss -ltnp | grep 8765; tail -8 app.log
curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://127.0.0.1:8765   # esperado: 302
```

#### Instância B — PRÉ-HOMOLOGAÇÃO (`:8766`) no MESMO servidor de DEV
Duas instâncias isoladas no `167.88.33.121` (ver `docs/superpowers/specs/_geral/2026-07-16-plano-de-testes.md`):
a **A** (INTEGRAÇÃO, `:8765`, `/root/orizon-manager`, auto do `main`) e a **B** (PRÉ-HOMOLOGAÇÃO,
`:8766`, **clone separado** `/root/orizon-homolog`, roda uma **tag fixada** — não o `main`).
> **Por que clone separado:** a A faz `git reset --hard origin/main` a cada deploy; se as duas
> compartilhassem o diretório, o deploy da A trocaria o código da B. Portas via **`ORIZON_PORT`**
> (implementado 2026-07-16), banco via **`DATABASE_URL`** — cada instância no seu.
```bash
# Uma vez: clonar a 2ª cópia e entrar na tag de homologação
cd /root
git clone https://github.com/mbnunes1972/orizon-manager.git orizon-homolog
cd orizon-homolog
git fetch --tags && git checkout <TAG_DE_HOMOLOG>     # ex.: git checkout v2026.07.16-homolog
ufw allow 8766/tcp 2>/dev/null
# Banco PRÓPRIO da B — arquivo SQLite separado (DB_PATH segue a DATABASE_URL sqlite, fix de
# 2026-07-16: as migracoes sqlite3 miram o arquivo certo, sem tocar o orizon.db da instancia A).
# FICA FORA da arvore do clone git (nao dentro de /root/orizon-homolog): senao um `git clean -fd`
# ali apagaria o banco da B, e `git status` mostraria o .db+journal/wal como ruido nao rastreado.
# Banco PRÓPRIO da B em POSTGRES (db orizon_homolog, mesmo servidor Postgres da A). DATABASE_URL em
# /root/orizon-B.env (fora do git). Só na 1ª vez cria schema + usuários:  . /root/orizon-B.env && python3 seed.py
# Sobe em screen proprio (a env traz ORIZON_HOST=0.0.0.0 + ORIZON_PORT=8766 + DATABASE_URL orizon_homolog):
screen -S orizon-homolog -dm bash -c 'cd /root/orizon-homolog && . /root/orizon-B.env && python3 main.py > app.log 2>&1'
# Espera por CONDICAO (nao `sleep 3` cego): o 1o boot importa muita coisa e pode passar de 3s —
# um curl cedo demais devolve 000 (falso alarme de "nao subiu"). Faz poll ate a porta responder.
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8766 || true)
  [ "$code" = "302" ] && break
  sleep 1
done
ss -ltnp | grep 8766; tail -8 app.log
echo "HTTP: $code (esperado 302)"   # se ficar em 000 apos 30s, veja o traceback em app.log
```
**Atualizar a B (promover novo build):** no `/root/orizon-homolog`, `git fetch --tags && git checkout
<NOVA_TAG>`, mate o screen `orizon-homolog` e suba de novo (NUNCA `git reset --hard origin/main` aqui —
a B é build tagueado, não o `main`). **Parar a B sem afetar a A:** `screen -S orizon-homolog -X quit`
(o `pkill -f main.py` do runbook da A mataria as DUAS — na B use o nome do screen).
> **Paridade com produção:** ✅ **feito em 2026-07-19** — Postgres 16 instalado no `167.88.33.121`
> (`apt install postgresql postgresql-contrib python3-psycopg2`), user `orizon`, dbs `orizon` (A) e
> `orizon_homolog` (B), Postgres escutando só em localhost. As duas instâncias rodam em Postgres via
> `/root/orizon-A.env` e `/root/orizon-B.env` (senha fora do git). SQLite **aposentado** (os `.db`
> antigos ficaram como backup). Para migrar DADOS de um SQLite legado, seria um passo à parte (dump/load).

#### Runbook de migração de nome — UMA vez (`omie_v3` → `orizon-manager`)
> Rodar **uma única vez** ao migrar o nome. O servidor ainda tem os nomes antigos; depois disto,
> use o runbook de deploy acima normalmente.
```bash
# 1) GitHub: renomear o repositório em Settings → Repository name → "orizon-manager"
#    (o GitHub mantém redirecionamento do nome antigo, mas atualize o remote abaixo)
# 2) No VPS:
ssh root@167.88.33.121
pkill -f main.py; sleep 1
for s in $(screen -ls | grep -oE '[0-9]+\.omie_v3'); do screen -S "$s" -X quit; done
screen -wipe
mv /root/omie_v3 /root/orizon-manager          # renomeia o diretório (preserva tudo)
cd /root/orizon-manager
[ -f omie.db ] && mv omie.db orizon.db          # preserva o banco com o novo nome
git remote set-url origin https://github.com/mbnunes1972/orizon-manager.git
git fetch origin && git reset --hard origin/main
screen -S orizon-manager -dm bash -c 'cd /root/orizon-manager && ORIZON_HOST=0.0.0.0 python3 main.py > app.log 2>&1'
sleep 3; ss -ltnp | grep 8765; tail -8 app.log
```

### Servidor de produção (orizonsolution.com.br) — em provisionamento (2026-07-15)
- IP: `179.197.77.9` (Hostinger) | VPS **dedicada** (nada mais rodando nela) | Ubuntu 24.04
- Domínio `orizonsolution.com.br` — **DNS ainda não apontado** (passo 0 abaixo).
- Diferente do servidor de DEV **de propósito** — nasce já no padrão profissional, não é o mesmo setup
  replicado: **PostgreSQL** (não SQLite, ver `docs/superpowers/specs/_geral/2026-07-15-migracao-postgresql.md`),
  **systemd** (não `screen` — sobrevive a reboot e reinicia sozinho se cair), **nginx + HTTPS** na frente
  (a porta 8765 do Python NÃO fica exposta direto à internet), `ufw` + `fail2ban`, backup automático.
- Acesso: `ssh root@179.197.77.9`, **só por chave** (login por senha será desabilitado no passo 1 — a
  chave já foi confirmada funcionando antes de desabilitar).
- **Pré-requisito ainda pendente:** o código com suporte a `DATABASE_URL` (conexão Postgres) está só
  local, não commitado (branch `feat/migracao-postgresql-v2`, worktree `wt-postgres-migration`) — precisa
  estar commitado/mergeado antes do Passo 2 (deploy do app).

#### Passo 0 — DNS (fora do servidor, no painel do registrador do domínio)
Criar registros A: `orizonsolution.com.br` → `179.197.77.9` e `www.orizonsolution.com.br` →
`179.197.77.9`. Propagação pode levar de minutos a algumas horas — dá pra rodar os Passos 1 e 2
enquanto espera; o Passo 3 (certificado HTTPS) só funciona depois do DNS propagar.

#### Passo 1 — Provisionamento base (rodar uma vez, via SSH)
```bash
apt update && apt upgrade -y && dpkg --configure -a   # garante que não sobrou nada pendente
apt install -y postgresql postgresql-contrib nginx certbot python3-certbot-nginx ufw fail2ban \
  python3-docx python3-openpyxl python3-requests python3-sqlalchemy python3-psycopg2 \
  weasyprint python3-markdown git

# Postgres: usuário + banco dedicados (troque a senha)
sudo -u postgres psql -c "CREATE USER orizon WITH PASSWORD 'TROQUE_ESTA_SENHA';"
sudo -u postgres psql -c "CREATE DATABASE orizon OWNER orizon;"

# Firewall: só SSH + HTTP/HTTPS (a 8765 fica só em localhost, atrás do nginx)
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# Hardening SSH — só desabilite senha DEPOIS de confirmar que a chave funciona numa
# segunda janela SSH aberta em paralelo (mesma lição do incidente de hoje: nunca feche
# a única sessão viva antes de confirmar a próxima)
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart ssh
```

#### Passo 2 — Deploy do app (depois que o código do DATABASE_URL estiver commitado)
```bash
cd /root
git clone https://github.com/mbnunes1972/orizon-manager.git
cd orizon-manager
git checkout feat/migracao-postgresql-v2   # trocar por 'main' assim que mergeado
pip install alembic --break-system-packages

cat > /etc/systemd/system/orizon.service <<'EOF'
[Unit]
Description=Orizon Manager
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory=/root/orizon-manager
Environment=ORIZON_HOST=127.0.0.1
Environment=DATABASE_URL=postgresql+psycopg2://orizon:TROQUE_ESTA_SENHA@localhost/orizon
ExecStart=/usr/bin/python3 main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Primeiro start cria o schema limpo no Postgres (create_all, sem migração de dados legados)
# e semeia os usuários iniciais — TROCAR AS SENHAS DE EXEMPLO ANTES DE USO REAL.
systemctl daemon-reload
systemctl enable --now orizon
sleep 3; systemctl status orizon --no-pager; curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://127.0.0.1:8765
```

#### Passo 3 — nginx + HTTPS (só depois do DNS propagado — Passo 0)
```bash
cat > /etc/nginx/sites-available/orizon <<'EOF'
server {
    listen 80;
    server_name orizonsolution.com.br www.orizonsolution.com.br;
    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ln -sf /etc/nginx/sites-available/orizon /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d orizonsolution.com.br -d www.orizonsolution.com.br   # HTTPS + redirect automático
```

#### Passo 4 — Backup automático (pg_dump diário)
```bash
mkdir -p /root/backups
cat > /root/backup_orizon.sh <<'EOF'
#!/bin/bash
DATA=$(date +%Y%m%d_%H%M%S)
sudo -u postgres pg_dump orizon | gzip > /root/backups/orizon_$DATA.sql.gz
find /root/backups -name "orizon_*.sql.gz" -mtime +14 -delete
EOF
chmod +x /root/backup_orizon.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /root/backup_orizon.sh") | crontab -
```
⚠️ Isso é backup **local** (mesmo disco da VPS) — protege contra erro de aplicação/banco, mas não
contra falha da própria VPS. Ainda falta sincronizar pra fora (ex.: S3/Backblaze) — pendente, não
bloqueia o go-live.

### Banco de dados
- **Servidor de DEV:** SQLite: `orizon.db` na raiz — **NÃO versionado** (está no `.gitignore`); cada
  ambiente tem o seu. Não comitar `orizon.db`.
- **Servidor de produção:** PostgreSQL (ver seção acima) — nasce limpo, sem dados do DEV.
- Para recriar usuários (ou um banco novo): `python3 seed.py` (cria schema via `init_db` + usuários)
- Migrações: SQLAlchemy + `_migrar_colunas`/`schema_migrations` (SQLite, legado) — Postgres usa Alembic
  a partir da migração (ver ADR).

### Dependências
- Listadas em `requirements.txt`. Local: `python3 -m pip install -r requirements.txt` (o contrato usa
  `weasyprint`; a proposta ainda usa docx/LibreOffice).
- Servidor (Ubuntu 24.04, PEP 668): instalar via `apt` (ver runbook) — `pip install`
  system-wide é bloqueado (`externally-managed-environment`).

### Testes após cada mudança
1. **Automatizados (backend):** `python3 -m pytest -q` — deve ficar tudo verde ANTES de commitar/mergear.
2. **Manuais (frontend, `static/index.html` — sem teste JS):** login com cada nível (Consultor, Gerente,
   Diretor); limite de desconto respeitado; autorização delegada funcional; logout redireciona para
   `/login`. Para sintaxe do JS: extrair o `<script>` e rodar `node --check`.

---

## MCP `orizon` — grafo de conhecimento (camada de consulta)

O projeto `../mcp-orizon` sobe um **grafo Neo4j** (via docker-compose) que ingere código, requisitos,
banco e decisões do Orizon Manager. O Claude Code fala com ele via servidor MCP (config em `.mcp.json`,
mounts para `E:/2026/desenvolvimento/...`). Ferramentas: `cobertura`, `rastrear_requisito`,
`impacto_de`, `decisoes_de`, `buscar`, `entidades_do_arquivo`, `etapa`, `ingerir`, `criar_relacao`.

**Papel e limites — leia antes de confiar nele:**
- É uma **camada de consulta/análise** ("o que implementa o requisito X? o que quebra se eu mexer no
  arquivo Y? quais requisitos não têm código?"). **Não** é controle de versão nem diário.
- É **derivado do código e local** (container Neo4j, fora do git). **Fica obsoleto** se o código muda e
  não re-ingere; **some** com `docker compose down -v` — aí é só re-ingerir.
- **Não substitui o DEV_LOG.** O DEV_LOG continua sendo a fonte narrativa versionada (estado, backlog,
  decisões + porquê, histórico) e a continuidade entre sessões. O grafo complementa.

**Controle de versão:** segue **100% no git** — o MCP não muda nada nisso.

**Ritual:** após mergear mudança relevante, **re-ingerir** (`ingerir` `fonte: "all"` ou
`POST http://localhost:8767/ingest/all`). Antes de fechar frente, vale rodar
`cobertura`/`rastrear_requisito` para pegar requisito sem implementação.

## TAGS DO DEV_LOG

| Tag | Uso |
|---|---|
| `[ESTADO]` | O que está funcionando agora |
| `[PENDENTE]` | Bug ou tarefa aberta — incluir prioridade (ALTA/MÉDIA/BAIXA) |
| `[DECIDIDO]` | Decisão de arquitetura — não reverter sem discussão |
| `[CONTEXTO]` | Variáveis, funções ou arquivos chave que o Claude precisa saber |
| `[BLOQUEIO]` | Impedimento que precisa ser resolvido antes de avançar |
