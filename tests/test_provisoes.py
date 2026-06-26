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
