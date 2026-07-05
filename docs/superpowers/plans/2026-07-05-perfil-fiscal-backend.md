# Painel de Configuração Fiscal · Sub-frente I (backend) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fundação backend do `PerfilFiscal` por loja — modelo de dados, criptografia em repouso dos segredos (tokens Focus), lógica pura (perfil-padrão de teste, validação, guarda de produção), endpoints CRUD gated, e a fiação `focus_client_para_loja`.

**Architecture:** Quatro unidades isoladas: `fiscal_cripto.py` (Fernet, chave fora do banco), `mod_fiscal.py` (lógica pura + wiring), o modelo `PerfilFiscal` em `database.py` (tabela dedicada 1:1 com Loja), e endpoints em `main.py` espelhando o padrão de `config-financeira`. Sem UI (Sub-frente II).

**Tech Stack:** Python 3 + SQLAlchemy/SQLite, `cryptography.Fernet` (já instalada, 48.0.0), `requests` (via focus_client da Fase 2), pytest.

**Base para ler antes:** spec `docs/superpowers/specs/2026-07-05-perfil-fiscal-backend-design.md`. Padrão de endpoint admin-loja a espelhar: `main.py:3998-4023` (`PUT …/config-financeira` — auth, `perfis.pode(nivel,"editar_dados_loja")`, `_ator_dict`, `db.get(Loja, id)`, `mod_tenancy.pode_editar_dados_loja(ator, {"id","rede_id"})`, commit). Modelos: `database.py` (Loja em ~183-218; padrão de teste de modelo com engine temp em `tests/test_ciclo.py:200`). Fixtures e2e: `tests/conftest.py` (`http_client_factory` com `.get/.put`; `seed` tem `loja1_id`,`loja2_id`,`dir_l2` (diretor loja2, tem `editar_dados_loja`), `cons_l1` (consultor loja1, sem a cap); `app_db` module-scoped expõe `get_session()` e os modelos).

**Lembrete de ambiente:** modelos/endpoints Python → **restart do servidor** para verificação manual; a suíte e2e sobe o próprio servidor. Baseline atual **470 passed**. Se `python3` do Bash for o stub WindowsApps, usar o interpretador real (nota no DEV_LOG).

---

## File Structure

- **Create** `fiscal_cripto.py` — Fernet isolado: `gerar_chave`, `encrypt`, `decrypt`, `token_definido`; chave via `ORIZON_FISCAL_KEY`→keyfile.
- **Create** `mod_fiscal.py` — `REGIMES/PAPEIS/AMBIENTES`, `perfil_padrao_teste`, `validar_config`, `pode_ativar_producao`, `focus_client_para_loja`.
- **Modify** `database.py` — modelo `PerfilFiscal` (tabela nova, auto-criada por `create_all`).
- **Modify** `main.py` — GET + 3 PUT endpoints (`/perfil-fiscal`, `/segredos`, `/ambiente`).
- **Create** `tests/test_fiscal_cripto.py`, `tests/test_mod_fiscal.py`, `tests/test_perfil_fiscal_model.py`, `tests/test_perfil_fiscal_e2e.py`.

---

## Task 1: `fiscal_cripto.py` — criptografia isolada

**Files:**
- Create: `fiscal_cripto.py`
- Test: `tests/test_fiscal_cripto.py`
- Modify: `.git/info/exclude` (ignore local de `config/fiscal.key`)

- [ ] **Step 1: Create the tests**

Criar `tests/test_fiscal_cripto.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from cryptography.fernet import Fernet
import fiscal_cripto as fcr


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setenv("ORIZON_FISCAL_KEY", Fernet.generate_key().decode())


def test_roundtrip():
    enc = fcr.encrypt("segredo-123")
    assert enc and enc != "segredo-123"
    assert fcr.decrypt(enc) == "segredo-123"


def test_ciphertext_muda_entre_chamadas():
    a = fcr.encrypt("igual")
    b = fcr.encrypt("igual")
    assert a != b                      # Fernet inclui IV/timestamp
    assert fcr.decrypt(a) == fcr.decrypt(b) == "igual"


def test_vazio_none():
    assert fcr.encrypt("") is None and fcr.encrypt(None) is None
    assert fcr.decrypt("") is None and fcr.decrypt(None) is None


def test_token_adulterado_levanta():
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        fcr.decrypt("nao-e-um-token-fernet-valido")


def test_token_definido():
    assert fcr.token_definido("x") is True
    assert fcr.token_definido(None) is False and fcr.token_definido("") is False


def test_gerar_chave_valida():
    k = fcr.gerar_chave()
    assert isinstance(k, str) and Fernet(k.encode())   # não levanta
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_fiscal_cripto.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'fiscal_cripto'`).

- [ ] **Step 3: Create `fiscal_cripto.py`**

```python
"""fiscal_cripto.py — criptografia em repouso dos segredos fiscais (tokens Focus).
Isolado e trocável: a chave vive FORA do banco (env ORIZON_FISCAL_KEY ou keyfile).
Migrar para KMS depois não deve tocar chamadores. NUNCA loga texto plano nem a chave."""
import os
import logging
from cryptography.fernet import Fernet

try:
    from storage import _BASE_DIR
except ImportError:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_KEYFILE = os.path.join(_BASE_DIR, "config", "fiscal.key")


def gerar_chave() -> str:
    """Chave Fernet nova (base64 urlsafe). Utilitário de setup."""
    return Fernet.generate_key().decode()


def _key_bytes():
    env = os.environ.get("ORIZON_FISCAL_KEY")
    if env:
        return env.encode()
    if os.path.exists(_KEYFILE):
        with open(_KEYFILE, "rb") as f:
            return f.read().strip()
    chave = Fernet.generate_key()
    os.makedirs(os.path.dirname(_KEYFILE), exist_ok=True)
    with open(_KEYFILE, "wb") as f:
        f.write(chave)
    try:
        os.chmod(_KEYFILE, 0o600)
    except OSError:
        pass
    logging.getLogger(__name__).warning("chave fiscal gerada em %s", _KEYFILE)
    return chave


def _fernet():
    # Sem cache: lê a chave a cada chamada (barato) → sempre respeita o env atual (testes limpos).
    return Fernet(_key_bytes())


def encrypt(texto):
    """texto plano -> ciphertext (str). '' / None -> None."""
    if not texto:
        return None
    return _fernet().encrypt(texto.encode()).decode()


def decrypt(token):
    """ciphertext -> texto plano. None/'' -> None. Token adulterado levanta InvalidToken."""
    if not token:
        return None
    return _fernet().decrypt(token.encode()).decode()


def token_definido(enc) -> bool:
    return bool(enc)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_fiscal_cripto.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Ignore local do keyfile**

```bash
grep -qxF 'config/fiscal.key' .git/info/exclude || echo 'config/fiscal.key' >> .git/info/exclude
```

- [ ] **Step 6: Commit**

```bash
git add fiscal_cripto.py tests/test_fiscal_cripto.py
git commit -m "feat(fiscal): fiscal_cripto (Fernet isolado, chave fora do banco)"
```

---

## Task 2: `mod_fiscal.py` — lógica pura (default/validação/guarda)

**Files:**
- Create: `mod_fiscal.py`
- Test: `tests/test_mod_fiscal.py`

- [ ] **Step 1: Create the tests**

Criar `tests/test_mod_fiscal.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_fiscal as mf


def test_perfil_padrao_teste():
    p = mf.perfil_padrao_teste()
    assert p["regime_tributario"] == "simples" and p["csosn_padrao"] == "101"
    assert p["cfop_dentro_uf"] == "5102" and p["cfop_fora_uf"] == "6102"
    assert p["aliquota_iss"] == 5.0 and p["papel_cnpj"] == "loja_produto_servico"
    # campos de teste sinalizados como placeholder
    for chave in ("regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss"):
        assert chave in p["placeholders"]


def test_validar_config_ok():
    ok, erro = mf.validar_config({"regime_tributario": "simples", "papel_cnpj": "avulso",
                                  "aliquota_iss": 5})
    assert ok is True and erro == ""


def test_validar_config_regime_invalido():
    ok, erro = mf.validar_config({"regime_tributario": "lucro_marciano"})
    assert ok is False and "regime" in erro


def test_validar_config_papel_invalido():
    ok, erro = mf.validar_config({"papel_cnpj": "imperador"})
    assert ok is False and "papel" in erro


def test_validar_config_iss_fora_faixa():
    ok, erro = mf.validar_config({"aliquota_iss": 150})
    assert ok is False and "iss" in erro.lower()
    ok2, _ = mf.validar_config({"aliquota_iss": "abc"})
    assert ok2 is False


def test_pode_ativar_producao():
    assert mf.pode_ativar_producao([]) is True
    assert mf.pode_ativar_producao(["regime_tributario"]) is False
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_mod_fiscal.py -q`
Expected: FAIL (`No module named 'mod_fiscal'`).

- [ ] **Step 3: Create `mod_fiscal.py`**

```python
"""mod_fiscal.py — lógica fiscal pura (perfil-padrão de teste, validação, guarda de produção)
e a fiação com o emissor (focus_client_para_loja). Config real vem do PerfilFiscal (banco)."""

REGIMES = {"simples", "simples_excesso", "normal", "mei"}
PAPEIS = {"central_produto", "loja_servico", "loja_produto_servico", "avulso"}
AMBIENTES = {"homologacao", "producao"}

_CNAE_PLACEHOLDER = "4330404"   # instalação/montagem de móveis (genérico — NÃO confirmado)
_CAMPOS_PADRAO = ["regime_tributario", "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf",
                  "cnae_servico", "aliquota_iss", "papel_cnpj"]


def perfil_padrao_teste():
    """Valores de teste p/ desbloquear (Simples, CFOP 5102/6102, CNAE placeholder, ISS 5%).
    `placeholders` lista os campos defaultados (dirige os badges da UI na Sub-frente II)."""
    return {
        "razao_social": None, "inscricao_estadual": None, "inscricao_municipal": None,
        "regime_tributario": "simples", "csosn_padrao": "101",
        "cfop_dentro_uf": "5102", "cfop_fora_uf": "6102",
        "serie_nfe": None, "discrimina_impostos": 1,
        "cnae_servico": _CNAE_PLACEHOLDER, "cod_servico_municipio": None,
        "aliquota_iss": 5.0, "retencao_json": None, "municipio_ibge": None,
        "papel_cnpj": "loja_produto_servico",
        "placeholders": list(_CAMPOS_PADRAO),
    }


def validar_config(req):
    """(ok, erro) para os campos não-secretos do PUT de config."""
    reg = req.get("regime_tributario")
    if reg is not None and reg not in REGIMES:
        return (False, "regime_tributario inválido")
    papel = req.get("papel_cnpj")
    if papel is not None and papel not in PAPEIS:
        return (False, "papel_cnpj inválido")
    iss = req.get("aliquota_iss")
    if iss is not None:
        try:
            v = float(iss)
        except (TypeError, ValueError):
            return (False, "aliquota_iss inválida")
        if not (0 <= v <= 100):
            return (False, "aliquota_iss fora da faixa (0-100)")
    return (True, "")


def pode_ativar_producao(placeholders):
    """False se restar qualquer placeholder — bloqueia produção com dado de teste."""
    return not placeholders


def focus_client_para_loja(db, loja_id):
    """Monta um FocusClient a partir do PerfilFiscal da loja: token do ambiente_ativo, decriptado,
    e base_url do ambiente. ValueError se não há perfil ou token para o ambiente."""
    import fiscal_cripto
    import focus_config
    from focus_client import FocusClient
    from database import PerfilFiscal
    pf = db.query(PerfilFiscal).filter_by(loja_id=loja_id).first()
    if not pf:
        raise ValueError("Loja %s sem PerfilFiscal configurado" % (loja_id,))
    amb = pf.ambiente_ativo or "homologacao"
    enc = pf.focus_token_homolog_enc if amb == "homologacao" else pf.focus_token_prod_enc
    if not enc:
        raise ValueError("Loja %s sem token Focus para o ambiente %s" % (loja_id, amb))
    return FocusClient(token=fiscal_cripto.decrypt(enc), base_url=focus_config.base_url_de(amb))
```

Note: `focus_client_para_loja` é testada na Task 5 (precisa do modelo `PerfilFiscal` da Task 3). Aqui só as 3 funções puras são exercitadas.

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_mod_fiscal.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add mod_fiscal.py tests/test_mod_fiscal.py
git commit -m "feat(fiscal): mod_fiscal (perfil-padrao de teste, validacao, guarda de producao)"
```

---

## Task 3: modelo `PerfilFiscal` em `database.py`

**Files:**
- Modify: `database.py`
- Test: `tests/test_perfil_fiscal_model.py`

- [ ] **Step 1: Write the failing test**

Criar `tests/test_perfil_fiscal_model.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_modelo_perfil_fiscal(tmp_path, monkeypatch):
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
    pf = database.PerfilFiscal(
        loja_id=1, regime_tributario="simples", csosn_padrao="101",
        cfop_dentro_uf="5102", ambiente_ativo="homologacao",
        focus_token_homolog_enc="ciphertext-xyz", placeholders_json='["regime_tributario"]')
    s.add(pf); s.commit()
    lido = s.query(database.PerfilFiscal).filter_by(loja_id=1).first()
    assert lido.regime_tributario == "simples" and lido.ambiente_ativo == "homologacao"
    assert lido.focus_token_homolog_enc == "ciphertext-xyz"
    # unicidade de loja_id (1:1)
    from sqlalchemy.exc import IntegrityError
    s.add(database.PerfilFiscal(loja_id=1))
    import pytest
    with pytest.raises(IntegrityError):
        s.commit()
    s.rollback(); s.close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_perfil_fiscal_model.py -q`
Expected: FAIL (`AttributeError: module 'database' has no attribute 'PerfilFiscal'`).

- [ ] **Step 3: Add the model to `database.py`**

Inserir a classe (após um modelo existente, ex.: depois de `CicloRevisao`). `Column, Integer, Text, Float, DateTime, ForeignKey, UniqueConstraint, datetime` já estão importados no arquivo.

```python
class PerfilFiscal(Base):
    """Perfil fiscal por CNPJ/loja (1:1 com Loja). Complementa Loja.cnpj/endereço.
    Segredos (tokens Focus) ficam CIFRADOS (fiscal_cripto); o certificado A1 NÃO fica aqui
    (vive no painel da Focus) — só validade + CNPJ de referência."""
    __tablename__ = "perfil_fiscal"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    loja_id = Column(Integer, ForeignKey("lojas.id"), nullable=False, unique=True)

    razao_social        = Column(Text, nullable=True)
    inscricao_estadual  = Column(Text, nullable=True)
    inscricao_municipal = Column(Text, nullable=True)

    regime_tributario   = Column(Text, nullable=True)   # simples|simples_excesso|normal|mei
    csosn_padrao        = Column(Text, nullable=True)

    cfop_dentro_uf      = Column(Text, nullable=True)
    cfop_fora_uf        = Column(Text, nullable=True)
    serie_nfe           = Column(Text, nullable=True)
    discrimina_impostos = Column(Integer, default=1)

    cnae_servico          = Column(Text,  nullable=True)
    cod_servico_municipio = Column(Text,  nullable=True)
    aliquota_iss          = Column(Float, nullable=True)
    retencao_json         = Column(Text,  nullable=True)
    municipio_ibge        = Column(Text,  nullable=True)

    cert_validade = Column(DateTime, nullable=True)
    cert_cnpj     = Column(Text,     nullable=True)

    papel_cnpj    = Column(Text, nullable=True)   # central_produto|loja_servico|loja_produto_servico|avulso

    focus_token_homolog_enc = Column(Text, nullable=True)
    focus_token_prod_enc    = Column(Text, nullable=True)
    ambiente_ativo          = Column(Text, default="homologacao")

    placeholders_json = Column(Text, nullable=True)

    criado_em     = Column(DateTime, default=datetime.utcnow)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_perfil_fiscal_model.py -q`
Expected: PASS (1 teste). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_perfil_fiscal_model.py
git commit -m "feat(fiscal): modelo PerfilFiscal (tabela 1:1 com Loja)"
```

---

## Task 4: endpoints GET/PUT em `main.py`

**Files:**
- Modify: `main.py` (import de `PerfilFiscal`; GET em `do_GET`; 3 PUT em `do_PUT` após o bloco `config-financeira` ~linha 4023)
- Test: `tests/test_perfil_fiscal_e2e.py`

- [ ] **Step 1: Create the e2e tests**

Criar `tests/test_perfil_fiscal_e2e.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import json as _json
from cryptography.fernet import Fernet
# chave fiscal fixa para toda a sessão deste módulo (server thread + checagens diretas no mesmo processo)
os.environ["ORIZON_FISCAL_KEY"] = Fernet.generate_key().decode()


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _reset_perfil(app_db, loja_id):
    db = app_db.get_session()
    db.query(app_db.PerfilFiscal).filter_by(loja_id=loja_id).delete()
    db.commit(); db.close()


def test_get_perfil_inexistente_devolve_padrao(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 200 and b["existe"] is False, b
    assert b["perfil"]["regime_tributario"] == "simples" and b["perfil"]["cfop_dentro_uf"] == "5102"
    assert "regime_tributario" in b["placeholders"]
    assert b["token_homolog_definido"] is False and b["token_prod_definido"] is False


def test_put_config_persiste(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal",
                  {"razao_social": "LOJA X LTDA", "regime_tributario": "simples", "placeholders": []})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["existe"] is True and b["perfil"]["razao_social"] == "LOJA X LTDA"
    assert b["placeholders"] == []


def test_put_config_valida(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"regime_tributario": "invalido"})
    assert st == 400 and "regime" in b["erro"]


def test_put_segredos_cifra_e_nao_ecoa(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    st, _ = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/segredos", {"focus_token_homolog": "TOKEN-SECRETO"})
    assert st == 200
    st2, b = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert b["token_homolog_definido"] is True
    assert "TOKEN-SECRETO" not in _json.dumps(b)          # nunca ecoado
    db = app_db.get_session()
    pf = db.query(app_db.PerfilFiscal).filter_by(loja_id=lid).first()
    assert pf.focus_token_homolog_enc and pf.focus_token_homolog_enc != "TOKEN-SECRETO"  # cifrado
    db.close()


def test_ambiente_producao_bloqueado_com_placeholder(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": ["regime_tributario"]})
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st == 400 and "produção" in b["erro"].lower()
    c.put(f"/api/admin/lojas/{lid}/perfil-fiscal", {"placeholders": []})
    st2, b2 = c.put(f"/api/admin/lojas/{lid}/perfil-fiscal/ambiente", {"ambiente": "producao"})
    assert st2 == 200 and b2["ambiente_ativo"] == "producao"


def test_perm_consultor_403(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "cons_l1")     # sem editar_dados_loja
    lid = seed["loja1_id"]
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 403


def test_perm_outra_loja_403(http_client_factory, seed, app_db):
    c = _login(http_client_factory, "dir_l2")      # diretor da loja2
    lid = seed["loja1_id"]                          # tentando a loja1
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 403


def test_nao_autenticado_401(http_client_factory, seed, app_db):
    c = http_client_factory()
    lid = seed["loja2_id"]
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-fiscal")
    assert st == 401


def test_focus_client_para_loja(http_client_factory, seed, app_db):
    import mod_fiscal, fiscal_cripto
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    db = app_db.get_session()
    db.add(app_db.PerfilFiscal(loja_id=lid, ambiente_ativo="homologacao",
                               focus_token_homolog_enc=fiscal_cripto.encrypt("TESTE-TOKEN")))
    db.commit(); db.close()
    db2 = app_db.get_session()
    cli = mod_fiscal.focus_client_para_loja(db2, lid)
    assert cli.token == "TESTE-TOKEN"
    assert cli.base_url == "https://homologacao.focusnfe.com.br"
    db2.close()


def test_focus_client_para_loja_sem_token(http_client_factory, seed, app_db):
    import mod_fiscal, pytest
    lid = seed["loja2_id"]
    _reset_perfil(app_db, lid)
    db = app_db.get_session()
    db.add(app_db.PerfilFiscal(loja_id=lid, ambiente_ativo="producao"))  # sem token prod
    db.commit(); db.close()
    db2 = app_db.get_session()
    with pytest.raises(ValueError):
        mod_fiscal.focus_client_para_loja(db2, lid)
    db2.close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_perfil_fiscal_e2e.py -q -k "perfil or segredos or ambiente or perm or autenticado"`
Expected: FAIL (rotas ainda não existem → 404 no lugar dos códigos esperados). (Os testes `focus_client_para_loja` já passam — a função existe da Task 2.)

- [ ] **Step 3: Import do modelo em `main.py`**

Adicionar `PerfilFiscal` à linha `from database import (... CicloDocumento, CicloRevisao)` (perto de `main.py:17`) → `... CicloDocumento, CicloRevisao, PerfilFiscal)`.

- [ ] **Step 4: GET endpoint em `do_GET`**

Inserir antes do fallback 404 do `do_GET` (usar o alias de regex que os blocos vizinhos do `do_GET` usam — `_re`):

```python
            # GET /api/admin/lojas/<id>/perfil-fiscal — config fiscal (segredos NUNCA retornados)
            m = _re.match(r'^/api/admin/lojas/(\d+)/perfil-fiscal$', path)
            if m:
                usuario = get_usuario_sessao(self)
                if not usuario:
                    self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
                import mod_fiscal, fiscal_cripto
                db = get_session()
                try:
                    ator = _ator_dict(db, usuario)
                    loja = db.get(Loja, int(m.group(1)))
                    if not loja:
                        self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                    if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                        self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                    pf = db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()
                    if not pf:
                        padrao = mod_fiscal.perfil_padrao_teste()
                        placeholders = padrao.pop("placeholders")
                        self.send_json({"ok": True, "existe": False, "perfil": padrao,
                                        "placeholders": placeholders, "ambiente_ativo": "homologacao",
                                        "token_homolog_definido": False, "token_prod_definido": False,
                                        "cert_validade": None, "cert_cnpj": None})
                        return
                    perfil = {c: getattr(pf, c) for c in (
                        "razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
                        "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf", "serie_nfe", "discrimina_impostos",
                        "cnae_servico", "cod_servico_municipio", "aliquota_iss", "retencao_json",
                        "municipio_ibge", "papel_cnpj")}
                    self.send_json({"ok": True, "existe": True, "perfil": perfil,
                                    "placeholders": json.loads(pf.placeholders_json or "[]"),
                                    "ambiente_ativo": pf.ambiente_ativo,
                                    "token_homolog_definido": fiscal_cripto.token_definido(pf.focus_token_homolog_enc),
                                    "token_prod_definido": fiscal_cripto.token_definido(pf.focus_token_prod_enc),
                                    "cert_validade": pf.cert_validade.isoformat() if pf.cert_validade else None,
                                    "cert_cnpj": pf.cert_cnpj})
                finally:
                    db.close()
                return
```

- [ ] **Step 5: Os 3 PUT em `do_PUT`**

Inserir logo após o bloco `PUT …/config-financeira` (~linha 4023, usar `re` como os blocos vizinhos do `do_PUT`). Helper local de get-or-create no topo dos blocos ou repetido — aqui repetido para clareza:

```python
        # ── PUT /api/admin/lojas/<id>/perfil-fiscal — config não-secreta ──────
        m_pf = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal$", path)
        if m_pf:
            import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            ok, erro = mod_fiscal.validar_config(req)
            if not ok:
                self.send_json({"ok": False, "erro": erro}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_pf.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                pf = db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()
                if not pf:
                    pf = PerfilFiscal(loja_id=loja.id); db.add(pf)
                for c in ("razao_social", "inscricao_estadual", "inscricao_municipal", "regime_tributario",
                          "csosn_padrao", "cfop_dentro_uf", "cfop_fora_uf", "serie_nfe", "discrimina_impostos",
                          "cnae_servico", "cod_servico_municipio", "aliquota_iss", "retencao_json",
                          "municipio_ibge", "papel_cnpj"):
                    if c in req:
                        setattr(pf, c, req[c])
                if "placeholders" in req:
                    pf.placeholders_json = json.dumps(req["placeholders"], ensure_ascii=False)
                db.commit()
                self.send_json({"ok": True})
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/segredos — write-only, cifrado ──
        m_seg = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/segredos$", path)
        if m_seg:
            import fiscal_cripto
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_seg.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                pf = db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()
                if not pf:
                    pf = PerfilFiscal(loja_id=loja.id); db.add(pf)
                for campo, col in (("focus_token_homolog", "focus_token_homolog_enc"),
                                   ("focus_token_prod", "focus_token_prod_enc")):
                    if campo in req:
                        v = req[campo]
                        if v is None:
                            setattr(pf, col, None)              # limpar
                        elif v != "":
                            setattr(pf, col, fiscal_cripto.encrypt(v))
                        # v == "" → não altera
                db.commit()
                self.send_json({"ok": True})
            except Exception:
                db.rollback()
                self.send_json({"ok": False, "erro": "Falha ao salvar segredos"}, code=500)
            finally:
                db.close()
            return

        # ── PUT /api/admin/lojas/<id>/perfil-fiscal/ambiente — troca explícita ──
        m_amb = re.match(r"^/api/admin/lojas/(\d+)/perfil-fiscal/ambiente$", path)
        if m_amb:
            import mod_fiscal
            usuario = get_usuario_sessao(self)
            if not usuario:
                self.send_json({"ok": False, "erro": "Não autenticado"}, code=401); return
            try:
                req = json.loads(body) if body else {}
            except Exception:
                self.send_json({"ok": False, "erro": "JSON inválido"}, code=400); return
            amb = req.get("ambiente")
            if amb not in ("homologacao", "producao"):
                self.send_json({"ok": False, "erro": "ambiente inválido"}, code=400); return
            db = get_session()
            try:
                ator = _ator_dict(db, usuario)
                loja = db.get(Loja, int(m_amb.group(1)))
                if not loja:
                    self.send_json({"ok": False, "erro": "Não encontrado"}, code=404); return
                if not mod_tenancy.pode_editar_dados_loja(ator, {"id": loja.id, "rede_id": loja.rede_id}):
                    self.send_json({"ok": False, "erro": "Acesso negado"}, code=403); return
                pf = db.query(PerfilFiscal).filter_by(loja_id=loja.id).first()
                if not pf:
                    pf = PerfilFiscal(loja_id=loja.id); db.add(pf)
                if amb == "producao":
                    placeholders = json.loads(pf.placeholders_json or "[]")
                    if not mod_fiscal.pode_ativar_producao(placeholders):
                        self.send_json({"ok": False,
                                        "erro": "Não é possível ativar produção com valores de teste pendentes: "
                                                + ", ".join(placeholders)}, code=400)
                        return
                pf.ambiente_ativo = amb
                db.commit()
                self.send_json({"ok": True, "ambiente_ativo": amb})
            finally:
                db.close()
            return
```

IMPORTANTE: confirmar o alias de regex de cada método (`do_GET` usa `_re`; `do_PUT` usa `re` — como no bloco `config-financeira`). Verificar que `get_usuario_sessao`, `_ator_dict`, `mod_tenancy`, `Loja`, `get_session`, `json` estão em escopo (estão, pelo padrão de `config-financeira`).

- [ ] **Step 6: Run to verify pass**

Run: `python3 -m pytest tests/test_perfil_fiscal_e2e.py -q`
Expected: PASS (10 testes). Full suite `python3 -m pytest -q` → verde.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_perfil_fiscal_e2e.py
git commit -m "feat(fiscal): endpoints perfil-fiscal (GET + PUT config/segredos/ambiente, gated)"
```

---

## Task 5: verificação da fiação `focus_client_para_loja`

`focus_client_para_loja` foi implementada na Task 2 e já é coberta pelos testes `test_focus_client_para_loja` / `test_focus_client_para_loja_sem_token` do arquivo e2e (Task 4). Esta task só confirma a integração ponta-a-ponta.

- [ ] **Step 1: Rodar os testes de fiação isolados**

Run: `python3 -m pytest tests/test_perfil_fiscal_e2e.py -q -k "focus_client_para_loja"`
Expected: PASS (2 testes) — client montado com token decriptado + base_url de homologação; `ValueError` sem token para o ambiente.

- [ ] **Step 2: Rodar a suíte completa**

Run: `python3 -m pytest -q`
Expected: verde (baseline 470 + os novos).

(Sem commit próprio — a implementação e os testes já foram commitados nas Tasks 2 e 4.)

---

## Task 6: Fechamento — DEV_LOG + status do spec

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/2026-07-05-perfil-fiscal-backend-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar `> Status: **APROVADO (brainstorming)** — a implementar. Parte da integração NF-e...` por
`> Status: **IMPLEMENTADO (Sessão N)** — Sub-frente I (backend) com testes; painel (Sub-frente II) e mapa fiscal pendentes.`

- [ ] **Step 3: DEV_LOG — nova sub-seção na Sessão 47 + ESTADO ATUAL**

Registrar: **PerfilFiscal (Sub-frente I) implementada** — `fiscal_cripto.py` (Fernet, chave fora do banco),
`mod_fiscal.py` (perfil-padrão de teste/validação/guarda de produção/`focus_client_para_loja`), modelo
`PerfilFiscal` (1:1 Loja), endpoints GET/PUT (segredos cifrados write-only, produção bloqueada com
placeholder), gated por `editar_dados_loja`+tenancy; suíte verde. **Cert A1 não fica conosco (Focus).**
Pendências: Sub-frente II (painel), Fase 3b (mapa fiscal + `EmissorFocusNfe`), e os insumos do contador
(valores fiscais reais) + token da Focus. Atualizar `⏸️ ESTADO ATUAL`.

- [ ] **Step 4: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/2026-07-05-perfil-fiscal-backend-design.md
git commit -m "docs(fiscal): DEV_LOG + spec Sub-frente I do Painel Fiscal como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §3 modelo (Task 3), §4 cripto (Task 1), §5 lógica pura (Task 2), §6 endpoints
  (Task 4), §7 fiação (Task 2 impl + Task 4/5 testes), §8 segurança (segredos write-only/cifrados/nunca no
  GET — Task 4; chave fora do banco — Task 1; guarda de produção — Task 2/4), §9 testes distribuídos.
  §10 fora de escopo respeitado (sem UI, sem mapa fiscal, sem EmissorFocusNfe).
- **Consistência de nomes:** colunas do `PerfilFiscal` idênticas entre modelo (Task 3), endpoints (Task 4)
  e testes; `encrypt/decrypt/token_definido/gerar_chave` (Task 1) usados consistentemente; `perfil_padrao_teste`
  retorna `placeholders` que o GET separa via `.pop`; `focus_client_para_loja(db, loja_id)` idêntico em impl
  e testes; `pode_ativar_producao(placeholders)` idem.
- **Segurança verificada nos testes:** `test_put_segredos_cifra_e_nao_ecoa` prova coluna cifrada + token
  fora do GET; `test_ambiente_producao_bloqueado_com_placeholder` prova a guarda.
- **Sem placeholders de plano:** todo passo com código tem o código completo. `Sessão N` = número corrente
  do DEV_LOG na hora.
```
