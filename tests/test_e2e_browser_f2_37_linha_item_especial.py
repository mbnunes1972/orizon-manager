# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-37 (Marcelo, 07/09).

O Item Especial vira LINHA na tabela de ambientes (Fatia 1) e o campo da caixa de edição ganha
formato financeiro (Fatia 2, `mascaraMoedaInput`/`parseMoeda` — já existentes, nenhuma máscara
nova). Critério de aceite: item lançado → linha aparece (Desc. % = 0 não editável, à vista =
valor cheio); item zerado → linha some; total da tabela bate com o VAVO do motor SEM somar de
novo (a linha só EXIBE uma fatia do que o total já contém).

Por que este teste TEM que ser de navegador: a linha é inserida/removida no DOM por
`_aplicarPreviewNaTela` (JS), reagindo ao preview do motor — nenhuma chamada de API isolada prova
que a estrutura da tabela reage certo, nem que a máscara formata ao vivo enquanto o usuário digita."""
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

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E F2-37" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
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


def test_linha_item_especial_aparece_some_e_nao_duplica_o_total(page, servidor_e2e):
    base = servidor_e2e

    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "F237 E2E")
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
    xml_path = "/tmp/e2e_f237_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('100.000,00')", timeout=10000)

    # ── ANTES: sem Item Especial, a linha não existe ──────────────────────────────────────────
    assert page.query_selector('tr[data-item-especial="1"]') is None

    # ── digita o valor: a caixa mostra o formato financeiro AO VIVO ("R$ 5.000,00") ────────────
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    inp = page.locator("#_ie-inp")
    inp.click()
    inp.press_sequentially("5000,00")   # digitado tecla a tecla — exercita mascaraMoedaInput no oninput
    assert inp.input_value() == "R$ 5.000,00"
    page.click('[data-act="ok"]')
    page.wait_for_timeout(1000)

    # ── DEPOIS: a linha aparece com Desc. % = 0 (não editável) e à vista = valor cheio ─────────
    tr = page.locator('tr[data-item-especial="1"]')
    tr.wait_for(state="visible", timeout=8000)
    assert "Item Especial" in tr.inner_text()
    desc_input = tr.locator("input[type='text'][disabled]")
    assert desc_input.input_value() == "0"
    assert desc_input.is_disabled()
    avista_cell = tr.locator('[data-col="avista"]')
    assert "5.000,00" in avista_cell.inner_text()
    fin_cell = tr.locator('[data-col="fin"]')
    assert "5.000,00" in fin_cell.inner_text()   # sem financiamento nesta modalidade (à vista): fin == avista

    # ── não-duplicação: o rodapé (Valor à Vista, soma dos ambientes) bate com o VAVO do motor,
    # que já inclui o item — a linha da tabela só EXIBE uma fatia, não soma de novo ────────────
    total_avista = page.inner_text("#neg-total-avista")
    v = float(total_avista.replace("R$", "").replace(".", "").replace(",", ".").strip())
    assert v == 105000.0, ("total da tabela tem que ser EXATAMENTE VAVO (100.000 dos ambientes + "
                           "5.000 do item, sem duplicar) — leu %r" % total_avista)

    # ── clicar na linha abre a MESMA caixa do botão (uma porta só) ─────────────────────────────
    tr.click()
    page.wait_for_selector("#_ie-inp", state="visible")
    assert page.inner_text("h4") == "Item Especial"
    page.click('[data-act="cancel"]')

    # ── item zerado → a linha SOME ─────────────────────────────────────────────────────────────
    page.click("#btn-item-especial")
    page.wait_for_selector("#_ie-inp", state="visible")
    page.fill("#_ie-inp", "0")
    page.click('[data-act="ok"]')
    page.wait_for_timeout(1000)
    page.wait_for_selector('tr[data-item-especial="1"]', state="detached", timeout=8000)
