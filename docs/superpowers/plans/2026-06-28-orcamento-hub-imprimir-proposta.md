# Etapa Orçamento como hub + Imprimir Orçamento (proposta) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Renomear a etapa "Primeiro orçamento" para "Orçamento", transformar as etapas de Orçamento/Aprovação em hubs que listam os orçamentos (abrir + imprimir), e gerar uma **Proposta** em PDF a partir de um modelo global, sob demanda.

**Architecture:** Um módulo novo `mod_proposta.py` reaproveita as primitivas de `mod_contrato` (`_substituir_marcadores`, `_converter_pdf`, `_montar_mapping`, `construir_contexto`) sobre um template novo `modelo_proposta.docx`. Uma rota `GET /api/orcamentos/<id>/proposta/pdf` gera e serve inline (sem persistir). O frontend ganha o botão Imprimir e os cards das etapas.

**Tech Stack:** Python 3 (`python3` no WSL), python-docx, SQLAlchemy/SQLite, `http.server` (`main.Handler`), SPA vanilla, `pytest` (frontend = verificação manual).

## Global Constraints

- Rodar com `python3`/`python3 -m pytest` (WSL), nunca `python`.
- **Proposta sob demanda, SEM persistir** (sem registro no banco, sem arquivamento; o arquivo é gerado num diretório temporário e servido inline).
- **Reusar `mod_contrato`** (não duplicar o motor de marcadores): `_substituir_marcadores(doc, mapping, coletor=None)`, `construir_contexto(cliente, usuario, forma_pagamento_json, loja)`, `_montar_mapping(ctx, pag)`, `_formatar_valor(v)`, `_converter_pdf(docx_path[, outdir])`, exceção `LibreOfficeIndisponivel`.
- **Sem LibreOffice → entrega `.docx`** (degradação graciosa, igual ao contrato).
- **Escopo por loja:** sessão (401) + `mod_tenancy.escopo_operacional(ator)` (403) + `_obj_da_loja(db, Orcamento, oid, loja_id)` (404 p/ outra loja).
- **Template global** `modelo_proposta.docx` na raiz (por loja fica para o #8).
- Marcadores do contrato disponíveis (de `_montar_mapping`): `NOME_CLIENTE, CPF_CLIENTE, EMAIL, TELEFONE, NOME_EMPRESA, CNPJ_EMPRESA, CONSULTOR_NOME, CONSULTOR_TELEFONE, MODALIDADE, NUM_PARCELAS, VALOR_ENTRADA, FORMA_ENTRADA, DATA_ENTRADA, TOTAL_CONTRATO, RES_*/INST_*`. Marcadores novos da proposta: `AMBIENTES_LISTA, VALOR_BRUTO, DESCONTO_PCT, VALOR_TOTAL, VALIDADE`.

---

### Task 1: Renomear etapa 4 "Primeiro orçamento" → "Orçamento"

**Files:**
- Modify: `mod_ciclo.py` (`ETAPA_NOME["4"]`)
- Modify: `static/index.html` (lista de etapas ~7383; toast ~7175)
- Test: `tests/test_ciclo.py` (ou arquivo de teste de mod_ciclo existente)

**Interfaces:**
- Produces: `mod_ciclo.ETAPA_NOME["4"] == "Orçamento"`.

- [ ] **Step 1: Write the failing test**

Localize o teste de `mod_ciclo` (`grep -l ETAPA_NOME tests/`). Se existir `tests/test_ciclo.py`, acrescente; senão crie `tests/test_ciclo_nome.py`:

```python
import mod_ciclo


def test_etapa_4_renomeada_para_orcamento():
    assert mod_ciclo.ETAPA_NOME["4"] == "Orçamento"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_ciclo_nome.py -v`
Expected: FAIL (valor atual é "Primeiro orçamento").

- [ ] **Step 3: Implement**

Em `mod_ciclo.py`, troque a linha `"4": "Primeiro orçamento",` por `"4": "Orçamento",`.
Em `static/index.html`: na lista de etapas (~7383) troque `{ codigo: "4", nome: "Primeiro orçamento", sub: false }` por `nome: "Orçamento"`; e no toast (~7175) troque o texto `... etapa "Primeiro orçamento".` por `... etapa "Orçamento".`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_ciclo_nome.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m pytest -q` (sem regressão).
```bash
git add mod_ciclo.py static/index.html tests/test_ciclo_nome.py
git commit -m "feat(ciclo): renomeia etapa 4 'Primeiro orcamento' -> 'Orcamento'"
```

---

### Task 2: Template `modelo_proposta.docx` (script de build)

**Files:**
- Create: `tools/build_modelo_proposta.py`
- Create: `modelo_proposta.docx` (gerado pelo script)
- Test: `tests/test_proposta_template.py`

**Interfaces:**
- Produces: `modelo_proposta.docx` na raiz, contendo os marcadores `[NOME_EMPRESA] [CNPJ_EMPRESA] [NOME_CLIENTE] [CPF_CLIENTE] [EMAIL] [TELEFONE] [CONSULTOR_NOME] [AMBIENTES_LISTA] [VALOR_BRUTO] [DESCONTO_PCT] [VALOR_TOTAL] [MODALIDADE] [VALOR_ENTRADA] [NUM_PARCELAS] [VALIDADE]`.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_proposta_template.py`:

```python
import os
from docx import Document

MARCADORES = ["NOME_EMPRESA", "NOME_CLIENTE", "CPF_CLIENTE", "AMBIENTES_LISTA",
              "VALOR_BRUTO", "DESCONTO_PCT", "VALOR_TOTAL", "MODALIDADE", "VALIDADE"]


def test_modelo_proposta_existe_e_tem_marcadores():
    path = os.path.join(os.path.dirname(__file__), "..", "modelo_proposta.docx")
    assert os.path.exists(path), "modelo_proposta.docx não foi gerado"
    doc = Document(path)
    texto = "\n".join(p.text for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                texto += "\n" + cell.text
    for m in MARCADORES:
        assert "[%s]" % m in texto, "marcador faltando: %s" % m
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_proposta_template.py -v`
Expected: FAIL (arquivo não existe).

- [ ] **Step 3: Criar o script de build e gerar o docx**

Crie `tools/build_modelo_proposta.py`:

```python
"""Gera modelo_proposta.docx (template da Proposta comercial) com marcadores [MARCADOR].
Baseado na 1a pagina do contrato: cabecalho da loja, partes, oferta (ambientes/valores),
condicoes de pagamento, validade. Rode: python3 tools/build_modelo_proposta.py"""
import os
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "modelo_proposta.docx")

doc = Document()
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("PROPOSTA COMERCIAL"); r.bold = True; r.font.size = None

doc.add_paragraph("[NOME_EMPRESA] — CNPJ [CNPJ_EMPRESA]")
doc.add_paragraph("")
doc.add_paragraph("Cliente: [NOME_CLIENTE]    CPF: [CPF_CLIENTE]")
doc.add_paragraph("E-mail: [EMAIL]    Telefone: [TELEFONE]")
doc.add_paragraph("Consultor: [CONSULTOR_NOME]")
doc.add_paragraph("")
doc.add_paragraph("Ambientes:")
doc.add_paragraph("[AMBIENTES_LISTA]")
doc.add_paragraph("")
doc.add_paragraph("Valor bruto: [VALOR_BRUTO]")
doc.add_paragraph("Desconto: [DESCONTO_PCT]")
doc.add_paragraph("Valor total: [VALOR_TOTAL]")
doc.add_paragraph("")
doc.add_paragraph("Condições de pagamento: [MODALIDADE]")
doc.add_paragraph("Entrada: [VALOR_ENTRADA] ([FORMA_ENTRADA]) em [DATA_ENTRADA]")
doc.add_paragraph("Parcelas: [NUM_PARCELAS]")
doc.add_paragraph("")
doc.add_paragraph("[VALIDADE]")

doc.save(OUT)
print("gerado:", OUT)
```

Gere o arquivo:

Run: `python3 tools/build_modelo_proposta.py`
Expected: imprime `gerado: .../modelo_proposta.docx`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_proposta_template.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/build_modelo_proposta.py modelo_proposta.docx tests/test_proposta_template.py
git commit -m "feat(proposta): template modelo_proposta.docx (build script + marcadores)"
```

---

### Task 3: `mod_proposta.py` — `contexto_proposta` + `gerar_proposta` (+ `_converter_pdf` com outdir)

**Files:**
- Modify: `mod_contrato.py` (`_converter_pdf` aceita `outdir`)
- Create: `mod_proposta.py`
- Test: `tests/test_proposta.py`

**Interfaces:**
- Consumes: `mod_contrato._substituir_marcadores`, `construir_contexto`, `_montar_mapping`, `_formatar_valor`, `_converter_pdf`, `LibreOfficeIndisponivel`; `modelo_proposta.docx`.
- Produces:
  - `mod_contrato._converter_pdf(docx_path, outdir=None) -> str` (outdir default = `CONTRATOS_DIR`).
  - `mod_proposta.contexto_proposta(cliente, usuario, loja, orcamento_dict, breakdown, forma_pagamento_json) -> dict` (mapping de MARCADORES).
  - `mod_proposta.gerar_proposta(variaveis, outdir) -> tuple[str, bool]` — preenche o template em `outdir`, tenta PDF (no mesmo `outdir`), retorna `(caminho, eh_pdf)`; `.docx` se LibreOffice ausente. Não persiste fora de `outdir`.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_proposta.py`:

```python
import os
import mod_proposta


def test_contexto_proposta_marcadores():
    cliente = {"nome": "Ana", "cpf": "111", "email": "a@x.com", "telefone": "9999",
               "logradouro": "", "numero": "", "complemento": "", "bairro": "",
               "cidade": "", "cep": "", "estado": "", "inst_mesmo_residencial": True,
               "inst_logradouro": "", "inst_numero": "", "inst_complemento": "",
               "inst_bairro": "", "inst_cidade": "", "inst_cep": "", "inst_uf": ""}
    usuario = {"nome": "Consultor X", "telefone": "", "email": ""}
    loja = {"nome": "Loja Z", "cnpj": "00.000.000/0001-00", "codigo": "LJZ"}
    orcamento_dict = {"ambientes": ["Cozinha", "Dormitório"]}
    breakdown = {"VBVO": 100000.0, "VAVO": 90000.0}
    m = mod_proposta.contexto_proposta(cliente, usuario, loja, orcamento_dict, breakdown, "")
    assert m["NOME_CLIENTE"] == "Ana"
    assert m["NOME_EMPRESA"] == "Loja Z"
    assert "Cozinha" in m["AMBIENTES_LISTA"] and "Dormitório" in m["AMBIENTES_LISTA"]
    assert m["VALOR_BRUTO"].replace(".", "").replace(",", "").startswith("R") or "100" in m["VALOR_BRUTO"]
    assert "%" in m["DESCONTO_PCT"]          # 10% (1 - 90000/100000)
    assert m["VALIDADE"]


def test_gerar_proposta_em_outdir(tmp_path):
    variaveis = {"NOME_CLIENTE": "Ana", "NOME_EMPRESA": "Loja Z", "AMBIENTES_LISTA": "Cozinha",
                 "VALOR_BRUTO": "R$ 100.000,00", "DESCONTO_PCT": "10,0%",
                 "VALOR_TOTAL": "R$ 90.000,00", "MODALIDADE": "A Vista", "VALIDADE": "Válida 10 dias."}
    caminho, eh_pdf = mod_proposta.gerar_proposta(variaveis, str(tmp_path))
    assert os.path.exists(caminho)
    # sem LibreOffice no ambiente: cai no .docx
    assert caminho.endswith(".pdf") or caminho.endswith(".docx")
    # o arquivo ficou DENTRO do outdir (não em CONTRATOS_DIR)
    assert os.path.dirname(os.path.abspath(caminho)) == os.path.abspath(str(tmp_path))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_proposta.py -v`
Expected: FAIL (`ModuleNotFoundError: mod_proposta`).

- [ ] **Step 3: Implement**

3a. Em `mod_contrato.py`, parametrize `_converter_pdf` (mantendo o default):

```python
def _converter_pdf(docx_path: str, outdir: str = None) -> str:
    """Converte um .docx EXISTENTE em PDF (não regenera). Retorna o caminho do PDF.
    outdir default = CONTRATOS_DIR (comportamento do contrato inalterado)."""
    destino = outdir or CONTRATOS_DIR
    try:
        subprocess.run(
            [_libreoffice_cmd(), "--headless", "--convert-to", "pdf",
             "--outdir", destino, docx_path],
            check=True, capture_output=True, timeout=120,
        )
    except FileNotFoundError:
        raise LibreOfficeIndisponivel(docx_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice falhou:\n{e.stderr.decode(errors='replace')}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice demorou mais de 120s")
    base = os.path.splitext(os.path.basename(docx_path))[0]
    return os.path.join(destino, f"{base}.pdf")
```

3b. Crie `mod_proposta.py`:

```python
"""Geração da Proposta comercial (PDF/docx) — reaproveita o motor de marcadores de mod_contrato.
Sob demanda, sem persistência: gera num diretório informado pelo chamador."""
import os
from docx import Document
import mod_contrato

_MODELO_PROPOSTA = os.path.join(os.path.dirname(__file__), "modelo_proposta.docx")


def contexto_proposta(cliente, usuario, loja, orcamento_dict, breakdown, forma_pagamento_json):
    """Monta o {MARCADOR: valor} da proposta (chaves MAIÚSCULAS, sem colchetes)."""
    ctx = mod_contrato.construir_contexto(cliente, usuario, forma_pagamento_json or "", loja)
    mapping = mod_contrato._montar_mapping(ctx, ctx.get("_pag", {}))
    f = mod_contrato._formatar_valor
    vbvo = float(breakdown.get("VBVO") or 0)
    vavo = float(breakdown.get("VAVO") or 0)
    desc = (1 - vavo / vbvo) * 100 if vbvo else 0.0
    mapping.update({
        "AMBIENTES_LISTA": "\n".join(orcamento_dict.get("ambientes") or []),
        "VALOR_BRUTO":  f(vbvo),
        "DESCONTO_PCT": f"{desc:.1f}%".replace(".", ","),
        "VALOR_TOTAL":  f(vavo),
        "VALIDADE":     "Proposta válida por 10 dias a partir da emissão.",
    })
    return mapping


def gerar_proposta(variaveis, outdir):
    """Preenche modelo_proposta.docx em outdir; tenta PDF (no mesmo outdir).
    Retorna (caminho, eh_pdf). Não persiste fora de outdir."""
    if not os.path.exists(_MODELO_PROPOSTA):
        raise FileNotFoundError("Modelo de proposta não encontrado: %s" % _MODELO_PROPOSTA)
    os.makedirs(outdir, exist_ok=True)
    doc = Document(_MODELO_PROPOSTA)
    mod_contrato._substituir_marcadores(doc, variaveis)
    docx_path = os.path.join(outdir, "proposta.docx")
    doc.save(docx_path)
    try:
        pdf_path = mod_contrato._converter_pdf(docx_path, outdir=outdir)
        return pdf_path, True
    except mod_contrato.LibreOfficeIndisponivel:
        return docx_path, False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_proposta.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m pytest -q` (sem regressão — `_converter_pdf` mantém o default; testes de contrato intactos).
```bash
git add mod_contrato.py mod_proposta.py tests/test_proposta.py
git commit -m "feat(proposta): mod_proposta (contexto + gerar) + _converter_pdf com outdir"
```

---

### Task 4: Rota `GET /api/orcamentos/<id>/proposta/pdf`

**Files:**
- Modify: `main.py` (ramo em `do_GET` + import de `mod_proposta`)
- Test: `tests/test_proposta_e2e.py`

**Interfaces:**
- Consumes: `mod_proposta.contexto_proposta`/`gerar_proposta`, `_montar_dados_projeto_para_contrato(nome_safe, orcamento_id, db) -> (projeto_dict, cliente_dict, orcamento_dict)`, `_loja_dict_para_contrato(db, loja_id)`, `_get_usuario_telefone(usuario_id, db)`, `_negociacao_breakdown(orc, db)`, `_obj_da_loja`, `escopo_operacional`.
- Produces: `GET /api/orcamentos/<id>/proposta/pdf` → serve inline o PDF (ou `.docx`); 401 anônimo; 403 sem escopo; 404 outra loja.

- [ ] **Step 1: Write the failing test**

Crie `tests/test_proposta_e2e.py`:

```python
import os
import pytest


@pytest.fixture(autouse=True)
def _template_existe():
    # garante que o template foi gerado (Task 2); senão pula o e2e
    if not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "modelo_proposta.docx")):
        pytest.skip("modelo_proposta.docx ausente")


def _setup_ambiente(app_db, seed):
    db = app_db.get_session()
    try:
        if not db.query(app_db.OrcamentoAmbiente).filter_by(orcamento_id=seed["orcamento_l1_id"]).first():
            pa = app_db.PoolAmbiente(projeto_id=seed["projeto_l1"], nome="Cozinha", versao=1,
                                     nome_exibicao="Cozinha", xml_path="", ambientes_json="[]",
                                     budget_total=90000.0, order_total=40000.0)
            db.add(pa); db.flush()
            db.add(app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                            pool_ambiente_id=pa.id, desconto_individual_pct=0.0))
            db.commit()
    finally:
        db.close()


def test_proposta_pdf_gera_e_serve(http_client_factory, app_db, seed, projetos_dir):
    _setup_ambiente(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st == 200
    assert body  # corpo não vazio (bytes do docx/pdf)


def test_proposta_pdf_outra_loja_404(http_client_factory, app_db, seed, projetos_dir):
    _setup_ambiente(app_db, seed)
    c = http_client_factory(); c.login("dir_l2", "senha123")
    st, _ = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st in (403, 404)


def test_proposta_pdf_anonimo_401(http_client_factory, seed):
    c = http_client_factory()
    st, _ = c.get("/api/orcamentos/%d/proposta/pdf" % seed["orcamento_l1_id"])
    assert st == 401
```

(O `HttpClient._req` lê o corpo como bytes quando não é JSON — `body` será os bytes do arquivo.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_proposta_e2e.py -v`
Expected: FAIL (rota inexistente → provavelmente 404 com corpo JSON, falhando os asserts).

- [ ] **Step 3: Implement**

Em `main.py`: garanta `import mod_proposta` no topo (junto dos outros `mod_*`). No `do_GET`, junto das rotas `/api/orcamentos/...`, adicione (adapte ao estilo de dispatch vizinho — `if m: ... return` dentro do `else`):

```python
        elif re.match(r"^/api/orcamentos/(\d+)/proposta/pdf$", path):
            import tempfile, shutil
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            oid = int(re.match(r"^/api/orcamentos/(\d+)/proposta/pdf$", path).group(1))
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja_id, _err = mod_tenancy.escopo_operacional(ator)
                if _err:
                    self.send_json({"ok": False, "erro": _err}, code=403); return
                orc = _obj_da_loja(db, Orcamento, oid, loja_id)
                if orc is None:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                _proj, cliente_dict, orcamento_dict = \
                    _montar_dados_projeto_para_contrato(orc.projeto_id, oid, db)
                loja_dict = _loja_dict_para_contrato(db, loja_id)
                usuario_ctx = {"nome": usuario.get("nome", ""),
                               "telefone": _get_usuario_telefone(usuario["id"], db),
                               "email": usuario.get("email", "") or ""}
                d = _negociacao_breakdown(orc, db)
                variaveis = mod_proposta.contexto_proposta(
                    cliente_dict, usuario_ctx, loja_dict, orcamento_dict, d, orc.forma_pagamento or "")
                outdir = tempfile.mkdtemp(prefix="proposta_")
                try:
                    caminho, eh_pdf = mod_proposta.gerar_proposta(variaveis, outdir)
                    with open(caminho, "rb") as fh:
                        data = fh.read()
                    ct = "application/pdf" if eh_pdf else \
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ext = "pdf" if eh_pdf else "docx"
                    self.send_response(200)
                    self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", len(data))
                    self.send_header("Content-Disposition", 'inline; filename="proposta_%d.%s"' % (oid, ext))
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    shutil.rmtree(outdir, ignore_errors=True)
            except Exception as e:
                self.send_json({"ok": False, "erro": str(e)}, code=500)
            finally:
                db.close()
```

(Se `mod_proposta` virar nome local no `do_GET` por causa de um import local num `elif` anterior, use `import mod_proposta as _mprop` neste bloco — mesmo padrão do guard que já existe para `mod_provisoes`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_proposta_e2e.py -v`
Expected: PASS (3 testes).

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m pytest -q`.
```bash
git add main.py tests/test_proposta_e2e.py
git commit -m "feat(proposta): GET /api/orcamentos/<id>/proposta/pdf (sob demanda, escopo+IDOR)"
```

---

### Task 5: Frontend — botão Imprimir + cards das etapas Orçamento/Aprovação

**Files:**
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `GET /api/orcamentos/<id>/proposta/pdf`; `_orcamentos` (lista, de `carregarOrcamentos`), `_orcamentoAtivoId`, `ativarOrcamento(id)`, `_renderCardGenerico(etapa, dados, bloqueada)`, `GET /api/projetos/<nome>/contrato` (orçamento aprovado).
- Produces: botão "🖨 Imprimir Orçamento" na negociação; cards das etapas 4 (Orçamento) e 6 (Aprovação) listando orçamentos com Abrir/Imprimir.

- [ ] **Step 1: Botão "Imprimir Orçamento" na negociação**

No `static/index.html`, ao lado de "Salvar Orçamento"/"Aprovar Orçamento" (~linha 1142-1143), adicione:

```html
      <a id="btn-imprimir-orcamento" class="btn btn-ghost" target="_blank" rel="noopener"
         style="text-decoration:none" href="#"
         onclick="this.href='/api/orcamentos/'+_orcamentoAtivoId+'/proposta/pdf'">&#x1F5A8; Imprimir Or&ccedil;amento</a>
```

(O `onclick` ajusta o href para o orçamento ativo no momento do clique; `target="_blank"` abre em nova aba — PDF de página inteira.)

- [ ] **Step 2: Card da etapa 4 (Orçamento) — lista os orçamentos**

Em `_renderCardGenerico(etapa, dados, bloqueada)` (~7651), adicione um caso especial para `etapa.codigo === '4'`, ANTES do retorno genérico, que lista `_orcamentos` com botões Abrir + Imprimir:

```js
  if (etapa.codigo === '4') {
    if (!_orcamentos || !_orcamentos.length) {
      return `<p style="color:var(--muted);font-size:.85rem">Nenhum orçamento ainda. Crie um orçamento na tela de negociação.</p>`;
    }
    const linhas = _orcamentos.map(o => `
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px">
        <span style="flex:1">${esc(o.nome || ('Orçamento ' + o.id))}</span>
        <button class="btn-ciclo" style="font-size:.8rem" onclick="fecharCiclo();ativarOrcamento(${o.id})">Abrir</button>
        <a class="btn-ciclo" style="font-size:.8rem;text-decoration:none" target="_blank" rel="noopener"
           href="/api/orcamentos/${o.id}/proposta/pdf">&#x1F5A8; Imprimir</a>
      </div>`).join('');
    return `<div>${linhas}</div>`;
  }
```

- [ ] **Step 3: Card da etapa 6 (Aprovação do orçamento) — orçamento aprovado**

Adicione em `_renderCardGenerico` um caso `etapa.codigo === '6'` que busca o contrato (para o `orcamento_id` aprovado) e mostra Abrir/Imprimir. Como o render é síncrono, use um placeholder com `id` e preencha via fetch:

```js
  if (etapa.codigo === '6') {
    setTimeout(async () => {
      const alvo = document.getElementById('aprov-orc-alvo');
      if (!alvo || !projetoAtivo) return;
      try {
        const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/contrato`);
        const j = await r.json();
        const oid = j.contrato && j.contrato.orcamento_id;
        if (!oid) { alvo.innerHTML = '<span style="color:var(--muted)">Nenhum orçamento aprovado ainda.</span>'; return; }
        const o = (_orcamentos || []).find(x => x.id === oid) || {id: oid, nome: 'Orçamento ' + oid};
        alvo.innerHTML = `
          <span style="flex:1">Aprovado: ${esc(o.nome || ('Orçamento ' + oid))}</span>
          <button class="btn-ciclo" style="font-size:.8rem" onclick="fecharCiclo();ativarOrcamento(${oid})">Abrir</button>
          <a class="btn-ciclo" style="font-size:.8rem;text-decoration:none" target="_blank" rel="noopener"
             href="/api/orcamentos/${oid}/proposta/pdf">&#x1F5A8; Imprimir proposta</a>`;
      } catch (e) { /* silencioso */ }
    }, 0);
    return `<div id="aprov-orc-alvo" style="display:flex;gap:8px;align-items:center"><span style="color:var(--muted)">Carregando…</span></div>`;
  }
```

- [ ] **Step 4: Sanity estático (sem pytest/servidor p/ o JS)**

Releia os 3 blocos: chaves/backticks balanceados; o botão Imprimir usa `_orcamentoAtivoId`; os cards usam `_orcamentos`/`ativarOrcamento`/`esc`; sem erro de sintaxe. Rode `python3 -m pytest -q` uma vez (deve seguir verde — served-file tests inalterados).

- [ ] **Step 5: Verificação manual + commit**

```bash
python3 main.py
```
Como diretor: tela de negociação → **🖨 Imprimir Orçamento** abre a proposta em nova aba (docx sem LibreOffice). Etapas do Projeto → etapa **Orçamento** lista os orçamentos (Abrir leva à negociação; Imprimir abre a proposta); etapa **Aprovação do orçamento** mostra o orçamento aprovado (após gerar contrato).

```bash
git add static/index.html
git commit -m "feat(proposta): botao Imprimir Orcamento + cards Orcamento/Aprovacao (abrir+imprimir)"
```

---

## Notas de implementação

- **Ordem/dependências:** Task 1 (rename) independente; Task 2 (template) antes de 3/4; Task 3 (módulo) antes de 4 (rota); Task 5 (frontend) depende de 4.
- **Branch:** `feat/orcamento-hub-proposta` (já criada, com o spec).
- **Hermetismo:** a proposta gera em `tempfile.mkdtemp` e é removida após servir — não toca `CONTRATOS_DIR` nem o repo.
- **Fora deste plano (futuro #8):** modelo de proposta por loja (Padrão/Personalizado); aplicar o padrão "etapa → artefatos" às demais etapas; persistir/versionar a proposta.
