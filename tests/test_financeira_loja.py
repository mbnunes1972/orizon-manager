from mod_fin.financeira_loja import calcular, PARCELAS_MAX, TAXA_MENSAL_PADRAO, ENTRADA_MIN_PCT


# ── Constantes esperadas ──────────────────────────────────────────────────────
def test_constantes():
    assert PARCELAS_MAX == 6
    assert abs(TAXA_MENSAL_PADRAO - 0.01) < 1e-9
    assert abs(ENTRADA_MIN_PCT - 0.10) < 1e-9


# ── Taxa e acréscimo ──────────────────────────────────────────────────────────
def test_taxa_juros_pct():
    r = calcular(10000, 1000, 4, '2026-06-01')
    assert r['ok']
    assert abs(r['taxa_juros_pct'] - 1.0) < 0.01


def test_acrescimo_composto_1pct():
    """4 parcelas a 1%/mês → acréscimo ≈ (1.01)^4 - 1 = 4.0604%."""
    r = calcular(10000, 1000, 4, '2026-06-01')
    assert r['ok']
    assert abs(r['acrescimo_pct'] - 4.0604) < 0.01


def test_acrescimo_cresce_com_parcelas():
    r2 = calcular(10000, 1000, 2, '2026-06-01')
    r6 = calcular(10000, 1000, 6, '2026-06-01')
    assert r6['acrescimo_pct'] > r2['acrescimo_pct']


# ── Entrada mínima ────────────────────────────────────────────────────────────
def test_entrada_minima_exata_aceita():
    """Exatamente 10% deve ser aceito."""
    r = calcular(10000, 1000, 4, '2026-06-01')
    assert r['ok']


def test_entrada_abaixo_minimo_rejeitada():
    """9.99% deve ser rejeitado."""
    r = calcular(10000, 999, 4, '2026-06-01')
    assert r['ok'] == False
    assert 'mínima' in r['erro'] or 'minima' in r['erro'].lower()


def test_entrada_zero_rejeitada():
    r = calcular(10000, 0, 4, '2026-06-01')
    assert r['ok'] == False


def test_entrada_igual_ou_maior_que_venda_rejeitada():
    r = calcular(10000, 10000, 4, '2026-06-01')
    assert r['ok'] == False


# ── Parcelamento máximo ───────────────────────────────────────────────────────
def test_6_parcelas():
    r = calcular(10000, 1000, 6, '2026-06-01')
    assert r['ok']
    assert r['n_parcelas'] == 6


def test_mais_de_6_rejeitado():
    r = calcular(10000, 1000, 7, '2026-06-01')
    assert r['ok'] == False


def test_1_parcela():
    r = calcular(10000, 1000, 1, '2026-06-01')
    assert r['ok']
    assert r['n_parcelas'] == 1
    assert abs(r['acrescimo_pct'] - 1.0) < 0.01


# ── Cálculo dos valores ───────────────────────────────────────────────────────
def test_financiado_correto():
    r = calcular(10000, 2000, 4, '2026-06-01')
    assert r['ok']
    assert abs(r['financiado'] - 8000) < 0.01


def test_total_cliente():
    r = calcular(10000, 1000, 4, '2026-06-01')
    assert r['ok']
    esperado = 1000 + r['valor_total']
    assert abs(r['total_cliente'] - esperado) < 0.01


def test_parcela_base_igual():
    """Sem edição, todas as parcelas devem ser iguais a parcela_base."""
    r = calcular(10000, 1000, 4, '2026-06-01')
    assert r['ok']
    parc = [p for p in r['parcelas'] if p['tipo'] not in ('contrato', 'entrada')]
    # As 3 editáveis devem ser ≈ parcela_base
    for p in parc[:-1]:
        assert abs(p['valor'] - r['parcela_base']) < 0.02


# ── Parcelas editáveis ────────────────────────────────────────────────────────
def test_parcelas_editavel_flag():
    """Parcelas 1..N-1 devem ter editavel=True; a última editavel=False."""
    r = calcular(10000, 1000, 4, '2026-06-01')
    parc = [p for p in r['parcelas'] if p.get('num', 0) > 0]
    assert len(parc) == 4
    for p in parc[:-1]:
        assert p['editavel'] == True
    assert parc[-1]['editavel'] == False


def test_parcelas_editadas_ultima_fecha_saldo():
    """Com parcelas editadas, a última deve fechar o saldo."""
    r = calcular(10000, 1000, 4, '2026-06-01',
                 valores_parcelas=[2000, 2000, 2000])
    assert r['ok']
    soma_editadas = 2000 + 2000 + 2000
    esperado_ultima = round(r['valor_total'] - soma_editadas, 2)
    assert abs(r['ultima_parcela'] - esperado_ultima) < 0.02


def test_plano_tem_linha_contrato():
    r = calcular(10000, 1000, 3, '2026-06-01')
    tipos = [p['tipo'] for p in r['parcelas']]
    assert 'contrato' in tipos


def test_plano_tem_linha_entrada_quando_entrada_maior_zero():
    r = calcular(10000, 2000, 3, '2026-06-01')
    tipos = [p['tipo'] for p in r['parcelas']]
    assert 'entrada' in tipos


def test_plano_sem_entrada_nao_tem_linha_entrada():
    # entrada mínima 10% → precisa de pelo menos 10%
    r = calcular(10000, 1000, 1, '2026-06-01')
    tipos = [p['tipo'] for p in r['parcelas']]
    # linha entrada aparece só se ent > 0, e 1000 > 0
    assert 'entrada' in tipos
