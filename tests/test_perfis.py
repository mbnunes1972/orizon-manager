import perfis


def test_slugs_sao_os_dez_perfis():
    esperado = {
        "diretor", "gerente_vendas", "consultor", "gerente_adm_fin",
        "assistente_logistico", "conferente", "supervisor_montagem",
        "assistente_administrativo", "projetista_executivo", "medidor",
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
