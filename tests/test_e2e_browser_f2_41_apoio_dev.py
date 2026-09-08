# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-41 Rodada 1, item 4 (docs/db/TAREFA_F2_41_FONTE_UNICA_
COMPLEMENTO.md): textos de apoio interno (desconto global/carga de custos adicionais, divergência
de sombra) somem da tela do cliente por padrão — MARCADOS (classe `apoio-dev`), não apagados.
Interruptor único `data-apoio` no `<body>`, default `off`; liga com `data-apoio="on"`."""
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


def test_apoio_dev_escondido_por_padrao_e_visivel_com_data_apoio_on(page, servidor_e2e):
    base = servidor_e2e
    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E F2-41 Apoio Dev")
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d"])

    import database
    db = _sessao_teste()
    try:
        pa = db.query(database.PoolAmbiente).filter_by(projeto_id=nome).first()
        pa.renegociar_pe = 1
        reg = database.ArquivoPE(projeto_nome=nome, pool_ambiente_id=pa.id,
                                 formato="xml_compl", valor_venda=154000.0, valor_atualizado=110000.0)
        db.add(reg)
        db.commit()
    finally:
        db.bind.dispose()
        db.close()

    page.evaluate("async () => { await carregarCiclo(); }")
    page.evaluate("() => { _fichaSelecionar('11e'); }")
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    page.click('button:has-text("Negociar Complemento")')
    modal = page.locator("#modal-pe-compl")
    modal.wait_for(state="visible", timeout=10000)
    page.locator("#pe-compl-modal-body .apoio-dev").first.wait_for(state="attached", timeout=10000)

    # ── 1) Default do sistema (data-apoio="off" já no <body>, como servido) — nada visível ──────
    assert page.evaluate("() => document.body.getAttribute('data-apoio')") == "off"
    apoio = page.locator(".apoio-dev")
    assert apoio.count() >= 2, "cabeçalho do modal + linha de divergência, os dois com apoio-dev"
    for i in range(apoio.count()):
        assert not apoio.nth(i).is_visible(), "apoio-dev tem que ficar invisível com data-apoio=off"

    # ── 2) data-apoio AUSENTE (não só "off") — mesmo resultado, aceite pede os dois casos ───────
    page.evaluate("() => document.body.removeAttribute('data-apoio')")
    for i in range(apoio.count()):
        assert not apoio.nth(i).is_visible(), "apoio-dev tem que ficar invisível com data-apoio ausente"

    # ── 3) Liga o interruptor — os textos aparecem ───────────────────────────────────────────────
    page.evaluate("() => document.body.setAttribute('data-apoio', 'on')")
    for i in range(apoio.count()):
        assert apoio.nth(i).is_visible(), "com data-apoio=on, apoio-dev tem que ficar visível"
    assert "divergência" in page.locator("#pe-compl-modal-body").inner_text().lower()

    # ── Desliga de novo — confirma que não é um efeito de uma via só ────────────────────────────
    page.evaluate("() => document.body.setAttribute('data-apoio', 'off')")
    for i in range(apoio.count()):
        assert not apoio.nth(i).is_visible()
