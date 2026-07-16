"""Comparação de CUSTO DE FÁBRICA (CFO) venda × Projeto Executivo (PE) — Fatia 1.

Lógica PURA (sem I/O, sem contabilidade, sem ciclo). O XML de PE vive fora do pool do orçamento
(tabela `arquivo_pe`); o valor extraído dele é um CFO/custo de fábrica (NÃO valor de venda — decisão
#4), comparável ao CFO original do pool (`PoolAmbiente.order_total`).
Spec: docs/superpowers/specs/2026-07-13-desmembramento-pe-parcial-design.md §4(#4,#9), §6.
"""


def montar_comparacao_pe(itens_cfo_original, valores_pe):
    """Monta a tabela de comparação de CFO ambiente a ambiente.

    itens_cfo_original: lista [(nome_exibicao, cfo_original), ...] — CFO por ambiente já no pool
                        (PoolAmbiente.order_total). Define ordem e rótulos (decisão #4).
    valores_pe:         dict {nome_exibicao: cfo_atualizado} extraído do XML de PE. Ambiente ausente
                        = XML de PE não carregado (cfo_pe = 0, pe_carregado = False).

    Retorna [{ambiente, cfo_original, cfo_pe, diferenca, pe_carregado}, ...] na ordem de
    `itens_cfo_original`. diferenca = round(cfo_pe - cfo_original, 2) (variação de custo).
    """
    linhas = []
    for nome, cfo_original in itens_cfo_original:
        co = float(cfo_original or 0)
        carregado = nome in valores_pe
        cpe = float(valores_pe.get(nome, 0) or 0)
        linhas.append({
            "ambiente": nome,
            "cfo_original": co,
            "cfo_pe": cpe,
            "diferenca": round(cpe - co, 2),
            "pe_carregado": carregado,
        })
    return linhas


def extrair_cfo_pe(arq_nome, xml_conteudo):
    """Extrai o CFO (custo de fábrica) de um XML de PE — Σ dos `order_total` dos itens, exatamente
    como o pool calcula `PoolAmbiente.order_total` (main.py:3927-3931). NÃO é o `total` (venda-bruta).
    Reusa o parser oficial `promob_grupos.ler_xml_str`. Decisão #4."""
    from integracoes.promob_grupos import ler_xml_str
    amb = ler_xml_str(arq_nome, xml_conteudo)
    return round(sum(item.get("order_total", 0.0)
                     for grupo in amb.get("grupos", [])
                     for item in grupo.get("itens", [])), 2)


def reconciliacao_estimada(provisoes, delta_cfo, val_cont, codigo_cfo="2.1.04.06"):
    """Reconciliação ESTIMADA referenciada ao Val_Cont (decisão #9, opção 1) — READ-ONLY, não lança.

    provisoes: [{codigo, nome, provisionado}, ...] do razão/contrato (mod_contabil.reconciliacao).
    delta_cfo: Σ(CFO_pe − CFO_original) dos ambientes com PE carregado (variação de custo de fábrica;
               = −saldo_margem_estimado). Positivo = custo subiu.
    Na Fatia 1 só a rubrica de Custo de Fábrica (`codigo_cfo`) se move no Estimado; as demais seguem o
    contrato (só mudam na liquidação, Fatia 3). Mostra TODAS as rubricas recebidas.

    Retorna {val_cont, linhas:[{codigo,nome,provisionado,estimado,delta}], margem_contratada,
    margem_estimada, delta_total}. margem = Val_Cont − Σ(coluna).
    """
    linhas = []
    for p in provisoes:
        prov = float(p.get("provisionado", 0) or 0)
        d = round(float(delta_cfo or 0), 2) if p.get("codigo") == codigo_cfo else 0.0
        linhas.append({
            "codigo": p.get("codigo"), "nome": p.get("nome"),
            "provisionado": round(prov, 2), "estimado": round(prov + d, 2), "delta": d,
        })
    soma_prov = round(sum(l["provisionado"] for l in linhas), 2)
    soma_est  = round(sum(l["estimado"] for l in linhas), 2)
    vc = round(float(val_cont or 0), 2)
    margem_contratada = round(vc - soma_prov, 2)
    margem_estimada   = round(vc - soma_est, 2)
    pct = lambda m: round(m / vc * 100, 2) if vc else 0.0
    return {
        "val_cont": vc,
        "linhas": linhas,
        "margem_contratada": margem_contratada,
        "margem_estimada":   margem_estimada,
        "margem_contratada_pct": pct(margem_contratada),   # indicador de topo (consolida)
        "margem_estimada_pct":   pct(margem_estimada),
        "delta_pct":             round(pct(margem_estimada) - pct(margem_contratada), 2),
        "delta_total":       round(sum(l["delta"] for l in linhas), 2),
    }


def saldo_margem_estimado(linhas):
    """Saldo GERENCIAL (não contábil) da margem evolutiva — decisão #9.

    Σ(cfo_original − cfo_pe) apenas dos ambientes com PE carregado. Sinal intuitivo:
    positivo = custo caiu = margem estimada melhorou; negativo = custo subiu = margem caiu.
    É estimativa de acompanhamento, NÃO o saldo contábil real (que só muda na liquidação, #3).
    """
    return round(sum((l["cfo_original"] - l["cfo_pe"])
                     for l in linhas if l["pe_carregado"]), 2)
