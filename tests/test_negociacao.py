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
    r = mn.calcular_orcamento(AMBS, PARAMS, 20.0, cust_fin=1413.44)
    _ap(r["VBVO"], 25481.49); _ap(r["CFO"], 23784.39)
    _ap(r["VBNO"], 31890.58); _ap(r["VAVO"], 25512.46)
    _ap(r["Cust_Ad"], 5561.50); _ap(r["Val_Liq"], 19950.97)
    _ap(r["Desc_Tot"] * 100, 21.70, tol=0.05); _ap(r["Markup"], 0.839, tol=0.002)
    _ap(r["Val_Cont"], 26925.90); _ap(r["Prov_Imp"], 0.08 * r["Val_Cont"], tol=0.05)
    ag = r["ambientes"][0]
    _ap(ag["VBNA"], 28375.43); _ap(ag["VAVA"], 22700.35)

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
    # Cust_Ad = só Com_Arq + Pro_Fid (12% do VAVO)
    _ap(r["Cust_Ad"], (0.12) * r["VAVO"], tol=0.05)

def test_desc_amb_por_ambiente():
    ambs = [{"VBVA": 1000.0, "CFA": 400.0, "desc_amb_pct": 50.0}]
    p = {"incluir_custos": False}
    r = mn.calcular_orcamento(ambs, p, 0.0)
    _ap(r["VAVO"], 500.0)                          # 1000 * (1-0.50)

def test_orcamento_vazio_nao_quebra():
    r = mn.calcular_orcamento([], {"incluir_custos": False}, 0.0)
    assert r["VBVO"] == 0 and r["Markup"] == 0 and r["Val_Liq"] == 0
