"""focus_client.py — cliente HTTP da Focus NFe (transporte puro; sem regra fiscal)."""
import time
import requests

_STATUS_RETRIAVEIS = {429, 500, 502, 503, 504}


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
            if not isinstance(dados, dict):
                dados = {"_raw": dados}
            if resp.status_code >= 400:
                msg = (dados.get("mensagem") or dados.get("erro")
                       or (resp.text or "")[:300] or ("HTTP %d" % resp.status_code))
                raise FocusError(msg, status_code=resp.status_code, erros=dados.get("erros"))
            dados["_http_status"] = resp.status_code
            return dados

    def enviar_nfe(self, ref, payload):
        # `ref` é a chave de idempotência: o retry de POST (em 5xx/429/timeout) é seguro
        # porque a Focus deduplica por `ref` — não desabilitar o retry aqui.
        return self._request("POST", "/v2/nfe", params={"ref": ref}, json_body=payload)

    def consultar_nfe(self, ref, completa=False):
        return self._request("GET", "/v2/nfe/%s" % ref, params={"completa": 1 if completa else 0})

    def cancelar_nfe(self, ref, justificativa):
        if not (15 <= len(justificativa or "") <= 255):
            raise ValueError("justificativa deve ter entre 15 e 255 caracteres")
        return self._request("DELETE", "/v2/nfe/%s" % ref, json_body={"justificativa": justificativa})

    def baixar(self, caminho):
        """GET binário de um caminho relativo retornado pela Focus (xml/danfe)."""
        resp = requests.get(self.base_url + caminho, auth=(self.token, ""), timeout=self.timeout)
        if resp.status_code >= 400:
            raise FocusError("Falha ao baixar %s" % caminho, status_code=resp.status_code)
        return resp.content

    def aguardar_processamento(self, ref, timeout=60, intervalo=3):
        """Polla consultar_nfe até sair de 'processando_autorizacao' ou esgotar as tentativas
        (bounded por timeout/intervalo — determinístico, sem relógio de parede)."""
        intervalo = max(1, intervalo)
        tentativas = max(1, int(timeout / intervalo))
        dados = self.consultar_nfe(ref)
        for _ in range(tentativas - 1):
            if dados.get("status") != "processando_autorizacao":
                break
            time.sleep(intervalo)
            dados = self.consultar_nfe(ref)
        return dados
