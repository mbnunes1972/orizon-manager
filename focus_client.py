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
