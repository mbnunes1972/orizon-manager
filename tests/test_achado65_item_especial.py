# -*- coding: utf-8 -*-
"""F2-35/F2-36 — ACHADO-65 (docs/db/ACHADOS_CONTABEIS.md): Item Especial, mercadoria de terceiro
vendida NA VENDA ("markup 1" — sem desconto, sem margem própria, ver mod_negociacao.py topo do
arquivo). F2-36 (07/09, ACHADO-66) renomeou o parâmetro/coluna de `out_forn` pra `item_especial`
— Outros Fornecedores é OUTRA coisa (substituição do Custo de Fábrica, nasce só na AF/etapa 12,
ver tests/test_achado66_outros_fornecedores_substituicao.py). O ECONÔMICO do Item Especial em si
(entrada simétrica em VBVO/VBNO/VAVO, diluição de Desc_Tot/Desc_Efetivo/Markup) NÃO mudou — só o
nome. Estes testes foram renomeados internamente (não o conceito).

Todos os números abaixo são derivados À MÃO (álgebra, não execução copiada) a partir da MESMA
fórmula que `mod_negociacao.calcular_orcamento` implementa — ver comentário de cada teste.
"""
import mod_negociacao
import mod_provisoes


def _base_amb(vbva=10000.0, cfa=6000.0, d_amb=0.0):
    return [{"VBVA": vbva, "CFA": cfa, "desc_amb_pct": d_amb}]


def test_item_especial_entra_cheio_em_vbvo_vbno_vavo_e_dilui_desc_tot_e_efetivo():
    """1 ambiente, sem nenhum toggle de custo adicional, 30% de desconto de orçamento, item de
    1.000. Sem toggles: VBNA=VBVA (não passa pelo gross-up de arq/fid), fator_desc=(1-0.30)=0.70.

    SEM item: VBVO=VBNO=10.000; VAVO=10.000*0.70=7.000; Val_Liq=7.000 (Cust_Ad=0);
              Desc_Tot=(10.000-7.000)/10.000=0,30; Desc_Efetivo=1-7.000/10.000=0,30;
              Markup=7.000/6.000=1,166667.
    COM item de 1.000 (fora do loop, sem fator_desc): VBVO=VBNO=11.000; VAVO=7.000+1.000=8.000;
              Val_Liq=8.000 (sobe EXATO o valor do item — Cust_Ad não recebe o item);
              Desc_Tot=(11.000-8.000)/11.000=3.000/11.000=0,272727 (dilui de 30,00% pra 27,27%);
              Desc_Efetivo=1-8.000/11.000=0,272727 (idêntico ao Desc_Tot aqui, pois VBVO=VBNO e
              Cust_Ad=0 neste cenário sem custos adicionais);
              Markup=8.000/(6.000+1.000)=8.000/7.000=1,142857 (dilui de 1,166667 rumo a 1,0)."""
    ambs = _base_amb()
    params = {}   # nenhum toggle ativo

    sem_item = mod_negociacao.calcular_orcamento(ambs, params, desc_orc_pct=30.0)
    assert sem_item["VBVO"] == 10000.0 and sem_item["VBNO"] == 10000.0
    assert sem_item["VAVO"] == 7000.0
    assert sem_item["Val_Liq"] == 7000.0
    assert sem_item["Desc_Tot"] == 0.3
    assert sem_item["Desc_Efetivo"] == 0.3
    assert sem_item["Markup"] == round(7000.0 / 6000.0, 3)

    com_item = mod_negociacao.calcular_orcamento(ambs, params, desc_orc_pct=30.0, item_especial=1000.0)
    assert com_item["VBVO"] == 11000.0 and com_item["VBNO"] == 11000.0
    assert com_item["VAVO"] == 8000.0
    assert com_item["Val_Liq"] == 8000.0, "Val_Liq tem que subir EXATO o valor do item"
    assert com_item["Val_Liq"] - sem_item["Val_Liq"] == 1000.0
    assert com_item["Item_Esp"] == 1000.0
    assert com_item["Desc_Tot"] == round(3000.0 / 11000.0, 4)
    assert com_item["Desc_Efetivo"] == round(3000.0 / 11000.0, 6)
    assert com_item["Desc_Tot"] < sem_item["Desc_Tot"], "item sem desconto tem que DILUIR o composto"
    assert com_item["Markup"] == round(8000.0 / 7000.0, 3)
    assert com_item["Markup"] < sem_item["Markup"], "markup exibido dilui rumo a 1,0 com o item"


def test_val_cont_e_prov_imp_sobem_pelo_item_na_proporcao_da_carga_tributaria():
    """Val_Cont = VAVO + Cust_Fin (item já está em VAVO); Prov_Imp = %carga_trib * Val_Cont.
    Com carga_trib=8%: SEM item, Val_Cont=7.000, Prov_Imp=560,00. COM item de 1.000,
    Val_Cont=8.000, Prov_Imp=640,00 — sobe EXATO 8% de 1.000 = 80,00."""
    ambs = _base_amb()
    params = {"carga_trib": 8.0}
    sem_item = mod_negociacao.calcular_orcamento(ambs, params, desc_orc_pct=30.0)
    com_item = mod_negociacao.calcular_orcamento(ambs, params, desc_orc_pct=30.0, item_especial=1000.0)
    assert sem_item["Val_Cont"] == 7000.0 and sem_item["Prov_Imp"] == 560.0
    assert com_item["Val_Cont"] == 8000.0 and com_item["Prov_Imp"] == 640.0
    assert round(com_item["Prov_Imp"] - sem_item["Prov_Imp"], 2) == 80.0


def test_markup_identico_a_hoje_quando_item_especial_zero():
    """item_especial=0.0 (default) não pode mudar NADA — mesma fórmula de antes do F2-35
    (Markup = Val_Liq/CFO, já que CFO+0 = CFO)."""
    ambs = _base_amb()
    d = mod_negociacao.calcular_orcamento(ambs, {}, desc_orc_pct=30.0)
    assert d["Markup"] == round(d["Val_Liq"] / d["CFO"], 3)
    assert d["Item_Esp"] == 0.0


def test_item_especial_imune_ao_desconto_por_ambiente():
    """2 ambientes com descontos individuais DIFERENTES (0% e 50%) — o Item Especial soma o
    MESMO valor de face nos três agregados, fora do loop por ambiente; não existe fator_desc
    que o alcance. VBVO/VBNO sobem exatamente `item_especial` acima da soma dos VBVA; VAVO sobe
    exatamente `item_especial` acima da soma dos VAVA — em ambos os casos, com ou sem item."""
    ambs = [{"VBVA": 5000.0, "CFA": 3000.0, "desc_amb_pct": 0.0},
            {"VBVA": 5000.0, "CFA": 3000.0, "desc_amb_pct": 50.0}]
    sem_item = mod_negociacao.calcular_orcamento(ambs, {}, desc_orc_pct=0.0)
    com_item = mod_negociacao.calcular_orcamento(ambs, {}, desc_orc_pct=0.0, item_especial=2000.0)
    assert com_item["VBVO"] - sem_item["VBVO"] == 2000.0
    assert com_item["VBNO"] - sem_item["VBNO"] == 2000.0
    assert com_item["VAVO"] - sem_item["VAVO"] == 2000.0
    # os VAVA por ambiente (rateio do desconto individual) não mudam com o item — ele nunca entra
    # no loop por ambiente.
    assert com_item["ambientes"][0]["VAVA"] == sem_item["ambientes"][0]["VAVA"]
    assert com_item["ambientes"][1]["VAVA"] == sem_item["ambientes"][1]["VAVA"]


def test_margem_contribuicao_igual_em_reais_menor_em_percentual():
    """Exemplo do próprio Marcelo (ACHADO-65, 06/09): Val_Liq 100.000 / Cust_Var 60.000 = 40,00%;
    com item de 5.000 nos dois lados (Val_Liq E Cust_Var — cust_var mantém item_especial),
    40.000/105.000 = 38,10%. Margem em REAIS igual (40.000 nos dois casos), só dilui em
    percentual — diluição correta, não é bug."""
    cfg = {"provisoes": {}, "provisoes_contabeis": {}}   # todas as %s zeradas → cust_var = CFO + item_especial

    sem_item = mod_provisoes.provisoes_orcamento(
        {"CFO": 60000.0, "Val_Liq": 100000.0, "VAVO": 100000.0, "Prov_Imp": 0.0}, cfg, item_especial=0.0)
    assert sem_item["Cust_Var"] == 60000.0
    assert sem_item["Marg_Cont"] == 0.40

    com_item = mod_provisoes.provisoes_orcamento(
        {"CFO": 60000.0, "Val_Liq": 105000.0, "VAVO": 105000.0, "Prov_Imp": 0.0}, cfg, item_especial=5000.0)
    assert com_item["Cust_Var"] == 65000.0
    margem_reais_sem = 100000.0 - sem_item["Cust_Var"]
    margem_reais_com = 105000.0 - com_item["Cust_Var"]
    assert margem_reais_com == margem_reais_sem == 40000.0, "margem em REAIS não muda"
    assert com_item["Marg_Cont"] == round(40000.0 / 105000.0, 4) == 0.381
    assert com_item["Marg_Cont"] < sem_item["Marg_Cont"], "dilui em percentual — sinal correto"


def _contrato_vigente(app_db, seed, nome):
    db = app_db.get_session()
    orc = app_db.Orcamento(projeto_id=nome, nome="O", ordem=1, loja_id=seed["loja1_id"],
                           desconto_pct=0.0, valor_total=0.0)
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="vigente"))
    db.add(orc); db.flush()
    oid = orc.id
    db.add(app_db.Contrato(projeto_nome=nome, orcamento_id=oid, status="vigente",
                           loja_id=seed["loja1_id"]))
    db.commit()
    db.close()
    return oid


def test_put_item_especial_recusado_apos_contrato_assinado(http_client_factory, app_db, seed):
    """F2-35/F2-36: mesma trava das demais edições de negociação — `_contrato_assinado`, mesma
    mensagem/código das rotas irmãs (main.py ~11426/11531/12309). Rota renomeada de /out-forn
    pra /item-especial no F2-36."""
    nome = "F236_contrato_vigente"
    oid = _contrato_vigente(app_db, seed, nome)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.put("/api/orcamentos/%d/item-especial" % oid, {"item_especial": 1000.0})
    assert st == 403 and body["ok"] is False, body
    assert "Contrato assinado" in body["erro"]

    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, oid)
        assert (orc.item_especial or 0.0) == 0.0, "nada pode ter sido persistido"
    finally:
        db.close()


def test_put_item_especial_funciona_sem_contrato_e_recalcula_sombra(http_client_factory, app_db, seed):
    """Controle-irmão do teste acima: sem contrato, o PUT tem que funcionar e devolver a sombra
    já recalculada (Val_Liq/Markup materializados atualizados — sem isto ficariam defasados até
    a próxima edição de negociação, mesmo padrão de `_persistirDescontosOrc`)."""
    db = app_db.get_session()
    nome = "F236_sem_contrato"
    orc = app_db.Orcamento(projeto_id=nome, nome="O", ordem=1, loja_id=seed["loja1_id"],
                           desconto_pct=0.0, valor_total=0.0)
    db.add(app_db.Projeto(nome_safe=nome, loja_id=seed["loja1_id"], status="vigente"))
    db.add(orc); db.flush()
    oid = orc.id
    db.commit(); db.close()

    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.put("/api/orcamentos/%d/item-especial" % oid, {"item_especial": 1000.0})
    assert st == 200 and body["ok"] is True, body
    assert body["sombra"]["Item_Esp"] == 1000.0

    db = app_db.get_session()
    try:
        orc2 = db.get(app_db.Orcamento, oid)
        assert orc2.item_especial == 1000.0
        assert orc2.val_liq == body["sombra"]["Val_Liq"], "coluna materializada tem que refletir o novo Val_Liq"
        assert orc2.markup == body["sombra"]["Markup"]
    finally:
        db.close()


def test_rota_out_forn_removida(http_client_factory, app_db, seed):
    """F2-36: a rota antiga /out-forn foi REMOVIDA — out_forn não se edita mais na negociação."""
    nome = "F236_rota_removida"
    oid = _contrato_vigente(app_db, seed, nome)
    c = http_client_factory(); c.login("dir_l1", "senha123")
    st, body = c.put("/api/orcamentos/%d/out-forn" % oid, {"out_forn": 1000.0})
    assert st == 404
