# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-39, Fatias 1 e 2 (Marcelo, 07/09).

Fatia 1: os campos do painel da Aprovação Financeira ganham formato financeiro
(`mascaraMoedaInput`/`parseMoeda`, já existentes — nenhuma máscara nova). Fatia 2: o Item
Especial (ACHADO-65/66) ganha linha no painel — read-only, "Atual" mostra o saldo vivo de
2.1.04.22.

Por que este teste TEM que ser de navegador: o critério de aceite exige que a máscara formate AO
VIVO no `oninput` (não só que o backend receba o número certo) e que o campo read-only do Item
Especial apareça desabilitado — só o DOM real prova as duas coisas."""
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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


def _seed_orcamento_com_item_especial(loja_id, cfo=100000.0, item_especial=4000.0):
    """Projeto+Orçamento com CFO constituído e Item Especial já lançado (par 1.1.06.22/2.1.04.22),
    como se o contrato já tivesse sido assinado com o item — sem passar pela tela de negociação,
    o objeto deste teste é o painel da AF."""
    import database
    import mod_contabil as mc

    db = _sessao_teste()
    try:
        nome = "AF E2E F2-39"
        db.query(database.Projeto).filter_by(nome_safe=nome).delete()
        db.commit()
        db.add(database.Projeto(nome_safe=nome, loja_id=loja_id, status="vigente"))
        orc = database.Orcamento(projeto_id=nome, nome="Orçamento 1", ordem=1,
                                 desconto_pct=0.0, loja_id=loja_id, valor_total=0.0,
                                 item_especial=item_especial)
        db.add(orc)
        db.flush()
        oid = orc.id
        db.commit()

        ot, own = mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
        # Constitui direto (sem passar por `_fin_provisoes_venda_seguro`, que exige o módulo
        # "financeiro" ativo na loja — achado ao investigar: a loja do bootstrap do e2e não tem
        # esse módulo ligado, e a função é fail-soft/silenciosa — mesmo padrão de
        # `_seed_orcamento_com_cfo` no teste-irmão do ACHADO-62, que já constituía o CFO assim).
        mc.constituir_provisoes_fechamento(db, ot, own, nome,
                                           {"custo_fabrica": cfo, "item_especial": item_especial},
                                           ref_base="pf:e2e-f239")
        db.add(database.ProvisaoRegistro(orcamento_id=oid, versao="venda",
            itens_json='{"frete_fab":0.0,"com_adm":0.0,"com_venda":0.0,"com_med":0.0,'
                       '"com_proj_exec":0.0,"frete_loc":0.0,"assist":0.0,"ins_loc":0.0,'
                       '"prov_imp":0.0,"out_forn":0.0,"item_especial":%.2f}' % item_especial,
            cfo=cfo, val_liq=0.0, cust_var=cfo + item_especial, marg_cont=0.0,
            decisao="venda", por_id=1))
        db.commit()
        return oid, nome
    finally:
        db.close()


def test_mascara_financeira_e_item_especial_no_painel_da_af(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    loja_id = page.evaluate("() => _usuarioAtual.loja_id")
    oid, nome = _seed_orcamento_com_item_especial(loja_id)

    page.evaluate("(oid) => abrirProvisoes(oid, '8')", oid)
    page.wait_for_selector("#_prov-inp-out_forn", state="attached")

    # ── Fatia 2: a linha "Item Especial" aparece na tabela Venda|Atual, com o saldo vivo ───────
    linha_item_esp = page.locator("tr", has_text="Item Especial")
    assert linha_item_esp.count() >= 1
    assert "4.000,00" in linha_item_esp.first.inner_text()

    page.evaluate("() => _provToggleRevisa()")

    # ── Fatia 2: o campo do Item Especial no formulário de revisão é read-only e formatado ────
    inp_item_esp = page.locator("#_prov-inp-item_especial")
    assert inp_item_esp.is_disabled()
    assert inp_item_esp.input_value() == "R$ 4.000,00"

    # ── Fatia 1: os read-only (Custo de Fábrica, Item Especial) exibem formatado ───────────────
    inp_cfo = page.locator("#_prov-inp-custo_fabrica")
    assert inp_cfo.is_disabled()
    assert inp_cfo.input_value() == "R$ 100.000,00"

    # ── Fatia 1: máscara ao vivo, milhar não vira decimal (12345,67) ───────────────────────────
    page.fill("#_prov-inp-frete_fab", "12345,67")
    assert page.input_value("#_prov-inp-frete_fab") == "R$ 12.345,67"

    # ── Fatia 1: campo vazio continua gravando 0 (mascaraMoedaInput normaliza pra "R$ 0" sozinha
    # — mesmo fallback já medido no F2-38; parseMoeda("R$ 0") == 0, idêntico ao "" de antes) ────
    page.fill("#_prov-inp-com_adm", "")
    assert page.input_value("#_prov-inp-com_adm") == "R$ 0"

    # ── Aprova (concorda — não editar out_forn/item_especial) e confere: Cust_Var idêntico ao
    # esperado, e 2.1.04.22 (Item Especial) NÃO recebe lançamento nenhum pela AF ────────────────
    page.evaluate("() => { _provAcao(%d, 'rev1', 'concorda'); }" % oid)
    page.wait_for_selector("#_cred-login", state="visible")
    page.fill("#_cred-login", "e2e_master")
    page.fill("#_cred-senha", "senha123")
    page.click('[data-act="ok"]')
    page.wait_for_timeout(1200)

    db = _sessao_teste()
    try:
        import mod_contabil as mc
        ot, own = mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
        saldo_item_esp = round(mc._mov(db, ot, own, "2.1.04.22", "credor", None, None,
                                       projeto_id=nome), 2)
        assert saldo_item_esp == 4000.0, "Item Especial não pode se mover por causa da AF (concorda)"
    finally:
        db.close()
