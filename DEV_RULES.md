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

### Servidor de produção/DEV
- IP: `167.88.33.121` | Porta: `8765` | URL: `http://167.88.33.121:8765`
- Acesso: `ssh root@167.88.33.121` | Projeto em `/root/orizon-manager`
- App roda em screen `orizon-manager` (Detached), iniciado com `ORIZON_HOST=0.0.0.0` (bind externo)
  e log em `app.log`. Ver: `screen -r orizon-manager` (sair sem matar: `Ctrl+A` depois `D`).
- **Bind:** `main.py` lê `ORIZON_HOST` (padrão `127.0.0.1` no dev local). Em produção
  é obrigatório `ORIZON_HOST=0.0.0.0`, senão o app fica acessível só por localhost.
- **Firewall:** a porta 8765/TCP precisa estar liberada (`ufw allow 8765/tcp` e,
  se houver, no painel do provedor do VPS).

#### Runbook de deploy (rodar no servidor via ssh)
```bash
cd /root/orizon-manager
pkill -f main.py; sleep 1
for s in $(screen -ls | grep -oE '[0-9]+\.orizon-manager'); do screen -S "$s" -X quit; done
screen -wipe
git fetch origin && git reset --hard origin/main
# Dependências (Ubuntu 24.04 / PEP 668 — usar apt, não pip):
apt install -y python3-docx python3-openpyxl python3-requests python3-sqlalchemy
ufw allow 8765/tcp 2>/dev/null
# Banco descartável no servidor (recria limpo + usuários). OMITIR se for preservar dados.
rm -f orizon.db && python3 seed.py
# Sobe em screen, bind externo, com log:
screen -S orizon-manager -dm bash -c 'cd /root/orizon-manager && ORIZON_HOST=0.0.0.0 python3 main.py > app.log 2>&1'
sleep 3; ss -ltnp | grep 8765; tail -8 app.log
curl -s -o /dev/null -w "HTTP: %{http_code}\n" http://127.0.0.1:8765   # esperado: 302
```

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

### Banco de dados
- SQLite: `orizon.db` na raiz — **NÃO versionado** (está no `.gitignore`); cada ambiente
  tem o seu. Não comitar `orizon.db`.
- Para recriar usuários (ou um banco novo): `python3 seed.py` (cria schema via `init_db` + usuários)
- Migrações: SQLAlchemy + `_migrar_colunas`/`schema_migrations` (já configurado)

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

## TAGS DO DEV_LOG

| Tag | Uso |
|---|---|
| `[ESTADO]` | O que está funcionando agora |
| `[PENDENTE]` | Bug ou tarefa aberta — incluir prioridade (ALTA/MÉDIA/BAIXA) |
| `[DECIDIDO]` | Decisão de arquitetura — não reverter sem discussão |
| `[CONTEXTO]` | Variáveis, funções ou arquivos chave que o Claude precisa saber |
| `[BLOQUEIO]` | Impedimento que precisa ser resolvido antes de avançar |
