# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-61 — REVERTIDO de propósito pelo F2-36 (ACHADO-65/66,
07/09). Histórico: o ACHADO-61 fazia `out_forn` (campo dos Parâmetros) constituir par próprio no
fechamento do contrato (1.1.06.14×2.1.04.14). O F2-35 reusou esse mesmo campo pro Item Especial
("markup 1"), e o F2-36 separou os dois conceitos de vez:

  - Item Especial (`item_especial`) — mercadoria de terceiro vendida NA VENDA, markup 1. Constitui
    par PRÓPRIO (1.1.06.22×2.1.04.22), nunca mexe no CFO. É o que este arquivo testa agora.
  - Outros Fornecedores (`out_forn`) — SUBSTITUIÇÃO do Custo de Fábrica, nasce só por
    reclassificação (etapa 12) ou migração da AF (ACHADO-59, `mod_contabil.disparar_deltas_af`),
    NUNCA no fechamento do contrato — a porta que o ACHADO-61 abriu fecha de volta (o campo dos
    Parâmetros que a alimentava na venda deixou de existir)."""
import mod_contabil as mc


def _saldo(db, ot, oid, codigo, nome):
    return round(mc._mov(db, ot, oid, codigo, "credor", None, None, projeto_id=nome), 2)


def _limpar(app_db, ot, owner_id, nome):
    """seed/app_db são module-scoped — sem isto, o teste de idempotência (mesmo projeto_l1)
    herdaria o lançamento do primeiro teste deste arquivo (regra dos irmãos, F2-29 Fatia D)."""
    db = app_db.get_session()
    db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=owner_id, projeto_id=nome).delete()
    db.commit(); db.close()


def test_item_especial_no_fechamento_constitui_par_proprio_sem_mexer_no_cfo(app_db, seed):
    import main

    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.valor_total = 5000.0
    orc.cfo = 10000.0
    orc.item_especial = 2000.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    assert _saldo(db, ot, owner_id, "2.1.04.22", nome) == 0.0
    assert _saldo(db, ot, owner_id, "1.1.06.22", nome) == 0.0
    assert _saldo(db, ot, owner_id, "2.1.04.14", nome) == 0.0

    main._fin_provisoes_venda_seguro(orc, nome, "f236:" + nome)
    db.close()

    db = app_db.get_session()
    saldo_prov_item_esp = _saldo(db, ot, owner_id, "2.1.04.22", nome)
    saldo_ativo_item_esp = mc._mov(db, ot, owner_id, "1.1.06.22", "devedor", None, None, projeto_id=nome)
    saldo_cfo = _saldo(db, ot, owner_id, "2.1.04.06", nome)
    saldo_outros_forn = _saldo(db, ot, owner_id, "2.1.04.14", nome)
    db.close()

    assert saldo_prov_item_esp == 2000.0, (
        "F2-36: item_especial tem que provisionar de verdade no fechamento, no par PRÓPRIO")
    assert round(saldo_ativo_item_esp, 2) == 2000.0
    # o CFO congelado tem que ficar EXATAMENTE no que foi constituído — Item Especial é ADITIVO
    # no contrato, nunca migra/reduz o Custo de Fábrica.
    assert saldo_cfo == 10000.0, "Item Especial no contrato não pode mexer no CFO"
    # Outros Fornecedores (2.1.04.14) fica ZERADO — não é mais essa a conta que nasce na venda.
    assert saldo_outros_forn == 0.0, "Item Especial não pode lançar em 2.1.04.14 (é outra conta)"
    _limpar(app_db, ot, owner_id, nome)


def test_item_especial_zero_nao_lanca(app_db, seed):
    import main

    oid = seed["orcamento_l2_id"]
    nome = seed["projeto_l2"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja2_id"]
    orc.valor_total = 3000.0
    orc.cfo = 1000.0
    orc.item_especial = 0.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja2_id"], "rede_id": None})
    main._fin_provisoes_venda_seguro(orc, nome, "f236-zero:" + nome)
    db.close()

    db = app_db.get_session()
    saldo = _saldo(db, ot, owner_id, "2.1.04.22", nome)
    db.close()
    assert saldo == 0.0, "item_especial == 0 não pode gerar lançamento nenhum em 2.1.04.22"


def test_item_especial_idempotente_por_ref(app_db, seed):
    import main

    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.valor_total = 5000.0
    orc.cfo = 10000.0
    orc.item_especial = 2000.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    ref_base = "f236-idemp:" + nome
    main._fin_provisoes_venda_seguro(orc, nome, ref_base)
    db.close()
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    main._fin_provisoes_venda_seguro(orc, nome, ref_base)
    db.close()

    db = app_db.get_session()
    saldo = _saldo(db, ot, owner_id, "2.1.04.22", nome)
    db.close()
    assert saldo == 2000.0, "rodar o wiring duas vezes com o mesmo ref_base não pode duplicar"
    _limpar(app_db, ot, owner_id, nome)


def test_out_forn_no_fechamento_nao_lanca_mais_a_porta_fechou(app_db, seed):
    """F2-36 (07/09, DECIDIDO): reverte o ACHADO-61 de propósito — o campo dos Parâmetros que
    alimentava `out_forn` na venda deixou de existir (virou Item Especial). Mesmo que
    `orc.out_forn` esteja (indevidamente) não-zero — resíduo de migração, por exemplo —, o
    fechamento do contrato NUNCA mais lança em 2.1.04.14; essa rubrica volta a nascer só por
    reclassificação (etapa 12) ou migração da AF (ACHADO-59)."""
    import main

    oid = seed["orcamento_l2_id"]
    nome = seed["projeto_l2"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja2_id"]
    orc.valor_total = 3000.0
    orc.cfo = 1000.0
    orc.out_forn = 2000.0   # não deveria acontecer pós-migration, mas a porta tem que estar fechada mesmo assim
    orc.item_especial = 0.0
    db.commit()

    ot, owner_id = mc.resolver_owner(db, {"loja_id": seed["loja2_id"], "rede_id": None})
    main._fin_provisoes_venda_seguro(orc, nome, "f236-porta-fechada:" + nome)
    db.close()

    db = app_db.get_session()
    saldo = _saldo(db, ot, owner_id, "2.1.04.14", nome)
    db.close()
    assert saldo == 0.0, "out_forn não pode mais nascer no fechamento do contrato — a porta fechou"
