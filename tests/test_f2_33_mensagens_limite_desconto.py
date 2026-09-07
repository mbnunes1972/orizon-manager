# -*- coding: utf-8 -*-
"""F2-33 — as caixas de aviso: texto (docs/db/ACHADOS_CONTABEIS.md).

DECIDIDO (Marcelo, 06/09): a mensagem de limite de desconto não cita comissão, fidelidade,
"efeito composto" nem percentual (esse número não aparece em nenhum outro lugar da tela — é um
terceiro dado que ninguém confere — e expõe a mecânica de comissão/fidelidade a quem está na
frente do cliente). Dois textos, escolhidos pelo teto ABSOLUTO (`perfis.desconto_max_absoluto()`
— o maior `desconto_max` entre os perfis de loja, hoje 50% de master, sem override por conta):
  - composto cabe no teto absoluto (existe QUEM pode autorizar):
      "Limite de desconto excedido. Autorização gerencial necessária."
  - composto excede o teto absoluto (NINGUÉM pode autorizar):
      "Limite máximo de desconto excedido." — sem falar em autorização.

NÃO MUDA: a regra de autorização, `_maior_desconto_efetivo_pct`, o step-up, o código 403 — só o
texto e a escolha entre os dois."""
import main


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


PALAVRAS_PROIBIDAS = ("comissão", "comissao", "fidelidade", "composto")


def _sem_palavras_proibidas(msg):
    baixo = msg.lower()
    return not any(p in baixo for p in PALAVRAS_PROIBIDAS)


def test_recusa_continua_acontecendo_com_a_mensagem_nova(http_client_factory, seed, app_db):
    """A trava em si (403 + requer_autorizacao + não persiste) é a mesma de sempre — só o texto
    muda. Mesma condição de test_margens_recusa_desconto_acima_do_limite_sem_autorizacao
    (test_desconto_autorizacao_e2e.py): operador (limite 10%) pedindo 25%."""
    c = _login(http_client_factory, "cons_l1")   # operador, limite 10%
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 25})
    assert st == 403
    assert body["requer_autorizacao"] is True
    assert body["limite"] == 10.0
    assert _sem_palavras_proibidas(body["erro"]), (
        "a mensagem não pode citar comissão/fidelidade/composto — achado: %r" % body["erro"])

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 25   # NÃO persistiu — a recusa é real, não só o texto
    db.close()


def test_mensagem_1_quando_existe_quem_autoriza(app_db):
    """25% excede o limite do operador (10%) mas cabe no teto absoluto (50%, master) —
    existe QUEM pode autorizar."""
    assert main._msg_limite_desconto_excedido(25.0) == (
        "Limite de desconto excedido. Autorização gerencial necessária.")


def test_mensagem_2_quando_ninguem_autoriza(app_db):
    """60% excede até o teto absoluto (50%, o maior limite entre os perfis de loja) —
    ninguém pode autorizar; a mensagem não pode oferecer um botão que nunca funciona."""
    msg = main._msg_limite_desconto_excedido(60.0)
    assert msg == "Limite máximo de desconto excedido."
    assert "autoriza" not in msg.lower()


def test_mensagem_2_via_api_acima_do_teto_absoluto(http_client_factory, seed, app_db):
    """Mesmo endpoint de sempre (/margens), agora pedindo 60% (acima do teto absoluto de 50%) —
    prova que o site real (não só a função isolada) escolhe a mensagem 2."""
    c = _login(http_client_factory, "cons_l1")
    oid = seed["orcamento_l1_id"]

    st, body = c.post(f"/api/orcamentos/{oid}/margens", {"desconto_pct": 60})
    assert st == 403
    assert body["requer_autorizacao"] is True
    assert body["erro"] == "Limite máximo de desconto excedido."
    assert _sem_palavras_proibidas(body["erro"])

    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    assert (orc.desconto_pct or 0) != 60
    db.close()


def test_no_limite_exato_do_teto_absoluto_ainda_e_mensagem_1(app_db):
    """Fronteira: exatamente 50% (o teto absoluto) ainda é "existe quem autoriza" (master cobre
    exatamente esse valor) — só ACIMA de 50% vira mensagem 2."""
    import auth.perfis as perfis
    teto = perfis.desconto_max_absoluto()
    assert teto == 50.0
    assert main._msg_limite_desconto_excedido(teto) == (
        "Limite de desconto excedido. Autorização gerencial necessária.")
    assert main._msg_limite_desconto_excedido(teto + 0.01) == "Limite máximo de desconto excedido."
