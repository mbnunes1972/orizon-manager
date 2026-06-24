# -*- coding: utf-8 -*-
"""mod_negociacao.py — Motor de cálculo da negociação (PURO, sem I/O).

Cálculo por ambiente (gross-up divisivo), agregado por orçamento. Siglas conforme
docs/superpowers/specs/2026-06-22-mecanismo-negociacao-design.md (§3/§4).
"""


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_orcamento(ambientes, params, desc_orc_pct, cust_fin=0.0, n_total_proj=None, vbvo_proj=None):
    """Ver docstring do plano/§4. `params` no formato parametros_json do projeto."""
    p = params or {}
    tog_cadi = bool(p.get("incluir_custos", False))      # master: repassa/absorve
    tog_carq = bool(p.get("comissao_arq_ativa", False))
    tog_fid  = bool(p.get("fidelidade_ativa", False))
    tog_cvia = bool(p.get("fora_da_sede", False))
    tog_bri  = bool(p.get("brinde_ativo", False))
    pct_arq  = _f(p.get("comissao_arq_pct")) / 100.0
    pct_fid  = _f(p.get("fidelidade_pct")) / 100.0
    cust_via = _f(p.get("custo_viagem"))
    bri      = _f(p.get("brinde"))
    pct_trib = _f(p.get("carga_trib")) / 100.0
    d_orc    = _f(desc_orc_pct) / 100.0

    ambs = [{"VBVA": _f(a.get("VBVA")), "CFA": _f(a.get("CFA")),
             "d_amb": _f(a.get("desc_amb_pct")) / 100.0} for a in (ambientes or [])]
    num_amb = len(ambs)
    VBVO = sum(a["VBVA"] for a in ambs)
    CFO  = sum(a["CFA"] for a in ambs)

    out_ambs = []
    VBNO = VAVO = 0.0
    com_arq = pro_fid = 0.0
    total_via = total_bri = 0.0
    for a in ambs:
        vbva, d_amb = a["VBVA"], a["d_amb"]
        fator_desc = (1 - d_orc) * (1 - d_amb)
        # parcelas de viagem (rateada) e brinde (igual/amb) deste ambiente
        den_via = vbvo_proj if vbvo_proj else VBVO          # projeto (proporcional) ou orçamento (fallback)
        den_bri = n_total_proj if n_total_proj else num_amb  # projeto (igual) ou orçamento (fallback)
        num_via = (cust_via * (vbva / den_via)) if (tog_cvia and den_via > 0) else 0.0
        num_bri = (bri / den_bri) if (tog_bri and den_bri) else 0.0
        if tog_cadi:
            fator_com = (1 - pct_arq if tog_carq else 1.0) * (1 - pct_fid if tog_fid else 1.0)
            termo_arqfid = (vbva / fator_com) if fator_com > 0 else vbva
            # viagem + brinde blindados do desconto (/fator_desc) → recuperados 100%
            termo_via_bri = ((num_via + num_bri) / fator_desc) if fator_desc > 0 else 0.0
            vbna = termo_arqfid + termo_via_bri
        else:
            vbna = vbva
        vava = vbna * fator_desc
        # comissão em cadeia, por ambiente: arq NÃO ganha sobre fid; e nem arq nem fid
        # ganham sobre viagem/brinde — a base exclui esses custos SEMPRE (repassados ou
        # absorvidos), conforme a fórmula `VAVA − viagem − brinde`.
        base_custos = num_via + num_bri
        pro_amb = (pct_fid * (vava - base_custos)) if tog_fid else 0.0
        com_amb = (pct_arq * (vava - pro_amb - base_custos)) if tog_carq else 0.0
        pro_fid += pro_amb
        com_arq += com_amb
        total_via += num_via
        total_bri += num_bri
        VBNO += vbna
        VAVO += vava
        liq_amb = vava - com_amb - pro_amb - num_via - num_bri
        out_ambs.append({"VBVA": round(vbva, 2), "CFA": round(a["CFA"], 2),
                         "VBNA": round(vbna, 2), "VAVA": round(vava, 2),
                         "Com_Arq": round(com_amb, 2), "Pro_Fid": round(pro_amb, 2),
                         "Cust_Via": round(num_via, 2), "Bri": round(num_bri, 2),
                         "Val_Liq": round(liq_amb, 2)})

    cust_ad = com_arq + pro_fid + (total_via if tog_cvia else 0.0) + (total_bri if tog_bri else 0.0)
    val_liq = VAVO - cust_ad
    desc_tot = ((VBVO - val_liq) / VBVO) if VBVO > 0 else 0.0
    markup = (val_liq / CFO) if CFO > 0 else 0.0
    val_cont = VAVO + _f(cust_fin)
    prov_imp = pct_trib * val_cont

    return {
        "VBVO": round(VBVO, 2), "CFO": round(CFO, 2), "VBNO": round(VBNO, 2),
        "VAVO": round(VAVO, 2), "Num_Amb": num_amb,
        "Com_Arq": round(com_arq, 2), "Pro_Fid": round(pro_fid, 2),
        "Cust_Via": round(total_via if tog_cvia else 0.0, 2),
        "Bri": round(total_bri if tog_bri else 0.0, 2),
        "Cust_Ad": round(cust_ad, 2),
        "Val_Liq": round(val_liq, 2), "Desc_Tot": round(desc_tot, 4), "Markup": round(markup, 3),
        "Cust_Fin": round(_f(cust_fin), 2), "Val_Cont": round(val_cont, 2), "Prov_Imp": round(prov_imp, 2),
        "ambientes": out_ambs,
    }
