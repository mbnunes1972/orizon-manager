# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — Termo Aditivo na 11e oferece a MESMA escolha de canal que os
três irmãos (ACHADO-69, Passo 3, aceite 9). Existe porque o argumento "os E2E de navegador estão
com flake não explicado, não vale a pena somar mais um agora" não vence nesta tela específica:
foi exatamente aqui, na 11e, que o ACHADO-25 aconteceu — um campo obrigatório novo que passou
despercebido com 2466 testes VERDES, e nenhum aditivo pôde ser assinado em produção. Esta tela já
provou que precisa de prova por clique real, não só por chamada de API.

Cobre as DUAS opções na mesma sessão de navegador:
  1. Canal interno (nome + CPF direto, sem ClickSign) — já provado em
     test_e2e_browser_conciliacao_final.py; repetido aqui como controle antes de trocar de canal
     na MESMA aba, não como duplicação.
  2. Canal ClickSign — enviar (com o modal de forma de pagamento do ACHADO-25 primeiro, porque
     ACHADO-21 6-c: o canal remoto não tem outro instante síncrono pra perguntar isso), verificar
     via clique real em "Verificar agora", e o card refletir "assinado" depois de reconciliado.

ClickSign real NUNCA é chamado por um teste automatizado — `main.py` sobe apontando pra um
servidor ClickSign FALSO local (`_FakeClickSignServer` abaixo), via
`ORIZON_CLICKSIGN_BASE_URL_OVERRIDE` (único seam de teste em `integracoes/clicksign_config.py`,
inerte quando a variável não existe). O "fechar o envelope" (sinal de conclusão — a ClickSign
real nunca preenche `signed_at` no signer, achado de 20/08) é um endpoint de administração do
próprio servidor falso, nunca exposto em produção.

Mesmas duas regras do teste terminal (`test_e2e_browser_conciliacao_final.py`): sobe o PRÓPRIO
servidor a partir do código atual, num subprocesso; navegador limpo (Chromium isolado do
pytest-playwright, sem perfil/extensão).
"""
import http.server
import json as _json
import os
import re
import socket
import subprocess
import sys
import threading
import time

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("ORIZON_FISCAL_KEY", Fernet.generate_key().decode())

from tests.test_e2e_browser_conciliacao_final import (
    REPO, TEST_DB_URL, XML_ONE_AMBIENTE, _porta_livre, _sessao_teste,
)


# ── Servidor ClickSign FALSO (thread local, nunca a rede real) ──────────────────────────────────

class _EstadoClickSignFalso:
    def __init__(self):
        self.seq = 0
        self.envelopes = {}   # envelope_id -> {status, signers: {signer_id: {email, name}}}

    def novo_id(self, prefixo):
        self.seq += 1
        return "%s-%d" % (prefixo, self.seq)


class _HandlerClickSignFalso(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass   # silencia o access log no stdout do teste

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        cru = self.rfile.read(n) if n else b""
        try:
            return _json.loads(cru) if cru else {}
        except Exception:
            return {}

    def _responder(self, status, payload):
        corpo = _json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/vnd.api+json")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_POST(self):
        st = self.server.estado
        m = re.match(r"^/_test/fechar/([^/]+)$", self.path)
        if m:   # gancho de administração do FALSO — nunca existe na ClickSign real
            env = st.envelopes.get(m.group(1))
            if env is not None:
                env["status"] = "closed"
            self._responder(200, {"ok": True})
            return
        corpo = self._corpo()
        if self.path == "/envelopes":
            env_id = st.novo_id("env")
            st.envelopes[env_id] = {"status": "running", "signers": {}}
            self._responder(201, {"data": {"id": env_id, "type": "envelopes"}})
            return
        if re.match(r"^/envelopes/[^/]+/documents$", self.path):
            self._responder(201, {"data": {"id": st.novo_id("doc"), "type": "documents"}})
            return
        m = re.match(r"^/envelopes/([^/]+)/signers$", self.path)
        if m:
            env = st.envelopes[m.group(1)]
            signer_id = st.novo_id("signer")
            attrs = (corpo.get("data") or {}).get("attributes") or {}
            env["signers"][signer_id] = {"email": attrs.get("email"), "name": attrs.get("name")}
            self._responder(201, {"data": {"id": signer_id, "type": "signers"}})
            return
        if re.match(r"^/envelopes/[^/]+/requirements$", self.path):
            self._responder(201, {"data": {"id": st.novo_id("req"), "type": "requirements"}})
            return
        if re.match(r"^/envelopes/[^/]+/notifications$", self.path):
            self._responder(201, {"data": {"id": st.novo_id("notif"), "type": "notifications"}})
            return
        self._responder(404, {"errors": [{"detail": "rota não implementada no falso: " + self.path}]})

    def do_PATCH(self):
        m = re.match(r"^/envelopes/([^/]+)$", self.path)
        if m:
            self._responder(200, {"data": {"id": m.group(1), "type": "envelopes"}})
            return
        self._responder(404, {"errors": [{"detail": "rota não implementada no falso: " + self.path}]})

    def do_GET(self):
        st = self.server.estado
        m = re.match(r"^/envelopes/([^/?]+)", self.path)
        if m:
            env = st.envelopes.get(m.group(1))
            if env is None:
                self._responder(404, {"errors": [{"detail": "envelope não existe no falso"}]})
                return
            included = [{"type": "signers", "id": sid, "attributes": {
                            "email": info["email"], "name": info["name"], "signed_at": None}}
                        for sid, info in env["signers"].items()]
            self._responder(200, {"data": {"id": m.group(1),
                                           "attributes": {"status": env["status"]}},
                                  "included": included})
            return
        self._responder(404, {"errors": [{"detail": "rota não implementada no falso: " + self.path}]})


@pytest.fixture(scope="module")
def clicksign_falso():
    porta = _porta_livre()
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", porta), _HandlerClickSignFalso)
    servidor.estado = _EstadoClickSignFalso()
    t = threading.Thread(target=servidor.serve_forever, daemon=True)
    t.start()
    try:
        yield servidor, "http://127.0.0.1:%d" % porta
    finally:
        servidor.shutdown()
        t.join(timeout=5)


@pytest.fixture(scope="module")
def servidor_e2e(clicksign_falso):
    _servidor_falso, base_falso = clicksign_falso
    porta = _porta_livre()
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "_e2e_bootstrap.py"),
                       TEST_DB_URL], cwd=REPO, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, "bootstrap do banco falhou:\n" + r.stdout + r.stderr

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DB_URL
    env["ORIZON_PORT"] = str(porta)
    env["ORIZON_HOST"] = "127.0.0.1"
    env["ORIZON_CLICKSIGN_BASE_URL_OVERRIDE"] = base_falso
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
                    saida = proc.stdout.read()
                    raise RuntimeError("servidor E2E morreu no boot:\n" + saida)
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


def _dispensar_alteracoes_nao_salvas(page):
    try:
        page.wait_for_selector('[data-act="salvar"]', timeout=2000)
        page.click('[data-act="salvar"]')
    except Exception:
        pass


def test_termo_aditivo_11e_oferece_as_duas_opcoes_de_canal(page, servidor_e2e, clicksign_falso):
    servidor_falso, _base_falso = clicksign_falso
    base = servidor_e2e
    nome_exibicao = "E2E Aditivo ClickSign"
    nome_projeto = nome_exibicao

    # ── 1. Login ─────────────────────────────────────────────────────────────────────────────
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    # ── 2. Criar projeto + briefing ──────────────────────────────────────────────────────────
    page.click('button:has-text("Novo Projeto")')
    page.fill("#novo-proj-nome", nome_exibicao)
    # Achado do MAPA_MODULOS/#np-cli-dropdown (14/09/2026): a busca debounça 300ms antes de
    # disparar o fetch — esperar só pelo <div> do dropdown corre contra esse timer implícito e
    # flakava mesmo com backend rápido e máquina ociosa. Espera a RESPOSTA de verdade primeiro.
    with page.expect_response(lambda r: "/api/clientes" in r.url and "q=" in r.url):
        page.fill("#novo-proj-cli", "Cliente E2E")
    page.wait_for_selector("#np-cli-dropdown div")
    page.click("#np-cli-dropdown div")
    page.click('button:has-text("Criar Projeto")')
    page.wait_for_selector("#modal-briefing", state="visible")
    nome_projeto = page.evaluate("() => projetoAtivo.nome_safe")

    page.select_option("#bf-tipo-imovel", index=1)
    page.fill("#bf-budget", "150000")
    page.select_option("#bf-categoria", index=1)
    page.fill("#bf-data-entrega", "2027-06-01")
    page.select_option("#bf-flexibilidade", index=1)
    page.click('button:has-text("Salvar Briefing")')
    page.wait_for_selector("#modal-briefing", state="hidden")

    # ── 3. Orçamento + ambiente (XML real) ───────────────────────────────────────────────────
    page.click("#btn-novo-orc")
    page.fill("#novo-orc-nome-input", "Orçamento 1")
    page.locator("#modal-novo-orc").get_by_role("button", name="Criar", exact=True).click()
    page.wait_for_selector("#modal-novo-orc", state="hidden")

    _dispensar_alteracoes_nao_salvas(page)
    page.click("#btn-novo-ambiente")
    xml_path = "/tmp/e2e_aditivo_clicksign_ambiente.xml"
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(XML_ONE_AMBIENTE)
    page.set_input_files("#xml-input-amb", xml_path)
    page.wait_for_selector("#neg-subtotal:has-text('140.000,00')", timeout=10000)

    # ── 4. Aprovar orçamento / gerar contrato ────────────────────────────────────────────────
    page.click("#btn-aprovar-orcamento")
    page.wait_for_selector("#modal-aprovacao-overlay")
    page.click('#modal-aprovacao-overlay button:has-text("Gerar Contrato")')
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.locator("text=Contrato gerado").count():
            break
        clicado = False
        for sel in ('[data-act="ok"]', 'button:has-text("Confirmar contatos")',
                   'button:has-text("Gerar assim")'):
            loc = page.locator(sel)
            if loc.count() and loc.first.is_visible():
                loc.first.click()
                clicado = True
                break
        page.wait_for_timeout(300 if clicado else 400)
    page.wait_for_selector("text=Contrato gerado", timeout=10000)

    # ── 5. Assinar contrato (canal interno) — pré-requisito do Aditivo ───────────────────────
    def _dispensar_transferir():
        btn = page.locator('button:has-text("Sim, transferir")')
        if btn.count() and btn.first.is_visible():
            btn.first.click()
            page.wait_for_timeout(300)

    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    _dispensar_transferir()
    ciclo.locator(".ficha-tab", has_text="Contrato").first.click()
    page.wait_for_timeout(500)
    _dispensar_transferir()

    page.fill("#ct-previsao-medicao", "2027-03-01")
    page.fill("#ct-data-entrega", "2027-06-01")
    page.click('button:has-text("Validar")')
    page.wait_for_timeout(500)

    with page.expect_popup():
        ciclo.get_by_role("link", name="Imprimir").first.click()
    assinatura = page.locator("#secao-assinatura-contrato")
    page.check("#conf-ct-loja")
    page.fill("#conf-ct-loja-nome", "Rep Loja E2E")
    page.fill("#conf-ct-loja-cpf", "111.444.777-35")
    page.check("#conf-ct-cliente")
    page.fill("#conf-ct-cliente-nome", "Cliente E2E")
    page.fill("#conf-ct-cliente-cpf", "111.444.777-35")
    assinatura.get_by_role("button", name="Confirmar", exact=True).click()
    page.wait_for_selector("text=Contrato assinado", timeout=10000)

    import mod_ciclo
    import database

    def _marcar_concluido(cod):
        db = _sessao_teste()
        try:
            et = db.query(database.CicloEtapa).filter_by(
                projeto_nome=nome_projeto, etapa_codigo=cod).first()
            if et is None:
                et = database.CicloEtapa(projeto_nome=nome_projeto, etapa_codigo=cod)
                db.add(et)
            et.status = "concluido"
            db.commit()
        finally:
            db.bind.dispose()
            db.close()

    _marcar_concluido(mod_ciclo.MEDICAO)

    # ── 6. Seed do complemento de PE (o XML em si não é o objeto deste teste, como em
    #      test_e2e_browser_conciliacao_final.py — semeado direto, igual à Medição acima) ──────
    def _seed_complemento(venda, cfo):
        db = _sessao_teste()
        try:
            pa = db.query(database.PoolAmbiente).filter_by(projeto_id=nome_projeto).first()
            pa.renegociar_pe = 1
            reg = (db.query(database.ArquivoPE)
                     .filter_by(projeto_nome=nome_projeto, pool_ambiente_id=pa.id,
                                formato="xml_compl").first())
            if reg is None:
                reg = database.ArquivoPE(projeto_nome=nome_projeto, pool_ambiente_id=pa.id,
                                         formato="xml_compl")
                db.add(reg)
            reg.valor_venda = venda
            reg.valor_atualizado = cfo
            db.commit()
        finally:
            db.bind.dispose()
            db.close()

    _seed_complemento(venda=180000.0, cfo=130000.0)

    page.evaluate("() => carregarCiclo()")
    ciclo.locator(".ficha-tab", has_text="Projeto executivo").first.click()
    page.wait_for_timeout(500)
    page.click("text=Aprovação do PE pelo cliente")
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    page.click('button:has-text("Negociar Complemento")')

    modal = page.locator("#modal-pe-compl")
    modal.wait_for(state="visible", timeout=10000)
    corpo = page.locator("#pe-compl-modal-body")
    corpo.locator('button:has-text("Definir forma de pagamento")').wait_for(state="visible", timeout=10000)
    corpo.locator('button:has-text("Definir forma de pagamento")').click()

    page.locator("#btn-salvar-orcamento").wait_for(state="visible", timeout=10000)
    page.click("#btn-salvar-orcamento")
    page.wait_for_selector("text=Orçamento salvo", timeout=10000)

    ciclo.wait_for(state="visible", timeout=10000)
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    page.click('button:has-text("Negociar Complemento")')
    modal.wait_for(state="visible", timeout=10000)
    corpo.locator('button:has-text("Gerar Termo Aditivo"):not([disabled])').wait_for(
        state="visible", timeout=10000)
    corpo.locator('button:has-text("Gerar Termo Aditivo")').click()
    page.wait_for_selector("text=Termo aditivo gerado", timeout=10000)
    modal.wait_for(state="hidden", timeout=5000)

    # ── 7. OPÇÃO 1 — canal interno: assina loja + cliente (controle, mesma sessão) ───────────
    page.fill("#pe-ad-nome", "Rep Loja E2E")
    page.fill("#pe-ad-cpf", "111.444.777-35")
    page.click('button:has-text("Assinar (loja)")')
    page.wait_for_selector("text=Assinatura registrada", timeout=10000)

    page.fill("#pe-ad-nome", "Cliente E2E")
    page.fill("#pe-ad-cpf", "111.444.777-35")
    page.click('button:has-text("Assinar (cliente)")')
    page.wait_for_selector("text=Forma de pagamento do aditivo", timeout=10000)
    page.click('[data-act="ok"]')
    page.wait_for_selector("text=✓ cliente", timeout=10000)

    # ── 8. Configura a integração ClickSign (loja) — nunca pela tela, é setup de teste ──────
    db = _sessao_teste()
    try:
        from integracoes import cripto_segredos
        loja = db.query(database.Loja).order_by(database.Loja.id).first()
        cfg = database.IntegracaoClickSign(loja_id=loja.id, ambiente_ativo="sandbox",
                                           token_sandbox_enc=cripto_segredos.encrypt("tok-e2e-falso"))
        db.add(cfg)
        db.commit()
    finally:
        db.bind.dispose()
        db.close()

    # ── 9. OPÇÃO 2 — canal ClickSign: nova rodada de renegociação, mesma tela ────────────────
    # A criação do orçamento de complemento da 2ª rodada não é o objeto deste teste — já é
    # clicada de verdade na 1ª rodada (passo 6) e não é o que o aceite 9 pede provar de novo.
    # POST direto (mesma sessão autenticada do navegador, via fetch na própria página) pelo
    # mesmo endpoint que "Definir forma de pagamento" aciona — ele já sabe criar um orçamento
    # NOVO quando o anterior tem aditivo assinado (POST /pe/complemento/orcamento, main.py).
    _seed_complemento(venda=184000.0, cfo=134000.0)   # incremento novo — 2ª rodada
    page.evaluate("""async () => {
        const r = await fetch(`/api/projetos/${encodeURIComponent(projetoAtivo.nome_safe)}/pe/complemento/orcamento`,
          {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: '{}'});
        const d = await r.json();
        if (!d.ok) throw new Error('setup da 2ª rodada falhou: ' + JSON.stringify(d));
    }""")
    page.evaluate("() => carregarCiclo()")
    ciclo.locator(".ficha-tab", has_text="Projeto executivo").first.click()
    page.wait_for_timeout(500)
    page.click("text=Aprovação do PE pelo cliente")
    page.click('button:has-text("Gerar novo Termo Aditivo")')
    # confirmarPopup() é a caixa própria do app (_popupOverlay/[data-act]) — NUNCA um dialog
    # nativo do navegador.
    page.wait_for_selector('[data-act="ok"]', timeout=5000)
    page.click('[data-act="ok"]')
    page.wait_for_selector("text=Novo termo aditivo gerado", timeout=10000)

    # A ESCOLHA — o próprio aceite 9: os dois botões, lado a lado, na mesma tela que o
    # ACHADO-25 já mostrou que precisa de prova por clique real.
    page.wait_for_selector('button:has-text("Assinar (loja)")', timeout=10000)
    page.wait_for_selector('button:has-text("Assinatura ClickSign")', timeout=10000)
    page.click('button:has-text("Assinatura ClickSign")')

    # ACHADO-21 6-c: o modal de forma de pagamento vem PRIMEIRO — não há outro instante síncrono
    # na conclusão remota pra perguntar isso.
    page.wait_for_selector("text=Forma de pagamento do aditivo", timeout=10000)
    page.click('[data-act="ok"]')

    page.wait_for_selector("#modal-clicksign-aditivo-confirmar", timeout=10000)
    page.fill("#csad-email-loja", "loja-e2e@exemplo.com")
    page.fill("#csad-email-cliente", "cliente-e2e@exemplo.com")
    page.click('#modal-clicksign-aditivo-confirmar [data-act="enviar"]')
    page.wait_for_selector("text=Termo aditivo enviado para assinatura eletrônica", timeout=10000)

    # O card tem que trocar pra caixa do ClickSign — nada de inputs de nome/CPF soltos enquanto
    # o canal for remoto.
    page.wait_for_selector('button:has-text("Verificar agora")', timeout=10000)
    page.wait_for_selector('button:has-text("Reenviar convite")', timeout=10000)
    assert page.locator("#pe-ad-nome").count() == 0, (
        "canal ClickSign não pode mostrar os inputs de assinatura interna")

    # ── 10. "Fecha" o envelope no servidor FALSO (sinal de conclusão — signed_at nunca vem
    #        preenchido na ClickSign real) e clica "Verificar agora" DE VERDADE ─────────────
    db = _sessao_teste()
    try:
        aditivo = (db.query(database.Aditivo).filter_by(projeto_nome=nome_projeto)
                     .order_by(database.Aditivo.id.desc()).first())
        envelope_id = aditivo.clicksign_envelope_id
    finally:
        db.bind.dispose()
        db.close()
    assert envelope_id, "envio pra ClickSign não gravou envelope_id"
    servidor_falso.estado.envelopes[envelope_id]["status"] = "closed"

    page.click('button:has-text("Verificar agora")')
    page.wait_for_selector("text=Assinado por todas as partes", timeout=10000)

    # ── 11. Postgres, fonte de verdade — o segundo aditivo está assinado pelo canal ClickSign
    db = _sessao_teste()
    try:
        aditivo = db.get(database.Aditivo, aditivo.id)
        status_final = aditivo.status
        canal_final = aditivo.assinatura_canal
    finally:
        db.bind.dispose()
        db.close()
    assert status_final == "assinado", status_final
    assert canal_final == "clicksign", canal_final
