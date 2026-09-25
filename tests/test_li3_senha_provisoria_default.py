# -*- coding: utf-8 -*-
"""LI-3/LP-35 (docs/db/LISTA_IMEDIATA.md) — `senha_provisoria` nasce 1 por omissão, não 0.

Antes: `default=0` — esquecer o parâmetro na criação de um Usuario produzia conta com senha
DEFINITIVA sem ninguém ter decidido isso (já aconteceu uma vez, na tela de Admin). Migração
`c64d026c88e5` inverte só o DEFAULT (schema, R6) — nenhuma linha existente muda; quem já tinha
`senha_provisoria=0` continua 0 (ver tests/test_seed_super_admin_env.py, que cobre exatamente
esse caso do dump de produção)."""
from database import Usuario


def test_usuario_sem_passar_o_campo_nasce_com_senha_provisoria_1(app_db, seed):
    db = app_db.get_session()
    try:
        u = Usuario(nome="Sem Flag Explícita", login="li3_sem_flag", nivel="operador",
                   loja_id=seed["loja1_id"], ativo=1)
        u.set_senha("qualquer123")
        db.add(u); db.commit()
        assert u.senha_provisoria == 1
    finally:
        db.close()


def test_scripts_de_piloto_que_pedem_0_continuam_explicitos(app_db, seed):
    """`scripts/seed_loja15.py` e `scripts/seed_funcionarios_homolog.py` já passam
    `senha_provisoria=0` explícito (contas de piloto com senha combinada fora do sistema) —
    o default novo não muda o comportamento de quem já é explícito, só de quem omite."""
    db = app_db.get_session()
    try:
        u = Usuario(nome="Piloto Explícito", login="li3_explicito_zero", nivel="operador",
                   loja_id=seed["loja1_id"], ativo=1, senha_provisoria=0)
        u.set_senha("qualquer123")
        db.add(u); db.commit()
        assert u.senha_provisoria == 0
    finally:
        db.close()
