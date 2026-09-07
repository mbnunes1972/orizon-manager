# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-35, ACHADO-65 (docs/db/ACHADOS_CONTABEIS.md).

Item Especial (Outros Fornecedores nascido na VENDA): botão novo ao lado de "Novo Ambiente",
caixa sóbria (promptPopup) pra editar o valor, campo #mp-out-forn no modal de Parâmetros virou
SÓ LEITURA (edição migrou pro botão). Critério de aceite: clicar o botão, digitar um valor, salvar
— e ver a tela de negociação (Valor Bruto, Total do Contrato) e o modal de Parâmetros reagirem ao
motor de verdade, não a um campo morto.

Por que este teste TEM que ser de navegador: o fio que liga o clique do botão → promptPopup →
mpSalvarOutForn → PUT /out-forn → _aplicarPreviewNaTela só existe encadeado no DOM real; nenhuma
chamada de API isolada prova que o botão certo dispara a caixa certa e que a tela se atualiza."""
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

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
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


def test_item_especial_botao_soma_no_bruto_e_no_total_e_campo_do_modal_vira_leitura(page, servidor_e2e):
    base = servidor_e2e

    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "Achado65 E2E")
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
    xml_path = "/tmp/e2e_achado65_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=10000)

    total_antes = page.inner_text("#neg-total")

    # ── botão "Item Especial" abre a caixa sóbria (promptPopup), não a vermelha de erro ──────
    page.click("#btn-item-especial")
    page.wait_for_selector("#_pp-inp", state="visible")
    page.fill("#_pp-inp", "5000,00")
    page.click('[data-act="ok"]')
    page.wait_for_timeout(1000)   # await interno de mpSalvarOutForn (fetch + redesenho)

    # ── Valor Bruto sobe pelo item (VBNO simétrico — "markup 1") ──────────────────────────────
    page.wait_for_selector("#neg-subtotal:has-text('105.000,00')", timeout=8000)

    # ── Total do Contrato sobe EXATO o valor do item (Val_Cont inclui via VAVO) ───────────────
    total_depois = page.inner_text("#neg-total")
    v_antes = float(total_antes.replace("R$", "").replace(".", "").replace(",", ".").strip())
    v_depois = float(total_depois.replace("R$", "").replace(".", "").replace(",", ".").strip())
    assert round(v_depois - v_antes, 2) == 5000.0, (total_antes, total_depois)

    # ── modal de Parâmetros: #mp-item-especial é um <span> só-leitura, mostrando o valor salvo ──
    # F2-36: Item Especial e Outros Fornecedores viraram DOIS campos — #mp-out-forn passou a
    # mostrar o saldo vivo de Outros Fornecedores (substituição da AF), não mais o Item Especial.
    page.click("#btn-params")
    page.wait_for_selector("#modal-params", state="visible")
    assert page.eval_on_selector("#mp-item-especial", "el => el.tagName") == "SPAN"
    assert "5.000,00" in page.inner_text("#mp-item-especial")
