# Perfis de Acesso Configuráveis por Loja — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o modelo hardcoded de 4 perfis por perfis de acesso **configuráveis no banco, por loja**, com 3 padrão (Master/Gerencial/Operador), painel de edição restrito ao Master, Mapa de Funções (Função → perfil default) e step-up por senha ao acessar módulo/painel fora do perfil.

**Architecture:** `perfil_acesso` (tabela nova, por loja) guarda `slug + nome + base + modulos_json + capacidades_json + sistema`. O **acesso a módulo/painel** é lido do `modulos_json` (DB). As **capacidades finas booleanas** (`autorizar`, `aprovar_financeiro`, `gerir_usuarios`, `gerir_perfis`, `ver_parametros`, execução/medição) têm um **preset vindo da `base`** (master/gerencial/operador em `perfis.py`) e podem ser **liberadas/bloqueadas individualmente** por perfil — os overrides ficam em `capacidades_json` (dict `{cap: bool}`; vazio = usa a base). `desconto_max` (numérico, não-toggle) segue vindo da `base`. `perfis.py` vira um **adaptador com registro carregado do DB** (cache com invalidação): `acessa_modulo/acessa_painel/matriz/slugs_da_loja` leem `modulos_json`; `pode(slug, cap)` resolve **override do perfil → base → PERFIS[base]**; `desconto_max/rotulo` resolvem `slug → base`. Perfis de plataforma (`super_admin/admin_rede`) NÃO entram na tabela e seguem 100% pelo `PERFIS` hardcoded (fallback). Os 3 padrão nascem **sem overrides** → capacidades finas idênticas às de hoje. Step-up reaproveita o padrão `_usuario_com_capacidade` + `/api/auth/liberar_impostos`, com log em `LogAcessoDelegado` (molde do `LogAcaoGerencial`).

**Tech Stack:** Python 3 (`http.server`, sem framework), SQLAlchemy + SQLite, `pytest`. Frontend: `static/index.html` (HTML+CSS+JS inline; sem teste JS → verificação manual + `node --check`).

**Convenções do projeto (ler antes):**
- `python3` sempre (nunca `python`). Rodar da raiz `E:\2026\desenvolvimento\orizon-manager`.
- Python muda → **restart** do servidor. `static/index.html` muda → **Ctrl+F5** (lido do disco a cada request).
- Testes: `python3 -m pytest -q` (verde antes de commitar). TDD nos módulos Python.
- Migração idempotente: dados via `_run_migracoes` (rastreada em `schema_migrations`); coluna via `_migrar_colunas` (idempotente por `PRAGMA`).
- `git add` só dos arquivos da mudança (nunca `git add .`). Não commitar `orizon.db`, `perfis_config.json`, `.claude/…`.

---

## Matriz-alvo dos 3 perfis padrão (fonte da verdade deste plano)

`operacionais` = `captacao, cadastro, comercial, producao, estoque, expedicao, montagem, assistencias` (8 domínios, `perfis.py:_MODULOS_OPERACIONAIS`).

| Perfil (slug=base) | operacionais | fiscal | financeiro/folha | Painel admin | Painel config |
|---|---|---|---|---|---|
| `master`    | ✔ | ✔ | ✔ | ✔ | ✔ |
| `gerencial` | ✔ | ✔ | ✔ | ✖ | ✖ |
| `operador`  | ✔ | ✔ | ✖ | ✖ | ✖ |

`modulos_json` resultante:
- **master**: `["captacao","cadastro","comercial","producao","estoque","expedicao","montagem","assistencias","fiscal","financeiro","folha","admin","config"]`
- **gerencial**: `["captacao","cadastro","comercial","producao","estoque","expedicao","montagem","assistencias","fiscal","financeiro","folha"]`
- **operador**: `["captacao","cadastro","comercial","producao","estoque","expedicao","montagem","assistencias","fiscal"]`

Migração de `Usuario.nivel`: `diretoria→master`, `gerencial→gerencial`, `consultor→operador`, `suporte→operador`, `super_admin→super_admin`, `admin_rede→admin_rede`.

---

## File Structure

| Arquivo | Responsabilidade | Ação |
|---|---|---|
| `database.py` | Modelo `PerfilAcesso`, `LogAcessoDelegado`, coluna `Funcao.perfil_padrao`, migrações `perfis_v4_2026` + `perfil_acesso_seed_v1`, `_migrar_colunas` | Modificar |
| `perfis.py` | Vira adaptador: `PERFIS` = **bases** (master/gerencial/operador) + plataforma para caps finas; registro carregado do DB para acesso a módulo/painel; API loja-aware | Reescrever núcleo |
| `mod_perfis.py` | **Novo.** Validadores puros: geração de slug único, validação de `modulos_json` contra `modulos.DOMINIOS`+painéis, base válida, nome | Criar |
| `perfil_store.py` | **Novo.** Camada de leitura/escrita ORM de `PerfilAcesso` + seed por loja idempotente (reusado por migração e criação de loja) | Criar |
| `mod_tenancy.py` | `perfis_atribuiveis` passa a listar perfis do DB da loja | Modificar |
| `main.py` | Endpoints `/api/admin/perfis` (GET/POST/PATCH), `perfis-matriz` re-apontado, `funcoes` c/ `perfil_padrao`, `_sem_acesso_modulo` retorna 403 estruturado, gate `gerir_perfis` | Modificar |
| `auth.py` / `auth_routes.py` | Endpoint `/api/auth/step-up` (valida senha de quem tem o módulo/painel + grava log + emite grant); `_usuario_dict` expõe `pode_gerir_perfis` | Modificar |
| `mod_cadastro.py` | `funcao_serialize`/`funcao_aplicar` incluem `perfil_padrao` | Modificar |
| `static/index.html` | Painel "Perfis de Usuário" editável (Master), Mapa de Funções, modal de step-up | Modificar |
| `tests/test_perfil_acesso_*.py` | Testes de migração, seed, registro, validadores, step-up | Criar |

---

## FASE 0 — `perfis.py`: bases de capacidades finas

### Task 1: Redefinir `PERFIS` como bases (master/gerencial/operador) + plataforma

**Files:**
- Modify: `perfis.py:11-45` (dict `PERFIS`), `perfis.py:112-145` (`CAPACIDADES` — add `gerir_perfis`)
- Test: `tests/test_perfil_bases.py` (Create)

- [ ] **Step 1: Escrever o teste que falha**

Create `tests/test_perfil_bases.py`:
```python
import perfis


def test_bases_existem_com_caps_finas():
    for slug in ("master", "gerencial", "operador"):
        assert perfis.PERFIS.get(slug), f"base {slug} ausente"
    # Master: topo — todas as finas
    assert perfis.pode("master", "gerir_usuarios") is True
    assert perfis.pode("master", "gerir_perfis") is True
    assert perfis.pode("master", "aprovar_financeiro") is True
    assert perfis.desconto_max("master") == 50.0
    # Gerencial: financeiro sim, mas sem painel admin → sem gerir_usuarios/perfis
    assert perfis.pode("gerencial", "aprovar_financeiro") is True
    assert perfis.pode("gerencial", "gerir_usuarios") is False
    assert perfis.pode("gerencial", "gerir_perfis") is False
    assert perfis.desconto_max("gerencial") == 20.0
    # Operador: base operacional/execução, sem financeiro/admin
    assert perfis.pode("operador", "aprovar_financeiro") is False
    assert perfis.pode("operador", "gerir_usuarios") is False
    assert perfis.pode("operador", "registrar_medicao") is True
    assert perfis.desconto_max("operador") == 10.0
    # Plataforma preservada
    assert perfis.pode("super_admin", "gerir_lojas") is True


def test_gerir_perfis_so_master():
    assert perfis.pode("master", "gerir_perfis") is True
    assert perfis.pode("gerencial", "gerir_perfis") is False
    assert perfis.pode("operador", "gerir_perfis") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfil_bases.py -q`
Expected: FAIL (`master` ausente em `PERFIS`).

- [ ] **Step 3: Reescrever `PERFIS` em `perfis.py:11-45`**

Substituir o dict `PERFIS` (os 4 slugs de loja `diretoria/gerencial/consultor/suporte`) pelas 3 **bases**, mantendo `super_admin`/`admin_rede` intactos. Os booleanos `acesso_*` continuam aqui só como **fallback** (plataforma) e como semente do `modulos_json` no seed; o acesso real de loja passa a vir do DB (Task 5).
```python
PERFIS = {
    "master": {"rotulo": "Master", "desconto_max": 50.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": True, "acesso_config": True,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": True,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": True, "gerir_perfis": True,
        "editar_dados_loja": True, "executar_pe": True, "revisar_pe": True, "registrar_medicao": True},
    "gerencial": {"rotulo": "Gerencial", "desconto_max": 20.0,
        "acesso_operacional": True, "acesso_financeiro": True, "acesso_fiscal": True,
        "acesso_admin": False, "acesso_config": False,
        "ver_parametros": True, "autorizar": True, "aprovar_financeiro": True,
        "aprovar_medicao_reprovada": True, "gerir_usuarios": False, "gerir_perfis": False,
        "editar_dados_loja": False, "executar_pe": True, "revisar_pe": True, "registrar_medicao": True},
    "operador": {"rotulo": "Operador", "desconto_max": 10.0,
        "acesso_operacional": True, "acesso_financeiro": False, "acesso_fiscal": True,
        "acesso_admin": False, "acesso_config": False,
        "ver_parametros": False, "autorizar": False, "aprovar_financeiro": False,
        "aprovar_medicao_reprovada": False, "gerir_usuarios": False, "gerir_perfis": False,
        "editar_dados_loja": False, "executar_pe": True, "revisar_pe": False, "registrar_medicao": True},
    # ── Plataforma/Rede (fora dos perfis de loja; NÃO entram na tabela perfil_acesso) ──
    "super_admin": {"rotulo": "Administrador da Plataforma", "desconto_max": 0.0,
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "gerir_perfis": True, "editar_dados_loja": True,
        "gerir_redes": True, "gerir_lojas": True},
    "admin_rede": {"rotulo": "Administrador de Rede", "desconto_max": 0.0,
        "acesso_operacional": False, "acesso_financeiro": False, "acesso_fiscal": False,
        "acesso_admin": True, "acesso_config": True,
        "gerir_usuarios": True, "gerir_perfis": False, "editar_dados_loja": True,
        "gerir_redes": False, "gerir_lojas": True},
}

# Compat: slugs antigos ainda referenciados por dados residuais resolvem para a base equivalente.
_ALIAS_BASE = {"diretoria": "master", "consultor": "operador", "suporte": "operador"}
```

Adicionar a `_DEFAULT` (`perfis.py:47-53`) a chave `"gerir_perfis": False`. E em `CAPACIDADES` (`perfis.py:112`) adicionar:
```python
    "gerir_perfis":              {"rotulo": "Gerir perfis de acesso", "grupo": "Administração",
        "descricao": "Criar/editar perfis de acesso da loja (só Master)."},
```

Ajustar `pode` (`perfis.py:105-106`) e `desconto_max`/`rotulo` para resolver alias de base:
```python
def _base(slug):
    """Resolve o slug para a BASE de capacidades finas (master/gerencial/operador/plataforma)."""
    if slug in PERFIS:
        return slug
    return _ALIAS_BASE.get(slug, slug)   # Task 5 sobrescreve p/ consultar o registro DB


def pode(slug, capacidade):
    return bool(PERFIS.get(_base(slug), _DEFAULT).get(capacidade, False))


def desconto_max(slug):
    return PERFIS.get(_base(slug), _DEFAULT)["desconto_max"]
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_perfil_bases.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte cheia (pega quebras nos gates que usam slugs antigos)**

Run: `python3 -m pytest -q`
Expected: PASS. Se algum teste referenciar `"diretoria"/"consultor"` como nível, ele resolve via `_ALIAS_BASE` — não deve quebrar `pode`. Anote qualquer falha para corrigir no próprio teste (sem afrouxar gate).

- [ ] **Step 6: Commit**

```bash
git add perfis.py tests/test_perfil_bases.py
git commit -m "feat(perfis): PERFIS vira bases master/gerencial/operador + gerir_perfis (fundação)"
```

---

## FASE 1 — Banco: modelo, migração de nivel, seed por loja

### Task 2: Modelos `PerfilAcesso` e `LogAcessoDelegado` + coluna `Funcao.perfil_padrao`

**Files:**
- Modify: `database.py` (após `Funcao` em `:202`; após `LogAcaoGerencial` em `:112`; `_migrar_colunas` bloco Cadastro v10 em `:1099-1118`)
- Test: `tests/test_perfil_acesso_schema.py` (Create)

- [ ] **Step 1: Teste que falha**

Create `tests/test_perfil_acesso_schema.py`:
```python
from sqlalchemy import create_engine, inspect
import database


def _mem():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    return eng


def test_tabela_perfil_acesso_existe():
    insp = inspect(_mem())
    assert "perfil_acesso" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("perfil_acesso")}
    assert {"id", "loja_id", "slug", "nome", "base", "modulos_json",
            "capacidades_json", "sistema", "criado_em"} <= cols


def test_funcao_tem_perfil_padrao():
    insp = inspect(_mem())
    cols = {c["name"] for c in insp.get_columns("funcoes")}
    assert "perfil_padrao" in cols


def test_log_acesso_delegado_existe():
    insp = inspect(_mem())
    assert "log_acesso_delegado" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("log_acesso_delegado")}
    assert {"id", "solicitante_id", "autorizador_id", "recurso", "criado_em"} <= cols
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfil_acesso_schema.py -q`
Expected: FAIL (tabela `perfil_acesso` ausente).

- [ ] **Step 3: Adicionar modelos e coluna**

Em `database.py`, após a classe `Funcao` (`:202`), adicionar:
```python
class PerfilAcesso(Base):
    """Perfil de acesso configurável POR LOJA (Regras_Funcoes_Perfis_Atribuicoes rev3 §2).
    Acesso a módulo/painel vem de `modulos_json`; capacidades finas vêm de perfis.PERFIS[`base`]."""
    __tablename__ = "perfil_acesso"

    id           = Column(Integer,     primary_key=True, autoincrement=True)
    loja_id      = Column(Integer,     ForeignKey("lojas.id"), nullable=False)  # perfis são por loja
    slug         = Column(String(40),  nullable=False)   # único globalmente (system: master/gerencial/operador)
    nome         = Column(String(80),  nullable=False)
    base         = Column(String(20),  nullable=False)   # master | gerencial | operador (preset das caps finas)
    modulos_json = Column(Text,        nullable=False, default="[]")  # JSON: ids de módulo/painel acessíveis
    capacidades_json = Column(Text,    nullable=False, default="{}")  # JSON {cap: bool} — overrides sobre a base
    sistema      = Column(Integer,     nullable=False, default=0)     # 1 = padrão, não apagável
    criado_em    = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("loja_id", "slug", name="uq_perfil_loja_slug"),)
```

Após `LogAcaoGerencial` (`:112`), adicionar:
```python
class LogAcessoDelegado(Base):
    """Auditoria do step-up por senha: fulano acessou um módulo/painel fora do perfil com a
    autorização (senha) de alguém que tinha o perfil. Molde do LogAcaoGerencial."""
    __tablename__ = "log_acesso_delegado"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    recurso        = Column(String(40), nullable=False)   # id do módulo ou 'admin'/'config'
    contexto       = Column(Text,     nullable=True)      # JSON opcional
    criado_em      = Column(DateTime, default=datetime.utcnow)
```

Na classe `Funcao` (`:193-202`), adicionar a coluna (para bancos novos):
```python
    perfil_padrao = Column(String(40), nullable=True)   # slug do perfil_acesso default da função
```

Em `_migrar_colunas`, no bloco Cadastro v10 (`database.py:1113`, junto dos outros `_add_cols`), adicionar:
```python
        _add_cols("funcoes", [("perfil_padrao", "VARCHAR(40)")])
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_perfil_acesso_schema.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_perfil_acesso_schema.py
git commit -m "feat(perfis): tabela perfil_acesso + log_acesso_delegado + Funcao.perfil_padrao"
```

### Task 3: Migração `perfis_v4_2026` — migrar `Usuario.nivel` + referências residuais de slug

**Files:**
- Modify: `database.py:_run_migracoes` (após `perfis_v3_2026`, `:1229`)
- Modify: `perfis.py` (expor helper público `base(slug)`)
- Modify: `main.py:7547` (`_PERFIS_ESCOPO_PROPRIO`/`_ve_apenas_proprios_projetos`), `mod_escopo.py:31` (`_ESCOPO_POSSE`/`pode_ver_projeto`), `mod_cadastro.py:61,105` (default `"consultor"`)
- Modify: `tests/conftest.py` (cons_l1 → `operador`), `tests/test_escopo_projetista.py`, `tests/test_atribuicoes.py` (slugs novos)
- Test: `tests/test_perfil_migracao_nivel.py` (Create)

**Contexto (achado da Task 1b):** a regra de segurança "vê só os próprios projetos" está keyed em slug literal `"consultor"` em DUAS cópias (`main.py:7547` e `mod_escopo.py:31`). Pós-migração ninguém é `"consultor"` → a regra quebraria. Solução dirigida pela **base** (cobre também perfis custom com base operador): `perfis.base(nivel) == "operador"`.

- [ ] **Step 1: Teste que falha**

Create `tests/test_perfil_migracao_nivel.py`:
```python
import sqlite3
import database


def _conn():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("""CREATE TABLE lojas (id INTEGER PRIMARY KEY, nome TEXT, cnpj TEXT, codigo TEXT,
        telefone TEXT, email TEXT, testemunha1_nome TEXT, testemunha1_cpf TEXT,
        testemunha2_nome TEXT, testemunha2_cpf TEXT, ativo INTEGER)""")
    cur.execute("INSERT INTO lojas(id, nome) VALUES (1, 'L1')")
    cur.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nivel TEXT, loja_id INTEGER, funcionario_id INTEGER, funcao_id INTEGER)")
    cur.execute("CREATE TABLE funcoes (id INTEGER PRIMARY KEY, loja_id INTEGER, nome TEXT, status TEXT, perfil_padrao TEXT)")
    for i, niv in enumerate(("diretoria", "gerencial", "consultor", "suporte", "super_admin"), start=1):
        cur.execute("INSERT INTO usuarios(id, nivel, loja_id) VALUES (?,?,1)", (i, niv))
    conn.commit()
    return conn


def test_migra_nivel_para_bases():
    conn = _conn()
    database._run_migracoes(conn)
    got = dict(conn.execute("SELECT id, nivel FROM usuarios").fetchall())
    assert got[1] == "master"      # diretoria
    assert got[2] == "gerencial"   # inalterado
    assert got[3] == "operador"    # consultor
    assert got[4] == "operador"    # suporte
    assert got[5] == "super_admin" # plataforma inalterada


def test_idempotente():
    conn = _conn()
    database._run_migracoes(conn)
    database._run_migracoes(conn)
    got = dict(conn.execute("SELECT id, nivel FROM usuarios").fetchall())
    assert got[1] == "master"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfil_migracao_nivel.py -q`
Expected: FAIL (`nivel` continua `diretoria`).

- [ ] **Step 3: Adicionar a migração**

Em `_run_migracoes`, após o bloco `perfis_v3_2026` (`database.py:1229`), espelhando o padrão de `perfis_v2_2026`:
```python
    # 2026-07-10: RESET rev3 — perfis viram configuráveis por loja; nivel passa a referenciar a BASE.
    if "perfis_v4_2026" not in aplicadas and _tabela_existe(cur, "usuarios"):
        _MAP = {"diretoria": "master", "consultor": "operador", "suporte": "operador"}
        for antigo, novo in _MAP.items():
            cur.execute("UPDATE usuarios SET nivel=? WHERE nivel=?", (novo, antigo))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfis_v4_2026')")
```

- [ ] **Step 4: Migrar referências residuais de slug no código de produção (dirigido pela base)**

Em `perfis.py`, expor um helper público (o `_base` já existe da Task 1):
```python
def base(slug):
    """Base (master/gerencial/operador/plataforma) de um slug de perfil — pública."""
    return _base(slug)
```

Em `main.py` — `_ve_apenas_proprios_projetos` (usa `_PERFIS_ESCOPO_PROPRIO = {"consultor"}` em `:7547`): trocar a checagem literal por base-driven. Ler a função e ajustar para:
```python
def _ve_apenas_proprios_projetos(nivel):
    return perfis.base(nivel) == "operador"
```
Remover o `_PERFIS_ESCOPO_PROPRIO` se ficar órfão (ou mantê-lo só se referenciado em outro ponto — conferir com grep antes).

Em `mod_escopo.py` — `_ESCOPO_POSSE = frozenset({"consultor"})` (`:31`), usado por `pode_ver_projeto`: trocar a checagem por `perfis.base(ator["nivel"]) == "operador"` (ler a função e adaptar; importar `perfis` se necessário). Preservar a semântica atual (operador vê só os próprios; gerência vê todos).

Em `mod_cadastro.py:61,105` — o default `"consultor"` do perfil de acesso ao criar conta de Funcionário: trocar por `"operador"` (nível de loja válido no novo modelo). (Task 8 depois liga isso ao `Funcao.perfil_padrao`.)

Atualizar os testes que fixam esses comportamentos com slug antigo:
- `tests/test_escopo_projetista.py`: `_ve_apenas_proprios_projetos("consultor")` → `"operador"` (True); `"gerente_vendas"`/`"diretor"`/`"gerente_adm_fin"` → `"gerencial"`/`"master"` (False). Ajustar os dicts `{"nivel": "consultor"}` → `"operador"`, `"gerente_vendas"` → `"gerencial"`.
- `tests/test_atribuicoes.py`: idem — `consultor`→`operador`, `diretor`/`gerente_vendas`/`gerente_adm_fin`→`master`/`gerencial`, mantendo o significado das asserções.
- `tests/conftest.py`: `cons_l1` volta a ser `"operador"` (agora que a regra é base-driven) e, se a Task 1b tiver criado um usuário ad-hoc em `tests/test_projeto_editar_e2e.py::test_consultores_endpoint_gerente_vs_consultor` para contornar isso, simplificar de volta para usar `cons_l1`.

> Nota: `contrato_editar.py:61` usa slugs pré-Perfil-4 (`gerente/diretor/admin`) — provável bug pré-existente, FORA do escopo desta frente. Só registrar no relatório, não corrigir aqui.

- [ ] **Step 5: Rodar e ver passar (arquivo + suíte cheia)**

Run: `python3 -m pytest tests/test_perfil_migracao_nivel.py tests/test_escopo_projetista.py tests/test_atribuicoes.py -q` → PASS.
Run: `python3 -m pytest -q` → tudo verde.

- [ ] **Step 6: Commit**

```bash
git add database.py perfis.py main.py mod_escopo.py mod_cadastro.py tests/test_perfil_migracao_nivel.py tests/test_escopo_projetista.py tests/test_atribuicoes.py tests/conftest.py tests/test_projeto_editar_e2e.py
git commit -m "feat(perfis): migração perfis_v4_2026 (nivel→base) + escopo-próprio/cadastro dirigidos pela base"
```

### Task 4: `perfil_store.py` + seed por loja `perfil_acesso_seed_v1`

**Files:**
- Create: `perfil_store.py`
- Modify: `database.py:_run_migracoes` (após `perfil_acesso_seed`), `database.py:FUNCOES_PADRAO` region (`:1146`) — add constantes dos 3 perfis
- Test: `tests/test_perfil_seed.py` (Create)

- [ ] **Step 1: Teste que falha**

Create `tests/test_perfil_seed.py`:
```python
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database
import perfil_store


def _sess():
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    db = S()
    db.add(database.Loja(id=1, nome="L1"))
    db.add(database.Loja(id=2, nome="L2"))
    db.commit()
    return db


def test_seed_cria_3_perfis_por_loja():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 2)
    p1 = db.query(database.PerfilAcesso).filter_by(loja_id=1).all()
    assert {p.slug for p in p1} == {"master", "gerencial", "operador"}
    assert all(p.sistema == 1 for p in p1)
    master = next(p for p in p1 if p.slug == "master")
    mods = set(json.loads(master.modulos_json))
    assert {"admin", "config", "financeiro", "fiscal"} <= mods
    operador = next(p for p in p1 if p.slug == "operador")
    omods = set(json.loads(operador.modulos_json))
    assert "fiscal" in omods and "financeiro" not in omods and "admin" not in omods


def test_seed_idempotente():
    db = _sess()
    perfil_store.seed_perfis_loja(db, 1)
    perfil_store.seed_perfis_loja(db, 1)
    assert db.query(database.PerfilAcesso).filter_by(loja_id=1).count() == 3
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfil_seed.py -q`
Expected: FAIL (`No module named 'perfil_store'`).

- [ ] **Step 3: Criar `perfil_store.py`**

```python
# -*- coding: utf-8 -*-
"""perfil_store.py — leitura/escrita ORM de PerfilAcesso e seed idempotente por loja."""
import json
from database import PerfilAcesso

# Definição dos 3 perfis padrão (rev3 §2). base == slug para os de sistema.
_OPERACIONAIS = ["captacao", "cadastro", "comercial", "producao",
                 "estoque", "expedicao", "montagem", "assistencias"]
PERFIS_PADRAO = [
    {"slug": "master", "nome": "Master", "base": "master",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha", "admin", "config"]},
    {"slug": "gerencial", "nome": "Gerencial", "base": "gerencial",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha"]},
    {"slug": "operador", "nome": "Operador", "base": "operador",
     "modulos": _OPERACIONAIS + ["fiscal"]},
]


def seed_perfis_loja(db, loja_id):
    """Semeia os 3 perfis padrão na loja. Idempotente por (loja_id, slug). Retorna nº criados."""
    if loja_id is None:
        return 0
    existentes = {p.slug for p in db.query(PerfilAcesso).filter_by(loja_id=loja_id).all()}
    criados = 0
    for spec in PERFIS_PADRAO:
        if spec["slug"] in existentes:
            continue
        db.add(PerfilAcesso(loja_id=loja_id, slug=spec["slug"], nome=spec["nome"],
                            base=spec["base"], modulos_json=json.dumps(spec["modulos"]),
                            sistema=1))
        criados += 1
    db.commit()
    return criados


def perfis_da_loja(db, loja_id):
    """Lista os PerfilAcesso de uma loja (ordenados: sistema primeiro, depois por nome)."""
    return (db.query(PerfilAcesso).filter_by(loja_id=loja_id)
            .order_by(PerfilAcesso.sistema.desc(), PerfilAcesso.nome).all())
```

- [ ] **Step 4: Migração de seed por loja (bancos existentes)**

Em `_run_migracoes`, após `perfis_v4_2026`, espelhando `funcoes_seed_v1` (`database.py:1190-1198`), com SQL cru (não ORM, pois roda sobre `sqlite3.Connection`):
```python
    # 2026-07-10: semeia os 3 perfis padrão nas lojas existentes (rev3 §2). Idempotente por (loja_id, slug).
    if "perfil_acesso_seed_v1" not in aplicadas and _tabela_existe(cur, "perfil_acesso") and _tabela_existe(cur, "lojas"):
        import json as _json
        _OP = ["captacao", "cadastro", "comercial", "producao", "estoque", "expedicao", "montagem", "assistencias"]
        _SPEC = [("master", "Master", "master", _OP + ["fiscal", "financeiro", "folha", "admin", "config"]),
                 ("gerencial", "Gerencial", "gerencial", _OP + ["fiscal", "financeiro", "folha"]),
                 ("operador", "Operador", "operador", _OP + ["fiscal"])]
        for (lid,) in cur.execute("SELECT id FROM lojas").fetchall():
            tem = {r[0] for r in cur.execute("SELECT slug FROM perfil_acesso WHERE loja_id=?", (lid,)).fetchall()}
            for slug, nome, base, mods in _SPEC:
                if slug not in tem:
                    cur.execute("INSERT INTO perfil_acesso(loja_id, slug, nome, base, modulos_json, capacidades_json, sistema) "
                                "VALUES(?,?,?,?,?,'{}',1)", (lid, slug, nome, base, _json.dumps(mods)))
        cur.execute("INSERT INTO schema_migrations(id) VALUES('perfil_acesso_seed_v1')")
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_perfil_seed.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add perfil_store.py database.py tests/test_perfil_seed.py
git commit -m "feat(perfis): perfil_store + seed idempotente dos 3 perfis por loja"
```

---

## FASE 2 — `perfis.py` como adaptador com registro do DB

### Task 5: Registro carregado do DB para acesso a módulo/painel + API loja-aware

**Files:**
- Modify: `perfis.py` (novas funções `_carregar_registro/recarregar/acessa_modulo/acessa_painel/rotulo/matriz_loja/slugs_da_loja/opcoes_da_loja`; `_base` passa a consultar o registro)
- Test: `tests/test_perfil_registro.py` (Create)

**Contexto de invalidação:** `perfis.py` mantém `_REG_BY_SLUG` e `_REG_BY_LOJA` (lazy). `recarregar()` zera o cache; deve ser chamado após qualquer escrita em `perfil_acesso` (Task 6) e após seed. Slugs de sistema (`master/gerencial/operador`) são idênticos entre lojas → colisão em `_REG_BY_SLUG` é benigna. Slugs custom são únicos globalmente (Task 7 garante).

- [ ] **Step 1: Teste que falha**

Create `tests/test_perfil_registro.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import database, perfil_store, perfis


def _bind_mem(monkeypatch):
    eng = create_engine("sqlite:///:memory:")
    database.Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    db = S()
    db.add(database.Loja(id=1, nome="L1"))
    db.commit()
    perfil_store.seed_perfis_loja(db, 1)
    db.close()
    # perfis.py deve ler via database.get_session → rebinda o Session global
    monkeypatch.setattr(database, "Session", S)
    perfis.recarregar()
    return S


def test_acessa_modulo_do_registro(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.acessa_modulo("operador", "fiscal") is True
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_modulo("master", "financeiro") is True
    # núcleo nunca é bloqueado
    assert perfis.acessa_modulo("operador", "auth") is True


def test_acessa_painel_do_registro(monkeypatch):
    _bind_mem(monkeypatch)
    assert perfis.acessa_painel("master", "admin") is True
    assert perfis.acessa_painel("gerencial", "admin") is False
    assert perfis.acessa_painel("operador", "config") is False


def test_base_resolve_caps_finas(monkeypatch):
    _bind_mem(monkeypatch)
    # 'operador' (slug DB) → base operador → sem gerir_usuarios
    assert perfis.pode("operador", "gerir_usuarios") is False
    assert perfis.pode("master", "gerir_usuarios") is True


def test_slugs_da_loja(monkeypatch):
    _bind_mem(monkeypatch)
    assert set(perfis.slugs_da_loja(1)) == {"master", "gerencial", "operador"}


def test_plataforma_fallback_sem_registro(monkeypatch):
    _bind_mem(monkeypatch)
    # super_admin não está na tabela → cai no PERFIS hardcoded
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.pode("super_admin", "gerir_lojas") is True


def test_override_de_capacidade_fina(monkeypatch):
    import json, database, perfil_store
    S = _bind_mem(monkeypatch)
    db = S()
    # perfil custom base operador, mas com aprovar_financeiro LIBERADO e registrar_medicao BLOQUEADO
    db.add(database.PerfilAcesso(loja_id=1, slug="operador_plus", nome="Operador+",
        base="operador", modulos_json=json.dumps(["comercial", "fiscal"]),
        capacidades_json=json.dumps({"aprovar_financeiro": True, "registrar_medicao": False}), sistema=0))
    db.commit(); db.close()
    perfis.recarregar()
    assert perfis.pode("operador_plus", "aprovar_financeiro") is True   # override liberou
    assert perfis.pode("operador_plus", "registrar_medicao") is False   # override bloqueou
    assert perfis.pode("operador_plus", "gerir_usuarios") is False      # sem override → base operador
    assert perfis.desconto_max("operador_plus") == 10.0                 # desconto vem da base
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfil_registro.py -q`
Expected: FAIL (`recarregar`/`slugs_da_loja` inexistentes).

- [ ] **Step 3: Implementar o registro em `perfis.py`**

Adicionar (após `CAPACIDADES`/`matriz`, mantendo `matriz()` legado como wrapper):
```python
import json as _json

_REG_BY_SLUG = None   # {slug: {"base","nome","modulos":set,"loja_id","sistema"}}
_REG_BY_LOJA = None   # {loja_id: {slug: <mesma info>}}


def _carregar_registro():
    """Carrega perfil_acesso do banco para os caches. Silencioso se a tabela ainda não existe."""
    global _REG_BY_SLUG, _REG_BY_LOJA
    _REG_BY_SLUG, _REG_BY_LOJA = {}, {}
    try:
        from database import Session, PerfilAcesso
        db = Session()
        try:
            for p in db.query(PerfilAcesso).all():
                info = {"base": p.base, "nome": p.nome, "sistema": bool(p.sistema),
                        "loja_id": p.loja_id, "modulos": set(_json.loads(p.modulos_json or "[]")),
                        "caps": _json.loads(p.capacidades_json or "{}")}   # overrides {cap: bool}
                _REG_BY_SLUG[p.slug] = info
                _REG_BY_LOJA.setdefault(p.loja_id, {})[p.slug] = info
        finally:
            db.close()
    except Exception:
        pass   # DB indisponível/tabela ausente → registro vazio, cai no fallback PERFIS


def recarregar():
    """Invalida o cache; próximo acesso recarrega do banco."""
    global _REG_BY_SLUG, _REG_BY_LOJA
    _REG_BY_SLUG, _REG_BY_LOJA = None, None


def _reg():
    if _REG_BY_SLUG is None:
        _carregar_registro()
    return _REG_BY_SLUG
```

Reescrever `_base`, `pode`, `acessa_modulo`, `acessa_painel`, `rotulo` (o `pode` da Task 1 é substituído por este, que aplica o override do perfil sobre a base):
```python
def _base(slug):
    info = _reg().get(slug)
    if info:
        return info["base"]
    if slug in PERFIS:
        return slug
    return _ALIAS_BASE.get(slug, slug)


def pode(slug, capacidade):
    """Override do perfil (capacidades_json) manda; senão cai na base PERFIS[base]."""
    info = _reg().get(slug)
    if info and capacidade in info["caps"]:
        return bool(info["caps"][capacidade])
    return bool(PERFIS.get(_base(slug), _DEFAULT).get(capacidade, False))


def acessa_modulo(slug, modulo_id):
    """True se o perfil pode abrir o módulo. Registro DB manda; núcleo/desconhecido nunca bloqueia."""
    info = _reg().get(slug)
    if info is not None:
        try:
            import modulos as _mod
            if modulo_id not in _mod.DOMINIOS:   # núcleo/desconhecido
                return True
        except Exception:
            pass
        return modulo_id in info["modulos"]
    # Fallback (plataforma / sem registro): comportamento antigo por capacidade.
    if modulo_id in _MODULO_ACESSO:
        return pode(slug, _MODULO_ACESSO[modulo_id])
    if modulo_id in _MODULOS_OPERACIONAIS:
        return pode(slug, "acesso_operacional")
    return True


def acessa_painel(slug, painel):
    info = _reg().get(slug)
    if info is not None:
        return painel in info["modulos"]
    return pode(slug, "acesso_admin" if painel == "admin" else "acesso_config")


def rotulo(slug):
    info = _reg().get(slug)
    if info:
        return info["nome"]
    return PERFIS.get(_base(slug), _DEFAULT)["rotulo"]


def slugs_da_loja(loja_id):
    if _REG_BY_LOJA is None:
        _carregar_registro()
    return list((_REG_BY_LOJA or {}).get(loja_id, {}).keys())


def opcoes_da_loja(loja_id):
    if _REG_BY_LOJA is None:
        _carregar_registro()
    reg = (_REG_BY_LOJA or {}).get(loja_id, {})
    return [{"slug": s, "rotulo": reg[s]["nome"]} for s in reg]


# Capacidades finas booleanas SELECIONÁVEIS no modal (exclui os acesso_* de módulo/painel — esses
# vêm de modulos_json — e as de plataforma gerir_redes/gerir_lojas). Ordem estável p/ a UI.
CAPS_SELECIONAVEIS = ["ver_parametros", "autorizar", "aprovar_financeiro", "gerir_usuarios",
                      "gerir_perfis", "editar_dados_loja", "registrar_medicao",
                      "aprovar_medicao_reprovada", "executar_pe", "revisar_pe"]


def capacidades_efetivas(slug):
    """Mapa {cap: bool} das caps selecionáveis, resolvido (override do perfil sobre a base)."""
    return {c: pode(slug, c) for c in CAPS_SELECIONAVEIS}


def matriz_loja(loja_id):
    """Perfis da loja com módulos + capacidades resolvidos — alimenta Admin › Perfis de Usuário (editável)."""
    if _REG_BY_LOJA is None:
        _carregar_registro()
    reg = (_REG_BY_LOJA or {}).get(loja_id, {})
    perfis_out = [{"slug": s, "nome": reg[s]["nome"], "base": reg[s]["base"],
                   "sistema": reg[s]["sistema"], "modulos": sorted(reg[s]["modulos"]),
                   "capacidades": capacidades_efetivas(s), "desconto_max": desconto_max(s)} for s in reg]
    return {"perfis": perfis_out, "capacidades": CAPACIDADES, "caps_selecionaveis": CAPS_SELECIONAVEIS}
```

> Nota: `matriz()` legado (`perfis.py:148`) fica como está (ainda usado por testes antigos); a tela nova usa `matriz_loja`. `slugs_loja()`/`opcoes_loja()` legados permanecem para plataforma.

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_perfil_registro.py -q`
Expected: PASS.

- [ ] **Step 5: Suíte cheia**

Run: `python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add perfis.py tests/test_perfil_registro.py
git commit -m "feat(perfis): registro DB (acesso a módulo/painel por loja) + API loja-aware"
```

---

## FASE 3 — Painel editável (Master) + Mapa de Funções

### Task 6: `mod_perfis.py` — validadores puros (slug/módulos/base/nome)

**Files:**
- Create: `mod_perfis.py`
- Test: `tests/test_mod_perfis.py` (Create)

- [ ] **Step 1: Teste que falha**

Create `tests/test_mod_perfis.py`:
```python
import mod_perfis


def test_slug_unico_gera_sufixo():
    existentes = {"master", "gerencial", "operador", "vendas"}
    s = mod_perfis.gerar_slug("Vendas", existentes)
    assert s not in existentes and s.startswith("vendas")


def test_valida_modulos_rejeita_id_desconhecido():
    ok, _ = mod_perfis.validar_modulos(["fiscal", "admin"])
    assert ok
    ok2, err = mod_perfis.validar_modulos(["fiscal", "inexistente"])
    assert not ok2 and "inexistente" in err


def test_valida_base():
    assert mod_perfis.validar_base("operador")[0]
    assert not mod_perfis.validar_base("xpto")[0]


def test_valida_nome():
    assert mod_perfis.validar_nome("Vendas Júnior")[0]
    assert not mod_perfis.validar_nome("  ")[0]


def test_valida_capacidades_aceita_subset_conhecido():
    ok, limpo = mod_perfis.validar_capacidades({"aprovar_financeiro": True, "gerir_usuarios": False})
    assert ok and limpo == {"aprovar_financeiro": True, "gerir_usuarios": False}


def test_valida_capacidades_rejeita_cap_desconhecida():
    ok, err = mod_perfis.validar_capacidades({"virar_deus": True})
    assert not ok and "virar_deus" in err
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_mod_perfis.py -q`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Criar `mod_perfis.py`**

```python
# -*- coding: utf-8 -*-
"""mod_perfis.py — validadores puros para criação/edição de perfil_acesso (sem I/O)."""
import re
import unicodedata
import modulos
import perfis

_PAINEIS = {"admin", "config"}
_BASES = {"master", "gerencial", "operador"}


def _slugify(txt):
    t = unicodedata.normalize("NFKD", txt or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
    return t or "perfil"


def gerar_slug(nome, existentes):
    """Slug único globalmente a partir do nome (append _2, _3… se colidir)."""
    base = _slugify(nome)
    if base not in existentes:
        return base
    i = 2
    while f"{base}_{i}" in existentes:
        i += 1
    return f"{base}_{i}"


def ids_validos():
    """Conjunto de ids selecionáveis: os 11 domínios + os 2 painéis."""
    return set(modulos.DOMINIOS) | _PAINEIS


def validar_modulos(lista):
    if not isinstance(lista, list):
        return False, "modulos deve ser lista"
    validos = ids_validos()
    for m in lista:
        if m not in validos:
            return False, f"módulo inválido: {m}"
    return True, ""


def validar_base(base):
    return (base in _BASES), ("" if base in _BASES else "base inválida")


def validar_nome(nome):
    n = (nome or "").strip()
    return (bool(n), "" if n else "nome obrigatório")


def validar_capacidades(caps):
    """caps = dict {cap: bool} de OVERRIDES; só aceita chaves em perfis.CAPS_SELECIONAVEIS.
    Retorna (True, dict_limpo) ou (False, erro)."""
    if caps in (None, {}):
        return True, {}
    if not isinstance(caps, dict):
        return False, "capacidades deve ser objeto {cap: bool}"
    permitidas = set(perfis.CAPS_SELECIONAVEIS)
    limpo = {}
    for k, v in caps.items():
        if k not in permitidas:
            return False, f"capacidade inválida: {k}"
        limpo[k] = bool(v)
    return True, limpo
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_mod_perfis.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_perfis.py tests/test_mod_perfis.py
git commit -m "feat(perfis): mod_perfis — validadores puros de perfil (slug/módulos/base/nome)"
```

### Task 7: Endpoints `/api/admin/perfis` (GET/POST/PATCH) + `perfis-matriz` re-apontado

**Files:**
- Modify: `main.py` (GET em `:1031-1039` `perfis-matriz`; adicionar `GET/POST/PATCH /api/admin/perfis`), `perfil_store.py` (funções `criar_perfil`, `editar_perfil`)
- Modify: `auth.py:_usuario_dict` (`:186`) — expõe `pode_gerir_perfis`
- Modify (gap): `perfis.existe(slug)` reconhece perfis do registro DB; `mod_tenancy.perfis_atribuiveis(ator,"loja")` lista os perfis do banco da loja (para o dropdown de usuário e a validação aceitarem perfis custom)
- Test: `tests/test_perfis_api_e2e.py` (Create — usa fixture `servidor`/`http_client_factory` do conftest)

**Gate:** criar/editar exige `perfis.pode(nivel, "gerir_perfis")` (só base `master`). GET continua em `gerir_usuarios` (mesma audiência que já vê a aba).

**Habilitadores (para assinalar usuário a perfil custom):**
- `perfis.existe(slug)` → `return slug in PERFIS or slug in _reg()`.
- `mod_tenancy.perfis_atribuiveis(ator, "loja")` → retorna `perfis.slugs_da_loja(<loja do ator>)` (fallback para `slugs_loja()` se o registro estiver vazio); ramos plataforma/rede inalterados.

- [ ] **Step 1: Teste que falha** (e2e HTTP; seguir estilo dos testes de integração existentes que usam `servidor`+`http_client_factory` do `tests/conftest.py`)

Create `tests/test_perfis_api_e2e.py`:
```python
import json


def _login(client, login, senha):
    r = client.post("/api/auth/login", json={"login": login, "senha": senha})
    return r  # cookie fica no client

def test_master_lista_cria_edita(servidor, http_client_factory):
    c = http_client_factory()
    _login(c, "pdm2026", "SENHA_MASTER")   # ajustar p/ credencial de teste do seed
    # GET lista
    r = c.get("/api/admin/perfis")
    assert r.status_code == 200 and r.json()["ok"]
    slugs = {p["slug"] for p in r.json()["perfis"]}
    assert {"master", "gerencial", "operador"} <= slugs
    # GET expõe as capacidades finas selecionáveis + as efetivas por perfil
    assert "caps_selecionaveis" in r.json()
    op = next(p for p in r.json()["perfis"] if p["slug"] == "operador")
    assert op["capacidades"]["aprovar_financeiro"] is False   # base operador, sem override
    # POST cria custom com módulos E override de capacidade fina
    r = c.post("/api/admin/perfis", json={"nome": "Vendas Jr", "base": "operador",
                                          "modulos": ["cadastro", "comercial", "fiscal"],
                                          "capacidades": {"aprovar_financeiro": True}})
    assert r.status_code == 201 and r.json()["ok"], r.text
    novo = r.json()["perfil"]["slug"]
    # PATCH edita módulos e capacidades
    r = c.patch(f"/api/admin/perfis/{novo}", json={"modulos": ["cadastro", "comercial"],
                                                   "capacidades": {"aprovar_financeiro": True, "autorizar": True}})
    assert r.status_code == 200 and r.json()["ok"]

def test_sistema_nao_edita_nem_apaga(servidor, http_client_factory):
    c = http_client_factory()
    _login(c, "pdm2026", "SENHA_MASTER")
    r = c.patch("/api/admin/perfis/master", json={"modulos": []})
    assert r.status_code == 403 or not r.json().get("ok")

def test_operador_nao_gerencia(servidor, http_client_factory):
    c = http_client_factory()
    _login(c, "<login_operador_seed>", "<senha>")
    r = c.post("/api/admin/perfis", json={"nome": "X", "base": "operador", "modulos": []})
    assert r.status_code == 403
```
> Ajustar logins/senhas para as credenciais do `seed`/DB de teste (ver `tests/conftest.py` fixture `seed` e `tests/test_multi_loja.py` para o padrão de login e2e).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_perfis_api_e2e.py -q`
Expected: FAIL (rotas inexistentes).

- [ ] **Step 3: Escrita ORM em `perfil_store.py`**

Adicionar:
```python
import mod_perfis


def criar_perfil(db, loja_id, nome, base, modulos, capacidades=None):
    ok, err = mod_perfis.validar_nome(nome)
    if not ok: return None, err
    ok, err = mod_perfis.validar_base(base)
    if not ok: return None, err
    ok, err = mod_perfis.validar_modulos(modulos)
    if not ok: return None, err
    ok, caps = mod_perfis.validar_capacidades(capacidades)
    if not ok: return None, caps
    existentes = {p.slug for p in db.query(PerfilAcesso).all()}   # slug único GLOBAL
    slug = mod_perfis.gerar_slug(nome, existentes)
    p = PerfilAcesso(loja_id=loja_id, slug=slug, nome=nome.strip(), base=base,
                     modulos_json=json.dumps(list(modulos)),
                     capacidades_json=json.dumps(caps), sistema=0)
    db.add(p); db.commit()
    return p, ""


def editar_perfil(db, loja_id, slug, nome=None, modulos=None, capacidades=None):
    p = db.query(PerfilAcesso).filter_by(loja_id=loja_id, slug=slug).first()
    if not p: return None, "perfil não encontrado"
    if p.sistema: return None, "perfil de sistema não é editável"
    if nome is not None:
        ok, err = mod_perfis.validar_nome(nome)
        if not ok: return None, err
        p.nome = nome.strip()
    if modulos is not None:
        ok, err = mod_perfis.validar_modulos(modulos)
        if not ok: return None, err
        p.modulos_json = json.dumps(list(modulos))
    if capacidades is not None:
        ok, caps = mod_perfis.validar_capacidades(capacidades)
        if not ok: return None, caps
        p.capacidades_json = json.dumps(caps)
    db.commit()
    return p, ""
```

- [ ] **Step 4: Endpoints em `main.py`**

Reapontar `perfis-matriz` (`main.py:1031-1039`) para a matriz por loja:
```python
        elif path == "/api/admin/perfis-matriz":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            lid = usuario.get("loja_id")
            _m = perfis.matriz_loja(lid)
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})
```

Adicionar rota GET `/api/admin/perfis` (perto de `:1039`):
```python
        elif path == "/api/admin/perfis":
            usuario = get_usuario_sessao(self)
            if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_usuarios"):
                self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
            _m = perfis.matriz_loja(usuario.get("loja_id"))
            self.send_json({"ok": True, "perfis": _m["perfis"], "capacidades": _m["capacidades"],
                            "caps_selecionaveis": _m["caps_selecionaveis"],
                            "modulos_opcoes": mod_perfis_opcoes(),
                            "pode_editar": perfis.pode(usuario.get("nivel"), "gerir_perfis")})
```
onde `mod_perfis_opcoes()` (helper local em `main.py`, perto dos imports) devolve rótulos p/ o front:
```python
def mod_perfis_opcoes():
    import modulos, mod_perfis
    doms = [{"id": d["id"], "rotulo": d["rotulo"]} for d in modulos.dominios_com_rotulo()]
    return {"dominios": doms, "paineis": [{"id": "admin", "rotulo": "Painel Administração"},
                                          {"id": "config", "rotulo": "Painel Config"}]}
```

Adicionar POST `/api/admin/perfis` (no bloco POST, perto de `main.py:4123`):
```python
            if path == "/api/admin/perfis":
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    import perfil_store
                    p, err = perfil_store.criar_perfil(db, usuario.get("loja_id"),
                                req.get("nome", ""), req.get("base", ""), req.get("modulos", []),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}}, code=201)
                finally:
                    db.close()
                return
```

Adicionar PATCH `/api/admin/perfis/<slug>` (no bloco PATCH, perto de `main.py:6477`):
```python
            m_perfil = re.match(r"^/api/admin/perfis/([a-z0-9_]+)$", path)
            if m_perfil:
                usuario = get_usuario_sessao(self)
                if not usuario or not perfis.pode(usuario.get("nivel"), "gerir_perfis"):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    import perfil_store
                    p, err = perfil_store.editar_perfil(db, usuario.get("loja_id"), m_perfil.group(1),
                                nome=req.get("nome"), modulos=req.get("modulos"),
                                capacidades=req.get("capacidades"))
                    if not p:
                        self.send_json({"ok": False, "erro": err}, code=403); return
                    perfis.recarregar()
                    self.send_json({"ok": True, "perfil": {"slug": p.slug, "nome": p.nome}})
                finally:
                    db.close()
                return
```

Em `auth.py:_usuario_dict` (`:186`), adicionar:
```python
        "pode_gerir_perfis":  perfis.pode(u.nivel, "gerir_perfis"),
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_perfis_api_e2e.py -q`
Expected: PASS.

- [ ] **Step 6: Suíte cheia + Commit**

```bash
python3 -m pytest -q
git add main.py perfil_store.py auth.py tests/test_perfis_api_e2e.py
git commit -m "feat(perfis): CRUD /api/admin/perfis (Master) + perfis-matriz por loja"
```

### Task 8: Mapa de Funções — `Funcao.perfil_padrao` no serialize/aplicar + endpoint

**Files:**
- Modify: `mod_cadastro.py:184-203` (`funcao_serialize`, `funcao_aplicar`)
- Test: `tests/test_funcao_perfil_padrao.py` (Create)

- [ ] **Step 1: Teste que falha**

Create `tests/test_funcao_perfil_padrao.py`:
```python
import mod_cadastro


class _F:  # stub simples
    def __init__(self): self.loja_id=None; self.nome=""; self.status="ativo"; self.perfil_padrao=None


def test_serialize_inclui_perfil_padrao():
    f = _F(); f.id = 1; f.nome = "Consultor"; f.perfil_padrao = "operador"
    d = mod_cadastro.funcao_serialize(f)
    assert d["perfil_padrao"] == "operador"


def test_aplicar_seta_perfil_padrao():
    f = _F()
    mod_cadastro.funcao_aplicar(None, f, {"nome": "Gerente", "perfil_padrao": "gerencial"}, loja_id=1)
    assert f.perfil_padrao == "gerencial"
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_funcao_perfil_padrao.py -q`
Expected: FAIL (`perfil_padrao` ausente no dict).

- [ ] **Step 3: Editar `mod_cadastro.py:184-203`**

```python
def funcao_serialize(f, db=None):
    return {"id": f.id, "nome": f.nome, "status": f.status or "ativo",
            "perfil_padrao": getattr(f, "perfil_padrao", None)}


def funcao_aplicar(db, f, req, loja_id):
    if f.loja_id is None:
        f.loja_id = loja_id
    if _s(req.get("nome")):
        f.nome = _s(req.get("nome"))
    if "status" in req:
        f.status = (_s(req.get("status")) or "ativo")
    if "perfil_padrao" in req:
        f.perfil_padrao = _s(req.get("perfil_padrao")) or None
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_funcao_perfil_padrao.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mod_cadastro.py tests/test_funcao_perfil_padrao.py
git commit -m "feat(perfis): Função ganha perfil_padrao (Mapa de Funções)"
```

---

## FASE 4 — Step-up por senha (acesso fora do perfil)

### Task 9: Endpoint `/api/auth/step-up` + grant + log

**Files:**
- Modify: `auth_routes.py` (novo POST, perto de `/api/auth/liberar_impostos` `:194-214`), `main.py` (`_stepup` store + `_sem_acesso_modulo` `:7307`)
- Test: `tests/test_stepup_e2e.py` (Create)

**Design do grant:** `/api/auth/step-up` valida login+senha de um usuário cujo perfil INCLUI o recurso (`perfis.acessa_modulo`/`acessa_painel`), grava `LogAcessoDelegado`, e registra um grant em memória `_STEPUP_GRANTS[(token, recurso)] = expira_em` (TTL 30 min). `_sem_acesso_modulo` passa a liberar se houver grant válido para `(token, modulo)`.

- [ ] **Step 1: Teste que falha**

Create `tests/test_stepup_e2e.py`:
```python
def test_operador_stepup_financeiro(servidor, http_client_factory):
    c = http_client_factory()
    c.post("/api/auth/login", json={"login": "<login_operador>", "senha": "<senha>"})
    # sem grant → módulo financeiro barra
    r = c.get("/api/folha")
    assert r.status_code == 403 and r.json().get("precisa_stepup") == "folha"
    # step-up com senha de quem tem financeiro (master pdm2026)
    r = c.post("/api/auth/step-up", json={"recurso": "folha",
              "login_autorizador": "pdm2026", "senha_autorizador": "<senha_master>"})
    assert r.status_code == 200 and r.json()["ok"]
    # agora libera
    r = c.get("/api/folha")
    assert r.status_code != 403


def test_stepup_recusa_autorizador_sem_o_perfil(servidor, http_client_factory):
    c = http_client_factory()
    c.post("/api/auth/login", json={"login": "<login_operador>", "senha": "<senha>"})
    r = c.post("/api/auth/step-up", json={"recurso": "folha",
              "login_autorizador": "<outro_operador>", "senha_autorizador": "<senha>"})
    assert r.status_code == 403
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_stepup_e2e.py -q`
Expected: FAIL (rota inexistente / sem `precisa_stepup`).

- [ ] **Step 3: Store de grant + gate em `main.py`**

Perto do topo de `main.py` (junto de helpers como `_usuario_com_capacidade` `:278`):
```python
import time as _time
_STEPUP_GRANTS = {}   # {(token, recurso): expira_em_epoch}
_STEPUP_TTL = 30 * 60


def _stepup_conceder(token, recurso):
    _STEPUP_GRANTS[(token, recurso)] = _time.time() + _STEPUP_TTL


def _stepup_valido(token, recurso):
    exp = _STEPUP_GRANTS.get((token, recurso))
    if exp and exp > _time.time():
        return True
    if exp:
        _STEPUP_GRANTS.pop((token, recurso), None)
    return False
```

Ajustar `_sem_acesso_modulo` (`main.py:7307-7309`) para reconhecer grant (precisa do token; passe o handler):
```python
def _sem_acesso_modulo(usuario, modulo_id, handler=None):
    if perfis.acessa_modulo(usuario.get("nivel"), modulo_id):
        return False
    if handler is not None:
        from auth_routes import get_token_from_cookie
        token = get_token_from_cookie(handler.headers.get("Cookie", ""))
        if _stepup_valido(token, modulo_id):
            return False
    return True
```
Nos call-sites de módulo (`main.py:634` folha, `:2042` fiscal, `:331` financeiro dentro de `_contabil_ctx`), passar `handler=self` e, ao barrar, devolver `precisa_stepup`:
```python
        if _sem_acesso_modulo(usuario, "folha", handler=self):
            self.send_json({"ok": False, "erro": "Sem acesso ao módulo.",
                            "precisa_stepup": "folha"}, code=403); return
```
(análogo para `fiscal` e `financeiro`; `_contabil_ctx` já recebe `handler`.)

- [ ] **Step 4: Endpoint em `auth_routes.py`** (clonando o padrão `/api/auth/liberar_impostos` `:194-214`)

```python
    if path == "/api/auth/step-up":
        try:
            req = json.loads(body) if body else {}
        except Exception:
            _send_json(handler, {"ok": False, "erro": "JSON inválido."}, 400); return True
        cookie = handler.headers.get("Cookie", "")
        token  = get_token_from_cookie(cookie)
        solicitante = validar_sessao(token)
        if not solicitante:
            _send_json(handler, {"ok": False, "erro": "Sessão inválida."}, 401); return True
        recurso = (req.get("recurso") or "").strip()
        login   = (req.get("login_autorizador") or "").strip()
        senha   = req.get("senha_autorizador") or ""
        db = get_session()
        try:
            u = db.query(Usuario).filter_by(login=login).first()
            if not u or not u.ativo or not u.check_senha(senha):
                _send_json(handler, {"ok": False, "erro": "Usuário ou senha inválidos."}, 401); return True
            tem = (perfis.acessa_painel(u.nivel, recurso) if recurso in ("admin", "config")
                   else perfis.acessa_modulo(u.nivel, recurso))
            if not tem:
                _send_json(handler, {"ok": False, "erro": f"{u.nome} não tem acesso a este recurso."}, 403); return True
            db.add(LogAcessoDelegado(solicitante_id=solicitante["id"], autorizador_id=u.id,
                                     recurso=recurso))
            db.commit()
            import main as _main
            _main._stepup_conceder(token, recurso)
            _send_json(handler, {"ok": True, "autorizador": {"nome": u.nome}})
        finally:
            db.close()
        return True
```
Garantir imports no topo de `auth_routes.py`: `LogAcessoDelegado`, `perfis`.

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_stepup_e2e.py -q`
Expected: PASS.

- [ ] **Step 6: Suíte cheia + Commit**

```bash
python3 -m pytest -q
git add auth_routes.py main.py tests/test_stepup_e2e.py
git commit -m "feat(perfis): step-up por senha p/ acesso fora do perfil + log_acesso_delegado"
```

---

## FASE 5 — Frontend (`static/index.html`; sem teste JS → verificação manual + `node --check`)

> Após cada task desta fase: extrair o `<script>` e rodar `node --check` p/ sintaxe, depois Ctrl+F5 no navegador. Sem restart (a menos que também tenha mudado Python).

### Task 10: Painel "Perfis de Usuário" editável (Master) — lista + modal com 2 tabelas

**Files:** Modify `static/index.html` — `adminPerfisCarregar` (`:2699-2726`), aba em `:8193/8201`.

Novo shape do `GET /api/admin/perfis`: `perfis[].{slug,nome,base,sistema,modulos[],capacidades{cap:bool}}`, `capacidades` (metadados `CAPACIDADES` = rótulo/descrição/grupo), `caps_selecionaveis` (ordem), `modulos_opcoes.{dominios[],paineis[]}`, `pode_editar`.

- [ ] **Step 1 — Lista dos perfis existentes:** Reescrever `adminPerfisCarregar()` para renderizar a **tabela dos perfis da loja**: colunas Nome, Base, Tipo (Sistema/Personalizado), Módulos/Painéis (chips por rótulo de `modulos_opcoes`), Capacidades liberadas (chips das `capacidades` cujo valor é `true`, rótulo de `caps_selecionaveis`/`capacidades`). Se `pode_editar`: botão **“+ Novo perfil”** no topo e, nas linhas `sistema===false`, botão **“Editar”**. Linhas `sistema===true` aparecem como somente-leitura (sem Editar).
- [ ] **Step 2 — Modal com DUAS tabelas de seleção:** Adicionar `#modal-perfil` com:
  - Campo **Nome** e `<select>` **Base** (Master/Gerencial/Operador) — ao trocar a base, os toggles de capacidade recebem o preset da base (chamar o backend não é necessário: derive o preset chamando um mapa local `PRESET_BASE` espelhado de `perfis.PERFIS`, OU simplesmente pré-selecione a partir de `capacidades` do perfil sendo editado / da base ao criar).
  - **Tabela 1 — Módulos/Painéis acessíveis:** uma linha por item de `modulos_opcoes.dominios` + `modulos_opcoes.paineis`, com checkbox marcado se estiver no `modulos[]` do perfil. Agrupar visualmente (Operacionais / Domínio / Painéis).
  - **Tabela 2 — Capacidades finas (liberar/bloquear):** uma linha por `caps_selecionaveis`, mostrando rótulo+descrição de `capacidades[cap]`, com um **toggle** (checkbox) refletindo `capacidades[cap]` (efetivo). Marcado = liberado, desmarcado = bloqueado.
  - Funções JS: `abrirModalPerfil(ctx)` (ctx = null p/ novo, ou o objeto perfil p/ editar), `salvarPerfil()` que monta `{nome, base, modulos:[ids marcados], capacidades:{cap:bool de cada toggle}}` e faz `POST /api/admin/perfis` (novo) ou `PATCH /api/admin/perfis/<slug>` (editar). On-success: `showToast` + fechar + `adminPerfisCarregar()`. Bloquear abrir/salvar perfil `sistema`.
- [ ] **Step 3:** `node --check` no `<script>` extraído. Expected: OK.
- [ ] **Step 4:** Ctrl+F5; logar como `pdm2026` (Master) → Admin › Perfis de Usuário lista os 3 padrão; “+ Novo perfil” abre o modal com as duas tabelas; criar “Operador+” (base Operador, módulos = comercial+fiscal, capacidade `aprovar_financeiro` liberada) e conferir que aparece na lista com a capacidade liberada. Print.
- [ ] **Step 5: Commit**
```bash
git add static/index.html
git commit -m "feat(perfis): painel Perfis editável (Master) — lista + modal módulos & capacidades finas"
```

### Task 11: Mapa de Funções (Função → perfil_padrao)

**Files:** Modify `static/index.html` — tela da Tabela de Funções (Config) onde funções são cadastradas.

- [ ] **Step 1:** No formulário de Função, adicionar `<select>` “Perfil de acesso padrão” populado por `GET /api/admin/perfis` (`perfis[].{slug,nome}` da loja) + opção “— nenhum —”. Enviar `perfil_padrao` no POST de `/api/funcoes`. Exibir a coluna “Perfil padrão” na lista de funções (usar `f.perfil_padrao` → nome).
- [ ] **Step 2:** `node --check`. Ctrl+F5. Definir perfil padrão numa função e confirmar persistência (recarregar a lista). Print.
- [ ] **Step 3: Commit**
```bash
git add static/index.html
git commit -m "feat(perfis): Mapa de Funções — Função recebe perfil de acesso padrão"
```

### Task 12: Modal de step-up ao barrar módulo/painel

**Files:** Modify `static/index.html` — clonar o par `abrirModalLiberarImpostos`/`confirmarLiberarImpostos` (`:5490-5521`, HTML `:2090-2102`) para um modal genérico de step-up.

- [ ] **Step 1:** Criar `abrirModalStepUp(recurso)` → Promise; HTML `#modal-stepup` (login+senha+erro) que faz `POST /api/auth/step-up` com `{recurso, login_autorizador, senha_autorizador}`. On `ok`: `showToast('Acesso liberado por ' + d.autorizador.nome)`, resolve `true`.
- [ ] **Step 2:** No wrapper de `fetch` das telas de módulo (ou nos handlers que hoje mostram “Sem acesso.”), quando a resposta for `403` com `precisa_stepup`, chamar `await abrirModalStepUp(d.precisa_stepup)`; se `true`, refazer a requisição original (o grant server-side agora libera).
- [ ] **Step 3:** `node --check`. Ctrl+F5. Logar como Operador, tentar abrir Financeiro/Folha → modal pede senha; com senha do Master, libera e a tela carrega. Conferir `log_acesso_delegado` no banco. Print.
- [ ] **Step 4: Commit**
```bash
git add static/index.html
git commit -m "feat(perfis): modal de step-up por senha ao acessar módulo/painel fora do perfil"
```

---

## FASE 6 — Verificação integrada e fechamento

### Task 13: Verificação de aceitação (rev3 §9) + prints

- [ ] **Restart** do servidor (mudou Python) e **Ctrl+F5**.
- [ ] `python3 -m pytest -q` → verde.
- [ ] Rodar `python3 main.py`, e verificar em navegador:
  - **pdm2026 (Master):** VÊ os 3 perfis, cria um perfil custom e edita seus módulos. Print.
  - **Gerencial (lds2026):** não abre Admin nem Config (navs escondidas); abre operacionais + fiscal + financeiro. Print.
  - **Operador:** não abre Admin/Config/Financeiro; ao tentar Financeiro, aparece modal de step-up; com senha do Master, libera e grava log. Print.
- [ ] Conferir no banco: `SELECT recurso, solicitante_id, autorizador_id FROM log_acesso_delegado;` mostra a autorização.

### Task 14: Fechar a frente (padrão do projeto)

- [ ] **DEV_LOG.md:** nova `## Sessão N` — resumo do RESET (tabela `perfil_acesso` por loja, bases, migração `perfis_v4_2026`, seed, step-up, painel editável), decisões+porquê (base+módulos; plataforma fora da tabela), e atualizar a seção `## ⏸️ ESTADO ATUAL`.
- [ ] **Spec:** atualizar `docs/superpowers/specs/` refletindo o modelo implementado (referenciar o rev3 do `.docx`).
- [ ] **Commit** de docs:
```bash
git add DEV_LOG.md docs/superpowers/specs/
git commit -m "docs: RESET perfis configuráveis por loja (Sessão N) + ESTADO ATUAL"
```
- [ ] **Push:** `git push origin main` (se falhar por credencial, pedir ao usuário `!git push origin main`).
- [ ] **Re-ingerir o grafo MCP:** `ingerir` com `fonte: "all"` (ou `POST http://localhost:8767/ingest/all`).

---

## Self-Review (cobertura do spec)

- **Configurável no banco, por loja, 3 padrão (seed idempotente):** Tasks 2, 4 (tabela + seed por loja idempotente).
- **Perfil = nome + módulos/painéis + capacidades finas selecionáveis:** Task 2 (`modulos_json`, `capacidades_json`), Task 6 (validação de ids + de capacidades), Task 10 (modal com as 2 tabelas).
- **Painel Perfis de Usuário editável, só Master:** Tasks 6–7 (gate `gerir_perfis`), Task 10 (UI).
- **Perfil pelo login (Usuario.nivel → perfil da loja):** Task 3 (migração nivel→base) + Task 5 (registro por loja).
- **Mapa de Funções (Função → perfil default):** Tasks 2 (coluna), 8 (serialize/aplicar), 11 (UI).
- **Step-up por senha, reaproveitando autorização delegada + log:** Task 9 (backend, `LogAcessoDelegado`), Task 12 (modal).
- **Gates de módulo checam “o perfil inclui o módulo/painel?”:** Task 5 (`acessa_modulo/painel` do DB) + Task 9 (`_sem_acesso_modulo` + `precisa_stepup`).
- **Capacidades finas:** preset pela `base` (Task 1) + override por perfil em `capacidades_json` (Tasks 2/5/6/7/10); os 3 padrão nascem sem override → idênticos a hoje. `desconto_max` segue vindo da base (não editável nesta frente). Gates finos não foram afrouxados.
- **Futuro (perfis de rede) preparado, fora de escopo:** `perfil_acesso.loja_id` NOT NULL hoje; rede fica para painel de gestão de rede futuro (registrar no DEV_LOG).
- **Bug “Sem acesso” do pdm2026:** subsumido — Master (base master) tem `admin`+`config` no `modulos_json` e `gerir_usuarios/gerir_perfis` na base.

**Riscos anotados:**
- Slug global único (não por loja) para o registro slug→base funcionar sem propagar `loja_id` nos ~40 gates `pode()`. Sistema: `master/gerencial/operador` idênticos entre lojas (colisão benigna). Custom: `gerar_slug` garante unicidade global (Task 6 consulta TODOS os slugs).
- `perfis._carregar_registro()` importa `database.Session` — em testes, rebindar `database.Session` e chamar `perfis.recarregar()` (feito nos fixtures das Tasks 5/7/9).
- Gerencial passa a ter `gerir_usuarios=False` (antes True): é o alvo do rev3 (Gerencial sem painel Admin). Confirmado na matriz.
