"""Fatia B — classificação do ramo de financiamento por modalidade (mod_fin.ramo_financiamento).
financeira (Aymoré/Cartão) = despesa; loja (Venda Programada/Total Flex) = receita própria; avista = nada.
"""
import mod_fin


def test_aymore_e_cartao_sao_financeira():
    assert mod_fin.ramo_financiamento("aymore") == "financeira"
    assert mod_fin.ramo_financiamento("cartao_credito") == "financeira"
    assert mod_fin.ramo_financiamento("cartao_credito_x") == "financeira"


def test_venda_programada_e_total_flex_sao_loja():
    assert mod_fin.ramo_financiamento("venda_programada") == "loja"
    assert mod_fin.ramo_financiamento("total_flex") == "loja"


def test_a_vista_e_avista():
    assert mod_fin.ramo_financiamento("a_vista") == "avista"


def test_codigo_desconhecido_default_loja_conservador():
    # default 'loja' = sem despesa (conservador: não inventa despesa financeira)
    assert mod_fin.ramo_financiamento("modalidade_nova_qualquer") == "loja"
