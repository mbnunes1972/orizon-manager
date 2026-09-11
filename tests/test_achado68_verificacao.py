# -*- coding: utf-8 -*-
"""docs/db/TAREFA_ACHADO68_VERIFICACAO.md — as duas pontas soltas do ACHADO-68.

Ponta 1: a sessão emprestada morre no SERVIDOR (o token deixa de valer pra QUALQUER requisição),
não só na tela. Teste de integração via HTTP real (`http_client_factory`), não de navegador —
navegador prova que a tela navegou, não que o token morreu.

Usa `/api/recebiveis/<id>/reprogramar` como representante dos 15 pontos de `_aprovador_
financeiro` (grava `LogAcaoGerencial` explícito, tem um caminho de falha DEPOIS do aprovador e
ANTES da resposta de sucesso — útil pra medir o caminho triste)."""
import json
from datetime import date

import pytest

import mod_contabil as mc
from database import LogAcaoGerencial, Recebivel, get_session


def _criar_recebivel_com_saldo(app_db, seed, tag, valor=4000.0, data_prevista=None):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    mc.seed_plano(db, ot, oid)
    mc.registrar_evento(db, ot, oid, "registro_venda_contrato", valor, projeto_id=seed["projeto_l1"],
                        ref="venda:%s:%s" % (seed["projeto_l1"], tag))
    rec = app_db.Recebivel(loja_id=seed["loja1_id"], projeto_nome=seed["projeto_l1"],
                           orcamento_id=seed["orcamento_l1_id"], tipo="parcela", numero=1,
                           forma="pix", valor_previsto=valor,
                           data_prevista=data_prevista or date.today(), status="previsto",
                           ref="recv:achado68v:%s:%s" % (seed["projeto_l1"], tag))
    db.add(rec); db.commit()
    rid = rec.id
    db.close()
    return rid


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %r" % who
    return c


def test_ponta1_sessao_emprestada_morre_no_servidor_nao_so_na_tela(http_client_factory, seed, app_db):
    """O passo 4 do doc: repetir a MESMA requisição do passo 2 com o mesmo token T tem que
    devolver 401. Devolver 200 reprova — significaria que a invalidação existe só no frontend."""
    rid = _criar_recebivel_com_saldo(app_db, seed, "p1sucesso")

    # 1. Autentica cons_l1 (operador, SEM aprovar_financeiro). T = o cookie desta sessão.
    c = _login(http_client_factory, "cons_l1")

    # 2. T funciona: uma requisição autenticada qualquer devolve 200.
    st, d = c.get("/api/auth/me")
    assert st == 200 and d["ok"] is True, d

    # 3. Dispara a operação financeira com credenciais de dir_l1 (TEM a capacidade), dentro da
    # sessão de cons_l1 — sessão emprestada por definição — e deixa CONCLUIR.
    st2, d2 = c.post("/api/recebiveis/%d/reprogramar" % rid,
                     {"data_prevista": "2027-03-01", "login": "dir_l1", "senha": "senha123"})
    assert st2 == 200 and d2["ok"] is True, d2
    assert d2.get("sessao_encerrada") is True, (
        "a resposta tem que dizer que a sessão foi encerrada: %r" % d2)

    # 4. Repete A MESMA requisição do passo 2, com o MESMO T (mesmo cookie/token).
    st3, d3 = c.get("/api/auth/me")
    assert st3 == 401, (
        "sessão emprestada devolveu %d em vez de 401 — a invalidação existe só no frontend, "
        "não no servidor: %r" % (st3, d3))


def test_ponta1_log_grava_o_autorizador_nao_o_dono_da_sessao(http_client_factory, seed, app_db):
    """'A janela dispensa a digitação, nunca o registro de quem autorizou o quê.'"""
    rid = _criar_recebivel_com_saldo(app_db, seed, "p1log")
    c = _login(http_client_factory, "cons_l1")
    st, d = c.post("/api/recebiveis/%d/reprogramar" % rid,
                   {"data_prevista": "2027-03-01", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d["ok"] is True, d

    db = get_session()
    try:
        log = (db.query(LogAcaoGerencial)
               .filter_by(acao="reprogramar_recebivel")
               .order_by(LogAcaoGerencial.id.desc()).first())
        assert log is not None
        ctx = json.loads(log.contexto)
        assert ctx["recebivel_id"] == rid
        from database import Usuario
        cons_l1 = db.query(Usuario).filter_by(login="cons_l1").first()
        dir_l1 = db.query(Usuario).filter_by(login="dir_l1").first()
        assert log.solicitante_id == cons_l1.id, (
            "solicitante tem que ser quem estava logado (cons_l1), não quem autorizou")
        assert log.autorizador_id == dir_l1.id, (
            "autorizador tem que ser quem digitou a senha (dir_l1), não o dono da sessão "
            "(cons_l1) — a janela dispensa a digitação, nunca o registro de quem autorizou")
    finally:
        db.close()


def test_ponta1_medido_falha_no_meio_nao_mata_a_sessao_hoje(http_client_factory, seed, app_db):
    """MEDIÇÃO, não decisão (docs/db/TAREFA_ACHADO68_VERIFICACAO.md: 'meça o que o código faz
    hoje... e pergunte ao Marcelo se for diferente de sempre morre'). Comportamento ATUAL: a
    operação que FALHA depois do aprovador (aqui, data_prevista inválida — 400) NUNCA chega em
    `_resposta_pos_aprovacao_financeira` (só chamada na resposta de SUCESSO), então a sessão
    emprestada SOBREVIVE a uma falha no meio. Isto não é asserção de que está certo — é registro
    do que É, pra decisão do Marcelo (uma sessão que sobrevive ao erro pode ser porta aberta;
    uma que morre no meio de um erro pode prender o operador fora do sistema)."""
    rid = _criar_recebivel_com_saldo(app_db, seed, "p1falha")
    c = _login(http_client_factory, "cons_l1")

    st, d = c.get("/api/auth/me")
    assert st == 200

    # data_prevista vazia -> 400, DEPOIS do aprovador ter validado a credencial de dir_l1
    # (sessao_emprestada=True já teria sido calculado), mas ANTES de qualquer commit/resposta
    # de sucesso — _resposta_pos_aprovacao_financeira nunca roda neste caminho.
    st_falha, d_falha = c.post("/api/recebiveis/%d/reprogramar" % rid,
                               {"data_prevista": "", "login": "dir_l1", "senha": "senha123"})
    assert st_falha == 400 and d_falha["ok"] is False, d_falha
    assert "sessao_encerrada" not in d_falha

    st_depois, d_depois = c.get("/api/auth/me")
    assert st_depois == 200, (
        "MEDIDO: hoje a sessão emprestada SOBREVIVE a uma operação que falhou no meio "
        "(esperado 200, comportamento atual). Se isso for indesejado, é decisão do Marcelo, "
        "não dedução deste teste — ver Ponta 1 do TAREFA_ACHADO68_VERIFICACAO.md."
    )
