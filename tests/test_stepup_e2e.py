# tests/test_stepup_e2e.py
# Task 9 — step-up por senha p/ acesso fora do perfil (módulo Folha)


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def test_operador_stepup_folha(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    # operador não tem acesso_financeiro → módulo Folha bloqueado, com sinalização de step-up
    st, body = c.get("/api/folha?competencia=2026-07")
    assert st == 403 and body.get("precisa_stepup") == "folha", body

    st, body = c.post("/api/auth/step-up", {
        "recurso": "folha",
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
    assert st == 200 and body["ok"], body
    assert body["autorizador"]["nome"] == "Diretor L1"

    # grant concedido nesta sessão → não bloqueia mais o mesmo recurso
    st, body = c.get("/api/folha?competencia=2026-07")
    assert st != 403, (st, body)
    assert body["ok"], body


def test_stepup_recusa_autorizador_sem_o_perfil(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/auth/step-up", {
        "recurso": "folha",
        "login_autorizador": "cons_l1", "senha_autorizador": "senha123"})
    assert st == 403, body


def test_stepup_recusa_senha_errada(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/auth/step-up", {
        "recurso": "folha",
        "login_autorizador": "dir_l1", "senha_autorizador": "errada"})
    assert st == 401, body


def test_stepup_grava_log_acesso_delegado(http_client_factory, seed):
    c = _login(http_client_factory, "cons_l1")
    st, body = c.post("/api/auth/step-up", {
        "recurso": "folha",
        "login_autorizador": "dir_l1", "senha_autorizador": "senha123"})
    assert st == 200 and body["ok"], body

    from database import get_session, LogAcessoDelegado
    db = get_session()
    try:
        logs = db.query(LogAcessoDelegado).filter_by(recurso="folha").all()
        assert len(logs) >= 1
        ultimo = logs[-1]
        assert ultimo.solicitante_id is not None and ultimo.autorizador_id is not None
    finally:
        db.close()
