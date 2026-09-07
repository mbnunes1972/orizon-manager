# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-38, Fatia 2 (Marcelo, 07/09).

SINTOMA reportado: digitar zero no Item Especial não fazia nada — o valor não zerava. Marcelo
testou em Homologação, na tag `v2026.09.07-beta2` (`52de29e`) — ANTERIOR ao F2-37 (`559e7a6`),
que trocou a caixa de edição de `promptPopup` (input genérico) por uma caixa própria com máscara
financeira. Reproduzido no navegador ANTES de mexer em código (com console aberto): no código
ATUAL (pós-F2-37), digitar "0" e apagar o campo inteiro JÁ funcionam — `mascaraMoedaInput` tem um
fallback (`|| '0'`) que normaliza um campo vazio pra "R$ 0" sozinho, e a caixa nova (`abrirItem
Especial`, F2-37) não tem o bug do `promptPopup` genérico (que tratava string vazia como
CANCELAR — `t ? t : null` —, nunca chegando a chamar `mpSalvarItemEspecial`). O F2-37 já
consertou isto de efeito colateral, sem ninguém perceber na hora.

Este teste é o ACEITE PERMANENTE pedido (mesmo padrão do ACHADO-64): prova que os dois caminhos
de zerar (digitar "0" e apagar o campo) funcionam HOJE, e falha se alguém voltar a trocar a caixa
por algo com o defeito do `promptPopup` genérico. Confirmado por git-checkout que este teste FALHA
contra `static/index.html` de `v2026.09.07-beta2` (o `promptPopup` antigo) e passa no código atual."""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E F2-38" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="Modulados" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="100000" TOTAL="100000"><MARGINS><ORDER TOTAL="70000"/><BUDGET TOTAL="100000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


def _sessao_teste():
    eng = create_engine(TEST_DB_URL)
    with eng.begin() as conn:
        atual = conn.execute(text("SELECT current_database()")).scalar()
    if atual != NOME_BANCO_ESPERADO:
        eng.dispose()
        raise RuntimeError("Recusado: sessão de teste só abre em %r — conectou em %r."
                          % (NOME_BANCO_ESPERADO, atual))


def _porta_livre():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def servidor_e2e():
    _sessao_teste()
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


def _setup_ate_o_ambiente(page, base, nome_projeto, xml_path):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", nome_projeto)
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "100000")
    page.select_option("#bf-categoria", index=1)
    page.fill("#bf-data-entrega", "2027-06-01")
    page.select_option("#bf-flexibilidade", index=1)
    page.click('button:has-text("Salvar Briefing")')
    page.wait_for_selector("#modal-briefing", state="hidden")

    page.click("#btn-novo-orc")
    page.fill("#novo-orc-nome-input", "Orçamento 1")
    page.locator("#modal-novo-orc").get_by_role("button", name="Criar", exact=True).click()
    page.wait_for_selector("#modal-novo-orc", state="hidden")
    try:
        page.wait_for_selector('[data-act="salvar"]', timeout=2000)
        page.click('[data-act="salvar"]')
    except Exception:
        pass
    page.click("#btn-novo-ambiente")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=10000)


def test_digitar_zero_zera_o_item_especial(page, servidor_e2e):
    base = servidor_e2e
    _setup_ate_o_ambiente(page, base, "F238 Zero E2E", "/tmp/e2e_f238_zero.xml")

    # lança 5.000
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    page.fill("#_ie-inp", "5000")
    page.click('[data-act="ok"]')
    page.wait_for_selector('tr[data-item-especial="1"]', state="visible", timeout=8000)
    page.wait_for_selector("#neg-subtotal:has-text('105.000,00')", timeout=8000)

    # digita "0" e salva — o item tem que zerar de verdade (linha some, subtotal volta)
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    page.fill("#_ie-inp", "0")
    page.click('[data-act="ok"]')
    page.wait_for_selector('tr[data-item-especial="1"]', state="detached", timeout=8000)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=8000)


def test_apagar_o_campo_e_salvar_tambem_zera_o_item_especial(page, servidor_e2e):
    base = servidor_e2e
    _setup_ate_o_ambiente(page, base, "F238 Zero Apagar E2E", "/tmp/e2e_f238_zero_apagar.xml")

    # lança 5.000
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    page.fill("#_ie-inp", "5000")
    page.click('[data-act="ok"]')
    page.wait_for_selector('tr[data-item-especial="1"]', state="visible", timeout=8000)
    page.wait_for_selector("#neg-subtotal:has-text('105.000,00')", timeout=8000)

    # APAGA o campo inteiro (não digita "0") e salva — mesmo resultado: item zerado
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    page.fill("#_ie-inp", "")
    page.click('[data-act="ok"]')
    page.wait_for_selector('tr[data-item-especial="1"]', state="detached", timeout=8000)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=8000)
