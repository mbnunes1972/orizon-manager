# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — TAREFA-B, B3/B4 (docs/db/TAREFA_LEAD_E_PAINEL_SAC.md),
provas 6 (a marca de "aguardando resposta" aparece no item) e 7 (duas conversas pendentes, a
de janela menor vem primeiro).

`_atdItemHTML`/`_atdOrdenar`/`_atdRestanteOrdenavel` (static/index.html) são lógica/render
PUROS — não existe teste JS neste projeto (CLAUDE.md: "Frontend: não há teste JS →
verificação manual no navegador"), e simular conversas `pendente` reais (com XML/negociação/
contrato) pra provar só render/ordenação herdaria o custo e o flake conhecido
(`#neg-subtotal`, família LP-22) dos e2e pesados, por um fato que não depende de nenhum deles.
Em vez disso, chama a função REAL da página carregada (`page.evaluate`, mesmo padrão de
test_aceite_b6_fila_tooltips.py) com dados sintéticos — rápido, determinístico, sem upload
nem cálculo de motor. O cálculo de `pendente` em si (última mensagem externa → True) já tem
cobertura de backend (tests/test_chat_arquivar.py); aqui é só o RENDER da marca."""
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


def test_marca_de_aguardando_resposta_aparece_no_item(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    com_pendente = page.evaluate("""() => _atdItemHTML({
      id: 1, tipo: 'grupo', titulo: 'Cliente Esperando', pendente: true,
      nao_lidas: 0, urgente: false, status: 'aberta',
    })""")
    sem_pendente = page.evaluate("""() => _atdItemHTML({
      id: 2, tipo: 'grupo', titulo: 'Cliente Em Dia', pendente: false,
      nao_lidas: 0, urgente: false, status: 'aberta',
    })""")
    assert "atd-pend-ico" in com_pendente, "pendente=true tinha que renderizar a marca"
    assert "atd-pend-ico" not in sem_pendente, "pendente=false não pode mostrar a marca"


def test_pendente_ordena_por_janela_restante_menor_primeiro(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # Sintético, de propósito (ver docstring do módulo): duas PENDENTE (janela "fechando" com
    # restante_seg diferente — a menor tem que vir primeiro), uma PENDENTE com janela já
    # FECHADA (mais urgente que qualquer restante_seg positivo — vem antes das duas), e uma
    # NÃO pendente (fica depois de todas, mantém a posição que já tinha).
    ordem = page.evaluate("""() => {
      const itens = [
        {id: 'A', pendente: true,  janela: {estado: 'fechando', restante_seg: 7200}},
        {id: 'B', pendente: true,  janela: {estado: 'fechando', restante_seg: 900}},
        {id: 'C', pendente: true,  janela: {estado: 'fechada'}},
        {id: 'D', pendente: false, janela: {estado: 'aberta'}},
      ];
      return _atdOrdenar(itens).map(c => c.id);
    }""")
    assert ordem == ["C", "B", "A", "D"], (
        "esperava fechada > menor restante > maior restante > não-pendente, veio: %r" % ordem)
