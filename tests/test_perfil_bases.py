from auth import perfis


def test_bases_existem_com_caps_finas():
    for slug in ("master", "gerencial", "operador"):
        assert perfis.PERFIS.get(slug), f"base {slug} ausente"
    # Master: topo — todas as finas
    assert perfis.pode("master", "gerir_usuarios") is True
    assert perfis.pode("master", "gerir_perfis") is True
    assert perfis.pode("master", "aprovar_financeiro") is True
    assert perfis.desconto_max("master") == 50.0
    # Gerencial: financeiro sim, mas sem painel admin → sem gerir_usuarios/perfis
    assert perfis.pode("gerencial", "aprovar_financeiro") is True
    assert perfis.pode("gerencial", "gerir_usuarios") is False
    assert perfis.pode("gerencial", "gerir_perfis") is False
    assert perfis.desconto_max("gerencial") == 20.0
    # Operador: base operacional/execução, sem financeiro/admin
    assert perfis.pode("operador", "aprovar_financeiro") is False
    assert perfis.pode("operador", "gerir_usuarios") is False
    assert perfis.pode("operador", "registrar_medicao") is True
    assert perfis.desconto_max("operador") == 10.0
    # Plataforma preservada
    assert perfis.pode("super_admin", "gerir_lojas") is True


def test_gerir_perfis_so_master():
    assert perfis.pode("master", "gerir_perfis") is True
    assert perfis.pode("gerencial", "gerir_perfis") is False
    assert perfis.pode("operador", "gerir_perfis") is False
