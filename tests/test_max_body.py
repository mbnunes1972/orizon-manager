"""ORIZON_MAX_BODY_MB: teto do body no ponto único de leitura (_ler_body), spec
docs/superpowers/specs/_geral/2026-07-21-uploads-grandes-limite-body-design.md.

Acima do teto → 413 JSON amigável SEM ler o corpo — os testes de socket cru enviam SÓ os
headers (Content-Length alto, zero bytes de body): se o servidor tentasse drenar o corpo
ficaria pendurado até o timeout, então a resposta imediata prova o não-read. Abaixo do
teto a rota segue intocada. Env inválido dá erro claro no padrão de porta_do_ambiente."""
import json
import socket
import pytest


# ── unidade: max_body_bytes (mesmo padrão de porta_do_ambiente) ──────────────

def test_teto_default_sem_env(servidor):
    import main
    assert main.max_body_bytes({}) == 50 * 1024 * 1024


def test_teto_env_vazio(servidor):
    import main
    assert main.max_body_bytes({"ORIZON_MAX_BODY_MB": ""}) == 50 * 1024 * 1024


def test_teto_le_valor_valido(servidor):
    import main
    assert main.max_body_bytes({"ORIZON_MAX_BODY_MB": "2"}) == 2 * 1024 * 1024


def test_teto_nao_numerico_erro_claro(servidor):
    import main
    with pytest.raises(ValueError):
        main.max_body_bytes({"ORIZON_MAX_BODY_MB": "abc"})


def test_teto_zero_erro(servidor):
    import main
    with pytest.raises(ValueError):
        main.max_body_bytes({"ORIZON_MAX_BODY_MB": "0"})


# ── E2E: 413 sem ler o corpo (socket cru, só headers) ────────────────────────

def _requisicao_so_headers(base, metodo, path, content_length, timeout=5):
    """Envia a linha de request + headers com Content-Length alto e NENHUM byte de
    corpo; devolve (status, dict_do_json). Lê até o servidor fechar (Connection: close)."""
    host, port = base.replace("http://", "").split(":")
    s = socket.create_connection((host, int(port)), timeout=timeout)
    try:
        req = ("%s %s HTTP/1.1\r\nHost: %s\r\nContent-Type: application/json\r\n"
               "Content-Length: %d\r\n\r\n" % (metodo, path, host, content_length))
        s.sendall(req.encode())
        raw = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            raw += chunk
    finally:
        s.close()
    status = int(raw.split(b" ", 2)[1])
    corpo = raw.split(b"\r\n\r\n", 1)[1]
    return status, json.loads(corpo)


def test_post_acima_do_teto_default_413_sem_ler(servidor):
    status, d = _requisicao_so_headers(servidor, "POST", "/api/auth/login",
                                       51 * 1024 * 1024)
    assert status == 413
    assert d["ok"] is False
    assert "50 MB" in d["erro"]


def test_put_acima_do_teto_413(servidor):
    status, d = _requisicao_so_headers(servidor, "PUT", "/api/financeiro/contas/1",
                                       51 * 1024 * 1024)
    assert status == 413
    assert d["ok"] is False


def test_patch_acima_do_teto_413(servidor):
    status, d = _requisicao_so_headers(servidor, "PATCH", "/api/adiantamentos/1",
                                       51 * 1024 * 1024)
    assert status == 413
    assert d["ok"] is False


def test_env_override_respeitado_e_mensagem_dinamica(servidor, monkeypatch):
    monkeypatch.setenv("ORIZON_MAX_BODY_MB", "1")
    status, d = _requisicao_so_headers(servidor, "POST", "/api/auth/login",
                                       2 * 1024 * 1024)
    assert status == 413
    assert "1 MB" in d["erro"]


# ── E2E: abaixo do teto a rota segue intocada ────────────────────────────────

def test_post_abaixo_do_teto_rota_intocada(servidor, http_client_factory):
    # 2 MB de payload (< 50 MB) tem que ATRAVESSAR o teto e chegar na rota de
    # login, que responde 401 de credencial — não 413.
    c = http_client_factory()
    status, d = c.post("/api/auth/login",
                       {"login": "nao-existe", "senha": "x", "pad": "A" * (2 * 1024 * 1024)})
    assert status == 401
    assert d["ok"] is False


def test_post_pequeno_sob_override_passa(servidor, http_client_factory, monkeypatch):
    monkeypatch.setenv("ORIZON_MAX_BODY_MB", "1")
    c = http_client_factory()
    status, d = c.post("/api/auth/login", {"login": "nao-existe", "senha": "x"})
    assert status == 401
