# F4 Multi-tenant — Isolamento operacional — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar escopo por loja em todas as queries operacionais — listagens filtradas, acesso por id/`nome_safe` com 404 cross-loja, criação carimbando a loja do ator, e 403 para perfis administrativos.

**Architecture:** Helpers reutilizáveis (puros onde dá) aplicados endpoint a endpoint, espelhando o padrão da F2. A lógica de escopo fica testável (funções que **retornam valor**); o handler envia 403/404. Spec: `docs/superpowers/specs/2026-06-21-multitenant-f4-isolamento-design.md`.

**Tech Stack:** Python 3 (stdlib http.server), SQLAlchemy + sqlite3, pytest.

---

## File Structure

- **`mod_tenancy.py`** (modify): `escopo_operacional(ator)` (puro).
- **`main.py`** (modify): helpers `_obj_da_loja`, `_projeto_da_loja`, `_filtrar_projetos_por_loja`; aplicação do escopo nas listagens/GETs/mutações operacionais; carimbo de `loja_id` na criação (cliente/projeto/orçamento); escopo da lista de parceiros.
- **`database.py`** (modify): backfill defensivo em `_migrar_dados`.
- **`tests/test_isolamento_f4.py`** (create): testes de `escopo_operacional`, dos helpers de acesso (stub db), do backfill (temp db), e cenário 2-lojas.
- **`docs/USUARIOS.md`**, **`DEV_LOG.md`** (modify): documentação.

**Convenção dos helpers de acesso:** funções planas que **retornam** o objeto ou `None`/tupla; o handler decide a resposta. Isso as torna testáveis com stub de db (como `_loja_dict_para_contrato` na F3). O envio de 403/404 fica no handler (1-2 linhas) e é coberto por revisão + smoke de API.

---

## Task 1: `escopo_operacional` (puro, em `mod_tenancy.py`)

**Files:** Create `tests/test_isolamento_f4.py`; Modify `mod_tenancy.py`.

- [ ] **Step 1: Write the failing test** — criar `tests/test_isolamento_f4.py`:

```python
# tests/test_isolamento_f4.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_escopo_operacional_usuario_de_loja():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "consultor", "loja_id": 7, "rede_id": None})
    assert loja_id == 7 and err is None


def test_escopo_operacional_super_admin_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "super_admin", "loja_id": None, "rede_id": None})
    assert loja_id is None and err  # mensagem não-vazia


def test_escopo_operacional_admin_rede_sem_acesso():
    import mod_tenancy as mt
    loja_id, err = mt.escopo_operacional({"nivel": "admin_rede", "loja_id": None, "rede_id": 3})
    assert loja_id is None and err
```

- [ ] **Step 2: Run → fail** — `python3 -m pytest tests/test_isolamento_f4.py -v` (ImportError).

- [ ] **Step 3: Implement** — em `mod_tenancy.py`, ao final do bloco de escopo:

```python
def escopo_operacional(ator):
    """Decide o escopo de uma operação NA LOJA.

    Retorna (loja_id, None) quando o ator é usuário de loja (opera nela).
    Retorna (None, motivo) quando o ator NÃO tem acesso operacional —
    super_admin/admin_rede têm loja_id None (administram a estrutura, não operam).
    Puro: a rota traduz o motivo em 403.
    """
    loja_id = ator.get("loja_id")
    if loja_id is None:
        return (None, "Sem acesso operacional (perfil administrativo ou sem loja).")
    return (loja_id, None)
```

- [ ] **Step 4: Run → pass** (3 testes).
- [ ] **Step 5: Commit** — `git add mod_tenancy.py tests/test_isolamento_f4.py && git commit -m "feat(tenancy): escopo_operacional (F4)"`

---

## Task 2: Helpers de acesso por id/projeto (em `main.py`)

**Files:** Modify `main.py`; Modify `tests/test_isolamento_f4.py`.

- [ ] **Step 1: Write the failing test** — append:

```python
def test_obj_da_loja():
    import main
    class _Obj:
        def __init__(self, loja_id): self.loja_id = loja_id
    class _DB:
        def __init__(self, obj): self._obj = obj
        def get(self, model, pk): return self._obj
    assert main._obj_da_loja(_DB(_Obj(1)), object, 5, 1).loja_id == 1   # mesma loja
    assert main._obj_da_loja(_DB(_Obj(2)), object, 5, 1) is None        # outra loja
    assert main._obj_da_loja(_DB(None), object, 5, 1) is None           # inexistente
    assert main._obj_da_loja(_DB(_Obj(1)), object, None, 1) is None     # pk vazio


def test_projeto_da_loja():
    import main
    class _Proj:
        def __init__(self, loja_id): self.loja_id = loja_id
    class _DB:
        def __init__(self, p): self._p = p
        def get(self, model, pk): return self._p
    assert main._projeto_da_loja(_DB(_Proj(1)), "casa_a", 1).loja_id == 1
    assert main._projeto_da_loja(_DB(_Proj(2)), "casa_a", 1) is None
    assert main._projeto_da_loja(_DB(None), "casa_a", 1) is None
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — em `main.py`, junto de `_loja_dict_para_contrato` (~line 3679):

```python
def _obj_da_loja(db, Model, pk, loja_id):
    """Retorna o objeto se existir E pertencer à loja `loja_id`; senão None.
    None cobre 'não existe' e 'é de outra loja' (o handler responde 404 nos dois)."""
    if pk is None:
        return None
    obj = db.get(Model, pk)
    if obj is None or getattr(obj, "loja_id", None) != loja_id:
        return None
    return obj


def _projeto_da_loja(db, nome_safe, loja_id):
    """Retorna o projetos_meta (PK = nome_safe) se pertencer à loja; senão None (=> 404).
    É o ponto de escopo das entidades 'por projeto' (pool/medição/ciclo/contrato)."""
    if not nome_safe:
        return None
    p = db.get(Projeto, nome_safe)
    if p is None or getattr(p, "loja_id", None) != loja_id:
        return None
    return p
```

(Confirme que `Projeto` é o model de `projetos_meta` com PK `nome_safe` — já usado em `db.get(Projeto, nome_safe)` no arquivo.)

- [ ] **Step 4: Run → pass.**
- [ ] **Step 5: Commit** — `git add main.py tests/test_isolamento_f4.py && git commit -m "feat(isolamento): helpers _obj_da_loja/_projeto_da_loja (F4)"`

---

## Task 3: Backfill defensivo em `_migrar_dados`

**Files:** Modify `database.py`; Modify `tests/test_isolamento_f4.py`.

- [ ] **Step 1: Write the failing test** — append (segue o padrão de `tests/test_tenancy_colunas.py`):

```python
import sqlite3
import database


def test_backfill_loja_id_operacional(tmp_path, monkeypatch):
    db = str(tmp_path / "f4.db")
    conn = sqlite3.connect(db)
    for t in ("clientes", "projetos_meta", "orcamentos", "contratos"):
        conn.execute(f"CREATE TABLE {t} (id INTEGER PRIMARY KEY, loja_id INTEGER)")
        conn.execute(f"INSERT INTO {t}(loja_id) VALUES (NULL)")
    conn.commit(); conn.close()
    monkeypatch.setattr(database, "DB_PATH", db)
    database._backfill_loja_operacional()      # função nova, idempotente
    database._backfill_loja_operacional()      # 2ª vez não muda nada
    conn = sqlite3.connect(db)
    for t in ("clientes", "projetos_meta", "orcamentos", "contratos"):
        nul = conn.execute(f"SELECT COUNT(*) FROM {t} WHERE loja_id IS NULL").fetchone()[0]
        assert nul == 0
    conn.close()
```

- [ ] **Step 2: Run → fail.**
- [ ] **Step 3: Implement** — em `database.py`, adicionar a função e chamá-la de `_migrar_dados` (`:687`):

```python
def _backfill_loja_operacional():
    """F4: nenhuma linha operacional pode ficar sem loja (senão some no filtro de escopo).
    Backfill defensivo NULL -> loja-semente (id=1). Idempotente."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for tbl in ("clientes", "projetos_meta", "orcamentos", "contratos"):
            cur.execute(f"UPDATE {tbl} SET loja_id=1 WHERE loja_id IS NULL")
        conn.commit()
    finally:
        conn.close()
```

E dentro de `_migrar_dados()` (após as migrações existentes), acrescentar a chamada:
```python
    _backfill_loja_operacional()
```

- [ ] **Step 4: Run → pass.** Depois `python3 -m pytest -q` (suíte inteira verde).
- [ ] **Step 5: Commit** — `git add database.py tests/test_isolamento_f4.py && git commit -m "feat(db): backfill defensivo de loja_id operacional (F4)"`

---

## Padrão de aplicação (vale para as Tasks 4–9)

No topo de cada handler operacional, **após** obter `usuario` e a sessão de db:
```python
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403)
                    return
```
- **Listagem (entidade com loja_id próprio):** `.filter(Model.loja_id == loja_id)` na query.
- **Acesso por id:** `obj = _obj_da_loja(db, Model, int(pk), loja_id)` → `if obj is None: self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return`.
- **Acesso por projeto (`nome_safe`):** `proj = _projeto_da_loja(db, nome_safe, loja_id)` → `if proj is None: 404`.
- **Criação:** setar `loja_id=loja_id` no objeto novo.

Cada task abaixo: READ os handlers citados (ancore por conteúdo; números de linha são do mapa pós-F3 e podem variar), aplique o padrão, rode `pytest -q`, smoke manual quando indicado, commit. **Indentação exata** (handlers aninhados).

---

## Task 4: Clientes

**Endpoints (route — linha aprox.):** `GET /api/clientes` (list, 357-396); `GET /api/clientes/<id>` (639-652); `GET /api/clientes/<id>/projetos` (669-682); `GET /api/clientes/<id>/briefing` (324-338); `POST /api/clientes` (create, 1313-1366); `POST /api/clientes/<id>/editar` (1493-1524).

- [ ] **Step 1:** Aplicar o padrão:
  - List: guard 403 + `.filter(Cliente.loja_id == loja_id)` na query (`db.query(Cliente)...`).
  - `<id>` (GET/editar/briefing/projetos): `c = _obj_da_loja(db, Cliente, int(id), loja_id)`; `if c is None: 404`. Para `<id>/projetos`, depois de validar o cliente, a lista de projetos dele já fica restrita à loja (mesmo cliente). Para `<id>/briefing`, idem (valida o cliente primeiro).
  - Create (`POST /api/clientes`, ~1330): `c = Cliente(..., loja_id=loja_id)` (setar a coluna).
  - Editar (~1498): trocar `db.get(Cliente, id)` por `_obj_da_loja(...)`.
- [ ] **Step 2: Test** — append em `tests/test_isolamento_f4.py` um teste de `_obj_da_loja` aplicado a um `Cliente`-like já cobre a lógica; o filtro de listagem e o carimbo são verificados por smoke de API (ver Task 10) — **documentar** que a fiação do handler é coberta por smoke.
- [ ] **Step 3:** `python3 -m pytest -q` verde; `python3 -c "import main"` OK.
- [ ] **Step 4: Commit** — `git commit -am "feat(isolamento): escopo de clientes (F4)"`

---

## Task 5: Projetos (inclui a lista baseada em storage)

**Endpoints:** `GET /projetos` (306-310); `GET /projetos/buscar` (312-322); `GET /projetos/<nome_safe>` (628-637); `GET /api/projetos/<nome>/ciclo` (706-748); `GET /projetos/<nome>/orcamentos` (610-626); `POST /projetos/novo` (create, 1182-1310); `POST /api/projetos/<nome>/parametros` (1597-1622).

- [ ] **Step 1: Filtro da lista (storage)** — adicionar helper em `main.py`:
```python
def _filtrar_projetos_por_loja(projetos, db, loja_id):
    """Mantém só os projetos cujo projetos_meta.loja_id == loja_id (lista vem do storage)."""
    nomes = [p.get("nome_safe") for p in projetos if p.get("nome_safe")]
    if not nomes:
        return projetos
    permitidos = {r[0] for r in db.query(Projeto.nome_safe)
                  .filter(Projeto.nome_safe.in_(nomes), Projeto.loja_id == loja_id).all()}
    return [p for p in projetos if p.get("nome_safe") in permitidos]
```
  Aplicar nos handlers `/projetos` e `/projetos/buscar`: obter `ator`/`loja_id` (403 se admin), abrir sessão, e `projetos = _filtrar_projetos_por_loja(projetos, db, loja_id)` **antes** de enriquecer/serializar. (No `/buscar`, filtrar `locais`; os resultados Omie ficam como estão — são externos.)
- [ ] **Step 2: GET por nome_safe e "por projeto"** — `/projetos/<nome_safe>`, `/ciclo`, `/orcamentos`: guard 403 + `if _projeto_da_loja(db, nome_safe, loja_id) is None: 404` antes de carregar.
- [ ] **Step 3: Criar** — `POST /projetos/novo` (~1241-1269): obter `loja_id` (403 se admin) e setar `loja_id=loja_id` na linha `projetos_meta` criada. **Parâmetros** (~1610): trocar `db.get(Projeto, nome_safe)` por `_projeto_da_loja(...)` (404 cross-loja).
- [ ] **Step 4: Test** — adicionar teste de `_filtrar_projetos_por_loja` com um stub de db cujo `query(...).filter(...).all()` devolve um subconjunto fixo (stub encadeável), ou cobrir por smoke; documentar. `pytest -q` verde.
- [ ] **Step 5: Commit** — `git commit -am "feat(isolamento): escopo de projetos + lista por loja (F4)"`

---

## Task 6: Orçamentos

**Endpoints:** `GET /orcamentos/<oid>/ambientes` (575-608); `POST /api/orcamentos/<oid>/margens` (1624-1656); `PUT /projetos/<nome>/orcamentos/<oid>` rename (2882-2917); `POST /orcamentos/<oid>/ambientes/<pid>` add (2119-2159); `POST /orcamentos/<oid>/ambientes/<pid>/remover` (2075-2117); `POST /projetos/<nome>/orcamentos` create (1661-1717).

- [ ] **Step 1:** Para todo acesso por `<oid>`: guard 403 + `orc = _obj_da_loja(db, Orcamento, int(oid), loja_id)` → `if orc is None: 404`. Substitui os `db.get(Orcamento, oid)` sem checagem.
- [ ] **Step 2:** Add/remove ambiente (`<oid>/ambientes/<pid>`): além do orçamento da loja, validar que o `PoolAmbiente pid` pertence ao mesmo projeto/orçamento (já existe vínculo por `projeto_id`); negar 404 se não.
- [ ] **Step 3:** Create (`POST /projetos/<nome>/orcamentos`, ~1697): validar o projeto via `_projeto_da_loja` e setar `loja_id=loja_id` no `Orcamento(...)`.
- [ ] **Step 4:** `pytest -q` verde; commit `feat(isolamento): escopo de orcamentos (F4)`.

---

## Task 7: Contratos

**Endpoints:** `GET /api/projetos/<nome>/contrato` (836-860); `GET .../contrato/pdf` (804-834); `POST .../contrato/assinar` (2452-2531); `POST .../contrato/editar` (2533-2607). (Gerar já resolve a loja na F3.)

- [ ] **Step 1:** Em cada um: guard 403 + `if _projeto_da_loja(db, nome_safe, loja_id) is None: 404` antes de buscar o contrato por `projeto_nome`. (Contrato é sempre acessado por `nome_safe` do projeto, então o escopo do projeto cobre.)
- [ ] **Step 2:** No gerar (Site #1/#2 da F3), acrescentar o mesmo guard de projeto (defesa em profundidade — o consultor não deve gerar contrato de projeto de outra loja). Apenas o guard; a resolução de loja da F3 permanece.
- [ ] **Step 3:** `pytest -q` verde; commit `feat(isolamento): escopo de contratos (F4)`.

---

## Task 8: Pool / Medição / Ciclo (transitivos por projeto)

**Endpoints:** Pool: `/projetos/<nome>/pool` get (543-573) + upload (1720-1873); `pool/<pid>/sobrescrever` (1875-1933), `nova-versao` (1935-1988), `renomear` (1990-2029), `criar_forcado` (2030-2072). Medição: `/api/projetos/<nome>/medicao` get (781-803), `arquivo/...` (755-780), `solicitacao` (2773-2800), `parecer` (2802-2839), `decisao-reprovado` (2841-2871). Ciclo: `desfazer_aprovacao` (2349-2389), `<codigo>/reabrir` (2391-2450).

- [ ] **Step 1:** Todos são chaveados por `nome_safe` do projeto → guard 403 + `if _projeto_da_loja(db, nome_safe, loja_id) is None: 404` no topo.
- [ ] **Step 2:** Para os que recebem um **sub-id próprio** (`pool/<pid>/...`): além do projeto da loja, validar que o `PoolAmbiente pid` pertence a esse `projeto_id` (`pa.projeto_id == nome_safe`); senão 404. Evita agir num pool de outro projeto/loja via id.
- [ ] **Step 3:** `pytest -q` verde; commit `feat(isolamento): escopo de pool/medicao/ciclo (F4)`.

---

## Task 9: Parceiros (listagem)

**Endpoints:** `GET /api/parceiros` (398-414); `GET /api/parceiros/<id>` (654-667). (Mutações já escopadas pela F2.)

- [ ] **Step 1:** Listagem: guard 403 + filtrar para os parceiros visíveis ao ator — abrangência `'loja'` com vínculo em `parceiro_lojas` para `loja_id`, ou abrangência `'rede'` cuja `rede_id` == rede da loja do ator (obter via `db.get(Loja, loja_id).rede_id`). Reusar a lógica de visibilidade da F2 (`pode_ver_loja`/`_aplicar_abrangencia_parceiro`) onde fizer sentido; implementar a query/filtro.
- [ ] **Step 2:** `GET /api/parceiros/<id>`: validar visibilidade do parceiro para o ator; senão 404.
- [ ] **Step 3:** `pytest -q` verde; commit `feat(isolamento): escopo da lista de parceiros (F4)`.

> Baixo risco hoje (tabela `parceiros` vazia); ainda assim implementar para consistência.

---

## Task 10: Verificação 2-lojas + DEV_LOG + fechamento

**Files:** Modify `DEV_LOG.md`, `docs/USUARIOS.md`; `tests/test_isolamento_f4.py`.

- [ ] **Step 1: Cenário 2-lojas (stub/temp db onde der)** — adicionar testes que montem dois objetos (loja A=1, B=2) e afirmem via os helpers: `_obj_da_loja(db_B, Model, pk, 1) is None` (A não acessa B), `_projeto_da_loja` idem, e `escopo_operacional` 403 para admin. (A fiação completa dos handlers — filtro de listagem, carimbo, 404/403 reais — é coberta pelo smoke de API abaixo, pois o app usa `BaseHTTPRequestHandler` sem testes de handler.)
- [ ] **Step 2: Smoke de API (servidor real)** — roteiro em `DEV_LOG`/doc: criar uma 2ª loja (id=2) + usuário operacional; logar como cada um e confirmar: listas isoladas; `GET` por id/`nome_safe` cruzado → **404**; criar cliente/projeto/orçamento na Loja A grava `loja_id=A`; super_admin → **403** em endpoint operacional. Registrar como **pendente** se não puder rodar no ambiente, com checklist (como na F3).
- [ ] **Step 3:** `python3 -m pytest -q` — toda a suíte verde (195 + novos).
- [ ] **Step 4:** Atualizar `docs/USUARIOS.md` (operacional isolado por loja) e `DEV_LOG.md` (sessão F4).
- [ ] **Step 5: Commit** — `git commit -am "docs: F4 isolamento operacional (sessao) + verificacao"`

---

## Self-Review

**1. Spec coverage:**
- Decisão 1 (cada loja só o seu; admin sem operacional) → `escopo_operacional` (Task 1) + guard 403 em todo handler (Tasks 4–9). ✓
- Decisão 2 (tudo numa fase: carimbo + filtro + anti-IDOR) → carimbo (Tasks 4/5/6), filtro (Tasks 4/5/9), IDOR por-id/projeto (Tasks 4–9). ✓
- Decisão 3 (cross-loja → 404) → `_obj_da_loja`/`_projeto_da_loja` retornam None → handler 404 (Tasks 2,4–9). ✓
- §5 lista de projetos via `projetos_meta` → Task 5 `_filtrar_projetos_por_loja`. ✓
- §6 backfill defensivo → Task 3. ✓
- §8 parceiros listagem → Task 9. ✓
- Riscos: sub-id transitivo validado contra o projeto → Tasks 6/8 Step 2. ✓

**2. Placeholder scan:** sem "TBD/TODO"; cada passo traz código/endpoints/comandos reais. As tasks de aplicação listam endpoints exatos + o helper a chamar (a inserção é o guard, que está especificado em "Padrão de aplicação").

**3. Type consistency:** `escopo_operacional(ator)->(loja_id|None, erro|None)`; `_obj_da_loja(db, Model, pk, loja_id)->obj|None`; `_projeto_da_loja(db, nome_safe, loja_id)->proj|None`; `_filtrar_projetos_por_loja(projetos, db, loja_id)->list`; `_backfill_loja_operacional()`. Nomes idênticos entre tasks. `Projeto` = model de `projetos_meta` (PK `nome_safe`).

> **Nota de testabilidade:** a fiação dos handlers HTTP não tem testes unitários (o app usa `BaseHTTPRequestHandler` cru; o repo nunca testou handlers). Cobertura automatizada concentra-se nas funções puras/helpers (stub/temp db); o resto é verificado por smoke de API (Task 10), declarado explicitamente — sem fingir cobertura que não existe.

---

## Execution Handoff

Após salvar o plano, oferecer execução: (1) Subagent-Driven (recomendado) ou (2) Inline.
