import perfis


def test_slugs_sao_os_perfis_novos():
    assert set(perfis.slugs()) == {
        "diretoria", "gerencial", "consultor", "suporte", "super_admin", "admin_rede"}
    assert set(perfis.slugs_loja()) == {"diretoria", "gerencial", "consultor", "suporte"}


def test_desconto_max():
    assert perfis.desconto_max("diretoria") == 50.0
    assert perfis.desconto_max("gerencial") == 20.0
    assert perfis.desconto_max("consultor") == 10.0
    assert perfis.desconto_max("suporte") == 0.0
    assert perfis.desconto_max("inexistente") == 0.0      # default seguro


def test_acesso_matriz_modulos_e_paineis():
    # operacionais: Diretoria/Gerencial/Consultor sim; Suporte não
    for p in ("diretoria", "gerencial", "consultor"):
        assert perfis.acessa_modulo(p, "comercial") is True
    assert perfis.acessa_modulo("suporte", "comercial") is False
    # Financeiro/Folha e Fiscal só Diretoria
    for m in ("financeiro", "folha", "fiscal"):
        assert perfis.acessa_modulo("diretoria", m) is True
        for p in ("gerencial", "consultor", "suporte"):
            assert perfis.acessa_modulo(p, m) is False, (p, m)
    # painéis Admin/Config: Diretoria/Gerencial/Suporte sim; Consultor não
    for p in ("diretoria", "gerencial", "suporte"):
        assert perfis.acessa_painel(p, "admin") and perfis.acessa_painel(p, "config")
    assert perfis.acessa_painel("consultor", "admin") is False
    assert perfis.acessa_painel("consultor", "config") is False


def test_capacidades_preservadas():
    assert perfis.pode("diretoria", "autorizar") is True
    assert perfis.pode("gerencial", "autorizar") is True
    assert perfis.pode("consultor", "autorizar") is False
    assert perfis.pode("diretoria", "aprovar_financeiro") is True
    assert perfis.pode("gerencial", "aprovar_financeiro") is False   # Gerencial sem Financeiro
    assert perfis.pode("diretoria", "gerir_usuarios") is True
    assert perfis.pode("suporte", "gerir_usuarios") is True
    assert perfis.pode("consultor", "gerir_usuarios") is False
    # ciclo operacional segue executável (grosseiro) p/ não travar o fluxo
    for p in ("diretoria", "gerencial", "consultor"):
        assert perfis.pode(p, "executar_pe") is True
        assert perfis.pode(p, "registrar_medicao") is True
    assert perfis.pode("suporte", "executar_pe") is False
    assert perfis.pode("inexistente", "gerir_usuarios") is False


def test_rotulo_e_existe():
    assert perfis.rotulo("diretoria") == "Diretoria"
    assert perfis.existe("consultor") is True
    assert perfis.existe("diretor") is False   # slug-cargo antigo aposentado


def test_usuario_delega_perfis():
    from database import Usuario
    assert Usuario(nome="X", login="x", nivel="gerencial").limite_desconto == 20.0
    assert Usuario(nome="X", login="x", nivel="suporte").limite_desconto == 0.0
    assert Usuario(nome="X", login="x", nivel="diretoria").pode_ver_parametros is True
    assert Usuario(nome="X", login="x", nivel="consultor").pode_ver_parametros is False


def test_usuario_dict_inclui_rotulo_e_gerir():
    from auth import _usuario_dict
    from database import Usuario
    d = _usuario_dict(Usuario(id=1, nome="Ana", login="ana", nivel="diretoria"))
    assert d["rotulo"] == "Diretoria" and d["pode_gerir_usuarios"] is True and d["limite_desconto"] == 50.0
    d2 = _usuario_dict(Usuario(id=2, nome="C", login="c", nivel="consultor"))
    assert d2["pode_gerir_usuarios"] is False
