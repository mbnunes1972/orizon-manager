# tests/test_perfis_atribuiveis.py
import mod_tenancy as mt

SUPER = {"nivel": "super_admin", "loja_id": None, "rede_id": None}
ADMR  = {"nivel": "admin_rede",  "loja_id": None, "rede_id": 1}
DIR   = {"nivel": "diretoria",     "loja_id": 10,   "rede_id": None}
CONS  = {"nivel": "consultor",   "loja_id": 10,   "rede_id": None}

def test_loja_lista_operacionais_sem_admins():
    for ator in (DIR, ADMR, SUPER):
        lst = mt.perfis_atribuiveis(ator, "loja")
        assert "consultor" in lst and "diretoria" in lst
        assert "super_admin" not in lst and "admin_rede" not in lst

def test_rede_so_admin_rede_e_so_para_super_e_admrede():
    assert mt.perfis_atribuiveis(SUPER, "rede") == ["admin_rede"]
    assert mt.perfis_atribuiveis(ADMR,  "rede") == ["admin_rede"]
    assert mt.perfis_atribuiveis(DIR,   "rede") == []

def test_plataforma_so_super_admin():
    assert mt.perfis_atribuiveis(SUPER, "plataforma") == ["super_admin"]
    assert mt.perfis_atribuiveis(ADMR,  "plataforma") == []

def test_sem_gerir_usuarios_lista_vazia():
    assert mt.perfis_atribuiveis(CONS, "loja") == []

def test_admin_rede_cria_par():
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "admin_rede"}) == (None, 1, [])

def test_admin_rede_nao_cria_super():
    _, _, erros = mt.atribuir_tenant_usuario(ADMR, {"nivel": "super_admin"})
    assert erros
