# -*- coding: utf-8 -*-
"""docs/db/TAREFA_REDEFINICAO_DE_SENHA.md, Caminho 1 — redefinição de senha pelo gestor.

PATCH /api/admin/usuarios/<id>/redefinir-senha: master/gerencial redefine a senha de um
funcionário da PRÓPRIA loja. Tenancy + hierarquia (nunca de nível igual ou acima) + trilha
(LogAcaoGerencial) — cobertos aqui via HTTP real (não só chamando a função)."""
import json

import pytest

from database import LogAcaoGerencial


def _login(f, who):
    c = f()
    c.login(who, "senha123")
    assert c.cookie
    return c


@pytest.fixture(scope="module")
def gestor_extra(app_db, seed):
    """Um gerencial e um 2º master na loja 1, e um operador na loja 2 — o seed padrão só tem
    master (dir_l1) e operador (cons_l1) na loja 1."""
    db = app_db.get_session()
    try:
        ger = app_db.Usuario(nome="Gerente L1", login="ger_l1", nivel="gerencial",
                             loja_id=seed["loja1_id"], ativo=1)
        ger.set_senha("senha123")
        master2 = app_db.Usuario(nome="Master 2 L1", login="master2_l1", nivel="master",
                                 loja_id=seed["loja1_id"], ativo=1)
        master2.set_senha("senha123")
        op_l2 = app_db.Usuario(nome="Operador L2", login="op_l2", nivel="operador",
                               loja_id=seed["loja2_id"], ativo=1)
        op_l2.set_senha("senha123")
        # Operador PRÓPRIO pra testar o bloqueio por nível do ATOR — não reusa cons_l1, que as
        # duas primeiras faixas deste arquivo já redefinem (troca a senha, "senha123" para de
        # funcionar; module-scoped, estado acumula entre testes do mesmo arquivo).
        op_l1_dedicado = app_db.Usuario(nome="Operador Dedicado L1", login="op_l1_dedicado",
                                        nivel="operador", loja_id=seed["loja1_id"], ativo=1)
        op_l1_dedicado.set_senha("senha123")
        db.add_all([ger, master2, op_l2, op_l1_dedicado]); db.commit()
        ids = {"ger_l1": ger.id, "master2_l1": master2.id, "op_l2": op_l2.id,
               "op_l1_dedicado": op_l1_dedicado.id}
    finally:
        db.close()
    return ids


def _uid(app_db, login):
    db = app_db.get_session()
    try:
        return db.query(app_db.Usuario).filter_by(login=login).first().id
    finally:
        db.close()


def test_master_redefine_senha_de_operador_da_propria_loja(http_client_factory, app_db, seed,
                                                            gestor_extra):
    alvo_id = _uid(app_db, "cons_l1")
    c = _login(http_client_factory, "dir_l1")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 200 and body["ok"], body
    nova = body["senha"]
    assert nova

    db = app_db.get_session()
    try:
        u = db.get(app_db.Usuario, alvo_id)
        assert u.senha_provisoria == 1
        log = (db.query(LogAcaoGerencial)
                 .filter_by(acao="redefinir_senha_funcionario")
                 .order_by(LogAcaoGerencial.id.desc()).first())
        assert log is not None
        ctx = json.loads(log.contexto)
        assert ctx["usuario_alvo_id"] == alvo_id and ctx["login_alvo"] == "cons_l1"
        assert nova not in log.contexto and nova not in (log.acao or "")
    finally:
        db.close()

    import auth.auth as auth_mod
    r = auth_mod.fazer_login("cons_l1", nova)
    assert r["ok"] is True and r["precisa_trocar_senha"] is True


def test_gerencial_redefine_operador_da_mesma_loja(http_client_factory, app_db, seed,
                                                    gestor_extra):
    alvo_id = _uid(app_db, "cons_l1")
    c = _login(http_client_factory, "ger_l1")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 200 and body["ok"], body


def test_gerencial_nao_redefine_master_nivel_acima(http_client_factory, app_db, seed,
                                                    gestor_extra):
    alvo_id = _uid(app_db, "dir_l1")
    c = _login(http_client_factory, "ger_l1")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 403 and body["ok"] is False


def test_master_nao_redefine_outro_master_mesmo_nivel(http_client_factory, app_db, seed,
                                                       gestor_extra):
    alvo_id = gestor_extra["master2_l1"]
    c = _login(http_client_factory, "dir_l1")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 403 and body["ok"] is False


def test_master_nao_redefine_usuario_de_outra_loja(http_client_factory, app_db, seed,
                                                    gestor_extra):
    alvo_id = gestor_extra["op_l2"]
    c = _login(http_client_factory, "dir_l1")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 403 and body["ok"] is False


def test_operador_nao_pode_redefinir_ninguem(http_client_factory, app_db, seed, gestor_extra):
    alvo_id = gestor_extra["op_l2"]  # nem chega a importar o alvo — nivel do ator ja barra
    c = _login(http_client_factory, "op_l1_dedicado")
    st, body = c.patch("/api/admin/usuarios/%d/redefinir-senha" % alvo_id)
    assert st == 403 and body["ok"] is False
