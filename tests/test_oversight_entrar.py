# -*- coding: utf-8 -*-
"""OVERSIGHT-ENTRAR (docs/db/TAREFA_OVERSIGHT_ENTRAR.md, decisão do Marcelo 26/09).

O Oversight abre conversa em leitura de propósito (`podePostar=false` fixo,
`static/index.html`, `ocAbrirTodas`) — é auditoria, não fila de trabalho. A regra nova não
contradiz isso: o gerente pode ENTRAR, por ato explícito (botão + registro na timeline), sem
liberar o compositor por engano. As cinco provas do documento, mais o reuso da escrita de
`ConversaParticipante` (`chat.core._participar`, extraída de `transferir_responsavel` — nenhum
terceiro lugar cria `ConversaParticipante` por este caminho)."""
import mod_chat
from database import Conversa, ConversaMensagem, ConversaParticipante

import pytest


def _uid(db, app_db, login):
    return db.query(app_db.Usuario).filter_by(login=login).first().id


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


def _login(f, who):
    c = f(); c.login(who, "senha123"); assert c.cookie; return c


# ── prova 1+3+4: pode_entrar em listar_todas_conversas — as três condições de visibilidade ────

def test_pode_entrar_true_para_master_nao_participante(app_db, seed):
    """master da loja, não participante -- vê pode_entrar=True."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")   # simula a "Gabriela": criou, é participante e responsável
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Cliente Fulano", [],
                                    exige_dois=False)
        db.commit()
        master_id = _uid(db, app_db, "dir_l1")
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=master_id, ator_nivel="master")
        item = next(i for i in itens if i["id"] == conv.id)
        assert item["pode_entrar"] is True
    finally:
        db.close()


def test_pode_entrar_false_para_operador_comum(app_db, seed):
    """operador comum (nem master/gerencial, nem Função SAC) -- não vê o botão, mesmo via
    Oversight (pode_trabalhar_fila recusa nível bruto 'operador' sem a Função)."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Cliente Beltrano", [],
                                    exige_dois=False)
        db.commit()
        operador_id = _uid(db, app_db, "cons_l1")
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=operador_id, ator_nivel="operador")
        item = next(i for i in itens if i["id"] == conv.id)
        assert item["pode_entrar"] is False
    finally:
        db.close()


def test_pode_entrar_true_para_sac_sem_nivel_gerencial(app_db, seed):
    """Função SAC também abre a porta, mesmo com nível bruto 'operador' -- mesmo gate de
    pode_trabalhar_fila (ADR-029)."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Cliente Cicrano", [],
                                    exige_dois=False)
        sac = _mk_func(db, app_db, seed["loja1_id"], "SAC", "Pessoa do SAC OE",
                       com_login="sac_oe_teste")
        db.commit()
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=sac.usuario_id, ator_nivel="operador")
        item = next(i for i in itens if i["id"] == conv.id)
        assert item["pode_entrar"] is True
    finally:
        db.close()


def test_pode_entrar_false_quem_ja_e_participante(app_db, seed):
    """Quem já participa não vê o botão (não duplica participação)."""
    db = app_db.get_session()
    try:
        criadora = _uid(db, app_db, "cons_l1")
        outro_master = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora, "Cliente Já Participa",
                                    [outro_master], exige_dois=False)
        db.commit()
        itens = mod_chat.listar_todas_conversas(db, seed["loja1_id"],
                                                ator_usuario_id=outro_master, ator_nivel="master")
        item = next(i for i in itens if i["id"] == conv.id)
        assert item["pode_entrar"] is False
    finally:
        db.close()


# ── prova 2: clique -- vira participante, timeline, responsável INALTERADO ────────────────────

def test_entrar_adiciona_participante_sem_trocar_responsavel(app_db, seed):
    db = app_db.get_session()
    try:
        criadora_id = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora_id, "Cliente Entra Aqui", [],
                                    exige_dois=False)
        db.commit()
        master_id = _uid(db, app_db, "dir_l1")
        assert not mod_chat.eh_participante(db, conv.id, master_id)

        u = mod_chat.entrar_na_conversa(db, conv, master_id)
        db.commit()

        assert u.id == master_id
        assert mod_chat.eh_participante(db, conv.id, master_id)
        conv2 = db.get(Conversa, conv.id)
        assert conv2.responsavel_usuario_id == criadora_id   # inalterado -- não é o Transferir

        p = db.query(ConversaParticipante).filter_by(conversa_id=conv.id,
                                                      usuario_id=master_id).first()
        assert p is not None and p.removido == 0 and p.origem == "manual"

        evento = (db.query(ConversaMensagem)
                    .filter_by(conversa_id=conv.id, evento="entrou_conversa").first())
        assert evento is not None and "entrou na conversa" in (evento.corpo or "")
    finally:
        db.close()


def test_entrar_recusa_quem_ja_participa(app_db, seed):
    db = app_db.get_session()
    try:
        criadora_id = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora_id, "Cliente Ja Dentro", [],
                                    exige_dois=False)
        db.commit()
        with pytest.raises(ValueError):
            mod_chat.entrar_na_conversa(db, conv, criadora_id)   # já é participante (criador)
    finally:
        db.close()


def test_entrar_recusa_mural(app_db, seed):
    db = app_db.get_session()
    try:
        mural = mod_chat.get_or_create_mural(db, seed["loja1_id"])
        db.commit()
        with pytest.raises(ValueError):
            mod_chat.entrar_na_conversa(db, mural, _uid(db, app_db, "dir_l1"))
    finally:
        db.close()


# ── prova 5: mural nunca aparece em listar_todas_conversas (regra própria, intocada) ──────────

def test_mural_fora_de_listar_todas_conversas(app_db, seed):
    db = app_db.get_session()
    try:
        mural = mod_chat.get_or_create_mural(db, seed["loja1_id"])
        db.commit()
        itens = mod_chat.listar_todas_conversas(
            db, seed["loja1_id"], ator_usuario_id=_uid(db, app_db, "dir_l1"), ator_nivel="master")
        assert all(i["id"] != mural.id for i in itens)
    finally:
        db.close()


# ── reuso: transferir_responsavel continua funcionando depois da extração de _participar ─────

def test_transferir_responsavel_continua_adicionando_participante(app_db, seed):
    db = app_db.get_session()
    try:
        criadora_id = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora_id, "Cliente Transferido", [],
                                    exige_dois=False)
        db.commit()
        destino_id = _uid(db, app_db, "dir_l1")
        assert not mod_chat.eh_participante(db, conv.id, destino_id)
        u = mod_chat.transferir_responsavel(db, conv, criadora_id, destino_id)
        db.commit()
        assert u.id == destino_id
        assert mod_chat.eh_participante(db, conv.id, destino_id)
        conv2 = db.get(Conversa, conv.id)
        assert conv2.responsavel_usuario_id == destino_id   # este SIM troca -- é o Transferir
    finally:
        db.close()


# ── endpoint + gate próprio (mais estrito que "participante ou ver_todas_conversas") ──────────

def test_endpoint_entrar(http_client_factory, app_db, seed):
    db = app_db.get_session()
    try:
        criadora_id = _uid(db, app_db, "cons_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora_id, "Cliente via Endpoint", [],
                                    exige_dois=False)
        db.commit(); cid = conv.id
    finally:
        db.close()
    master = _login(http_client_factory, "dir_l1")
    st, b = master.post("/api/comunicacao/conversas/%d/entrar" % cid, {})
    assert st == 200 and b["ok"] and b["usuario"]["id"]

    db = app_db.get_session()
    try:
        assert mod_chat.eh_participante(db, cid, _uid(db, app_db, "dir_l1"))
    finally:
        db.close()

    # tenancy: loja 2 não alcança
    outro = _login(http_client_factory, "dir_l2")
    assert outro.post("/api/comunicacao/conversas/%d/entrar" % cid, {})[0] == 404


def test_endpoint_entrar_recusa_operador_comum(http_client_factory, app_db, seed):
    """Gate PRÓPRIO do "entrar" -- mais estrito que o "participante ou ver_todas_conversas" dos
    outros itens da mesma família de endpoint. cons_l1 (operador, nível bruto, sem Função SAC)
    tem ver_todas_conversas? Não precisa saber -- o gate de entrar barra de qualquer forma."""
    db = app_db.get_session()
    try:
        criadora_id = _uid(db, app_db, "dir_l1")
        conv = mod_chat.criar_grupo(db, seed["loja1_id"], criadora_id, "Cliente Gate Estrito", [],
                                    exige_dois=False)
        db.commit(); cid = conv.id
    finally:
        db.close()
    operador = _login(http_client_factory, "cons_l1")
    st, b = operador.post("/api/comunicacao/conversas/%d/entrar" % cid, {})
    assert st == 403 and not b["ok"]
