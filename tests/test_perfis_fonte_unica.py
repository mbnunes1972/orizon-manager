import json
from auth import perfis
import mod_cadastro
import storage


# ── perfis.py como fonte única dos perfis de ACESSO (Função × Perfil, frente irmã) ──
def test_slugs_loja_exclui_plataforma_e_rede():
    slugs = set(perfis.slugs_loja())
    assert "super_admin" not in slugs and "admin_rede" not in slugs
    assert {"operador", "gerencial", "master"} <= slugs


def test_opcoes_acesso_derivadas_sem_orfao_gerente():
    ops = mod_cadastro.META["perfis_acesso"]
    assert all("slug" in o and "rotulo" in o for o in ops)
    slugs = {o["slug"] for o in ops}
    assert slugs <= set(perfis.slugs())      # nada fora de perfis.py
    assert "gerente" not in slugs            # órfão antigo — nunca foi slug de perfis.py
    assert "gerencial" in slugs              # perfil real (Perfil-4)
    assert "super_admin" not in slugs


def test_func_sync_acesso_valida_contra_perfis_py(app_db):
    db = app_db.get_session()
    # Funcionario.loja_id é FK real (lojas.id) — cria a loja de verdade em vez do literal `1`.
    loja = app_db.Loja(nome="Loja Perfis Fonte Unica")
    db.add(loja); db.flush()
    f = app_db.Funcionario(loja_id=loja.id, nome="Fulano", status="ativo")
    db.add(f); db.flush()
    # slug órfão antigo → rejeitado
    ok, err = mod_cadastro.func_sync_acesso(
        db, f, {"acesso": {"tem_acesso": True, "email": "a@loja.com", "perfil": "gerente"}})
    assert ok is False and "inválido" in (err or "").lower()
    # slug real de perfis.py → aceito (cria a conta com nivel válido)
    ok2, err2 = mod_cadastro.func_sync_acesso(
        db, f, {"acesso": {"tem_acesso": True, "email": "b@loja.com", "perfil": "gerencial"}})
    assert ok2 is True, err2
    u = db.get(app_db.Usuario, f.usuario_id)
    assert u.nivel == "gerencial" and perfis.existe(u.nivel)
    db.close()


def test_perfis_carregar_derivado_de_perfis_py_sem_senha_hardcoded():
    d = storage.perfis_carregar()
    # valores de permissão vêm de perfis.py (não do JSON legado)
    assert d["perfis"]["consultor"]["desconto_max_pct"] == perfis.desconto_max("consultor")
    assert d["perfis"]["gerente"]["desconto_max_pct"] == perfis.desconto_max("gerente_vendas")
    assert d["perfis"]["diretoria"]["desconto_max_pct"] == perfis.desconto_max("diretor")
    # nenhuma senha embutida no config derivado
    assert "senha_gerente" not in json.dumps(d)
