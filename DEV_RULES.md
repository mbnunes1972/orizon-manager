# DEV_RULES.md — Regras de Sessão de Desenvolvimento
## Omie_V3 | Dalmóbile

---

## OBJETIVO
Garantir continuidade total entre sessões de desenvolvimento, sem perda de contexto, independente do tempo entre sessões ou da ferramenta usada (Claude Chat ou Claude Code).

---

## DOCUMENTOS DO PROJETO

| Arquivo | Propósito |
|---|---|
| `DEV_RULES.md` | Este arquivo — regras do processo |
| `DEV_LOG.md` | Diário de desenvolvimento — estado atual e histórico |
| `REQUIREMENTS.md` | Requisitos do sistema — referência permanente |

---

## AO ABRIR UMA NOVA SESSÃO

### No Claude Chat
Cole no início da conversa:
> "Leia os arquivos DEV_LOG.md e REQUIREMENTS.md do projeto Omie_V3 e me ajude a continuar de onde paramos."

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
- [ ] O servidor local foi testado (`python main.py`)
- [ ] Os testes básicos foram feitos (login, funcionalidade alterada)
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

### Servidor de desenvolvimento
- IP: `167.88.33.121` | Porta: `8765`
- Acesso: `ssh root@167.88.33.121`
- App roda em screen: `screen -r omie`
- Para atualizar: `cd /root/omie_v3 && git pull && pkill -f "python3 main.py" && python3 main.py`

### Banco de dados
- SQLite local: `omie.db` na raiz do projeto
- Para recriar usuários: `python seed.py`
- Migrações futuras: usar SQLAlchemy (já configurado)

### Testes básicos após cada mudança
1. Login com cada nível (Consultor, Gerente, Diretor)
2. Limite de desconto respeitado
3. Autorização delegada funcional
4. Logout redireciona para `/login`

---

## TAGS DO DEV_LOG

| Tag | Uso |
|---|---|
| `[ESTADO]` | O que está funcionando agora |
| `[PENDENTE]` | Bug ou tarefa aberta — incluir prioridade (ALTA/MÉDIA/BAIXA) |
| `[DECIDIDO]` | Decisão de arquitetura — não reverter sem discussão |
| `[CONTEXTO]` | Variáveis, funções ou arquivos chave que o Claude precisa saber |
| `[BLOQUEIO]` | Impedimento que precisa ser resolvido antes de avançar |
