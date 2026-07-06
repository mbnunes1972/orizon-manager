# NF-e Fase 4 — Emissão real + acompanhamento (`nfe_emissao`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serviço que emite a NF-e da loja via Focus (homologação), acompanha o status por polling, guarda o XML/DANFE (`CicloDocumento`) e rastreia a emissão (`NfeEmissao`) — idempotente e com guarda contra produção — + um endpoint mínimo de teste.

**Architecture:** Tabela `NfeEmissao` (rastreio por `ref`). Módulo `nfe_emissao.py` (serviço `emitir`/`consultar`/`cancelar`, com `emissor` injetável para testes offline; em produção usa `mod_fiscal.focus_client_para_loja` + `EmissorFocusNfe`). Endpoint `POST /api/admin/lojas/<id>/nfe/emitir-teste` monta a nota (preview + mapa_fiscal) e chama o serviço. Nenhuma chamada de rede na suíte (emissor fake).

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, pytest. Reusa `mod_nfe` (Fase 1), `mapa_fiscal` (Fase 3b), `emissor_focus.EmissorFocusNfe` (Fase 3b), `mod_fiscal.focus_client_para_loja` (Sub-frente I), `emissor_fiscal` (Fase 2), `storage` (`storage_salvar_binario`, `PROJETOS_DIR`).

**Base para ler antes:** spec `docs/superpowers/specs/2026-07-05-nfe-fase4-emissao-real-design.md`. Modelo `CicloDocumento` (`database.py`: projeto_nome, etapa_codigo, tipo, arquivo_path, nome_original, enviado_por_id, enviado_em). `ResultadoEmissao`/`StatusNota`/`resultado_de_focus` em `emissor_fiscal.py`. Padrão de upload append-only (etapa 12) em `main.py` (`_parse_multipart_arquivos`, `_ator_dict`, `mod_tenancy.pode_editar_dados_loja`, `get_session`). Fixtures: `tests/conftest.py` (`app_db`, `seed` com `loja2_id`/`projeto_l2`=`Proj_L2`/`cliente_l2_id`/`dir_l2`, `projetos_dir` que rebinda `PROJETOS_DIR` e cria os projetos em disco). Fixture de XML: `tests/fixtures/nfe/nfe_basica.xml` (Fase 1).

**Lembrete de ambiente:** modelos/endpoints Python → **restart** para verificação manual; a suíte e2e sobe o próprio servidor. Baseline **507 passed**. `python3` do Bash pode ser o stub WindowsApps (usar o interpretador real, nota no DEV_LOG).

---

## File Structure

- **Modify** `database.py` — modelo `NfeEmissao` (tabela nova, auto-criada).
- **Create** `nfe_emissao.py` — serviço `emitir`/`consultar`/`cancelar` + helpers (`_guardar_doc`, `_emissor_para`, `_aplicar_resultado`, `_resultado_de_registro`).
- **Modify** `main.py` — endpoint `POST /api/admin/lojas/<id>/nfe/emitir-teste`.
- **Create** `tests/test_nfe_emissao_model.py`, `tests/test_nfe_emissao.py`, `tests/test_nfe_emitir_teste_e2e.py`.

---

## Task 1: modelo `NfeEmissao`

**Files:**
- Modify: `database.py`
- Test: `tests/test_nfe_emissao_model.py`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_nfe_emissao_model.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_modelo_nfe_emissao(tmp_path, monkeypatch):
    import database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    dbf = str(tmp_path / "t.db")
    engine = create_engine(f"sqlite:///{dbf}")
    monkeypatch.setattr(database, "DB_PATH", dbf)
    monkeypatch.setattr(database, "ENGINE", engine)
    monkeypatch.setattr(database, "Session", sessionmaker(bind=engine))
    database.init_db()
    s = database.Session()
    e = database.NfeEmissao(ref="TESTE-1", projeto_nome="Proj_L2", loja_id=1,
                            status="autorizado", chave_nfe="CH", numero="10", serie="1")
    s.add(e); s.commit()
    lido = s.query(database.NfeEmissao).filter_by(ref="TESTE-1").first()
    assert lido.status == "autorizado" and lido.chave_nfe == "CH" and lido.etapa_codigo == "15"
    # ref único
    from sqlalchemy.exc import IntegrityError
    import pytest
    s.add(database.NfeEmissao(ref="TESTE-1"))
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback(); s.close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_emissao_model.py -q`
Expected: FAIL (`AttributeError: module 'database' has no attribute 'NfeEmissao'`).

- [ ] **Step 3: Add the model to `database.py`** (após `PerfilFiscal`; imports já existem)

```python
class NfeEmissao(Base):
    """Rastreio de uma NF-e emitida pela loja (Focus). `ref` = idempotência. XML/DANFE ficam
    em CicloDocumento (etapa 15) referenciados por xml_doc_id/danfe_doc_id."""
    __tablename__ = "nfe_emissao"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    ref            = Column(Text, nullable=False, unique=True)
    projeto_nome   = Column(Text, nullable=True)
    etapa_codigo   = Column(Text, default="15")
    loja_id        = Column(Integer, ForeignKey("lojas.id"), nullable=True)
    status         = Column(Text, nullable=True)
    chave_nfe      = Column(Text, nullable=True)
    numero         = Column(Text, nullable=True)
    serie          = Column(Text, nullable=True)
    mensagem_sefaz = Column(Text, nullable=True)
    erros_json     = Column(Text, nullable=True)
    xml_doc_id     = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    danfe_doc_id   = Column(Integer, ForeignKey("ciclo_documentos.id"), nullable=True)
    emitido_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_emissao_model.py -q`
Expected: PASS (1). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_nfe_emissao_model.py
git commit -m "feat(nfe): modelo NfeEmissao (rastreio de emissao por ref)"
```

---

## Task 2: serviço `nfe_emissao.emitir` (+ helpers)

**Files:**
- Create: `nfe_emissao.py`
- Test: `tests/test_nfe_emissao.py`

- [ ] **Step 1: Create the tests**

Criar `tests/test_nfe_emissao.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import nfe_emissao
from emissor_fiscal import resultado_de_focus, StatusNota


class FakeClient:
    def __init__(self): self.baixados = []
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH123", "numero": "10", "serie": "1",
                "caminho_xml_nota_fiscal": "/nfe/xml.xml", "caminho_danfe": "/nfe/danfe.pdf"}
    def baixar(self, caminho):
        self.baixados.append(caminho)
        return b"BYTES:" + caminho.encode()


class FakeEmissor:
    def __init__(self, status="processando_autorizacao", erros=None):
        self.client = FakeClient(); self._status = status; self._erros = erros; self.emit_calls = 0
    def emitir_nfe_produto(self, nota):
        self.emit_calls += 1
        d = {"ref": nota["ref"], "status": self._status}
        if self._erros: d["erros"] = self._erros
        return resultado_de_focus(d)
    def consultar_status(self, ref):
        return resultado_de_focus({"ref": ref, "status": "autorizado", "chave_nfe": "CH",
                                   "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"})
    def cancelar(self, ref, justificativa):
        return resultado_de_focus({"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})


def _nota(ref):
    return {"ref": ref, "natureza_operacao": "Venda", "data_emissao": "D",
            "emitente": {"doc_tipo": "cnpj", "doc": "1", "nome": "L", "regime": 1, "ie": "1",
                         "logradouro": "a", "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "destinatario": {"nome": "C", "doc_tipo": "cpf", "doc": "2", "logradouro": "a", "numero": "1",
                             "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102", "pis_cst": "49", "cofins_cst": "49"},
            "itens": [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN", "qCom": 1.0, "preco_venda_unit": 10.0}]}


def _reset(app_db, ref, proj):
    db = app_db.get_session()
    db.query(app_db.NfeEmissao).filter_by(ref=ref).delete()
    db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").delete()
    db.commit(); db.close()


def _perfil(app_db, loja_id, ambiente="homologacao"):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.add(app_db.PerfilFiscal(loja_id=loja_id, ambiente_ativo=ambiente, csosn_padrao="101",
                               cfop_dentro_uf="5102", cfop_fora_uf="6102"))
    db.commit(); db.close()


def test_emitir_autoriza_guarda_docs(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-1", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-1"), emissor=fake)
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH123"
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-1").first()
    assert reg.status == "autorizado" and reg.xml_doc_id and reg.danfe_doc_id
    docs = db.query(app_db.CicloDocumento).filter_by(projeto_nome=proj, etapa_codigo="15").all()
    assert {d.tipo for d in docs} == {"nfe_loja_xml", "nfe_loja_danfe"}
    assert fake.client.baixados == ["/nfe/xml.xml", "/nfe/danfe.pdf"]
    db.close()


def test_emitir_idempotente(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-2", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor()
    db = app_db.get_session()
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emissor=fake)
    nfe_emissao.emitir(db, lid, proj, _nota("R-2"), emissor=fake)   # já autorizada
    assert fake.emit_calls == 1                                     # não re-emitiu
    db.close()


def test_emitir_guarda_producao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-3", proj); _perfil(app_db, lid, "producao")
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.emitir(db, lid, proj, _nota("R-3"), emissor=FakeEmissor())
    # com permitir_producao=True emite
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-3"), permitir_producao=True, emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    db.close()


def test_emitir_erro_autorizacao(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-4", proj); _perfil(app_db, lid, "homologacao")
    fake = FakeEmissor(status="erro_autorizacao", erros=[{"codigo": "215", "mensagem": "falha"}])
    db = app_db.get_session()
    res = nfe_emissao.emitir(db, lid, proj, _nota("R-4"), emissor=fake)
    assert res.status == StatusNota.ERRO
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-4").first()
    assert reg.status == "erro" and reg.erros_json and not reg.xml_doc_id
    db.close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_emissao.py -q`
Expected: FAIL (`No module named 'nfe_emissao'`).

- [ ] **Step 3: Create `nfe_emissao.py`**

```python
"""nfe_emissao.py — serviço de emissão da NF-e da loja via Focus (Fase 4).
Emite, acompanha (polling), guarda XML/DANFE (CicloDocumento) e rastreia (NfeEmissao).
Testável offline: `emissor` é injetável. Nenhuma UI/rota aqui."""
import os
import json
import uuid
from datetime import datetime

import storage
from database import NfeEmissao, PerfilFiscal, CicloDocumento
from emissor_fiscal import StatusNota, ResultadoEmissao, resultado_de_focus

_TIPO_XML = "nfe_loja_xml"
_TIPO_DANFE = "nfe_loja_danfe"
_TIPO_CANC = "nfe_loja_cancelamento_xml"


def _emissor_para(db, loja_id):
    import mod_fiscal
    from emissor_focus import EmissorFocusNfe
    return EmissorFocusNfe(mod_fiscal.focus_client_para_loja(db, loja_id))


def _guardar_doc(db, projeto_nome, tipo, caminho_focus, client):
    if not projeto_nome or not caminho_focus:
        return None
    data = client.baixar(caminho_focus)
    base = os.path.basename(caminho_focus) or (tipo + ".bin")
    unico = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8] + "_" + base
    rel = os.path.join("ciclo", "15", unico)
    doc = CicloDocumento(projeto_nome=projeto_nome, etapa_codigo="15", tipo=tipo,
                         arquivo_path=rel, nome_original=base)
    db.add(doc)
    db.flush()   # doc.id
    storage.storage_salvar_binario(os.path.join(storage.PROJETOS_DIR, projeto_nome, rel), data)
    return doc


def _aplicar_resultado(reg, res):
    reg.status = res.status.value if hasattr(res.status, "value") else res.status
    reg.chave_nfe = res.chave
    reg.numero = res.numero
    reg.serie = res.serie
    reg.mensagem_sefaz = res.mensagem_sefaz
    reg.erros_json = json.dumps(res.erros, ensure_ascii=False) if res.erros else None


def _resultado_de_registro(reg):
    st = StatusNota(reg.status) if reg.status else StatusNota.DESCONHECIDO
    return ResultadoEmissao(ref=reg.ref, status=st, chave=reg.chave_nfe, numero=reg.numero,
                            serie=reg.serie, mensagem_sefaz=reg.mensagem_sefaz)


def _guardar_docs_autorizado(db, reg, res, client):
    xml_doc = _guardar_doc(db, reg.projeto_nome, _TIPO_XML, res.xml_url, client)
    danfe_doc = _guardar_doc(db, reg.projeto_nome, _TIPO_DANFE, res.danfe_url, client)
    if xml_doc:
        reg.xml_doc_id = xml_doc.id
    if danfe_doc:
        reg.danfe_doc_id = danfe_doc.id


def emitir(db, loja_id, projeto_nome, nota, permitir_producao=False, emissor=None):
    """Emite (ou devolve idempotente), acompanha até o status final e guarda XML/DANFE."""
    ref = nota["ref"]
    reg = db.query(NfeEmissao).filter_by(ref=ref).first()
    if reg and reg.status == "autorizado":
        return _resultado_de_registro(reg)
    pf = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
    ambiente = (pf.ambiente_ativo if pf else "homologacao") or "homologacao"
    if ambiente == "producao" and not permitir_producao:
        raise ValueError("Emissão em produção bloqueada (use permitir_producao=True).")
    if emissor is None:
        emissor = _emissor_para(db, loja_id)
    res = emissor.emitir_nfe_produto(nota)
    if res.status == StatusNota.PROCESSANDO:
        res = resultado_de_focus(emissor.client.aguardar_processamento(ref))
    if not reg:
        reg = NfeEmissao(ref=ref, projeto_nome=projeto_nome, loja_id=loja_id, etapa_codigo="15")
        db.add(reg)
    _aplicar_resultado(reg, res)
    if res.status == StatusNota.AUTORIZADO:
        _guardar_docs_autorizado(db, reg, res, emissor.client)
    db.commit()
    return res


def consultar(db, ref, emissor=None):
    """Reconsulta o status e atualiza o registro (baixa docs se recém-autorizado)."""
    reg = db.query(NfeEmissao).filter_by(ref=ref).first()
    if not reg:
        raise ValueError("NfeEmissao %s não encontrada" % (ref,))
    if emissor is None:
        emissor = _emissor_para(db, reg.loja_id)
    res = emissor.consultar_status(ref)
    ja_tinha = reg.xml_doc_id is not None
    _aplicar_resultado(reg, res)
    if res.status == StatusNota.AUTORIZADO and not ja_tinha:
        _guardar_docs_autorizado(db, reg, res, emissor.client)
    db.commit()
    return res


def cancelar(db, ref, justificativa, emissor=None):
    """Cancela na Focus e atualiza o registro (guarda o XML de cancelamento)."""
    reg = db.query(NfeEmissao).filter_by(ref=ref).first()
    if not reg:
        raise ValueError("NfeEmissao %s não encontrada" % (ref,))
    if emissor is None:
        emissor = _emissor_para(db, reg.loja_id)
    res = emissor.cancelar(ref, justificativa)
    _aplicar_resultado(reg, res)
    if res.xml_cancelamento_url:
        doc = _guardar_doc(db, reg.projeto_nome, _TIPO_CANC, res.xml_cancelamento_url, emissor.client)
        # (não há coluna dedicada; o XML de cancelamento fica como CicloDocumento da etapa 15)
    db.commit()
    return res
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_emissao.py -q`
Expected: PASS (4 testes). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add nfe_emissao.py tests/test_nfe_emissao.py
git commit -m "feat(nfe): servico nfe_emissao.emitir (emite, acompanha, guarda XML/DANFE, idempotente)"
```

---

## Task 3: `consultar` + `cancelar` (testes)

`consultar`/`cancelar` já foram implementados na Task 2. Esta task só adiciona a cobertura.

**Files:**
- Test: `tests/test_nfe_emissao.py` (adicionar)

- [ ] **Step 1: Write the tests**

Adicionar em `tests/test_nfe_emissao.py`:

```python
def test_consultar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-5", proj); _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.NfeEmissao(ref="R-5", projeto_nome=proj, loja_id=lid, status="processando"))
    db.commit()
    res = nfe_emissao.consultar(db, "R-5", emissor=FakeEmissor())
    assert res.status == StatusNota.AUTORIZADO
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-5").first()
    assert reg.status == "autorizado" and reg.xml_doc_id       # baixou docs ao autorizar
    db.close()


def test_cancelar_atualiza_registro(app_db, seed, projetos_dir):
    proj = seed["projeto_l2"]; lid = seed["loja2_id"]
    _reset(app_db, "R-6", proj); _perfil(app_db, lid, "homologacao")
    db = app_db.get_session()
    db.add(app_db.NfeEmissao(ref="R-6", projeto_nome=proj, loja_id=lid, status="autorizado"))
    db.commit()
    res = nfe_emissao.cancelar(db, "R-6", "cancelamento por erro de digitacao", emissor=FakeEmissor())
    assert res.status == StatusNota.CANCELADO
    reg = db.query(app_db.NfeEmissao).filter_by(ref="R-6").first()
    assert reg.status == "cancelado"
    db.close()


def test_consultar_ref_inexistente(app_db, seed, projetos_dir):
    db = app_db.get_session()
    with pytest.raises(ValueError):
        nfe_emissao.consultar(db, "NAO-EXISTE", emissor=FakeEmissor())
    db.close()
```

- [ ] **Step 2: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_emissao.py -q`
Expected: PASS (7 testes). (A implementação já existe da Task 2.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_nfe_emissao.py
git commit -m "test(nfe): cobertura de consultar/cancelar do nfe_emissao"
```

---

## Task 4: endpoint `POST …/nfe/emitir-teste`

**Files:**
- Modify: `main.py` (import de `NfeEmissao` se preciso; endpoint em `do_POST`)
- Test: `tests/test_nfe_emitir_teste_e2e.py`

- [ ] **Step 1: Create the e2e test**

Criar `tests/test_nfe_emitir_teste_e2e.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import uuid as _uuid, json as _json
import urllib.request, urllib.error
import nfe_emissao
from emissor_fiscal import resultado_de_focus


class FakeClient:
    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH999",
                "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    def baixar(self, caminho): return b"BYTES"


class FakeEmissor:
    def __init__(self): self.client = FakeClient()
    def emitir_nfe_produto(self, nota): return resultado_de_focus({"ref": nota["ref"], "status": "processando_autorizacao"})


def _post_multipart(base, cookie, path, fields, filename, filedata):
    boundary = "----t" + _uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(("--"+boundary+"\r\n").encode())
        parts.append((f'Content-Disposition: form-data; name="{k}"\r\n\r\n').encode())
        parts.append((str(v)+"\r\n").encode())
    parts.append(("--"+boundary+"\r\n").encode())
    parts.append((f'Content-Disposition: form-data; name="arquivo"; filename="{filename}"\r\n').encode())
    parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
    parts.append(filedata); parts.append(b"\r\n")
    parts.append(("--"+boundary+"--\r\n").encode())
    req = urllib.request.Request(base+path, data=b"".join(parts), method="POST")
    req.add_header("Content-Type", "multipart/form-data; boundary="+boundary)
    if cookie: req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, _json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read() or b"{}")


def _login(factory, who):
    c = factory(); c.login(who, "senha123"); assert c.cookie; return c


def _fixture_xml():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "nfe", "nfe_basica.xml"), "rb") as f:
        return f.read()


def _perfil(app_db, loja_id):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.add(app_db.PerfilFiscal(loja_id=loja_id, ambiente_ativo="homologacao", razao_social="LOJA X",
                               csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102"))
    db.commit(); db.close()


def test_emitir_teste_ok(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    _perfil(app_db, seed["loja2_id"])
    c = _login(http_client_factory, "dir_l2")
    proj = seed["projeto_l2"]
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": proj, "markup_pct": "30"}, "fabrica.xml", _fixture_xml())
    assert st == 200 and b.get("ok") is True, b
    assert b["status"] == "autorizado" and b["chave"] == "CH999" and b["xml_doc_id"]


def test_emitir_teste_sem_perfil_400(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, lid: FakeEmissor())
    db = app_db.get_session(); db.query(app_db.PerfilFiscal).filter_by(loja_id=seed["loja2_id"]).delete(); db.commit(); db.close()
    c = _login(http_client_factory, "dir_l2")
    st, b = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja2_id']}/nfe/emitir-teste",
                            {"projeto_nome": seed["projeto_l2"], "markup_pct": "30"}, "f.xml", _fixture_xml())
    assert st == 400


def test_emitir_teste_perm_403(http_client_factory, seed, app_db, projetos_dir):
    c = _login(http_client_factory, "cons_l1")     # sem editar_dados_loja
    st, _ = _post_multipart(c.base, c.cookie, f"/api/admin/lojas/{seed['loja1_id']}/nfe/emitir-teste",
                            {"projeto_nome": seed["projeto_l1"], "markup_pct": "30"}, "f.xml", _fixture_xml())
    assert st == 403
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_nfe_emitir_teste_e2e.py -q`
Expected: FAIL (rota inexistente → 404/erro).

- [ ] **Step 3: Add the endpoint in `main.py` (`do_POST`)**

Garantir que `NfeEmissao` está importado de `database` no topo (adicionar à linha `from database import (...)` se necessário — o endpoint em si não usa `NfeEmissao` diretamente, mas o serviço sim; não é obrigatório importá-lo no main). Inserir o bloco no `do_POST` (usar o alias `_re` dos blocos vizinhos):

```python
            # POST /api/admin/lojas/<id>/nfe/emitir-teste — emissão de teste (homologação)
            m = _re.match(r'^/api/admin/lojas/(\d+)/nfe/emitir-teste$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_nfe, mapa_fiscal, nfe_emissao
                arquivos, campos = _parse_multipart_arquivos(body, self.headers.get("Content-Type", ""))
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    perfil = db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()
                    if not perfil:
                        self.send_json({"ok": False, "erro": "Configure o Perfil Fiscal da loja antes de emitir."}, code=400); return
                    if "arquivo" not in arquivos:
                        self.send_json({"ok": False, "erro": "Anexe o XML da fábrica."}, code=400); return
                    projeto_nome = campos.get("projeto_nome")
                    projeto = db.get(Projeto, projeto_nome) if projeto_nome else None
                    if not projeto:
                        self.send_json({"ok": False, "erro": "Informe um projeto válido da loja."}, code=400); return
                    cliente = db.get(Cliente, projeto.cliente_id) if projeto.cliente_id else None
                    if not cliente:
                        self.send_json({"ok": False, "erro": "O projeto não tem cliente para o destinatário."}, code=400); return
                    try:
                        markup = float(campos.get("markup_pct") or 0)
                    except ValueError:
                        markup = 0.0
                    _fname, data = arquivos["arquivo"]
                    preview = mod_nfe.preview(data, markup)
                    ref = "TESTE-" + datetime.utcnow().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]
                    data_emissao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-03:00")
                    nota = mapa_fiscal.montar_nota(perfil, loja, cliente, preview["itens"], ref, data_emissao)
                    res = nfe_emissao.emitir(db, loja.id, projeto_nome, nota)
                    self.send_json({"ok": True, "ref": ref,
                                    "status": res.status.value if hasattr(res.status, "value") else res.status,
                                    "chave": res.chave, "numero": res.numero, "serie": res.serie,
                                    "mensagem_sefaz": res.mensagem_sefaz, "erros": res.erros,
                                    "xml_doc_id": (db.query(NfeEmissao).filter_by(ref=ref).first() or NfeEmissao()).xml_doc_id,
                                    "danfe_doc_id": (db.query(NfeEmissao).filter_by(ref=ref).first() or NfeEmissao()).danfe_doc_id})
                except ValueError as e:
                    self.send_json({"ok": False, "erro": str(e)}, code=400)
                except Exception as e:
                    db.rollback(); self.send_json({"ok": False, "erro": "Falha na emissão: " + str(e)}, code=500)
                finally:
                    db.close()
                return
```

Para o `xml_doc_id`/`danfe_doc_id` na resposta, importar `NfeEmissao` no topo do `main.py` (`from database import (... PerfilFiscal, NfeEmissao)`). Confirmar que `Projeto`, `Cliente`, `PerfilFiscal`, `Loja`, `datetime`, `uuid` estão em escopo (Projeto/Cliente/Loja/PerfilFiscal via import de models; `datetime`/`uuid` já usados no arquivo).

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_nfe_emitir_teste_e2e.py -q`
Expected: PASS (3 testes). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_nfe_emitir_teste_e2e.py
git commit -m "feat(nfe): endpoint POST .../nfe/emitir-teste (emissao de teste em homologacao)"
```

---

## Task 5: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/2026-07-05-nfe-fase4-emissao-real-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar `> Status: **APROVADO (brainstorming)** — a implementar. Emite a NF-e...` por
`> Status: **IMPLEMENTADO (Sessão N)** — serviço + endpoint com testes offline; smoke real em homologação pendente do token da Focus.`

- [ ] **Step 3: DEV_LOG — atualizar o mapa do módulo fiscal**

Na tabela de fases do `⏸️ ESTADO ATUAL`, marcar **Fase 4** como ✅ (serviço `nfe_emissao` + modelo `NfeEmissao`
+ endpoint `emitir-teste`, testes offline; **smoke real pendente do token**). Registrar que o gatilho real é
o token no perfil da loja (painel → Credenciais Focus). Atualizar contagens se re-ingerir.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/2026-07-05-nfe-fase4-emissao-real-design.md
git commit -m "docs(nfe): DEV_LOG + spec Fase 4 como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §3 modelo (Task 1), §4 serviço `emitir` (Task 2) + `consultar`/`cancelar`
  (impl na Task 2, testes na Task 3), §5 endpoint (Task 4), §7 testes distribuídos (autoriza+docs,
  idempotência, guarda de produção, erro, consultar/cancelar, e2e do endpoint). §6 segurança (guarda de
  produção testada; token nunca logado). §8 fora de escopo respeitado (sem UI etapa 15).
- **Consistência de nomes:** `NfeEmissao` (colunas), `emitir/consultar/cancelar(db, …, emissor=None)`,
  `_guardar_doc`, `_emissor_para`, tipos `nfe_loja_xml`/`nfe_loja_danfe`, `StatusNota` values
  (`autorizado`/`erro`/`cancelado`/`processando`) idênticos entre modelo, serviço, endpoint e testes.
  O emissor fake espelha a interface real (`emitir_nfe_produto`/`consultar_status`/`cancelar` + `.client`
  com `aguardar_processamento`/`baixar`).
- **Sem placeholders:** todo passo com código completo. `Sessão N` = número corrente do DEV_LOG na hora.
```
