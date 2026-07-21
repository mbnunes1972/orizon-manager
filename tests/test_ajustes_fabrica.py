"""Descontos e Acréscimos Excepcionais de Fábrica — motor PURO (mod_ajustes_fabrica).

Spec: docs/superpowers/specs/financeiro/2026-07-21-descontos-acrescimos-excepcionais-fabrica-design.md
Ordem fixa: DESCONTOS sobre o valor conferido; ACRÉSCIMOS sobre o pós-descontos.
Exemplos numéricos da spec fecham ao centavo.
"""
import mod_ajustes_fabrica as maf


def _aj(id, tipo, pct, tratamento, acordo_id=None, **kw):
    base = {"id": id, "tipo": tipo, "pct": pct, "tratamento": tratamento,
            "acordo_id": acordo_id, "natureza": "recorrente", "ativo": True,
            "vigencia_de": None, "vigencia_ate": None, "projetos": None,
            "base": "pos_descontos"}
    base.update(kw)
    return base


def test_exemplo_loja3_100k_95k_104k5():
    # spec: pedido 100.000 → 5% off (custo) = 95.000; NF-e com +10% (consumir_saldo) = 104.500
    ajustes = [_aj(1, "desconto", 5.0, "custo"),
               _aj(2, "acrescimo", 10.0, "consumir_saldo", acordo_id=7)]
    r = maf.calcular_aplicacoes(100000.0, ajustes, disponiveis={7: 999999.0})
    assert r["custo_fabrica_final"] == 95000.0          # CMV futuro (só descontos de CUSTO)
    assert r["a_pagar_final"] == 104500.0               # casa com a NF-e da fábrica
    ap = {a["id"]: a for a in r["aplicacoes"]}
    assert ap[1]["valor"] == 5000.0 and ap[1]["base_calculo"] == 100000.0
    assert ap[2]["valor"] == 9500.0 and ap[2]["base_calculo"] == 95000.0   # sobre o pós-descontos
    assert not ap[2]["capado"]


def test_exemplo_inspirium_3pct_credito():
    # spec: paga 97.000 à fábrica, CMV segue 100.000 (consumir_saldo não muda custo econômico)
    ajustes = [_aj(1, "desconto", 3.0, "consumir_saldo", acordo_id=5)]
    r = maf.calcular_aplicacoes(100000.0, ajustes, disponiveis={5: 50000.0})
    assert r["custo_fabrica_final"] == 100000.0
    assert r["a_pagar_final"] == 97000.0
    assert r["aplicacoes"][0]["valor"] == 3000.0


def test_cap_ao_disponivel_consumo_parcial_e_esgotamento():
    # disponível menor que o % → aplica parcial, marca capado e esgota o acordo
    ajustes = [_aj(1, "desconto", 5.0, "consumir_saldo", acordo_id=9)]
    r = maf.calcular_aplicacoes(100000.0, ajustes, disponiveis={9: 1200.0})
    a = r["aplicacoes"][0]
    assert a["valor"] == 1200.0 and a["capado"] is True
    assert r["a_pagar_final"] == 98800.0
    assert 9 in r["acordos_esgotados"]


def test_dois_ajustes_no_mesmo_acordo_compartilham_o_cap():
    ajustes = [_aj(1, "desconto", 3.0, "consumir_saldo", acordo_id=5),
               _aj(2, "desconto", 5.0, "consumir_saldo", acordo_id=5)]
    r = maf.calcular_aplicacoes(100000.0, ajustes, disponiveis={5: 4000.0})
    ap = {a["id"]: a for a in r["aplicacoes"]}
    assert ap[1]["valor"] == 3000.0 and not ap[1]["capado"]
    assert ap[2]["valor"] == 1000.0 and ap[2]["capado"]     # sobrou só 1.000 do cap
    assert 5 in r["acordos_esgotados"]


def test_acrescimo_base_valor_conferido_opcional():
    ajustes = [_aj(1, "desconto", 5.0, "custo"),
               _aj(2, "acrescimo", 10.0, "consumir_saldo", acordo_id=7, base="valor_conferido")]
    r = maf.calcular_aplicacoes(100000.0, ajustes, disponiveis={7: 999999.0})
    ap = {a["id"]: a for a in r["aplicacoes"]}
    assert ap[2]["base_calculo"] == 100000.0 and ap[2]["valor"] == 10000.0
    assert r["a_pagar_final"] == 105000.0


def test_vigencia_inativo_e_janela():
    ajustes = [_aj(1, "desconto", 5.0, "custo", ativo=False),
               _aj(2, "desconto", 3.0, "custo", vigencia_de="2026-08-01"),
               _aj(3, "desconto", 2.0, "custo", vigencia_ate="2026-06-30"),
               _aj(4, "desconto", 1.0, "custo", vigencia_de="2026-07-01", vigencia_ate="2026-12-31")]
    r = maf.calcular_aplicacoes(100000.0, ajustes, hoje="2026-07-21")
    assert [a["id"] for a in r["aplicacoes"]] == [4]
    assert r["a_pagar_final"] == 99000.0


def test_pontual_so_no_projeto_vinculado():
    ajustes = [_aj(1, "desconto", 5.0, "custo", natureza="pontual", projetos=["Proj_A"])]
    r = maf.calcular_aplicacoes(100000.0, ajustes, projeto="Proj_B")
    assert r["aplicacoes"] == []
    r2 = maf.calcular_aplicacoes(100000.0, ajustes, projeto="Proj_A")
    assert r2["aplicacoes"][0]["valor"] == 5000.0


def test_arredondamento_por_aplicacao():
    # round(…, 2) POR aplicação; encadeamento usa o valor arredondado
    ajustes = [_aj(1, "desconto", 3.333, "custo"),
               _aj(2, "acrescimo", 7.777, "consumir_saldo", acordo_id=1)]
    r = maf.calcular_aplicacoes(999.99, ajustes, disponiveis={1: 999999.0})
    d = round(999.99 * 0.03333, 2)                       # 33.33
    pos = round(999.99 - d, 2)                           # 966.66
    a = round(pos * 0.07777, 2)                          # 75.18
    ap = {x["id"]: x for x in r["aplicacoes"]}
    assert ap[1]["valor"] == d and ap[2]["valor"] == a
    assert r["a_pagar_final"] == round(pos + a, 2)


def test_disponivel_acordo():
    assert maf.disponivel_acordo(10000.0, 3000.0) == 7000.0
    assert maf.disponivel_acordo(1000.0, 2500.0) == 0.0    # nunca negativo
