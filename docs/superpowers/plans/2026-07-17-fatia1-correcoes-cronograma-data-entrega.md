# Fatia 1 — Correções de Cronograma e Persistência da Data de Entrega — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir os três defeitos que destravam o uso hoje — a data de entrega que "some" da tela, a
folga incompreensível e o Cronograma Padrão com semântica ambígua — sem adicionar colunas nem mudar a UI
além de religar a leitura.

**Architecture:** `prazo_dias` passa a significar **duração da etapa** (dias corridos). `gerar_cronograma_projeto`
acumula durações. O default do Cronograma Padrão é reescrito com durações realistas e ganha um marcador
`cronograma_formato` (1=legado acumulado, 2=durações) que normaliza configs antigas na leitura, de forma
idempotente. A serialização do contrato passa a devolver `data_entrega` do `Projeto`, que o card já sabe ler.

**Tech Stack:** Python puro (`http.server`, SQLAlchemy), pytest/TDD, frontend em `static/index.html` (JS inline).

**Escopo desta fatia (spec §2 e §3):** correção de persistência da `data_entrega`, `gerar_cronograma_projeto`
acumulando durações, novo default + `cronograma_formato`. **Fora desta fatia:** colunas `previsao_medicao`/
`venda_programada`, fórmula de folga medição→entrega, bloqueio gerencial, prazo contratual, sinal de atraso
(Fatias 2–4).

**Referência:** `docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md`.

---

## File Structure

- `mod_provisoes.py` — default do Cronograma Padrão (durações + `cronograma_formato`) e nova função pura
  `normalizar_cronograma_formato`.
- `mod_cronograma.py` — `gerar_cronograma_projeto` passa a acumular durações.
- `main.py` — `_cfg_financeira_loja` (8490) e o GET config-financeira (1568) normalizam o `stored` antes do
  merge; a serialização do contrato (2369) inclui `data_entrega`.
- `static/index.html` — nenhuma mudança de código nova (o card já lê `contrato.data_entrega`); só verificação.
- Testes: `tests/test_cronograma.py` (existentes, ajustados), `tests/test_data_entrega.py` (novo caso de
  round-trip).

---

## Task 1: Novo default do Cronograma Padrão (durações) + marcador `cronograma_formato`

**Files:**
- Modify: `mod_provisoes.py:39-47` (bloco `cronograma_padrao` dentro de `config_financeira_default`)
- Test: `tests/test_cronograma.py`

- [ ] **Step 1: Escrever o teste falhando**

Adicionar em `tests/test_cronograma.py` (após `test_config_default_inclui_cronograma`, linha 98):

```python
def test_default_cronograma_em_duracoes_e_formato_2():
    cfg = mod_provisoes.config_financeira_default()
    assert cfg.get("cronograma_formato") == 2                      # nasce em durações
    fases = cfg["cronograma_padrao"]
    # durações (não acumulado): nenhuma etapa isolada dura mais que o ciclo inteiro
    total = sum(int(f["prazo_dias"]) for f in fases)
    assert total <= 90                                             # ~50 dias úteis ≈ ~72 corridos
    assert all(int(f["prazo_dias"]) <= 30 for f in fases)          # nenhuma etapa vira o acumulado antigo (55,70…)
```

- [ ] **Step 2: Rodar o teste e ver falhar**

Run: `python3 -m pytest tests/test_cronograma.py::test_default_cronograma_em_duracoes_e_formato_2 -v`
Expected: FAIL — hoje `cronograma_formato` não existe (é `None`) e os prazos são acumulados (55, 70…).

- [ ] **Step 3: Reescrever o default com durações + marcador**

Substituir o bloco em `mod_provisoes.py:37-47` por:

```python
        # Cronograma de Projeto Padrão: prazo_dias = DURAÇÃO da etapa (dias corridos). Na assinatura,
        # data_prevista = D0 + Σ durações até a etapa. cronograma_formato=2 marca o formato "durações"
        # (1/ausente = legado acumulado, convertido na leitura por normalizar_cronograma_formato).
        "cronograma_formato": 2,
        "cronograma_padrao": [
            {"codigo": "8",  "prazo_dias": 2},   {"codigo": "9",  "prazo_dias": 3},
            {"codigo": "10", "prazo_dias": 5},   {"codigo": "11", "prazo_dias": 10},
            {"codigo": "12", "prazo_dias": 3},   {"codigo": "13", "prazo_dias": 25},
            {"codigo": "14", "prazo_dias": 5},   {"codigo": "15", "prazo_dias": 2},
            {"codigo": "16", "prazo_dias": 5},   {"codigo": "17", "prazo_dias": 5},
            {"codigo": "18", "prazo_dias": 3},   {"codigo": "19", "prazo_dias": 2},
            {"codigo": "20", "prazo_dias": 2},
        ],
```

- [ ] **Step 4: Rodar o teste e ver passar**

Run: `python3 -m pytest tests/test_cronograma.py::test_default_cronograma_em_duracoes_e_formato_2 tests/test_cronograma.py::test_config_default_inclui_cronograma -v`
Expected: PASS (ambos).

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_cronograma.py
git commit -m "feat(cronograma): default do Cronograma Padrão em durações + marcador cronograma_formato

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Função pura `normalizar_cronograma_formato` (legado acumulado → durações)

**Files:**
- Modify: `mod_provisoes.py` (nova função após `config_financeira_default`, ~linha 49)
- Test: `tests/test_cronograma.py`

- [ ] **Step 1: Escrever o teste falhando**

Adicionar em `tests/test_cronograma.py`:

```python
def test_normalizar_cronograma_formato_converte_legado():
    # config legada: acumulado (dias desde D0), sem marcador de formato
    legado = {"cronograma_padrao": [
        {"codigo": "8", "prazo_dias": 2}, {"codigo": "9", "prazo_dias": 5},
        {"codigo": "10", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 55},
    ]}
    out = mod_provisoes.normalizar_cronograma_formato(legado)
    by = {f["codigo"]: f["prazo_dias"] for f in out["cronograma_padrao"]}
    assert by == {"8": 2, "9": 3, "10": 5, "16": 45}   # diferenças = durações
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_idempotente():
    ja = {"cronograma_formato": 2, "cronograma_padrao": [{"codigo": "8", "prazo_dias": 2}]}
    out = mod_provisoes.normalizar_cronograma_formato(ja)
    assert out["cronograma_padrao"][0]["prazo_dias"] == 2   # não converte de novo
    assert out["cronograma_formato"] == 2


def test_normalizar_cronograma_formato_sem_cronograma_nao_inventa():
    # config antiga sem a chave → não cria lista vazia (o merge com default é quem preenche)
    out = mod_provisoes.normalizar_cronograma_formato({"provisoes": {}})
    assert "cronograma_padrao" not in out
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cronograma.py -k normalizar -v`
Expected: FAIL — `AttributeError: module 'mod_provisoes' has no attribute 'normalizar_cronograma_formato'`.

- [ ] **Step 3: Implementar a função**

Adicionar em `mod_provisoes.py` logo após `config_financeira_default` (antes de `validar_config_financeira`):

```python
def normalizar_cronograma_formato(cfg):
    """Converte o cronograma_padrao do formato-legado ACUMULADO (dias desde D0) para DURAÇÕES por etapa,
    idempotente via a chave 'cronograma_formato' (ausente/1 = acumulado → converte; 2 = durações → mantém).
    Não inventa cronograma_padrao se a chave não existe (o merge com o default é quem preenche). Muta e
    retorna o próprio cfg."""
    cfg = cfg or {}
    if "cronograma_padrao" not in cfg:
        return cfg
    if int(cfg.get("cronograma_formato") or 1) >= 2:
        return cfg
    prev = 0
    novas = []
    for it in (cfg.get("cronograma_padrao") or []):
        acc = int((it or {}).get("prazo_dias") or 0)
        nova = dict(it or {})
        nova["prazo_dias"] = max(0, acc - prev)
        prev = acc
        novas.append(nova)
    cfg["cronograma_padrao"] = novas
    cfg["cronograma_formato"] = 2
    return cfg
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_cronograma.py -k normalizar -v`
Expected: PASS (3 casos).

- [ ] **Step 5: Commit**

```bash
git add mod_provisoes.py tests/test_cronograma.py
git commit -m "feat(cronograma): normalizar_cronograma_formato converte config legada (acumulado→durações)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Aplicar a normalização na leitura da config (antes do merge)

**Files:**
- Modify: `main.py:8495-8499` (`_cfg_financeira_loja`)
- Modify: `main.py:1568-1569` (GET config-financeira da loja)
- Test: `tests/test_cronograma.py`

- [ ] **Step 1: Escrever o teste falhando**

Adicionar em `tests/test_cronograma.py` (usa a loja do seed com config legada salva):

```python
def test_cfg_loja_converte_cronograma_legado_na_leitura(http_client_factory, seed, app_db):
    # grava no config da loja o formato-legado acumulado (sem cronograma_formato)
    db = app_db.get_session()
    import json as _json
    loja = db.query(app_db.Loja).filter_by(id=db.query(app_db.Usuario)
              .filter_by(login="dir_l1").first().loja_id).first()
    loja.config_financeira_json = _json.dumps({"cronograma_padrao": [
        {"codigo": "10", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 55}]})
    db.commit(); loja_id = loja.id; db.close()
    # GET config-financeira deve devolver durações (10→10, 16→45), não o acumulado
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.get("/api/admin/lojas/%d/config-financeira" % loja_id)
    assert st == 200
    by = {f["codigo"]: f["prazo_dias"] for f in d["config"]["cronograma_padrao"]}
    assert by["10"] == 10 and by["16"] == 45
    assert d["config"]["cronograma_formato"] == 2
```

> Path confirmado: `GET /api/admin/lojas/<id>/config-financeira` (`main.py:1552-1557`).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cronograma.py::test_cfg_loja_converte_cronograma_legado_na_leitura -v`
Expected: FAIL — hoje `by["16"] == 55` (acumulado) e não há `cronograma_formato`.

- [ ] **Step 3: Normalizar o stored antes do merge nos dois pontos**

Em `main.py:8495-8499` (`_cfg_financeira_loja`), substituir o corpo do `try`:

```python
        try:
            # Normaliza o STORED antes do merge: config legada (sem cronograma_formato) é convertida de
            # acumulado para durações. O merge preenche chaves novas sem apagar o já configurado.
            _stored = mod_provisoes.normalizar_cronograma_formato(json.loads(loja.config_financeira_json))
            return {**mod_provisoes.config_financeira_default(), **_stored}
        except Exception:
            pass
```

Em `main.py:1568-1569` (GET config-financeira), substituir:

```python
                _stored = mod_provisoes.normalizar_cronograma_formato(
                    json.loads(loja.config_financeira_json) if loja.config_financeira_json else {})
                cfg = {**mod_provisoes.config_financeira_default(), **_stored}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_cronograma.py::test_cfg_loja_converte_cronograma_legado_na_leitura -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_cronograma.py
git commit -m "fix(cronograma): normaliza config legada (acumulado→durações) na leitura, antes do merge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `gerar_cronograma_projeto` acumula durações

**Files:**
- Modify: `mod_cronograma.py:37-54` (`gerar_cronograma_projeto`)
- Test: `tests/test_cronograma.py:128-138` (ajustar teste existente à nova semântica)

- [ ] **Step 1: Ajustar o teste existente para a semântica acumulada**

Substituir `test_gerar_cronograma_define_data_prevista` (`tests/test_cronograma.py:128-138`) por:

```python
def test_gerar_cronograma_define_data_prevista_acumulado(app_db):
    db = app_db.get_session()
    d0 = datetime(2026, 7, 1, 12, 0, 0)
    # prazo_dias = DURAÇÃO por etapa; data_prevista = D0 + Σ durações até a etapa (inclusive)
    cfg = _cfg([{"codigo": "9", "prazo_dias": 5}, {"codigo": "13", "prazo_dias": 45}])
    mod_cronograma.gerar_cronograma_projeto(db, "ProjX", cfg, d0); db.commit()
    e9 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="9").first()
    e13 = db.query(app_db.CicloEtapa).filter_by(projeto_nome="ProjX", etapa_codigo="13").first()
    assert e9.data_prevista_conclusao == d0 + timedelta(days=5)        # 1ª etapa: só a própria duração
    assert e13.data_prevista_conclusao == d0 + timedelta(days=50)      # 5 + 45 acumulado
    assert e9.concluido_em is None
    db.close()
```

> Nota: `test_gerar_cronograma_idempotente_e_preserva_conclusao` e `test_gerar_cronograma_herda_funcao_responsavel`
> usam cfg de UMA etapa (acumulado == duração), então continuam válidos sem mudança.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cronograma.py::test_gerar_cronograma_define_data_prevista_acumulado -v`
Expected: FAIL — hoje `e13` grava `d0 + 45` (offset direto), o teste espera `d0 + 50` (acumulado).

- [ ] **Step 3: Fazer `gerar_cronograma_projeto` acumular**

Substituir `mod_cronograma.py:37-54` por:

```python
def gerar_cronograma_projeto(db, projeto_nome, cfg, d0):
    """Para cada fase do Cronograma Padrão, cria/atualiza a etapa do projeto com
    data_prevista_conclusao = d0 + Σ(durações das etapas até esta, inclusive). prazo_dias é a DURAÇÃO
    da etapa (dias corridos). Não toca data de conclusão. Idempotente. Retorna as CicloEtapa afetadas."""
    afetadas = []
    acc = 0
    for fase in cronograma_padrao(cfg):
        acc += fase["prazo_dias"]
        prevista = d0 + timedelta(days=acc)
        reg = (db.query(CicloEtapa)
               .filter_by(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"]).first())
        if reg is None:
            reg = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"])
            db.add(reg)
        reg.data_prevista_conclusao = prevista
        # Herda a FUNÇÃO responsável do padrão (v12); não sobrescreve o funcionário já escolhido.
        reg.funcao_responsavel_id = fase.get("funcao_id")
        afetadas.append(reg)
    db.flush()
    return afetadas
```

- [ ] **Step 4: Rodar e ver passar (o módulo inteiro, para pegar regressões)**

Run: `python3 -m pytest tests/test_cronograma.py tests/test_cronogramas_dois.py -v`
Expected: PASS em todos.

- [ ] **Step 5: Commit**

```bash
git add mod_cronograma.py tests/test_cronograma.py
git commit -m "fix(cronograma): gerar_cronograma_projeto acumula durações (data_prevista = D0 + Σ até a etapa)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Bug de persistência — serializar `data_entrega` no GET contrato

**Files:**
- Modify: `main.py:2369-2380` (payload de `GET /api/projetos/<nome>/contrato`)
- Test: `tests/test_data_entrega.py`
- Verify: `static/index.html:13602` (o card já lê `contrato.data_entrega` — só confirmar, sem mudança)

- [ ] **Step 1: Escrever o teste de round-trip falhando**

Adicionar em `tests/test_data_entrega.py`:

```python
def test_data_entrega_persiste_e_volta_no_contrato(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj, {"data_entrega": "2028-01-01"})
    assert st == 200 and d["ok"], (st, d)
    # o GET do contrato deve devolver a data gravada (hoje não devolve → o card relê vazio)
    st2, d2 = c.get("/api/projetos/%s/contrato" % proj)
    assert st2 == 200 and d2["contrato"] is not None, (st2, d2)
    assert (d2["contrato"].get("data_entrega") or "").startswith("2028-01-01"), d2["contrato"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_data_entrega.py::test_data_entrega_persiste_e_volta_no_contrato -v`
Expected: FAIL — `data_entrega` não está no payload (KeyError/None), então o `startswith` falha.

- [ ] **Step 3: Incluir `data_entrega` do projeto na serialização**

Em `main.py`, dentro do handler do GET contrato, logo antes de montar o `send_json` (por volta da linha
2364, ao lado de `_orc_src = db.get(Orcamento, ...)`), buscar o projeto:

```python
                    _proj_meta = db.get(Projeto, nome_safe)
```

E acrescentar a chave no dict serializado (dentro do bloco `"contrato": { ... }`, após `"orcamento_id"`):

```python
                        "data_entrega":         _proj_meta.data_entrega.isoformat() if (_proj_meta and _proj_meta.data_entrega) else None,
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_data_entrega.py -v`
Expected: PASS (o novo caso e os três existentes).

- [ ] **Step 5: Verificar o card no navegador (manual)**

`static/index.html` é lido do disco a cada request → só Ctrl+F5, sem restart (mas mudou Python → **reinicie**
`python3 main.py`). No card do Contrato: informar a data, clicar Validar, sair do projeto e voltar — o campo
deve reexibir a data (antes voltava vazio). O input já lê `contrato.data_entrega` (`static/index.html:13602`);
nenhuma mudança de JS é necessária.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_data_entrega.py
git commit -m "fix(contrato): serializa data_entrega do projeto no GET contrato — corrige data que 'sumia' do card

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Suíte verde completa (regressão) + fecho da fatia

- [ ] **Step 1: Rodar a suíte inteira**

Run: `python3 -m pytest -q`
Expected: tudo verde. Se algo do cronograma/provisões quebrar, é regressão desta fatia — investigar antes
de seguir (candidatos: testes que assumiam o default acumulado antigo, ex. em `tests/test_provisoes.py`).

- [ ] **Step 2: Se `tests/test_provisoes.py` referenciava os prazos antigos, ajustar**

Buscar: `python3 -m pytest tests/test_provisoes.py -q` e, se falhar por causa de `cronograma_padrao`/valores
55/70, atualizar a expectativa do teste para os novos valores/estrutura (a asserção de que o default inclui
`cronograma_padrao` continua válida; só valores mudaram).

- [ ] **Step 3: Commit (se houve ajuste no Step 2)**

```bash
git add tests/test_provisoes.py
git commit -m "test(provisoes): ajusta expectativa do cronograma_padrao ao novo default em durações

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 4: Atualizar o DEV_LOG**

Acrescentar uma nova seção `## Sessão N` no `DEV_LOG.md` resumindo a Fatia 1 (bug da data corrigido, semântica
`prazo_dias`=duração, `gerar_cronograma_projeto` acumula, `cronograma_formato`). Commit:

```bash
git add DEV_LOG.md
git commit -m "docs(devlog): Fatia 1 — correções de cronograma e persistência da data de entrega

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review (coberto por esta fatia)

- **Spec §2 (persistência):** Task 5. ✓
- **Spec §3 (gerar_cronograma acumula, default durações, cronograma_formato):** Tasks 1–4. ✓
- **Fora de escopo confirmado:** colunas novas, folga medição→entrega, bloqueio gerencial, prazo contratual,
  sinal de atraso → Fatias 2–4. ✓
- **Regressão conhecida tratada:** `test_gerar_cronograma_define_data_prevista` (Task 4) e possível
  `test_provisoes.py` (Task 6). ✓
