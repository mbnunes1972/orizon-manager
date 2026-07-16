"""Fatia 1 — comparação de CUSTO DE FÁBRICA (CFO) venda × PE + saldo gerencial de margem.
Função pura, sem contabilidade nem ciclo.
Spec: docs/superpowers/specs/2026-07-13-desmembramento-pe-parcial-design.md §4(#4,#9), §6."""
import os
from mod_pe_comparacao import (montar_comparacao_pe, saldo_margem_estimado, extrair_cfo_pe,
                               reconciliacao_estimada)


def test_reconciliacao_estimada_so_cfo_se_move_e_ancora_no_val_cont():
    # #9/opção 1: todas as rubricas; só a de Custo de Fábrica (2.1.04.06) muda no Estimado (delta_cfo);
    # as demais seguem o contrato; margem referenciada ao Val_Cont.
    provisoes = [
        {"codigo": "2.1.04.06", "nome": "Provisão de Custo de Fábrica", "provisionado": 40000.0},
        {"codigo": "2.1.04.01", "nome": "Provisão de Comissão",         "provisionado": 10000.0},
    ]
    r = reconciliacao_estimada(provisoes, delta_cfo=2000.0, val_cont=100000.0)  # PE subiu o custo 2000

    cfo = next(l for l in r["linhas"] if l["codigo"] == "2.1.04.06")
    com = next(l for l in r["linhas"] if l["codigo"] == "2.1.04.01")
    assert cfo["estimado"] == 42000.0 and cfo["delta"] == 2000.0
    assert com["estimado"] == 10000.0 and com["delta"] == 0.0        # rubrica não-CFO não se move (Fatia 1)
    assert r["margem_contratada"] == 50000.0                          # 100000 - (40000+10000)
    assert r["margem_estimada"] == 48000.0                            # custo subiu 2000 → margem cai 2000
    assert r["delta_total"] == 2000.0
    assert len(r["linhas"]) == 2                                      # mostra TODAS as rubricas
    # margem % — indicador de topo (consolida o conjunto)
    assert r["margem_contratada_pct"] == 50.0                         # 50000/100000
    assert r["margem_estimada_pct"] == 48.0                           # 48000/100000
    assert r["delta_pct"] == -2.0                                     # pontos percentuais de margem perdidos
from integracoes.promob_grupos import ler_xml_str


def test_extrai_cfo_de_venda_nao_o_total():
    # decisão #4: o valor extraído do XML é o CUSTO (Σ order_total), não o total de venda-bruta.
    caminho = "PROJETOS/Casa_Nova/xmls/Cozinha.xml"
    if not os.path.exists(caminho):
        import pytest; pytest.skip("XML de exemplo ausente")
    conteudo = open(caminho, "rb").read()
    amb = ler_xml_str("Cozinha.xml", conteudo)
    cfo = round(sum(i.get("order_total", 0.0) for g in amb.get("grupos", [])
                    for i in g.get("itens", [])), 2)
    assert extrair_cfo_pe("Cozinha.xml", conteudo) == cfo
    assert cfo > 0
    # e é uma grandeza diferente do total de venda-bruta (guard contra usar o campo errado)
    assert extrair_cfo_pe("Cozinha.xml", conteudo) != round(amb.get("total", 0.0), 2) or amb.get("total", 0.0) == cfo


def test_ambiente_com_e_sem_pe():
    # itens_cfo_original = CFO por ambiente já no pool (PoolAmbiente.order_total), decisão #4.
    itens_cfo = [("Cozinha", 6000.0), ("Dormitório", 3000.0)]
    valores_pe = {"Cozinha": 6300.0}   # só a Cozinha teve XML de PE carregado

    linhas = montar_comparacao_pe(itens_cfo, valores_pe)

    coz, dorm = linhas
    # com PE: diferenca = cfo_pe - cfo_original (§6 invariante 2)
    assert coz == {"ambiente": "Cozinha", "cfo_original": 6000.0,
                   "cfo_pe": 6300.0, "diferenca": 300.0, "pe_carregado": True}
    # sem PE: cfo_pe=0, não carregado, diferenca = -cfo_original (invariante 1)
    assert dorm["cfo_pe"] == 0
    assert dorm["pe_carregado"] is False
    assert dorm["diferenca"] == -3000.0


def test_ordem_e_rotulos_seguem_o_cfo_original():
    linhas = montar_comparacao_pe([("B", 1.0), ("A", 2.0)], {})
    assert [l["ambiente"] for l in linhas] == ["B", "A"]


def test_diferenca_arredondada_a_2_casas():
    linhas = montar_comparacao_pe([("X", 0.1)], {"X": 0.3})
    assert linhas[0]["diferenca"] == 0.2


def test_saldo_margem_estimado_soma_so_ambientes_com_pe():
    # #9: saldo = Σ(cfo_original - cfo_pe) só dos ambientes com PE carregado.
    # positivo = custo caiu = margem melhorou.
    linhas = montar_comparacao_pe(
        [("A", 6000.0), ("B", 3000.0), ("C", 1000.0)],
        {"A": 5800.0, "B": 3200.0},          # C sem PE
    )
    # A: 6000-5800=+200 ; B: 3000-3200=-200 ; C: sem PE → 0  →  soma = 0
    assert saldo_margem_estimado(linhas) == 0.0

    # só A com PE, custo caiu 200 → margem estimada +200
    assert saldo_margem_estimado(montar_comparacao_pe([("A", 6000.0)], {"A": 5800.0})) == 200.0

    # custo subiu → margem estimada negativa
    assert saldo_margem_estimado(montar_comparacao_pe([("A", 6000.0)], {"A": 6250.0})) == -250.0
