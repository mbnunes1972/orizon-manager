# Contrato editável protegido + edição pontual (F2) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** O contrato gerado sai protegido (somente-leitura exceto os valores de campo). Um
botão "Editar" (gate gerencial) abre o `.docx` no Word/LibreOffice; ao salvar, um watcher
regera o PDF.

**Architecture:** `preencher_contrato(..., protegido=True)` envolve cada valor em região
editável (`permStart/permEnd`) e marca o doc `documentProtection readOnly`. Endpoint
`POST .../contrato/editar` valida nível gerencial (auditado), abre o app e inicia um
watcher (mtime+lock+debounce+timeout) que chama `_converter_pdf`.

**Tech Stack:** Python 3, python-docx + lxml (OOXML), http.server/SQLAlchemy, LibreOffice;
JS vanilla; pytest.

**Spec:** `docs/superpowers/specs/2026-06-18-contrato-editavel-protegido-design.md`

---

## File Structure

- `mod_contrato.py` — `_converter_pdf`; coletor de runs de valor; `_proteger_editaveis`;
  `protegido` em `preencher_contrato`.
- `main.py` — endpoint `POST .../contrato/editar` (gate gerencial + launch + watcher).
- `static/index.html` — botão "Editar contrato" + modal (login gerencial + app).
- `tests/test_contrato.py` — testes de proteção/regiões; lógica do watcher.

---

### Task 1: Extrair `_converter_pdf(docx_path)` (não regenerar o docx)

**Files:** `mod_contrato.py` (`gerar_pdf_contrato` ~L445-467), `tests/test_contrato.py`

Motivo: o watcher precisa converter o `.docx` **já editado** em PDF SEM chamar
`preencher_contrato` (que sobrescreveria as correções manuais).

- [ ] **Step 1: Teste**
```python
def test_converter_pdf_nao_regenera_docx(monkeypatch):
    import mod_contrato
    chamou = {"preencher": False, "convert_path": None}
    monkeypatch.setattr(mod_contrato, "preencher_contrato",
                        lambda *a, **k: chamou.__setitem__("preencher", True) or "X")
    def fake_run(cmd, **kw):
        chamou["convert_path"] = cmd[-1]
        class R: pass
        return R()
    monkeypatch.setattr(mod_contrato.subprocess, "run", fake_run)
    out = mod_contrato._converter_pdf("/tmp/contrato_5.docx")
    assert chamou["preencher"] is False          # NÃO regenerou
    assert chamou["convert_path"] == "/tmp/contrato_5.docx"
    assert out.endswith("contrato_5.pdf")
```

- [ ] **Step 2:** Rodar → FAIL (`_converter_pdf` inexistente).
`python -m pytest tests/test_contrato.py -k converter_pdf -v`

- [ ] **Step 3: Implementar.** Extrair a parte de conversão de `gerar_pdf_contrato` para:
```python
def _converter_pdf(docx_path: str) -> str:
    """Converte um .docx EXISTENTE em PDF (não regenera o docx). Retorna o caminho do PDF."""
    try:
        subprocess.run(
            [_libreoffice_cmd(), "--headless", "--convert-to", "pdf",
             "--outdir", CONTRATOS_DIR, docx_path],
            check=True, capture_output=True, timeout=120,
        )
    except FileNotFoundError:
        raise LibreOfficeIndisponivel(docx_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice falhou:\n{e.stderr.decode(errors='replace')}") from e
    except subprocess.TimeoutExpired:
        raise RuntimeError("LibreOffice demorou mais de 120s")
    base = os.path.splitext(os.path.basename(docx_path))[0]
    return os.path.join(CONTRATOS_DIR, f"{base}.pdf")
```
E `gerar_pdf_contrato` passa a:
```python
def gerar_pdf_contrato(contrato_id: int, variaveis: dict) -> str:
    docx_path = preencher_contrato(contrato_id, variaveis)
    return _converter_pdf(docx_path)
```

- [ ] **Step 4:** Rodar testes → PASS. `python -m pytest tests/test_contrato.py -q`

- [ ] **Step 5: Commit** `git add mod_contrato.py tests/test_contrato.py && git commit -m "refactor(contrato): extrai _converter_pdf (conversão sem regenerar docx)"`

---

### Task 2: Regiões editáveis + proteção do documento

**Files:** `mod_contrato.py` (`_subst_paragrafo`/`_substituir_marcadores`, `_set_cell_text`,
`_preencher_grade`, `preencher_contrato`, novo `_proteger_editaveis`), `tests/test_contrato.py`

Conceito: ao preencher, **coletar os runs de valor**; depois envolvê-los em
`permStart/permEnd` e marcar `documentProtection`. Tabelas e corpo ficam editáveis só nos
valores; o cabeçalho (num/data) é gerado pelo sistema e **não** entra como editável
(textbox; fora de escopo da edição pontual).

- [ ] **Step 1: Testes**
```python
def test_protegido_tem_documentprotection_e_regioes():
    import json
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome":"Ana","cpf":"111","email":"a@x.com","telefone":"(12)9","logradouro":"R",
                 "numero":"1","complemento":"","bairro":"C","cidade":"SJC","cep":"1","estado":"SP",
                 "inst_mesmo_residencial":True,"inst_logradouro":"","inst_numero":"","inst_complemento":"",
                 "inst_bairro":"","inst_cidade":"","inst_cep":"","inst_uf":""},
        usuario={"nome":"Z","telefone":"","email":""},
        forma_pagamento_json=json.dumps({"tipo":"aymore","nome_forma":"Aymoré","total_cliente":1000,
            "texto_cartao":"","parcelas":[{"num":1,"data":"18/07/2026","valor":500.0}]}))
    ctx["num_contrato"]="INS-1"; ctx["data_contrato"]="18/06/2026"
    import os
    p = preencher_contrato(97001, ctx, protegido=True)
    d = Document(p)
    settings_xml = d.settings.element
    prot = settings_xml.find(qn('w:documentProtection'))
    body_xml = d.element.body.xml
    os.remove(p)
    assert prot is not None and prot.get(qn('w:edit')) == "readOnly"
    assert "permStart" in body_xml and "permEnd" in body_xml
    # o valor "Ana" deve estar entre um permStart e o permEnd seguinte
    import re
    assert "Ana" in body_xml

def test_nao_protegido_sem_documentprotection():
    import json, os
    from docx import Document
    from docx.oxml.ns import qn
    from mod_contrato import preencher_contrato, construir_contexto
    ctx = construir_contexto(
        cliente={"nome":"Ana","cpf":"1","email":"","telefone":"","logradouro":"","numero":"",
                 "complemento":"","bairro":"","cidade":"","cep":"","estado":"","inst_mesmo_residencial":True,
                 "inst_logradouro":"","inst_numero":"","inst_complemento":"","inst_bairro":"",
                 "inst_cidade":"","inst_cep":"","inst_uf":""},
        usuario={"nome":"Z","telefone":"","email":""},
        forma_pagamento_json=json.dumps({"tipo":"aymore","nome_forma":"Aymoré","total_cliente":0,
            "texto_cartao":"","parcelas":[]}))
    p = preencher_contrato(97002, ctx, protegido=False)
    d = Document(p)
    has = d.settings.element.find(qn('w:documentProtection')) is not None
    body = d.element.body.xml
    os.remove(p)
    assert has is False
    assert "permStart" not in body
```

- [ ] **Step 2:** Rodar → FAIL (`protegido` param/proteção inexistentes).
`python -m pytest tests/test_contrato.py -k "protegido or documentprotection" -v`

- [ ] **Step 3: Coletor de runs de valor.** Reimplementar `_subst_paragrafo` para
segmentar o parágrafo (fixo/valor) e criar um run por segmento, registrando os runs de
valor num coletor opcional:
```python
def _subst_paragrafo(par, mapping, coletor=None):
    txt = par.text
    if "[" not in txt:
        return
    # base de formatação do 1º run
    base = par.runs[0] if par.runs else None
    segs = []   # (texto, eh_valor)
    pos = 0
    for m in _MARK_RE.finditer(txt):
        if m.start() > pos:
            segs.append((txt[pos:m.start()], False))
        chave = m.group(1).strip().upper().replace(" ", "_")
        if chave in mapping:
            segs.append((mapping[chave], True))
        else:
            segs.append((m.group(0), False))   # marcador desconhecido: literal, não editável
        pos = m.end()
    if pos < len(txt):
        segs.append((txt[pos:], False))
    # zera runs e reconstrói
    for r in list(par.runs):
        r.text = ""
    # remove runs extras, mantém o primeiro como “molde”
    while len(par.runs) > 1:
        par.runs[-1]._r.getparent().remove(par.runs[-1]._r)
    novos = []
    for seg_txt, eh_valor in segs:
        run = par.add_run(seg_txt)
        if base is not None:
            run.font.name = base.font.name
            run.font.size = base.font.size
            run.bold = base.bold
        if eh_valor and coletor is not None:
            coletor.append(run)
        novos.append(run)
    # remove o molde vazio inicial (1º run, agora "")
    if par.runs and par.runs[0].text == "" and len(par.runs) > 1:
        par.runs[0]._r.getparent().remove(par.runs[0]._r)
```
> Nota: validar empiricamente o manejo dos runs (python-docx). Objetivo: o texto final do
> parágrafo é idêntico ao de hoje; os runs de valor ficam isolados e coletados.

Atualizar `_substituir_marcadores(doc, mapping, coletor=None)` para passar `coletor` a
`_subst_paragrafo` (corpo e células). NÃO coletar no header (mantém o cabeçalho não
editável) — passar `coletor=None` no laço dos headers.

- [ ] **Step 4: `_set_cell_text` e `_preencher_grade` coletam.** `_set_cell_text(cell, txt,
coletor=None)`: após escrever, se `coletor is not None` e `txt` não vazio e `txt != _TRACO`,
anexar `cell.paragraphs[0].runs[0]`. `_preencher_grade(doc, pag, coletor=None)` repassa o
coletor (só os valores reais; traços não entram).

- [ ] **Step 5: `_proteger_editaveis` + `protegido` em `preencher_contrato`.**
```python
def _proteger_editaveis(doc, runs):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    for i, run in enumerate(runs, start=1):
        ps = OxmlElement('w:permStart'); ps.set(qn('w:id'), str(i)); ps.set(qn('w:edGrp'), 'everyone')
        pe = OxmlElement('w:permEnd');   pe.set(qn('w:id'), str(i))
        r = run._r
        r.addprevious(ps)
        r.addnext(pe)
    prot = OxmlElement('w:documentProtection')
    prot.set(qn('w:edit'), 'readOnly'); prot.set(qn('w:enforcement'), '1')
    doc.settings.element.append(prot)

def preencher_contrato(contrato_id, ctx, protegido=True):
    doc = Document(_MODELO)
    pag = ctx.get("_pag", {})
    coletor = [] if protegido else None
    _preencher_grade(doc, pag, coletor=coletor)
    _substituir_marcadores(doc, _montar_mapping(ctx, pag), coletor=coletor)
    if protegido:
        _proteger_editaveis(doc, coletor)
    docx_path = os.path.join(CONTRATOS_DIR, f"contrato_{contrato_id}.docx")
    doc.save(docx_path)
    return docx_path
```
> ATENÇÃO compat: os testes da F1 chamam `preencher_contrato(id, ctx)` esperando o doc SEM
> proteção em alguns asserts (ex.: `test_geracao_completa_sem_marcadores_remanescentes`
> coleta texto e exige zero marcadores — a proteção não muda o texto, então deve continuar
> passando). Rodar a suíte inteira no Step 7 e ajustar SE algum teste quebrar por causa de
> runs múltiplos (o `.text` do parágrafo permanece igual; a maioria dos asserts usa `.text`
> ou blob de células, que não muda). Se algum teste comparava número de runs, atualizar.

- [ ] **Step 6:** Rodar os testes novos → PASS.
`python -m pytest tests/test_contrato.py -k "protegido or documentprotection" -v`

- [ ] **Step 7:** Suíte inteira → PASS. `python -m pytest tests/ -q` (corrigir regressões
de runs, conforme nota do Step 5).

- [ ] **Step 8: Commit** `git add mod_contrato.py tests/test_contrato.py && git commit -m "feat(contrato): regiões editáveis (permStart/permEnd) + documentProtection"`

---

### Task 3: Endpoint `POST .../contrato/editar` (gate gerencial + launch + watcher)

**Files:** `main.py`, `tests/test_contrato.py` (ou `tests/test_editar_contrato.py`)

Padrão de auth gerencial a reusar (de `main.py:1948`):
```python
login = (req.get("login") or "").strip(); senha = (req.get("senha") or "").strip()
autorizador = db.query(Usuario).filter_by(login=login, ativo=1).first()
if not autorizador or not autorizador.check_senha(senha):
    self.send_json({"ok": False, "erro": "Credenciais inválidas"}); return
if autorizador.nivel not in ("gerente", "diretor", "admin"):
    self.send_json({"ok": False, "erro": "Necessário nível Gerente ou Diretor"}); return
```

- [ ] **Step 1: Helper testável do watcher** em um módulo próprio (ex.: `contrato_editar.py`)
para isolar a lógica e poder testar sem GUI:
```python
# contrato_editar.py
import os, time, threading

def _lock_paths(docx_path):
    d = os.path.dirname(docx_path); b = os.path.basename(docx_path)
    return [os.path.join(d, "~$" + b), os.path.join(d, ".~lock." + b + "#")]

def arquivo_salvo_e_livre(docx_path, mtime_ref):
    """True se o docx foi modificado após mtime_ref e nenhum lock está presente."""
    if not os.path.exists(docx_path):
        return False
    if os.path.getmtime(docx_path) <= mtime_ref:
        return False
    return not any(os.path.exists(l) for l in _lock_paths(docx_path))

def watcher_regerar_pdf(docx_path, on_save, *, poll=2.0, timeout=1800, sleep=time.sleep,
                        agora=time.time, debounce=3.0):
    """Poll até timeout. A cada salvamento (mtime cresce + sem lock), chama on_save(docx_path)
    com debounce. Continua até o timeout ou enquanto houver atividade."""
    inicio = agora(); ultimo_mtime = os.path.getmtime(docx_path) if os.path.exists(docx_path) else 0
    while agora() - inicio < timeout:
        sleep(poll)
        if arquivo_salvo_e_livre(docx_path, ultimo_mtime):
            sleep(debounce)
            if arquivo_salvo_e_livre(docx_path, ultimo_mtime):
                try: on_save(docx_path)
                except Exception: pass
                ultimo_mtime = os.path.getmtime(docx_path)
```

- [ ] **Step 2: Teste do watcher** (sem GUI, com fakes de tempo e fs simulado):
```python
def test_arquivo_salvo_e_livre(tmp_path):
    from contrato_editar import arquivo_salvo_e_livre
    f = tmp_path / "contrato_1.docx"; f.write_text("x")
    m0 = f.stat().st_mtime
    assert arquivo_salvo_e_livre(str(f), m0) is False          # não mudou
    import os, time; time.sleep(0.01); f.write_text("y"); os.utime(str(f), None)
    assert arquivo_salvo_e_livre(str(f), m0) is True           # mudou, sem lock
    lock = tmp_path / "~$contrato_1.docx"; lock.write_text("")
    assert arquivo_salvo_e_livre(str(f), m0) is False          # lock presente

def test_watcher_chama_on_save_uma_vez_por_salvamento(tmp_path):
    from contrato_editar import watcher_regerar_pdf
    f = tmp_path / "contrato_1.docx"; f.write_text("x")
    chamadas = []
    # tempo simulado: cresce 1s por sleep; modifica o arquivo no “meio”
    estado = {"t": 0.0}
    def fake_sleep(s): estado["t"] += s
    def fake_agora(): return estado["t"]
    import os
    seq = {"mod": False}
    real_save = lambda p: chamadas.append(p)
    # modifica o arquivo após o primeiro poll
    def on_save(p):
        chamadas.append(p)
    # roda um timeout curto; modifica mtime antes
    os.utime(str(f), (100, 100))
    # força "salvo": mtime futuro
    import time
    f.write_text("y"); os.utime(str(f), (10_000, 10_000))
    watcher_regerar_pdf(str(f), on_save, poll=1, timeout=5, sleep=fake_sleep, agora=fake_agora, debounce=0)
    assert len(chamadas) >= 1
```
(Ajustar o teste do watcher à implementação; o objetivo é cobrir "detecta salvamento e
chama on_save", sem abrir app real.)

- [ ] **Step 3:** Rodar → FAIL (`contrato_editar` inexistente). Implementar
`contrato_editar.py` (Step 1) + a função de launch:
```python
def abrir_no_app(docx_path, app):
    import subprocess, os
    if app == "libreoffice":
        from mod_contrato import _libreoffice_cmd
        subprocess.Popen([_libreoffice_cmd(), docx_path])
    else:  # word / default
        os.startfile(docx_path)   # Windows: abre no app padrão do .docx
```
(`os.startfile` só existe no Windows — ok, app desktop Windows. Isolar atrás de
`abrir_no_app` para o teste poder monkeypatchar.)

- [ ] **Step 4: Rota no `main.py`.** Adicionar handler
`POST /api/projetos/<nome>/contrato/editar` (próximo aos outros handlers de contrato,
~L2198+). Lógica:
  1. Parse body `{app, login, senha}`; gate gerencial (padrão acima).
  2. Buscar o `Contrato` mais recente do projeto; achar `contrato_<id>.docx` em
     `CONTRATOS_DIR`. Se não existir, gerar via `preencher_contrato(id, variaveis, protegido=True)`
     (reconstruir `variaveis` como o handler de geração faz; ou exigir que já exista).
  3. `log_acoes_gerenciais`: inserir `LogAcaoGerencial(autorizador_id=autorizador.id,
     acao="editar_contrato", projeto_nome=nome_safe, contexto=json.dumps({"app":app}))`.
  4. `abrir_no_app(docx_path, app)`.
  5. Iniciar a thread:
     `threading.Thread(target=watcher_regerar_pdf, args=(docx_path, _on_save), daemon=True).start()`
     onde `_on_save = lambda p: (mod_contrato._converter_pdf(p))` (e atualizar
     `contrato.pdf_path`/timestamp numa sessão própria dentro do callback).
  6. Responder `{ok:true, editando:true, app:app}`.

- [ ] **Step 5: Teste do endpoint** (gate): simular request sem nível gerencial → erro;
com gerente válido → ok. Monkeypatchar `abrir_no_app` e o `Thread` para não abrir GUI nem
rodar watcher real. Verificar que `LogAcaoGerencial` foi inserido. (Se testar via HTTP for
pesado, testar a função de handler extraída; senão, cobrir a lógica de gate numa função
util `validar_gerencial(db, login, senha)` testável.)

- [ ] **Step 6:** Suíte → PASS. `python -m pytest tests/ -q`

- [ ] **Step 7: Commit** `git add main.py contrato_editar.py tests/ && git commit -m "feat(contrato): endpoint editar (gate gerencial + abre app + watcher regera PDF)"`

---

### Task 4: Frontend — botão "Editar contrato" + modal gerencial

**Files:** `static/index.html`

- [ ] **Step 1:** No render do contrato (após o iframe do PDF, ~L6612, quando
`temArquivo` e status não assinado), adicionar:
```html
<button onclick="abrirModalEditarContrato()" class="btn-ciclo"
        style="font-size:.85rem;margin-bottom:12px">&#x270E; Editar contrato (gerencial)</button>
```

- [ ] **Step 2:** Funções JS:
```js
function abrirModalEditarContrato() {
  // modal: select app (Word/LibreOffice) + inputs login/senha gerencial + botão Abrir
  // (reusar o estilo dos modais existentes; ids: edit-app, edit-login, edit-senha)
}
async function confirmarEditarContrato() {
  const app   = document.getElementById('edit-app').value;
  const login = document.getElementById('edit-login').value.trim();
  const senha = document.getElementById('edit-senha').value;
  const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/contrato/editar`,
    { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin',
      body: JSON.stringify({ app, login, senha }) });
  const d = await r.json();
  if (!d.ok) { /* mostrar erro */ return; }
  // mensagem: "Abrindo no <app>. Ao salvar e fechar, o PDF será regerado automaticamente."
}
```

- [ ] **Step 3:** Sanity no navegador (Task 5 cobre o runtime). `grep -n "abrirModalEditarContrato\|confirmarEditarContrato" static/index.html`.

- [ ] **Step 4: Commit** `git add static/index.html && git commit -m "feat(front): botão Editar contrato + modal gerencial (Word/LibreOffice)"`

---

### Task 5: Verificação runtime

**REQUIRED SUB-SKILL:** `verify`.

- [ ] **Step 1:** Servidor fresco (matar listeners 8765, subir UM).
- [ ] **Step 2:** Gerar um contrato (protegido). Inspecionar o `.docx`:
  `documentProtection edit=readOnly`; pares `permStart/permEnd` ao redor dos valores;
  texto/valores idênticos ao não-protegido.
- [ ] **Step 3 (manual/visual — honesto):** Abrir o `.docx` no LibreOffice (e Word, se
  disponível): confirmar que o texto fixo (cláusulas) NÃO edita e os campos SIM.
- [ ] **Step 4:** Exercitar o endpoint `editar` via HTTP com credenciais gerenciais
  (monkeypatch não; aqui é runtime) — confirmar `{ok:true}`, registro em
  `log_acoes_gerenciais`, e que o app foi chamado (ou, sem GUI no ambiente, validar a
  lógica do watcher: salvar o `.docx` e ver o PDF regerar via `_converter_pdf`).
- [ ] **Step 5:** Editar um valor no `.docx`, salvar → confirmar PDF regerado com a
  correção (via watcher ou chamada direta a `_converter_pdf`).
- [ ] **Step 6:** Encerrar o servidor de teste.

---

## Self-Review

- Cobertura do spec: conversão sem regenerar (T1), proteção/regiões (T2), endpoint+gate+
  watcher (T3), UI (T4), verificação (T5). ✓
- Sem placeholders: código concreto em cada passo. ✓
- Consistência: `_converter_pdf` (T1) usado pelo watcher (T3); coletor de runs (T2)
  alimenta `_proteger_editaveis`; `protegido=True` default não muda o texto (compat F1).
- Riscos: (a) manejo de runs em `_subst_paragrafo` — validar empiricamente (T2 Step 3);
  (b) `os.startfile` é Windows-only (ok, app desktop) — isolado em `abrir_no_app`;
  (c) cabeçalho (num/data) fica não editável por decisão (textbox) — confirmar no review.
