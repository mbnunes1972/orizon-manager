# -*- coding: utf-8 -*-
"""F2-38 (07/09, DECIDIDO pelo Marcelo): o Item Especial fica FORA das comissões e das provisões
operacionais (não tem o que remunerar numa mercadoria repassada a custo, sem margem) — mas o
IMPOSTO fica (o item sai na nota, o imposto é devido de verdade).

Cenário do próprio pacote, reconstruído à mão (não copiado de execução): CFO 47.900,00, VAVO
(sem item) 100.000,00, Val_Liq (sem item) 80.000,00, Cust_Fin 0 (Val_Cont = VAVO), carga
tributária 8%. Config: com_adm 1%, com_venda 3%, com_med 1%, com_proj_exec 1% (base Val_Liq,
soma 6%); frete_loc 1%, assist 1%, ins_loc 0,5%, montagem 4%, garantia 1% (base VAVO, soma 7,5%);
frete_fab 0%.

  SEM item: Prov_Imp = 8% × 100.000 = 8.000,00
    Cust_Var = CFO(47.900) + 6%×80.000(4.800) + 7,5%×100.000(7.500) + Prov_Imp(8.000) = 68.200,00
    margem = 80.000 − 68.200 = 11.800,00 → 11.800/80.000 = 14,75%
  COM item de 5.000: Val_Liq=85.000, VAVO=105.000, Val_Cont=105.000
    Prov_Imp = 8% × 105.000 = 8.400,00 (sobe exatamente 400,00 = 8%×5.000 — o imposto do item)
    base_vl = 85.000−5.000 = 80.000 (idêntica à de "sem item"); base_vavo = 105.000−5.000 =
    100.000 (idem) — as NOVE rubricas % saem com os MESMOS valores de antes.
    Cust_Var = CFO(47.900) + item(5.000) + 4.800 + 7.500 + Prov_Imp(8.400) = 73.600,00
      (sobe exatamente 5.400,00 = item 5.000,00 + imposto 400,00 — nada mais)
    margem = 85.000 − 73.600 = 11.400,00 → 11.400/85.000 = 13,41%
      (cai exatamente 400,00 em reais = o imposto do item, nada mais)
"""
import mod_provisoes


def _siglas(item_especial):
    val_liq = 80000.0 + item_especial
    vavo = 100000.0 + item_especial
    val_cont = vavo   # Cust_Fin = 0
    prov_imp = round(0.08 * val_cont, 2)
    return {"CFO": 47900.0, "Val_Liq": val_liq, "VAVO": vavo, "Prov_Imp": prov_imp}


_CFG = {
    "provisoes": {
        "frete_fab_pct": 0.0, "com_adm_pct": 1.0, "com_med_pct": 1.0,
        "com_proj_exec_pct": 1.0, "frete_loc_pct": 1.0, "assist_pct": 1.0, "ins_loc_pct": 0.5,
    },
    "provisoes_contabeis": {"montagem_pct": 4.0, "garantia_pct": 1.0},
}


def test_sem_item_bate_com_o_cenario_de_referencia():
    d = mod_provisoes.provisoes_orcamento(_siglas(0.0), _CFG, item_especial=0.0, com_venda_pct=3.0)
    assert d["Cust_Var"] == 68200.0
    assert d["Marg_Cont"] == 0.1475


def test_item_especial_isento_de_comissao_e_provisao_operacional_so_imposto_incide():
    sem = mod_provisoes.provisoes_orcamento(_siglas(0.0), _CFG, item_especial=0.0, com_venda_pct=3.0)
    com = mod_provisoes.provisoes_orcamento(_siglas(5000.0), _CFG, item_especial=5000.0, com_venda_pct=3.0)

    assert com["Cust_Var"] == 73600.0
    assert round(com["Cust_Var"] - sem["Cust_Var"], 2) == 5400.0, (
        "Cust_Var tem que subir EXATO item(5.000) + imposto(400) — nada mais")

    assert com["Marg_Cont"] == 0.1341
    margem_rs_sem = 80000.0 - sem["Cust_Var"]
    margem_rs_com = 85000.0 - com["Cust_Var"]
    assert round(margem_rs_sem - margem_rs_com, 2) == 400.0, (
        "a margem em reais só pode cair pelo IMPOSTO do item — 400,00, nada mais")

    # as NOVE rubricas percentuais: valores IDÊNTICOS com e sem o item (bases sem o item)
    for chave in ("Com_Adm_Orc", "Com_Venda_Orc", "Com_Med_Orc", "Com_Proj_Exec_Orc",
                 "Frete_Loc_Orc", "Assist_Orc", "Ins_Loc_Orc", "Prov_Mont", "Prov_Gar"):
        assert com[chave] == sem[chave], "%s tem que ser idêntico com e sem o item" % chave

    # só o imposto (Prov_Imp, fora de provisoes_orcamento — vem do motor) e o próprio item mudam
    assert round(com["Item_Esp"] - sem["Item_Esp"], 2) == 5000.0


def test_item_especial_zero_e_identico_ao_default_do_parametro():
    """Controle: item_especial=0.0 (explícito) não pode diferir do default (out_forn=0 pré-F2-35
    não passava por aqui de propósito nenhum) — base_vl/base_vavo com item=0 são o Val_Liq/VAVO
    cheios, exatamente como antes do F2-38."""
    s = _siglas(0.0)
    com_default = mod_provisoes.provisoes_orcamento(s, _CFG, com_venda_pct=3.0)
    com_explicito = mod_provisoes.provisoes_orcamento(s, _CFG, item_especial=0.0, com_venda_pct=3.0)
    assert com_default == com_explicito


def test_cust_var_marg_cont_bate_com_provisoes_orcamento_com_item_especial():
    """CONFERIR A IRMÃ (pedido explícito do Marcelo): cust_var_marg_cont (painel da AF, recalcula
    de um `itens` snapshot) tem que produzir o MESMO Cust_Var que provisoes_orcamento (o motor)
    pro MESMO orçamento — o comentário de `_RUBRICAS` existe pra evitar as duas fórmulas
    divergindo silenciosamente. `itens_provisao` é a ponte entre as duas (o que popula o
    snapshot); ambas têm que fechar com item_especial > 0."""
    siglas_com = _siglas(5000.0)
    d = dict(siglas_com)
    prov = mod_provisoes.provisoes_orcamento(siglas_com, _CFG, item_especial=5000.0, com_venda_pct=3.0)
    d.update(prov)
    cust_var_motor = d["Cust_Var"]

    itens = mod_provisoes.itens_provisao(d)
    assert itens["item_especial"] == 5000.0
    cust_var_af, marg_af = mod_provisoes.cust_var_marg_cont(d["CFO"], d["Val_Liq"], itens)
    assert cust_var_af == cust_var_motor == 73600.0
    assert marg_af == prov["Marg_Cont"] == 0.1341


def test_faixa_de_comissao_nao_muda_por_causa_do_item_especial():
    """Medido (07/09): a FAIXA de comissão de venda era resolvida com o Val_Liq CHEIO — um item
    grande podia empurrar o consultor pra uma faixa superior (% maior) sobre a venda INTEIRA, o
    efeito mais caro e menos visível. Faixas: até 82.000 -> 2,0%; acima -> 3,0%.

    Val_Liq sem item = 80.000 (dentro de 2,0%). Val_Liq CHEIO com item de 5.000 = 85.000
    (cruzaria pra 3,0% se o item contasse) — confirma que o efeito medido é real. A correção
    (main.py, _negociacao_breakdown) passa Val_Liq − item_especial pra resolver_comissao_venda:
    80.000 de novo, a MESMA faixa de antes do item."""
    cfg = {"comissao_vendas": {"faixas_comissao": [
        {"venda_ate": 82000.0, "pct": 2.0}, {"venda_ate": None, "pct": 3.0}]}}
    pct_sem_item = mod_provisoes.resolver_comissao_venda(cfg, 80000.0, 0.0)
    assert pct_sem_item == 2.0

    pct_errado_val_liq_cheio = mod_provisoes.resolver_comissao_venda(cfg, 85000.0, 0.0)
    assert pct_errado_val_liq_cheio == 3.0, "confirma que o efeito medido é real: cruza faixa"

    pct_certo_base_sem_item = mod_provisoes.resolver_comissao_venda(cfg, 85000.0 - 5000.0, 0.0)
    assert pct_certo_base_sem_item == pct_sem_item == 2.0, (
        "com a base correta (Val_Liq - item_especial), a faixa não muda por causa do item")
