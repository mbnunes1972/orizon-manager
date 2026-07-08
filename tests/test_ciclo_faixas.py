import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_ciclo as mc


def test_faixa_por_etapa_cobre_principais():
    for cod in [c for c in mc.ETAPAS_PRINCIPAIS]:
        assert mc.faixa_da_etapa(cod) is not None, f"etapa {cod} sem faixa"


def test_faixas_conhecidas():
    assert mc.faixa_da_etapa("1") == "vendas"
    assert mc.faixa_da_etapa("7") == "vendas"
    assert mc.faixa_da_etapa("8") == "gate_financeiro_1"
    assert mc.faixa_da_etapa("11d") == "gate_financeiro_2"
    assert mc.faixa_da_etapa("11a") == "execucao_projeto"
    assert mc.faixa_da_etapa("13") == "expedicao"
    assert mc.faixa_da_etapa("18") == "montagem"


def test_gates_sao_faixas_de_gate():
    for g in mc.ETAPAS_APROVACAO_FINANCEIRA:
        assert mc.faixa_da_etapa(g).startswith("gate_")


def test_faixa_desconhecida_none():
    assert mc.faixa_da_etapa("999") is None
