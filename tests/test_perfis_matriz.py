from auth import perfis


def test_capacidades_cobrem_todas_usadas_e_sao_reais():
    # toda capacidade booleana usada em PERFIS tem metadado em CAPACIDADES (sem órfão)
    usadas = set()
    for p in perfis.PERFIS.values():
        for k, v in p.items():
            if k in ("rotulo", "desconto_max"):
                continue
            if v is True:
                usadas.add(k)
    faltando = usadas - set(perfis.CAPACIDADES)
    assert not faltando, "capacidade usada sem metadado: %s" % sorted(faltando)
    # e todo metadado corresponde a uma capacidade REAL (existe no _DEFAULT)
    reais = set(perfis._DEFAULT) - {"rotulo", "desconto_max"}
    assert set(perfis.CAPACIDADES) <= reais, "metadado sem capacidade real: %s" % sorted(
        set(perfis.CAPACIDADES) - reais)


def test_cada_capacidade_tem_rotulo_e_descricao():
    for slug, meta in perfis.CAPACIDADES.items():
        assert meta.get("rotulo") and meta.get("descricao") and meta.get("grupo"), slug


def test_matriz_deriva_de_perfis():
    m = perfis.matriz()
    assert len(m["perfis"]) == len(perfis.slugs())
    d = next(x for x in m["perfis"] if x["slug"] == "master")
    assert "autorizar" in d["capacidades"] and d["desconto_max"] == 50.0 and d["loja"] is True
    op = next(x for x in m["perfis"] if x["slug"] == "operador")
    assert "acesso_operacional" in op["capacidades"] and "autorizar" not in op["capacidades"]
    assert op["desconto_max"] == 10.0
    sa = next(x for x in m["perfis"] if x["slug"] == "super_admin")
    assert sa["loja"] is False
    assert set(m["capacidades"]) == set(perfis.CAPACIDADES)


# ── endpoint: gate gerir_usuarios ────────────────────────────────────────────────
def test_perfis_matriz_endpoint_gate(http_client_factory, seed):
    g = http_client_factory(); g.login("dir_l1", "senha123")     # master: gerir_usuarios
    st, d = g.get("/api/admin/perfis-matriz")
    assert st == 200 and d.get("ok") is True
    assert {"master", "gerencial", "operador"} <= {p["slug"] for p in d["perfis"]}
    assert "autorizar" in d["capacidades"] and "acesso_financeiro" in d["capacidades"]
    c = http_client_factory(); c.login("cons_l1", "senha123")    # operador: sem gerir_usuarios
    assert c.get("/api/admin/perfis-matriz")[0] == 403
