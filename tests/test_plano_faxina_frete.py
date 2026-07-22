# -*- coding: utf-8 -*-
"""Faxina do plano (decisão do usuário, 2026-07-22): a 5.1.02 "Frete Fábrica" sai do seed —
nenhum evento do motor a usa e ela convidava ao lançamento manual DUPLICADO (a despesa do
frete de fábrica nasce SEMPRE na 5.6.04, no matching da NF-e). A família 5.6.0X perde o
"Constituição —" do nome: desde a FASE D2 o que cai nela é o RECONHECIMENTO da despesa
(a constituição virou ativo diferido, sem DRE). Migração idempotente para planos antigos."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_contabil as mc


def test_seed_novo_sem_5102_e_nomes_novos(app_db):
    db = app_db.get_session()
    mc.seed_plano(db, "loja", 900)
    contas = {c.codigo: c for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=900).all()}
    db.close()
    assert "5.1.02" not in contas                       # Frete Fábrica não nasce mais
    assert "5.1.01" in contas                           # CMV Fábrica intacto
    assert contas["5.6"].nome == "Despesas Reconhecidas de Provisões"
    assert contas["5.6.04"].nome == "Frete de Fábrica — Despesa Reconhecida"
    assert contas["5.6.09"].nome == "Retenção de Comissão de Vendas — Despesa Reconhecida"
    assert contas["5.6.10"].nome == "Ajuste de Provisões"   # fora da faxina


def _plano_antigo(db, oid):
    """Simula um owner com o plano ANTERIOR à faxina: seed novo + 5.1.02 recriada + nomes
    antigos restaurados na família 5.6 (é o estado real das bases em produção)."""
    mc.seed_plano(db, "loja", oid)
    grupo51 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo="5.1").first()
    db.add(mc.Conta(owner_tipo="loja", owner_id=oid, codigo="5.1.02", nome="Frete Fábrica",
                    grupo=5, tipo="analitica", natureza="devedora", pai_id=grupo51.id,
                    ativa=1, ordem=999))
    for cod, (antigo, _novo) in mc._RENOMES_5_6.items():
        c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=oid, codigo=cod).first()
        c.nome = antigo
    db.commit()


def test_migracao_remove_5102_sem_movimento_e_renomeia(app_db):
    db = app_db.get_session()
    _plano_antigo(db, 901)
    out = mc.migrar_plano_faxina_frete(db)
    assert out["removidas"] >= 1
    contas = {c.codigo: c.nome for c in db.query(mc.Conta)
              .filter_by(owner_tipo="loja", owner_id=901).all()}
    assert "5.1.02" not in contas
    assert contas["5.6"] == "Despesas Reconhecidas de Provisões"
    assert contas["5.6.04"] == "Frete de Fábrica — Despesa Reconhecida"
    # idempotente: rodar de novo não muda nada
    out2 = mc.migrar_plano_faxina_frete(db)
    assert out2["removidas"] == 0 and out2["renomeadas"] == 0
    db.close()


def test_migracao_5102_com_movimento_desativa_em_vez_de_apagar(app_db):
    db = app_db.get_session()
    _plano_antigo(db, 902)
    c5102 = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="5.1.02").first()
    caixa = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="1.1.01").first()
    mc.lancar(db, "loja", 902, c5102.id, caixa.id, 100.0, historico="frete lançado à mão")
    mc.migrar_plano_faxina_frete(db)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=902, codigo="5.1.02").first()
    assert c is not None and not c.ativa            # histórico preservado, conta desativada
    db.close()


def test_migracao_preserva_nome_customizado(app_db):
    db = app_db.get_session()
    _plano_antigo(db, 903)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=903, codigo="5.6.05").first()
    c.nome = "Frete Local da Minha Loja"            # usuário renomeou no painel
    db.commit()
    mc.migrar_plano_faxina_frete(db)
    c = db.query(mc.Conta).filter_by(owner_tipo="loja", owner_id=903, codigo="5.6.05").first()
    assert c.nome == "Frete Local da Minha Loja"    # migração não sobrescreve
    db.close()


def test_evento_frete_fabrica_segue_na_5604(app_db):
    """O motor não muda: reconhecimento na NF-e continua debitando a 5.6.04 (agora com o
    nome novo) contra a baixa do ativo 1.1.06.07."""
    ev = mc.EVENTOS["reconhecimento_despesa_frete_fabrica"]
    assert ev[0] == "5.6.04" and ev[1] == "1.1.06.07"
