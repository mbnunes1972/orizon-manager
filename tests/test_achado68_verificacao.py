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


def test_adendo_item4_sessao_emprestada_nao_ganha_a_janela_de_15min(http_client_factory, seed, app_db):
    """ADENDO (docs/db/TAREFA_ACHADO68_VERIFICACAO.md): 'se a sessão emprestada ganhar a janela,
    isso é defeito independente e MAIS URGENTE — seriam 15 minutos de elevação nas mãos de quem
    não tem a capacidade.' Medição de ponta a ponta (HTTP, não a chamada direta da função):
    a resposta de uma operação por sessão emprestada nunca traz o campo que indicaria janela
    aberta, e o dict interno de janelas nunca ganha entrada para este token."""
    import main
    rid = _criar_recebivel_com_saldo(app_db, seed, "adendo4")
    c = _login(http_client_factory, "cons_l1")
    token_antes = dict(main._STEPUP_GRANTS)

    st, d = c.post("/api/recebiveis/%d/reprogramar" % rid,
                   {"data_prevista": "2027-03-01", "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and d["ok"] is True, d
    assert d.get("sessao_encerrada") is True

    assert "janela_aprovar_financeiro_expira_em_ms" not in d, (
        "a resposta de uma sessão emprestada NUNCA pode sinalizar janela aberta: %r" % d)
    # Nenhuma entrada NOVA em _STEPUP_GRANTS depois da operação (a única mudança aceitável seria
    # a limpeza feita por _stepup_revogar_todos ao encerrar a sessão — nunca uma concessão nova).
    novas_chaves = set(main._STEPUP_GRANTS) - set(token_antes)
    assert not novas_chaves, (
        "sessão emprestada abriu janela de verdade no dict interno — defeito grave, "
        "independente da decisão do adendo: %r" % novas_chaves)


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


def test_adendo_item1_sessao_emprestada_morre_em_falha_pos_aprovador(http_client_factory, seed, app_db):
    """ADENDO (docs/db/TAREFA_ACHADO68_VERIFICACAO.md), decisão de 11/09: 'a sessão emprestada
    termina quando o ato de autorização termina, qualquer que seja o desfecho — conclusão, falha
    ou cancelamento'. Prova via /duvidoso, que NÃO foi reordenado (ao contrário de /reprogramar,
    ver item 3): ele chama `_aprovador_financeiro` ANTES de checar `rec.status == 'previsto'`,
    então um recebível fora desse estado produz um 409 genuíno DEPOIS de a credencial já ter
    sido gasta — o mesmo 401 da Ponta 1, por outro caminho."""
    rid = _criar_recebivel_com_saldo(app_db, seed, "adendo1")
    # Estado inválido pra /duvidoso, direto no banco — sem passar pelo endpoint (que gastaria
    # a credencial de propósito só pra chegar aqui e não mediria nada de novo).
    db = get_session()
    try:
        rec = db.get(Recebivel, rid)
        rec.status = "confirmado"
        db.commit()
    finally:
        db.close()

    c = _login(http_client_factory, "cons_l1")
    st, d = c.get("/api/auth/me")
    assert st == 200

    st_falha, d_falha = c.post("/api/recebiveis/%d/duvidoso" % rid,
                               {"login": "dir_l1", "senha": "senha123"})
    assert st_falha == 409 and d_falha["ok"] is False, d_falha
    assert "sessao_encerrada" not in d_falha

    st_depois, d_depois = c.get("/api/auth/me")
    assert st_depois == 401, (
        "ADENDO: a sessão emprestada tem que morrer mesmo quando a operação falha depois do "
        "aprovador — mesma regra do sucesso, sem ramificação por tipo de erro: %r" % d_depois)


def test_adendo_item2_sessao_emprestada_morre_em_excecao_no_confirmar(http_client_factory, seed, app_db, monkeypatch):
    """ADENDO item 2: teste equivalente ao item 1, mas para o 'cancelamento' — aqui, uma exceção
    genuína no meio da operação (banco/integração fora do ar), não uma falha de regra de negócio.
    /confirmar não tem try/except em volta de `mod_contabil.registrar_recebimento_venda`, e
    `do_POST` não tem wrapper global de exceção (medido: a exceção propaga até o `http.server`,
    que fecha a conexão sem resposta HTTP limpa — RemoteDisconnected/ConnectionResetError, ambos
    OSError). Mas o `finally:` do endpoint roda do mesmo jeito — semântica normal de exceção em
    Python, sem fronteira de thread/processo entre o `elif` e quem o chama — e é ele que mata a
    sessão emprestada. O teste prova isso: a conexão quebra sem status HTTP, e mesmo assim a
    PRÓXIMA requisição com o mesmo cookie já está morta."""
    def _explode(*a, **kw):
        raise RuntimeError("falha forçada — ADENDO item 2 (banco/integração fora do ar)")

    monkeypatch.setattr(mc, "registrar_recebimento_venda", _explode)

    rid = _criar_recebivel_com_saldo(app_db, seed, "adendo2")
    c = _login(http_client_factory, "cons_l1")
    st, d = c.get("/api/auth/me")
    assert st == 200

    try:
        c.post("/api/recebiveis/%d/confirmar" % rid, {"login": "dir_l1", "senha": "senha123"})
    except OSError:
        # Esperado: sem wrapper global de exceção, o handler morre no meio e a conexão fecha
        # sem resposta HTTP limpa — o que importa aqui não é a resposta, é o que sobra da sessão.
        pass

    st_depois, d_depois = c.get("/api/auth/me")
    assert st_depois == 401, (
        "ADENDO: a sessão emprestada tem que morrer mesmo quando a operação quebra com uma "
        "exceção genuína no meio — o `finally:` do endpoint é quem garante isso: %r" % d_depois)


def test_adendo_item3_validacao_antes_da_senha_no_reprogramar(http_client_factory, seed, app_db, monkeypatch):
    """ADENDO item 3: ao menos uma operação reordenada — validação completa ANTES do pedido de
    credenciais. /reprogramar foi a escolhida (era a que motivou a dúvida original: data_prevista
    vazia). Prova: entrada inválida é recusada com 400 SEM NUNCA chamar `_aprovador_financeiro`
    — nem login nem senha vão no corpo, e mesmo assim a validação dispara primeiro (se a ordem
    antiga ainda estivesse em vigor, a ausência de credencial teria produzido 403, não 400)."""
    import main
    chamadas = []
    original = main._aprovador_financeiro

    def _espiao(*a, **kw):
        chamadas.append((a, kw))
        return original(*a, **kw)

    monkeypatch.setattr(main, "_aprovador_financeiro", _espiao)

    rid = _criar_recebivel_com_saldo(app_db, seed, "adendo3")
    c = _login(http_client_factory, "cons_l1")

    st, d = c.post("/api/recebiveis/%d/reprogramar" % rid, {"data_prevista": ""})
    assert st == 400 and d["ok"] is False, d
    assert not chamadas, (
        "a credencial foi checada ANTES da validação — a senha seria gasta num pedido que já "
        "ia falhar por motivo alheio à aprovação: %r" % chamadas)
