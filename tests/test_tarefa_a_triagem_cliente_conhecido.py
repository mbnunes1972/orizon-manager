# -*- coding: utf-8 -*-
"""TAREFA-A — quem já é cliente não é tratado como lead
(docs/db/TAREFA_TRIAGEM_CLIENTE_CONHECIDO.md).

Regra do Marcelo (24/09): número de Cliente cadastrado NESTA loja (LP-39: quem recebeu decide
a loja) não recebe o menu de segmentos — recebe reconhecimento (P1: projeto em andamento, ou
outro assunto). Projeto → 1 ativo cai direto, 2+ pede escolha (P2), 0 ativos vira "outro
assunto". Projeto definido → P3 confirma o consultor; sem consultor, ou consultor recusado,
vai pro "ramo do comercial" (segmento comercial, responsável SAC — nunca atribuição direta).
Sem resposta em 2min, em QUALQUER estado, a varredura de sempre materializa com segmento
'triagem'. Nove das dez provas do documento (a décima, o botão promover a Lead, é A5 — commit
à parte)."""
import datetime as _dt
import json

import mod_chat_externo as ext
from chat import triagem as tri
from database import Cliente, Conversa, Projeto, TriagemEntrada

import pytest


def _mk_func(db, app_db, loja_id, nome_funcao, nome_pessoa, com_login=None):
    fn = db.query(app_db.Funcao).filter_by(loja_id=loja_id, nome=nome_funcao).first()
    if fn is None:
        fn = app_db.Funcao(loja_id=loja_id, nome=nome_funcao)
        db.add(fn); db.flush()
    f = app_db.Funcionario(loja_id=loja_id, nome=nome_pessoa, funcao_id=fn.id, status="ativo")
    db.add(f); db.flush()
    if com_login:
        u = app_db.Usuario(nome=nome_pessoa, login=com_login, nivel="operador",
                           loja_id=loja_id, ativo=1)
        u.set_senha("senha123")
        db.add(u); db.flush()
        f.usuario_id = u.id; db.flush()
    return f


@pytest.fixture(scope="module", autouse=True)
def numero_da_loja1(app_db, seed):
    """Mesmo padrão de tests/test_triagem_fila.py: 1 NumeroConectado só (loja 1) — resolução de
    loja determinística (LP-39), sem depender do fallback "primeira loja"."""
    db = app_db.get_session()
    db.add(app_db.NumeroConectado(loja_id=seed["loja1_id"], numero="+55 12 90000-0009"))
    db.commit(); db.close()


# ── prova 1: 1 projeto ativo, consultor confirmado → conversa DAQUELE projeto ────────────────

def test_um_projeto_ativo_com_consultor_confirmado_entra_na_conversa_do_projeto(app_db, seed):
    db = app_db.get_session()
    try:
        consultor = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
        cli = Cliente(nome="Cliente Projeto Unico", loja_id=seed["loja1_id"],
                      rede_id=seed["rede_id"], whatsapp="5512999992001")
        db.add(cli); db.flush()
        proj = Projeto(nome_safe="Proj_TarefaA_1", cliente_id=cli.id, loja_id=seed["loja1_id"],
                       status="quente", criado_por_id=consultor.id)
        db.add(proj); db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992001", "oi", id_externo="wamid.ta.1a")
        db.commit()
        assert r1["status"] == "triagem"
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert json.loads(ent.dialogo_json)["estado"] == "aguardando_reconhecimento"

        r2 = ext.processar_entrada(db, "whatsapp", "5512999992001", "1",   # projeto
                                   id_externo="wamid.ta.1b")
        db.commit()
        assert r2["status"] == "triagem"
        dialogo = json.loads(db.get(TriagemEntrada, ent.id).dialogo_json)
        assert dialogo["estado"] == "aguardando_consultor" and dialogo["projeto"] == "Proj_TarefaA_1"

        r3 = ext.processar_entrada(db, "whatsapp", "5512999992001", "1",   # sim
                                   id_externo="wamid.ta.1c")
        db.commit()
        assert r3["status"] == "roteado"
        conv = db.get(Conversa, r3["conversa_id"])
        assert conv.projeto_nome == "Proj_TarefaA_1"
        assert conv.cliente_id == cli.id
        assert conv.lead_id is None
        assert db.query(Conversa).filter_by(projeto_nome="Proj_TarefaA_1").count() == 1
    finally:
        db.close()


# ── prova 2: 2 projetos ativos → P2, escolha entrega no projeto escolhido ────────────────────

def test_dois_projetos_ativos_envia_p2_e_entrega_no_escolhido(app_db, seed):
    db = app_db.get_session()
    try:
        consultor = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
        cli = Cliente(nome="Cliente Dois Projetos", loja_id=seed["loja1_id"],
                      rede_id=seed["rede_id"], whatsapp="5512999992002")
        db.add(cli); db.flush()
        db.add_all([
            Projeto(nome_safe="Proj_TarefaA_2A", cliente_id=cli.id, loja_id=seed["loja1_id"],
                   status="quente", criado_por_id=consultor.id),
            Projeto(nome_safe="Proj_TarefaA_2B", cliente_id=cli.id, loja_id=seed["loja1_id"],
                   status="morno", criado_por_id=consultor.id),
        ])
        db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992002", "oi", id_externo="wamid.ta.2a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", "5512999992002", "1",   # projeto
                                   id_externo="wamid.ta.2b")
        db.commit()
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert json.loads(ent.dialogo_json)["estado"] == "aguardando_projeto"

        r3 = ext.processar_entrada(db, "whatsapp", "5512999992002", "2",   # 2º da lista (ordem alfabética)
                                   id_externo="wamid.ta.2c")
        db.commit()
        dialogo = json.loads(db.get(TriagemEntrada, ent.id).dialogo_json)
        assert dialogo["projeto"] == "Proj_TarefaA_2B" and dialogo["estado"] == "aguardando_consultor"

        r4 = ext.processar_entrada(db, "whatsapp", "5512999992002", "1",   # sim
                                   id_externo="wamid.ta.2d")
        db.commit()
        assert r4["status"] == "roteado"
        conv = db.get(Conversa, r4["conversa_id"])
        assert conv.projeto_nome == "Proj_TarefaA_2B"
    finally:
        db.close()


# ── prova 3: 0 projeto ativo, "projeto" → ramo 3 (menu), sem erro e sem loop ─────────────────

def test_zero_projeto_ativo_cai_no_menu_de_segmentos(app_db, seed):
    db = app_db.get_session()
    try:
        cli = Cliente(nome="Cliente Sem Projeto Ativo", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992003")
        db.add(cli); db.flush()
        db.add(Projeto(nome_safe="Proj_TarefaA_3", cliente_id=cli.id, loja_id=seed["loja1_id"],
                      status="concluido"))                 # terminal -- não conta como ativo
        db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992003", "oi", id_externo="wamid.ta.3a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", "5512999992003", "1",   # projeto
                                   id_externo="wamid.ta.3b")
        db.commit()
        assert r2["status"] == "triagem"                   # sem erro, sem loop
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert json.loads(ent.dialogo_json)["estado"] == "aguardando_segmento"
    finally:
        db.close()


# ── prova 4: "outro assunto" → menu, materializa com segmento, lead_id nulo, cliente_id gravado

def test_outro_assunto_materializa_com_segmento_sem_lead(app_db, seed):
    db = app_db.get_session()
    try:
        cli = Cliente(nome="Cliente Outro Assunto", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992004")
        db.add(cli); db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992004", "oi", id_externo="wamid.ta.4a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", "5512999992004", "2",   # outro assunto
                                   id_externo="wamid.ta.4b")
        db.commit()
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert json.loads(ent.dialogo_json)["estado"] == "aguardando_segmento"

        r3 = ext.processar_entrada(db, "whatsapp", "5512999992004", "1",   # 1º do menu de sempre
                                   id_externo="wamid.ta.4c")
        db.commit()
        assert r3["status"] == "roteado"
        conv = db.get(Conversa, r3["conversa_id"])
        assert conv.cliente_id == cli.id
        assert conv.lead_id is None
    finally:
        db.close()


# ── prova 5: projeto sem consultor → direto pro comercial, responsável SAC ───────────────────

def test_projeto_sem_consultor_vai_direto_pro_comercial_com_sac(app_db, seed):
    db = app_db.get_session()
    try:
        sac = _mk_func(db, app_db, seed["loja1_id"], "SAC", "SAC Tarefa A 5", com_login="sac_ta5")
        db.commit()
        cli = Cliente(nome="Cliente Sem Consultor", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992005")
        db.add(cli); db.flush()
        db.add(Projeto(nome_safe="Proj_TarefaA_5", cliente_id=cli.id, loja_id=seed["loja1_id"],
                      status="quente", criado_por_id=None))
        db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992005", "oi", id_externo="wamid.ta.5a")
        db.commit()
        r2 = ext.processar_entrada(db, "whatsapp", "5512999992005", "1",   # projeto
                                   id_externo="wamid.ta.5b")
        db.commit()
        assert r2["status"] == "roteado"          # sem consultor -- resolve direto, sem P3
        conv = db.get(Conversa, r2["conversa_id"])
        assert conv.segmento == "comercial"
        assert conv.responsavel_usuario_id == sac.usuario_id
        assert conv.projeto_nome is None          # ramo comercial: grupo normal, não o do projeto
    finally:
        db.close()


# ── prova 6: "não" em P3 → mesmo destino (comercial + SAC) ───────────────────────────────────

def test_consultor_recusado_em_p3_vai_pro_comercial_com_sac(app_db, seed):
    """Reusa o SAC da loja 1 se a prova 5 já rodou nesta sessão de módulo (mesmo padrão de
    tests/test_triagem_fila.py); cria um se rodar isolado (`pytest -k`) — nunca um segundo
    junto do da prova 5, senão a resolução (primeiro por Função 'SAC') fica ambígua pro teste."""
    db = app_db.get_session()
    try:
        sac_usuario_id = tri._sac_usuario_id(db, seed["loja1_id"])
        if sac_usuario_id is None:
            f = _mk_func(db, app_db, seed["loja1_id"], "SAC", "SAC Tarefa A 6",
                        com_login="sac_ta6")
            sac_usuario_id = f.usuario_id
        consultor = db.query(app_db.Usuario).filter_by(login="dir_l1").first()
        db.commit()
        cli = Cliente(nome="Cliente Recusa Consultor", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992006")
        db.add(cli); db.flush()
        db.add(Projeto(nome_safe="Proj_TarefaA_6", cliente_id=cli.id, loja_id=seed["loja1_id"],
                      status="quente", criado_por_id=consultor.id))
        db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992006", "oi", id_externo="wamid.ta.6a")
        db.commit()
        ext.processar_entrada(db, "whatsapp", "5512999992006", "1",       # projeto
                              id_externo="wamid.ta.6b")
        db.commit()
        r3 = ext.processar_entrada(db, "whatsapp", "5512999992006", "2",  # não
                                   id_externo="wamid.ta.6c")
        db.commit()
        assert r3["status"] == "roteado"
        conv = db.get(Conversa, r3["conversa_id"])
        assert conv.segmento == "comercial"
        assert conv.responsavel_usuario_id == sac_usuario_id
    finally:
        db.close()


# ── prova 7: silêncio em qualquer estado → varredura materializa com segmento 'triagem' ──────

def test_silencio_em_qualquer_estado_a_varredura_materializa_triagem(app_db, seed):
    db = app_db.get_session()
    try:
        cli = Cliente(nome="Cliente Silencioso", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992007")
        db.add(cli); db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992007", "oi", id_externo="wamid.ta.7a")
        db.commit()
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert ent.dialogo_json is not None        # meio do diálogo (P1 ainda pendente)
        ent.criado_em = _dt.datetime.utcnow() - _dt.timedelta(minutes=3)
        db.commit()

        tri.varrer_triagem_vencida(db, seed["loja1_id"])
        db.commit()
        ent2 = db.get(TriagemEntrada, ent.id)
        assert ent2.status == "resolvido"
        conv = db.get(Conversa, ent2.conversa_id)
        assert conv.segmento == tri.SEGMENTO_TRIAGEM
    finally:
        db.close()


# ── prova 8: número desconhecido → nada muda, dialogo_json nulo ──────────────────────────────

def test_numero_desconhecido_dialogo_json_nulo(app_db, seed):
    db = app_db.get_session()
    try:
        r1 = ext.processar_entrada(db, "whatsapp", "5512999992008", "oi", id_externo="wamid.ta.8a")
        db.commit()
        assert r1["status"] == "triagem"
        ent = db.get(TriagemEntrada, r1["triagem_id"])
        assert ent.dialogo_json is None
    finally:
        db.close()


# ── prova 9: reentrega do mesmo wamid → no-op (idempotência de hoje preservada) ──────────────

def test_reentrega_mesmo_wamid_no_op(app_db, seed):
    db = app_db.get_session()
    try:
        cli = Cliente(nome="Cliente Reentrega", loja_id=seed["loja1_id"],
                     rede_id=seed["rede_id"], whatsapp="5512999992009")
        db.add(cli); db.commit()

        r1 = ext.processar_entrada(db, "whatsapp", "5512999992009", "oi", id_externo="wamid.ta.9a")
        db.commit()
        r1_dup = ext.processar_entrada(db, "whatsapp", "5512999992009", "oi",
                                       id_externo="wamid.ta.9a")
        db.commit()
        assert r1_dup == r1
        assert db.query(TriagemEntrada).filter_by(remetente="5512999992009").count() == 1
    finally:
        db.close()
