from mod_fin.aymore import calcular


def test_8x_20d_sem_entrada():
    r = calcular(100000, 0, 8, 20, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['taxa_retencao_pct'] - 9.2755) < 0.001
    assert abs(r['valor_liberado']   - 100000)  < 1
    assert abs(r['total_cliente']    - 110223.82) < 1
    assert abs(r['valor_parcela']    - 13777.98) < 0.1


def test_8x_20d_com_entrada_20k():
    r = calcular(100000, 20000, 8, 20, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['valor_liberado']  - 100000)    < 1
    assert abs(r['total_cliente']   - 108179.05) < 1
    assert abs(r['financiado']      - 88179.05)  < 0.5


def test_carencia_maior_aumenta_retencao():
    r30 = calcular(100000, 0, 8, 30, '2026-06-01')
    r60 = calcular(100000, 0, 8, 60, '2026-06-01')
    assert r60['taxa_retencao_pct'] > r30['taxa_retencao_pct']


def test_carencia_menor_diminui_retencao():
    r30 = calcular(100000, 0, 8, 30, '2026-06-01')
    r15 = calcular(100000, 0, 8, 15, '2026-06-01')
    assert r15['taxa_retencao_pct'] < r30['taxa_retencao_pct']


def test_parcelas_maximas():
    r = calcular(100000, 0, 24, 30, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['valor_liberado'] - 100000) < 1
    assert abs(r['valor_parcela']  - 5600.98) < 0.1


def test_1_parcela():
    r = calcular(100000, 0, 1, 30, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['taxa_retencao_pct'] - 4.2046) < 0.001
    assert abs(r['valor_liberado'] - 100000) < 1


def test_entrada_invalida():
    r = calcular(100000, 100000, 8, 30, '2026-06-01')
    assert r['ok'] == False


def test_n_parcelas_invalido():
    r = calcular(100000, 0, 25, 30, '2026-06-01')
    assert r['ok'] == False


def test_carencia_invalida():
    r = calcular(100000, 0, 8, 5, '2026-06-01')
    assert r['ok'] == False


def test_valor_liberado_igual_valor_avista():
    """Invariante central: loja sempre recebe exatamente valor_avista."""
    for n in (1, 8, 12, 24):
        for car in (15, 30, 60, 120):
            r = calcular(50000, 0, n, car, '2026-06-01')
            assert r['ok'], f"falhou n={n} car={car}"
            assert abs(r['valor_liberado'] - 50000) < 1, \
                f"valor_liberado={r['valor_liberado']} != 50000 (n={n}, car={car})"
