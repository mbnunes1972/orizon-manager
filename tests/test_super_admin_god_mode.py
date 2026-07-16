"""super_admin = acesso pleno e irrestrito (god-mode): ignora todos os gates de
capacidade e de módulo/painel; opera dentro de qualquer loja (loja do header)."""
from auth import perfis
import mod_tenancy


def test_super_admin_pode_qualquer_capacidade():
    # capacidades reais e uma inexistente — super_admin nunca é barrado
    for cap in ("gerir_usuarios", "gerir_perfis", "acesso_operacional",
                "acesso_financeiro", "acesso_fiscal", "autorizar",
                "ver_parametros", "editar_dados_loja", "capacidade_que_nao_existe"):
        assert perfis.pode("super_admin", cap) is True, cap


def test_super_admin_acessa_todo_modulo_e_painel():
    for mod in ("cadastro", "comercial", "financeiro", "folha", "fiscal",
                "estoque", "expedicao", "montagem", "assistencias"):
        assert perfis.acessa_modulo("super_admin", mod) is True, mod
    assert perfis.acessa_painel("super_admin", "admin") is True
    assert perfis.acessa_painel("super_admin", "config") is True


def test_bypass_nao_vaza_para_outros_perfis():
    # operador continua barrado onde já era barrado (não abre buraco lateral)
    assert perfis.pode("operador", "gerir_perfis") is False
    assert perfis.acessa_modulo("operador", "financeiro") is False
    assert perfis.acessa_painel("operador", "admin") is False
