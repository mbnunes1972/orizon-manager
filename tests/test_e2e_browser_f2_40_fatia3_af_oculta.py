# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-40 Fatia 3 (docs/db/ROTEIRO.md): etapas 8 (AF1) e 11d (AF2)
somem POR INTEIRO do fichário — nem sub-aba, nem card, nem aviso restrito — para quem não tem
`pode_aprovar_financeiro` (perfil "operador"). Antes desta fatia, a sub-aba e o card continuavam
visíveis/clicáveis; só o CONTEÚDO virava um aviso "restrito". Prova que a navegação entre etapas
VIZINHAS (7↔9↔11↔...) continua funcionando ponta a ponta para esse perfil, e que forçar
`_fichaSelecionar('8')`/`('11d')` diretamente (bypass do clique) não abre o card mesmo assim —
`_fichaVisivelParaUsuario` redireciona pra mãe."""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.test_e2e_browser_remover_ciclo import (
    _criar_projeto_e_assinar_contrato, _marcar_concluidas,
)

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO


def _sessao_teste():
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        atual = conn.execute(text("SELECT current_database()")).scalar()
    if atual != NOME_BANCO_ESPERADO:
        eng.dispose()
        raise RuntimeError("Recusado: sessão de teste só abre em %r — conectou em %r."
                          % (NOME_BANCO_ESPERADO, atual))
    return sessionmaker(bind=eng)()


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor_e2e():
    porta = _porta_livre()
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "_e2e_bootstrap.py"),
                       TEST_DB_URL], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "bootstrap do banco falhou:\n" + r.stdout + r.stderr

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DB_URL
    env["ORIZON_PORT"] = str(porta)
    env["ORIZON_HOST"] = "127.0.0.1"
    env.pop("ORIZON_WA_TOKEN", None); env.pop("ORIZON_SMTP_PASS", None)
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base_url = "http://127.0.0.1:%d" % porta
    try:
        import urllib.request
        ok = False
        for _ in range(60):
            try:
                urllib.request.urlopen(base_url, timeout=1)
                ok = True
                break
            except Exception:
                if proc.poll() is not None:
                    raise RuntimeError("servidor E2E morreu no boot:\n" + proc.stdout.read())
                time.sleep(0.5)
        assert ok, "servidor E2E não respondeu em 30s"
        yield base_url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def page(page):
    page.set_default_timeout(15000)
    return page


def _criar_operador(loja_id, nome_projeto):
    """Usuário nível 'operador' — auth/perfis.py: aprovar_financeiro=False. Único perfil de loja
    sem essa capacidade (master/gerencial têm True). Escopo por projetista (main.py
    `_ve_apenas_proprios_projetos`): 'operador' só enxerga projetos que CRIOU — sem isto o
    projeto (criado pelo e2e_master) daria 404 pra ele, e o teste não provaria nada sobre 8/11d,
    só sobre escopo de visibilidade (assunto diferente)."""
    import database
    db = _sessao_teste()
    try:
        u = database.Usuario(nome="E2E Operador", login="e2e_operador_f240", nivel="operador",
                             loja_id=loja_id, ativo=1)
        u.set_senha("senha123")
        db.add(u); db.flush()
        uid = u.id
        proj = db.get(database.Projeto, nome_projeto)
        proj.criado_por_id = uid
        db.commit()
        return uid
    finally:
        db.bind.dispose()
        db.close()


def _login(page, base, login, senha):
    page.goto(base + "/static/login.html")
    page.fill("#email", login)
    page.fill("#senha", senha)
    page.click("#loginBtn")
    page.wait_for_url(base + "/")


def test_af1_af2_somem_por_inteiro_e_navegacao_vizinha_continua(page, servidor_e2e):
    base = servidor_e2e
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E F2-40 Fatia3 AF Oculta")
    # etapas anteriores a 11 concluídas (puro "marcar como feito" — objeto do teste é 8/11d)
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d"])

    import database
    db = _sessao_teste()
    try:
        loja = db.query(database.Loja).order_by(database.Loja.id).first()
        loja_id = loja.id
    finally:
        db.bind.dispose(); db.close()
    _criar_operador(loja_id, nome)

    # ── Como e2e_master (tem pode_aprovar_financeiro): confirma que HOJE a sub-aba "8" existe —
    # controle positivo, senão o teste do operador poderia estar "passando" só porque a sub-aba
    # nunca existiu em lugar nenhum (projeto sem CicloEtapa pra "8", por exemplo). ─────────────
    page.evaluate("() => carregarCiclo()")
    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    ciclo.locator(".ficha-tab", has_text="Contrato").first.click()
    page.wait_for_timeout(300)
    assert ciclo.locator(".ficha-subtab", has_text="Aprovação financeira I").count() == 1, (
        "controle positivo: e2e_master (aprova financeiro) tem que VER a sub-aba 8 hoje")

    # ── Login como operador (sem pode_aprovar_financeiro) ──────────────────────────────────────
    _login(page, base, "e2e_operador_f240", "senha123")
    page.evaluate("async (nome) => { await abrirProjeto(nome); goPage(2); abrirCiclo(); }", nome)
    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    podeAF = page.evaluate("() => !!(_usuarioAtual && _usuarioAtual.pode_aprovar_financeiro)")
    assert podeAF is False, "pré-condição do teste: operador não pode aprovar financeiro"

    # 1) Sub-aba "8" (dentro do grupo "Contrato") some por inteiro — nem tab, nem card ─────────
    ciclo.locator(".ficha-tab", has_text="Contrato").first.click()
    page.wait_for_timeout(300)
    assert ciclo.locator(".ficha-subtab", has_text="Aprovação financeira I").count() == 0, (
        "F2-40 Fatia 3: sub-aba da AF1 não pode existir pra quem não aprova financeiro")
    assert "Aprovação financeira I" not in ciclo.inner_text()

    # 2) Sub-aba "11d" (dentro do grupo "Projeto executivo") some por inteiro ──────────────────
    ciclo.locator(".ficha-tab", has_text="Projeto executivo").first.click()
    page.wait_for_timeout(300)
    assert ciclo.locator(".ficha-subtab", has_text="Aprovação financeira II").count() == 0, (
        "F2-40 Fatia 3: sub-aba da AF2 não pode existir pra quem não aprova financeiro")
    assert "Aprovação financeira II" not in ciclo.inner_text()
    assert "restrita ao Gerente" not in ciclo.inner_text(), (
        "não é warn-restrito — é ausência total, sem mensagem nenhuma")

    # 3) Navegação entre etapas VIZINHAS continua funcionando ponta a ponta (não quebrou nada
    #    ao redor do buraco deixado por 8/11d) ─────────────────────────────────────────────────
    ciclo.locator(".ficha-subtab", has_text="Revisão de PE").first.click()
    page.wait_for_timeout(300)
    assert "Revisão de PE" in ciclo.inner_text()
    ciclo.locator(".ficha-subtab", has_text="Aprovação do PE pelo cliente").first.click()
    page.wait_for_timeout(300)
    assert "Aprovação do PE pelo cliente" in ciclo.inner_text()
    ciclo.locator(".ficha-tab", has_text="Medição").first.click()
    page.wait_for_timeout(300)
    assert page_errs == [], "navegação entre etapas vizinhas não pode gerar erro de JS: %r" % page_errs

    # 4) Defesa: forçar _fichaSelecionar('8')/('11d') direto (bypass do clique) não abre o card —
    #    _fichaVisivelParaUsuario redireciona pra mãe, mesmo chamado fora de um clique real. ────
    page.evaluate("() => { _fichaSelecionar('8'); }")
    page.wait_for_timeout(300)
    assert "restrita ao Gerente" not in ciclo.inner_text()
    assert "Aprovação financeira I" not in ciclo.inner_text() or \
           page.evaluate("() => _cicloEtapaAtiva") != "8", (
        "_fichaSelecionar('8') forçado não pode deixar a etapa ativa em '8' pra este usuário")
    assert page.evaluate("() => _cicloEtapaAtiva") != "8"

    page.evaluate("() => { _fichaSelecionar('11d'); }")
    page.wait_for_timeout(300)
    assert page.evaluate("() => _cicloEtapaAtiva") != "11d"
    assert page_errs == [], "erro de JS ao forçar seleção de etapa oculta: %r" % page_errs
