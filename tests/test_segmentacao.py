"""FASE B1 — Segmentação de receita Mercadoria × Serviço.

Val_Cont divide-se em Mercadoria (NF-e produto, 4.1.01) + Serviço (NFS-e, 4.2.01) por um percentual
configurável (default 65/35). É a base da receita segmentada (sem duplicar) e a chave da futura
distribuidora. Funções puras (sem I/O)."""
import pytest
import mod_orcamento_params as mp


def test_default_65_35():
    assert mp.SEGMENTACAO_DEFAULT == {"pct_mercadoria": 65.0, "pct_servico": 35.0}


def test_segmentar_divide_e_fecha_no_val_cont():
    merc, serv = mp.segmentar(1000.0, 65.0)
    assert merc == 650.0 and serv == 350.0
    assert round(merc + serv, 2) == 1000.0


def test_segmentar_resto_absorve_arredondamento():
    """Serviço = resto (Val_Cont − Mercadoria) → soma fecha EXATAMENTE no Val_Cont, sem centavo perdido."""
    merc, serv = mp.segmentar(100.0, 33.33)
    assert round(merc + serv, 2) == 100.0
    assert merc == 33.33 and serv == 66.67


def test_validar_soma_100_ok():
    mp.validar_segmentacao(65.0, 35.0)   # não levanta


def test_validar_soma_diferente_de_100_falha():
    with pytest.raises(ValueError):
        mp.validar_segmentacao(65.0, 30.0)


def test_validar_fora_da_faixa_falha():
    with pytest.raises(ValueError):
        mp.validar_segmentacao(-5.0, 105.0)


def test_resolver_null_cai_no_default():
    assert mp.resolver_segmentacao(None, None) == mp.SEGMENTACAO_DEFAULT
    assert mp.resolver_segmentacao(70.0, 30.0) == {"pct_mercadoria": 70.0, "pct_servico": 30.0}


def test_efetiva_override_do_projeto_vence_a_loja():
    loja = {"pct_mercadoria": 65.0, "pct_servico": 35.0}
    # sem override → herda a loja
    assert mp.segmentacao_efetiva(loja, {}) == loja
    assert mp.segmentacao_efetiva(loja, {"comissao_arq_pct": 5}) == loja
    # com override do Diretor → vence
    ov = {"pct_mercadoria": 80.0, "pct_servico": 20.0}
    assert mp.segmentacao_efetiva(loja, ov) == ov
