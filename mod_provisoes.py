# -*- coding: utf-8 -*-
"""mod_provisoes.py — Provisões pós-fechamento e margem real (PURO, sem I/O).

Recebe as siglas do motor (mod_negociacao) + a config financeira da loja e devolve
as provisões por orçamento, Cust_Var e Marg_Cont. Percentuais em número-percent
(10 = 10%), divididos por 100 aqui — mesma convenção do mod_negociacao.
Fórmulas fechadas: docs/modulos/financeiro/PROVISOES_E_VARIAVEIS.md.
"""

_PROV_KEYS = ("frete_fab_pct", "com_adm_pct", "com_med_pct", "com_proj_exec_pct",
              "frete_loc_pct", "assist_pct", "ins_loc_pct")


def _f(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def config_financeira_default():
    return {
        "defaults_negociacao": {"comissao_arq_pct": 0.0, "fidelidade_pct": 0.0, "carga_trib_pct": 0.0},
        "provisoes": {k: 0.0 for k in _PROV_KEYS},
        # v6 §6.4: % contábil das provisões constituídas no fechamento (Financeiro, desacoplado do preço).
        # assistencia herda provisoes.assist_pct → não fica aqui; só montagem/garantia são config nova.
        "provisoes_contabeis": {"montagem_pct": 0.0, "garantia_pct": 0.0, "comissao_pct": 0.0},
        # Fatia C (#10): limites de aumento de custo na Aprovação Financeira que exigem step-up do Diretor.
        "aprovacao_financeira": {"limite_af1_pct": 1.0, "limite_af2_pct": 2.0},
        "comissao_vendas": {
            "meta_mensal": 0.0,
            "faixas_comissao": [{"venda_ate": None, "pct": 0.0}],
            "limitador_desconto": {"ativo": False, "base_desconto": "Desc_Orc", "limites": []},
        },
        # Cronograma de Projeto Padrão (Modulos_Orizon_v11): prazo em dias a partir de D0 (assinatura
        # do contrato) por etapa do ciclo. Na assinatura, cada etapa ganha data_prevista = D0 + prazo.
        "cronograma_padrao": [
            {"codigo": "8",  "prazo_dias": 2},   {"codigo": "9",  "prazo_dias": 5},
            {"codigo": "10", "prazo_dias": 10},  {"codigo": "11", "prazo_dias": 20},
            {"codigo": "12", "prazo_dias": 25},  {"codigo": "13", "prazo_dias": 45},
            {"codigo": "14", "prazo_dias": 50},  {"codigo": "15", "prazo_dias": 52},
            {"codigo": "16", "prazo_dias": 55},  {"codigo": "17", "prazo_dias": 60},
            {"codigo": "18", "prazo_dias": 63},  {"codigo": "19", "prazo_dias": 68},
            {"codigo": "20", "prazo_dias": 70},
        ],
    }


def validar_config_financeira(dados):
    erros = []
    d = dados or {}
    prov = d.get("provisoes", {})
    for k in _PROV_KEYS:
        if _f(prov.get(k)) < 0:
            erros.append(f"Provisão {k} não pode ser negativa.")
        elif _f(prov.get(k)) > 100:
            erros.append(f"Provisão {k} não pode passar de 100%.")
    for k, v in (d.get("defaults_negociacao", {}) or {}).items():
        if _f(v) < 0:
            erros.append(f"Default {k} não pode ser negativo.")
        elif _f(v) > 100:
            erros.append(f"Default {k} não pode passar de 100%.")
    for k in ("montagem_pct", "garantia_pct", "comissao_pct"):     # provisões contábeis (v6 §6.4 / v8 Config)
        v = (d.get("provisoes_contabeis", {}) or {}).get(k)
        if _f(v) < 0 or _f(v) > 100:
            erros.append(f"Provisão contábil {k} deve estar entre 0 e 100%.")
    cv = d.get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", [])
    if not faixas:
        erros.append("Comissão de vendas precisa de ao menos uma faixa.")
    for fx in faixas:
        if "pct" not in fx:
            erros.append("Cada faixa de comissão precisa de 'pct'.")
        elif _f(fx.get("pct")) < 0:
            erros.append("Percentual de faixa não pode ser negativo.")
        elif _f(fx.get("pct")) > 100:
            erros.append("Percentual de faixa não pode passar de 100%.")
    for lim in (cv.get("limitador_desconto", {}) or {}).get("limites", []):
        if _f(lim.get("redutor_pct")) < 0 or _f(lim.get("desconto_acima_de")) < 0:
            erros.append("Limite de desconto com valor negativo.")
        if _f(lim.get("redutor_pct")) > 100:
            erros.append("Limite de desconto fora de 0–100%.")
        if _f(lim.get("desconto_acima_de")) > 100:
            erros.append("Limite de desconto fora de 0–100%.")
    return erros


def resolver_comissao_venda(cfg, val_liq_mes, desc_orc_pct):
    cv = (cfg or {}).get("comissao_vendas", {}) or {}
    faixas = cv.get("faixas_comissao", []) or []
    pct = 0.0
    for fx in faixas:
        ate = fx.get("venda_ate")
        if ate is None or _f(val_liq_mes) < _f(ate):
            pct = _f(fx.get("pct"))
            break
    else:
        pct = _f(faixas[-1].get("pct")) if faixas else 0.0
    lim = cv.get("limitador_desconto", {}) or {}
    if lim.get("ativo"):
        redutor = 0.0
        for L in sorted(lim.get("limites", []) or [], key=lambda x: _f(x.get("desconto_acima_de"))):
            if _f(desc_orc_pct) > _f(L.get("desconto_acima_de")):
                redutor = _f(L.get("redutor_pct"))
        pct = pct * (1 - redutor / 100.0)
    return round(pct, 4)


# IMPORTANTE: estas 12 rubricas são exatamente os addendos de Cust_Var em provisoes_orcamento
# (CFO + out_forn + as 8 rubricas % + Prov_Imp + Prov_Mont + Prov_Gar). cust_var_marg_cont recalcula
# Cust_Var como CFO + Σ(itens) — então, ao adicionar/remover uma rubrica do motor, atualize ESTE mapa
# também, senão as duas fórmulas de Cust_Var divergem silenciosamente.
_RUBRICAS = {
    "frete_fab": "Frete_Fab_Orc", "com_adm": "Com_Adm_Orc", "com_venda": "Com_Venda_Orc",
    "com_med": "Com_Med_Orc", "com_proj_exec": "Com_Proj_Exec_Orc", "frete_loc": "Frete_Loc_Orc",
    "assist": "Assist_Orc", "ins_loc": "Ins_Loc_Orc", "prov_imp": "Prov_Imp", "out_forn": "Out_Forn",
    "prov_mont": "Prov_Mont", "prov_gar": "Prov_Gar",   # FASE 2: fold Montagem/Garantia (visão)
}


def itens_provisao(siglas):
    """Extrai as 10 rubricas de provisão do breakdown do motor (dict {rubrica: valor R$})."""
    s = siglas or {}
    return {k: round(_f(s.get(v)), 2) for k, v in _RUBRICAS.items()}


def margens_venda(vavo, cust_ad, cust_var, val_cont):
    """As TRÊS margens da venda (VISÃO da negociação) — todas com o MESMO numerador (margem em R$ =
    VAVO − Cust_Ad − Cust_Var), expressas sobre bases crescentes:
      - margem_contribuicao : base val_liq_loja = VAVO − Cust_Ad (base das comissões internas da loja)
      - margem_venda        : base VAVO (valor à vista)
      - margem_contrato     : base Val_Cont (inclui o custo financeiro — que se cancela no numerador)
    Invariante (quando a margem em R$ é POSITIVA): margem_contribuicao >= margem_venda >= margem_contrato
    (bases crescentes). Em prejuízo (margem R$ < 0) a ordem se inverte — a divisão por base maior deixa o
    número "menos negativo" —, o que é aritmeticamente correto; a leitura de % assume venda com lucro.
    NÃO confundir com a **Margem Operacional** (4ª margem), que é da DRE — após TODOS os custos, derivada
    do razão, não da negociação. Estas três são VISÃO managerial (não lançam nada); o RESULTADO financeiro
    (receita/despesa) é indicador à parte (ramo loja×financeira).
    """
    vavo = _f(vavo); cust_ad = _f(cust_ad); cust_var = _f(cust_var); val_cont = _f(val_cont)
    val_liq_loja = vavo - cust_ad
    margem_rs = round(vavo - cust_ad - cust_var, 2)
    _m = lambda base: round(margem_rs / base, 4) if base else 0.0
    return {
        "margem_rs": margem_rs,
        "margem_contribuicao": _m(val_liq_loja),
        "margem_venda": _m(vavo),
        "margem_contrato": _m(val_cont),
    }


def cust_var_marg_cont(cfo, val_liq, itens):
    """Recalcula (Cust_Var, Marg_Cont) a partir de itens (possivelmente editados).
    Cust_Var = CFO + Σ itens (os itens já incluem out_forn e prov_imp)."""
    cust_var = round(_f(cfo) + sum(_f(v) for v in (itens or {}).values()), 2)
    vl = _f(val_liq)
    marg = round((vl - cust_var) / vl, 4) if vl else 0.0
    return cust_var, marg


def provisoes_orcamento(siglas, cfg, out_forn=0.0, com_venda_pct=0.0):
    s = siglas or {}
    CFO = _f(s.get("CFO")); Val_Liq = _f(s.get("Val_Liq"))
    VAVO = _f(s.get("VAVO")); Prov_Imp = _f(s.get("Prov_Imp"))
    prov = (cfg or {}).get("provisoes", {}) or {}
    pc = (cfg or {}).get("provisoes_contabeis", {}) or {}
    out_forn = _f(out_forn)

    frete_fab = _f(prov.get("frete_fab_pct")) / 100.0 * CFO
    com_adm   = _f(prov.get("com_adm_pct"))   / 100.0 * Val_Liq
    com_venda = _f(com_venda_pct)             / 100.0 * Val_Liq
    com_med   = _f(prov.get("com_med_pct"))   / 100.0 * Val_Liq
    com_proj  = _f(prov.get("com_proj_exec_pct")) / 100.0 * Val_Liq
    frete_loc = _f(prov.get("frete_loc_pct")) / 100.0 * VAVO
    assist    = _f(prov.get("assist_pct"))    / 100.0 * VAVO
    ins_loc   = _f(prov.get("ins_loc_pct"))   / 100.0 * VAVO
    # Fold (FASE 2): provisões contábeis de Montagem/Garantia entram no Cust_Var — base = VAVO
    # (convenção canônica de bases, NOMENCLATURA §"Bases": provisões % sobre a VENDA usam VAVO, valor à
    # vista, DEPOIS de extrair o Cust_Fin) e MESMO arredondamento da constituição no fechamento
    # (mod_contabil.constituir_provisoes_venda, também base VAVO). É VISÃO: não lança nada no razão.
    prov_mont = round(_f(pc.get("montagem_pct")) / 100.0 * VAVO, 2)
    prov_gar  = round(_f(pc.get("garantia_pct")) / 100.0 * VAVO, 2)

    cust_var = (CFO + out_forn + frete_fab + com_adm + com_venda + com_med
                + com_proj + frete_loc + assist + ins_loc + Prov_Imp + prov_mont + prov_gar)
    marg_cont = ((Val_Liq - cust_var) / Val_Liq) if Val_Liq else 0.0
    return {
        "Frete_Fab_Orc": round(frete_fab, 2), "Com_Adm_Orc": round(com_adm, 2),
        "Com_Venda_Orc": round(com_venda, 2), "Com_Med_Orc": round(com_med, 2),
        "Com_Proj_Exec_Orc": round(com_proj, 2), "Frete_Loc_Orc": round(frete_loc, 2),
        "Assist_Orc": round(assist, 2), "Ins_Loc_Orc": round(ins_loc, 2),
        "Out_Forn": round(out_forn, 2),
        "Prov_Mont": prov_mont, "Prov_Gar": prov_gar,
        "Cust_Var": round(cust_var, 2), "Marg_Cont": round(marg_cont, 4),
    }
