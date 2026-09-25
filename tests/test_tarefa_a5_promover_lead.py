# -*- coding: utf-8 -*-
"""TAREFA-A, A5 — botão "promover a Lead" na tela do SAC
(docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md, decisão de 24/09: resposta à pergunta aberta da
TAREFA-B). Contato de atendimento comum (nem Lead nem Cliente — `contato_tipo` 'contato' em
`serializar_conversa`) que não veio de campanha (B2 só cria Lead automático via `referral` da
Meta): o SAC decide manualmente que é comercial. Cria o `Lead` a partir do
`ConversaParticipanteExterno` da própria conversa, liga `conversa.lead_id` — a conversa
continua exatamente onde está (10ª prova do documento)."""
import mod_chat
import mod_chat_externo as ext
from database import Conversa, Lead

import pytest


@pytest.fixture(scope="module", autouse=True)
def numero_da_loja1(app_db, seed):
    db = app_db.get_session()
    db.add(app_db.NumeroConectado(loja_id=seed["loja1_id"], numero="+55 12 90000-2000"))
    db.commit(); db.close()


def _conversa_contato_comum(app_db, seed, remetente, id_externo):
    """Mesmo caminho de tests/test_triagem_fila.py::test_segmento_reconhecido_materializa_com_
    sac_responsavel: número desconhecido, sem referral, escolhe segmento no menu → nasce
    'contato' puro (sem lead_id, sem cliente_id) — exatamente o alvo do botão."""
    db = app_db.get_session()
    try:
        ext.processar_entrada(db, "whatsapp", remetente, "quero um orçamento",
                              id_externo=id_externo + "a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", remetente, "1", id_externo=id_externo + "b")
        db.commit()
        conv = db.get(Conversa, r2["conversa_id"])
        assert conv.lead_id is None and conv.cliente_id is None   # âncora: é mesmo 'contato'
        return conv.id
    finally:
        db.close()


# ── prova 10: botão promove, liga lead_id, a conversa não se move ────────────────────────────

def test_promover_lead_liga_lead_id_sem_mover_a_conversa(app_db, seed):
    conv_id = _conversa_contato_comum(app_db, seed, "5512999993001", "wamid.a5.1")
    db = app_db.get_session()
    try:
        conv = db.get(Conversa, conv_id)
        lead = mod_chat.promover_lead(db, conv, None)
        db.commit()
        assert isinstance(lead, Lead)
        assert lead.loja_id == seed["loja1_id"]
        assert lead.canal == "manual_sac"
        assert "999993001" in (lead.whatsapp or "")
        conv2 = db.get(Conversa, conv_id)
        assert conv2.id == conv_id                      # a conversa não se move
        assert conv2.lead_id == lead.id
        assert conv2.cliente_id is None
    finally:
        db.close()


def test_promover_lead_ja_lead_recusa(app_db, seed):
    conv_id = _conversa_contato_comum(app_db, seed, "5512999993002", "wamid.a5.2")
    db = app_db.get_session()
    try:
        conv = db.get(Conversa, conv_id)
        mod_chat.promover_lead(db, conv, None)
        db.commit()
        with pytest.raises(ValueError):
            mod_chat.promover_lead(db, db.get(Conversa, conv_id), None)
    finally:
        db.close()


def test_promover_lead_ja_cliente_recusa(app_db, seed):
    db = app_db.get_session()
    try:
        from database import Cliente
        cli = Cliente(nome="Cliente A5", loja_id=seed["loja1_id"], rede_id=seed["rede_id"],
                     whatsapp="5512999993003")
        db.add(cli); db.commit()
        r1 = ext.processar_entrada(db, "whatsapp", "5512999993003", "oi",
                                   id_externo="wamid.a5.3a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", "5512999993003", "2",   # P1: outro assunto
                                   id_externo="wamid.a5.3b")
        db.commit()
        r3 = ext.processar_entrada(db, "whatsapp", "5512999993003", "1",   # menu de segmentos
                                   id_externo="wamid.a5.3c")
        db.commit()
        conv = db.get(Conversa, r3["conversa_id"])
        assert conv.cliente_id == cli.id
        with pytest.raises(ValueError):
            mod_chat.promover_lead(db, conv, None)
    finally:
        db.close()


def test_promover_lead_sem_contato_externo_recusa(app_db, seed):
    db = app_db.get_session()
    try:
        conv = mod_chat.get_or_create_conversa_projeto(db, seed["loja1_id"], "Proj_A5_SemExterno")
        db.commit()
        with pytest.raises(ValueError):
            mod_chat.promover_lead(db, conv, None)
    finally:
        db.close()
