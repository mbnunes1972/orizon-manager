# -*- coding: utf-8 -*-
"""F2-34, ACHADO-62 — a redução de Outros Fornecedores na AF é aceita em silêncio.

MEDIDO (percurso do Marcelo em beta3, confirmando o diagnóstico de 06/09): subir o valor
funciona e lança certo; baixar de 4.000 para 2.000 atualizava a coluna Rev1 pra 2.000 e NÃO
fazia lançamento nenhum — o razão ficava em 4.000. Causa: `_migracao = max(0.0, novo − atual)`
dava zero na redução, e `out_forn` saía do lote genérico (`_itens_af.pop`), então
`disparar_deltas_af` também não o ajustava.

DECIDIDO (Marcelo, 06/09) — muda a decisão anterior, de propósito: a redução NÃO passa a
funcionar. É BLOQUEADA. Devolver valor ao Custo de Fábrica significaria aumentar a previsão da
fábrica, incoerente com a operação. O conserto é a RECUSA, não o aviso — nenhum lançamento,
nenhum ProvisaoRegistro gravado, a coluna Rev1 permanece com o valor anterior."""
import json

import mod_contabil as mc
from tests.test_provisao_registro import _setup_venda


def _base_itens(**over):
    base = {"frete_fab": 0.0, "com_adm": 0.0, "com_venda": 0.0, "com_med": 0.0,
            "com_proj_exec": 0.0, "frete_loc": 0.0, "assist": 0.0, "ins_loc": 0.0, "prov_imp": 0.0}
    base.update(over)
    return base


def _saldo(db, ot, oid, cod, projeto_id):
    c = db.query(mc.Conta).filter_by(owner_tipo=ot, owner_id=oid, codigo=cod).first()
    sentido = "devedor" if mc._natureza(c.grupo) == "devedora" else "credor"
    return round(mc._mov(db, ot, oid, cod, sentido, None, None, projeto_id=projeto_id), 2)


def _preparar(app_db, seed, cfo=101446.51):
    _setup_venda(app_db, seed)
    db = app_db.get_session()
    try:
        ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        mc.constituir_provisoes_fechamento(db, ot, oid, seed["projeto_l1"],
                                           {"custo_fabrica": cfo}, ref_base="pf:direto")
        db.commit()
    finally:
        db.close()


def _limpar(app_db, seed):
    db = app_db.get_session()
    ot, oid = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=seed["orcamento_l1_id"]).delete()
    db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid,
                                      projeto_id=seed["projeto_l1"]).delete()
    db.commit(); db.close()


def test_percurso_3000_4000_2000_a_reducao_e_recusada(http_client_factory, app_db, seed, projetos_dir):
    """Reproduz o percurso exato do Marcelo: 3.000 → 4.000 (ok) → 2.000 (recusado, Rev1 intacta)."""
    _preparar(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]

    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=3000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=4000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=2000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 400 and body["ok"] is False, body
    assert "reduzido" in body["erro"]
    assert "4000" in body["erro"] or "4.000" in body["erro"] or "4000.00" in body["erro"], body

    db = app_db.get_session()
    try:
        ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _saldo(db, ot, oid_, "2.1.04.14", seed["projeto_l1"]) == 4000.0   # inalterado
        rev1 = db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=oid, versao="rev1").first()
        assert json.loads(rev1.itens_json)["out_forn"] == 4000.0   # Rev1 intacta
    finally:
        db.close()
    _limpar(app_db, seed)


def test_aumento_continua_funcionando(http_client_factory, app_db, seed, projetos_dir):
    _preparar(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
          {"decisao": "revisa", "itens": _base_itens(out_forn=1000.0),
           "login": "dir_l1", "senha": "senha123"})
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=1500.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    try:
        ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _saldo(db, ot, oid_, "2.1.04.14", seed["projeto_l1"]) == 1500.0
    finally:
        db.close()
    _limpar(app_db, seed)


def test_valor_igual_e_noop_sem_erro(http_client_factory, app_db, seed, projetos_dir):
    _preparar(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
          {"decisao": "revisa", "itens": _base_itens(out_forn=2000.0),
           "login": "dir_l1", "senha": "senha123"})
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=2000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    try:
        ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _saldo(db, ot, oid_, "2.1.04.14", seed["projeto_l1"]) == 2000.0
    finally:
        db.close()
    _limpar(app_db, seed)


def test_outra_rubrica_reduzida_na_mesma_submissao_continua_funcionando(
        http_client_factory, app_db, seed, projetos_dir):
    """A recusa é de out_forn, não da AF inteira — reduzir OUTRA rubrica (assistência) na MESMA
    submissão onde out_forn fica igual/sobe continua funcionando normalmente."""
    _preparar(app_db, seed)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
          {"decisao": "revisa", "itens": _base_itens(out_forn=1000.0, assist=800.0),
           "login": "dir_l1", "senha": "senha123"})
    # out_forn fica igual (1000, no-op); assistência CAI de 800 pra 300 — deve funcionar.
    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=1000.0, assist=300.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body
    db = app_db.get_session()
    try:
        ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _saldo(db, ot, oid_, "2.1.04.14", seed["projeto_l1"]) == 1000.0   # out_forn intacto
        assert _saldo(db, ot, oid_, "2.1.04.05", seed["projeto_l1"]) == 300.0    # assist caiu de verdade
    finally:
        db.close()
    _limpar(app_db, seed)
