# -*- coding: utf-8 -*-
"""E2E de NAVEGADOR (Playwright) — F2-40 Fatia 2 (docs/db/ROTEIRO.md): o modal "Negociar
Complemento" virou a tela cheia do mockup — Desc.% por ambiente, coluna "A cobrar", totais no
rodapé (Diferença bruta/Desconto/Complemento), SEM campo de desconto global (o motor já neutraliza
d_orc pra orçamento de complemento). A faixa de pagamento NÃO foi duplicada dentro do modal — o
"Gerar Termo Aditivo" fica travado até `forma_pagamento` existir, com um caminho explícito
("Definir forma de pagamento") que ativa o mesmo orçamento na tela real (página 2, sidebar já
existente) para essa escolha, sem duplicar ~150 ids fixos."""
import json
import os
import socket
import subprocess
import sys
import time

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from tests.test_e2e_browser_remover_ciclo import (
    _criar_projeto_e_assinar_contrato, _marcar_concluidas,
)

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


def _seed_segundo_ambiente_e_complementos(nome_projeto):
    """1º ambiente (o do XML da UI, budget 140.000/order 100.000) ganha um xml_compl com venda
    MAIOR (diferença real, positiva). 2º ambiente (novo, criado direto no banco, vínculo com o
    MESMO orçamento contratado) ganha xml_compl IDÊNTICO ao seu próprio budget/order — a
    propriedade já provada em tests/test_complemento_pe_e2e.py: XML idêntico ⇒ diferença ZERO.
    Devolve (pid_real, pid_zero)."""
    import database
    db = _sessao_teste()
    try:
        # NÃO pegar "o 1º orçamento do projeto" — "Criar Projeto" pode deixar um "Orçamento 1"
        # vazio (draft) além do que a UI realmente negociou; o CONTRATADO de verdade é o que o
        # Contrato aponta (mesma fonte que _pe_fator_contexto usa: ct.orcamento_id).
        ct = (db.query(database.Contrato).filter_by(projeto_nome=nome_projeto)
                .order_by(database.Contrato.id.desc()).first())
        orc = db.get(database.Orcamento, ct.orcamento_id)
        pa1 = db.query(database.PoolAmbiente).filter_by(projeto_id=nome_projeto).order_by(
            database.PoolAmbiente.id.asc()).first()
        pa1.renegociar_pe = 1
        pid1 = pa1.id

        pa2 = database.PoolAmbiente(nome="Sala E2E", nome_exibicao="Sala E2E",
                                    xml_path="fake/sala_e2e.xml", ambientes_json="{}",
                                    projeto_id=nome_projeto, budget_total=40000.0, order_total=16000.0)
        db.add(pa2); db.flush()
        db.add(database.OrcamentoAmbiente(orcamento_id=orc.id, pool_ambiente_id=pa2.id, ordem=2))
        pa2.renegociar_pe = 1
        pid2 = pa2.id

        db.add(database.ArquivoPE(projeto_nome=nome_projeto, pool_ambiente_id=pid1,
                                  formato="xml_compl", valor_venda=154000.0, valor_atualizado=110000.0))
        db.add(database.ArquivoPE(projeto_nome=nome_projeto, pool_ambiente_id=pid2,
                                  formato="xml_compl", valor_venda=40000.0, valor_atualizado=16000.0))
        db.commit()
        return pid1, pid2
    finally:
        db.bind.dispose()
        db.close()


def _orcamento_complemento_id(nome_projeto):
    import database
    db = _sessao_teste()
    try:
        orc = (db.query(database.Orcamento)
                 .filter_by(projeto_id=nome_projeto, complemento_pe=1, parcela_id=None)
                 .order_by(database.Orcamento.id.desc()).first())
        return orc.id if orc else None
    finally:
        db.bind.dispose()
        db.close()


def test_modal_complemento_desc_pct_totais_e_travamento_por_pagamento(page, servidor_e2e):
    base = servidor_e2e
    page_errs = []
    page.on("pageerror", lambda exc: page_errs.append(str(exc)))

    nome = _criar_projeto_e_assinar_contrato(page, base, "E2E F2-40 Fatia2 Modal")
    _marcar_concluidas(nome, ["8", "9", "10", "11", "11a", "11b", "11c", "11d"])
    pid_real, pid_zero = _seed_segundo_ambiente_e_complementos(nome)

    page.evaluate("async () => { await carregarCiclo(); }")
    page.evaluate("() => { _fichaSelecionar('11e'); }")
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    page.click('button:has-text("Negociar Complemento")')

    # NUNCA usar seletor page-wide para "Gerar Termo Aditivo": o card por trás do modal (bloco
    # "Termo Aditivo" de peComplementoRender) tem SUA PRÓPRIA cópia do mesmo texto — sempre
    # escopar em `modal`/`corpo`.
    modal = page.locator("#modal-pe-compl")
    modal.wait_for(state="visible", timeout=10000)
    corpo = page.locator("#pe-compl-modal-body")
    corpo.locator('button:has-text("Gerar Termo Aditivo")').wait_for(state="visible", timeout=10000)

    # ── SEM campo de desconto global no modal — só por ambiente ───────────────────────────────
    assert corpo.locator("#neg-desconto").count() == 0
    assert "desconto global" not in corpo.inner_text().lower()

    # ── Linha com diferença ZERO: "—"/sem input de Desc.%, excluída dos totais ────────────────
    assert "Sala E2E" in corpo.inner_text()
    linha_zero = corpo.locator("tr", has_text="Sala E2E")
    assert linha_zero.locator('input[type="number"]').count() == 0, (
        "linha de diferença zero não pode ter input de Desc.% habilitado")

    # ── Linha com diferença real: input de Desc.% existe, editável ────────────────────────────
    linha_real = corpo.locator("tr", has_text="e2e_a58_ambiente")
    input_desc = linha_real.locator('input[type="number"]')
    assert input_desc.count() == 1, "linha com diferença real tem que ter o input de Desc.%"
    assert "Diferença bruta" in corpo.inner_text() and "Complemento" in corpo.inner_text()

    # ── Muda Desc.% pra 10 — "A cobrar" da linha e o total "Complemento" têm que recalcular ────
    input_desc.fill("10")
    input_desc.dispatch_event("change")
    page.wait_for_timeout(300)
    # diferença real: 154.000 − 140.000 = 14.000 (fator 1, sem custo adicional configurado);
    # 10% de desconto ⇒ A cobrar = 12.600,00
    assert "12.600,00" in corpo.inner_text(), (
        "A cobrar/Complemento tem que refletir os 10% de desconto sobre a diferença — texto atual:\n"
        + corpo.inner_text())

    # ── "Gerar Termo Aditivo" travado: sem forma_pagamento ainda ──────────────────────────────
    btn_gerar = corpo.locator('button:has-text("Gerar Termo Aditivo")')
    assert btn_gerar.is_disabled(), "sem forma de pagamento definida, o botão tem que estar travado"
    assert "não definida" in corpo.inner_text().lower() or "definir forma de pagamento" in corpo.inner_text().lower()

    # ── Handoff: "Definir forma de pagamento" ativa o MESMO orçamento na tela real (pág. 2) ────
    orc_id_esperado = _orcamento_complemento_id(nome)
    assert orc_id_esperado is not None
    corpo.locator('button:has-text("Definir forma de pagamento")').click()
    page.wait_for_selector("#neg-desconto", timeout=10000)
    page.wait_for_timeout(500)
    orc_ativo = page.evaluate("() => _orcamentoAtivoId")
    assert orc_ativo == orc_id_esperado, (
        "o handoff tem que ativar o MESMO orçamento de complemento na tela de negociação — "
        "esperado %r, ativo %r" % (orc_id_esperado, orc_ativo))

    # Salva o plano à vista (default de um complemento recém-ativado) pela tela REAL —
    # nenhum cálculo novo, é o mesmo botão/rota que qualquer orçamento usa.
    page.click("#btn-salvar-orcamento")
    page.wait_for_selector("text=Orçamento salvo", timeout=10000)

    # ── Achado ao ligar este handoff (F2-40): atualizarBotoesAprovacao() escondia Salvar pra
    # QUALQUER orçamento pós-assinatura sem checar _orcamentoComplementoAtivo() — só
    # _aplicarLockNegociacaoPosAssinatura() checava, e ativarOrcamento() só chama esse helper,
    # nunca a função inteira. Conserto: o toggle de Salvar/Aprovar entrou no helper único. Prova
    # ida E volta (mesma classe de regressão que o "QA Vera" já tinha pego uma vez).
    outros_orcs = page.evaluate("() => (_orcamentos||[]).filter(o => !o.complemento_pe).map(o => o.id)")
    assert outros_orcs, "precisa existir o orçamento CONTRATADO pra testar a troca"
    orc_contratado = outros_orcs[0]
    page.evaluate("(id) => ativarOrcamento(id)", orc_contratado)
    page.wait_for_timeout(300)
    assert page.locator("#btn-salvar-orcamento").is_hidden(), (
        "orçamento CONTRATADO com contrato assinado: Salvar tem que ficar escondido")
    page.evaluate("(id) => ativarOrcamento(id)", orc_id_esperado)
    page.wait_for_timeout(300)
    assert page.locator("#btn-salvar-orcamento").is_visible(), (
        "voltar pro COMPLEMENTO tem que reexibir Salvar — não pode ficar 'travado' escondido")
    assert page.locator("#btn-aprovar-orcamento").is_hidden(), (
        "Aprovar continua escondido pro complemento — ele não se 'aprova', vira Termo Aditivo")

    db_check = _sessao_teste()
    try:
        import database
        orc_row = db_check.get(database.Orcamento, orc_id_esperado)
        assert orc_row.forma_pagamento, "salvarOrcamento tinha que ter persistido forma_pagamento"
    finally:
        db_check.bind.dispose(); db_check.close()

    # ── Volta pro ciclo, reabre a 11e e o modal — "Gerar Termo Aditivo" agora liberado ─────────
    page.evaluate("() => { abrirCiclo(); }")
    ciclo = page.locator("#ciclo-panel")
    ciclo.wait_for(state="visible", timeout=10000)
    page.evaluate("() => { _fichaSelecionar('11e'); }")
    page.wait_for_selector('button:has-text("Negociar Complemento")', timeout=10000)
    page.click('button:has-text("Negociar Complemento")')
    modal.wait_for(state="visible", timeout=10000)
    corpo.locator('button:has-text("Gerar Termo Aditivo"):not([disabled])').wait_for(
        state="visible", timeout=10000)
    assert "definida" in corpo.inner_text().lower() or "à vista" in corpo.inner_text().lower() or \
           "forma de pagamento" in corpo.inner_text().lower()

    # Reaplica o desconto de 10% (o estado do modal não sobrevive ao fechar/reabrir — é intencional,
    # os descontos só ficam persistidos no servidor depois de salvos por este próprio fluxo).
    linha_real = corpo.locator("tr", has_text="e2e_a58_ambiente")
    linha_real.locator('input[type="number"]').fill("10")
    linha_real.locator('input[type="number"]').dispatch_event("change")
    page.wait_for_timeout(300)

    corpo.locator('button:has-text("Gerar Termo Aditivo")').click()
    page.wait_for_selector("text=Termo aditivo gerado", timeout=10000)
    assert modal.is_hidden(), "o modal tem que fechar após gerar o aditivo"

    db_final = _sessao_teste()
    try:
        import database
        aditivo = (db_final.query(database.Aditivo).filter_by(orcamento_complemento_id=orc_id_esperado)
                    .order_by(database.Aditivo.id.desc()).first())
        assert aditivo is not None, "o aditivo tem que ter sido criado apontando pro complemento certo"
        dados = json.loads(aditivo.dados_json)
        # As DUAS linhas entram (vínculos — resync incondicional, docs/db/TAREFA_F2_40_RESET_
        # COMPLEMENTO.md): Cozinha com a diferença real (menos os 10% de desconto) e Sala E2E
        # com diferença zero (VBVA=0) — "excluída dos totais" é sobre A CIFRA ser zero, não
        # sobre o vínculo desaparecer do aditivo.
        assert len(dados["ambientes"]) == 2, dados["ambientes"]
        por_amb = {a["pool_ambiente_id"]: a for a in dados["ambientes"]}
        assert abs(por_amb[pid_zero]["diferenca"]) < 0.01, por_amb[pid_zero]
        assert abs(por_amb[pid_real]["diferenca"] - 12600.0) < 0.05, por_amb[pid_real]
    finally:
        db_final.bind.dispose(); db_final.close()

    assert page_errs == [], "erro de JS durante o percurso: %r" % page_errs
