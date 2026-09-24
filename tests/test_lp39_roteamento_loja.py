# -*- coding: utf-8 -*-
"""LP-39 passo 1 — QUEM RECEBEU decide a loja (docs/db/TAREFA_LP39_ROTEAMENTO.md).

Medido em campo três vezes (22/09 e 23/09): mensagem que chegou pelo número da loja A foi parar
em conversa/triagem da loja B, porque `_loja_da_entrada` colocava o cliente cadastrado ACIMA do
número que de fato recebeu, e porque `_rotear_com_candidatos` não filtrava candidatas por loja —
uma conversa antiga de outra loja vencia antes de qualquer decisão de loja.

As quatro provas da tarefa, uma por teste. Números distintos por teste: o `app_db` é por MÓDULO,
os testes deste arquivo compartilham o mesmo banco."""


def _num_conectado(app_db, db, loja_id, numero):
    """Deixa a instalação com EXATAMENTE um numero_conectado, o da loja pedida."""
    db.query(app_db.NumeroConectado).delete()
    db.flush()
    db.add(app_db.NumeroConectado(loja_id=loja_id, numero=numero, rotulo="teste LP-39"))
    db.commit()


def _sem_num_conectado(app_db, db):
    db.query(app_db.NumeroConectado).delete()
    db.commit()


# ── prova 1: cliente da loja B, entrada pelo número da loja A → loja A ───────────

def test_cliente_de_outra_loja_nao_rouba_a_entrada(app_db, seed):
    """O caso do Marcelo, medido três vezes: o telefone é de um Cliente cadastrado na loja 2,
    mas quem RECEBEU foi o número da loja 1 → a entrada é da loja 1."""
    import mod_chat_externo as ext
    db = app_db.get_session()
    cli2 = db.get(app_db.Cliente, seed["cliente_l2_id"])
    cli2.whatsapp = "(12) 90000-3301"
    db.commit()
    _num_conectado(app_db, db, seed["loja1_id"], "+55 12 99999-0001")

    assert ext._loja_da_entrada(db, remetente="(12) 90000-3301",
                                meio="whatsapp") == seed["loja1_id"]

    out = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-3301",
                                texto="oi", id_externo_ref=None, id_externo="wamid.LP39.1")
    db.commit()
    assert out["status"] == "triagem" and out["conversa_id"] is None
    ent = db.get(app_db.TriagemEntrada, out["triagem_id"])
    assert ent.loja_id == seed["loja1_id"]          # não a loja do cliente
    db.close()


# ── prova 2: conversa existente na loja B não captura entrada da loja A ──────────

def test_conversa_de_outra_loja_nao_captura(app_db, seed):
    """Conversa viva na loja 2 com aquele número; a mensagem chega pelo número da loja 1 →
    nasce TRIAGEM na loja 1. É o filtro de loja em `_rotear_com_candidatos` — sem ele a
    conversa antiga vence antes de qualquer decisão de loja (foi assim que a mensagem 113
    entrou na conversa 31 da loja 15 pelo número da loja 1)."""
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv2 = mod_chat.get_or_create_conversa_projeto(db, seed["loja2_id"], "Proj_L2"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv2, None, "msg loja 2", canal="comercial",
                                 _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", seed["cliente_l2_id"],
                        "(12) 90000-3302")
    db.commit()
    _num_conectado(app_db, db, seed["loja1_id"], "+55 12 99999-0001")

    # o roteamento sozinho, com a loja informada, não devolve a conversa da outra loja
    alvo = ext.rotear_entrada(db, "whatsapp", remetente="(12) 90000-3302",
                              loja_id=seed["loja1_id"])
    assert alvo is None

    out = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-3302",
                                texto="oi", id_externo_ref=None, id_externo="wamid.LP39.2")
    db.commit()
    assert out["status"] == "triagem" and out["conversa_id"] is None
    ent = db.get(app_db.TriagemEntrada, out["triagem_id"])
    assert ent.loja_id == seed["loja1_id"]
    # a conversa da loja 2 continua existindo — ela só deixou de ser o destino
    assert db.get(app_db.Conversa, conv2.id) is not None
    db.close()


# ── prova 3: conversa existente na MESMA loja continua recebendo ─────────────────

def test_conversa_da_mesma_loja_continua_recebendo(app_db, seed):
    """O filtro não pode criar conversa duplicada quando a loja bate."""
    import mod_chat_externo as ext, mod_chat
    db = app_db.get_session()
    conv1 = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_L1"); db.flush()
    m = mod_chat.enviar_mensagem(db, conv1, None, "msg loja 1", canal="comercial",
                                 _permitir_externo=True)
    ext.registrar_envio(db, m, "whatsapp", "comercial", "cliente", seed["cliente_l1_id"],
                        "(12) 90000-3303")
    db.commit()
    _num_conectado(app_db, db, seed["loja1_id"], "+55 12 99999-0001")

    out = ext.processar_entrada(db, "whatsapp", remetente="(12) 90000-3303",
                                texto="resposta", id_externo_ref=None, id_externo="wamid.LP39.3")
    db.commit()
    assert out["status"] == "roteado" and out["conversa_id"] == conv1.id
    db.close()


# ── prova 4: sem numero_conectado nenhum → comportamento de antes, intacto ───────

def test_sem_numero_conectado_mantem_comportamento_antigo(app_db, seed):
    """Instalação que ainda não conectou número: o cliente cadastrado volta a decidir — é o
    fallback explícito da tarefa, para não mudar quem não tem como saber quem recebeu."""
    import mod_chat_externo as ext
    db = app_db.get_session()
    cli2 = db.get(app_db.Cliente, seed["cliente_l2_id"])
    cli2.whatsapp = "(12) 90000-3304"
    db.commit()
    _sem_num_conectado(app_db, db)

    assert ext._loja_da_entrada(db, remetente="(12) 90000-3304",
                                meio="whatsapp") == seed["loja2_id"]
    db.close()
