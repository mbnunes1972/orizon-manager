# Stack Técnica — Omie_V3

## Visão geral

| Camada | Tecnologia | Observação |
|---|---|---|
| Backend | Python 3.12, `http.server` nativo | Sem framework — servidor HTTP puro |
| Banco de dados | SQLite + SQLAlchemy 2.0 | Migração futura para MySQL via troca de string de conexão |
| Frontend | HTML/CSS/JS puro (SPA) | Sem framework — single page application |
| Autenticação | Cookie de sessão (token hex 32) | Sem JWT — sessão server-side |
| Infraestrutura | Hostinger VPS, Ubuntu 24.04 | IP: 167.88.33.121, porta 8765 |
| Repositório | GitHub | github.com/mbnunes1972/omie_v3 |

---

## Estrutura de arquivos

```
Omie_V3/
├── main.py                 # Ponto de entrada — servidor HTTP e todas as rotas
├── database.py             # Modelos SQLAlchemy e conexão com banco
├── auth.py                 # Lógica de autenticação e autorização
├── auth_routes.py          # Rotas HTTP de autenticação (integradas ao main.py)
├── mod_omie.py             # Integração com API do Omie ERP
├── mod_margens.py          # Cálculo de margens e descontos
├── mod_fin/                # Módulos financeiros
│   ├── __init__.py
│   ├── base.py
│   ├── aymore.py
│   ├── cartao.py
│   ├── total_flex.py
│   └── venda_programada.py
├── promob_grupos.py        # Classificação de grupos Promob
├── storage.py              # Funções de persistência em arquivo JSON
├── seed.py                 # Criação de usuários iniciais
├── omie.db                 # Banco SQLite (não versionar dados de produção)
├── omie_config.json        # Credenciais Omie (não commitar)
├── perfis_config.json      # Configuração de perfis de acesso
├── config/
│   └── total_flex.json     # Configuração do módulo Total Flex
├── tabelas_financeiras/    # Tabelas de taxas e condições financeiras
│   ├── aymore.json
│   ├── a_vista.json
│   ├── cartao_credito.json
│   ├── total_flex.json
│   └── venda_programada.json
├── static/
│   ├── index.html          # Frontend SPA completo
│   └── login.html          # Tela de login
├── PROJETOS/               # Projetos salvos em JSON (um diretório por projeto)
│   └── <nome_safe>/
│       ├── projeto.json
│       └── xmls/           # XMLs do Promob
└── docs/                   # Esta documentação
```

---

## Padrões de código

### Backend (Python)

**Rotas no main.py:**
```python
# Padrão GET
elif path == "/rota":
    self.send_json({"ok": True, "dados": [...]})

# Padrão POST
elif path == "/rota":
    dados = json.loads(body)
    # processamento
    self.send_json({"ok": True})

# Padrão de erro
self.send_json({"ok": False, "erro": "Mensagem de erro"})
```

**Banco de dados (SQLAlchemy):**
```python
db = get_session()
try:
    # operações
    db.commit()
finally:
    db.close()
```

**Nunca usar** `db.query(Modelo).get(id)` — API deprecated. Usar `db.get(Modelo, id)`.

### Frontend (JavaScript)

**Chamadas de API:**
```javascript
const r = await fetch('/rota', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(dados)
});
const d = await r.json();
if(!d.ok) { showToast(d.erro, true); return; }
```

**Navegação entre páginas:**
```javascript
goPage(0)  // Projetos
goPage(2)  // Negociação
goPage(9)  // Configurações
```

---

## Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `OMIE_HOST` | `127.0.0.1` | Host do servidor HTTP (usar `0.0.0.0` no servidor DEV) |

No servidor, após `git pull`:
```bash
sed -i 's/127.0.0.1/0.0.0.0/g' main.py
python3 main.py
```

---

## Banco de dados

**String de conexão atual (SQLite):**
```python
ENGINE = create_engine("sqlite:///omie.db", echo=False)
```

**Para migrar para MySQL** (quando necessário):
```python
ENGINE = create_engine("mysql+mysqlconnector://user:pass@host/omie_v3", echo=False)
```
O resto do código não muda — SQLAlchemy abstrai o banco.

---

## Gitignore recomendado

```
omie_config.json
omie.db
__pycache__/
*.pyc
.env
PROJETOS/
```
