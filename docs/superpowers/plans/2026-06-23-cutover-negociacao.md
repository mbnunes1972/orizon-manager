# Cutover do Motor de Negociação (Fase B) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer a tela de negociação e o modal usarem o motor `mod_negociacao` (preview ao vivo) e persistirem `valor_total = Val_Cont` / `valor_liquido = Val_Liq`, retirando o cálculo legado do frontend.

**Architecture:** Um endpoint de **preview** (puro, sem gravar) e um helper de **recálculo** (grava) compartilham UM cálculo do motor (`_negociacao_breakdown`). O frontend chama o preview (debounce) para exibir e repõe o `valorAvista` (que alimenta o pagamento) para o `VAVO` do motor. O save passa a gravar `valor_total`/`valor_liquido` no backend (autoritativo). Contrato reflete automaticamente.

**Tech Stack:** Python 3 (stdlib http.server, SQLAlchemy, sqlite), frontend HTML/JS vanilla em `static/index.html`, pytest. No WSL é `python3` (não `python`).

## Global Constraints

- **Fonte única:** o cálculo do motor vive no backend (`mod_negociacao` + `_negociacao_breakdown`); o frontend **nunca** recalcula a negociação — só exibe o preview. NÃO portar a fórmula para JS.
- **`mod_fin` reusado como está:** `valor_total = total_cliente` (da modalidade de pagamento já calculada com o `VAVO` do motor); `Cust_Fin = valor_total − VAVO`; `Val_Cont = valor_total`. À vista (sem modalidade) ⇒ `Cust_Fin = 0`, `valor_total = VAVO`.
- **`valor_liquido = Val_Liq`** do motor (hoje guardava o bruto — passa a ficar correto).
- **Limite de desconto: 35% hardcoded** (`_LIMITE_DESC_TOTAL`), checado contra o `%Desc_Tot` do motor.
- **Backend autoritativo:** o `PATCH /api/orcamentos/<id>` deixa de aceitar `valor_total`/`valor_liquido` do frontend (recalcula).
- **Contrato assinado é intocável:** `_contrato_assinado` já bloqueia edição; não recalcular orçamento de contrato assinado.
- Chaves do motor (siglas) inalteradas: `VBVO, CFO, VBNO, VAVO, Com_Arq, Pro_Fid, Cust_Ad, Val_Liq, Desc_Tot, Markup, Cust_Fin, Val_Cont, Prov_Imp` + `ambientes[].{VBVA,CFA,VBNA,VAVA}`.
- `python3 -m pytest`. Commits frequentes, um por task. `git add` só dos arquivos da task.

---

### Task 1: Branch + golden-master baseline

**Files:**
- Create: `scripts/snapshot_cutover.py`
- Create: `tests/golden/cutover_baseline.json`

**Interfaces:**
- Produces: baseline commitado com `valor_total`/`valor_liquido` LEGADOS de todos os orçamentos, para o relatório old×new após o cutover.

- [ ] **Step 1: Criar a branch a partir do main**

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout -b feat/cutover-negociacao
git branch --show-current   # feat/cutover-negociacao
```

- [ ] **Step 2: Script de fotografia (legado)**

```python
# scripts/snapshot_cutover.py
"""Fotografa valor_total/valor_liquido LEGADOS de todos os orçamentos antes do cutover."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    db = get_session()
    out = [{"id": o.id, "projeto": o.projeto_id, "ordem": o.ordem,
            "valor_total": o.valor_total, "valor_liquido": o.valor_liquido}
           for o in db.query(Orcamento).order_by(Orcamento.id).all()]
    db.close()
    path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "cutover_baseline.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{len(out)} orçamentos -> {path}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Gerar a baseline**

Run: `python3 scripts/snapshot_cutover.py`
Expected: imprime "N orçamentos -> .../cutover_baseline.json" e cria o arquivo.

- [ ] **Step 4: Commit**

```bash
git add scripts/snapshot_cutover.py tests/golden/cutover_baseline.json
git commit -m "chore(cutover): golden-master baseline dos valores legados"
```

---

### Task 2: `_negociacao_breakdown` + endpoint de preview (B1 backend)

**Files:**
- Modify: `main.py` (novo helper `_negociacao_breakdown`; novo handler `POST /api/orcamentos/<id>/negociacao-preview`)
- Test: `tests/test_cutover_e2e.py` (criar)

**Interfaces:**
- Consumes: `mod_negociacao.calcular_orcamento`; modelos `Orcamento`/`OrcamentoAmbiente`/`PoolAmbiente`/`Projeto`; `mod_tenancy.escopo_operacional`, `_obj_da_loja`, `get_usuario_sessao`.
- Produces: `_negociacao_breakdown(orc, db, params=None, desc_orc=None, descontos_amb=None, total_cliente=None) -> dict` (sem gravar) com chaves do motor + `"ambientes"`. Endpoint `POST /api/orcamentos/<id>/negociacao-preview`.

- [ ] **Step 1: Escrever o teste E2E que falha**

```python
# tests/test_cutover_e2e.py
def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c

def test_preview_devolve_valores_do_motor(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, body = c.post(f"/api/orcamentos/{oid}/negociacao-preview", {})
    assert st == 200 and body["ok"]
    s = body["sombra"]
    # chaves da cadeia completa presentes
    for k in ("VBVO", "VAVO", "Val_Liq", "Markup", "Desc_Tot", "Com_Arq", "Pro_Fid", "Cust_Ad", "Val_Cont"):
        assert k in s
    assert "ambientes" in body

def test_preview_fora_do_escopo_404(http_client_factory, seed):
    c = _login(http_client_factory, "dir_l2")           # loja 2
    st, body = c.post(f"/api/orcamentos/{seed['orcamento_l1_id']}/negociacao-preview", {})
    assert st == 404 and body.get("ok") is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cutover_e2e.py -v`
Expected: FAIL (rota inexistente).

- [ ] **Step 3: Implementar o helper `_negociacao_breakdown`**

Em `main.py`, junto aos helpers de orçamento (perto de `_sombra_dict`), adicionar:

```python
def _negociacao_breakdown(orc, db, params=None, desc_orc=None, descontos_amb=None, total_cliente=None):
    """Calcula a cadeia do motor para um orçamento, SEM gravar. `params`/`desc_orc`/
    `descontos_amb` opcionais sobrepõem o salvo (estado em edição do modal). `total_cliente`
    (da modalidade via mod_fin) define o Cust_Fin; None ⇒ à vista (Cust_Fin=0)."""
    import mod_negociacao
    proj = db.query(Projeto).filter_by(nome_safe=orc.projeto_id).first()
    if params is None:
        params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
    if desc_orc is None:
        desc_orc = orc.desconto_pct or 0.0
    descontos_amb = descontos_amb or {}
    ambs = []
    for lk in db.query(OrcamentoAmbiente).filter_by(orcamento_id=orc.id).all():
        pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
        if pa:
            d_amb = descontos_amb.get(str(lk.pool_ambiente_id),
                                      descontos_amb.get(lk.pool_ambiente_id,
                                                        lk.desconto_individual_pct or 0.0))
            ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                         "desc_amb_pct": float(d_amb or 0.0)})
    d0 = mod_negociacao.calcular_orcamento(ambs, params, desc_orc)
    if total_cliente is None:
        cust_fin = 0.0
    else:
        cust_fin = max(0.0, float(total_cliente) - d0["VAVO"])
    d = mod_negociacao.calcular_orcamento(ambs, params, desc_orc, cust_fin=cust_fin)
    return d
```

- [ ] **Step 4: Implementar o endpoint de preview**

Em `main.py`, no do_POST, junto aos handlers de orçamento, adicionar:

```python
            m_prev = _re.match(r"^/api/orcamentos/(\d+)/negociacao-preview$", path)
            if m_prev:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401)
                    return
                req = json.loads(body) if body else {}
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja_id, _err = mod_tenancy.escopo_operacional(ator)
                    if _err:
                        self.send_json({"ok": False, "erro": _err}, code=403)
                        return
                    orc = _obj_da_loja(db, Orcamento, int(m_prev.group(1)), loja_id)
                    if orc is None:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404)
                        return
                    pag = req.get("pagamento") or {}
                    d = _negociacao_breakdown(
                        orc, db,
                        params=req.get("params"), desc_orc=req.get("desc_orc"),
                        descontos_amb=req.get("descontos_amb"),
                        total_cliente=pag.get("total_cliente"))
                    self.send_json({"ok": True, "sombra": d, "ambientes": d.get("ambientes", [])})
                finally:
                    db.close()
                return
```

> Nota: confirme via grep o nome do alias de regex no do_POST (`_re` ou `re`) e use o mesmo. `_negociacao_breakdown` retorna o dict do motor (já inclui `"ambientes"`).

- [ ] **Step 5: Rodar e ver passar**

Run: `python3 -m pytest tests/test_cutover_e2e.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_cutover_e2e.py
git commit -m "feat(cutover): endpoint de preview da negociacao (motor, sem gravar)"
```

---

### Task 3: `_recalcular_orcamento` + persistência autoritativa (B2 backend)

**Files:**
- Modify: `main.py` (helper `_recalcular_orcamento`; usar no `POST /api/orcamentos/<id>/margens` ~1996-2022 e no `PATCH /api/orcamentos/<id>` ~3622-3630)
- Test: `tests/test_cutover_e2e.py` (acrescentar)

**Interfaces:**
- Consumes: `_negociacao_breakdown` (Task 2).
- Produces: `_recalcular_orcamento(orc, db)` — grava colunas sombra + `valor_total = Val_Cont` + `valor_liquido = Val_Liq`. PATCH deixa de aceitar `valor_total`/`valor_liquido`.

- [ ] **Step 1: Escrever os testes E2E que falham**

```python
def test_save_margens_grava_valor_do_motor(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    st, _ = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 10})
    assert st == 200
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    # valor_liquido == Val_Liq do motor (== val_liq sombra); valor_total == Val_Cont (== val_cont)
    assert abs((o.valor_liquido or 0) - (o.val_liq or 0)) < 0.02
    assert abs((o.valor_total or 0) - (o.val_cont or 0)) < 0.02
    db.close()

def test_patch_nao_aceita_valor_total_do_frontend(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l1")
    oid = seed["orcamento_l1_id"]
    c.patch(f"/api/orcamentos/{oid}", {"valor_total": 999999.0, "valor_liquido": 888888.0})
    db = app_db.get_session(); o = db.get(app_db.Orcamento, oid)
    assert (o.valor_total or 0) != 999999.0      # ignorado/recalculado
    db.close()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `python3 -m pytest tests/test_cutover_e2e.py -v`
Expected: FAIL (valor_total/valor_liquido ainda não vêm do motor; PATCH ainda aceita).

- [ ] **Step 3: Implementar `_recalcular_orcamento`**

Em `main.py`, junto a `_negociacao_breakdown`, adicionar:

```python
def _recalcular_orcamento(orc, db):
    """Recalcula a negociação pelo motor e GRAVA: colunas sombra + valor_total/valor_liquido.
    `valor_total` vem da modalidade (forma_pagamento.total_cliente, já calculada com o VAVO);
    à vista ⇒ valor_total = VAVO. NÃO grava se contrato assinado (chamador já checa)."""
    total_cliente = None
    try:
        fp = json.loads(orc.forma_pagamento) if orc.forma_pagamento else None
        if isinstance(fp, dict) and fp.get("total_cliente"):
            total_cliente = float(fp["total_cliente"])
    except Exception:
        total_cliente = None
    d = _negociacao_breakdown(orc, db, total_cliente=total_cliente)
    orc.vbvo, orc.cfo, orc.vbno, orc.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
    orc.cust_ad, orc.val_liq = d["Cust_Ad"], d["Val_Liq"]
    orc.com_arq_orc, orc.pro_fid_orc = d["Com_Arq"], d["Pro_Fid"]
    orc.desc_tot_pct, orc.markup, orc.prov_imp = d["Desc_Tot"], d["Markup"], d["Prov_Imp"]
    orc.cust_fin, orc.val_cont = d["Cust_Fin"], d["Val_Cont"]
    # persistência autoritativa (cutover):
    orc.valor_total = d["Val_Cont"]
    orc.valor_liquido = d["Val_Liq"]
```

- [ ] **Step 4: Usar no save de margens**

Em `main.py`, no `POST /api/orcamentos/<id>/margens`, substituir o bloco sombra inline (do `try: import mod_negociacao` até `orc.val_cont = d["Val_Cont"]`, ~1996-2016) por:

```python
                try:
                    _recalcular_orcamento(orc, db)
                    db.commit()
                except Exception as _e:
                    db.rollback()
                    print("[CUTOVER] falha ao recalcular orçamento:", _e)
```

(O `send_json({"ok": True, "margens": atual, "sombra": _sombra_dict(orc)})` logo abaixo permanece.)

- [ ] **Step 5: Recalcular no PATCH e parar de aceitar valores do frontend**

Em `main.py`, no `PATCH /api/orcamentos/<id>` (~3622-3630), substituir o bloco que aceita `valor_total`/`valor_liquido`/`forma_pagamento`/`negociacao_json` por:

```python
                    # backend autoritativo: NÃO aceita valor_total/valor_liquido do frontend
                    if "forma_pagamento" in req:
                        orc.forma_pagamento = req["forma_pagamento"] or None
                    if "negociacao_json" in req:
                        orc.negociacao_json = req["negociacao_json"] or None
                    orc.updated_at = datetime.utcnow()
                    db.flush()                      # forma_pagamento disponível para o recálculo
                    try:
                        _recalcular_orcamento(orc, db)
                    except Exception as _e:
                        print("[CUTOVER] recalculo no PATCH falhou:", _e)
                    db.commit()
```

- [ ] **Step 6: Rodar e ver passar + suíte**

Run: `python3 -m pytest tests/test_cutover_e2e.py -v`
Expected: PASS.
Run: `python3 -m pytest -q`
Expected: PASS (sem regressão; testes que dependiam do PATCH aceitar valores podem precisar de ajuste — se algum quebrar por isso, ajuste a expectativa para o novo comportamento autoritativo).

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_cutover_e2e.py
git commit -m "feat(cutover): persistencia autoritativa (valor_total/valor_liquido do motor)"
```

---

### Task 4: Frontend consome o preview (B1+B2 display)

**Files:**
- Modify: `static/index.html` (`mpAtualizarApoio` ~5331, `renderTabelaNeg`, o `valorAvista` que alimenta o pagamento ~3529-3565, o limite `_LIMITE_DESC_TOTAL` ~1846, `salvarValorNegociado`)

**Interfaces:**
- Consumes: `POST /api/orcamentos/<id>/negociacao-preview` (Task 2).
- Produces: a tela exibe os valores do motor; `valorAvista` = `VAVO` do preview; limite usa `%Desc_Tot`; save não envia `valor_total`/`valor_liquido`.

> **Sem harness JS** — verificação **manual** (passo final). Edições cirúrgicas; use Read para localizar cada ponto.

- [ ] **Step 1: Função de preview (fetch + cache)**

Adicionar em `static/index.html` (perto de `_orcSombra`):

```javascript
let _previewNeg = null;   // último resultado do motor (preview)
async function negPreview() {
  if (!_orcamentoAtivoId) return null;
  const params = (typeof coletarParametrosModal === 'function') ? coletarParametrosModal() : null;
  const body = {
    params: params,
    desc_orc: (typeof _descontoOrcamento !== 'undefined') ? _descontoOrcamento : undefined,
    descontos_amb: (typeof _descIndividual !== 'undefined') ? _descIndividual : undefined,
    pagamento: (typeof _formaPagamentoAtual !== 'undefined') ? _formaPagamentoAtual : undefined,
  };
  try {
    const r = await fetch(`/api/orcamentos/${_orcamentoAtivoId}/negociacao-preview`,
      { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const d = await r.json();
    _previewNeg = d.ok ? d.sombra : null;
    return _previewNeg;
  } catch (e) { console.warn('preview:', e); return null; }
}
```

> Nota: ajuste os nomes (`coletarParametrosModal`, `_descontoOrcamento`, `_descIndividual`, `_formaPagamentoAtual`) aos reais do arquivo — o objetivo é mandar o estado em edição. Se um campo não existir prontamente, omita (o backend cai no valor salvo).

- [ ] **Step 2: `mpAtualizarApoio` exibe o preview (debounced)**

Em `mpAtualizarApoio`, após o cálculo legado de apoio, chamar `negPreview()` (debounced) e preencher os campos do painel com o resultado do motor: `mp-a-avista`←`VAVO`, `mp-a-arq`←`Com_Arq`, `mp-a-fid`←`Pro_Fid`, `mp-a-liq`←`Val_Liq`, `mp-a-margem`←`Desc_Tot×100`. O `_mpRenderSombra` deixa de ser "HOJE×NOVO" e passa a mostrar só o motor (remover a coluna HOJE; manter a tabela completa). Debounce ~250ms para não disparar fetch a cada tecla.

- [ ] **Step 3: `valorAvista` (que alimenta o pagamento) vem do `VAVO`**

Localize onde `valorAvista`/`neg-avista` é calculado e enviado ao cálculo de pagamento (~3529-3565). Trocar a fonte: usar `_previewNeg.VAVO` como o à vista que vai para `/calcular_cartao` etc. Assim `total_cliente = mod_fin(VAVO do motor)` e o `valor_total` persistido (Task 3) fica correto.

- [ ] **Step 4: Limite de desconto usa `%Desc_Tot` do motor**

No `_verificarLimiteDescTotal` (~1846), trocar `_margemAtual` por `(_previewNeg ? _previewNeg.Desc_Tot*100 : _margemAtual)` na comparação com `_LIMITE_DESC_TOTAL` (35).

- [ ] **Step 5: `salvarValorNegociado` para de enviar `valor_total`/`valor_liquido`**

No payload do PATCH/save (`salvarValorNegociado`), remover as chaves `valor_total` e `valor_liquido` (o backend recalcula). Manter `forma_pagamento`/`negociacao_json`.

- [ ] **Step 6: Verificação manual no navegador**

Run: `python3 main.py` → `http://127.0.0.1:8765`
Passos: login diretor → abrir projeto/orçamento → tela de negociação: os valores (à vista, comissão, fidelidade, líquido, bruto negociado) refletem o motor ao vivo ao mexer nos parâmetros/descontos; escolher modalidade de pagamento usa o à vista do motor; salvar → reabrir → contrato mostra `valor_total`/`valor_liquido` do motor. O desconto total acima de 35% bloqueia.

- [ ] **Step 7: Commit**

```bash
git add static/index.html
git commit -m "feat(cutover): tela de negociacao e modal usam o motor (preview); para de enviar valores"
```

---

### Task 5: Golden-master old×new + DEV_LOG

**Files:**
- Create: `scripts/diff_cutover.py`
- Modify: `DEV_LOG.md`

- [ ] **Step 1: Script de comparação**

```python
# scripts/diff_cutover.py
"""Compara a baseline legada (tests/golden/cutover_baseline.json) com os valores atuais,
listando os orçamentos cujo valor_total/valor_liquido mudou com o cutover (e de quanto)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    base_path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "cutover_baseline.json")
    base = {b["id"]: b for b in json.load(open(base_path, encoding="utf-8"))}
    db = get_session()
    print("%-22s | %12s %12s | %12s %12s" % ("Projeto/Orç", "v_tot OLD", "v_tot NEW", "v_liq OLD", "v_liq NEW"))
    for o in db.query(Orcamento).order_by(Orcamento.id).all():
        b = base.get(o.id)
        if not b: continue
        if abs((b["valor_total"] or 0) - (o.valor_total or 0)) > 0.01 or \
           abs((b["valor_liquido"] or 0) - (o.valor_liquido or 0)) > 0.01:
            print("%-22s | %12.2f %12.2f | %12.2f %12.2f" % (
                (o.projeto_id + "/" + o.nome)[:22], b["valor_total"] or 0, o.valor_total or 0,
                b["valor_liquido"] or 0, o.valor_liquido or 0))
    db.close()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Documentar no DEV_LOG**

Acrescentar entrada ao `DEV_LOG.md`: cutover Fase B — preview + persistência autoritativa; `valor_total`/`valor_liquido` passam a vir do motor; contrato reflete; limite 35% sobre `%Desc_Tot`; baseline/diff em `scripts/`; Fase C (limpeza do legado) e o reset de teste (Task 6) são passos seguintes.

- [ ] **Step 3: Commit**

```bash
git add scripts/diff_cutover.py DEV_LOG.md
git commit -m "chore(cutover): script de diff old×new + DEV_LOG"
```

---

### Task 6: Reset de teste (B3 — operação pós-cutover)

**Files:**
- Create: `scripts/reset_para_teste.py`

> Operação **destrutiva** e à parte: só roda quando o usuário pedir, com backup antes. Cancela contratos, volta o ciclo de todos os projetos à fase de orçamento e recalcula tudo pelo motor — para testar o fluxo inteiro novo + transições de fase.

- [ ] **Step 1: Script de reset**

```python
# scripts/reset_para_teste.py
"""DESTRUTIVO: cancela contratos, volta o ciclo de TODOS os projetos à fase de orçamento e
recalcula valor_total/valor_liquido pelo motor. Faça backup do orizon.db antes."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento, Contrato, ContratoAssinatura, CicloEtapa

def main():
    db = get_session()
    # 1) cancelar contratos (assinaturas primeiro — FK)
    db.query(ContratoAssinatura).delete()
    n_ct = db.query(Contrato).delete()
    # 2) ciclo: remover etapas posteriores ao orçamento (mantém 1..4)
    n_et = db.query(CicloEtapa).filter(~CicloEtapa.etapa_codigo.in_(["1", "2", "3", "4"])).delete(synchronize_session=False)
    # 3) recalcular todos pelo motor (importa o helper do main)
    import main as _m
    for o in db.query(Orcamento).all():
        try:
            _m._recalcular_orcamento(o, db)
        except Exception as e:
            print("recalc falhou orc", o.id, e)
    db.commit(); db.close()
    print(f"reset: {n_ct} contratos removidos, {n_et} etapas pós-orçamento limpas, orçamentos recalculados.")

if __name__ == "__main__":
    main()
```

> Nota ao implementer: modelos confirmados — `Contrato`/`ContratoAssinatura`/`CicloEtapa` (coluna `etapa_codigo`), helper `_recalcular_orcamento` em `main.py`. Há PDFs em `CONTRATOS/` que o script NÃO remove (limpeza de disco opcional, à parte). NÃO execute o script nesta task — só crie e valide a sintaxe (`python3 -c "import ast; ast.parse(open('scripts/reset_para_teste.py').read())"`). A execução é decisão do usuário (com backup).

- [ ] **Step 2: Validar sintaxe e commit**

```bash
python3 -c "import ast; ast.parse(open('scripts/reset_para_teste.py').read())" && echo OK
git add scripts/reset_para_teste.py
git commit -m "chore(cutover): script de reset de teste (destrutivo, execucao manual)"
```

---

## Self-Review (autor)

**Cobertura do spec:**
- §1 preview endpoint → Task 2. ✔
- §2 persistência autoritativa (valor_total/valor_liquido do motor; PATCH não aceita) → Task 3. ✔
- §3 UI consome preview (avista←VAVO, displays, some HOJE) → Task 4. ✔
- §4 limite 35% sobre %Desc_Tot → Task 4 Step 4. ✔
- §5 contrato reflete automaticamente → consequência da Task 3 (lê valor_total/valor_liquido). ✔
- §6 golden-master + fases B1/B2/B3 → Task 1 (baseline), Task 5 (diff), Task 6 (reset B3). ✔
- §7 testes → Tasks 2/3 (E2E), Task 4 (manual), Task 5 (golden-master). ✔
- mod_fin reusado / 35% hardcoded → Global Constraints + Task 3/4. ✔

**Consistência de nomes:** `_negociacao_breakdown(orc, db, params, desc_orc, descontos_amb, total_cliente)`, `_recalcular_orcamento(orc, db)`, endpoint `/api/orcamentos/<id>/negociacao-preview`, sub-objeto com chaves-sigla do motor — usados igual entre Tasks 2/3/4/6.

**Observações:** Tasks 4 (UI) e 6 (reset) não têm teste automatizado (sem harness JS; reset é destrutivo/manual) — verificação manual; a lógica por trás (motor, persistência) é coberta por Tasks 2/3. Task 3 Step 6 avisa que algum teste legado que dependia do PATCH aceitar `valor_total` pode precisar de ajuste para o novo comportamento autoritativo.
