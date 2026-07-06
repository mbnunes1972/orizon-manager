# Etapas: Ordem + Gating Sequencial — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inverter Briefing ↔ Criação do projeto, tornar o ciclo de etapas sequencial (gating rígido) e permitir reabertura em cascata autorizada por gerente e auditada.

**Architecture:** Um novo módulo `mod_ciclo.py` concentra a ordem canônica e as regras de gating como funções puras (testáveis). O backend (`main.py`) valida o gating no `PATCH /ciclo`, ganha um endpoint `reabrir` e uma migração de dados idempotente (troca 2↔3). O frontend (`static/index.html`) reordena as etapas, mostra cadeado nas bloqueadas e abre um modal de autorização gerencial para a reabertura. Auditoria numa nova tabela `log_acoes_gerenciais`.

**Tech Stack:** Python 3 + SQLAlchemy + sqlite3 (migração raw), `http.server` (sem framework), pytest, HTML/CSS/JS vanilla.

**Spec:** `docs/superpowers/specs/2026-06-17-etapas-ordem-gating-design.md`

**Branch:** `feat/etapas-ordem-gating` (já criada).

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `mod_ciclo.py` (novo) | Ordem canônica das etapas + helpers puros de gating/cascata. Fonte única da verdade no backend. |
| `tests/test_ciclo.py` (novo) | Testes unitários de `mod_ciclo` e da troca 2↔3 de migração. |
| `database.py` (mod.) | Nova tabela `LogAcaoGerencial`; função de migração de dados `_run_migracoes()` + chamada em `init_db`. |
| `main.py` (mod.) | Gating no `PATCH /ciclo`; ordenação correta no `GET /ciclo`; endpoint `POST .../ciclo/<cod>/reabrir`; ajuste do auto-marcar na criação; briefing marca `"3"`. |
| `static/index.html` (mod.) | `ETAPAS_CICLO` reordenado; estado `bloqueado` + 🔒 em `renderCiclo`; modal de autorização + chamada de reabertura. |

---

## Task 1: `mod_ciclo.py` — ordem canônica e helpers de gating

**Files:**
- Create: `mod_ciclo.py`
- Test: `tests/test_ciclo.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ciclo.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import mod_ciclo as mc


def test_etapa_anterior():
    assert mc.etapa_anterior("4") == "3"
    assert mc.etapa_anterior("2") == "1"
    assert mc.etapa_anterior("1") is None
    # sub-etapas não fazem parte da cadeia principal
    assert mc.etapa_anterior("11a") is None


def test_ordenar_codigos_numerico_com_subetapas():
    entrada = ["10", "2", "11a", "11", "3", "1", "17a", "17"]
    assert mc.ordenar_codigos(entrada) == ["1", "2", "3", "10", "11", "11a", "17", "17a"]


def test_pode_avancar_principal_exige_anterior_concluida():
    assert mc.pode_avancar("4", {"3": "concluido"}) is True
    assert mc.pode_avancar("4", {"3": "pendente"}) is False
    assert mc.pode_avancar("4", {}) is False            # anterior ausente = não concluída


def test_pode_avancar_primeira_etapa_sempre_liberada():
    assert mc.pode_avancar("1", {}) is True


def test_pode_avancar_subetapa_sempre_livre():
    assert mc.pode_avancar("11b", {}) is True


def test_codigos_a_resetar_inclui_alvo_e_posteriores_e_subs():
    existentes = ["1", "2", "3", "4", "5", "11", "11a", "11b"]
    resetar = mc.codigos_a_resetar("3", existentes)
    assert set(resetar) == {"3", "4", "5", "11", "11a", "11b"}
    # etapas anteriores ao alvo permanecem fora
    assert "1" not in resetar and "2" not in resetar


def test_reabertura_bloqueada_por_contrato():
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "assinado") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "vigente") is True
    assert mc.reabertura_bloqueada_por_contrato(["3", "7"], "rascunho") is False
    assert mc.reabertura_bloqueada_por_contrato(["8", "9"], "assinado") is False  # 7 fora do reset
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ciclo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'mod_ciclo'`

- [ ] **Step 3: Implement `mod_ciclo.py`**

Create `mod_ciclo.py`:

```python
"""
mod_ciclo.py — Ordem canônica das etapas do ciclo e regras de gating sequencial.

Fonte única da verdade (backend) para "qual é a etapa anterior" e se uma etapa
pode avançar. Espelha o ETAPAS_CICLO do frontend (static/index.html).
"""

# Etapas PRINCIPAIS, na ordem. Sub-etapas ("11a".."11e", "17a") NÃO entram aqui
# — elas são livres dentro do pai.
ETAPAS_PRINCIPAIS = [
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
]

ETAPA_NOME = {
    "1": "Captação do cliente",
    "2": "Criação do projeto",
    "3": "Briefing",
    "4": "Primeiro orçamento",
    "5": "Revisão de projeto",
    "6": "Aprovação do orçamento pelo cliente",
    "7": "Contrato",
    "8": "Aprovação financeira I",
    "9": "Solicitação de medição",
    "10": "Planta de pontos medidos",
    "11": "Projeto executivo",
    "12": "Implantação do pedido",
    "13": "Produção",
    "14": "Entrega no depósito",
    "15": "Emissão da NFe do cliente",
    "16": "Entrega no cliente",
    "17": "Montagem",
    "18": "Assistência pós Montagem",
    "19": "Vistoria final",
    "20": "Aprovação final",
}

STATUS_CONCLUIDO = "concluido"


def _parse_codigo(codigo):
    """'11a' -> (11, 'a'); '2' -> (2, ''). Para ordenação e agrupamento por pai."""
    num, suf = "", ""
    for ch in str(codigo):
        if ch.isdigit() and not suf:
            num += ch
        else:
            suf += ch
    return (int(num) if num else 0, suf)


def is_principal(codigo):
    return codigo in ETAPAS_PRINCIPAIS


def etapa_anterior(codigo):
    """Código da etapa principal imediatamente anterior, ou None."""
    if codigo not in ETAPAS_PRINCIPAIS:
        return None
    i = ETAPAS_PRINCIPAIS.index(codigo)
    return ETAPAS_PRINCIPAIS[i - 1] if i > 0 else None


def ordenar_codigos(codigos):
    """Ordena códigos numericamente, com sub-etapas logo após o pai."""
    return sorted(codigos, key=_parse_codigo)


def chave_ordenacao(codigo):
    """Key para sorted() quando se ordena objetos por etapa_codigo."""
    return _parse_codigo(codigo)


def pode_avancar(codigo, status_por_codigo):
    """
    True se a etapa pode sair de 'pendente' (iniciar/concluir).
    Sub-etapas são sempre livres. Principais exigem a anterior concluída.
    status_por_codigo: dict {codigo: status}.
    """
    if codigo not in ETAPAS_PRINCIPAIS:
        return True
    ant = etapa_anterior(codigo)
    if ant is None:
        return True
    return status_por_codigo.get(ant) == STATUS_CONCLUIDO


def codigos_a_resetar(codigo_alvo, codigos_existentes):
    """
    Reabertura em cascata: o próprio alvo + todos posteriores (principais e
    suas sub-etapas). Qualquer código cujo (num, sufixo) >= (num, sufixo) do alvo.
    """
    alvo = _parse_codigo(codigo_alvo)
    return [c for c in codigos_existentes if _parse_codigo(c) >= alvo]


def reabertura_bloqueada_por_contrato(codigos_a_resetar_lista, contrato_status):
    """True se a cascata desfaria a etapa 7 (Contrato) com contrato já firmado."""
    return "7" in set(codigos_a_resetar_lista) and contrato_status in ("assinado", "vigente")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ciclo.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add mod_ciclo.py tests/test_ciclo.py
git commit -m "feat(ciclo): mod_ciclo com ordem canonica e helpers de gating (TDD)"
```

---

## Task 2: Migração de dados — troca de códigos 2↔3 (idempotente)

**Files:**
- Modify: `database.py` (adicionar `_run_migracoes`, chamar em `init_db` na linha 308-310)
- Test: `tests/test_ciclo.py` (acrescentar testes de migração)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_ciclo.py`:

```python
import sqlite3
import database


def _mk_ciclo_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE ciclo_etapas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projeto_nome TEXT, etapa_codigo TEXT, status TEXT)""")
    # Projeto com a ordem ANTIGA: "2"=Briefing, "3"=Criacao
    conn.executemany(
        "INSERT INTO ciclo_etapas(projeto_nome, etapa_codigo, status) VALUES(?,?,?)",
        [("P", "1", "concluido"), ("P", "2", "concluido"), ("P", "3", "concluido"),
         ("P", "4", "pendente")],
    )
    conn.commit()
    return conn


def _codigos(conn):
    cur = conn.execute("SELECT etapa_codigo FROM ciclo_etapas ORDER BY etapa_codigo")
    return [r[0] for r in cur.fetchall()]


def test_swap_2_3_troca_os_codigos():
    conn = _mk_ciclo_db()
    database._run_migracoes(conn)
    # apos a troca os 4 codigos continuam {1,2,3,4} (apenas relabel de 2<->3)
    assert _codigos(conn) == ["1", "2", "3", "4"]
    # confirma que houve a inversao: a linha que era "2" agora e "3" e vice-versa
    # (todas eram 'concluido', entao validamos via contagem e marcador)
    cur = conn.execute("SELECT id FROM schema_migrations WHERE id='etapas_swap_2_3'")
    assert cur.fetchone() is not None


def test_swap_2_3_idempotente():
    conn = _mk_ciclo_db()
    database._run_migracoes(conn)
    database._run_migracoes(conn)   # roda 2x — não pode inverter de volta
    assert _codigos(conn) == ["1", "2", "3", "4"]
    # so existe UM registro da migracao
    cur = conn.execute("SELECT COUNT(*) FROM schema_migrations WHERE id='etapas_swap_2_3'")
    assert cur.fetchone()[0] == 1
```

Para validar a inversão de fato (não só a contagem), **adicione também** este teste, que usa o `status` como marcador para provar que o conteúdo de "2" e "3" foi de fato trocado:

```python
def test_swap_2_3_inverte_conteudo():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE ciclo_etapas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        projeto_nome TEXT, etapa_codigo TEXT, status TEXT)""")
    # status serve de marcador: 2->"era_briefing", 3->"era_criacao"
    conn.executemany(
        "INSERT INTO ciclo_etapas(projeto_nome, etapa_codigo, status) VALUES(?,?,?)",
        [("P", "2", "era_briefing"), ("P", "3", "era_criacao")],
    )
    conn.commit()
    database._run_migracoes(conn)
    cur = conn.execute("SELECT etapa_codigo, status FROM ciclo_etapas ORDER BY etapa_codigo")
    pares = dict(cur.fetchall())
    assert pares["2"] == "era_criacao"   # o que era 3 (criacao) agora e 2
    assert pares["3"] == "era_briefing"  # o que era 2 (briefing) agora e 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ciclo.py -k swap -v`
Expected: FAIL with `AttributeError: module 'database' has no attribute '_run_migracoes'`

- [ ] **Step 3: Implement the migration in `database.py`**

Add these two functions right **after** `_migrar_colunas()` (i.e., after line 383):

```python
def _run_migracoes(conn):
    """Migrações de DADOS (não de schema), idempotentes, rastreadas em schema_migrations.
    Recebe uma conexão sqlite3 (facilita teste com :memory:)."""
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
        id          TEXT PRIMARY KEY,
        aplicada_em DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("SELECT id FROM schema_migrations")
    aplicadas = {r[0] for r in cur.fetchall()}

    # 2026-06-17: trocar etapa_codigo 2<->3 (Briefing <-> Criação do projeto).
    # A troca direta colidiria com UNIQUE(projeto_nome, etapa_codigo); usa código temporário.
    if "etapas_swap_2_3" not in aplicadas:
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='_swap2' WHERE etapa_codigo='2'")
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='2'      WHERE etapa_codigo='3'")
        cur.execute("UPDATE ciclo_etapas SET etapa_codigo='3'      WHERE etapa_codigo='_swap2'")
        cur.execute("INSERT INTO schema_migrations(id) VALUES('etapas_swap_2_3')")

    conn.commit()


def _migrar_dados():
    """Abre a conexão real e roda as migrações de dados idempotentes."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    try:
        _run_migracoes(conn)
    except Exception:
        pass
    finally:
        conn.close()
```

Then update `init_db()` (lines 308-310) to call it:

```python
def init_db():
    Base.metadata.create_all(ENGINE)
    _migrar_colunas()
    _migrar_dados()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_ciclo.py -v`
Expected: PASS (all, including swap tests)

- [ ] **Step 5: Apply the migration to the real DB and verify**

Run: `python -c "import database; database.init_db(); print('migrado')"`
Then verify the swap landed:
Run: `python -c "import sqlite3; c=sqlite3.connect('omie.db'); print(c.execute(\"SELECT id FROM schema_migrations\").fetchall())"`
Expected: contains `('etapas_swap_2_3',)`

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_ciclo.py omie.db
git commit -m "feat(ciclo): migracao idempotente troca codigos 2<->3 (briefing/criacao)"
```

---

## Task 3: Backend — gating no `PATCH /ciclo` e ordenação correta no `GET /ciclo`

**Files:**
- Modify: `main.py` — import de `mod_ciclo`; ordenação em `main.py:541`; gating no handler `PATCH` em `main.py:2172-2188`

- [ ] **Step 1: Add the import**

No topo de `main.py`, junto aos demais imports de módulos locais (perto de `from mod_contrato import ...`, linha ~41), adicione:

```python
import mod_ciclo
```

- [ ] **Step 2: Fix ordering in `GET /ciclo`**

Em `main.py:541`, substitua:

```python
                    etapas_sorted = sorted(etapas, key=lambda e: e.etapa_codigo)
```

por:

```python
                    etapas_sorted = sorted(etapas, key=lambda e: mod_ciclo.chave_ordenacao(e.etapa_codigo))
```

- [ ] **Step 3: Add gating to `PATCH /ciclo/<codigo>`**

Em `main.py`, dentro do handler PATCH, logo **após** o bloco que obtém/cria `etapa` (após a linha 2177 `db.add(etapa)`) e **antes** de `if novo_status:` (linha 2178), insira a verificação de gating:

```python
                    # Gating sequencial: etapa principal só avança se a anterior está concluída.
                    if novo_status and novo_status != "pendente":
                        todas = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                        status_por_codigo = {e.etapa_codigo: e.status for e in todas}
                        status_por_codigo[etapa_cod] = etapa.status
                        if not mod_ciclo.pode_avancar(etapa_cod, status_por_codigo):
                            ant = mod_ciclo.etapa_anterior(etapa_cod)
                            nome_ant = mod_ciclo.ETAPA_NOME.get(ant, ant)
                            self.send_json({
                                "ok": False,
                                "erro": f"Conclua a etapa anterior ({nome_ant}) antes de iniciar esta.",
                            }, code=400)
                            return
```

- [ ] **Step 4: Manual verification (no HTTP test harness in this project)**

Inicie o servidor (`python main.py`) num projeto de teste cujo Briefing (`"3"`) esteja pendente e tente concluir a etapa 4 pela UI. Esperado: erro 400 "Conclua a etapa anterior (Briefing)…". A lógica `pode_avancar` em si já é coberta pelos testes da Task 1.

Smoke test rápido de import e ordenação:
Run: `python -c "import main; import mod_ciclo; print(mod_ciclo.chave_ordenacao('10') > mod_ciclo.chave_ordenacao('2'))"`
Expected: `True`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(ciclo): gating sequencial no PATCH /ciclo e ordenacao numerica no GET"
```

---

## Task 4: Backend — ajustar auto-marcar na criação + briefing marca "3"

**Files:**
- Modify: `main.py:1003` (loop de marcação na criação de projeto)
- Modify: `main.py:1166` (marcação do briefing)

- [ ] **Step 1: Não marcar Briefing como concluído ao criar projeto**

Em `main.py:1003`, substitua:

```python
                    for cod in ["1", "2", "3"]:
```

por:

```python
                    # Marca apenas Captação(1) e Criação do projeto(2). Briefing(3) fica
                    # pendente — vira a "etapa corrente" e deve ser preenchido (sub-projeto D).
                    for cod in ["1", "2"]:
```

- [ ] **Step 2: Briefing concluído marca etapa "3" (era "2")**

Em `main.py:1166`, substitua:

```python
                    _marcar_etapa_cliente(cliente_id, "2", db, usuario)
```

por:

```python
                    _marcar_etapa_cliente(cliente_id, "3", db, usuario)
```

- [ ] **Step 3: Verify no other literal etapa "2"/"3" references were missed**

Run: `python -X utf8 -c "import re; t=open('main.py',encoding='utf-8').read(); [print(i+1, l) for i,l in enumerate(t.splitlines()) if re.search(r'etapa_codigo=\"[23]\"|, \"[23]\",', l)]"`
Expected: revise cada ocorrência impressa e confirme que se refere à nova semântica (2=Criação, 3=Briefing). A linha 1859/1861 (`desfazer_aprovacao`, etapas "6"/"7") não é afetada.

- [ ] **Step 4: Smoke test**

Run: `python -c "import ast; ast.parse(open('main.py',encoding='utf-8').read()); print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(ciclo): criar projeto nao conclui Briefing; briefing marca etapa 3"
```

---

## Task 5: Backend — tabela de auditoria + endpoint de reabertura em cascata

**Files:**
- Modify: `database.py` (nova classe `LogAcaoGerencial` após `LogAutorizacao`, linha 81)
- Modify: `main.py` (import do modelo; novo handler POST `reabrir`)
- Test: já coberto por `tests/test_ciclo.py` (helpers `codigos_a_resetar` e `reabertura_bloqueada_por_contrato`, Task 1)

- [ ] **Step 1: Add the audit model**

Em `database.py`, logo **após** a classe `LogAutorizacao` (após a linha 81), adicione:

```python
class LogAcaoGerencial(Base):
    """Auditoria de ações destrutivas autorizadas por gerente (ex.: reabrir cascata)."""
    __tablename__ = "log_acoes_gerenciais"

    id             = Column(Integer,  primary_key=True, autoincrement=True)
    solicitante_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=True)
    autorizador_id = Column(Integer,  ForeignKey("usuarios.id"), nullable=False)
    acao           = Column(Text,     nullable=False)   # ex.: "reabrir_cascata"
    projeto_nome   = Column(Text,     nullable=True)
    etapa_alvo     = Column(Text,     nullable=True)
    contexto       = Column(Text,     nullable=True)    # JSON
    criado_em      = Column(DateTime, default=datetime.utcnow)

    solicitante = relationship("Usuario", foreign_keys=[solicitante_id])
    autorizador = relationship("Usuario", foreign_keys=[autorizador_id])
```

A tabela é criada automaticamente por `Base.metadata.create_all` em `init_db`.

- [ ] **Step 2: Import the model in `main.py`**

Em `main.py`, no import de `database` (linha ~14, onde já vêm `CicloEtapa, Contrato, ...`), adicione `LogAcaoGerencial` à lista importada. Confirme também que `Usuario` já está importado (está — usado no `desfazer_aprovacao`).

- [ ] **Step 3: Add the `reabrir` POST handler**

Em `main.py`, no bloco de handlers POST, logo **após** o handler de `desfazer_aprovacao` (após a linha 1873), adicione:

```python
            # POST /api/projetos/<nome>/ciclo/<codigo>/reabrir — reabre em cascata (requer gerente)
            m = _re.match(r'^/api/projetos/([^/]+)/ciclo/([^/]+)/reabrir$', path)
            if m:
                nome_safe   = unquote(m.group(1))
                etapa_cod   = unquote(m.group(2))
                solicitante = get_usuario_sessao(self)
                if not solicitante:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req   = json.loads(body or b'{}')
                login = (req.get("login") or "").strip()
                senha = (req.get("senha") or "").strip()
                db = get_session()
                try:
                    autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                    if not autorizador or not autorizador.check_senha(senha):
                        self.send_json({"ok": False, "erro": "Credenciais inválidas"}, code=403)
                        return
                    if autorizador.nivel not in ("gerente", "diretor", "admin"):
                        self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"}, code=403)
                        return
                    todas    = db.query(CicloEtapa).filter_by(projeto_nome=nome_safe).all()
                    codigos  = [e.etapa_codigo for e in todas]
                    resetar  = mod_ciclo.codigos_a_resetar(etapa_cod, codigos)
                    # Trava: não reabrir se desfaz contrato assinado/vigente
                    contrato = db.query(Contrato).filter_by(projeto_nome=nome_safe)\
                                 .order_by(Contrato.id.desc()).first()
                    cstatus  = contrato.status if contrato else ""
                    if mod_ciclo.reabertura_bloqueada_por_contrato(resetar, cstatus):
                        self.send_json({"ok": False,
                                        "erro": "Contrato já assinado — não é possível reabrir esta etapa"},
                                       code=400)
                        return
                    resetar_set = set(resetar)
                    status_anterior = {e.etapa_codigo: e.status for e in todas
                                       if e.etapa_codigo in resetar_set}
                    for e in todas:
                        if e.etapa_codigo in resetar_set:
                            e.status         = "pendente"
                            e.iniciado_em    = None
                            e.concluido_em   = None
                            e.responsavel_id = None
                    log = LogAcaoGerencial(
                        solicitante_id=solicitante["id"],
                        autorizador_id=autorizador.id,
                        acao="reabrir_cascata",
                        projeto_nome=nome_safe,
                        etapa_alvo=etapa_cod,
                        contexto=json.dumps({"resetadas": sorted(resetar_set),
                                             "status_anterior": status_anterior}),
                    )
                    db.add(log)
                    db.commit()
                    self.send_json({"ok": True, "resetadas": sorted(resetar_set)})
                except Exception as e:
                    db.rollback()
                    self.send_json({"ok": False, "erro": str(e)}, code=500)
                finally:
                    db.close()
                return
```

> Nota: a rota PATCH genérica `^/api/projetos/([^/]+)/ciclo/([^/]+)$` **não** conflita — ela exige fim de string após o 2º segmento, e este endpoint tem `/reabrir` adicional e é POST.

- [ ] **Step 4: Run the helper tests + import smoke test**

Run: `python -m pytest tests/test_ciclo.py -v`
Expected: PASS (helpers já cobrem a seleção de cascata e a trava de contrato)

Run: `python -c "import database; database.init_db(); import main; print('import ok')"`
Expected: `import ok` (a tabela `log_acoes_gerenciais` é criada sem erro)

- [ ] **Step 5: Commit**

```bash
git add database.py main.py
git commit -m "feat(ciclo): endpoint reabrir cascata com auth gerencial + auditoria"
```

---

## Task 6: Frontend — reordenar etapas, cadeado nas bloqueadas e modal de reabertura

**Files:**
- Modify: `static/index.html` — `ETAPAS_CICLO` (linha 6119); `renderCiclo` (linha 6218); novo helper `_etapaBloqueada`; modal de autorização + `reabrirEtapaCascata`

> Sem harness de teste JS no projeto → verificação **manual** com o app rodando. Faça edições pequenas e confira no navegador.

- [ ] **Step 1: Reorder `ETAPAS_CICLO`**

Em `static/index.html:6119`, troque as duas primeiras entradas de dados (o "1 Captação" permanece; invertem-se Briefing e Criação) para:

```javascript
const ETAPAS_CICLO = [
  { codigo: "1",   nome: "Captação do cliente",                sub: false },
  { codigo: "2",   nome: "Criação do projeto",                 sub: false },
  { codigo: "3",   nome: "Briefing",                           sub: false },
  { codigo: "4",   nome: "Primeiro orçamento",                 sub: false },
  // ... (demais linhas 5..20 inalteradas)
```

Mantenha todo o restante do array exatamente como está.

- [ ] **Step 2: Add a JS canonical-order helper + `_etapaBloqueada`**

Logo após a definição de `ETAPAS_CICLO` (após a linha que fecha o array `];`), adicione:

```javascript
// Ordem canônica das etapas PRINCIPAIS (espelha mod_ciclo.py no backend).
const ETAPAS_PRINCIPAIS = ["1","2","3","4","5","6","7","8","9","10",
                           "11","12","13","14","15","16","17","18","19","20"];

// Bloqueada = etapa principal cuja anterior (na ordem) não está concluída.
function _etapaBloqueada(codigo) {
  const i = ETAPAS_PRINCIPAIS.indexOf(codigo);
  if (i <= 0) return false;                 // sub-etapa ou a primeira → nunca bloqueada
  const ant = ETAPAS_PRINCIPAIS[i - 1];
  return (_cicloData[ant]?.status) !== 'concluido';
}
```

- [ ] **Step 3: Render the locked state in `renderCiclo`**

Em `renderCiclo` (`static/index.html:6218`), onde hoje calcula `etStatus`/`etIcone`/`etCor` (linhas ~6231-6239), incorpore o estado bloqueado. Substitua aquele bloco por:

```javascript
      const dados    = _cicloData[etapa.codigo] || {};
      const bloqueada = _etapaBloqueada(etapa.codigo) && (dados.status || 'pendente') !== 'concluido';
      const etStatus = bloqueada ? 'bloqueado' : (dados.status || 'pendente');
      const etIcone  = etStatus === 'concluido'    ? '✓' :
                       etStatus === 'em_andamento' ? '◉' :
                       etStatus === 'bloqueado'    ? '🔒' : '◯';
      const etCor    = etStatus === 'concluido'    ? 'var(--ok, #50c878)' :
                       etStatus === 'em_andamento' ? 'var(--dalm-gold)' : 'var(--muted)';
```

Em seguida, no ponto em que o header da etapa é montado com `onclick="toggleCicloCard(...)"` (linha ~6245), torne o card não-clicável quando bloqueado:

```javascript
      const onclickHeader = bloqueada ? '' : `onclick="toggleCicloCard('${etapa.codigo}')"`;
```

e use `${onclickHeader}` no lugar do `onclick="toggleCicloCard('${etapa.codigo}')"` literal do header.

- [ ] **Step 4: Disable action/toggle buttons when blocked**

No trecho que monta o `btnToggle` (linha ~6323) e nos cards de ação (contrato/aprovação financeira), só renderize botões ativos quando `!bloqueada`. Para o `btnToggle`, envolva a expressão:

```javascript
const btnToggle = (etapa.toggleavel && !bloqueada) ? (() => {
  // ... corpo atual inalterado ...
})() : '';
```

- [ ] **Step 5: Add the "Reabrir" button on concluded etapas + manager modal**

No card genérico de uma etapa **concluída** e principal, ofereça um botão "🔓 Reabrir (gerente)". Adicione ao final do corpo do card (onde hoje fica o `btnToggle`), condicionado a `dados.status === 'concluido' && ETAPAS_PRINCIPAIS.includes(etapa.codigo)`:

```javascript
const btnReabrir = (dados.status === 'concluido' && ETAPAS_PRINCIPAIS.includes(etapa.codigo))
  ? `<button onclick="abrirModalReabrir('${etapa.codigo}')"
       style="border:1px solid var(--muted);color:var(--muted);background:none;
              border-radius:5px;padding:6px 14px;font-size:.8rem;cursor:pointer;margin-top:10px;margin-left:8px">
       🔓 Reabrir (gerente)</button>`
  : '';
```

E inclua `${btnReabrir}` na string de saída do card, ao lado de `${btnToggle}`.

- [ ] **Step 6: Add the modal + cascade call function**

Em qualquer ponto do bloco `<script>` (ex.: perto de `toggleSalvarEtapa`), adicione:

```javascript
let _reabrirCodigo = null;

function abrirModalReabrir(codigo) {
  _reabrirCodigo = codigo;
  const nome = (ETAPAS_CICLO.find(e => e.codigo === codigo) || {}).nome || codigo;
  const ok = confirm(
    `Reabrir "${nome}" reabrirá TAMBÉM todas as etapas seguintes (volta tudo a pendente).\n` +
    `Esta ação exige autorização de GERENTE e será registrada.\n\nDeseja continuar?`);
  if (!ok) { _reabrirCodigo = null; return; }
  const login = prompt('Login do gerente:');
  if (!login) { _reabrirCodigo = null; return; }
  const senha = prompt('Senha do gerente:');
  if (!senha) { _reabrirCodigo = null; return; }
  reabrirEtapaCascata(login, senha);
}

async function reabrirEtapaCascata(login, senha) {
  if (!projetoAtivo || !_reabrirCodigo) return;
  try {
    const r = await fetch(
      `/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/ciclo/${encodeURIComponent(_reabrirCodigo)}/reabrir`,
      { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, senha }) });
    const d = await r.json();
    if (!d.ok) { showToast('Erro: ' + (d.erro || 'falha'), true); return; }
    showToast('Etapas reabertas: ' + (d.resetadas || []).join(', '));
    _reabrirCodigo = null;
    await carregarCiclo();
  } catch (e) { showToast('Erro de rede: ' + e.message, true); }
}
```

> MVP usa `confirm`/`prompt`. Um modal estilizado pode substituir depois sem mudar o backend.

- [ ] **Step 7: Add a `.badge-bloqueado` visual (optional but consistent)**

O CSS já tem `.badge-bloqueado` (visto em `static/index.html`). Garanta que etapas bloqueadas usem `etCor`/ícone 🔒 — nenhuma mudança de CSS adicional é obrigatória.

- [ ] **Step 8: Manual verification with the app**

Run: `python main.py` e abra o navegador.

Verifique:
1. A ordem agora mostra **Criação do projeto** (2) antes de **Briefing** (3).
2. Num projeto novo, o Briefing aparece como etapa corrente (◯) e a etapa 4 aparece **bloqueada** (🔒, botão desabilitado).
3. Concluir o Briefing destrava a etapa 4.
4. Clicar "🔓 Reabrir (gerente)" numa etapa concluída pede login/senha; com credencial de **consultor** → erro "Necessário nível Gerente"; com credencial de **gerente** → etapas seguintes voltam a pendente e some o cadeado conforme o caso.
5. Reabrir uma etapa que desfaria contrato assinado → erro de bloqueio.

- [ ] **Step 9: Commit**

```bash
git add static/index.html
git commit -m "feat(ciclo): UI reordenada, cadeado em etapas bloqueadas e reabertura por gerente"
```

---

## Final verification

- [ ] **Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: todos passam (inclui `test_ciclo.py` e os testes pré-existentes).

- [ ] **Confirm migration marker + ordering on real DB**

Run: `python -X utf8 -c "import sqlite3; c=sqlite3.connect('omie.db'); print('migracao:', c.execute(\"SELECT id FROM schema_migrations\").fetchall())"`
Expected: contém `etapas_swap_2_3`.

---

## Notas de escopo (fora deste plano)

- **Sub-projeto B** — `validar_cliente_para_contrato` já existe (`mod_contrato.py`); o popup "Cadastro Incompleto" na aprovação é outro plano.
- **Sub-projeto C** — "Aprovar Orçamento" concluir Revisão+Aprovação juntas; 1º orçamento por XML; renomear botão de contrato.
- **Sub-projeto D** — tornar o Briefing efetivamente obrigatório (bloquear avanço ao 1º orçamento sem briefing completo). Este plano deixa o Briefing pendente; D adiciona a obrigatoriedade.
- **Opcional** — alinhar `desfazer_aprovacao` à nova auditoria `log_acoes_gerenciais`.
```
