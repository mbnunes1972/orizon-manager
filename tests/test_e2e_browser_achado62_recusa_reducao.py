# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-34, ACHADO-62 (docs/db/ACHADOS_CONTABEIS.md).

Reproduz o percurso exato do Marcelo em beta3: no painel de Provisões (AF1), digitar Outros
Fornecedores 3.000 (ok, lança), depois 4.000 (ok, migra mais 1.000), depois 2.000 (recusado —
Rev1 continua em 4.000, nenhum lançamento novo, texto simples na própria tela, sem popup de
erro nem caixa vermelha — ver F2-33).

Por que este teste TEM que ser de navegador: o critério de aceite inclui que a coluna Rev1 NÃO
mude na tela após a recusa (não é só "o servidor devolveu 400" — é "o usuário vê o valor
anterior, não o rejeitado") — isso só o motor do navegador, renderizando o retorno real do
fetch no DOM, prova.

Setup: cria Projeto/Orçamento/CFO diretamente por sessão de banco (mesma disciplina de
`_e2e_bootstrap.py` — sessão própria, guarda de banco antes de escrever) — a tela é dirigida
pelas MESMAS funções JS que um clique real usa (`abrirProvisoes`, `_provToggleRevisa`,
`_provAcao`), só pulando os ~6 passos de setup (briefing/ambiente/contrato) que não são o
objeto deste teste."""
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


def test_percurso_3000_4000_2000_recusado_na_tela(page, servidor_e2e):
    base = servidor_e2e
    page.goto(base + "/static/login.html")
    page.fill("#email", "e2e_master")
    page.fill("#senha", "senha123")
    page.click("#loginBtn")
    page.wait_for_url(base + "/")

    loja_id = page.evaluate("() => _usuarioAtual.loja_id")
    oid = _seed_orcamento_com_cfo(loja_id)

    def _fechar_modal_se_existir():
        # _provAcao, no SUCESSO, já remove o overlay antigo e reabre sozinho — fechar de novo
        # aqui é no-op nesse caso; no FRACASSO (recusa) o modal antigo fica, com o valor
        # rejeitado ainda digitado — fechar explicitamente evita duas cópias de #_prov-inp-*
        # no DOM ao reabrir manualmente.
        page.evaluate("() => { if (window._provModalOv) { window._provModalOv.remove(); "
                     "window._provModalOv = null; } }")

    def _abrir_e_revisar():
        _fechar_modal_se_existir()
        page.evaluate("(oid) => abrirProvisoes(oid, '8')", oid)
        page.wait_for_selector("#_prov-inp-out_forn", state="attached")
        page.evaluate("() => _provToggleRevisa()")

    def _submeter(valor):
        page.fill("#_prov-inp-out_forn", str(valor))
        # _provAcao chama pedirCredenciaisGerente(capacidade:'aprovar_financeiro') — essa
        # capacidade SEMPRE pede senha de novo (achado 2026-08-25, mesmo logado com a
        # permissão), então o modal de credenciais abre de verdade aqui.
        page.evaluate("() => { _provAcao(%d, 'rev1', 'revisa'); }" % oid)
        page.wait_for_selector("#_cred-login", state="visible")
        page.fill("#_cred-login", "e2e_master")
        page.fill("#_cred-senha", "senha123")
        page.click('[data-act="ok"]')

    _abrir_e_revisar()
    # 3.000 → ok (sucesso remove o modal velho e abre um novo sozinho)
    _submeter(3000)
    page.wait_for_timeout(1200)   # await interno de _provAcao (fetch + reabertura do modal)

    _abrir_e_revisar()
    # 4.000 → ok
    _submeter(4000)
    page.wait_for_timeout(1200)

    _abrir_e_revisar()
    # 2.000 → recusado (no fracasso o modal NÃO é trocado — o erro aparece na própria tela)
    _submeter(2000)
    page.wait_for_selector("text=reduzido", timeout=8000)
    erro = page.locator("#_prov-erro").inner_text()
    assert "reduzido" in erro and ("4000" in erro or "4.000" in erro or "4000.00" in erro), erro

    # nenhuma caixa de erro/popup — texto simples na própria tela (F2-33)
    assert page.query_selector("#erro-modal-overlay") is None

    # Rev1 PERSISTIDA continua em 4.000 — reabre fresco (fora do modal com o 2.000 rejeitado
    # ainda no input) pra confirmar que o servidor não gravou nada.
    _abrir_e_revisar()
    valor_tela = page.input_value("#_prov-inp-out_forn")
    assert valor_tela.replace(",", ".") in ("4000.00", "4000"), valor_tela
