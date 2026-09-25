# -*- coding: utf-8 -*-
"""TAREFA-B — Lead de verdade e o painel do SAC (docs/db/TAREFA_LEAD_E_PAINEL_SAC.md).

B1: `triagem_materializar` parava de rotular todo contato novo como "Lead — Nome" no título;
o selo (Lead/Cliente/Contato) passa a ser DERIVADO em `serializar_conversa`
(`lead_id`/`cliente_id`), nunca mais escrito no título; Cliente reconhecido grava
`conv.cliente_id` (a informação já estava na mão e era descartada).

B2: **Lead é quem veio de campanha** — `referral` (Click-to-WhatsApp da Meta) presente e
telefone desconhecido → `Lead` nasce NA ENTRADA (`processar_entrada`), não na materialização;
`triagem_materializar` passa a PROCURAR Lead existente por (telefone, loja) em vez de criar
incondicionalmente — sem `referral` nenhum, nenhum Lead nasce (selo "Contato").

As 5 primeiras provas da seção "Prova" do documento (B1+B2) + a metade de BACKEND da prova 6
(B3, item 9: `pendente` computado certo — a metade de FRONTEND, a marca aparecendo no item,
está em tests/test_e2e_browser_tarefa_b_ordenacao.py, junto da prova 7 de ordenação)."""
import mod_chat_externo as ext
import mod_chat
from chat import triagem as tri
from database import Lead, TriagemEntrada, Conversa

import pytest


REFERRAL_EXEMPLO = {"source_type": "ad", "source_id": "anuncio-123",
                    "headline": "Cozinhas planejadas", "body": "Peça seu orçamento"}


@pytest.fixture(scope="module", autouse=True)
def numero_da_loja1(app_db, seed):
    """Fiel à produção (RF-01) e ao mesmo padrão de tests/test_triagem_fila.py: com 1
    NumeroConectado só, `_loja_da_entrada` (LP-39) resolve a loja de forma determinística —
    sem isto, o fallback "primeira loja por id" cairia na loja-seed do `_seed_loja_padrao`,
    não em `seed["loja1_id"]`."""
    db = app_db.get_session()
    db.add(app_db.NumeroConectado(loja_id=seed["loja1_id"], numero="+55 12 90000-1000"))
    db.commit(); db.close()


def _limpar(app_db, remetente):
    db = app_db.get_session()
    try:
        for e in db.query(TriagemEntrada).filter_by(remetente=remetente).all():
            db.delete(e)
        for lead in db.query(Lead).filter_by(whatsapp=remetente).all():
            db.delete(lead)
        db.commit()
    finally:
        db.close()


# ── prova 1: referral de telefone desconhecido → Lead na entrada, materializa ligado a ELE ──

def test_referral_cria_lead_na_entrada_e_materializa_ligado_a_ele(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999991001"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        r1 = ext.processar_entrada(db, "whatsapp", tel, "quero uma cozinha",
                                   id_externo="wamid.tb.1", referral=REFERRAL_EXEMPLO)
        db.commit()
        assert r1["status"] == "triagem" and r1["triagem_id"]

        leads = db.query(Lead).filter_by(whatsapp=tel, loja_id=seed["loja1_id"]).all()
        assert len(leads) == 1, "referral tinha que criar o Lead NA ENTRADA, não esperar a triagem"
        lead = leads[0]
        assert lead.canal == "ad"                              # source_type do referral
        assert lead.template == "whatsapp_referral"
        dados = lead.dados_json
        assert dados and "anuncio-123" in dados and "Cozinhas planejadas" in dados

        # materializa (resposta reconhecida "1" = primeiro segmento do menu) — mesma sequência
        # de processar_entrada (interpreta, depois materializa com o segmento devolvido).
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        seg = tri.registrar_resposta_triagem(db, ent, "1")
        db.commit()
        assert seg
        conv = tri.triagem_materializar(db, ent, seg)
        db.commit()
        assert conv.lead_id == lead.id, "materializou ligado a um Lead DIFERENTE do da entrada"
        assert conv.cliente_id is None
        assert "Lead —" not in (conv.titulo or ""), "título não pode mais carregar o prefixo"

        # nenhum Lead duplicado nasceu no caminho (materialização não cria, só liga)
        leads_depois = db.query(Lead).filter_by(whatsapp=tel, loja_id=seed["loja1_id"]).all()
        assert len(leads_depois) == 1
    finally:
        db.close()


# ── prova 2: SEM referral, telefone desconhecido → nenhum Lead ──────────────────────────────

def test_sem_referral_telefone_desconhecido_nao_cria_lead(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999991002"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        r1 = ext.processar_entrada(db, "whatsapp", tel, "oi, vi vocês no bairro",
                                   id_externo="wamid.tb.2", referral=None)
        db.commit()
        assert r1["status"] == "triagem"
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 0

        ent = db.get(TriagemEntrada, r1["triagem_id"])
        seg = tri.registrar_resposta_triagem(db, ent, "1")
        db.commit()
        assert seg
        conv = tri.triagem_materializar(db, ent, seg)
        db.commit()
        assert conv.lead_id is None and conv.cliente_id is None
        assert "Lead —" not in (conv.titulo or "")
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 0, \
            "sem referral, telefone desconhecido NÃO pode virar Lead — vira atendimento comum"
    finally:
        db.close()


# ── prova 3: telefone de Cliente cadastrado → cliente_id gravado, sem "Lead —" ───────────────

def test_telefone_de_cliente_grava_cliente_id_sem_prefixo_lead(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999991003"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        cli = app_db.Cliente(nome="Cliente Tarefa B", loja_id=seed["loja1_id"],
                             whatsapp=tel, rede_id=seed["rede_id"])
        db.add(cli); db.commit()
        cli_id = cli.id

        r1 = ext.processar_entrada(db, "whatsapp", tel, "quero renegociar",
                                   id_externo="wamid.tb.3", referral=REFERRAL_EXEMPLO)
        db.commit()
        # cliente cadastrado NUNCA vira Lead, mesmo com referral (regra do Marcelo, item 48)
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 0

        ent = db.get(TriagemEntrada, r1["triagem_id"])
        seg = tri.registrar_resposta_triagem(db, ent, "1")
        db.commit()
        conv = tri.triagem_materializar(db, ent, seg)
        db.commit()
        assert conv.cliente_id == cli_id
        assert conv.lead_id is None
        assert "Lead —" not in (conv.titulo or "")
        assert conv.titulo == "Cliente Tarefa B"
    finally:
        db.close()


# ── prova 4: segunda mensagem do MESMO telefone de anúncio → não cria Lead novo ──────────────

def test_segunda_mensagem_do_mesmo_telefone_de_anuncio_nao_duplica_lead(app_db, seed, monkeypatch):
    monkeypatch.delenv("ORIZON_WA_TOKEN", raising=False)
    monkeypatch.delenv("ORIZON_WA_PHONE_ID", raising=False)
    tel = "5512999991004"
    _limpar(app_db, tel)
    db = app_db.get_session()
    try:
        r1 = ext.processar_entrada(db, "whatsapp", tel, "quero um armário",
                                   id_externo="wamid.tb.4a", referral=REFERRAL_EXEMPLO)
        db.commit()
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 1

        # segunda mensagem, mesmo telefone, ainda dentro da janela de triagem (mesma entrada
        # pendente) — cenário mais comum: a pessoa manda mais de uma mensagem antes de
        # responder o menu.
        r2 = ext.processar_entrada(db, "whatsapp", tel, "urgente, pode ser?",
                                   id_externo="wamid.tb.4b", referral=REFERRAL_EXEMPLO)
        db.commit()
        assert r2["triagem_id"] == r1["triagem_id"], "tinha que ser a MESMA entrada, não uma nova"
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 1, \
            "segunda mensagem do mesmo telefone de anúncio não pode duplicar o Lead"
    finally:
        db.close()


# ── prova 4b: dedup também vale quando a triagem gera uma entrada NOVA (projeto concluído,
#    reentrada etc.) para um telefone que já tem Lead nesta loja — é o que triagem_materializar
#    (item 7) resolve procurando antes de criar. ──────────────────────────────────────────────

def test_triagem_materializar_reusa_lead_existente_em_vez_de_duplicar(app_db, seed):
    tel = "5512999991005"
    db = app_db.get_session()
    try:
        db.query(TriagemEntrada).filter_by(remetente=tel).delete()
        db.query(Lead).filter_by(whatsapp=tel).delete()
        lead_previo = app_db.Lead(nome="Contato Antigo", loja_id=seed["loja1_id"],
                                  whatsapp=tel, canal="ad", template="whatsapp_referral",
                                  dados_json="{}")
        db.add(lead_previo); db.commit()
        lead_id = lead_previo.id

        ent = app_db.TriagemEntrada(loja_id=seed["loja1_id"], meio="whatsapp", remetente=tel,
                                    texto="de novo por aqui")
        db.add(ent); db.commit()

        conv = tri.triagem_materializar(db, ent, "comercial")
        db.commit()
        assert conv.lead_id == lead_id
        assert db.query(Lead).filter_by(whatsapp=tel).count() == 1, \
            "materializar tinha que REUSAR o Lead já existente, nunca criar um segundo"
    finally:
        db.close()


# ── prova 5: serializar_conversa devolve o selo derivado certo nos três casos ────────────────

def test_serializar_conversa_devolve_selo_derivado(app_db, seed):
    db = app_db.get_session()
    try:
        uid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        lead = app_db.Lead(nome="Lead Selo", loja_id=seed["loja1_id"], whatsapp="55129999zz1",
                           canal="ad", template="whatsapp_referral", dados_json="{}")
        db.add(lead); db.flush()
        conv_lead = mod_chat.criar_grupo(db, seed["loja1_id"], uid, "Lead Selo", [uid],
                                         exige_dois=False)
        conv_lead.lead_id = lead.id

        conv_cliente = mod_chat.criar_grupo(db, seed["loja1_id"], uid, "Cliente Selo", [uid],
                                            exige_dois=False)
        conv_cliente.cliente_id = seed["cliente_l1_id"]

        conv_contato = mod_chat.criar_grupo(db, seed["loja1_id"], uid, "Contato Selo", [uid],
                                            exige_dois=False)
        db.commit()

        d_lead = mod_chat.serializar_conversa(db, conv_lead, uid)
        d_cliente = mod_chat.serializar_conversa(db, conv_cliente, uid)
        d_contato = mod_chat.serializar_conversa(db, conv_contato, uid)
        assert d_lead["contato_tipo"] == "lead"
        assert d_cliente["contato_tipo"] == "cliente"
        assert d_contato["contato_tipo"] == "contato"
    finally:
        db.close()


# ── prova 6 (metade backend): última mensagem externa → pendente verdadeiro ──────────────────
# A metade de frontend (a marca aparecendo no item) está em
# tests/test_e2e_browser_tarefa_b_ordenacao.py::test_marca_de_aguardando_resposta_aparece_no_item.

def test_ultima_mensagem_externa_marca_pendente_verdadeiro(app_db, seed):
    db = app_db.get_session()
    try:
        uid = db.query(app_db.Usuario).filter_by(login="dir_l1").first().id
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], uid, "Aguardando Resposta", [uid],
                                    exige_dois=False, assunto_tipo="livre")
        db.commit()
        mod_chat.enviar_mensagem(db, conv, uid, "oi, tudo bem?", canal="comercial",
                                 _permitir_externo=True)
        db.commit()
        assert mod_chat.serializar_conversa(db, conv, uid)["pendente"] is False, \
            "última mensagem NOSSA (autor interno) não pode marcar pendente"

        mod_chat.enviar_mensagem(db, conv, None, "quero saber do orçamento", canal="comercial",
                                 _permitir_externo=True)
        db.commit()
        assert mod_chat.serializar_conversa(db, conv, uid)["pendente"] is True, \
            "última mensagem EXTERNA (autor NULL) tem que marcar pendente verdadeiro"
    finally:
        db.close()
