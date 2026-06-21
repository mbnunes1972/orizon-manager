import perfis


def test_slugs_sao_os_doze_perfis():
    esperado = {
        "diretor", "gerente_vendas", "consultor", "gerente_adm_fin",
        "assistente_logistico", "conferente", "supervisor_montagem",
        "assistente_administrativo", "projetista_executivo", "medidor",
        "super_admin", "admin_rede",
    }
    assert set(perfis.slugs()) == esperado


def test_desconto_max():
    assert perfis.desconto_max("diretor") == 50.0
    assert perfis.desconto_max("gerente_vendas") == 20.0
    assert perfis.desconto_max("consultor") == 10.0
    assert perfis.desconto_max("medidor") == 0.0
    assert perfis.desconto_max("gerente_adm_fin") == 0.0
    assert perfis.desconto_max("inexistente") == 0.0      # default seguro


def test_capacidades():
    assert perfis.pode("diretor", "gerir_usuarios") is True
    assert perfis.pode("gerente_adm_fin", "gerir_usuarios") is True
    assert perfis.pode("gerente_vendas", "gerir_usuarios") is False
    assert perfis.pode("diretor", "autorizar") is True
    assert perfis.pode("gerente_vendas", "autorizar") is True
    assert perfis.pode("gerente_adm_fin", "autorizar") is False
    assert perfis.pode("consultor", "autorizar") is False
    assert perfis.pode("gerente_adm_fin", "ver_parametros") is True
    assert perfis.pode("consultor", "ver_parametros") is False
    assert perfis.pode("inexistente", "gerir_usuarios") is False   # default seguro


def test_rotulo_e_existe():
    assert perfis.rotulo("gerente_adm_fin") == "Gerente Administrativo/Financeiro"
    assert perfis.existe("medidor") is True
    assert perfis.existe("admin") is False


def test_usuario_limite_desconto_delega_perfis():
    from database import Usuario
    assert Usuario(nome="X", login="x", nivel="gerente_vendas").limite_desconto == 20.0
    assert Usuario(nome="X", login="x", nivel="medidor").limite_desconto == 0.0
    assert Usuario(nome="X", login="x", nivel="diretor").pode_ver_parametros is True
    assert Usuario(nome="X", login="x", nivel="consultor").pode_ver_parametros is False


def test_usuario_dict_inclui_rotulo_e_gerir():
    from auth import _usuario_dict
    from database import Usuario
    d = _usuario_dict(Usuario(id=1, nome="Ana", login="ana", nivel="gerente_adm_fin"))
    assert d["rotulo"] == "Gerente Administrativo/Financeiro"
    assert d["pode_gerir_usuarios"] is True
    assert d["limite_desconto"] == 0.0
    d2 = _usuario_dict(Usuario(id=2, nome="C", login="c", nivel="consultor"))
    assert d2["pode_gerir_usuarios"] is False


def test_capacidade_aprovar_financeiro():
    assert perfis.pode("diretor", "aprovar_financeiro") is True
    assert perfis.pode("gerente_adm_fin", "aprovar_financeiro") is True
    assert perfis.pode("gerente_vendas", "aprovar_financeiro") is False
    assert perfis.pode("consultor", "aprovar_financeiro") is False
    assert perfis.pode("medidor", "aprovar_financeiro") is False
    assert perfis.pode("inexistente", "aprovar_financeiro") is False


def test_capacidades_medicao():
    assert perfis.pode("medidor", "registrar_medicao") is True
    assert perfis.pode("diretor", "registrar_medicao") is True
    assert perfis.pode("gerente_vendas", "registrar_medicao") is False
    assert perfis.pode("consultor", "registrar_medicao") is False
    assert perfis.pode("gerente_vendas", "aprovar_medicao_reprovada") is True
    assert perfis.pode("gerente_adm_fin", "aprovar_medicao_reprovada") is True
    assert perfis.pode("diretor", "aprovar_medicao_reprovada") is True
    assert perfis.pode("medidor", "aprovar_medicao_reprovada") is False
    assert perfis.pode("consultor", "aprovar_medicao_reprovada") is False
