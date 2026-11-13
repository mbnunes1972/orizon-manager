# Orizon One (orizon-manager)

ERP para redes de lojas de móveis planejados: orçamento importado do Promob, negociação,
contrato assinado, ciclo do projeto, fiscal (NF-e/NFS-e) e fechamento contábil.
Python sem framework web (`http.server`) + SQLAlchemy + PostgreSQL; frontend em
`static/index.html`.

## Rodar localmente

1. PostgreSQL 16 com os bancos `orizon` e `orizon_test` (dono: usuário `orizon`).
2. `cp .env.example .env` e preencha a senha.
3. `python3 -m venv .venv && source .venv/bin/activate`
4. `pip install -r requirements.txt pytest pytest-timeout`
5. `set -a; . ./.env; set +a; alembic upgrade head` — **antes** do primeiro boot. Se o app subir
   antes, o `init_db()` cria as tabelas sem registrar a versão no Alembic.
6. `python3 seed.py` (usuários de desenvolvimento; o super_admin só nasce com
   `ORIZON_ADMIN_LOGIN` e `ORIZON_ADMIN_SENHA` definidos)
7. `./run.sh` → http://127.0.0.1:8765

## Testes

```bash
BROWSER=true python3 -m pytest -q
```

A suíte roda sempre contra Postgres (banco `orizon_test`, derivado do `.env`). Os testes de
migração usam também o banco `orizon_baseline_teste`, e os E2E de navegador usam `orizon_e2e` e o
Playwright (`pip install playwright pytest-playwright && playwright install chromium`).
`BROWSER=true` impede que cada servidor de teste abra uma janela no navegador. Detalhes no
`CLAUDE.md`.

## Por onde ler

- `CLAUDE.md` — regras e contexto do projeto (comece por aqui)
- `DEV_RULES.md` — fluxo de git, deploy e runbooks
- `REQUIREMENTS.md` — requisitos de negócio
- `docs/README.md` — mapa da documentação
