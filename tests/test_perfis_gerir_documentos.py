import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from auth import perfis


def test_master_pode():
    assert perfis.pode("master", "gerir_documentos") is True


def test_gerencial_e_operador_nao_podem():
    """Trocar cláusula de contrato não vem de brinde com o perfil gerencial."""
    assert perfis.pode("gerencial", "gerir_documentos") is False
    assert perfis.pode("operador", "gerir_documentos") is False


def test_e_selecionavel_por_perfil():
    assert "gerir_documentos" in perfis.CAPS_SELECIONAVEIS


def test_tem_verbete_no_catalogo_de_capacidades():
    v = perfis.CAPACIDADES["gerir_documentos"]
    assert v["rotulo"] and v["descricao"] and v["grupo"]


def test_perfil_desconhecido_nao_pode():
    assert perfis.pode("perfil_que_nao_existe", "gerir_documentos") is False
