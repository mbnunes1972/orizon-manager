"""Lógica pura dos parâmetros de negociação por orçamento (sem I/O).

- MARGENS_DEFAULT: valores padrão das 12 chaves de margens.
- merge_margens(atual, req): aplica sobre `atual` somente as chaves enviadas em `req`,
  coagindo tipos. Espelha o merge que antes vivia no handler POST /projetos/<nome>/margens.
- sanear_descontos(pares, ids_validos): normaliza {pool_ambiente_id: pct}, filtra ids fora
  do orçamento e exige 0 <= pct <= 100.
"""

MARGENS_DEFAULT = {
    "desconto_pct":         0.0,
    "custo_viagem":         0.0,
    "fora_da_sede":         False,
    "brinde":               0.0,
    "brinde_ativo":         False,
    "comissao_arq_pct":     0.0,
    "comissao_arq_ativa":   False,
    "fidelidade_pct":       0.0,
    "fidelidade_ativa":     False,
    "incluir_custos":       False,
    "carga_trib":           8.0,
}

_FLOAT_KEYS = ("desconto_pct", "custo_viagem", "brinde",
               "comissao_arq_pct", "fidelidade_pct", "carga_trib")
_BOOL_KEYS  = ("fora_da_sede", "brinde_ativo", "comissao_arq_ativa",
               "fidelidade_ativa", "incluir_custos")


def _coerce_bool(v):
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return bool(v)


def merge_margens(atual: dict, req: dict) -> dict:
    base = dict(MARGENS_DEFAULT)
    if atual:
        base.update({k: atual[k] for k in MARGENS_DEFAULT if k in atual})
    for k in _FLOAT_KEYS:
        if k in req:
            base[k] = float(req[k])
    for k in _BOOL_KEYS:
        if k in req:
            base[k] = _coerce_bool(req[k])
    return base


PARAMETROS_DEFAULT = {
    "incluir_custos":     False,
    "comissao_arq_pct":   0.0,
    "comissao_arq_ativa": False,
    "fidelidade_pct":     0.0,
    "fidelidade_ativa":   False,
    "fora_da_sede":       False,
    "custo_viagem":       0.0,
    "brinde":             0.0,
    "brinde_ativo":       False,
    "carga_trib":         8.0,
}

_PARAM_FLOAT_KEYS = ("comissao_arq_pct", "fidelidade_pct", "custo_viagem", "brinde", "carga_trib")
_PARAM_BOOL_KEYS  = ("incluir_custos", "comissao_arq_ativa", "fidelidade_ativa",
                     "fora_da_sede", "brinde_ativo")


def merge_parametros(atual: dict, req: dict) -> dict:
    base = dict(PARAMETROS_DEFAULT)
    if atual:
        base.update({k: atual[k] for k in PARAMETROS_DEFAULT if k in atual})
    for k in _PARAM_FLOAT_KEYS:
        if k in req:
            base[k] = float(req[k])
    for k in _PARAM_BOOL_KEYS:
        if k in req:
            base[k] = _coerce_bool(req[k])
    return base


def parametros_default_loja(cfg):
    """parametros_json inicial de um projeto, com defaults da loja sobre o PARAMETROS_DEFAULT."""
    base = dict(PARAMETROS_DEFAULT)
    base["incluir_custos"] = True   # padrão inicial: repassar custos adicionais ao cliente
    dn = (cfg or {}).get("defaults_negociacao", {}) or {}
    if "comissao_arq_pct" in dn: base["comissao_arq_pct"] = float(dn["comissao_arq_pct"] or 0)
    if "fidelidade_pct" in dn:   base["fidelidade_pct"]   = float(dn["fidelidade_pct"] or 0)
    if "carga_trib_pct" in dn:   base["carga_trib"]       = float(dn["carga_trib_pct"] or 0)
    return base


def sanear_descontos(pares, ids_validos) -> dict:
    ids_validos = set(ids_validos)
    out = {}
    itens = pares.items() if isinstance(pares, dict) else pares
    for pid, pct in itens:
        pid = int(pid)
        if pid not in ids_validos:
            continue
        pct = float(pct)
        if not (0 <= pct <= 100):
            raise ValueError(f"Desconto fora da faixa 0..100: {pct}")
        out[pid] = pct
    return out
