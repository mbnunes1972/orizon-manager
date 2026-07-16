"""/auth/me expõe as capacidades de aba (p/ o cadeado de Admin/Config) derivadas de perfis.pode —
respeitando o god-mode do super_admin. master libera admin; operador não; super_admin tudo."""


def _me(c):
    _, out = c.get("/api/auth/me")
    return out["usuario"]


def test_caps_de_aba_por_perfil(http_client_factory, seed):
    m = _me(_login(http_client_factory, "dir_l1"))          # master
    assert m["pode_gerir_usuarios"] and m["pode_gerir_perfis"]
    assert m["pode_gerir_documentos"] and m["pode_ver_parametros"]

    o = _me(_login(http_client_factory, "cons_l1"))          # operador
    assert o["pode_gerir_usuarios"] is False and o["pode_gerir_perfis"] is False
    assert o["pode_gerir_documentos"] is False and o["pode_ver_parametros"] is False

    s = _me(_login(http_client_factory, "super"))            # super_admin (god-mode)
    assert s["pode_gerir_usuarios"] and s["pode_gerir_perfis"]
    assert s["pode_gerir_documentos"] and s["pode_ver_parametros"]


def _login(f, who):
    c = f(); c.login(who, "senha123"); return c
