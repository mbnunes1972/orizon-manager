# -*- coding: utf-8 -*-
"""docs/db/TAREFA_F2_43_PAGAMENTO_COMPLEMENTO.md — achado da medição (não do relato original).

O relato do usuário (percurso 11e → Negociar Complemento → Definir forma de pagamento) não foi
reproduzido pela medição: nas rodadas feitas, `_resetPagamentoPadrao` sempre terminava e já
deixava `_tipoAtivo='avista'` antes de qualquer preview do motor chegar. Mas a medição mediu uma
assimetria REAL e independente do relato: das cinco modalidades, só à vista (`avistaRecalcular`,
~10080) NÃO tem entrada em `_atualizarPaineisAbertos()` (~10505) — as outras quatro (Aymoré,
Cartão, VP, TF) recalculam por VISIBILIDADE do painel no DOM (`painel-*.style.display !== 'none'`)
toda vez que um preview do motor chega; à vista só recalcula sob um gate à parte
(`_tipoAtivo === 'avista'`, ~11715), uma variável JS separada da visibilidade do painel. Se essa
variável ficar um passo atrás do DOM (troca de orçamento em voo, fetch de `/pagamentos/.../faixas`
que resolve depois do preview, etc. — mecanismo plausível, não reproduzido ponta a ponta), a caixa
"Valor Total do Contrato" (#neg-parcelado), "Valor da liquidação" (#av-liq-valor) e
`window._planoPagamento` ficam com o plano de ANTES — o mesmo defeito, por uma porta diferente do
precedente de 2026-08-17 (comentário ~11707-11714).

Este teste não depende de complemento nem de dois orçamentos — é a promessa que vale pra QUALQUER
orçamento em qualquer modalidade: depois de qualquer preview do motor, a caixa da modalidade à
vista concorda com o `#neg-avista` que o PRÓPRIO preview acabou de escrever, independentemente do
que estivesse na tela ou em `_tipoAtivo` antes. "Envenena" as caixas com um plano que não é o do
preview (simulando o que sobraria de outro orçamento/modalidade) e a variável `_tipoAtivo` com um
valor que não é 'avista' (simulando a variável atrasada), dispara `_aplicarPreviewNaTela` (o mesmo
ponto de entrada real que qualquer preview do motor usa) e afirma que a tela corrige sozinha.
"""
import os
import socket
import subprocess
import sys
import time

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO

XML_ONE_AMBIENTE = '''<PROJECT DESCRIPTION="Cozinha E2E" DATE="01/01/2026"><CATEGORY DESCRIPTION="Cozinha"><ITEMS>
<ITEM REFERENCE="A" DESCRIPTION="Modulados" UNIT="UN" QUANTITY="1" SHOWPRICE="Y">
<PRICE TABLE="140000" TOTAL="140000"><MARGINS><ORDER TOTAL="100000"/><BUDGET TOTAL="140000"/></MARGINS></PRICE></ITEM>
</ITEMS></CATEGORY></PROJECT>'''


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


def test_avista_concorda_com_neg_avista_apos_preview_mesmo_envenenada(page, servidor_e2e):
    base = servidor_e2e
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    # ── Preâmbulo mínimo: projeto + 1 ambiente, sem aprovar/assinar nada — a promessa não
    # depende de complemento nem de contrato, só de existir uma negociação em à vista. ──────────
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", "F2-43 Avista Concorda")
    page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "150000")
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
    xml_path = "/tmp/e2e_f2_43_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('140.000,00')", timeout=10000)

    # ── Ponto de partida: à vista (default), painel visível, tudo consistente ────────────────
    page.select_option("#neg-pagamento", "a_vista")
    page.wait_for_timeout(500)
    assert page.evaluate("() => _tipoAtivo") == "avista"
    assert page.evaluate(
        "() => document.getElementById('painel-avista').style.display") != "none"

    # ── Envenena as caixas com um plano que NÃO é o que o preview vai mandar, e atrasa
    # `_tipoAtivo` (simula a variável um passo atrás do DOM/preview — o mecanismo medido).
    # NOTA: `#neg-parcelado` (um dos 8 itens do doc original) é hoje um gêmeo morto — apagado do
    # DOM no ACHADO-64 (06/09, ver comentário ~1540-1545); `negMostrarParcelado()` virou no-op
    # segura. A caixa viva equivalente ("Valor Total do Contrato") é `#neg-total-final`, escrita
    # DIRETO por `_aplicarPreviewNaTela` (não por avistaRecalcular) — por isso nunca fica presa
    # ao plano velho. As caixas realmente dependentes de avistaRecalcular são `#av-liq-valor`,
    # `#av-r-liq-valor` (resumo read-only) e `window._planoPagamento`. ──────────────────────────
    page.evaluate("""() => {
        document.getElementById('av-liq-valor').value = 'R$ 999.999,99';
        document.getElementById('av-r-liq-valor').textContent = 'R$ 999.999,99';
        window._planoPagamento = {
            tipo: 'cartao_credito', nome_forma: 'Cartao De Outro Orcamento (envenenado)',
            entrada_valor: 0, total_cliente: 999999.99, texto_cartao: '15x com juros',
            parcelas: Array.from({length: 15}, (_, i) => ({num: i + 1, valor: 66666.66})),
        };
        _tipoAtivo = 'cartao_credito';   // a variável, atrasada — o painel visível continua sendo o de à vista
    }""")
    assert page.evaluate("() => document.getElementById('av-liq-valor').value") == "R$ 999.999,99"
    assert page.evaluate("() => _tipoAtivo") == "cartao_credito"

    # ── Dispara um preview do motor pelo MESMO ponto de entrada real (_aplicarPreviewNaTela) —
    # à vista, sem financiamento: VBNO=VAVO=Val_Cont=140.000,00. ─────────────────────────────
    page.evaluate("""() => {
        _aplicarPreviewNaTela({VBNO: 140000, VAVO: 140000, Val_Cont: 140000, Desc_Efetivo: 0});
    }""")
    page.wait_for_timeout(500)

    neg_avista_txt = page.inner_text("#neg-avista")
    assert "140.000,00" in neg_avista_txt, neg_avista_txt

    liq = page.evaluate("() => document.getElementById('av-liq-valor').value")
    liq_resumo = page.evaluate("() => document.getElementById('av-r-liq-valor').textContent")
    plano = page.evaluate("() => window._planoPagamento")

    assert "140.000,00" in liq, (
        "#av-liq-valor ficou com o plano envenenado depois do preview: %r "
        "(o #neg-avista do MESMO preview já mostra %r)" % (liq, neg_avista_txt))
    assert "140.000,00" in liq_resumo, (
        "#av-r-liq-valor (resumo) ficou com o plano envenenado depois do preview: %r" % liq_resumo)
    assert plano.get("tipo") == "avista" and abs(plano.get("total_cliente", 0) - 140000) < 0.01, (
        "window._planoPagamento ficou com o plano de outro orçamento/modalidade depois do "
        "preview: %r" % plano)

    assert page_errs == [], "erro de JS durante o percurso: %r" % page_errs
