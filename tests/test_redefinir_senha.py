# -*- coding: utf-8 -*-
"""scripts/redefinir_senha.py — Caminho 3 (TAREFA_REDEFINICAO_DE_SENHA.md, 18/09): contas sem
gestor acima e sem telefone (super_admin, contas soltas da tela Admin). Roda o script de
verdade (subprocess, contra o banco de teste isolado do `app_db`) e confirma pelo caminho de
autenticação REAL do app (`auth.fazer_login`) — não só que o hash mudou no banco."""
import os
import re
import subprocess
import sys

import auth.auth as auth_mod

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _rodar_script(db_url, login):
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run([sys.executable, "scripts/redefinir_senha.py", "--login", login],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True)


def _extrair_senha(stdout):
    m = re.search(r"Senha nova \(só aparece agora, não fica gravada em lugar nenhum\): (\S+)",
                  stdout)
    assert m, "nao achei a senha na saida:\n%s" % stdout
    return m.group(1)


def test_redefine_senha_sem_cpf_gera_token_e_liga_provisoria(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Sad Admin", login="sad_teste", nivel="super_admin", ativo=1)
    u.set_senha("senhaAntiga123")
    db.add(u); db.commit()
    uid = u.id
    db.close()

    db_url = app_db.ENGINE.url.render_as_string(hide_password=False)
    proc = _rodar_script(db_url, "sad_teste")
    assert proc.returncode == 0, "script falhou:\n%s\n%s" % (proc.stdout, proc.stderr)
    nova = _extrair_senha(proc.stdout)
    assert nova != "senhaAntiga123"

    r_antiga = auth_mod.fazer_login("sad_teste", "senhaAntiga123")
    assert r_antiga["ok"] is False, "senha antiga nao podia continuar funcionando"

    r_nova = auth_mod.fazer_login("sad_teste", nova)
    assert r_nova["ok"] is True, r_nova
    assert r_nova["precisa_trocar_senha"] is True

    db = app_db.get_session()
    u2 = db.get(app_db.Usuario, uid)
    assert u2.senha_provisoria == 1
    db.close()


def test_redefine_com_cpf_usa_digitos_do_cpf_mesmo_gerador_do_func_sync_acesso(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Func com CPF", login="func_cpf_teste", nivel="operador",
                       cpf="123.456.789-09", ativo=1)
    u.set_senha("outrasenha123")
    db.add(u); db.commit()
    db.close()

    db_url = app_db.ENGINE.url.render_as_string(hide_password=False)
    proc = _rodar_script(db_url, "func_cpf_teste")
    assert proc.returncode == 0, "script falhou:\n%s\n%s" % (proc.stdout, proc.stderr)
    nova = _extrair_senha(proc.stdout)
    assert nova == "12345678909"

    r = auth_mod.fazer_login("func_cpf_teste", "12345678909")
    assert r["ok"] is True and r["precisa_trocar_senha"] is True


def test_recusa_login_inexistente(app_db):
    db_url = app_db.ENGINE.url.render_as_string(hide_password=False)
    proc = _rodar_script(db_url, "nao-existe-de-verdade")
    assert proc.returncode != 0
    assert "RECUSADO" in (proc.stdout + proc.stderr)


def test_recusa_conta_inativa(app_db):
    db = app_db.get_session()
    u = app_db.Usuario(nome="Inativo", login="inativo_teste", nivel="operador", ativo=0)
    u.set_senha("qualquercoisa123")
    db.add(u); db.commit()
    db.close()

    db_url = app_db.ENGINE.url.render_as_string(hide_password=False)
    proc = _rodar_script(db_url, "inativo_teste")
    assert proc.returncode != 0
    assert "RECUSADO" in (proc.stdout + proc.stderr)
