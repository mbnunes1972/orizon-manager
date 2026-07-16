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


def test_super_admin_adota_loja_do_header():
    # sem membership e sem loja própria, mas com header → loja ativa = header
    assert mod_tenancy.resolver_loja_ativa([], 5, None, is_super=True) == 5
    # sem header → sem loja ativa (precisa escolher uma loja no console)
    assert mod_tenancy.resolver_loja_ativa([], None, None, is_super=True) is None


def test_resolver_loja_ativa_nao_super_inalterado():
    # comportamento pré-existente preservado p/ usuário de loja
    assert mod_tenancy.resolver_loja_ativa([], 5, None) is None          # header sem acesso → None
    assert mod_tenancy.resolver_loja_ativa([7], None, 7) == 7            # default acessível
    assert mod_tenancy.resolver_loja_ativa([7], 7, None) == 7            # header acessível
