import mod_provisoes


def test_default_tem_estrutura_completa():
    c = mod_provisoes.config_financeira_default()
    assert set(c.keys()) == {"defaults_negociacao", "provisoes", "comissao_vendas"}
    assert c["provisoes"]["frete_fab_pct"] == 0.0
    assert c["comissao_vendas"]["limitador_desconto"]["ativo"] is False


def test_validar_aceita_default():
    assert mod_provisoes.validar_config_financeira(mod_provisoes.config_financeira_default()) == []


def test_validar_rejeita_percentual_negativo():
    c = mod_provisoes.config_financeira_default()
    c["provisoes"]["com_adm_pct"] = -1.0
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros and any("negativ" in e.lower() for e in erros)


def test_validar_rejeita_faixa_sem_pct():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [{"venda_ate": 1000.0}]
    erros = mod_provisoes.validar_config_financeira(c)
    assert erros


def _cfg_comissao():
    c = mod_provisoes.config_financeira_default()
    c["comissao_vendas"]["faixas_comissao"] = [
        {"venda_ate": 10000.0, "pct": 1.0},   # < 10k
        {"venda_ate": 30000.0, "pct": 2.0},   # 10k–30k
        {"venda_ate": None,    "pct": 3.0},   # ≥ 30k
    ]
    c["comissao_vendas"]["limitador_desconto"] = {
        "ativo": True, "base_desconto": "Desc_Orc",
        "limites": [{"desconto_acima_de": 5.0, "redutor_pct": 50.0},
                    {"desconto_acima_de": 10.0, "redutor_pct": 80.0}],
    }
    return c


def test_faixa_por_venda():
    c = _cfg_comissao()
    assert mod_provisoes.resolver_comissao_venda(c, 5000.0, 0.0) == 1.0
    assert mod_provisoes.resolver_comissao_venda(c, 20000.0, 0.0) == 2.0
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 0.0) == 3.0


def test_redutor_por_desconto():
    c = _cfg_comissao()
    # faixa 3% (venda 50k), desconto 12% > 10% → redutor 80% → 3 × 0.2 = 0.6
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 0.6
    # desconto 7% → redutor 50% → 3 × 0.5 = 1.5
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 7.0) == 1.5


def test_limitador_desligado_nao_reduz():
    c = _cfg_comissao()
    c["comissao_vendas"]["limitador_desconto"]["ativo"] = False
    assert mod_provisoes.resolver_comissao_venda(c, 50000.0, 12.0) == 3.0


def test_provisoes_e_margem():
    siglas = {"CFO": 1000.0, "Val_Liq": 2000.0, "VAVO": 2500.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    c["provisoes"].update({"frete_fab_pct": 10.0, "com_adm_pct": 5.0,
                           "frete_loc_pct": 2.0})
    r = mod_provisoes.provisoes_orcamento(siglas, c, out_forn=300.0, com_venda_pct=1.0)
    assert r["Frete_Fab_Orc"] == 100.0      # 10% × 1000 CFO
    assert r["Com_Adm_Orc"] == 100.0        # 5% × 2000 Val_Liq
    assert r["Com_Venda_Orc"] == 20.0       # 1% × 2000 Val_Liq
    assert r["Frete_Loc_Orc"] == 50.0       # 2% × 2500 VAVO
    assert r["Out_Forn"] == 300.0
    # Cust_Var = 1000 CFO + 300 Out + 100 + 100 + 20 + 0 + 0 + 50 + 0 + 0 + 0 Prov_Imp = 1570
    assert r["Cust_Var"] == 1570.0
    # Marg_Cont = (2000 - 1570)/2000 = 0.215
    assert r["Marg_Cont"] == 0.215


def test_margem_negativa_e_val_liq_zero():
    siglas = {"CFO": 5000.0, "Val_Liq": 1000.0, "VAVO": 1000.0, "Prov_Imp": 0.0}
    c = mod_provisoes.config_financeira_default()
    r = mod_provisoes.provisoes_orcamento(siglas, c)
    assert r["Marg_Cont"] < 0                       # Cust_Var (5000) > Val_Liq (1000)
    siglas0 = {"CFO": 0.0, "Val_Liq": 0.0, "VAVO": 0.0, "Prov_Imp": 0.0}
    assert mod_provisoes.provisoes_orcamento(siglas0, c)["Marg_Cont"] == 0.0
