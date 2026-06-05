from mod_margens import calcular_margens


def test_desconto_10pct():
    r = calcular_margens(100000, desconto_pct=10)
    assert abs(r['valor_final'] - 90000) < 1


def test_sem_desconto():
    r = calcular_margens(100000, desconto_pct=0)
    assert abs(r['valor_final'] - 100000) < 1


def test_desconto_total():
    r = calcular_margens(100000, desconto_pct=100)
    assert r['valor_final'] == 0


def test_comissao_arq():
    r = calcular_margens(100000, desconto_pct=0,
                         comissao_arq_pct=5, comissao_arq_ativa=True)
    assert abs(r['valor_final'] - 95000) < 1


def test_fidelidade():
    r = calcular_margens(100000, desconto_pct=0,
                         fidelidade_pct=3, fidelidade_ativa=True)
    assert abs(r['valor_final'] - 97000) < 1


def test_desconto_e_arq_sequencial():
    """Desconto aplicado antes da comissão."""
    r = calcular_margens(100000, desconto_pct=10,
                         comissao_arq_pct=5, comissao_arq_ativa=True)
    esperado = 100000 * 0.9 * 0.95
    assert abs(r['valor_final'] - esperado) < 1


def test_brinde():
    r = calcular_margens(100000, desconto_pct=0,
                         brinde=500, brinde_ativo=True)
    assert abs(r['valor_final'] - 99500) < 1
