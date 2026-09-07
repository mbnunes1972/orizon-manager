# -*- coding: utf-8 -*-
"""F2-34, ACHADO-62 — REVERTIDO de propósito pelo F2-39 (07/09). Este arquivo testava a RECUSA da
redução de Outros Fornecedores; agora testa o oposto, com o MESMO cuidado de não perder a
história (nenhum teste apagado, todos reescritos com o motivo).

POR QUE MUDOU — registrar assim, porque "erramos e voltamos atrás" seria falso: o bloqueio de
06/09 tinha motivo real NAQUELE desenho, em que `out_forn` carregava DUAS naturezas — mercadoria
a mais vinda da venda (aditiva) e substituição do Custo de Fábrica — e devolver ao CFO podia
inflar a previsão da fábrica além do que ela forneceria. O F2-36 (07/09) separou as duas: a
natureza aditiva saiu pro Item Especial (conta própria, 1.1.06.22/2.1.04.22); `out_forn` ficou
SÓ substituição — uma fatia recortada do CFO congelado. Devolvê-la é desfazer o recorte, não
inflar nada. O motivo do bloqueio se foi junto com a ambiguidade que o F2-36 eliminou.

DECIDIDO (Marcelo, 07/09): "com a inserção do item especial voltamos a poder congelar CFO, e
Outros Fornecedores pode ser alterado para menos, só não pode ser negativo." Reclassificação
BIDIRECIONAL (main.py, POST .../provisoes/<rev>, ramo "revisa"): delta > 0 migra
2.1.04.06→2.1.04.14 (como sempre); delta < 0 devolve 2.1.04.14→2.1.04.06 (`reclassificar_
provisao`, mesma função, só invertida — nenhuma lógica nova). Invariante que isso estabelece:
saldo(2.1.04.06) + saldo(2.1.04.14) == CFO congelado, em qualquer sequência de altas e baixas."""
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


def test_percurso_encadeado_sobe_desce_e_zera_out_forn_com_cfo_espelhando(
        http_client_factory, app_db, seed, projetos_dir):
    """ACEITE F2-39 Fatia 3 (números à mão, CFO congelado 100.000):
      a) sobe out_forn 0 -> 3.000:  2.1.04.06 = 97.000  2.1.04.14 = 3.000  soma 100.000
      b) baixa 3.000 -> 1.000:      2.1.04.06 = 99.000  2.1.04.14 = 1.000  soma 100.000
      c) zera 1.000 -> 0:           2.1.04.06 = 100.000 2.1.04.14 = 0      soma 100.000
    Em cada passo, `itens["custo_fabrica"]` gravado no Rev1 == saldo vivo de 2.1.04.06 depois."""
    _preparar(app_db, seed, cfo=100000.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    db.close()

    def _passo(valor_novo, cfo_esperado, of_esperado):
        st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                          {"decisao": "revisa", "itens": _base_itens(out_forn=valor_novo),
                           "login": "dir_l1", "senha": "senha123"})
        assert st == 200 and body["ok"] is True, body
        db = app_db.get_session()
        try:
            cfo = _saldo(db, ot, oid_, "2.1.04.06", nome)
            of = _saldo(db, ot, oid_, "2.1.04.14", nome)
            assert cfo == cfo_esperado, ("2.1.04.06 esperado %r, achou %r" % (cfo_esperado, cfo))
            assert of == of_esperado, ("2.1.04.14 esperado %r, achou %r" % (of_esperado, of))
            assert round(cfo + of, 2) == 100000.0, "invariante CFO+Outros Fornecedores == congelado"
            rev1 = db.query(app_db.ProvisaoRegistro).filter_by(orcamento_id=oid, versao="rev1").first()
            assert json.loads(rev1.itens_json)["custo_fabrica"] == cfo_esperado, (
                "itens['custo_fabrica'] gravado tem que refletir o razão DEPOIS da submissão")
        finally:
            db.close()

    _passo(3000.0, 97000.0, 3000.0)   # a) sobe 0 -> 3.000
    _passo(1000.0, 99000.0, 1000.0)   # b) baixa 3.000 -> 1.000
    _passo(0.0,   100000.0,    0.0)   # c) zera 1.000 -> 0

    _limpar(app_db, seed)


def test_reducao_alem_do_saneamento_de_entrada_vira_zero_nao_erro(
        http_client_factory, app_db, seed, projetos_dir):
    """F2-39: "valor negativo continua recusado" — pela MESMA sanitização que já existe pra
    TODAS as rubricas na entrada da rota (`max(0.0, float(v or 0))`, antes de chegar no ramo de
    Outros Fornecedores) — não é uma trava nova só pra out_forn. Submeter -500 com out_forn em
    3.000 não gera erro 400: o valor negativo vira 0.0 na sanitização de entrada, e 0.0 é uma
    redução válida (zera). Não é "recusado" no sentido de rejeitar a submissão — é absorvido
    pela mesma regra genérica que qualquer outro campo já tem."""
    _preparar(app_db, seed, cfo=100000.0)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]

    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=3000.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body

    st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                      {"decisao": "revisa", "itens": _base_itens(out_forn=-500.0),
                       "login": "dir_l1", "senha": "senha123"})
    assert st == 200 and body["ok"] is True, body   # sanitizado pra 0.0, não recusado com 400

    db = app_db.get_session()
    try:
        ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
        assert _saldo(db, ot, oid_, "2.1.04.14", nome) == 0.0
        assert _saldo(db, ot, oid_, "2.1.04.06", nome) == 100000.0
    finally:
        db.close()
    _limpar(app_db, seed)


def test_item_especial_intocado_durante_a_migracao_bidirecional_de_out_forn(
        http_client_factory, app_db, seed, projetos_dir):
    """ACEITE F2-39 (g): o Item Especial (2.1.04.22) não se move em NENHUM passo da migração de
    Outros Fornecedores (2.1.04.14) — prova que a separação do F2-36 segurou: as duas rubricas
    têm par ativo×provisão PRÓPRIO, sem interseção nenhuma no razão."""
    import main
    oid = seed["orcamento_l1_id"]
    nome = seed["projeto_l1"]
    db = app_db.get_session()
    orc = db.get(app_db.Orcamento, oid)
    orc.loja_id = seed["loja1_id"]
    orc.item_especial = 4000.0
    db.commit()
    ot, oid_ = mc.resolver_owner(db, {"loja_id": seed["loja1_id"], "rede_id": None})
    main._fin_provisoes_venda_seguro(orc, nome, "f239-item-esp:" + nome)
    db.commit()
    db.close()
    _preparar(app_db, seed, cfo=100000.0)

    assert _saldo(app_db.get_session(), ot, oid_, "2.1.04.22", nome) == 4000.0

    c = http_client_factory(); c.login("dir_l1", "senha123")
    for valor in (3000.0, 1000.0, 0.0, 2500.0):
        st, body = c.post("/api/orcamentos/%d/provisoes/rev1" % oid,
                          {"decisao": "revisa", "itens": _base_itens(out_forn=valor),
                           "login": "dir_l1", "senha": "senha123"})
        assert st == 200 and body["ok"] is True, body
        db = app_db.get_session()
        try:
            assert _saldo(db, ot, oid_, "2.1.04.22", nome) == 4000.0, (
                "Item Especial não pode se mover por causa de uma migração de Outros Fornecedores")
        finally:
            db.close()

    db = app_db.get_session()
    db.query(mc.Lancamento).filter_by(owner_tipo=ot, owner_id=oid_, projeto_id=nome).delete()
    db.commit(); db.close()
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
    """A regra de Outros Fornecedores agora é bidirecional por conta própria — nada aqui exigia
    isolamento de "só out_forn é verificado"; mantido como controle de que reduzir OUTRA rubrica
    (assistência) na MESMA submissão continua funcionando normalmente."""
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
        assert _saldo(db, ot, oid_, "2.1.04.14", seed["projeto_l1"]) == 1000.0    # out_forn intacto
        assert _saldo(db, ot, oid_, "2.1.04.05", seed["projeto_l1"]) == 300.0    # assist caiu de verdade
    finally:
        db.close()
    _limpar(app_db, seed)
