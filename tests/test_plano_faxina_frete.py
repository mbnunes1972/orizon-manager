# -*- coding: utf-8 -*-
"""Faxina do plano (decisões do usuário, 2026-07-22, Sessões 107–108): cada rubrica de despesa
tem UMA conta — a da família 5.6 — porque a despesa "sair de um processamento contábil de
provisão ou ocorrer de um fato direto não muda o teor contábil". As duplicatas mortas no motor
saem do seed (5.1.02 Frete Fábrica, 5.2.01 Montagem, 5.2.08 Frete Local, 5.2.09 Insumos) e a
família 5.6 fica com o nome PURO da rubrica (sem "Constituição —" nem "— Despesa Reconhecida").
Migração idempotente cobre os DOIS estados históricos de nome (seed original e o da S107)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_contabil as mc

DUPES = ("5.1.02", "5.2.01", "5.2.08", "5.2.09")


def test_seed_novo_sem_duplicatas_e_nomes_puros(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 900)
    contas = {c.codigo: c for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=900).all()}
    db.close()
    for cod in DUPES:
        assert cod not in contas, cod                   # duplicatas não nascem mais
    assert "5.1.01" in contas and "5.2.02" in contas    # vizinhas intactas
    assert contas["5.6"].nome == "Despesas de Provisões"
    assert contas["5.6.02"].nome == "Montagem"
    assert contas["5.6.04"].nome == "Frete de Fábrica"
    assert contas["5.6.05"].nome == "Frete Local"
    assert contas["5.6.06"].nome == "Insumos Locais"
    assert contas["5.6.10"].nome == "Ajuste de Provisões"   # fora da faxina


def _restaurar_estado(db, oid, geracao):
    """Simula um owner nos estados históricos: geracao=0 (seed ORIGINAL, 'Constituição — …' +
    4 duplicatas) ou geracao=1 (estado pós-S107: '… — Despesa Reconhecida' + só as 3 do 5.2)."""
    mc.seed_plano(db, "loja", oid)
    pais = {c.codigo: c for c in db.query(mc.Conta)
            .filter_by(owner_tipo="loja", owner_id=oid).all()}
    dupes = {"5.1.02": ("Frete Fábrica", "5.1"), "5.2.01": ("Montagem", "5.2"),
             "5.2.08": ("Frete Local", "5.2"), "5.2.09": ("Insumos", "5.2")}
    for cod, (nome, pai) in dupes.items():
        if geracao == 1 and cod == "5.1.02":
            continue                                    # a S107 já a removeu
        db.add(mc.Conta(owner_tipo="loja", owner_id=oid, codigo=cod, nome=nome,
                        grupo=5, tipo="analitica", natureza="devedora",
                        pai_id=pais[pai].id, ativa=1, ordem=999))
    for cod, (antigos, _novo) in mc._RENOMES_5_6.items():
        c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first()
        c.nome = antigos[geracao]
    db.commit()


def test_migracao_do_seed_original(app_db):
    db = app_db.get_session()
    _restaurar_estado(db, 901, geracao=0)
    out = mc.migrar_plano_faxina_frete(db)
    assert out["removidas"] >= 4
    contas = {c.codigo: c.nome for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=901).all()}
    for cod in DUPES:
        assert cod not in contas, cod
    assert contas["5.6"] == "Despesas de Provisões"
    assert contas["5.6.04"] == "Frete de Fábrica"
    # idempotente
    out2 = mc.migrar_plano_faxina_frete(db)
    assert out2["removidas"] == 0 and out2["renomeadas"] == 0
    db.close()


def test_migracao_do_estado_s107(app_db):
    """Bases que já rodaram a S107 ('… — Despesa Reconhecida') também chegam ao nome puro."""
    db = app_db.get_session()
    _restaurar_estado(db, 904, geracao=1)
    mc.migrar_plano_faxina_frete(db)
    contas = {c.codigo: c.nome for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=904).all()}
    for cod in ("5.2.01", "5.2.08", "5.2.09"):
        assert cod not in contas, cod
    assert contas["5.6"] == "Despesas de Provisões"
    assert contas["5.6.02"] == "Montagem"
    assert contas["5.6.09"] == "Retenção de Comissão de Vendas"
    db.close()


def test_migracao_dupe_com_movimento_desativa_em_vez_de_apagar(app_db):
    db = app_db.get_session()
    _restaurar_estado(db, 902, geracao=0)
    c5201 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="5.2.01").first()
    caixa = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="1.1.01").first()
    mc.lancar(db, "loja", 902, c5201.id, caixa.id, 100.0, historico="montagem lançada à mão")
    mc.migrar_plano_faxina_frete(db)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="5.2.01").first()
    assert c is not None and not c.ativa            # histórico preservado, conta desativada
    assert db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902,
                                        codigo="5.1.02").first() is None  # sem movimento: some
    db.close()


def test_migracao_preserva_nome_customizado(app_db):
    db = app_db.get_session()
    _restaurar_estado(db, 903, geracao=0)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=903, codigo="5.6.05").first()
    c.nome = "Frete Local da Minha Loja"            # usuário renomeou no painel
    db.commit()
    mc.migrar_plano_faxina_frete(db)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=903, codigo="5.6.05").first()
    assert c.nome == "Frete Local da Minha Loja"    # migração não sobrescreve
    db.close()


def test_eventos_seguem_nas_mesmas_contas(app_db):
    """O motor não muda: reconhecimento na NF-e segue na família 5.6 × baixa do ativo 1.1.06."""
    ev = mc.EVENTOS["reconhecimento_despesa_frete_fabrica"]
    assert ev[0] == "5.6.04" and ev[1] == "1.1.06.07"
    ev = mc.EVENTOS["reconhecimento_despesa_frete_local"]
    assert ev[0] == "5.6.05" and ev[1] == "1.1.06.08"
