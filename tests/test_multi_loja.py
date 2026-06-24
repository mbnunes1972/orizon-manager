import pytest
import database


def test_membership_vazio_para_usuario_sem_vinculo(app_db, seed):
    db = app_db.get_session()
    try:
        # cria um usuário sem nenhuma linha em usuario_lojas
        u = app_db.Usuario(nome="Sem Loja", login="semloja", nivel="consultor", ativo=1)
        u.set_senha("x"); db.add(u); db.commit()
        assert database.membership_loja_ids(db, u.id) == []
    finally:
        db.close()


def test_membership_lista_lojas(app_db, seed):
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="Multi", login="multi1", nivel="diretor",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("x"); db.add(u); db.flush()
        db.add_all([
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja1_id"]),
            app_db.UsuarioLoja(usuario_id=u.id, loja_id=seed["loja2_id"]),
        ])
        db.commit()
        assert set(database.membership_loja_ids(db, u.id)) == {seed["loja1_id"], seed["loja2_id"]}
    finally:
        db.close()


def test_backfill_cria_uma_membership_por_loja_id(app_db, seed):
    import sqlite3
    # usuário com loja_id e SEM membership (simula estado pré-migração)
    db = app_db.get_session()
    try:
        u = app_db.Usuario(nome="Legado", login="legado1", nivel="consultor",
                           loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("x"); db.add(u); db.commit()
        uid = u.id
    finally:
        db.close()
    # roda o backfill direto sobre a conexão sqlite
    con = sqlite3.connect(database.DB_PATH)
    try:
        database._backfill_usuario_lojas(con.cursor()); con.commit()
    finally:
        con.close()
    db = app_db.get_session()
    try:
        assert database.membership_loja_ids(db, uid) == [seed["loja1_id"]]
        # idempotente: rodar de novo não duplica
    finally:
        db.close()
    con = sqlite3.connect(database.DB_PATH)
    try:
        database._backfill_usuario_lojas(con.cursor()); con.commit()
    finally:
        con.close()
    db = app_db.get_session()
    try:
        assert database.membership_loja_ids(db, uid) == [seed["loja1_id"]]
    finally:
        db.close()
