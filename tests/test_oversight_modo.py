# -*- coding: utf-8 -*-
"""OVERSIGHT-MODO (docs/db/TAREFA_OVERSIGHT_MODO.md, 28/09) — duas queixas do mesmo print.

Queixa 1: `listar_todas_conversas` não devolvia `janela` nem `responsavel` (mesma causa que já
tinha explicado o "Responsável: SAC" de 26/09) — corrigido reusando `_atendimento_meta`/
`_resolver_responsavel`, as MESMAS funções que `listar_inbox` já chama. Este arquivo trava isso
com um teste que compara os dois serializers pra MESMA conversa (item central da Prova — é o
que impede o terceiro sintoma da mesma causa)."""
import mod_chat
from database import Conversa, ConversaMensagem, EnvioExterno


def _uid(db, app_db, login):
    return db.query(app_db.Usuario).filter_by(login=login).first().id


# ── Queixa 1: janela/responsavel agora vêm no Oversight ────────────────────────────────────────

def test_listar_todas_conversas_devolve_janela_e_responsavel(app_db, seed):
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Grupo Com Dados", [],
                                    exige_dois=False)
        db.commit()
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=_uid(db, app_db, "dir_l1"),
                                                ator_nivel="master")
        item = next(i for i in itens if i["id"] == conv.id)
        assert "janela" in item and item["janela"] == {"estado": "na"}
        assert "responsavel" in item
        assert item["responsavel"] == {"id": criadora, "nome": "Consultor L1"}
    finally:
        db.close()


def test_responsavel_no_oversight_nao_cai_no_fallback_sac(app_db, seed):
    """Prova: com responsável de verdade, o Oversight devolve o nome dele -- não None (que faria
    o frontend cair no fallback "SAC", o mesmo sintoma medido em 26/09)."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        destino = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Grupo Transferido", [],
                                    exige_dois=False)
        db.commit()
        mod_chat.transferir_responsavel(db, conv, criadora, destino)
        db.commit()
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=destino, ator_nivel="master")
        item = next(i for i in itens if i["id"] == conv.id)
        assert item["responsavel"]["nome"] == "Diretor L1"   # não None -- não vira "SAC" na tela
    finally:
        db.close()


def test_janela_fechada_mesmo_texto_nos_dois_modos(app_db, seed):
    """Prova: item com janela fechada aparece com a mesma tarja nos dois caminhos."""
    import datetime as _dt
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Grupo Janela Fechada", [],
                                    exige_dois=False)
        conv.segmento = "comercial"
        db.commit()
        m = mod_chat.enviar_mensagem(db, conv, None, "oi", canal="comercial",
                                     _permitir_externo=True)
        db.commit()
        env = EnvioExterno(mensagem_id=m.id, meio="whatsapp", direcao="entrada",
                          criado_em=_dt.datetime.utcnow() - _dt.timedelta(hours=30))
        db.add(env); db.commit()

        inbox = mod_chat.listar_inbox(db, seed["loja1_id"], criadora)
        item_inbox = next(i for i in inbox if i["id"] == conv.id)
        todas = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=criadora, ator_nivel="operador")
        item_todas = next(i for i in todas if i["id"] == conv.id)

        assert item_inbox["janela"]["estado"] == "fechada"
        assert item_todas["janela"]["estado"] == "fechada"
        assert item_inbox["janela"] == item_todas["janela"]
    finally:
        db.close()


# ── Prova central: os dois serializers concordam nos campos comuns ────────────────────────────

def test_oversight_e_inbox_concordam_nos_campos_comuns(app_db, seed):
    """É este teste que impede o terceiro sintoma da mesma causa (o serializer do Oversight
    divergindo do da inbox pessoal em silêncio) -- compara a MESMA conversa pelos dois
    caminhos e falha se um campo comum divergir."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Grupo Comparado", [],
                                    exige_dois=False)
        conv.segmento = "comercial"
        conv.urgente = 1
        db.commit()

        inbox = mod_chat.listar_inbox(db, seed["loja1_id"], criadora)
        item_inbox = next(i for i in inbox if i["id"] == conv.id)
        todas = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=criadora, ator_nivel="operador")
        item_todas = next(i for i in todas if i["id"] == conv.id)

        comuns = ["id", "tipo", "titulo", "projeto_nome", "segmento", "janela", "responsavel",
                 "urgente", "status", "pendente", "ultima_previa", "ultima_em", "criado_em"]
        for campo in comuns:
            assert item_inbox[campo] == item_todas[campo], (
                "campo %r divergiu entre os dois serializers: inbox=%r todas=%r"
                % (campo, item_inbox[campo], item_todas[campo]))
    finally:
        db.close()


def test_oversight_e_inbox_concordam_mesmo_sem_segmento_explicito(app_db, seed):
    """Mesmo teste central, mas SEM `segmento` setado manualmente -- prova que o fallback
    derivado do tráfego (dentro de `_atendimento_meta`) também bate nos dois caminhos, não só o
    caso "já tem segmento manual"."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Grupo Sem Segmento", [],
                                    exige_dois=False)
        db.commit()

        inbox = mod_chat.listar_inbox(db, seed["loja1_id"], criadora)
        item_inbox = next(i for i in inbox if i["id"] == conv.id)
        todas = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=criadora, ator_nivel="operador")
        item_todas = next(i for i in todas if i["id"] == conv.id)

        assert item_inbox["segmento"] == item_todas["segmento"] is None
        assert item_inbox["responsavel"] == item_todas["responsavel"]
    finally:
        db.close()
