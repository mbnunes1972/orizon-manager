from mod_fin.cartao import calcular


def test_6x_sem_entrada():
    r = calcular(10000, 0, 6, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['taxa_retencao_pct'] - 5.65)    < 0.001
    assert abs(r['valor_liberado']    - 10000)   < 1
    assert abs(r['total_cliente']     - 10598.83) < 1
    assert abs(r['valor_parcela']     - 1766.47) < 0.1


def test_6x_com_entrada_2k():
    r = calcular(10000, 2000, 6, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['valor_liberado']  - 10000)    < 1
    assert abs(r['total_cliente']   - 10479.07) < 1
    assert abs(r['valor_parcela']   - 1413.18)  < 0.1


def test_1x_a_vista():
    r = calcular(10000, 0, 1, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['taxa_retencao_pct'] - 2.85)   < 0.001
    assert abs(r['valor_liberado']    - 10000)  < 1
    assert abs(r['total_cliente']     - 10293.59) < 1


def test_prazo_maior_aumenta_retencao():
    r1  = calcular(10000, 0,  1, '2026-06-01')
    r12 = calcular(10000, 0, 12, '2026-06-01')
    assert r12['taxa_retencao_pct'] > r1['taxa_retencao_pct']


def test_prazo_maximo():
    r = calcular(10000, 0, 21, '2026-06-01')
    assert r['ok'] == True
    assert abs(r['taxa_retencao_pct'] - 13.16) < 0.001
    assert abs(r['valor_liberado']    - 10000) < 1


def test_entrada_invalida():
    r = calcular(10000, 10000, 6, '2026-06-01')
    assert r['ok'] == False


def test_n_parcelas_invalido():
    r = calcular(10000, 0, 22, '2026-06-01')
    assert r['ok'] == False


def test_valor_liberado_igual_valor_avista():
    """Invariante central: loja sempre recebe exatamente valor_avista."""
    for n in (1, 6, 12, 21):
        r = calcular(20000, 0, n, '2026-06-01')
        assert r['ok'], f"falhou n={n}"
        assert abs(r['valor_liberado'] - 20000) < 1, \
            f"valor_liberado={r['valor_liberado']} != 20000 (n={n})"
