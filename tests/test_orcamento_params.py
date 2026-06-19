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
