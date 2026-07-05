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
