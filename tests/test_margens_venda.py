"""As três margens da venda (mod_provisoes.margens_venda) — prova de que compartilham o
mesmo numerador (margem em R$) sobre bases crescentes val_liq_loja < VAVO < val_cont.
"""
import mod_provisoes as mp


def test_tres_margens_mesmo_numerador_bases_crescentes():
    # VAVO 10000; cust_ad 1000 (custos adicionais); cust_var 6000; cust_fin 500 → val_cont 10500
    r = mp.margens_venda(vavo=10000.0, cust_ad=1000.0, cust_var=6000.0, val_cont=10500.0)
    # margem em R$ = VAVO - cust_ad - cust_var = 10000 - 1000 - 6000 = 3000
    assert r["margem_rs"] == 3000.0
    # bases: val_liq_loja = 9000; VAVO = 10000; val_cont = 10500
    assert r["margem_loja"] == round(3000.0 / 9000.0, 4)      # 0.3333
    assert r["margem_venda"] == round(3000.0 / 10000.0, 4)    # 0.3000
    assert r["margem_contrato"] == round(3000.0 / 10500.0, 4) # 0.2857
    # invariante: bases crescentes → margens decrescentes
    assert r["margem_loja"] > r["margem_venda"] > r["margem_contrato"]


def test_margem_contrato_neutraliza_o_custo_financeiro():
    # provar M3 = (val_cont - cust_var - cust_ad - cust_fin)/val_cont, com cust_fin cancelando
    vavo, cust_ad, cust_var, cust_fin = 8000.0, 500.0, 5000.0, 300.0
    val_cont = vavo + cust_fin
    r = mp.margens_venda(vavo, cust_ad, cust_var, val_cont)
    esperado_m3 = round((val_cont - cust_var - cust_ad - cust_fin) / val_cont, 4)
    assert r["margem_contrato"] == esperado_m3
    assert r["margem_rs"] == round(vavo - cust_ad - cust_var, 2)  # 2500


def test_bases_zero_nao_dividem():
    r = mp.margens_venda(vavo=0.0, cust_ad=0.0, cust_var=0.0, val_cont=0.0)
    assert r["margem_loja"] == 0.0 and r["margem_venda"] == 0.0 and r["margem_contrato"] == 0.0
