# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-40 Fatia 1 (docs/db/ROTEIRO.md): "Negociar Complemento"
sai do bloco de upload de XML (dentro de #pe-complemento-container, etapa 11e) e vai para o
cabeçalho do card "Aprovação do Projeto Executivo", MESMA etapa 11e — condição de exibição
IDÊNTICA à de antes (linhas.length > 0: pelo menos um ambiente marcado para complemento na
Revisão de PE), medida e reusada, não reinventada."""
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


def _marcar_renegociar_pe(nome_projeto, valor):
    import database
    db = _sessao_teste()
    try:
        pas = db.query(database.PoolAmbiente).filter_by(projeto_id=nome_projeto).all()
        assert pas, "projeto precisa ter ao menos 1 ambiente"
        for pa in pas:
            pa.renegociar_pe = valor
        db.commit()
    finally:
        db.bind.dispose()
        db.close()


def test_botao_negociar_complemento_vive_no_card_de_aprovacao_no_11e(page, servidor_e2e):
    base = servidor_e2e
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E F2-40 Fatia1 Botao 11e")
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d"])

    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    # carregarCiclo() de novo: _cicloData no browser ainda reflete o snapshot de ANTES de
    # _marcar_concluidas (que escreveu direto no banco) — sem isto, "11e" continua "bloqueada".
    page.evaluate("async () => { await carregarCiclo(); }")

    # ── Condição de exibição = 0 (nenhum ambiente marcado): SEM botão em lugar nenhum ─────────
    page.evaluate("() => { _fichaSelecionar('11e'); }")
    page.wait_for_selector("text=Nenhum ambiente marcado para complemento", timeout=10000)
    assert page.locator('button:has-text("Negociar Complemento")').count() == 0, (
        "sem ambiente marcado (linhas.length===0), o botão não pode aparecer em lugar nenhum")
    assert "Nenhum ambiente marcado para complemento" in ciclo.inner_text()

    # ── Marca o ambiente e reabre a 11e — condição vira verdadeira ────────────────────────────
    _marcar_renegociar_pe(nome, 1)
    page.evaluate("() => { peComplementoRender(); }")
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    btn = page.locator('button:has-text("Negociar Complemento")')
    assert btn.count() == 1, "com 1 ambiente marcado, o botão tem que existir — só 1 cópia"

    # ── O botão vive no cabeçalho do card "Aprovação do Projeto Executivo", NÃO mais no bloco
    #    de upload de XML ("Carregar Complemento de Projeto") — mesma etapa 11e, bloco diferente.
    cont = page.locator("#pe-complemento-container")
    html = cont.inner_html()
    pos_upload = html.find("Carregar Complemento de Projeto")
    pos_aprovacao = html.find("Aprovação do Projeto Executivo")
    pos_botao = html.find("Negociar Complemento")
    assert pos_upload >= 0 and pos_aprovacao >= 0 and pos_botao >= 0, (
        "os três marcadores têm que existir no container — %r" % (
            (pos_upload, pos_aprovacao, pos_botao),))
    assert pos_botao > pos_aprovacao, (
        "o botão precisa vir DEPOIS do título 'Aprovação do Projeto Executivo' — está no card errado")
    assert not (pos_upload < pos_botao < pos_aprovacao), (
        "o botão não pode estar entre o bloco de upload e o de aprovação (bloco antigo)")

    # ── Desmarca de novo — condição volta a falso, botão some ─────────────────────────────────
    _marcar_renegociar_pe(nome, 0)
    page.evaluate("() => { peComplementoRender(); }")
    page.wait_for_selector("text=Nenhum ambiente marcado para complemento", timeout=10000)
    assert page.locator('button:has-text("Negociar Complemento")').count() == 0

    assert page_errs == [], "erro de JS durante o percurso: %r" % page_errs
