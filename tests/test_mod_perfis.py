import mod_perfis


def test_slug_unico_gera_sufixo():
    existentes = {"master", "gerencial", "operador", "vendas"}
    s = mod_perfis.gerar_slug("Vendas", existentes)
    assert s not in existentes and s.startswith("vendas")


def test_valida_modulos_rejeita_id_desconhecido():
    ok, _ = mod_perfis.validar_modulos(["fiscal", "admin"])
    assert ok
    ok2, err = mod_perfis.validar_modulos(["fiscal", "inexistente"])
    assert not ok2 and "inexistente" in err


def test_valida_base():
    assert mod_perfis.validar_base("operador")[0]
    assert not mod_perfis.validar_base("xpto")[0]


def test_valida_nome():
    assert mod_perfis.validar_nome("Vendas Júnior")[0]
    assert not mod_perfis.validar_nome("  ")[0]


def test_valida_capacidades_aceita_subset_conhecido():
    ok, limpo = mod_perfis.validar_capacidades({"aprovar_financeiro": True, "gerir_usuarios": False})
    assert ok and limpo == {"aprovar_financeiro": True, "gerir_usuarios": False}


def test_valida_capacidades_rejeita_cap_desconhecida():
    ok, err = mod_perfis.validar_capacidades({"virar_deus": True})
    assert not ok and "virar_deus" in err
