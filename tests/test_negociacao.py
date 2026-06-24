# tests/test_negociacao.py
import mod_negociacao as mn

# LELEU oç1 — params do projeto, todos os toggles ON (spec §9)
PARAMS = {"incluir_custos": True, "comissao_arq_pct": 10.0, "comissao_arq_ativa": True,
          "fidelidade_pct": 2.0, "fidelidade_ativa": True, "fora_da_sede": True,
          "custo_viagem": 2000.0, "brinde": 500.0, "brinde_ativo": True, "carga_trib": 8.0}
AMBS = [{"VBVA": 22830.99, "CFA": 22830.99, "desc_amb_pct": 0.0},
        {"VBVA": 2650.50,  "CFA": 953.40,   "desc_amb_pct": 0.0}]

def _ap(a, b, tol=0.02): assert abs(a - b) <= tol, f"{a} != {b}"

def test_leleu_ancora():
    # comissão em cadeia (arq não ganha sobre fid; ambos excluem viagem/brinde)
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0, cust_fin=1413.44)
    _ap(r["VBVO"], 25481.49); _ap(r["CFO"], 23784.39)
    _ap(r["VBNO"], 32015.58); _ap(r["VAVO"], 25612.46)
    _ap(r["Com_Arq"], 2265.02); _ap(r["Pro_Fid"], 462.25)
    _ap(r["Cust_Ad"], 5227.27); _ap(r["Val_Liq"], 20385.19)
    _ap(r["Desc_Tot"] * 100, 20.00, tol=0.02); _ap(r["Markup"], 0.857, tol=0.002)
    _ap(r["Val_Cont"], r["VAVO"] + 1413.44); _ap(r["Prov_Imp"], 0.08 * r["Val_Cont"], tol=0.05)
    ag = r["ambientes"][0]
    _ap(ag["VBNA"], 28437.93); _ap(ag["VAVA"], 22750.35)

def test_protecao_total_com_cadeia():
    # com a comissão em cadeia, todos os custos repassados são recuperados 100%:
    # o líquido COM custos (Tog_Cadi true) = líquido SEM custo nenhum, e Desc_Tot == Desc_Orc.
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0)
    _ap(r["Val_Liq"], r["VBVO"] * 0.80)            # 20385.19 — proteção total
    _ap(r["Desc_Tot"] * 100, 20.00, tol=0.02)      # desconto total == desconto do orçamento

def test_comissao_exclui_custos_no_absorve():
    # absorve (Tog_Cadi false): a comissão NÃO incide sobre viagem/brinde — a base é
    # VAVA − viagem − brinde mesmo a loja absorvendo os custos (fórmula sem condição de toggle).
    p = {"incluir_custos": False, "fidelidade_pct": 2.0, "fidelidade_ativa": True,
         "fora_da_sede": True, "custo_viagem": 2000.0, "brinde": 500.0, "brinde_ativo": True,
         "comissao_arq_ativa": False}
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    vavo = r["VBVO"] * 0.80                          # 20385.19 (absorve, só desconto)
    pro_esperado = 0.02 * (vavo - 2000 - 500)        # 357.70 — exclui viagem+brinde
    _ap(r["Pro_Fid"], pro_esperado)
    _ap(r["Val_Liq"], vavo - (pro_esperado + 2000 + 500))   # 17527.49

def test_brinde_blindado_do_desconto():
    # brinde repassado (Tog_Cadi) deve ser recuperado 100% mesmo com desconto:
    # o líquido com só brinde deve igualar o líquido sem custo nenhum.
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 0.0}]
    so_brinde = {"incluir_custos": True, "brinde": 100.0, "brinde_ativo": True}
    r = mn.calcular_orcamento(ambs, so_brinde, 20.0)
    _ap(r["Val_Liq"], 800.0)            # 1000*(1-0.20) — brinde totalmente recuperado

def test_tog_cadi_off_absorve():
    # sem gross-up: VBNA = VBVA; custos ainda abatem o líquido
    p = {**PARAMS, "incluir_custos": False}
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    _ap(r["VBNO"], r["VBVO"])                      # VBNA = VBVA
    _ap(r["VAVO"], r["VBVO"] * 0.80)              # só o desconto
    assert r["Cust_Ad"] > 0                        # custos seguem abatendo

def test_toggle_individual_zera_componente():
    p = {**PARAMS, "brinde_ativo": False, "fora_da_sede": False}  # sem brinde nem viagem
    r = mn.calcular_orcamento(AMBS, p, 20.0)
    # Cust_Ad = só Com_Arq + Pro_Fid, em cadeia: fid + arq·(1-fid) = 0.02 + 0.10·0.98 = 0.118
    _ap(r["Cust_Ad"], 0.118 * r["VAVO"], tol=0.05)

def test_desc_amb_por_ambiente():
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 50.0}]
    p = {"incluir_custos": False}
    r = mn.calcular_orcamento(ambs, p, 0.0)
    _ap(r["VAVO"], 500.0)                          # 1000 * (1-0.50)

def test_orcamento_vazio_nao_quebra():
    r = mn.calcular_orcamento([], {"incluir_custos": False}, 0.0)
    assert r["VBVO"] == 0 and r["Markup"] == 0 and r["Val_Liq"] == 0

def test_retorna_cust_via_e_bri():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": True, "custo_viagem": 300,
         "brinde_ativo": True, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 300.0
    assert d["Bri"] == 200.0
    # cadeia fecha: VAVO − Com_Arq − Pro_Fid − Cust_Via − Bri == Val_Liq
    assert abs((d["VAVO"] - d["Com_Arq"] - d["Pro_Fid"] - d["Cust_Via"] - d["Bri"]) - d["Val_Liq"]) < 0.05

def test_cust_via_bri_zerados_quando_toggle_off():
    amb = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "fora_da_sede": False, "custo_viagem": 300,
         "brinde_ativo": False, "brinde": 200}
    d = __import__("mod_negociacao").calcular_orcamento(amb, p, 0)
    assert d["Cust_Via"] == 0.0 and d["Bri"] == 0.0


def test_distribuicao_3_de_7():
    """Projeto com 7 ambientes (pool), orçamento com 3 → brinde 3/7; viagem proporcional."""
    # orçamento = 3 ambientes (valores 10000, 10000, 10000); projeto = 7 ambientes
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    n_total_proj = 7
    vbvo_proj = 70000.0                      # 7 × 10000 (todos iguais p/ simplificar)
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0, n_total_proj=n_total_proj, vbvo_proj=vbvo_proj)
    # brinde recuperado = 3 × (700/7) = 300
    assert abs(d["Bri"] - 300.0) < 0.01
    # viagem recuperada = 700 × (30000/70000) = 300
    assert abs(d["Cust_Via"] - 300.0) < 0.01


def test_ambiente_expoe_waterfall_e_soma_bate():
    """Cada ambiente expõe Com_Arq/Pro_Fid/Cust_Via/Bri/Val_Liq; a soma bate com os agregados."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0},
            {"VBVA": 20000, "CFA": 8000, "desc_amb_pct": 0}]
    p = {"incluir_custos": True, "comissao_arq_ativa": True, "comissao_arq_pct": 10,
         "fidelidade_ativa": True, "fidelidade_pct": 5, "fora_da_sede": True,
         "custo_viagem": 600, "brinde_ativo": True, "brinde": 400}
    d = mn.calcular_orcamento(ambs, p, 5)
    aa = d["ambientes"]
    for a in aa:
        for k in ("Com_Arq", "Pro_Fid", "Cust_Via", "Bri", "Val_Liq"):
            assert k in a
        assert abs(a["Val_Liq"] - (a["VAVA"] - a["Com_Arq"] - a["Pro_Fid"]
                                   - a["Cust_Via"] - a["Bri"])) < 0.01
    assert abs(sum(a["Com_Arq"]  for a in aa) - d["Com_Arq"])  < 0.02
    assert abs(sum(a["Pro_Fid"]  for a in aa) - d["Pro_Fid"])  < 0.02
    assert abs(sum(a["Cust_Via"] for a in aa) - d["Cust_Via"]) < 0.02
    assert abs(sum(a["Bri"]      for a in aa) - d["Bri"])      < 0.02
    assert abs(sum(a["Val_Liq"]  for a in aa) - d["Val_Liq"])  < 0.02


def test_fallback_sem_contexto_inalterado():
    """Sem n_total_proj/vbvo_proj → comportamento atual (orçamento recebe o valor cheio)."""
    ambs = [{"VBVA": 10000, "CFA": 4000, "desc_amb_pct": 0} for _ in range(3)]
    p = {"incluir_custos": False, "fora_da_sede": True, "custo_viagem": 700,
         "brinde_ativo": True, "brinde": 700}
    d = mn.calcular_orcamento(ambs, p, 0)    # sem contexto
    assert abs(d["Bri"] - 700.0) < 0.01      # cheio
    assert abs(d["Cust_Via"] - 700.0) < 0.01 # cheio
