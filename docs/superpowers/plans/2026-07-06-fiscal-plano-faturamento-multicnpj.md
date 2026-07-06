# Fiscal — Plano de Faturamento multi-CNPJ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) ou superpowers:executing-plans para implementar tarefa a tarefa. Passos usam checkbox (`- [ ]`).

**Goal:** Desacoplar "quem vende" de "quem emite" na base fiscal: `Emitente` de 1ª classe + Perfil de Emissão (loja/rede) + `documento_fiscal` (tipo+emitente), re-plataformando a emissão de NF-e de produto. NFS-e fica como slot modelado.

**Architecture:** Aditivo primeiro (Emitente + resolução, sem consumir), depois generaliza `NfeEmissao→documento_fiscal`, depois **troca** a emissão de produto para resolver o emitente por documento, por fim limpa `perfil_fiscal`. Suíte verde a cada tarefa. Branch `feat/fiscal-emitente-multicnpj`.

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `http.server`, pytest; frontend HTML/JS inline. Base: spec `docs/superpowers/specs/2026-07-06-fiscal-plano-faturamento-multicnpj-design.md`.

**Ler antes:** o spec acima; `database.py` (modelos `PerfilFiscal` ~501-539, `NfeEmissao` ~542-561, `Loja` ~194, `Rede` ~183, `_migrar_colunas`/`_migrar_dados` ~570+); `mod_fiscal.py` (`perfil_padrao_teste`, `focus_client_para_loja`); `mapa_fiscal.py` (`montar_nota` 9-45, `montar_payload`); `nfe_emissao.py` (`_emissor_para`, `emitir`, `consultar`, `cancelar`); `main.py` endpoint `…/ciclo/15/emitir-nfe` (~4160-4290) e o `emitir-teste` (Fase 4). Testes atuais: `tests/test_perfil_fiscal_model.py`, `test_perfil_fiscal_e2e.py`, `test_mod_fiscal.py`, `test_mapa_fiscal.py`, `test_nfe_emissao*.py`, `test_nfe_etapa15_e2e.py`, `test_nfe_emitir_teste_e2e.py`.

**Ambiente:** teste `python3 -m pytest -q` (fallback `C:\Users\mbn19\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -q`); **baseline 532 passed**. `git add` só os arquivos da mudança. Migração de coluna segue o padrão `PRAGMA table_info`/`ALTER TABLE` de `_migrar_colunas`; migração de dados (backfill/rename) em `_migrar_dados`.

---

## File Structure
- **Modify** `database.py` — `Emitente`, `PerfilEmissao`, `DocumentoFiscal` (rename de `NfeEmissao`), `Loja.emitente_id`, `Rede.emitente_central_id`; migrações.
- **Modify** `mod_fiscal.py` — `resolver_emitente`, `resolver_plano`, `focus_client_para_emitente`.
- **Modify** `mapa_fiscal.py` — `montar_nota(emitente, …)`.
- **Modify** `nfe_emissao.py` — `emitir(…, tipo_documento, emitente_id)`, `_emissor_para(emitente_id)`, consultar/cancelar por `emitente_id`.
- **Modify** `main.py` — endpoint `…/ciclo/15/emitir-nfe` resolve emitente; consultar/cancelar; GET estado mostra emitente.
- **Modify** `static/index.html` — painel etapa 15 mostra o emitente.
- **Modify** testes acima + **Create** `tests/test_emitente_model.py`, `tests/test_resolver_emissao.py`.

---

## Task 1: `Emitente` (absorve PerfilFiscal) + vínculos + migração (aditivo)

**Files:** Modify `database.py`; Create `tests/test_emitente_model.py`.

- [ ] **Step 1: Teste falhando (modelo + migração)**

`tests/test_emitente_model.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import database

def _fresh(tmp_path, monkeypatch):
    db_file = tmp_path / "t.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    monkeypatch.setattr(database, "ENGINE", database.create_engine(f"sqlite:///{db_file}"))
    database.Base.metadata.create_all(database.ENGINE)
    database.SessionLocal = database.sessionmaker(bind=database.ENGINE)
    return database

def test_emitente_persiste_campos_fiscais(tmp_path, monkeypatch):
    db = _fresh(tmp_path, monkeypatch); s = db.SessionLocal()
    e = db.Emitente(cnpj="19152134000156", razao_social="LOJA X", regime_tributario="simples",
                    csosn_padrao="101", cfop_dentro_uf="5102", cfop_fora_uf="6102", uf="SP",
                    cidade="SAO PAULO", ambiente_ativo="homologacao", papel_cnpj="loja_produto_servico")
    s.add(e); s.commit(); eid = e.id
    lido = s.query(db.Emitente).get(eid)
    assert lido.cnpj == "19152134000156" and lido.uf == "SP" and lido.ambiente_ativo == "homologacao"
    s.close()

def test_loja_e_rede_referenciam_emitente(tmp_path, monkeypatch):
    db = _fresh(tmp_path, monkeypatch); s = db.SessionLocal()
    e = db.Emitente(cnpj="1"); s.add(e); s.flush()
    r = db.Rede(nome="R", emitente_central_id=e.id); s.add(r); s.flush()
    l = db.Loja(nome="L", rede_id=r.id, emitente_id=e.id); s.add(l); s.commit()
    assert s.query(db.Loja).first().emitente_id == e.id
    assert s.query(db.Rede).first().emitente_central_id == e.id
    s.close()
```
> Se o boilerplate `_fresh` divergir da forma real de criar sessão de teste no projeto, use a fixture
> `app_db` do `conftest` (como os demais testes de modelo fazem) em vez de recriar o engine.

- [ ] **Step 2: Rodar → falha** `python3 -m pytest tests/test_emitente_model.py -q` → FAIL (Emitente/colunas inexistentes).

- [ ] **Step 3: Adicionar `Emitente` em `database.py`** (após `PerfilFiscal`; copiar os campos fiscais de `PerfilFiscal` + endereço do emitente):
```python
class Emitente(Base):
    """Identidade fiscal de 1 CNPJ (absorve PerfilFiscal). Emite documentos; NÃO é a loja vendedora."""
    __tablename__ = "emitente"
    id = Column(Integer, primary_key=True, autoincrement=True)
    cnpj = Column(String(18), nullable=True)
    razao_social = Column(Text, nullable=True)
    nome_fantasia = Column(Text, nullable=True)
    inscricao_estadual = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)
    regime_tributario = Column(Text, nullable=True)
    csosn_padrao = Column(Text, nullable=True)
    cfop_dentro_uf = Column(Text, nullable=True)
    cfop_fora_uf = Column(Text, nullable=True)
    serie_nfe = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)
    cnae_servico = Column(Text, nullable=True)
    cod_servico_municipio = Column(Text, nullable=True)
    aliquota_iss = Column(Float, nullable=True)
    retencao_json = Column(Text, nullable=True)
    municipio_ibge = Column(Text, nullable=True)
    logradouro = Column(Text, nullable=True)
    numero = Column(Text, nullable=True)
    bairro = Column(Text, nullable=True)
    cidade = Column(Text, nullable=True)
    uf = Column(Text, nullable=True)
    cep = Column(Text, nullable=True)
    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj = Column(Text, nullable=True)
    papel_cnpj = Column(Text, nullable=True)
    focus_token_homolog_enc = Column(Text, nullable=True)
    focus_token_prod_enc = Column(Text, nullable=True)
    ambiente_ativo = Column(Text, default="homologacao")
    placeholders_json = Column(Text, nullable=True)
    rede_id = Column(Integer, ForeignKey("redes.id"), nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```
Adicionar em `Loja`: `emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)`.
Adicionar em `Rede`: `emitente_central_id = Column(Integer, ForeignKey("emitente.id"), nullable=True)`.

- [ ] **Step 4: Migração de colunas** em `_migrar_colunas` (idempotente, padrão do arquivo): `ALTER TABLE lojas ADD COLUMN emitente_id INTEGER` e `ALTER TABLE redes ADD COLUMN emitente_central_id INTEGER` (guardados por `PRAGMA table_info`). A tabela `emitente` é criada por `create_all`.

- [ ] **Step 5: Migração de dados** em `_migrar_dados` — backfill `perfil_fiscal → emitente` + `loja.emitente_id` (idempotente):
```python
        # perfil_fiscal -> emitente (1 por loja/CNPJ); loja.emitente_id = self
        cur.execute("PRAGMA table_info(emitente)")
        if cur.fetchall():
            cur.execute("SELECT id, loja_id, razao_social, inscricao_estadual, inscricao_municipal, regime_tributario, csosn_padrao, cfop_dentro_uf, cfop_fora_uf, serie_nfe, discrimina_impostos, cnae_servico, cod_servico_municipio, aliquota_iss, retencao_json, municipio_ibge, cert_validade, cert_cnpj, papel_cnpj, focus_token_homolog_enc, focus_token_prod_enc, ambiente_ativo, placeholders_json FROM perfil_fiscal")
            for row in cur.fetchall():
                loja_id = row[1]
                cur.execute("SELECT emitente_id FROM lojas WHERE id=?", (loja_id,))
                lj = cur.fetchone()
                if lj and lj[0]:
                    continue   # já migrado
                cur.execute("SELECT cnpj, logradouro, numero, bairro, cidade, estado, cep FROM lojas WHERE id=?", (loja_id,))
                lo = cur.fetchone() or (None,)*7
                cur.execute("""INSERT INTO emitente (cnpj, razao_social, inscricao_estadual, inscricao_municipal, regime_tributario, csosn_padrao, cfop_dentro_uf, cfop_fora_uf, serie_nfe, discrimina_impostos, cnae_servico, cod_servico_municipio, aliquota_iss, retencao_json, municipio_ibge, logradouro, numero, bairro, cidade, uf, cep, cert_validade, cert_cnpj, papel_cnpj, focus_token_homolog_enc, focus_token_prod_enc, ambiente_ativo, placeholders_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (lo[0], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11], row[12], row[13], row[14], row[15],
                     lo[1], lo[2], lo[3], lo[4], lo[5], lo[6], row[16], row[17], row[18], row[19], row[20], row[21], row[22]))
                cur.execute("UPDATE lojas SET emitente_id=? WHERE id=?", (cur.lastrowid, loja_id))
            conn.commit()
```
> Confirme os nomes reais das colunas de `perfil_fiscal`/`lojas` (`estado` vs `uf`) e ajuste o SELECT/INSERT.

- [ ] **Step 6: Rodar** `python3 -m pytest -q` → verde (esperado 534). **Commit:**
```
git add database.py tests/test_emitente_model.py
git commit -m "feat(fiscal): Emitente (1a classe, absorve PerfilFiscal) + Loja.emitente_id/Rede.emitente_central_id + migracao"
```

---

## Task 2: `PerfilEmissao` + resolução (`resolver_emitente`/`resolver_plano`/`focus_client_para_emitente`)

**Files:** Modify `database.py`, `mod_fiscal.py`; Create `tests/test_resolver_emissao.py`.

- [ ] **Step 1: Teste falhando** `tests/test_resolver_emissao.py` (usa `app_db`):
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_fiscal

def _setup(app_db):
    db = app_db.get_session()
    ec = app_db.Emitente(cnpj="CENTRAL"); es = app_db.Emitente(cnpj="LOJA"); db.add_all([ec, es]); db.flush()
    rede = app_db.Rede(nome="Orizon", emitente_central_id=ec.id); db.add(rede); db.flush()
    loja = app_db.Loja(nome="Inspirium", rede_id=rede.id, emitente_id=es.id); db.add(loja); db.flush()
    # política da rede: produto -> central
    db.add(app_db.PerfilEmissao(owner_tipo="rede", owner_id=rede.id, tipo_doc="produto", emitente_id=ec.id))
    db.commit()
    return db, loja, ec, es

def test_resolver_produto_default_rede(app_db):
    db, loja, ec, es = _setup(app_db)
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == ec.id   # rede default
    assert mod_fiscal.resolver_emitente(db, loja, "servico").id == es.id   # self (sem política)
    db.close()

def test_resolver_override_loja(app_db):
    db, loja, ec, es = _setup(app_db)
    db.add(app_db.PerfilEmissao(owner_tipo="loja", owner_id=loja.id, tipo_doc="produto", emitente_id=es.id))
    db.commit()
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == es.id   # override loja vence
    db.close()

def test_resolver_avulsa_self(app_db):
    db = app_db.get_session()
    e = app_db.Emitente(cnpj="AV"); db.add(e); db.flush()
    loja = app_db.Loja(nome="Avulsa", rede_id=None, emitente_id=e.id); db.add(loja); db.commit()
    assert mod_fiscal.resolver_emitente(db, loja, "produto").id == e.id
    assert mod_fiscal.resolver_emitente(db, loja, "servico").id == e.id
    db.close()
```

- [ ] **Step 2: Rodar → falha** (`PerfilEmissao`/`resolver_emitente` inexistentes).

- [ ] **Step 3: `PerfilEmissao` em `database.py`** + migração (tabela nova via `create_all`):
```python
class PerfilEmissao(Base):
    """Política: qual Emitente assina cada tipo de documento, por owner (loja|rede)."""
    __tablename__ = "perfil_emissao"
    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_tipo = Column(Text, nullable=False)   # "loja" | "rede"
    owner_id = Column(Integer, nullable=False)
    tipo_doc = Column(Text, nullable=False)      # "produto" | "servico"
    emitente_id = Column(Integer, ForeignKey("emitente.id"), nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Funções em `mod_fiscal.py`:**
```python
def resolver_emitente(db, loja, tipo_doc):
    """Emitente que assina tipo_doc para esta loja: override loja -> default rede -> self."""
    from database import PerfilEmissao, Emitente
    pe = db.query(PerfilEmissao).filter_by(owner_tipo="loja", owner_id=loja.id, tipo_doc=tipo_doc).first()
    if not pe and getattr(loja, "rede_id", None):
        pe = db.query(PerfilEmissao).filter_by(owner_tipo="rede", owner_id=loja.rede_id, tipo_doc=tipo_doc).first()
    if pe:
        return db.get(Emitente, pe.emitente_id)
    if getattr(loja, "emitente_id", None):
        return db.get(Emitente, loja.emitente_id)   # self
    raise ValueError("Loja %s sem emitente para %s (configure o Perfil de Emissão)." % (loja.id, tipo_doc))


def resolver_plano(db, projeto, tem_produto=True, tem_servico=False):
    """Plano de faturamento: lista de {tipo_doc, emitente} conforme a venda tem mercadoria/serviço."""
    from database import Loja
    loja = db.get(Loja, projeto.loja_id)
    plano = []
    if tem_produto:
        plano.append({"tipo_doc": "produto", "emitente": resolver_emitente(db, loja, "produto")})
    if tem_servico:
        plano.append({"tipo_doc": "servico", "emitente": resolver_emitente(db, loja, "servico")})
    return plano


def focus_client_para_emitente(db, emitente_id):
    """FocusClient a partir do Emitente (token do ambiente_ativo, decriptado)."""
    import fiscal_cripto, focus_config
    from focus_client import FocusClient
    from database import Emitente
    em = db.get(Emitente, emitente_id)
    if not em:
        raise ValueError("Emitente %s inexistente" % (emitente_id,))
    amb = em.ambiente_ativo or "homologacao"
    enc = em.focus_token_homolog_enc if amb == "homologacao" else em.focus_token_prod_enc
    if not enc:
        raise ValueError("Emitente %s sem token Focus para %s" % (emitente_id, amb))
    return FocusClient(token=fiscal_cripto.decrypt(enc), base_url=focus_config.base_url_de(amb))
```
> `resolver_plano` recebe `tem_produto`/`tem_servico` como entrada por ora (detecção fina fica p/ depois).

- [ ] **Step 5: Rodar** os testes de resolução → passam; `pytest -q` → verde. **Commit:**
```
git add database.py mod_fiscal.py tests/test_resolver_emissao.py
git commit -m "feat(fiscal): PerfilEmissao + resolver_emitente/resolver_plano/focus_client_para_emitente"
```

---

## Task 3: `NfeEmissao → DocumentoFiscal` (+ `tipo_documento`, `emitente_id`)

**Files:** Modify `database.py`, `nfe_emissao.py`, `main.py`, `tests/test_nfe_emissao_model.py` (e demais refs).

- [ ] **Step 1: Teste falhando** — em `tests/test_nfe_emissao_model.py`, trocar `NfeEmissao` por `DocumentoFiscal` e adicionar campos:
```python
    d = database.DocumentoFiscal(ref="R-1", venda_ref="Proj_L2", tipo_documento="produto",
                                 emitente_id=1, loja_id=1, fabrica_doc_id=7, status="autorizado")
    ...
    assert lido.tipo_documento == "produto" and lido.emitente_id == 1 and lido.fabrica_doc_id == 7
```

- [ ] **Step 2: Rodar → falha.**

- [ ] **Step 3: Renomear o modelo em `database.py`** — `class NfeEmissao` → `class DocumentoFiscal`, `__tablename__ = "documento_fiscal"`; renomear `projeto_nome` → `venda_ref` (manter coluna `projeto_nome`? preferir `venda_ref`), adicionar:
```python
    tipo_documento = Column(Text, default="produto")   # produto | servico
    emitente_id    = Column(Integer, ForeignKey("emitente.id"), nullable=True)
```
Manter `loja_id` (escopo da venda). Manter `ref` unique, `fabrica_doc_id`, `xml_doc_id`, `danfe_doc_id`, etc.

- [ ] **Step 4: Migração de dados** em `_migrar_dados` — renomear tabela + colunas + backfill (idempotente):
```python
        cur.execute("PRAGMA table_info(nfe_emissao)")
        if cur.fetchall():   # ainda não renomeada
            cur.execute("ALTER TABLE nfe_emissao RENAME TO documento_fiscal")
        cur.execute("PRAGMA table_info(documento_fiscal)")
        dcols = [r[1] for r in cur.fetchall()]
        if "tipo_documento" not in dcols:
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN tipo_documento TEXT DEFAULT 'produto'")
        if "emitente_id" not in dcols:
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN emitente_id INTEGER")
        if "venda_ref" not in dcols:
            cur.execute("ALTER TABLE documento_fiscal ADD COLUMN venda_ref TEXT")
            cur.execute("UPDATE documento_fiscal SET venda_ref = projeto_nome WHERE venda_ref IS NULL")
        # backfill emitente_id = emitente da loja_id
        cur.execute("UPDATE documento_fiscal SET emitente_id=(SELECT emitente_id FROM lojas WHERE lojas.id=documento_fiscal.loja_id) WHERE emitente_id IS NULL")
        conn.commit()
```

- [ ] **Step 5: Atualizar refs de `NfeEmissao`** em `nfe_emissao.py` e `main.py` → `DocumentoFiscal`; e `projeto_nome=` nas queries → `venda_ref=` (ou manter compat lendo ambos). Rodar `grep -rn "NfeEmissao" *.py` até zerar (fora de docs).

- [ ] **Step 6: Rodar** `pytest -q` → verde (ajustar os testes que ainda citam `NfeEmissao`). **Commit:**
```
git add database.py nfe_emissao.py main.py tests/
git commit -m "refactor(fiscal): NfeEmissao -> DocumentoFiscal (tipo_documento + emitente_id) + migracao"
```

---

## Task 4: Re-plataforma da emissão de produto (resolver emitente por documento)

**Files:** Modify `mapa_fiscal.py`, `nfe_emissao.py`, `main.py`, testes fiscais.

- [ ] **Step 1: Testes falhando** — adaptar `test_mapa_fiscal.py` para `montar_nota(emitente, cliente, …)` e adicionar em `test_nfe_etapa15_e2e.py` o **caso multi-CNPJ**:
```python
def test_emitir_produto_sob_emitente_da_rede(http_client_factory, seed, app_db, projetos_dir, monkeypatch):
    monkeypatch.setattr(nfe_emissao, "_emissor_para", lambda db, eid: FakeEmissor())
    # seed: loja2 com emitente self + rede com emitente central + PerfilEmissao(produto->central)
    ... (criar Emitente central, PerfilEmissao rede produto->central, loja2.emitente_id=self)
    st, b = _post(c, f"/api/projetos/{proj}/ciclo/15/emitir-nfe", {"fabrica_doc_id": doc, "markup_pct": 30})
    assert st == 200
    reg = <DocumentoFiscal do ref>
    assert reg.emitente_id == <id da central> and reg.tipo_documento == "produto"
```

- [ ] **Step 2: `mapa_fiscal.montar_nota(emitente, cliente, itens, ref, data, natureza=…)`** — trocar a fonte do bloco `emitente` para o objeto `Emitente` (cnpj, razao_social, regime, ie, endereço próprios); destinatário segue do `cliente`. Remover o parâmetro `loja`/`perfil` antigos. Ajustar `montar_nota` e o `fiscal` (csosn/cfop do emitente).

- [ ] **Step 3: `nfe_emissao`** — `_emissor_para(db, emitente_id)` usa `focus_client_para_emitente`; `emitir(db, venda_ref, nota, tipo_documento="produto", emitente_id=…, permitir_producao=False, emissor=None, fabrica_doc_id=None)` grava `DocumentoFiscal(tipo_documento, emitente_id, loja_id?)`; guarda de produção lê `Emitente.ambiente_ativo`; homolog dest-name mantém. `consultar`/`cancelar` resolvem emissor por `reg.emitente_id`.

- [ ] **Step 4: `main.py` endpoint `…/ciclo/15/emitir-nfe`** — após obter a `loja` do escopo: `emitente = mod_fiscal.resolver_emitente(db, loja, "produto")` (400 claro em `ValueError`); `nota = mapa_fiscal.montar_nota(emitente, cliente, preview["itens"], ref, data)`; `nfe_emissao.emitir(db, nome_safe, nota, tipo_documento="produto", emitente_id=emitente.id, fabrica_doc_id=doc.id)`. `consultar`/`cancelar` inalterados no gate; usam `reg.emitente_id`. GET estado inclui `emitente` (cnpj/razão) por documento.

- [ ] **Step 5:** adaptar `test_nfe_emissao*.py`, `test_nfe_emitir_teste_e2e.py`, `test_perfil_fiscal_*` e `conftest` (o seed cria `Emitente` + `loja.emitente_id`). Rodar `pytest -q` → verde. **Commit:**
```
git add mapa_fiscal.py nfe_emissao.py main.py tests/
git commit -m "feat(fiscal): emissao de produto resolve o Emitente por documento (multi-CNPJ) + testes"
```

---

## Task 5: Painel etapa 15 mostra o emitente

**Files:** Modify `static/index.html`.

- [ ] **Step 1:** no `_renderCardEmissaoNfe`/estado, exibir por documento o **emitente** (cnpj/razão) ao lado do status — deixando explícito quando o emitente ≠ loja vendedora. Consumir o campo `emitente` que o `GET …/ciclo/15/nfe` passou a devolver (Task 4 Step 4).
- [ ] **Step 2:** checagem estrutural do `<script>` (balanceamento) + `pytest -q` verde (frontend não afeta backend). **Commit:**
```
git add static/index.html
git commit -m "feat(nfe): painel etapa 15 mostra o emitente de cada documento"
```

---

## Task 6: Limpeza + documentação

**Files:** Modify `database.py` (opcional: descontinuar `perfil_fiscal`), `DEV_LOG.md`, spec, `docs/historias/BACKLOG.md`.

- [ ] **Step 1:** confirmar que nada consome mais `PerfilFiscal` (`grep -rn "PerfilFiscal" *.py`). Se limpo, **descontinuar** o modelo `PerfilFiscal` (remover a classe; a tabela `perfil_fiscal` pode permanecer no banco como legado — não dropar dados sem necessidade) — OU manter a classe como alias fino se algum ponto ainda referenciar. Rodar `pytest -q`.
- [ ] **Step 2:** spec → Status **IMPLEMENTADO**; `DEV_LOG` nova `## Sessão N` (Emitente/Plano de Faturamento multi-CNPJ; contratos de API trocados; migração preservou o token do smoke); `BACKLOG` — novo épico **EP-11** (multi-CNPJ) marcando US-32 (NFS-e) como dependente desta base.
- [ ] **Step 3: Commit** + **re-ingerir MCP** após o merge.
```
git add DEV_LOG.md docs/superpowers/specs/2026-07-06-fiscal-plano-faturamento-multicnpj-design.md docs/historias/BACKLOG.md database.py
git commit -m "docs(fiscal): multi-CNPJ como implementado (DEV_LOG + spec + backlog EP-11) + limpeza PerfilFiscal"
```

---

## Self-review do plano
- **Cobertura do spec:** §3.1 Emitente (T1) · §3.2 vínculos (T1) · §3.3 PerfilEmissao (T2) · §3.4 documento_fiscal (T3) · §4 resolução (T2) · §5 re-plataforma (T4) · §6 migração (T1/T3) · §7 testes (por tarefa) · §8 fora de escopo respeitado (NFS-e slot; sem UI de config; sem Estoque/Financeiro).
- **Sem placeholders:** cada passo tem código/rotina concreta; os pontos "confirme nome de coluna" são verificações explícitas, não lacunas.
- **Consistência:** `Emitente`, `PerfilEmissao`, `DocumentoFiscal`, `resolver_emitente`, `focus_client_para_emitente`, `montar_nota(emitente,…)`, `emitir(…, tipo_documento, emitente_id)` usados de forma idêntica entre tarefas. Verde a cada tarefa (aditivo → generaliza → troca → limpa).
