"""Item 1: Função com atribuições (papéis), remuneração padrão, regime de trabalho/contratação."""


def _funcoes(c):
    st, d = c.get("/api/funcoes")
    return d.get("itens") or d.get("funcoes") or []


def _criar_funcao(app_db):
    db = app_db.get_session()
    loja_id = db.query(app_db.Usuario).filter_by(login="dir_l1").first().loja_id
    f = app_db.Funcao(loja_id=loja_id, nome="Função Teste", status="ativo")
    db.add(f); db.commit()
    fid = f.id
    db.close()
    return fid


def test_editar_funcao_campos_novos(http_client_factory, seed, app_db):
    fid = _criar_funcao(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")   # master
    st, out = c.post(f"/api/funcoes/{fid}", {
        "descricao": "Elabora o projeto executivo e acompanha a obra.",
        "remuneracao_padrao": "fixa_variavel",
        "regime_trabalho": "misto",
        "regime_contratacao": "terceirizacao",
        "perfil_padrao": "operador",
    })
    assert out.get("ok"), out
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["descricao"] == "Elabora o projeto executivo e acompanha a obra."
    assert fn["remuneracao_padrao"] == "fixa_variavel"
    assert fn["regime_trabalho"] == "misto"
    assert fn["regime_contratacao"] == "terceirizacao"
    assert fn["perfil_padrao"] == "operador"


def test_valores_invalidos_viram_none(http_client_factory, seed, app_db):
    fid = _criar_funcao(app_db)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    c.post(f"/api/funcoes/{fid}", {"remuneracao_padrao": "zzz", "regime_trabalho": "zzz", "regime_contratacao": "zzz"})
    fn = next(x for x in _funcoes(c) if x["id"] == fid)
    assert fn["remuneracao_padrao"] in (None, "") and fn["regime_trabalho"] in (None, "") and fn["regime_contratacao"] in (None, "")
