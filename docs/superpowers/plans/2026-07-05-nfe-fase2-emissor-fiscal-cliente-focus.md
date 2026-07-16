# NF-e Fase 2 — Interface `EmissorFiscal` + Cliente HTTP Focus NFe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar o contrato de emissão fiscal (`EmissorFiscal` ABC + DTOs neutros) e o transporte HTTP para a Focus NFe (`FocusClient`), isolados e testáveis sem token (HTTP mockado).

**Architecture:** Três módulos puros na raiz do projeto: `emissor_fiscal.py` (contrato neutro + normalizador), `focus_config.py` (config/base-url), `focus_client.py` (cliente REST com Basic-auth, retry/backoff e `FocusError`). Nenhuma regra fiscal e nenhuma UI (Fases 3/5). Nenhuma chamada de rede real nos testes.

**Tech Stack:** Python 3 (stdlib: `abc`, `dataclasses`, `enum`, `os`, `json`, `time`), `requests` (já usado no `mod_omie`), pytest. Sem dependências novas.

**Base para ler antes:** spec `docs/superpowers/specs/fiscal/2026-07-05-nfe-fase2-emissor-fiscal-cliente-focus-design.md`. Padrão de HTTP+retry a espelhar: `mod_omie.py:26` (`omie_post`). Padrão de config em JSON: `storage.py` (`omie_config.json`, `_BASE_DIR`). `requests` 2.33.1 instalado.

**Lembrete de ambiente:** módulos Python novos **não exigem restart de servidor** para os testes (a suíte é pura). Rodar a suíte: `python3 -m pytest -q` (baseline atual **431 passed**). `python3` do Bash pode ser o stub do WindowsApps — se `pytest` falhar por isso, usar o interpretador real conforme nota no DEV_LOG.

---

## File Structure

- **Create** `emissor_fiscal.py` — `StatusNota` (enum), `ResultadoEmissao` (dataclass), `EmissorFiscal` (ABC), `resultado_de_focus()` (normalizador Focus→DTO). Sem dependência de Focus/rede.
- **Create** `focus_config.py` — `base_url_de(ambiente)`, `get_focus_config()`; caminho `focus_config.json` (gitignored via `.git/info/exclude`).
- **Create** `focus_client.py` — `FocusError`, `FocusClient` (`_request` com retry, `enviar_nfe`, `consultar_nfe`, `cancelar_nfe`, `baixar`, `aguardar_processamento`).
- **Create** `tests/test_emissor_fiscal.py`, `tests/test_focus_client.py`.
- **Modify** `DEV_LOG.md` + spec header (fechamento).

---

## Task 1: `emissor_fiscal.py` — contrato neutro + normalizador

**Files:**
- Create: `emissor_fiscal.py`
- Test: `tests/test_emissor_fiscal.py`

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_emissor_fiscal.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import emissor_fiscal as ef


def test_statusnota_valores():
    assert ef.StatusNota.AUTORIZADO.value == "autorizado"
    assert set(ef.StatusNota) >= {
        ef.StatusNota.PROCESSANDO, ef.StatusNota.AUTORIZADO,
        ef.StatusNota.ERRO, ef.StatusNota.CANCELADO, ef.StatusNota.DESCONHECIDO}


def test_resultado_de_focus_autorizado():
    dados = {"ref": "R1", "status": "autorizado", "chave_nfe": "CH", "numero": "10",
             "serie": "1", "status_sefaz": "100", "mensagem_sefaz": "Autorizado",
             "caminho_xml_nota_fiscal": "/x.xml", "caminho_danfe": "/d.pdf"}
    r = ef.resultado_de_focus(dados)
    assert r.ref == "R1" and r.status == ef.StatusNota.AUTORIZADO
    assert r.chave == "CH" and r.numero == "10" and r.serie == "1"
    assert r.xml_url == "/x.xml" and r.danfe_url == "/d.pdf"
    assert r.raw == dados


def test_resultado_de_focus_processando_erro_cancelado():
    assert ef.resultado_de_focus({"status": "processando_autorizacao"}).status == ef.StatusNota.PROCESSANDO
    r_erro = ef.resultado_de_focus({"status": "erro_autorizacao", "erros": [{"codigo": "1", "mensagem": "x"}]})
    assert r_erro.status == ef.StatusNota.ERRO and r_erro.erros == [{"codigo": "1", "mensagem": "x"}]
    r_can = ef.resultado_de_focus({"status": "cancelado", "caminho_xml_cancelamento": "/c.xml"})
    assert r_can.status == ef.StatusNota.CANCELADO and r_can.xml_cancelamento_url == "/c.xml"


def test_resultado_de_focus_desconhecido():
    assert ef.resultado_de_focus({}).status == ef.StatusNota.DESCONHECIDO
    assert ef.resultado_de_focus({"status": "algo_novo"}).status == ef.StatusNota.DESCONHECIDO


def test_emissor_fiscal_abc_nao_instancia():
    with pytest.raises(TypeError):
        ef.EmissorFiscal()


def test_nfse_stub_levanta_notimplemented():
    class E(ef.EmissorFiscal):
        def emitir_nfe_produto(self, nota): return None
        def consultar_status(self, ref): return None
        def cancelar(self, ref, justificativa): return None
    with pytest.raises(NotImplementedError):
        E().emitir_nfse_servico({})
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_emissor_fiscal.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'emissor_fiscal'`).

- [ ] **Step 3: Implement `emissor_fiscal.py`**

```python
"""emissor_fiscal.py — contrato neutro de emissão fiscal (independe de provedor).
A implementação concreta (Focus NFe) chega na Fase 3."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class StatusNota(str, Enum):
    PROCESSANDO  = "processando"
    AUTORIZADO   = "autorizado"
    ERRO         = "erro"
    CANCELADO    = "cancelado"
    DESCONHECIDO = "desconhecido"


@dataclass
class ResultadoEmissao:
    ref: str | None
    status: StatusNota
    chave: str | None = None
    numero: str | None = None
    serie: str | None = None
    status_sefaz: str | None = None
    mensagem_sefaz: str | None = None
    xml_url: str | None = None
    danfe_url: str | None = None
    xml_cancelamento_url: str | None = None
    erros: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class EmissorFiscal(ABC):
    """Interface de emissão. Uma implementação por provedor (Focus NFe na Fase 3)."""

    @abstractmethod
    def emitir_nfe_produto(self, nota) -> ResultadoEmissao: ...

    @abstractmethod
    def consultar_status(self, ref: str) -> ResultadoEmissao: ...

    @abstractmethod
    def cancelar(self, ref: str, justificativa: str) -> ResultadoEmissao: ...

    def emitir_nfse_servico(self, servico) -> ResultadoEmissao:
        raise NotImplementedError(
            "NFS-e será implementada quando houver 2º CNPJ + município integrado na Focus.")


_MAP_STATUS_FOCUS = {
    "processando_autorizacao": StatusNota.PROCESSANDO,
    "autorizado":              StatusNota.AUTORIZADO,
    "erro_autorizacao":        StatusNota.ERRO,
    "cancelado":               StatusNota.CANCELADO,
}


def resultado_de_focus(dados: dict) -> ResultadoEmissao:
    """Normaliza a resposta JSON da Focus NFe para ResultadoEmissao (DTO neutro)."""
    return ResultadoEmissao(
        ref=dados.get("ref"),
        status=_MAP_STATUS_FOCUS.get(dados.get("status"), StatusNota.DESCONHECIDO),
        chave=dados.get("chave_nfe"),
        numero=dados.get("numero"),
        serie=dados.get("serie"),
        status_sefaz=dados.get("status_sefaz"),
        mensagem_sefaz=dados.get("mensagem_sefaz"),
        xml_url=dados.get("caminho_xml_nota_fiscal"),
        danfe_url=dados.get("caminho_danfe"),
        xml_cancelamento_url=dados.get("caminho_xml_cancelamento"),
        erros=dados.get("erros") or [],
        raw=dados,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_emissor_fiscal.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add emissor_fiscal.py tests/test_emissor_fiscal.py
git commit -m "feat(nfe): contrato EmissorFiscal + DTOs + normalizador Focus (Fase 2)"
```

---

## Task 2: `focus_config.py` — base URL + config gitignored

**Files:**
- Create: `focus_config.py`
- Test: `tests/test_focus_config.py`
- Modify: `.git/info/exclude` (local ignore de `focus_config.json`)

- [ ] **Step 1: Write the failing tests**

Criar `tests/test_focus_config.py`:

```python
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import focus_config as fc


def test_base_url_de():
    assert fc.base_url_de("homologacao") == "https://homologacao.focusnfe.com.br"
    assert fc.base_url_de("producao") == "https://api.focusnfe.com.br"


def test_base_url_de_invalido():
    with pytest.raises(ValueError):
        fc.base_url_de("qualquer")


def test_get_focus_config_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "FOCUS_CONFIG_FILE", str(tmp_path / "nao_existe.json"))
    with pytest.raises(FileNotFoundError):
        fc.get_focus_config()


def test_get_focus_config_le(tmp_path, monkeypatch):
    p = tmp_path / "focus_config.json"
    p.write_text(json.dumps({"ambiente": "homologacao", "token": "T", "cnpj_emitente": "19152134000156"}),
                 encoding="utf-8")
    monkeypatch.setattr(fc, "FOCUS_CONFIG_FILE", str(p))
    cfg = fc.get_focus_config()
    assert cfg["token"] == "T" and cfg["ambiente"] == "homologacao"
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_focus_config.py -q`
Expected: FAIL (`No module named 'focus_config'`).

- [ ] **Step 3: Implement `focus_config.py`**

```python
"""focus_config.py — configuração da Focus NFe (token/ambiente/CNPJ).
Config por loja é Fase 3/5; aqui é o loader central (padrão do omie_config.json)."""
import os
import json

try:
    from storage import _BASE_DIR
except Exception:  # fallback fora do app
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOCUS_CONFIG_FILE = os.path.join(_BASE_DIR, "focus_config.json")

_BASES = {
    "homologacao": "https://homologacao.focusnfe.com.br",
    "producao":    "https://api.focusnfe.com.br",
}


def base_url_de(ambiente: str) -> str:
    try:
        return _BASES[ambiente]
    except KeyError:
        raise ValueError("ambiente inválido: %r (use 'homologacao' ou 'producao')" % (ambiente,))


def get_focus_config() -> dict:
    """Lê focus_config.json → {ambiente, token, cnpj_emitente}. FileNotFoundError se ausente."""
    if not os.path.exists(FOCUS_CONFIG_FILE):
        raise FileNotFoundError(
            "focus_config.json ausente em %s — crie com {ambiente, token, cnpj_emitente}." % FOCUS_CONFIG_FILE)
    with open(FOCUS_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_focus_config.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Ignore local do `focus_config.json`**

```bash
grep -qxF 'focus_config.json' .git/info/exclude || echo 'focus_config.json' >> .git/info/exclude
```

- [ ] **Step 6: Commit**

```bash
git add focus_config.py tests/test_focus_config.py
git commit -m "feat(nfe): focus_config (base URL homolog/prod + loader gitignored)"
```

---

## Task 3: `focus_client.py` — cliente REST (métodos + validação, sem retry ainda)

**Files:**
- Create: `focus_client.py`
- Test: `tests/test_focus_client.py`

- [ ] **Step 1: Write the failing tests (happy paths + validação)**

Criar `tests/test_focus_client.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import requests
import focus_client as fc


class FakeResp:
    def __init__(self, status_code, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json = json_data
        self.text = text
        self.headers = headers or {}
    def json(self):
        if self._json is None:
            raise ValueError("sem json")
        return self._json


def _client():
    return fc.FocusClient(token="Tok", base_url="https://homologacao.focusnfe.com.br", timeout=5)


def _capture(monkeypatch, seq):
    """Substitui requests.request por um fake que consome `seq` (lista de FakeResp
    ou Exception) e grava as chamadas em `chamadas`."""
    chamadas = []
    it = list(seq)
    def fake_request(method, url, params=None, json=None, auth=None, timeout=None):
        chamadas.append({"method": method, "url": url, "params": params, "json": json, "auth": auth})
        r = it.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(fc.requests, "request", fake_request)
    monkeypatch.setattr(fc.time, "sleep", lambda s: None)
    return chamadas


def test_enviar_nfe_monta_request(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(202, {"status": "processando_autorizacao", "ref": "R1"})])
    dados = _client().enviar_nfe("R1", {"cnpj_emitente": "19152134000156", "items": []})
    c = chamadas[0]
    assert c["method"] == "POST" and c["url"].endswith("/v2/nfe")
    assert c["params"] == {"ref": "R1"}
    assert c["json"]["cnpj_emitente"] == "19152134000156"
    assert c["auth"] == ("Tok", "")
    assert dados["status"] == "processando_autorizacao" and dados["_http_status"] == 202


def test_consultar_nfe(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"status": "autorizado"})])
    _client().consultar_nfe("R1", completa=True)
    c = chamadas[0]
    assert c["method"] == "GET" and c["url"].endswith("/v2/nfe/R1")
    assert c["params"] == {"completa": 1}


def test_cancelar_nfe(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(200, {"status": "cancelado"})])
    _client().cancelar_nfe("R1", "Cancelamento por erro de digitacao no pedido")
    c = chamadas[0]
    assert c["method"] == "DELETE" and c["url"].endswith("/v2/nfe/R1")
    assert c["json"] == {"justificativa": "Cancelamento por erro de digitacao no pedido"}


def test_cancelar_justificativa_curta(monkeypatch):
    _capture(monkeypatch, [])  # não deve chegar a requisitar
    with pytest.raises(ValueError):
        _client().cancelar_nfe("R1", "curta")


def test_erro_4xx_vira_focuserror(monkeypatch):
    _capture(monkeypatch, [FakeResp(422, {"mensagem": "cnpj invalido",
                                          "erros": [{"codigo": "cnpj", "mensagem": "invalido"}]})])
    with pytest.raises(fc.FocusError) as e:
        _client().enviar_nfe("R1", {})
    assert e.value.status_code == 422 and "cnpj invalido" in str(e.value)
    assert e.value.erros == [{"codigo": "cnpj", "mensagem": "invalido"}]
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_focus_client.py -q`
Expected: FAIL (`No module named 'focus_client'`).

- [ ] **Step 3: Implement `focus_client.py` (single-attempt; o retry entra na Task 4)**

```python
"""focus_client.py — cliente HTTP da Focus NFe (transporte puro; sem regra fiscal)."""
import time  # noqa: F401  (usado pelo retry/polling nas Tasks 4-5; e pelos testes via fc.time)
import requests


class FocusError(Exception):
    def __init__(self, mensagem, status_code=None, erros=None):
        super().__init__(mensagem)
        self.status_code = status_code
        self.erros = erros or []


class FocusClient:
    def __init__(self, token, base_url, timeout=20, max_tentativas=3):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_tentativas = max_tentativas

    def _request(self, method, path, params=None, json_body=None):
        url = self.base_url + path
        try:
            resp = requests.request(method, url, params=params, json=json_body,
                                    auth=(self.token, ""), timeout=self.timeout)
        except requests.RequestException as e:
            raise FocusError("Falha de conexão com a Focus NFe: %s" % e)
        try:
            dados = resp.json()
        except ValueError:
            dados = {}
        if resp.status_code >= 400:
            msg = (dados.get("mensagem") or dados.get("erro")
                   or (resp.text or "")[:300] or ("HTTP %d" % resp.status_code))
            raise FocusError(msg, status_code=resp.status_code, erros=dados.get("erros"))
        dados["_http_status"] = resp.status_code
        return dados

    def enviar_nfe(self, ref, payload):
        return self._request("POST", "/v2/nfe", params={"ref": ref}, json_body=payload)

    def consultar_nfe(self, ref, completa=False):
        return self._request("GET", "/v2/nfe/%s" % ref, params={"completa": 1 if completa else 0})

    def cancelar_nfe(self, ref, justificativa):
        if not (15 <= len(justificativa or "") <= 255):
            raise ValueError("justificativa deve ter entre 15 e 255 caracteres")
        return self._request("DELETE", "/v2/nfe/%s" % ref, json_body={"justificativa": justificativa})
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_focus_client.py -q`
Expected: PASS (5 testes). (O retry vem na Task 4.)

- [ ] **Step 5: Commit**

```bash
git add focus_client.py tests/test_focus_client.py
git commit -m "feat(nfe): FocusClient (enviar/consultar/cancelar + FocusError, Fase 2)"
```

---

## Task 4: retry/backoff do `FocusClient` (test-first)

**Files:**
- Modify: `focus_client.py` (adiciona o loop de retry ao `_request`)
- Test: `tests/test_focus_client.py` (adicionar)

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_focus_client.py`:

```python
def test_retry_5xx_depois_sucesso(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(500, {"mensagem": "erro interno"}),
                                      FakeResp(200, {"status": "autorizado"})])
    dados = _client().consultar_nfe("R1")
    assert dados["status"] == "autorizado"
    assert len(chamadas) == 2   # 1 falha + 1 sucesso


def test_retry_esgota_5xx(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(500, {"mensagem": "e"})] * 3)
    with pytest.raises(fc.FocusError) as e:
        _client().consultar_nfe("R1")
    assert e.value.status_code == 500
    assert len(chamadas) == 3   # max_tentativas


def test_retry_429_respeita(monkeypatch):
    chamadas = _capture(monkeypatch, [FakeResp(429, {}, headers={"Retry-After": "2"}),
                                      FakeResp(200, {"status": "autorizado"})])
    _client().consultar_nfe("R1")
    assert len(chamadas) == 2


def test_erro_conexao_retry_e_falha(monkeypatch):
    chamadas = _capture(monkeypatch, [requests.ConnectionError("reset"),
                                      requests.ConnectionError("reset"),
                                      requests.ConnectionError("reset")])
    with pytest.raises(fc.FocusError):
        _client().consultar_nfe("R1")
    assert len(chamadas) == 3


def test_erro_conexao_recupera(monkeypatch):
    chamadas = _capture(monkeypatch, [requests.ConnectionError("reset"),
                                      FakeResp(200, {"status": "autorizado"})])
    dados = _client().consultar_nfe("R1")
    assert dados["status"] == "autorizado" and len(chamadas) == 2
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_focus_client.py -q -k "retry or conexao"`
Expected: FAIL — o `_request` single-attempt não repete (ex.: `test_retry_5xx_depois_sucesso` levanta `FocusError` no 1º 500 em vez de repetir; `test_erro_conexao_recupera` falha na 1ª exceção).

- [ ] **Step 3: Add retry to `_request`**

Adicionar a constante de módulo (após os imports) e o método `_backoff`, e **substituir** o corpo do `_request` pela versão com loop:

```python
_STATUS_RETRIAVEIS = {429, 500, 502, 503, 504}
```

```python
    def _backoff(self, tentativa, resp):
        if resp is not None:
            ra = resp.headers.get("Retry-After")
            if ra and str(ra).isdigit():
                return min(int(ra), 30)
        return min(2 ** tentativa, 8)

    def _request(self, method, path, params=None, json_body=None):
        url = self.base_url + path
        for tentativa in range(self.max_tentativas):
            ultima = tentativa == self.max_tentativas - 1
            try:
                resp = requests.request(method, url, params=params, json=json_body,
                                        auth=(self.token, ""), timeout=self.timeout)
            except requests.RequestException as e:
                if ultima:
                    raise FocusError("Falha de conexão com a Focus NFe: %s" % e)
                time.sleep(self._backoff(tentativa, None))
                continue
            if resp.status_code in _STATUS_RETRIAVEIS and not ultima:
                time.sleep(self._backoff(tentativa, resp))
                continue
            try:
                dados = resp.json()
            except ValueError:
                dados = {}
            if resp.status_code >= 400:
                msg = (dados.get("mensagem") or dados.get("erro")
                       or (resp.text or "")[:300] or ("HTTP %d" % resp.status_code))
                raise FocusError(msg, status_code=resp.status_code, erros=dados.get("erros"))
            dados["_http_status"] = resp.status_code
            return dados
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_focus_client.py -q`
Expected: PASS (todos — 5 da Task 3 + 5 novos = 10).

- [ ] **Step 5: Commit**

```bash
git add focus_client.py tests/test_focus_client.py
git commit -m "feat(nfe): retry/backoff do FocusClient (5xx/429/conexao)"
```

---

## Task 5: `baixar` + `aguardar_processamento`

**Files:**
- Modify: `focus_client.py`
- Test: `tests/test_focus_client.py` (adicionar)

- [ ] **Step 1: Write the failing tests**

Adicionar em `tests/test_focus_client.py`:

```python
def test_baixar_conteudo(monkeypatch):
    chamadas = []
    class RespBin(FakeResp):
        content = b"%PDF-bin"
    def fake_get(url, auth=None, timeout=None):
        chamadas.append({"url": url, "auth": auth})
        return RespBin(200)
    monkeypatch.setattr(fc.requests, "get", fake_get)
    data = _client().baixar("/notas/12345.pdf")
    assert data == b"%PDF-bin"
    assert chamadas[0]["url"].endswith("/notas/12345.pdf")
    assert chamadas[0]["auth"] == ("Tok", "")


def test_baixar_erro(monkeypatch):
    class RespBin(FakeResp):
        content = b""
    monkeypatch.setattr(fc.requests, "get", lambda url, auth=None, timeout=None: RespBin(404))
    with pytest.raises(fc.FocusError):
        _client().baixar("/x.pdf")


def test_aguardar_processamento_ate_autorizado(monkeypatch):
    monkeypatch.setattr(fc.time, "sleep", lambda s: None)
    seq = [{"status": "processando_autorizacao"},
           {"status": "processando_autorizacao"},
           {"status": "autorizado"}]
    monkeypatch.setattr(fc.FocusClient, "consultar_nfe", lambda self, ref, completa=False: seq.pop(0))
    dados = _client().aguardar_processamento("R1", timeout=9, intervalo=3)
    assert dados["status"] == "autorizado"


def test_aguardar_processamento_estoura_timeout(monkeypatch):
    monkeypatch.setattr(fc.time, "sleep", lambda s: None)
    monkeypatch.setattr(fc.FocusClient, "consultar_nfe",
                        lambda self, ref, completa=False: {"status": "processando_autorizacao"})
    dados = _client().aguardar_processamento("R1", timeout=6, intervalo=3)
    assert dados["status"] == "processando_autorizacao"   # não trava, retorna o último
```

- [ ] **Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_focus_client.py -q -k "baixar or aguardar"`
Expected: FAIL (`AttributeError: 'FocusClient' object has no attribute 'baixar'`).

- [ ] **Step 3: Implement in `focus_client.py` (adicionar métodos à classe `FocusClient`)**

```python
    def baixar(self, caminho):
        """GET binário de um caminho relativo retornado pela Focus (xml/danfe)."""
        resp = requests.get(self.base_url + caminho, auth=(self.token, ""), timeout=self.timeout)
        if resp.status_code >= 400:
            raise FocusError("Falha ao baixar %s" % caminho, status_code=resp.status_code)
        return resp.content

    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        """Polla consultar_nfe até sair de 'processando_autorizacao' ou esgotar as tentativas
        (bounded por timeout/intervalo — determinístico, sem relógio de parede)."""
        tentativas = max(1, int(timeout / intervalo))
        dados = self.consultar_nfe(ref)
        for _ in range(tentativas - 1):
            if dados.get("status") != "processando_autorizacao":
                break
            time.sleep(intervalo)
            dados = self.consultar_nfe(ref)
        return dados
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_focus_client.py -q`
Expected: PASS (todos — 14).

- [ ] **Step 5: Run full suite**

Run: `python3 -m pytest -q`
Expected: verde (baseline 431 + os novos módulos).

- [ ] **Step 6: Commit**

```bash
git add focus_client.py tests/test_focus_client.py
git commit -m "feat(nfe): FocusClient.baixar + aguardar_processamento (polling)"
```

---

## Task 6: Fechamento — DEV_LOG + status do spec + nota de smoke test

**Files:**
- Modify: `DEV_LOG.md`, `docs/superpowers/specs/fiscal/2026-07-05-nfe-fase2-emissor-fiscal-cliente-focus-design.md`

- [ ] **Step 1: Run full suite (verde antes de documentar)**

Run: `python3 -m pytest -q`
Expected: verde.

- [ ] **Step 2: Spec status → IMPLEMENTADO**

Trocar a linha `> Status: **APROVADO (brainstorming)** — a implementar. Segunda das fases...` por
`> Status: **IMPLEMENTADO (Sessão N)** — contrato + cliente HTTP com testes; smoke em homologação pendente do token da Focus.`

- [ ] **Step 3: DEV_LOG — nova sessão + ESTADO ATUAL**

Adicionar `## Sessão N — NF-e Fase 2 (EmissorFiscal + cliente Focus, branch feat/nfe)` cobrindo: os 3 módulos (`emissor_fiscal.py`/`focus_config.py`/`focus_client.py`), a fronteira (contrato+transporte; concreto na Fase 3), retry espelhando `omie_post`, config gitignored, testes com `requests`/`time.sleep` mockados (nenhuma rede), e a pendência: **smoke test em homologação** quando o token existir + o **perfil fiscal Simples do CNPJ 19.152.134/0001-56** para a Fase 3. Atualizar `⏸️ ESTADO ATUAL`.

- [ ] **Step 4: Nota do smoke test (transporte-only, dentro do DEV_LOG/spec)**

Documentar (no DEV_LOG, na sessão): com `focus_config.json` de homologação preenchido, um teste manual de transporte é `FocusClient(cfg["token"], base_url_de("homologacao")).consultar_nfe("ref-inexistente")` → deve levantar `FocusError` com `status_code` **404** (nota não encontrada) e **não 401** — provando que auth + base URL funcionam sem depender de payload fiscal (que é Fase 3).

- [ ] **Step 5: Commit**

```bash
git add DEV_LOG.md docs/superpowers/specs/fiscal/2026-07-05-nfe-fase2-emissor-fiscal-cliente-focus-design.md
git commit -m "docs(nfe): DEV_LOG sessao N + spec Fase 2 como implementado"
```

---

## Notas de verificação (self-review do plano)

- **Cobertura do spec:** §4.1 contrato+normalizador (Task 1), §4.3 config (Task 2), §4.2 cliente:
  enviar/consultar/cancelar+validação (Task 3), retry/backoff+FocusError (Task 4), baixar+aguardar (Task 5);
  §5 testes distribuídos nas tasks; smoke test documentado (Task 6). §6 fora de escopo respeitado
  (nenhum payload fiscal, nenhum `EmissorFocusNfe`, nenhuma UI).
- **Consistência de tipos/assinaturas:** `ResultadoEmissao`, `StatusNota`, `resultado_de_focus`,
  `FocusError(mensagem, status_code, erros)`, `FocusClient(token, base_url, timeout, max_tentativas)` e
  métodos (`enviar_nfe(ref,payload)`, `consultar_nfe(ref,completa)`, `cancelar_nfe(ref,justificativa)`,
  `baixar(caminho)`, `aguardar_processamento(ref,timeout,intervalo)`) idênticos entre implementação e
  testes. Auth sempre `(token, "")`. Paths sempre `/v2/nfe...`.
- **Sem placeholders:** todo passo com código tem o código completo. `Sessão N` é o único símbolo a
  resolver na hora (número da sessão corrente do DEV_LOG).
```
