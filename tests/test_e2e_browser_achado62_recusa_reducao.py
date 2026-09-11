# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-34, ACHADO-62 — REVERTIDO de propósito pelo F2-39 (07/09).

Este arquivo provava a RECUSA da redução de Outros Fornecedores; agora prova o oposto — a
redução (e a devolução total) funcionam de verdade na TELA, não só na API. Ver o docstring de
`tests/test_achado62_recusa_reducao_out_forn.py` pro motivo completo da reversão (a separação do
Item Especial no F2-36 tirou a ambiguidade que motivava o bloqueio de 06/09).

Reproduz o percurso: no painel de Provisões (AF1), digitar Outros Fornecedores 3.000 (ok, lança),
depois 4.000 (ok, migra mais 1.000), depois 2.000 — agora ACEITO, migra de volta 2.000 pro Custo
de Fábrica. F2-39 Fatia 1 (mesma rodada): o campo ganhou máscara financeira
(`mascaraMoedaInput`/`parseMoeda`) — o valor abre como "R$ 4.000,00", não mais "4000.00".

Por que este teste TEM que ser de navegador: o critério de aceite inclui que a coluna Rev1
reflita o valor reduzido DE VERDADE na tela (não é só "o servidor devolveu 200" — é "o usuário vê
o valor novo, renderizado pelo fetch real no DOM") — isso só o motor do navegador prova.

ACHADO-68 (11/09, docs/db/TAREFA_ACHADO68_REAUTENTICACAO.md): a garantia de 25/08 — "aprovar_
financeiro SEMPRE pede senha de novo, mesmo pra quem já tem a capacidade" — foi invertida DE
PROPÓSITO por uma janela de 15min (pede uma vez, as ações financeiras seguintes na mesma sessão
não pedem mais). Mesmo padrão do F2-42 removendo `test_aceite_1_sombra_nao_muda_o_que_e_cobrado`
com o motivo escrito. Por isso as 3 submissões abaixo (3.000/4.000/2.000) agora esperam o modal
de credenciais SÓ na 1ª — a 2ª e a 3ª PROVAM a janela: o teste falha se o modal aparecer de novo
(sinal de que a janela quebrou) e falha se ele não aparecer na 1ª (sinal de que a janela está
vazando pra sessões/ações que nunca autenticaram)."""
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


def _seed_orcamento_com_cfo(loja_id, cfo=101446.51):
    """Cria Projeto+Orçamento e constitui o CFO no razão (sem passar pela tela — o objeto deste
    teste é o comportamento do AF1, não a criação do projeto)."""
    import database
    import mod_contabil as mc

    db = _sessao_teste()
    try:
        nome = "AF E2E Achado62"
        db.query(database.Projeto).filter_by(nome_safe=nome).delete()
        db.commit()
        db.add(database.Projeto(nome_safe=nome, loja_id=loja_id, status="vigente"))
        orc = database.Orcamento(projeto_id=nome, nome="Orçamento 1", ordem=1,
                                 desconto_pct=0.0, loja_id=loja_id, valor_total=0.0)
        db.add(orc)
        db.flush()
        oid = orc.id
        db.commit()

        ot, own = mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, own, nome, {"custo_fabrica": cfo},
                                           ref_base="pf:e2e-achado62")
        db.add(database.ProvisaoRegistro(orcamento_id=oid, versao="venda",
            itens_json='{"frete_fab":0.0,"com_adm":0.0,"com_venda":0.0,"com_med":0.0,'
                       '"com_proj_exec":0.0,"frete_loc":0.0,"assist":0.0,"ins_loc":0.0,'
                       '"prov_imp":0.0,"out_forn":0.0}',
            cfo=cfo, val_liq=0.0, cust_var=0.0, marg_cont=0.0, decisao="venda", por_id=1))
        db.commit()
        return oid
    finally:
        db.close()


def test_percurso_3000_4000_2000_a_reducao_e_aceita(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    loja_id = page.evaluate("() => _usuarioAtual.loja_id")
    oid = _seed_orcamento_com_cfo(loja_id)

    def _fechar_modal_se_existir():
        page.evaluate("() => { if (window._provModalOv) { window._provModalOv.remove(); "
                     "window._provModalOv = null; } }")

    def _abrir_e_revisar():
        _fechar_modal_se_existir()
        page.evaluate("(oid) => abrirProvisoes(oid, '8')", oid)
        page.wait_for_selector("#_prov-inp-out_forn", state="attached")
        page.evaluate("() => _provToggleRevisa()")

    def _fmt_brl(valor):
        # "3000" (dígitos crus, sem vírgula) -> "R$ 3.000" — mascaraMoedaInput só acrescenta
        # ",XX" quando o próprio texto digitado já tem vírgula (não insere centavos sozinha).
        inteiro = "{:,.0f}".format(valor).replace(",", ".")
        return "R$ " + inteiro

    def _submeter(valor, espera_modal):
        page.fill("#_prov-inp-out_forn", str(valor))
        # F2-39 Fatia 1: o oninput da máscara roda no fill — confirma o formato antes de submeter.
        assert page.input_value("#_prov-inp-out_forn") == _fmt_brl(valor)
        # _provAcao chama pedirCredenciaisGerente(capacidade:'aprovar_financeiro'). ACHADO-68:
        # só a 1ª ação financeira da sessão pede senha de verdade — as seguintes, dentro da
        # janela de 15min, não mostram modal nenhum (ver docstring do arquivo).
        page.evaluate("() => { _provAcao(%d, 'rev1', 'revisa'); }" % oid)
        if espera_modal:
            page.wait_for_selector("#_cred-login", state="visible")
            page.fill("#_cred-login", "e2e_master")
            page.fill("#_cred-senha", "senha123")
            page.click('[data-act="ok"]')
        else:
            # Prova POSITIVA da janela, não só "o teste passou por acaso": afirma que o modal
            # NÃO aparece — se a janela quebrar (deixar de cobrir), isto falha aqui, antes até
            # de qualquer asserção de negócio mais adiante.
            page.wait_for_timeout(300)
            assert page.locator("#_cred-login").count() == 0, (
                "modal de credenciais apareceu de novo dentro da janela de 15min do ACHADO-68 "
                "— a janela parou de cobrir esta ação")

    _abrir_e_revisar()
    # 3.000 → ok, 1ª ação financeira da sessão: modal aparece de verdade, abre a janela.
    _submeter(3000, espera_modal=True)
    page.wait_for_timeout(1200)   # await interno de _provAcao (fetch + reabertura do modal)

    _abrir_e_revisar()
    # 4.000 → ok, dentro da janela: SEM modal (prova a janela, não só tolera a ausência dela).
    _submeter(4000, espera_modal=False)
    page.wait_for_timeout(1200)

    _abrir_e_revisar()
    # 2.000 → F2-39: ACEITO agora (era recusado antes da reversão do ACHADO-62) — migra
    # 2.000 de volta pro Custo de Fábrica, sem erro na tela. Ainda dentro da janela: sem modal.
    _submeter(2000, espera_modal=False)
    page.wait_for_timeout(1200)
    assert page.query_selector("#_prov-erro") is None or page.inner_text("#_prov-erro") == ""
    assert page.query_selector("#erro-modal-overlay") is None

    # Rev1 PERSISTIDA reflete o valor REDUZIDO — reabre fresco pra confirmar que o servidor gravou.
    _abrir_e_revisar()
    valor_tela = page.input_value("#_prov-inp-out_forn")
    assert valor_tela == "R$ 2.000,00", valor_tela

    # confirma no razão: 2.1.04.14 == 2.000 (final); CFO congelado (101.446,51) menos o que
    # ainda está migrado (2.000) — invariante CFO_inicial - saldo(2.1.04.14) == saldo(2.1.04.06),
    # nenhum reconhecimento de NF-e no meio do caminho pra capar o espelho do ativo.
    db = _sessao_teste()
    try:
        import mod_contabil as mc
        ot, own = mc.resolver_owner(db, {"loja_id": loja_id, "rede_id": None})
        saldo_of = round(mc._mov(db, ot, own, "2.1.04.14", "credor", None, None,
                                 projeto_id="AF E2E Achado62"), 2)
        saldo_cfo = round(mc._mov(db, ot, own, "2.1.04.06", "credor", None, None,
                                  projeto_id="AF E2E Achado62"), 2)
        assert saldo_of == 2000.0
        assert saldo_cfo == 99446.51   # 101.446,51 - 2.000 (o que ficou migrado no final)
        assert round(saldo_of + saldo_cfo, 2) == 101446.51
    finally:
        db.close()
