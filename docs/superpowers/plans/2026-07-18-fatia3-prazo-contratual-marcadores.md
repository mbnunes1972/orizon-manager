# Fatia 3 — Prazo Contratual (dias úteis) + Marcadores no Contrato — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para executar task-a-task. Steps usam checkbox (`- [ ]`).

**Goal:** Levar ao documento do contrato as datas do acordo e o prazo contratual — via marcadores automáticos — e introduzir o prazo contratual em **dias úteis** como parâmetro da loja.

**Architecture:** Novo parâmetro `prazo_contratual_dias_uteis` (default 50) na config da loja. Helper puro `somar_dias_uteis` em `mod_cronograma` (seg–sex, sem feriados). Quatro marcadores novos entram em `mod_marcadores.CATALOGO` **e** `mod_contrato._montar_mapping` no **mesmo commit** (teste anti-drift trava a paridade). O `ctx` da geração do contrato passa a carregar os campos do projeto (medição/entrega/venda programada) + o prazo contratual. Aviso de coerência (não bloqueio) na aba Config → Cronograma.

**Tech Stack:** Python puro (SQLAlchemy, http.server), WeasyPrint (contrato PDF), pytest/TDD, frontend `static/index.html`.

**Escopo (spec §5):** parâmetro do prazo, `somar_dias_uteis`, 4 marcadores, injeção no `ctx`, aviso de coerência. **Fora:** distribuidora Orizon Soluções / 2ª CONTRATADA (spec `2026-07-16-segmentacao-distribuidora-contrato`), feriados no cálculo de dias úteis, Agenda Global, IA.

**Referência:** `docs/superpowers/specs/ciclo/2026-07-17-ancora-entrega-folga-venda-programada-design.md` (§5) — e o teste anti-drift `tests/test_marcadores.py` (`test_catalogo_cobre_todo_marcador_do_mapping` / `test_catalogo_nao_inventa_marcador`).

---

## File Structure

- `mod_provisoes.py` — `config_financeira_default` ganha `prazo_contratual_dias_uteis` (int, default 50); `validar_config_financeira` valida (>0).
- `mod_cronograma.py` — novo `somar_dias_uteis(data, n)` (puro) + helper de coerência padrão × prazo.
- `mod_marcadores.py` — 4 verbetes novos no `CATALOGO` (escopo `documento`).
- `mod_contrato.py` — `_montar_mapping` produz os 4 marcadores a partir do `ctx`; o builder do `ctx` (`_montar_html_contrato`, ~linha 747) recebe/expõe os campos do projeto + prazo.
- `main.py` — onde o contrato é gerado, injeta no `ctx` os dados do `Projeto` (data_entrega/previsao_medicao/venda_programada) + `prazo_contratual_dias_uteis` da loja.
- `static/index.html` — aba Config → Cronograma: aviso quando o total do padrão (dias corridos) não cabe no prazo contratual (dias úteis).
- Testes: `tests/test_cronogramas_dois.py` (somar_dias_uteis + coerência), `tests/test_marcadores.py` (anti-drift já cobre os novos; + render), `tests/test_contrato*.py` (marcadores no PDF).

---

## Task 1: Parâmetro `prazo_contratual_dias_uteis` na config da loja

**Files:** `mod_provisoes.py` (`config_financeira_default` + `validar_config_financeira`); Test: `tests/test_provisoes.py`.

- [ ] **Step 1: teste falhando** — em `tests/test_provisoes.py`:
```python
def test_default_tem_prazo_contratual_dias_uteis():
    import mod_provisoes
    cfg = mod_provisoes.config_financeira_default()
    assert cfg.get("prazo_contratual_dias_uteis") == 50
```
- [ ] **Step 2: rodar e ver falhar:** `python3 -m pytest tests/test_provisoes.py::test_default_tem_prazo_contratual_dias_uteis -v`
- [ ] **Step 3: implementar** — em `mod_provisoes.config_financeira_default()`, adicionar a chave (ao lado de `cronograma_formato`):
```python
        # Prazo contratual (Fatia 3): promessa formal em DIAS ÚTEIS a partir da assinatura.
        "prazo_contratual_dias_uteis": 50,
```
E em `validar_config_financeira`, validar `> 0` (mensagem pt-BR) se a chave estiver presente. **Atenção:** `tests/test_provisoes.py::test_default_tem_estrutura_completa` asserta o conjunto de chaves — adicionar a nova chave lá também (mesmo commit).
- [ ] **Step 4: rodar e ver passar** + `python3 -m pytest tests/test_provisoes.py -q`.
- [ ] **Step 5: commit** — `feat(config): prazo_contratual_dias_uteis (default 50) na config da loja`.

---

## Task 2: `somar_dias_uteis` (puro) em `mod_cronograma`

**Files:** `mod_cronograma.py` (nova função); Test: `tests/test_cronogramas_dois.py`.

- [ ] **Step 1: testes falhando** — em `tests/test_cronogramas_dois.py`:
```python
def test_somar_dias_uteis_pula_fim_de_semana():
    # 2026-07-01 é quarta. +3 dias úteis = qui, sex, seg → 2026-07-06 (segunda).
    assert mcr.somar_dias_uteis(datetime(2026, 7, 1), 3) == datetime(2026, 7, 6)

def test_somar_dias_uteis_zero_no_mesmo_dia():
    assert mcr.somar_dias_uteis(datetime(2026, 7, 1), 0) == datetime(2026, 7, 1)

def test_somar_dias_uteis_sexta_mais_um_vai_segunda():
    # 2026-07-03 é sexta. +1 dia útil = segunda 2026-07-06.
    assert mcr.somar_dias_uteis(datetime(2026, 7, 3), 1) == datetime(2026, 7, 6)
```
> Confirme os dias da semana antes de codar (2026-07-01 = quarta, 2026-07-03 = sexta). Ajuste se divergir.
- [ ] **Step 2: rodar e ver falhar:** `python3 -m pytest tests/test_cronogramas_dois.py -k somar_dias_uteis -v`
- [ ] **Step 3: implementar** — em `mod_cronograma.py`:
```python
def somar_dias_uteis(data, n):
    """Avança `n` dias ÚTEIS (seg–sex; sem feriados) a partir de `data`. n=0 → a própria data.
    Único prazo do sistema em dias úteis (o prazo contratual, Fatia 3); o resto usa dias corridos."""
    from datetime import timedelta
    d = data
    passos = 0
    while passos < n:
        d = d + timedelta(days=1)
        if d.weekday() < 5:   # 0=seg .. 4=sex
            passos += 1
    return d
```
- [ ] **Step 4: rodar e ver passar** + suíte inteira `python3 -m pytest -q`.
- [ ] **Step 5: commit** — `feat(cronograma): somar_dias_uteis (prazo contratual em dias úteis)`.

---

## Task 3: Aviso de coerência padrão × prazo contratual (Config → Cronograma)

**Files:** `mod_cronograma.py` (helper puro); `static/index.html` (aba Config → Cronograma, `cfgCronogramaRender`); Test: `tests/test_cronogramas_dois.py`.

- [ ] **Step 1: teste falhando** — helper que compara datas resultantes (padrão corrido × prazo em dias úteis) a partir de um D0:
```python
def test_cabe_no_prazo_contratual():
    # Σ durações do padrão (corridos) vs prazo em dias úteis, comparando datas a partir de D0.
    cfg = {"cronograma_formato": 2, "cronograma_padrao": [
        {"codigo": "8", "prazo_dias": 2}, {"codigo": "16", "prazo_dias": 5}], "prazo_contratual_dias_uteis": 50}
    assert mcr.padrao_cabe_no_prazo_contratual(cfg, datetime(2026, 7, 1)) is True
    cfg2 = dict(cfg); cfg2["prazo_contratual_dias_uteis"] = 2
    assert mcr.padrao_cabe_no_prazo_contratual(cfg2, datetime(2026, 7, 1)) is False
```
- [ ] **Step 2: rodar e ver falhar.**
- [ ] **Step 3: implementar** `padrao_cabe_no_prazo_contratual(cfg, d0)` em `mod_cronograma`:
```python
def padrao_cabe_no_prazo_contratual(cfg, d0):
    """True se a data de ENTREGA pelo Cronograma Padrão (d0 + Σ durações corridas) cabe na data-limite
    contratual (d0 + prazo_contratual_dias_uteis, em dias úteis). Aviso, não bloqueio."""
    total = sum(f["prazo_dias"] for f in cronograma_padrao(cfg))
    from datetime import timedelta
    entrega_padrao = d0 + timedelta(days=total)
    limite = somar_dias_uteis(d0, int((cfg or {}).get("prazo_contratual_dias_uteis") or 50))
    return entrega_padrao <= limite
```
- [ ] **Step 4: rodar e ver passar** + suíte.
- [ ] **Step 5: frontend** — em `cfgCronogramaRender` (static/index.html), ao renderizar/salvar o padrão, exibir aviso (não bloqueia salvar) quando o total do padrão não couber no prazo contratual. Usa os valores já carregados em `_cfgFin` (cronograma_padrao + prazo_contratual_dias_uteis). `node --check` do script.
- [ ] **Step 6: commit** — `feat(config): aviso quando o Cronograma Padrão não cabe no prazo contratual`.

---

## Task 4: Quatro marcadores novos (CATALOGO + _montar_mapping, anti-drift)

**Files:** `mod_marcadores.py` (CATALOGO); `mod_contrato.py` (`_montar_mapping` + builder do `ctx`); `main.py` (injeta dados do projeto no `ctx`); Test: `tests/test_marcadores.py`.

- [ ] **Step 1: entender o anti-drift** — `tests/test_marcadores.py::test_catalogo_cobre_todo_marcador_do_mapping` e `::test_catalogo_nao_inventa_marcador` exigem paridade CATALOGO × _montar_mapping. Os 4 marcadores entram nos DOIS no mesmo commit.
- [ ] **Step 2: adicionar ao CATALOGO** (`mod_marcadores.py`, seção `documento`):
```python
    "DATA_PREVISTA_ENTREGA": {"rotulo": "Data prevista de entrega (expectativa)", "escopo": "documento"},
    "PREVISAO_MEDICAO":      {"rotulo": "Previsão de medição",                    "escopo": "documento"},
    "PRAZO_CONTRATUAL":      {"rotulo": "Prazo contratual (dias úteis)",          "escopo": "documento"},
    "VENDA_PROGRAMADA":      {"rotulo": "Venda programada (observação)",          "escopo": "documento"},
```
- [ ] **Step 3: produzir no `_montar_mapping`** (`mod_contrato.py`) — a partir de `ctx`:
```python
        "DATA_PREVISTA_ENTREGA": ctx.get("data_prevista_entrega", "") or "",
        "PREVISAO_MEDICAO":      ctx.get("previsao_medicao", "") or "",
        "PRAZO_CONTRATUAL":      ctx.get("prazo_contratual", "") or "",
        "VENDA_PROGRAMADA":      ctx.get("venda_programada_txt", "") or "",
```
- [ ] **Step 4: alimentar o `ctx`** — no builder do `ctx` (`mod_contrato.py:747`, `_montar_html_contrato`) e/ou no CHAMADOR (main.py, onde o contrato é gerado). O chamador tem o `Projeto`; passar:
  - `data_prevista_entrega` = data_entrega formatada (dd/mm/aaaa) ou "".
  - `previsao_medicao` = previsao_medicao formatada ou "".
  - `prazo_contratual` = `"%d dias úteis a partir da assinatura" % prazo` (do `prazo_contratual_dias_uteis` da loja).
  - `venda_programada_txt` = texto da observação quando `venda_programada` é 1, senão "".
  > **Confirme** o ponto exato onde o contrato é gerado em `main.py` (grep `gerar_pdf_contrato`/`_montar_html_contrato`) e como o `Projeto` chega lá; threade os campos pelo `ctx` sem quebrar as chamadas existentes (o builder do ctx pode ganhar um param opcional `projeto`/`extras`).
- [ ] **Step 5: rodar o anti-drift** — `python3 -m pytest tests/test_marcadores.py -q` (deve passar; os 4 marcadores agora existem nos dois lados). Adicionar um teste de render:
```python
def test_novos_marcadores_saem_no_mapping():
    ctx = {"loja": {"nome": "L", "cnpj": "1", "cidade": "C"},
           "data_prevista_entrega": "01/01/2028", "previsao_medicao": "01/06/2027",
           "prazo_contratual": "50 dias úteis a partir da assinatura", "venda_programada_txt": "Venda programada."}
    m = mod_contrato._montar_mapping(ctx, {})
    assert m["DATA_PREVISTA_ENTREGA"] == "01/01/2028"
    assert m["VENDA_PROGRAMADA"] == "Venda programada."
```
- [ ] **Step 6: rodar suíte inteira** `python3 -m pytest -q` (o `_html_corpo` já ESCAPA os valores — sem risco de HTML injetado). Commit — `feat(contrato): marcadores DATA_PREVISTA_ENTREGA/PREVISAO_MEDICAO/PRAZO_CONTRATUAL/VENDA_PROGRAMADA`.

---

## Task 5: Suíte verde (SQLite + Postgres) + DEV_LOG

- [ ] **Step 1:** `python3 -m pytest -q` (SQLite) verde.
- [ ] **Step 2:** `TEST_DATABASE_URL="postgresql+psycopg2://orizon:senha_local_qualquer@localhost/orizon_test" python3 -m pytest -q` — validar em Postgres também (o `prazo_contratual_dias_uteis` é config JSON, sem coluna nova; nenhuma migração de schema esperada). Anotar 1 e2e flaky conhecido (timeout de PDF), se reaparecer.
- [ ] **Step 3:** DEV_LOG — nova `## Sessão N` resumindo a Fatia 3 (prazo contratual em dias úteis, 4 marcadores, aviso de coerência). Commit.

---

## Self-review (cobertura da spec §5)

- **Parâmetro prazo contratual (dias úteis, configurável, default 50):** Task 1. ✓
- **`somar_dias_uteis` (só o prazo contratual em dias úteis):** Task 2. ✓
- **4 marcadores no contrato (anti-drift):** Task 4. ✓
- **Aviso de coerência padrão × prazo:** Task 3. ✓
- **Fora de escopo confirmado:** distribuidora/2ª CONTRATADA, feriados. ✓

## Riscos / pontos de atenção

1. **Threading do `Projeto` no `ctx`** (Task 4 Step 4) — é o ponto menos mapeado; o executor confirma o chamador em `main.py` e evita quebrar as assinaturas de `_montar_html_contrato`/`gerar_pdf_contrato` (param opcional).
2. **Data-limite contratual monitorada** (assinatura + N dias úteis) — nesta fatia o marcador `PRAZO_CONTRATUAL` é a CLÁUSULA ("N dias úteis a partir da assinatura"); a data-limite concreta (calculada no D0 da assinatura) para monitoramento interno pode entrar aqui como campo do projeto ou ficar para a frente de monitoramento (Fatia 4/Agenda). Decidir no início da Task 4.
3. **Template do contrato** — os marcadores só aparecem no PDF se o corpo do modelo os referenciar (`[DATA_PREVISTA_ENTREGA]` etc.). Cabe ao lojista inserir no modelo; documentar no fecho.
