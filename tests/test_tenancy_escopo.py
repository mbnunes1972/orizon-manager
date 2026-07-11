# tests/test_tenancy_escopo.py
import mod_tenancy as mt

SUPER = {"nivel": "super_admin", "loja_id": None, "rede_id": None}
ADMR  = {"nivel": "admin_rede",  "loja_id": None, "rede_id": 1}
DIR   = {"nivel": "diretoria",     "loja_id": 10,   "rede_id": None}

LOJA_R1 = {"id": 10, "rede_id": 1}
LOJA_R2 = {"id": 20, "rede_id": 2}
LOJA_AVULSA = {"id": 30, "rede_id": None}


def test_pode_ver_rede():
    assert mt.pode_ver_rede(SUPER, 1) is True
    assert mt.pode_ver_rede(SUPER, 99) is True
    assert mt.pode_ver_rede(ADMR, 1) is True
    assert mt.pode_ver_rede(ADMR, 2) is False
    assert mt.pode_ver_rede(DIR, 1) is False


def test_pode_editar_dados_rede():
    # auditoria A6: editar config da rede exige capacidade de edição + escopo da rede.
    assert mt.pode_editar_dados_rede(SUPER, 1) is True
    assert mt.pode_editar_dados_rede(SUPER, 99) is True
    assert mt.pode_editar_dados_rede(ADMR, 1) is True
    assert mt.pode_editar_dados_rede(ADMR, 2) is False     # outra rede
    assert mt.pode_editar_dados_rede(DIR, 1) is False      # diretor não enxerga a rede
    # gerente adm/fin não tem editar_dados_loja → nunca edita config de rede
    assert mt.pode_editar_dados_rede({"nivel": "consultor", "rede_id": 1}, 1) is False


def test_pode_ver_loja():
    assert mt.pode_ver_loja(SUPER, LOJA_R2) is True
    assert mt.pode_ver_loja(SUPER, LOJA_AVULSA) is True
    assert mt.pode_ver_loja(ADMR, LOJA_R1) is True
    assert mt.pode_ver_loja(ADMR, LOJA_R2) is False
    assert mt.pode_ver_loja(ADMR, LOJA_AVULSA) is False
    assert mt.pode_ver_loja(DIR, LOJA_R1) is True
    assert mt.pode_ver_loja(DIR, LOJA_R2) is False


def test_pode_editar_dados_loja():
    assert mt.pode_editar_dados_loja(SUPER, LOJA_R2) is True
    assert mt.pode_editar_dados_loja(ADMR, LOJA_R1) is True
    assert mt.pode_editar_dados_loja(ADMR, LOJA_R2) is False
    assert mt.pode_editar_dados_loja(DIR, LOJA_R1) is True
    assert mt.pode_editar_dados_loja(DIR, LOJA_R2) is False
    consultor = {"nivel": "consultor", "loja_id": 10, "rede_id": None}
    assert mt.pode_editar_dados_loja(consultor, LOJA_R1) is False


def test_atribuir_tenant_super_admin():
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "super_admin"}) == (None, None, [])
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "admin_rede", "rede_id": 5}) == (None, 5, [])
    loja_id, rede_id, erros = mt.atribuir_tenant_usuario(SUPER, {"nivel": "admin_rede"})
    assert erros and rede_id is None
    assert mt.atribuir_tenant_usuario(SUPER, {"nivel": "diretoria", "loja_id": 30}) == (30, None, [])


def test_atribuir_tenant_admin_rede():
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "diretoria", "loja_id": 10}) == (10, None, [])
    # admin_rede agora cria PAR admin_rede (herda a própria rede); super_admin segue bloqueado
    assert mt.atribuir_tenant_usuario(ADMR, {"nivel": "admin_rede"}) == (None, 1, [])
    _, _, e_super = mt.atribuir_tenant_usuario(ADMR, {"nivel": "super_admin"})
    assert e_super


def test_atribuir_tenant_diretor_herda_propria_loja():
    assert mt.atribuir_tenant_usuario(DIR, {"nivel": "consultor", "loja_id": 999}) == (10, None, [])
    _, _, e = mt.atribuir_tenant_usuario(DIR, {"nivel": "super_admin"})
    assert e
