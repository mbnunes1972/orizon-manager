# -*- coding: utf-8 -*-
"""docs/db/ACHADOS_CONTABEIS.md, ACHADO-66 — F2-36 (07/09, DECIDIDO).

MEDIDO: antes da separação Item Especial × Outros Fornecedores, `out_forn` entrava em
`mod_provisoes._RUBRICAS` (somado no Cust_Var) — mas o CFO congelado (base de
`cust_var_marg_cont`) nunca caía quando a AF migrava Outros Fornecedores (a migração É a queda do
CFO, só que o SNAPSHOT usa o CFO de ANTES). Somar os dois contava a mesma mercadoria duas vezes:
uma migração de 3.000 sem custo novo nenhum derrubava a margem de 42,00% pra 40,50%.

CONSERTO (F2-36): `out_forn` SAI de `_RUBRICAS` — ele já está DENTRO do CFO congelado (é
substituição, não custo novo). A migração deixa de mexer no Cust_Var."""
import mod_contabil as mc
from tests.test_provisao_registro import _setup_venda


def test_migracao_de_outros_fornecedores_nao_muda_cust_var(http_client_factory, app_db, seed, projetos_dir):
    _setup_venda(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]

    _, prov = c.get("/api/orcamentos/%d/provisoes" % oid)
    cust_var_venda = prov["provisoes"]["venda"]["cust_var"]

    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 0.0, "out_forn": 3000.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    _, prov2 = c.get("/api/orcamentos/%d/provisoes" % oid)
    cust_var_rev1 = prov2["provisoes"]["rev1"]["cust_var"]

    assert cust_var_rev1 == cust_var_venda, (
        "ACHADO-66: migrar Outros Fornecedores (substituição, já dentro do CFO congelado) não "
        "pode mudar o Cust_Var — %r virou %r" % (cust_var_venda, cust_var_rev1))

    # controle: o razão realmente migrou (senão a asserção acima seria vácua)
    db = app_db.get_session()
    try:
        ot, oidx = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        saldo_of = round(mc._mov(db, ot, oidx, "2.1.04.14", "credor", None, None, projeto_id=nome), 2)
        assert saldo_of == 3000.0, "a migração tem que ter acontecido de verdade no razão"
    finally:
        db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=oid).delete()
        db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oidx, projeto_id=nome).delete()
        db.commit(); db.close()


def test_item_especial_sobrevive_a_revisoes_sucessivas_da_af(http_client_factory, app_db, seed, projetos_dir):
    """Item Especial não é editável na AF (congelado após a assinatura) — a tela nunca o submete
    no `itens` da revisão. Sem o carregamento explícito do registro ANTERIOR (main.py, POST
    .../provisoes/<rev>), cada revisão apagaria sua contribuição ao Cust_Var (regra dos irmãos:
    ele é a ÚNICA rubrica que soma em Cust_Var mas nunca vem no `itens` submetido)."""
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.item_especial = 4000.0
        db.commit()
    finally:
        db.close()
    _setup_venda(app_db, seed)   # _registrar_provisao_venda lê orc.item_especial via o motor
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]

    _, prov = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert prov["provisoes"]["venda"]["itens"]["item_especial"] == 4000.0
    cust_var_venda = prov["provisoes"]["venda"]["cust_var"]

    itens = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
             "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0,
             "prov_imp": 300.0, "out_forn": 0.0}
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": itens, "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    _, prov2 = c.get("/api/orcamentos/%d/provisoes" % oid)
    assert prov2["provisoes"]["rev1"]["itens"]["item_especial"] == 4000.0, (
        "item_especial tem que sobreviver à revisão — a tela nunca o submete")
    assert prov2["provisoes"]["rev1"]["cust_var"] == cust_var_venda + 300.0, (
        "só o delta de prov_imp (300,00) pode mudar o Cust_Var — item_especial continua igual")

    db = app_db.get_session()
    db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=oid).delete()
    db.commit(); db.close()
