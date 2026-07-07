import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, f"login falhou para {who}"
    return c


def _set_central(app_db, rede_id):
    """Cria um Emitente central e o vincula à rede (emitente_central_id).
    Retorna o id do central."""
    db = app_db.get_session()
    try:
        c = app_db.Emitente(cnpj="99999999000199", razao_social="CENTRAL DA REDE LTDA",
                            regime_tributario="simples", csosn_padrao="101",
                            cfop_dentro_uf="5102", cfop_fora_uf="6102",
                            ambiente_ativo="homologacao")
        db.add(c); db.flush()
        cid = c.id
        rede = db.get(app_db.Rede, rede_id)
        rede.emitente_central_id = cid
        db.commit()
        return cid
    finally:
        db.close()


def _limpa_perfis(app_db, owner_tipo, owner_id):
    db = app_db.get_session()
    try:
        for pe in db.query(app_db.PerfilEmissao).filter_by(
                owner_tipo=owner_tipo, owner_id=owner_id).all():
            db.delete(pe)
        db.commit()
    finally:
        db.close()


def _perfis(app_db, owner_tipo, owner_id):
    db = app_db.get_session()
    try:
        return {pe.tipo_doc: pe.emitente_id for pe in db.query(app_db.PerfilEmissao)
                .filter_by(owner_tipo=owner_tipo, owner_id=owner_id).all()}
    finally:
        db.close()


# ── Rede default ──────────────────────────────────────────────────────────
def test_rede_put_cria_produto_e_get_reflete(http_client_factory, seed, app_db):
    rid = seed["rede_id"]
    _limpa_perfis(app_db, "rede", rid)
    central = _set_central(app_db, rid)
    c = _login(http_client_factory, "adm_rede")

    st, b = c.put(f"/api/admin/redes/{rid}/perfil-emissao",
                  {"produto": central, "servico": None})
    assert st == 200, b
    # persistiu produto→central; serviço não criado
    perfis = _perfis(app_db, "rede", rid)
    assert perfis.get("produto") == central
    assert "servico" not in perfis

    st2, g = c.get(f"/api/admin/redes/{rid}/perfil-emissao")
    assert st2 == 200, g
    assert g["produto"] == central and g["servico"] is None
    ids = [o["id"] for o in g["opcoes"]]
    assert central in ids


def test_rede_put_null_remove_linha(http_client_factory, seed, app_db):
    rid = seed["rede_id"]
    _limpa_perfis(app_db, "rede", rid)
    central = _set_central(app_db, rid)
    c = _login(http_client_factory, "adm_rede")
    c.put(f"/api/admin/redes/{rid}/perfil-emissao", {"produto": central})
    assert _perfis(app_db, "rede", rid).get("produto") == central
    # agora limpa
    st, b = c.put(f"/api/admin/redes/{rid}/perfil-emissao", {"produto": None})
    assert st == 200, b
    assert "produto" not in _perfis(app_db, "rede", rid)
    st2, g = c.get(f"/api/admin/redes/{rid}/perfil-emissao")
    assert g["produto"] is None


# ── Loja override ─────────────────────────────────────────────────────────
def test_loja_override_get_reflete_e_opcoes(http_client_factory, seed, app_db):
    rid = seed["rede_id"]
    lid = seed["loja2_id"]
    self_id = seed["emitente_l2_id"]
    _limpa_perfis(app_db, "loja", lid)
    central = _set_central(app_db, rid)
    c = _login(http_client_factory, "dir_l2")

    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-emissao", {"produto": self_id})
    assert st == 200, b
    st2, g = c.get(f"/api/admin/lojas/{lid}/perfil-emissao")
    assert st2 == 200, g
    assert g["produto"] == self_id and g["servico"] is None
    ids = [o["id"] for o in g["opcoes"]]
    assert self_id in ids and central in ids
    papeis = {o["papel"] for o in g["opcoes"]}
    assert "self" in papeis and "central" in papeis


# ── Resolução ponta a ponta (via mod_fiscal.resolver_emitente direto) ─────
def test_resolucao_ponta_a_ponta(http_client_factory, seed, app_db):
    import mod_fiscal
    rid = seed["rede_id"]
    lid = seed["loja2_id"]
    self_id = seed["emitente_l2_id"]
    _limpa_perfis(app_db, "rede", rid)
    _limpa_perfis(app_db, "loja", lid)
    central = _set_central(app_db, rid)

    # rede default produto→central, sem override de loja → resolve central
    cr = _login(http_client_factory, "adm_rede")
    cr.put(f"/api/admin/redes/{rid}/perfil-emissao", {"produto": central})
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, lid)
        assert mod_fiscal.resolver_emitente(db, loja, "produto").id == central
    finally:
        db.close()

    # override de loja produto→self → resolve self
    cl = _login(http_client_factory, "dir_l2")
    cl.put(f"/api/admin/lojas/{lid}/perfil-emissao", {"produto": self_id})
    db = app_db.get_session()
    try:
        loja = db.get(app_db.Loja, lid)
        assert mod_fiscal.resolver_emitente(db, loja, "produto").id == self_id
    finally:
        db.close()


# ── Validação ─────────────────────────────────────────────────────────────
def test_put_valor_invalido_400(http_client_factory, seed, app_db):
    lid = seed["loja2_id"]
    _limpa_perfis(app_db, "loja", lid)
    _set_central(app_db, seed["rede_id"])
    c = _login(http_client_factory, "dir_l2")
    # 999999 não é self nem central → 400
    st, b = c.put(f"/api/admin/lojas/{lid}/perfil-emissao", {"produto": 999999})
    assert st == 400, b


# ── Gates ─────────────────────────────────────────────────────────────────
def test_gate_consultor_403(http_client_factory, seed, app_db):
    lid = seed["loja1_id"]
    c = _login(http_client_factory, "cons_l1")
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-emissao")
    assert st == 403


def test_gate_nao_auth_401(http_client_factory, seed, app_db):
    lid = seed["loja2_id"]
    c = http_client_factory()
    st, _ = c.get(f"/api/admin/lojas/{lid}/perfil-emissao")
    assert st == 401


def test_gate_admin_rede_outra_rede_403(http_client_factory, seed, app_db):
    # cria uma segunda rede; adm_rede (rede do seed) não pode vê-la
    db = app_db.get_session()
    try:
        r2 = app_db.Rede(nome="Rede Outra")
        db.add(r2); db.commit()
        r2_id = r2.id
    finally:
        db.close()
    c = _login(http_client_factory, "adm_rede")
    st, _ = c.get(f"/api/admin/redes/{r2_id}/perfil-emissao")
    assert st == 403
