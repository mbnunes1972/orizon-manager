# -*- coding: utf-8 -*-
"""PDV (Ponto de Venda avançado) — Fatia 1: fundação.

Spec: docs/superpowers/specs/_geral/2026-07-22-ponto-de-venda-design.md
PDV = Loja com mãe (loja_mae_id). Cobre: criação gated a super_admin, herança
(rede, config financeira), desvios fiscal (emitente da mãe) e documental (modelos
e dados da mãe, código do PDV na numeração) e tenancy (PDV não vê a mãe; a mãe
não vê o PDV fora dos painéis opt-in — que são da Fatia 2).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from conftest import HttpClient

CFG_MAE = '{"meta_mensal": 123456.0}'
CNPJ_MAE = "11.222.333/0001-81"


@pytest.fixture(scope="module")
def pdv(servidor, app_db, seed):
    """Cria o PDV da Loja 1 via API (super_admin), com a mãe já configurada
    (config financeira + CNPJ + endereço) para exercitar as heranças."""
    db = app_db.get_session()
    l1 = db.get(app_db.Loja, seed["loja1_id"])
    l1.config_financeira_json = CFG_MAE
    l1.cnpj = CNPJ_MAE
    l1.cidade = "Sao Jose dos Campos"; l1.estado = "SP"
    l1.logradouro = "Av Matriz"; l1.numero = "100"
    l1.testemunha1_nome = "Testemunha Mae"; l1.testemunha1_cpf = "390.533.447-05"
    db.commit(); db.close()

    c = HttpClient(servidor); c.login("super", "senha123")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"], {
        "nome": "PDV Praia", "codigo": "PRA",
        "telefone": "(12) 3888-0000", "cidade": "Caraguatatuba", "estado": "SP",
        "testemunha1_nome": "Testemunha PDV", "testemunha1_cpf": "111.444.777-35",
    })
    assert st == 200 and out.get("ok"), (st, out)
    return out["pdv"]


@pytest.fixture(scope="module")
def pdv_user(app_db, pdv):
    """Diretor (master) do PDV, para os testes de tenancy."""
    db = app_db.get_session()
    u = app_db.Usuario(nome="Diretor PDV", login="dir_pdv", nivel="master",
                       loja_id=pdv["id"], ativo=1)
    u.set_senha("senha123")
    db.add(u); db.flush()
    db.add(app_db.UsuarioLoja(usuario_id=u.id, loja_id=pdv["id"]))
    db.commit(); db.close()
    return "dir_pdv"


def _login(factory, who):
    c = factory()
    c.login(who, "senha123")
    assert c.cookie, "login falhou para %s" % who
    return c


# ── Criação e herança ────────────────────────────────────────────────────────

def test_pdv_nasce_como_loja_com_mae(pdv, seed):
    assert pdv["tipo"] == "ponto_venda"
    assert pdv["loja_mae_id"] == seed["loja1_id"]
    assert pdv["rede_id"] == seed["rede_id"]          # herdado da mãe
    assert pdv["codigo"] == "PRA"
    assert pdv["cnpj"] == ""                          # PDV sem CNPJ próprio (fiscal pela mãe)


def test_config_financeira_copiada_da_mae(app_db, pdv):
    db = app_db.get_session()
    l = db.get(app_db.Loja, pdv["id"])
    db.close()
    assert l.config_financeira_json == CFG_MAE
    assert l.emitente_id is None                      # nasce sem emitente próprio


def test_lojista_nao_cria_pdv(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"],
                     {"nome": "PDV Pirata", "codigo": "PIR"})
    assert st == 403


def test_pdv_de_pdv_negado(http_client_factory, pdv):
    c = _login(http_client_factory, "super")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % pdv["id"],
                     {"nome": "PDV Neto", "codigo": "NET"})
    assert st == 400


def test_codigo_duplicado_recusado(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "super")
    st, out = c.post("/api/admin/lojas/%d/pdvs" % seed["loja1_id"],
                     {"nome": "PDV Clone", "codigo": "PRA"})
    assert out.get("ok") is False and "existe" in out.get("erro", "")


# ── Cadastro Admin: lojista visualiza, não edita ─────────────────────────────

def test_lojista_ve_pdvs_da_propria_loja(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/admin/lojas/%d/pdvs" % seed["loja1_id"])
    assert st == 200 and out["ok"]
    assert [p["id"] for p in out["pdvs"]] == [pdv["id"]]


def test_lojista_de_outra_loja_nao_ve_pdvs(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l2")
    st, out = c.get("/api/admin/lojas/%d/pdvs" % seed["loja1_id"])
    assert st == 404


def test_lojista_nao_edita_pdv(http_client_factory, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.patch("/api/admin/lojas/%d" % pdv["id"], {"nome": "Hackeado"})
    assert st == 403


def test_super_edita_pdv_mas_rede_e_herdada(http_client_factory, app_db, pdv, seed):
    c = _login(http_client_factory, "super")
    st, out = c.patch("/api/admin/lojas/%d" % pdv["id"],
                      {"nome": "PDV Caragua", "rede_id": 999999})
    assert st == 200 and out["ok"], (st, out)
    assert out["loja"]["nome"] == "PDV Caragua"
    assert out["loja"]["rede_id"] == seed["rede_id"]   # rede_id do PDV não é editável


# ── Tenancy: PDV não enxerga a mãe; a mãe não enxerga o PDV ──────────────────

def test_usuario_do_pdv_nao_ve_a_mae(http_client_factory, seed, pdv, pdv_user):
    c = _login(http_client_factory, pdv_user)
    st, out = c.get("/api/admin/lojas")
    assert st == 200 and out["ok"]
    assert {l["id"] for l in out["lojas"]} == {pdv["id"]}
    st, _ = c.get("/api/admin/lojas/%d/pdvs" % seed["loja1_id"])
    assert st == 404


def test_usuario_da_mae_nao_ve_o_pdv_na_lista(http_client_factory, seed, pdv):
    c = _login(http_client_factory, "dir_l1")
    st, out = c.get("/api/admin/lojas")
    assert st == 200 and out["ok"]
    assert {l["id"] for l in out["lojas"]} == {seed["loja1_id"]}


def test_usuario_do_pdv_nao_ve_projetos_da_mae(http_client_factory, seed, pdv, pdv_user, projetos_dir):
    c = _login(http_client_factory, pdv_user)
    st, _ = c.get("/projetos/%s" % seed["projeto_l1"])
    assert st == 404


# ── Desvio 1 — Fiscal: emite pela mãe ────────────────────────────────────────

def test_resolver_emitente_do_pdv_cai_na_mae(app_db, pdv, seed):
    from fiscal import mod_fiscal
    db = app_db.get_session()
    try:
        l = db.get(app_db.Loja, pdv["id"])
        em = mod_fiscal.resolver_emitente(db, l, "produto")
        assert em.id == seed["emitente_l1_id"]
    finally:
        db.close()


def test_override_proprio_do_pdv_vence_a_mae(app_db, pdv):
    from fiscal import mod_fiscal
    db = app_db.get_session()
    try:
        em3 = app_db.Emitente(cnpj="33333333000133", razao_social="EMITENTE PDV LTDA",
                              regime_tributario="simples", uf="SP",
                              ambiente_ativo="homologacao")
        db.add(em3); db.flush()
        db.add(app_db.PerfilEmissao(owner_tipo="loja", owner_id=pdv["id"],
                                    tipo_doc="servico", emitente_id=em3.id))
        db.commit()
        l = db.get(app_db.Loja, pdv["id"])
        em = mod_fiscal.resolver_emitente(db, l, "servico")
        assert em.id == em3.id
    finally:
        db.close()


# ── Desvio 2 — Documentos: modelos e dados da mãe, código do PDV ─────────────

def test_modelo_de_documento_vem_da_mae(app_db, pdv, seed):
    import mod_documentos as mdoc
    db = app_db.get_session()
    try:
        m = app_db.DocumentoModelo(loja_id=seed["loja1_id"], tipo="contrato",
                                   versao=1, corpo_md="## CLAUSULA DA MAE", ativo=1)
        db.add(m); db.commit()
        ativo = mdoc.ativo_de(db, pdv["id"], "contrato")
        assert ativo is not None and ativo.id == m.id
        # loja plena SEM mãe segue sem fallback (retrocompatibilidade)
        assert mdoc.ativo_de(db, seed["loja2_id"], "contrato") is None
    finally:
        db.close()


def test_dados_do_contrato_sao_da_mae_com_codigo_do_pdv(app_db, pdv, seed):
    import main
    db = app_db.get_session()
    try:
        d = main._loja_dict_para_contrato(db, pdv["id"])
    finally:
        db.close()
    assert d["nome"] == "Loja 1"                       # CONTRATADA = mãe
    assert d["cnpj"] == CNPJ_MAE
    assert d["cidade"] == "Sao Jose dos Campos"
    assert d["codigo"] == "PRA"                        # numeração rastreia o PDV
    assert d["testemunha1_nome"] == "Testemunha PDV"   # testemunha própria do PDV vence
    from mod_contrato import gerar_num_contrato
    assert gerar_num_contrato([], d["codigo"]).startswith("PRA")


def test_loja_plena_continua_identica(app_db, seed):
    import main
    db = app_db.get_session()
    try:
        d = main._loja_dict_para_contrato(db, seed["loja2_id"])
    finally:
        db.close()
    assert d["nome"] == "Loja 2" and d["codigo"] == "LJ2"
