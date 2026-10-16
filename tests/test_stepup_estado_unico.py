# tests/test_stepup_estado_unico.py
# Cadeado de módulo (16/10/2026, achado na verificação do manual): em produção o servidor sobe
# com `python3 main.py`, então o módulo roda como `__main__`. auth/auth_routes.py fazia
# `import main as _main` — isso carrega uma SEGUNDA cópia de main.py, com outro `_STEPUP_GRANTS`.
# A liberação (POST /api/auth/step-up) gravava numa cópia e o gate (_sem_acesso_modulo) lia a
# outra: o servidor respondia ok e o módulo seguia 403. Os testes de step-up não pegavam porque
# aqui main.py é importado como `main` (uma cópia só). O estado agora mora em auth/stepup.py.
import http.cookiejar
import json
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent


def test_auth_routes_nao_importa_main():
    """Qualquer `import main` dentro do pacote auth recria a 2ª cópia quando main roda como script."""
    src = (RAIZ / "auth" / "auth_routes.py").read_text(encoding="utf-8")
    assert "import main" not in src


def test_main_e_auth_compartilham_o_mesmo_estado(app_db):
    import main
    from auth import stepup
    assert main._STEPUP_GRANTS is stepup.GRANTS
    stepup.GRANTS.clear()
    stepup.conceder("tok-x", "financeiro")
    assert main._stepup_valido("tok-x", "financeiro")
    stepup.revogar_todos("tok-x")
    assert not main._stepup_valido("tok-x", "financeiro")


def test_stepup_libera_financeiro(http_client_factory, seed):
    c = http_client_factory()
    c.login("cons_l1", "senha123")
    st, body = c.get("/api/financeiro/dashboard")
    assert st == 403 and body.get("precisa_stepup") == "financeiro", body
    st, body = c.post("/api/auth/step-up", {"recurso": "financeiro",
                                            "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
    assert st == 200 and body["ok"], body
    st, body = c.get("/api/financeiro/dashboard")
    assert st == 200 and body["ok"], (st, body)


def _porta_livre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_stepup_com_servidor_subido_como_script(app_db, seed):
    """O cenário real: `python main.py` (main = __main__), como nos 3 ambientes."""
    porta = _porta_livre()
    env = dict(os.environ, DATABASE_URL=str(app_db.ENGINE.url.render_as_string(hide_password=False)),
               ORIZON_HOST="127.0.0.1", ORIZON_PORT=str(porta), PYTHONIOENCODING="utf-8")
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=str(RAIZ), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % porta
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def req(path, dados=None):
        r = urllib.request.Request(base + path, data=None if dados is None else json.dumps(dados).encode(),
                                   headers={"Content-Type": "application/json"})
        try:
            with op.open(r, timeout=20) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for _ in range(120):
            try:
                socket.create_connection(("127.0.0.1", porta), timeout=1).close(); break
            except OSError:
                assert proc.poll() is None, "main.py encerrou na subida"
                time.sleep(0.5)
        st, body = req("/api/auth/login", {"login": "cons_l1", "senha": "senha123"})
        assert st == 200 and body["ok"], body
        st, body = req("/api/financeiro/dashboard")
        assert st == 403 and body.get("precisa_stepup") == "financeiro", body
        st, body = req("/api/auth/step-up", {"recurso": "financeiro",
                                             "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
        assert st == 200 and body["ok"], body
        st, body = req("/api/financeiro/dashboard")
        assert st == 200 and body["ok"], (st, body)
    finally:
        proc.terminate(); proc.wait(timeout=20)
