import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mod_orcamento_params import MARGENS_DEFAULT, merge_margens, sanear_descontos


def test_merge_usa_defaults_quando_vazio():
    out = merge_margens({}, {})
    assert out == MARGENS_DEFAULT
    assert out["carga_trib"] == 8.0
    assert out["incluir_custos"] is False


def test_merge_atualiza_apenas_enviados_preservando_resto():
    atual = dict(MARGENS_DEFAULT, comissao_arq_pct=10.0, comissao_arq_ativa=True)
    out = merge_margens(atual, {"desconto_pct": 5})
    assert out["desconto_pct"] == 5.0
    assert out["comissao_arq_pct"] == 10.0
    assert out["comissao_arq_ativa"] is True


def test_merge_coage_tipos():
    out = merge_margens({}, {"desconto_pct": "12.5", "fora_da_sede": 1, "brinde": "300"})
    assert out["desconto_pct"] == 12.5
    assert out["fora_da_sede"] is True
    assert out["brinde"] == 300.0


def test_sanear_descontos_filtra_ids_fora_do_orcamento():
    out = sanear_descontos({"1": 5, "2": 10, "99": 50}, ids_validos={1, 2})
    assert out == {1: 5.0, 2: 10.0}


def test_sanear_descontos_rejeita_fora_de_faixa():
    with pytest.raises(ValueError):
        sanear_descontos({"1": 150}, ids_validos={1})
    with pytest.raises(ValueError):
        sanear_descontos({"1": -1}, ids_validos={1})


def test_sanear_descontos_aceita_limites():
    out = sanear_descontos({"1": 0, "2": 100}, ids_validos={1, 2})
    assert out == {1: 0.0, 2: 100.0}


def test_merge_coage_bool_string_falsy():
    out = merge_margens({}, {"fora_da_sede": "false", "brinde_ativo": "0"})
    assert out["fora_da_sede"] is False
    assert out["brinde_ativo"] is False
    out2 = merge_margens({}, {"fora_da_sede": "true", "brinde_ativo": "on"})
    assert out2["fora_da_sede"] is True
    assert out2["brinde_ativo"] is True


def test_sanear_descontos_rejeita_nan():
    import math
    with pytest.raises(ValueError):
        sanear_descontos({"1": math.nan}, ids_validos={1})


def test_parametros_default_tem_12_chaves_estruturais():
    from mod_orcamento_params import PARAMETROS_DEFAULT
    assert set(PARAMETROS_DEFAULT) == {
        "incluir_custos", "comissao_arq_pct", "comissao_arq_ativa",
        "fidelidade_pct", "fidelidade_ativa", "fora_da_sede", "custo_viagem",
        "brinde", "brinde_ativo", "custo_especial", "custo_especial_ativo", "carga_trib"}
    assert "desconto_pct" not in PARAMETROS_DEFAULT
    assert PARAMETROS_DEFAULT["carga_trib"] == 8.0


def test_parametros_default_loja_inclui_custos_por_padrao():
    # Padrão inicial de um projeto novo: o toggle "incluir custos adicionais" nasce ON.
    from mod_orcamento_params import parametros_default_loja
    out = parametros_default_loja({})
    assert out["incluir_custos"] is True


def test_parametros_default_loja_herda_pcts_e_mantem_incluir_custos():
    from mod_orcamento_params import parametros_default_loja
    out = parametros_default_loja(
        {"defaults_negociacao": {"comissao_arq_pct": 6, "fidelidade_pct": 2, "carga_trib_pct": 9}})
    assert out["comissao_arq_pct"] == 6.0
    assert out["fidelidade_pct"] == 2.0
    assert out["carga_trib"] == 9.0
    assert out["incluir_custos"] is True


def test_merge_parametros_coage_e_preserva():
    from mod_orcamento_params import merge_parametros, PARAMETROS_DEFAULT
    atual = dict(PARAMETROS_DEFAULT, comissao_arq_pct=10.0)
    out = merge_parametros(atual, {"brinde": "300", "fora_da_sede": "true"})
    assert out["brinde"] == 300.0
    assert out["fora_da_sede"] is True
    assert out["comissao_arq_pct"] == 10.0      # preservado
    assert "desconto_pct" not in out            # estruturais não incluem desconto


def test_merge_custo_especial_coage_tipos():
    from mod_orcamento_params import merge_parametros, merge_margens, PARAMETROS_DEFAULT
    out = merge_parametros(dict(PARAMETROS_DEFAULT), {"custo_especial": "1000", "custo_especial_ativo": "true"})
    assert out["custo_especial"] == 1000.0 and out["custo_especial_ativo"] is True
    out2 = merge_margens({}, {"custo_especial": 250, "custo_especial_ativo": 1})
    assert out2["custo_especial"] == 250.0 and out2["custo_especial_ativo"] is True
