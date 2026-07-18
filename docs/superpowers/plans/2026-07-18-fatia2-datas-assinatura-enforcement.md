# Fatia 2 — Datas da Assinatura, Folga Medição→Entrega e Enforcement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a **previsão de medição** e a **expectativa de entrega** obrigatórias e monitoráveis na assinatura, com a folga calculada no trecho **medição→entrega** e **bloqueio real** (override gerencial) quando não cabe.

**Architecture:** Duas colunas novas no `Projeto` (`previsao_medicao`, `venda_programada`). A folga passa a ser `(data_entrega − previsao_medicao) − Σ durações das etapas após a medição até a "16"` (só o trecho sob controle da loja). O endpoint `POST /data-entrega` persiste os três campos e bloqueia `folga<0` salvo reautenticação Gerente+ (auditada em `LogAcaoGerencial`). A trava da 2ª assinatura passa a exigir **ambas** as datas. UI mínima de entrada entra junto para manter a fatia deployável.

**Tech Stack:** Python puro (`http.server`, SQLAlchemy), pytest/TDD, frontend `static/index.html` (JS inline).

**Escopo (spec §1, §3-folga, §4):** colunas + persistência, `folga_medicao_entrega`, bloqueio+override, trava de assinatura pelas duas datas, e a **UI mínima de entrada** (campo previsão de medição + checkbox venda programada). **Fora:** prazo contratual + marcadores no contrato (Fatia 3), sinal de atraso + UI final polida (Fatia 4).

> **Desvio deliberado da spec:** a spec rotula a UI do card como Fatia 4. Como a Fatia 2 torna a previsão de medição obrigatória para assinar, a UI de entrada é incluída aqui — sem ela a assinatura travaria em produção entre as fatias. Só a UI de ENTRADA (campo + checkbox + wiring + fluxo de override) entra; o sinal de atraso e o polimento ficam na Fatia 4.

**Referência:** `docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md`.

---

## File Structure

- `database.py` — `Projeto` (linha 507) ganha `previsao_medicao` (DateTime) e `venda_programada` (Integer 0/1); migração via `_add_cols("projetos_meta", …)` (linha 1420).
- `mod_cronograma.py` — nova função pura `folga_medicao_entrega(cfg, previsao_medicao, data_entrega, …)`.
- `main.py` — endpoint `POST /data-entrega` (linha 4838) reescrito (persiste 3 campos + folga nova + bloqueio + override); serialização do GET contrato (linha 2461) ganha `previsao_medicao`/`venda_programada`; trava da 2ª assinatura (linha 6306) passa a exigir as duas datas.
- `static/index.html` — card do Contrato (bloco linha 13746) ganha campo previsão de medição + checkbox venda programada; `salvarDataEntrega` (linha 13687) posta os três campos + fluxo de override.
- Testes: `tests/test_cronograma.py`, `tests/test_data_entrega.py`, `tests/test_af_gate_data_entrega.py` (verificar), mais quaisquer testes de fluxo de assinatura que passem a exigir `previsao_medicao`.

---

## Task 1: Colunas `previsao_medicao` e `venda_programada` no `Projeto`

**Files:**
- Modify: `database.py:521` (model `Projeto`, após `equipe_json`)
- Modify: `database.py:1420-1421` (migração `_add_cols`)
- Test: `tests/test_cronograma.py`

- [ ] **Step 1: Escrever o teste falhando**

Adicionar em `tests/test_cronograma.py`:

```python
def test_projeto_tem_previsao_medicao_e_venda_programada(app_db):
    from datetime import datetime
    db = app_db.get_session()
    p = app_db.Projeto(nome_safe="ProjVP", previsao_medicao=datetime(2026, 8, 1), venda_programada=1)
    db.add(p); db.commit()
    got = db.get(app_db.Projeto, "ProjVP")
    assert got.previsao_medicao == datetime(2026, 8, 1)
    assert got.venda_programada == 1
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cronograma.py::test_projeto_tem_previsao_medicao_e_venda_programada -v`
Expected: FAIL — `TypeError: 'previsao_medicao' is an invalid keyword argument for Projeto` (coluna não existe).

- [ ] **Step 3: Adicionar as colunas no model**

Em `database.py`, logo após a linha `equipe_json = Column(Text, …)` (linha 521) dentro de `class Projeto`:

```python
    previsao_medicao = Column(DateTime, nullable=True)   # marco de medição (venda programada / obra do cliente)
    venda_programada = Column(Integer,  default=0)        # 1 = obra do cliente controla a medição (classificação + marcador no contrato, Fatia 3)
```

- [ ] **Step 4: Adicionar a migração idempotente**

Em `database.py`, logo após a linha `_add_cols("projetos_meta", [("equipe_json","TEXT")])` (linha 1421):

```python
        _add_cols("projetos_meta", [("previsao_medicao","DATETIME"), ("venda_programada","INTEGER")])   # Fatia 2: marco de medição + classificação
```

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_cronograma.py::test_projeto_tem_previsao_medicao_e_venda_programada -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add database.py tests/test_cronograma.py
git commit -m "feat(projeto): colunas previsao_medicao + venda_programada (Fatia 2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `folga_medicao_entrega` (pura) em `mod_cronograma`

**Files:**
- Modify: `mod_cronograma.py` (nova função após `cabe_no_cronograma`, ~linha 128)
- Test: `tests/test_cronogramas_dois.py`

- [ ] **Step 1: Escrever os testes falhando**

Adicionar em `tests/test_cronogramas_dois.py`:

```python
def test_folga_medicao_entrega_cabe():
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "9", "prazo_dias": 3}, {"codigo": "10", "prazo_dias": 5},
        {"codigo": "11", "prazo_dias": 10}, {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 9, 1)     # 31 dias corridos
    # etapas APÓS "10" até "16": 11(10) + 16(5) = 15 → folga = 31 − 15 = 16
    assert mcr.folga_medicao_entrega(cfg, med, ent) == 16


def test_folga_medicao_entrega_nao_cabe():
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "10", "prazo_dias": 5}, {"codigo": "11", "prazo_dias": 10},
        {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 8, 10)    # 9 dias
    # após "10": 11(10)+16(5)=15 → folga = 9 − 15 = −6
    assert mcr.folga_medicao_entrega(cfg, med, ent) == -6


def test_folga_medicao_entrega_fallback_sem_10():
    # sem etapa "10" → âncora cai na "9"; após "9": 13(20)+16(5)=25
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "9", "prazo_dias": 4}, {"codigo": "13", "prazo_dias": 20},
        {"codigo": "16", "prazo_dias": 5}]}
    med = datetime(2026, 8, 1); ent = datetime(2026, 10, 1)    # 61 dias
    assert mcr.folga_medicao_entrega(cfg, med, ent) == 61 - 25
```

> `tests/test_cronogramas_dois.py` já importa `from datetime import datetime` e `import mod_cronograma as mcr` (topo do arquivo).

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cronogramas_dois.py -k folga_medicao -v`
Expected: FAIL — `AttributeError: module 'mod_cronograma' has no attribute 'folga_medicao_entrega'`.

- [ ] **Step 3: Implementar a função**

Adicionar em `mod_cronograma.py` logo após `cabe_no_cronograma` (antes de `cronograma_projeto_view`):

```python
def folga_medicao_entrega(cfg, previsao_medicao, data_entrega, cod_medicao="10", cod_entrega="16"):
    """Folga do trecho MEDIÇÃO→ENTREGA em dias corridos: (data_entrega − previsao_medicao) menos a soma
    das DURAÇÕES das etapas APÓS a medição até a entrega (inclusive). Só as etapas sob controle da loja
    (PE, produção, entrega) contam; as anteriores à medição dependem da obra do cliente. Negativa = não
    cabe. Âncora da medição: prefere `cod_medicao` ("10"); se ausente, "9"; se nenhum, a 1ª etapa.
    `cod_entrega` default "16" (Entrega no cliente); se ausente, a última etapa."""
    etapas = cronograma_padrao(cfg)
    cods = [e["codigo"] for e in etapas]
    if cod_medicao in cods:
        idx_med = cods.index(cod_medicao)
    elif "9" in cods:
        idx_med = cods.index("9")
    else:
        idx_med = 0
    idx_ent = cods.index(cod_entrega) if cod_entrega in cods else len(etapas) - 1
    soma = sum(int(etapas[i]["prazo_dias"]) for i in range(idx_med + 1, idx_ent + 1))
    return (data_entrega - previsao_medicao).days - soma
```

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_cronogramas_dois.py -k folga_medicao -v`
Expected: PASS (3 casos).

- [ ] **Step 5: Commit**

```bash
git add mod_cronograma.py tests/test_cronogramas_dois.py
git commit -m "feat(cronograma): folga_medicao_entrega (trecho sob controle da loja)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Endpoint `POST /data-entrega` — persiste 3 campos + folga nova + bloqueio + override

**Files:**
- Modify: `main.py:4838-4872` (handler inteiro do `POST /api/projetos/<nome>/data-entrega`)
- Test: `tests/test_data_entrega.py` (reescrever os casos existentes + novos)

- [ ] **Step 1: Reescrever os testes de `tests/test_data_entrega.py`**

Substituir TODO o conteúdo dos 3 testes existentes (`test_data_entrega_folgada_cabe_e_persiste`, `test_data_entrega_apertada_nao_cabe`, `test_data_entrega_invalida_400`) e o de round-trip adicionado na Fatia 1 (`test_data_entrega_persiste_e_volta_no_contrato`) pelos abaixo. O default do cronograma (durações) soma ~52 dias do trecho medição→entrega (etapas 11..16: 10+3+25+5+2+5 = 50); os testes usam datas folgadas/apertadas em torno disso:

```python
from database import Projeto


def test_data_entrega_folgada_cabe_e_persiste(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})   # ~7 meses de trecho
    assert st == 200, (st, d)
    assert d["ok"] and d.get("cabe") is True and d.get("folga_min") is not None
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is not None and p.previsao_medicao is not None and p.data_inicio is not None
    db.close()


def test_data_entrega_apertada_nao_cabe_nao_grava(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2026-08-05", "previsao_medicao": "2026-08-01"})   # 4 dias < ~50
    assert st == 200 and d["ok"]
    assert d["cabe"] is False and d["folga_min"] < 0 and d.get("requer_autorizacao") is True
    db = app_db.get_session()   # bloqueado → NÃO grava
    p = db.get(Projeto, proj)
    assert p.data_entrega is None
    db.close()


def test_data_entrega_sem_folga_grava_com_autorizacao_gerencial(http_client_factory, seed, app_db):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2026-08-05", "previsao_medicao": "2026-08-01",
                    "login": "dir_l1", "senha": "senha123"})   # override Gerente+
    assert st == 200 and d["ok"] and d["cabe"] is False, (st, d)
    db = app_db.get_session()
    p = db.get(Projeto, proj)
    assert p.data_entrega is not None   # gravou sob autorização
    log = (db.query(app_db.LogAcaoGerencial)
           .filter_by(projeto_nome=proj, acao="data_entrega_sem_folga").first())
    assert log is not None
    db.close()


def test_data_entrega_exige_previsao_medicao(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, d = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {"data_entrega": "2028-01-01"})
    assert st == 400 and "medição" in (d.get("erro", "").lower())


def test_data_entrega_invalida_400(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, _ = c.post("/api/projetos/%s/data-entrega" % seed["projeto_l1"], {})
    assert st == 400


def test_data_entrega_persiste_e_volta_no_contrato(http_client_factory, seed):
    c = http_client_factory(); c.login("dir_l1", "senha123")
    proj = seed["projeto_l1"]
    st, d = c.post("/api/projetos/%s/data-entrega" % proj,
                   {"data_entrega": "2028-01-01", "previsao_medicao": "2027-06-01"})
    assert st == 200 and d["ok"], (st, d)
    st2, d2 = c.get("/api/projetos/%s/contrato" % proj)
    assert st2 == 200 and d2["contrato"] is not None, (st2, d2)
    assert (d2["contrato"].get("data_entrega") or "").startswith("2028-01-01")
    assert (d2["contrato"].get("previsao_medicao") or "").startswith("2027-06-01")
```

> Verifique se há OUTROS testes em `tests/test_data_entrega.py` além destes; se houver, ajuste-os para incluir `previsao_medicao`. O `test_data_entrega_apertada_nao_cabe` original muda de nome para `_nao_grava`.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_data_entrega.py -v`
Expected: FAIL (endpoint ainda usa a folga antiga, não exige previsão de medição, grava sempre, não faz override).

- [ ] **Step 3: Reescrever o handler**

Substituir TODO o bloco `main.py:4838-4872` por:

```python
        elif re.match(r"^/api/projetos/([^/]+)/data-entrega$", path):
            # ── POST /api/projetos/<nome>/data-entrega — persiste expectativa de entrega + previsão de
            # medição + venda programada e valida a FOLGA do trecho medição→entrega. folga<0 só grava com
            # reautenticação Gerente+ (auditada). Base do monitoramento e do gate da assinatura. ──
            from urllib.parse import unquote as _unq
            import mod_cronograma as _mcr, mod_tenancy as _mten
            m_de = re.match(r"^/api/projetos/([^/]+)/data-entrega$", path)
            nome_safe = _unq(m_de.group(1))
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            req = json.loads(body) if body else {}
            data_entrega = _parse_data(req.get("data_entrega"))
            previsao_medicao = _parse_data(req.get("previsao_medicao"))
            if not data_entrega:
                self.send_json({"ok": False, "erro": "Informe a data de entrega esperada (AAAA-MM-DD)."}, code=400); return
            if not previsao_medicao:
                self.send_json({"ok": False, "erro": "Informe a previsão de medição (AAAA-MM-DD)."}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = _mten.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                if _projeto_da_loja(db, nome_safe, loja_id) is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                cfg = _cfg_financeira_loja(db, loja_id)
                folga = _mcr.folga_medicao_entrega(cfg, previsao_medicao, data_entrega)
                cabe = folga >= 0
                # Override gerencial: folga<0 só grava com reautenticação Gerente+ (auditada).
                override_ok = False
                if not cabe:
                    login = (req.get("login") or "").strip()
                    senha = (req.get("senha") or "").strip()
                    if login and senha:
                        autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
                        if autorizador and autorizador.check_senha(senha) and perfis.pode(autorizador.nivel, "autorizar"):
                            override_ok = True
                            db.add(LogAcaoGerencial(
                                solicitante_id=usuario["id"], autorizador_id=autorizador.id,
                                acao="data_entrega_sem_folga", projeto_nome=nome_safe,
                                contexto=json.dumps({
                                    "data_entrega": data_entrega.isoformat(),
                                    "previsao_medicao": previsao_medicao.isoformat(),
                                    "folga": folga})))
                if not cabe and not override_ok:
                    self.send_json({"ok": True, "cabe": False, "folga_min": folga, "requer_autorizacao": True})
                    return
                proj = db.get(Projeto, nome_safe)
                proj.data_entrega = data_entrega
                proj.previsao_medicao = previsao_medicao
                proj.venda_programada = 1 if req.get("venda_programada") else 0
                if not proj.data_inicio:
                    proj.data_inicio = datetime.utcnow()   # âncora do progressivo
                db.commit()
                self.send_json({"ok": True, "cabe": cabe, "folga_min": folga})
            finally:
                db.close()
            return
```

> Confirme que `perfis`, `Usuario`, `LogAcaoGerencial`, `Projeto`, `_parse_data`, `_cfg_financeira_loja` estão no escopo do módulo (todos já usados em `main.py`). `usuario["id"]` segue o padrão do handler `data-prevista` (linha 5983).

- [ ] **Step 4: Rodar e ver passar**

Run: `python3 -m pytest tests/test_data_entrega.py -v`
Expected: PASS (todos os casos). Depois `python3 -m pytest -q` (não pode regredir; se algum teste de assinatura/AF quebrar, é a Task 5 — anote e siga).

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_data_entrega.py
git commit -m "feat(cronograma): data-entrega persiste medição/venda programada + folga medição→entrega com bloqueio e override gerencial

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Serializar `previsao_medicao` + `venda_programada` no GET contrato

**Files:**
- Modify: `main.py:2462` (dict serializado do contrato, após a linha `"data_entrega": …`)
- Test: coberto pelo `test_data_entrega_persiste_e_volta_no_contrato` (Task 3) — este task só adiciona a serialização que o teste já exige.

- [ ] **Step 1: Rodar o teste que já exige o campo (deve falhar)**

Run: `python3 -m pytest tests/test_data_entrega.py::test_data_entrega_persiste_e_volta_no_contrato -v`
Expected: FAIL na asserção `previsao_medicao` (o payload ainda não devolve o campo).

> Se a Task 3 foi feita antes desta, este teste já falha exatamente aqui. Se passar, confirme que a linha da serialização abaixo já não existe.

- [ ] **Step 2: Adicionar as chaves na serialização**

Em `main.py`, logo após a linha `"data_entrega": _meta.data_entrega.isoformat() if (_meta and _meta.data_entrega) else None,` (linha 2462):

```python
                        "previsao_medicao":     _meta.previsao_medicao.isoformat() if (_meta and _meta.previsao_medicao) else None,
                        "venda_programada":     bool(_meta.venda_programada) if _meta else False,
```

- [ ] **Step 3: Rodar e ver passar**

Run: `python3 -m pytest tests/test_data_entrega.py::test_data_entrega_persiste_e_volta_no_contrato -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(contrato): serializa previsao_medicao + venda_programada no GET contrato

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Trava da 2ª assinatura exige as DUAS datas

**Files:**
- Modify: `main.py:6306-6315` (guard do cronograma na assinatura que completa loja+cliente)
- Test: `tests/test_af_gate_data_entrega.py` (verificar) + qualquer teste de fluxo de assinatura que passe a falhar

- [ ] **Step 1: Escrever o teste falhando**

Adicionar em `tests/test_af_gate_data_entrega.py` (usa os helpers/fixtures já existentes no arquivo; assinatura via o endpoint de assinar do contrato). Se o arquivo não tiver um helper de assinatura, criar um teste HTTP mínimo que:
1. deixa o contrato com só a 1ª assinatura (loja) e `previsao_medicao=None`, `data_entrega` definida;
2. tenta a 2ª assinatura (cliente) → espera 400 com "previsão de medição" na mensagem.

```python
def test_assinatura_exige_previsao_medicao(app_db, seed, http_client_factory):
    from database import Projeto, Contrato, ContratoAssinatura
    nome = seed["projeto_l1"]; cid = seed["contrato_l1_id"]
    db = app_db.get_session()
    db.get(Projeto, nome).data_entrega = datetime(2028, 1, 1)
    db.get(Projeto, nome).previsao_medicao = None                 # falta a medição
    ct = db.get(Contrato, cid); ct.status = "assinado_loja"
    db.add(ContratoAssinatura(contrato_id=cid, parte="loja", nome="L", cpf="00000000000",
                              assinado_em=datetime.utcnow()))
    db.commit(); db.close()
    c = http_client_factory(); c.login("dir_l1", "senha123")
    # tentativa da 2ª assinatura (cliente) — ajuste o path/payload ao endpoint real de assinar
    st, d = c.post("/api/projetos/%s/contrato/assinar" % nome,
                   {"parte": "cliente", "nome": "Cliente", "cpf": "11111111111"})
    assert st == 400 and "medição" in (d.get("erro", "").lower()), (st, d)
```

> Path/payload confirmados: `POST /api/projetos/<nome>/contrato/assinar` com `{parte, nome, cpf}` (`main.py:6266-6283`). O teste acima já usa o contrato real. Se já existir um helper de assinatura em `tests/`, reuse-o.

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_af_gate_data_entrega.py::test_assinatura_exige_previsao_medicao -v`
Expected: FAIL — hoje a 2ª assinatura passa só com `data_entrega`.

- [ ] **Step 3: Estender o guard**

Substituir `main.py:6310-6315`:

```python
                    if _completaria:
                        _pm = db.get(Projeto, nome_safe)
                        if _pm is None or _pm.data_entrega is None or _pm.previsao_medicao is None:
                            self.send_json({"ok": False,
                                "erro": "Defina a data de entrega esperada E a previsão de medição antes de finalizar a assinatura."}, code=400)
                            return
```

- [ ] **Step 4: Rodar e ver passar + caçar regressões de fluxo de assinatura**

Run: `python3 -m pytest tests/test_af_gate_data_entrega.py -v`
Depois: `python3 -m pytest -q`. Se algum teste que COMPLETA a assinatura (loja+cliente) quebrar por falta de `previsao_medicao`, ajuste esse teste para definir `previsao_medicao` no `Projeto` antes de assinar (mesmo padrão do `_prep` em `test_af_gate_data_entrega.py`, que já define `data_entrega`). Liste os testes ajustados.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_af_gate_data_entrega.py
git commit -m "feat(assinatura): 2ª assinatura exige data de entrega E previsão de medição

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: UI mínima no card do Contrato (previsão de medição + venda programada + override)

**Files:**
- Modify: `static/index.html:13746-13755` (bloco "Data de entrega esperada")
- Modify: `static/index.html:13687-13704` (`salvarDataEntrega`)
- Verificação: manual no navegador (não há teste JS)

- [ ] **Step 1: Adicionar os campos no card**

Substituir o bloco `static/index.html:13746-13755` por (mantém o input de data de entrega, adiciona previsão de medição + checkbox venda programada):

```html
    <div style="border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:14px">
      <div style="font-size:var(--fs-sm);font-weight:600;margin-bottom:4px">Datas do acordo (cliente)</div>
      <div style="font-size:var(--fs-xs);color:var(--text-3);margin-bottom:8px">Previsão de medição e expectativa de entrega — obrigatórias para finalizar a assinatura. A folga é medida do trecho medição→entrega.</div>
      <div style="display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap">
        <label style="font-size:var(--fs-xs);color:var(--text-3)">Previsão de medição<br>
          <input type="date" id="ct-previsao-medicao" value="${(contrato.previsao_medicao||'').slice(0,10)}"
            style="height:var(--control-h-sm);padding:0 var(--sp-3);background:var(--surface);border:1px solid var(--field-border);border-radius:var(--radius-sm);color:var(--text);font-family:var(--font-mono);font-size:var(--fs-body)"></label>
        <label style="font-size:var(--fs-xs);color:var(--text-3)">Expectativa de entrega<br>
          <input type="date" id="ct-data-entrega" value="${(contrato.data_entrega||'').slice(0,10)}"
            style="height:var(--control-h-sm);padding:0 var(--sp-3);background:var(--surface);border:1px solid var(--field-border);border-radius:var(--radius-sm);color:var(--text);font-family:var(--font-mono);font-size:var(--fs-body)"></label>
        <label style="font-size:var(--fs-xs);display:flex;align-items:center;gap:4px">
          <input type="checkbox" id="ct-venda-programada" ${contrato.venda_programada ? 'checked' : ''}> Venda programada</label>
        <button class="btn-ciclo" onclick="salvarDataEntrega()"><i class="ti ti-calendar-check"></i> Validar</button>
      </div>
      <div style="margin-top:6px"><span id="ct-entrega-result" style="font-size:var(--fs-xs)"></span></div>
    </div>
```

- [ ] **Step 2: Reescrever `salvarDataEntrega`**

Substituir `static/index.html:13687-13704` por:

```javascript
async function salvarDataEntrega(autorizacao){
  if(!projetoAtivo) return;
  const data  = (document.getElementById('ct-data-entrega')||{}).value || '';
  const med   = (document.getElementById('ct-previsao-medicao')||{}).value || '';
  const prog  = !!(document.getElementById('ct-venda-programada')||{}).checked;
  const res = document.getElementById('ct-entrega-result');
  const setRes = (txt, cor) => { if(res){ res.innerHTML = txt; res.style.color = cor; } };
  if(!med){ setRes('Informe a previsão de medição.', 'var(--err)'); return; }
  if(!data){ setRes('Informe a expectativa de entrega.', 'var(--err)'); return; }
  const payload = { data_entrega: data, previsao_medicao: med, venda_programada: prog };
  if(autorizacao){ payload.login = autorizacao.login; payload.senha = autorizacao.senha; }
  try {
    const j = await fetch('/api/projetos/'+encodeURIComponent(projetoAtivo.nome_safe)+'/data-entrega',
      { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload) }).then(r=>r.json());
    if(!j.ok){ setRes(esc(j.erro||'Erro'), 'var(--err)'); return; }
    const fm = (j.folga_min!=null) ? (j.folga_min+'d') : '—';
    if(j.cabe){ setRes('&#x2713; Cabe (folga do trecho medição→entrega: '+fm+').', 'var(--ok)'); return; }
    // não cabe: oferece registro com autorização gerencial (Gerente+)
    let msg = '&#x26A0; Não cabe (folga '+fm+'). ';
    if(_podeAutorizarFront && _podeAutorizarFront()){
      msg += '<button class="btn-ciclo" style="font-size:var(--fs-xs);border-color:var(--cancel);color:var(--cancel)" onclick="autorizarDataEntrega()">Registrar com autorização</button>';
    } else {
      msg += 'Requer autorização de Gerente/Diretor.';
    }
    setRes(msg, 'var(--err)');
  } catch(e){ setRes('Erro de rede.', 'var(--err)'); }
}

function autorizarDataEntrega(){
  const login = prompt('Login do autorizador (Gerente/Diretor):'); if(!login) return;
  const senha = prompt('Senha:'); if(!senha) return;
  salvarDataEntrega({ login: login.trim(), senha: senha.trim() });
}
```

> `_podeAutorizarFront()` confirmado no frontend (`static/index.html:11752`, usado nos gates gerenciais). O backend valida de qualquer modo, então o gate no front é só cosmético (esconde o botão de quem não pode).

- [ ] **Step 3: Remover o `cronogramaProprioEmBreve` órfão (se ficou sem uso)**

Verifique se `cronogramaProprioEmBreve` (linha ~13705) ainda é referenciado em algum lugar (`grep -n cronogramaProprioEmBreve static/index.html`). Se não houver mais chamador (o botão "Cronograma próprio" saiu do fluxo), **deixe a função como está** (não é escopo desta fatia removê-la) — apenas confirme que nada quebrou.

- [ ] **Step 4: Verificação de sintaxe JS**

Extrair o `<script>` e rodar `node --check`, ou (mais simples) confirmar visualmente que não há erro de template string. Documente no relatório.

- [ ] **Step 5: Verificação manual (descrever no relatório; requer reiniciar o servidor por causa das mudanças em `main.py`)**

Roteiro: abrir o card do Contrato → preencher previsão de medição + expectativa de entrega folgadas → Validar → "Cabe (folga …)"; datas apertadas → "Não cabe" + botão "Registrar com autorização" (logado como Gerente+) → informar login/senha → grava. Sair e voltar ao projeto → os dois campos + checkbox reexibem os valores. Tentar finalizar a assinatura sem previsão de medição → bloqueio.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat(contrato/ui): card com previsão de medição + venda programada + fluxo de override na folga

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Suíte verde + DEV_LOG

- [ ] **Step 1: Suíte inteira verde**

Run: `python3 -m pytest -q`
Expected: tudo verde. Investigar qualquer regressão (candidatos: testes de fluxo de assinatura que agora exigem `previsao_medicao` — ver Task 5).

- [ ] **Step 2: Atualizar o DEV_LOG**

Acrescentar nova seção `## Sessão N` no `DEV_LOG.md` (N = próxima disponível; conferir com `grep -n "## Sessão" DEV_LOG.md | head`) resumindo a Fatia 2 (colunas medição/venda programada, folga medição→entrega, bloqueio+override gerencial, trava da assinatura pelas duas datas, UI mínima de entrada). Atualizar o ponteiro `## ⏸️ ESTADO ATUAL` no topo com a data corrente e o estado da branch. Commit:

```bash
git add DEV_LOG.md
git commit -m "docs(devlog): Sessão N — Fatia 2 (datas da assinatura + folga medição→entrega + enforcement)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

- [ ] **Step 3: Reingerir o grafo MCP** (após merge na main, no fecho da frente)

`curl -s -X POST http://localhost:8767/ingest/all` — só quando a fatia for para a `main` (passo 6 do "Fechar uma frente").

---

## Self-review (cobertura da spec)

- **§1 colunas + persistência:** Tasks 1, 3. ✓
- **§3 folga medição→entrega:** Task 2 (função) + Task 3 (uso). ✓
- **§4 bloqueio + override gerencial + trava de assinatura:** Tasks 3, 5. ✓
- **UI de entrada (deployabilidade):** Task 6. ✓
- **Fora de escopo confirmado:** prazo contratual + marcadores (Fatia 3), sinal de atraso + UI final (Fatia 4). ✓
- **Regressões conhecidas tratadas:** testes de `data-entrega` reescritos (Task 3), testes de fluxo de assinatura (Task 5). ✓
