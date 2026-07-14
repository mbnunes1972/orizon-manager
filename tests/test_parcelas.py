"""TDD da Fatia 2 — lógica pura de congelamento de parcela (decisão #5 do spec
2026-07-13-desmembramento-pe-parcial-design.md).

Invariante central: Σ val_cont_congelado == round(Val_Cont, 2) EXATO (ao centavo),
com a última parcela (maior ordem) absorvendo o resto do arredondamento.
"""
import pytest

from mod_parcelas import (
    congelar_parcelas,
    exige_aprovacao_diretor,
    validar_particao_parcelas,
    LIMITE_AF1_DEFAULT,
    LIMITE_AF2_DEFAULT,
)


def _soma(res):
    return round(sum(p["val_cont_congelado"] for p in res), 2)


def test_duas_parcelas_soma_exata_e_fracao():
    # Val_Cont 3000; parcela 1 = ambientes (600+400=1000), parcela 2 = (2000)
    res = congelar_parcelas([[600.0, 400.0], [2000.0]], 3000.0)
    assert [p["ordem"] for p in res] == [1, 2]
    assert res[0]["fracao_val_cont"] == pytest.approx(1000.0 / 3000.0)
    assert res[1]["fracao_val_cont"] == pytest.approx(2000.0 / 3000.0)
    # invariante: soma exata ao centavo
    assert _soma(res) == 3000.00
    # a 1ª parcela é arredondada; a última fecha a conta
    assert res[0]["val_cont_congelado"] == 1000.00
    assert res[1]["val_cont_congelado"] == 2000.00


def test_ultima_parcela_absorve_resto_de_centavo():
    # Val_Cont 100.00 dividido em 3 ambientes com dízima (33,33 / 33,33 / 33,34)
    res = congelar_parcelas([[33.33], [33.33], [33.34]], 100.00)
    # naive: 33.33 + 33.33 + 33.33 = 99.99 -> a última leva o resto e fecha 100.00
    assert _soma(res) == 100.00
    assert res[2]["val_cont_congelado"] == round(100.00 - res[0]["val_cont_congelado"] - res[1]["val_cont_congelado"], 2)


def test_valcont_com_dizima_fecha_exato():
    # força divergência de arredondamento: Val_Cont 100.01, duas parcelas 50.00/50.01
    res = congelar_parcelas([[50.00], [50.01]], 100.01)
    assert _soma(res) == 100.01
    # a última parcela = Val_Cont - anteriores (resto), não o round direto
    assert res[-1]["val_cont_congelado"] == round(100.01 - res[0]["val_cont_congelado"], 2)


def test_parcela_unica_leva_val_cont_inteiro():
    res = congelar_parcelas([[1234.56]], 5000.00)
    assert len(res) == 1
    assert res[0]["val_cont_congelado"] == 5000.00   # única = última = resto inteiro
    assert res[0]["ordem"] == 1


def test_val_cont_zero_ou_negativo_retorna_zeros_sem_dividir():
    res = congelar_parcelas([[100.0], [200.0]], 0.0)
    assert _soma(res) == 0.00
    assert all(p["fracao_val_cont"] == 0.0 for p in res)
    assert all(p["val_cont_congelado"] == 0.0 for p in res)


def test_lista_vazia_retorna_vazio():
    assert congelar_parcelas([], 3000.0) == []


# ── #10 — gate de Aprovação Financeira (step-up do Diretor acima do limite) ──

def test_gate_aumento_dentro_do_limite_nao_exige_diretor():
    # +0,5% com limite 1% → não exige
    assert exige_aprovacao_diretor(10000.0, 10050.0, LIMITE_AF1_DEFAULT) is False


def test_gate_aumento_acima_do_limite_exige_diretor():
    # +2% com limite 1% → exige
    assert exige_aprovacao_diretor(10000.0, 10200.0, LIMITE_AF1_DEFAULT) is True


def test_gate_exatamente_no_limite_nao_exige():
    # +1% exato com limite 1% → estritamente maior, então NÃO exige
    assert exige_aprovacao_diretor(10000.0, 10100.0, LIMITE_AF1_DEFAULT) is False


def test_gate_reducao_ou_igual_nunca_exige():
    assert exige_aprovacao_diretor(10000.0, 9000.0, LIMITE_AF1_DEFAULT) is False
    assert exige_aprovacao_diretor(10000.0, 10000.0, LIMITE_AF1_DEFAULT) is False


def test_gate_base_zero_com_aumento_exige():
    assert exige_aprovacao_diretor(0.0, 500.0, LIMITE_AF2_DEFAULT) is True


def test_gate_limite_af2_mais_folgado():
    # +1,5%: passa do limite AF1 (1%) mas não do AF2 (2%)
    assert exige_aprovacao_diretor(10000.0, 10150.0, LIMITE_AF1_DEFAULT) is True
    assert exige_aprovacao_diretor(10000.0, 10150.0, LIMITE_AF2_DEFAULT) is False


# ── #1 — partição do pool em parcelas ──

def test_particao_valida():
    ok, erro = validar_particao_parcelas([1, 2, 3, 4], [[1, 2], [3, 4]])
    assert ok is True and erro is None


def test_particao_sobreposicao_rejeitada():
    ok, erro = validar_particao_parcelas([1, 2, 3], [[1, 2], [2, 3]])
    assert ok is False and "mais de uma parcela" in erro


def test_particao_com_sobra_rejeitada():
    ok, erro = validar_particao_parcelas([1, 2, 3, 4], [[1, 2], [3]])   # 4 fora
    assert ok is False and "fora de qualquer parcela" in erro


def test_particao_ambiente_estranho_ao_pool_rejeitado():
    ok, erro = validar_particao_parcelas([1, 2], [[1], [2, 99]])
    assert ok is False and "não pertence ao pool" in erro


def test_particao_parcela_vazia_rejeitada():
    ok, erro = validar_particao_parcelas([1, 2], [[1, 2], []])
    assert ok is False and "vazia" in erro


def test_particao_sem_parcelas_rejeitada():
    ok, erro = validar_particao_parcelas([1, 2], [])
    assert ok is False
