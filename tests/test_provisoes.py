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
