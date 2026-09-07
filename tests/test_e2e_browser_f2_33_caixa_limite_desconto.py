# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-33, Fatia B (docs/db/ACHADOS_CONTABEIS.md).

DECIDIDO (Marcelo, 06/09): um bloqueio de rotina — "teu limite não cobre esse desconto" — NÃO é
erro e não deve usar a roupa de erro (`mostrarErroModal`/`#erro-modal-overlay`: fundo `--err-soft`,
borda `--err`, ícone de alerta grande e centralizado). Passa a usar a caixa sóbria padrão
(`avisoPopup`/`_popupOverlay`: fundo `--surface`, borda `--border`, título à esquerda, botão à
direita).

Por que este teste TEM que ser de navegador: qual CAIXA aparece (estilo, DOM, classe visual) é
puramente de tela — nenhuma chamada de API vê isto, só o motor do navegador renderizando.
Mocka o fetch de `/margens` pra devolver a recusa canônica (mesmo padrão de
`test_e2e_browser_paineis_identificam_projeto.py`), sem precisar montar orçamento/ambiente
reais — o que se prova aqui é qual componente de tela reage a `requer_autorizacao`, não o
cálculo do backend (já coberto em tests/test_f2_33_mensagens_limite_desconto.py)."""
import os
import socket
import subprocess
import sys
import time

import pytest

REPO = os.path.join(os.path.dirname(__file__), "..")
NOME_BANCO_ESPERADO = "orizon_e2e"
TEST_DB_URL = "postgresql+psycopg2://orizon:senha_local_qualquer@localhost/%s" % NOME_BANCO_ESPERADO


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


def _login(page, base):
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")


def test_limite_de_desconto_mostra_caixa_sobria_nao_a_vermelha(page, servidor_e2e):
    base = servidor_e2e
    _login(page, base)

    # mock do /margens (mesmo padrão de test_e2e_browser_paineis_identificam_projeto.py) +
    # _limiteAutorizado alto pra passar do early-return de salvarDescontoAutomatico() (o guard
    # cliente `if(desconto > cfgGetDescontoMax()) return;` é orthogonal ao que este teste prova —
    # o que importa é qual caixa a tela abre quando o SERVIDOR devolve requer_autorizacao).
    page.evaluate("""() => {
      _orcamentoAtivoId = 999;
      projetoAtivo = { margens: {} };
      _limiteAutorizado = 99;
      document.getElementById('neg-desconto').value = '60';
      const fetchOriginal = window.fetch;
      window.fetch = (url, opts) => {
        if (String(url).includes('/api/orcamentos/') && String(url).includes('/margens')) {
          return Promise.resolve({json: () => Promise.resolve({
            ok: false, requer_autorizacao: true,
            erro: 'Limite máximo de desconto excedido.'
          })});
        }
        return fetchOriginal(url, opts);
      };
    }""")
    # dispara sem esperar a promise: salvarDescontoAutomatico() é async e só resolve depois
    # que o avisoPopup for fechado — um page.evaluate que aguardasse a promise travaria aqui.
    page.evaluate("() => { salvarDescontoAutomatico(); }")

    # a caixa sóbria (_popupOverlay, usada por avisoPopup) — título à esquerda, botão à direita.
    page.wait_for_selector("text=Limite máximo de desconto excedido.", timeout=5000)

    # critério de aceite: a caixa VERMELHA (mostrarErroModal) NÃO pode ter sido aberta.
    assert page.query_selector("#erro-modal-overlay") is None, (
        "ACHADO F2-33: um bloqueio de rotina abriu a caixa de ERRO (#erro-modal-overlay, "
        "fundo --err-soft/borda --err) — devia abrir a caixa sóbria (avisoPopup)")

    # a caixa sóbria tem botão "OK" à direita (avisoPopup) — confirma que é a certa, não só que
    # a vermelha está ausente.
    botoes = page.locator('button:has-text("OK")')
    assert botoes.count() > 0, "avisoPopup não renderizou o botão OK esperado"
