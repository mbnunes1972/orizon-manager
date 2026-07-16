# Auditoria 07 — Cadeia de Dependências & Suíte de Testes

**Sistema:** Orizon Manager / Dalmóbile — backend Python puro (`http.server`), SQLAlchemy + SQLite (`orizon.db`).
**Escopo:** dependências (`requirements.txt`, imports, supply-chain, CVEs por conhecimento) e suíte `pytest`.
**Método:** análise estática (Read/Grep/Glob/PowerShell). Suíte **não** foi executada. READ-ONLY.
**Exclusões:** `.claude/worktrees/`, `.git`, `__pycache__`.
**Data:** 2026-07-03.

> Nota sobre CVEs: sinalizações abaixo são **análise por conhecimento** do auditor (até jan/2026), **não** um scan ao vivo. Recomenda-se rodar `pip-audit`/`osv-scanner` para confirmar em versões reais.

---

## Parte A — Dependências

### A1. `requirements.txt` sem pins de versão (unpinned)
- **Severidade:** 🔴
- **Evidência:** `requirements.txt:5-10` — `python-docx`, `openpyxl`, `requests`, `SQLAlchemy`, `weasyprint`, `markdown` listados **sem** `==`, `~=` ou qualquer restrição.
- **Impacto:** builds não são reprodutíveis. Cada `pip install` pode trazer uma versão diferente; uma release nova (ou comprometida) entra silenciosamente. Quebra o princípio de supply-chain "known-good". Um `weasyprint` ou `SQLAlchemy` major novo pode quebrar produção sem nenhuma alteração de código.
- **Recomendação:** fixar versões exatas e adotar **lockfile com hashes**. Fluxo recomendado: `requirements.in` (dependências diretas) → `pip-compile --generate-hashes` (pip-tools) → `requirements.txt` com hashes. Instalar com `pip install --require-hashes`. Alternativa: `uv pip compile`.

### A2. Divergência silenciosa dev (pip) × produção (apt)
- **Severidade:** 🔴
- **Evidência:** `requirements.txt:2-4` — dev usa `pip install -r requirements.txt`; produção usa `apt install python3-docx python3-openpyxl python3-requests python3-sqlalchemy weasyprint python3-markdown` (Ubuntu 24.04 / PEP 668). CLAUDE.md confirma "WeasyPrint 69 no user-site do python3.14" — ou seja, o runtime dev já é heterogêneo (apt + user-site + python3.14).
- **Impacto:** as versões instaladas por `apt` (congeladas no ciclo do Ubuntu) e por `pip` divergem por design. "Verde local" pode não refletir produção. Caso concreto e grave: **A6** (SQLAlchemy 2.x).
- **Recomendação:** padronizar o runtime. Idealmente **venv dedicado em produção** (`python3 -m venv`) instalando o mesmo lockfile do dev, contornando o PEP 668 sem `--break-system-packages`. Se manter apt, documentar a matriz exata de versões apt do Ubuntu 24.04 e testar contra ela num job de CI.

### A3. Ausência de `pyproject.toml` / `setup.py` / gestão de venv
- **Severidade:** 🟠
- **Evidência:** varredura da raiz — **inexistentes**: `pyproject.toml`, `setup.py`, `setup.cfg`, `tox.ini`, `Pipfile`, `*.lock`. Nenhum `pytest.ini` tampouco. Único artefato de dependência é o `requirements.txt`.
- **Impacto:** não há metadados de projeto, nem centralização de config de ferramentas (pytest, ruff, pip-audit), nem declaração de versão de Python suportada. Onboarding e reprodutibilidade dependem de conhecimento tácito (CLAUDE.md).
- **Recomendação:** criar `pyproject.toml` mínimo com `[project]` (nome, `requires-python = ">=3.14"`), `[tool.pytest.ini_options]` (`testpaths=["tests"]`) e, quando adotado, `[tool.pip-audit]`. Mantém tudo versionado num só lugar.

### A4. Dependências transitivas críticas não declaradas nem pinadas (lxml, pydyf, cffi, Pillow)
- **Severidade:** 🟠
- **Evidência:** `mod_contrato.py` importa `weasyprint` (geração de PDF). WeasyPrint 69 arrasta `pydyf`, `tinycss2`, `cssselect2`, `Pyphen`, `fontTools`, `Pillow` e (dependendo da versão) `html5lib`/`cffi`. Grep por `lxml|PIL|Pillow|cffi|pydyf|tinycss|fontTools` no backend: **nenhum import direto** (o único match `PIL` é a string `'PIL'` em `promob_grupos.py:96`, não o pacote).
- **Impacto:** a maior superfície de CVE do projeto (parsing de fontes/imagens/CSS em C — historicamente `Pillow` e `lxml`) está **fora** do `requirements.txt` e portanto invisível ao controle de versão. Sem lockfile, sobem sem revisão.
- **Recomendação:** o lockfile de A1 (com `--generate-hashes`) captura **toda** a árvore transitiva, resolvendo isto automaticamente. Enquanto não houver, registrar a árvore com `pip freeze` e monitorar essas libs.

### A5. `requests` — histórico de CVEs; validar versão instalada
- **Severidade:** 🟡
- **Evidência:** `requirements.txt:7` (`requests` sem pin); uso em `mod_omie.py:36` (`requests.post(url, json=payload, timeout=timeout)`). **Positivo:** todas as chamadas usam `timeout=` (10/30/60s) e **não** há `verify=False` no backend.
- **Impacto (por conhecimento):** `requests < 2.32.0` teve CVE-2024-35195 (sessão ignorando `verify=False` após 1ª req) e a cadeia `urllib3 < 2.2.2`/`< 1.26.19` teve CVEs de redirect/proxy (ex. CVE-2024-37891). Sem pin, não há garantia de estar acima do piso seguro.
- **Recomendação:** pinar `requests>=2.32.3` e `urllib3` compatível no lockfile; confirmar via `pip-audit`. O uso já é defensivo (timeouts, sem `verify=False`) — o risco é só de versão.

### A6. SQLAlchemy 2.x exigido, mas declarado sem pin (risco de quebra em produção)
- **Severidade:** 🔴
- **Evidência:** `database.py:7` — `from sqlalchemy.orm import DeclarativeBase` e `database.py:25` `class Base(DeclarativeBase)`. `DeclarativeBase` **só existe em SQLAlchemy 2.0+**. `requirements.txt:8` declara `SQLAlchemy` sem versão.
- **Impacto:** se o `apt` do Ubuntu 24.04 (ou qualquer ambiente) resolver `python3-sqlalchemy` para a série **1.4**, o `import database` **falha na hora** (`ImportError: cannot import name 'DeclarativeBase'`) — o app não sobe. É exatamente o cenário de divergência A2 materializado num crash total.
- **Recomendação:** pinar `SQLAlchemy>=2.0,<2.1` no requirements/lockfile e validar que a versão apt de produção satisfaz isso (ou migrar produção para venv). Adicionar um smoke-test de import no CI.

### A7. `orizon.db`, `.bak` e segredos — cobertura parcial no `.gitignore`
- **Severidade:** 🟠
- **Evidência:** `.gitignore` **cobre**: `orizon.db` (l.12), `.env` (l.9), `omie_config.json` (l.4), `*.xlsx` (l.8), `/PROJETOS/`, `/CONTRATOS/`, `__pycache__/`. **NÃO cobre:** o padrão `*.bak*` — o working tree tem `omie.db.bak-2026-06-24-pre-drop-margens`, `omie.db.bak-prebackfill`, `modelo_contrato_mapeado.docx.bak-*` (vistos no `git status` inicial). `omie_grupos_cache.json` está ignorado (l.5), mas **não** há regra para `~$*.docx` nem `*.tmp` (citados no CLAUDE.md como ruído).
- **Impacto:** backups de banco (`omie.db.bak*`) contêm **dados de produção / hashes de senha** e podem ser commitados por acidente (basta um `git add .`). Vazamento de PII (clientes, CPFs) e credenciais.
- **Recomendação:** adicionar ao `.gitignore`: `*.bak`, `*.bak-*`, `~$*.docx`, `*.tmp`. Confirmar que nenhum `.bak`/`orizon.db` já está no histórico (`git log --all -- '*.bak*'`); se estiver, remover via `git filter-repo` e rotacionar segredos.

### A8. Hashing de senha sem salt e sem KDF (dependência de segurança ausente)
- **Severidade:** 🟠
- **Evidência:** `database.py:13-15` — `_hash_senha` faz `hashlib.sha256(senha.encode()).hexdigest()`. Sem salt, sem iterações, sem KDF. `set_senha` (`database.py:49`) e o seed (`database.py:632`) usam a mesma função. `requirements.txt` **não** declara `bcrypt`/`argon2-cffi`/`passlib`.
- **Impacto:** SHA-256 puro é rápido demais e sem salt → vulnerável a rainbow tables e brute-force em massa se o `orizon.db` vazar (ver A7). Não é uma vuln "de dependência" clássica, mas é uma **dependência de segurança que deveria existir e não está declarada**.
- **Recomendação:** migrar para `argon2-cffi` ou `bcrypt` (pinado no lockfile), com salt por-usuário e re-hash na próxima autenticação bem-sucedida. Fora do escopo estrito desta auditoria, mas amplifica o impacto de A7.

### A9. Dependências declaradas × usadas — reconciliação
- **Severidade:** ℹ️ (informativo — sem sobras nem faltas de diretas)
- **Evidência:** cruzamento de todos os imports de terceiros do backend com o `requirements.txt`:
  - `python-docx` (import `docx`) → `mod_contrato.py`, `mod_proposta.py`, `scripts/*` ✅ usada
  - `openpyxl` → `mod_omie.py`, `_ler_aymore.py` ✅ usada
  - `requests` → `mod_omie.py` ✅ usada
  - `SQLAlchemy` → `database.py`, `main.py`, testes ✅ usada
  - `weasyprint` → `mod_contrato.py` ✅ usada
  - `markdown` → `mod_contrato.py` ✅ usada
  - **Nenhuma dependência direta declarada e não usada; nenhuma dependência direta usada e não declarada.** (`pytest` corretamente comentado como dev-only.)
- **Impacto:** o conjunto de **diretas** está limpo. O risco real está nas **transitivas** (A4) e nos **pins** (A1).
- **Recomendação:** manter a higiene; o lockfile de A1 formaliza a árvore completa.

### A10. Sem `pip-audit` / Dependabot / política de atualização
- **Severidade:** 🟠
- **Evidência:** ausência de `.github/` (confirmada), ausência de qualquer config de scanner. Nada automatiza a detecção de CVE nas deps.
- **Impacto:** CVEs novos em weasyprint/Pillow/lxml/requests/SQLAlchemy passam despercebidos indefinidamente.
- **Recomendação:** adotar `pip-audit` como passo de CI (falha o build em severidade alta) e/ou habilitar **Dependabot** (`.github/dependabot.yml`) para PRs de bump. Requer lockfile (A1) para render bem.

---

## Parte B — Suíte de Testes

### Inventário
- **57 arquivos de teste** em `tests/` (`test_*.py`), 1 `conftest.py`, 1 `README.md`, `tests/golden/` (baselines `negociacao_baseline.json`, `cutover_baseline.json`).
- Harness hermético em `tests/conftest.py`: fixtures `app_db` (rebind da engine para SQLite temp + restauração no teardown), `seed` (2 lojas/rede, usuários por nível), `projetos_dir` (redireciona `PROJETOS_DIR` p/ tmp), `servidor` (sobe `main.Handler` em thread, porta efêmera), `HttpClient` com cookie jar. **Bom padrão.**

### B1. `main.py` (roteamento, 4758 LOC) sem teste unitário direto
- **Severidade:** 🔴
- **Evidência:** `main.py` tem **4758 linhas** (o maior módulo por larga margem) e concentra o roteamento HTTP, parsing de request e a maior parte da lógica de orquestração. Nenhum teste importa/testa handlers de `main` isoladamente; a cobertura vem **só** dos E2E via fixture `servidor` (ex.: `test_*_e2e.py`, `test_isolamento_f4_e2e.py`).
- **Impacto:** um arquivo dessa dimensão com cobertura apenas end-to-end deixa a maioria dos ramos (validação de payload, códigos de erro, branches condicionais de rota) **sem exercício**. Regressões em rotas pouco percorridas passam. E2E é lento e não substitui teste de unidade de borda.
- **Recomendação:** (a) extrair lógica de `main.py` para módulos testáveis (o `mod_*` já é o padrão — continuar puxando handlers para lá); (b) medir cobertura real com `pytest --cov=. --cov-report=term-missing` e mirar as rotas de `main.py`; (c) adicionar testes de contrato por rota (status/erro) via o `HttpClient` já existente.

### B2. `mod_omie.py` (737 LOC, integração Omie + parsing xlsx) praticamente sem teste
- **Severidade:** 🔴
- **Evidência:** Grep por `mod_omie` em `tests/*.py` → **1 único arquivo** (`test_projeto_parceiro.py`), e mesmo assim de forma tangencial. `mod_omie.py` faz `requests.post` para a API Omie (`mod_omie.py:36`) e parsing de planilhas via `openpyxl` (`_ler_aymore.py`/`mod_omie.py`) — lógica de parsing complexa e propensa a erro.
- **Impacto:** o segundo maior módulo, que toca I/O externo e parsing financeiro/estrutural, está essencialmente sem rede de segurança. Mudança na resposta da API Omie ou no layout da planilha quebra silenciosamente.
- **Recomendação:** testar as funções **puras** de parsing/normalização com fixtures de xlsx e de respostas JSON mockadas (`requests` monkeypatch); não é necessário bater na API real. Priorizar as rotinas que alimentam o motor financeiro.

### B3. Ausência total de CI
- **Severidade:** 🔴
- **Evidência:** `.github/` **inexistente**; sem `tox.ini`, `Makefile`, nem qualquer workflow. `tests/README.md:16-17` estabelece a regra "nenhum commit sem testes passando" — mas ela é **manual**, sem enforcement.
- **Impacto:** "verde local" não garante nada. Sem CI, nada impede um merge com suíte vermelha, nem valida a matriz de versões de A2/A6, nem roda `pip-audit`. A regra do README depende inteiramente da disciplina humana.
- **Recomendação:** criar `.github/workflows/ci.yml` que, a cada push/PR: instala do **lockfile** (A1), roda `python3 -m pytest -q --cov`, e roda `pip-audit`. Idealmente com matriz de Python/versões que espelhe produção (A2). Considerar rodar num job Ubuntu 24.04 com deps **apt** para pegar o cenário A6.

### B4. `README` de testes recomenda `git add .` (contradiz CLAUDE.md e amplifica A7)
- **Severidade:** 🟡
- **Evidência:** `tests/README.md:24` — fluxo sugerido inclui `git add .`. CLAUDE.md diz explicitamente "**Sempre `git add` só os arquivos da mudança (nunca `git add .`)**".
- **Impacto:** seguir o README pode commitar `omie.db.bak*`, `perfis_config.json`, `~$*.docx` etc. (ruído + PII), especialmente enquanto A7 não fecha os gaps do `.gitignore`.
- **Recomendação:** corrigir o README para `git add <arquivos-da-mudança>` e alinhá-lo ao CLAUDE.md. Também atualiza o fluxo `develop` (o projeto commita direto na `main` hoje).

### B5. Testes que apenas verificam "importa / não explode" (fraco valor de asserção)
- **Severidade:** 🟡
- **Evidência:** `tests/test_contrato_pdf.py:8-9` (`test_markdown_disponivel` só faz `import markdown`); o teste de PDF real (`test_gerar_pdf_contrato_gera_pdf`, l.118) é **`skipif` quando weasyprint ausente** — em ambiente sem weasyprint ele some silenciosamente, e a única checagem que resta é "gera bytes `%PDF-` > 1000" (l.135-137), sem validar **conteúdo** do PDF.
- **Impacto:** o caminho crítico de produção (contrato → PDF via WeasyPrint) pode ficar **sem cobertura efetiva** num runner que não tenha weasyprint, e mesmo com ele, valida só a existência do arquivo — não que os dados/marcadores certos entraram no PDF. **Ressalva:** a maior parte de `test_contrato_pdf.py` é forte (testa `_montar_html_contrato`, escaping, níveis de cláusula com asserts reais de conteúdo) — a fraqueza é pontual, no PDF final.
- **Recomendação:** garantir weasyprint no runner de CI (sem skip no CI) e, no teste de PDF, extrair texto do PDF (ex. `pdfminardo`/`pypdf`) para assertar que nome do cliente/valores/nº de contrato aparecem. Transformar o `skipif` em falha no CI.

### B6. Cobertura financeira de regressão — **forte** (ponto positivo)
- **Severidade:** ℹ️
- **Evidência:** `tests/test_negociacao.py` ancora no caso "LELEU" com **valores golden** e asserts numéricos precisos (`test_leleu_ancora`, l.13-23: VBVO/CFO/VBNO/VAVO/Com_Arq/Pro_Fid/Markup...), reconciliação de waterfall por ambiente (`test_ambiente_expoe_waterfall_e_soma_bate`, l.109-127), proteção total de custos, distribuição proporcional (3/7), e casos de borda (orçamento vazio, toggles off). Complementado por `test_aymore.py`, `test_cartao.py`, `test_provisoes*.py`, `test_margens.py`, `tests/golden/`.
- **Impacto:** o núcleo financeiro (motor `mod_negociacao`/`mod_provisoes`/`mod_fin`) tem rede de regressão robusta com asserts de valor reais — a área de maior risco de negócio está bem coberta.
- **Recomendação:** manter. Estender o mesmo rigor golden a `mod_omie` (B2) e ao PDF (B5).

### B7. Herméticos vs estado global — em geral bom, com um risco residual
- **Severidade:** 🟡
- **Evidência:** `conftest.py:19-29` — `app_db` **guarda e restaura** os globais de `database` no teardown (bom). Porém as fixtures principais são `scope="module"` e **rebindam globais de processo** (`database.ENGINE`, `PROJETOS_DIR` em `storage`/`main`/`mod_omie`, l.152-154). Testes que usam `database` **sem** depender de `app_db` (há vários que fazem `create_engine`/`init_db` próprios — 17 arquivos com `create_engine`/rebind) podem, em ordens de execução específicas, ver `database.ENGINE` apontando para o banco de outro módulo se a restauração não cobrir todos os globais rebindados (ex.: `PROJETOS_DIR` **não** é restaurado no teardown de `projetos_dir`).
- **Impacto:** acoplamento pela ordem de testes; risco de flakiness ou de um teste tardio ler `PROJETOS_DIR` de um tmp já deletado. Não observado como falha (suíte não foi rodada), mas é frágil por construção.
- **Recomendação:** restaurar **todos** os globais mutados nos teardowns (incluindo `PROJETOS_DIR` em `storage`/`main`/`mod_omie`); considerar `scope="function"` onde o custo permitir, ou `pytest-randomly` no CI para expor dependência de ordem.

### B8. Cobertura de tenancy/autorização — **ampla** (ponto positivo, com lacuna em `main`)
- **Severidade:** 🟡
- **Evidência:** conjunto robusto: `test_tenancy_{schema,colunas,migracao,seed,bootstrap,validadores,escopo}.py`, `test_perfis*.py`, `test_isolamento_f4*.py`, `test_multi_loja*.py`, `test_escopo_projetista.py`, `test_usuarios*.py`. Cobre schema, migração, escopo por loja/rede e isolamento E2E.
- **Impacto:** a lógica de tenancy em si está bem exercitada. A lacuna é que a **aplicação** dessas regras acontece em rotas de `main.py` (B1) — testada só via os E2E de isolamento, não exaustivamente por rota.
- **Recomendação:** ao endereçar B1, incluir uma matriz de autorização por rota (cada endpoint × cada nível de perfil → permitido/negado) usando o `HttpClient`.

### Tabela — módulo de produção → tem teste?

| Módulo (prod) | LOC | Tem teste? | Observação |
|---|---:|:---:|---|
| `main.py` (router HTTP) | 4758 | **parcial** | só via E2E `servidor`; sem unit por rota (B1) |
| `mod_contrato.py` | 741 | **sim** | `test_contrato*.py` forte no HTML; PDF fraco/skip (B5) |
| `mod_omie.py` | 737 | **não** | 1 menção tangencial; sem teste de parsing/API (B2) |
| `database.py` | 693 | **parcial** | exercitado via fixtures/tenancy; sem teste de hashing/models dedicado |
| `promob_grupos.py` | 289 | **não** | mapeamento de grupos sem teste |
| `auth_routes.py` | 186 | **parcial** | via `test_usuarios_e2e`/login nas fixtures |
| `storage.py` | 184 | **parcial** | exercitado via `projetos_dir`; sem unit direto |
| `mod_tenancy.py` | 175 | **sim** | `test_tenancy_*` amplo (B8) |
| `auth.py` | 156 | **parcial** | login via E2E; sem teste de sessão/expiração dedicado |
| `mod_provisoes.py` | 121 | **sim** | `test_provisoes*.py`, `test_provisao_registro.py` |
| `mod_ciclo.py` | 99 | **sim** | `test_ciclo.py` |
| `mod_orcamento_params.py` | 87 | **sim** | `test_orcamento_params.py`, `test_parametros_projeto.py` |
| `mod_negociacao.py` | 85 | **sim** | `test_negociacao.py` golden forte (B6) |
| `mod_arvore.py` | 66 | **sim** | `test_arvore*.py` |
| `seed.py` | 57 | **parcial** | via fixtures de seed |
| `mod_margens.py` | 52 | **sim** | `test_margens.py` |
| `contrato_editar.py` | 52 | **não** | watcher/regeração de PDF sem teste |
| `_ler_aymore.py` | 40 | **parcial** | coberto indiretamente por `test_aymore.py` |
| `mod_usuarios.py` | 37 | **sim** | `test_usuarios*.py` |
| `mod_proposta.py` | 37 | **sim** | `test_proposta*.py` |
| `perfis.py` | 32 | **sim** | `test_perfis*.py` |
| `mod_qualidade_xml.py` | 32 | **sim** | `test_qualidade_xml.py`, `test_qualidade_upload_e2e.py` |
| `reset_ep07.py` | 28 | **não** | script utilitário |
| `mod_medicao.py` | 12 | **sim** | `test_medicao.py` |
| `mod_fin/aymore.py` | 104 | **sim** | `test_aymore.py` |
| `mod_fin/total_flex.py` | 220 | **parcial** | coberto por `test_config_financeira`/negociação; sem teste dedicado ao nome |
| `mod_fin/venda_programada.py` | 88 | **parcial** | via negociação/provisões |
| `mod_fin/cartao.py` | 85 | **sim** | `test_cartao.py` |
| `mod_fin/base.py` | 32 | **parcial** | utilitário compartilhado |

Resumo: **sem teste** — `mod_omie.py`, `promob_grupos.py`, `contrato_editar.py`, `reset_ep07.py`. **Parcial (só E2E ou indireto)** — `main.py`, `database.py`, `storage.py`, `auth*.py`, `seed.py`, partes de `mod_fin`.

---

## Placar por severidade

| Sev | Qtde | Achados |
|:---:|:---:|---|
| 🔴 Crítico | 5 | A1 (sem pins), A2 (dev×prod), A6 (SQLAlchemy 2.x sem pin), B1 (`main.py` sem unit), B2 (`mod_omie` sem teste), B3 (sem CI) |
| 🟠 Alto | 5 | A3 (sem pyproject), A4 (transitivas), A7 (`.gitignore` `.bak`), A8 (hash sem salt), A10 (sem pip-audit) |
| 🟡 Médio | 4 | A5 (requests CVEs), B4 (README `git add .`), B5 (testes "não explode"/PDF skip), B7 (estado global), B8 (autorização por rota) |
| 🔵 Baixo | 0 | — |
| ℹ️ Info | 2 | A9 (diretas reconciliadas OK), B6 (financeiro golden forte) |

> Contagem exata: 🔴 **6** achados (A1, A2, A6, B1, B2, B3) · 🟠 **5** (A3, A4, A7, A8, A10) · 🟡 **5** (A5, B4, B5, B7, B8) · 🔵 **0** · ℹ️ **2** (A9, B6). Total: **18 achados**.

### Recomendação-mãe (ordem de ataque)
1. **Lockfile com hashes + pin de SQLAlchemy≥2.0** (A1+A6) — fecha reprodutibilidade e o crash de import.
2. **CI no GitHub Actions** rodando pytest + cobertura + pip-audit, num runner que espelhe produção (A2+B3+A10).
3. **Fechar `.gitignore`** (`*.bak*`, `~$*.docx`, `*.tmp`) e corrigir o README (A7+B4).
4. **Testes de `mod_omie` e por-rota de `main.py`** (B2+B1); tornar o teste de PDF não-skip no CI (B5).
5. **KDF com salt** para senhas (A8) — amplifica a mitigação de A7.
