"""Lógica pura de parcelas do desmembramento de PE (Fatia 2).

Segue o padrão do projeto (cálculo puro em `mod_*.py`, sem tocar banco/HTTP — a
persistência e os endpoints ficam no `main.py`). Espelha as funções puras de
`mod_pe_comparacao.py` (Fatia 1).

Decisão #5 (spec 2026-07-13-desmembramento-pe-parcial-design.md): ao criar as
parcelas, cada uma congela `fracao_val_cont` e `val_cont_congelado`; a ÚLTIMA
parcela (maior ordem) absorve o resto do arredondamento, de forma que
`Σ val_cont_congelado == round(Val_Cont, 2)` seja EXATO ao centavo — base do
faturamento e do matching de NF-e parcial (Fatia 3).
"""


LIMITE_AF1_DEFAULT = 0.01   # 1% — Limite de Aprovação Financeira 1 (#10)
LIMITE_AF2_DEFAULT = 0.02   # 2% — Limite de Aprovação Financeira 2 (#10)


def exige_aprovacao_diretor(valor_anterior, valor_novo, limite_frac):
    """#10 — gate da Aprovação Financeira: um AUMENTO de custo de uma versão de
    provisão para a próxima (venda→rev1 na AF1, rev1→rev2 na AF2) acima do limite
    configurado exige step-up do Diretor (mecanismo de step-up já existente).

    `limite_frac` é fração (0.01 = 1%). Retorna True quando o aumento relativo
    passa do limite: (valor_novo - valor_anterior) / valor_anterior > limite_frac.
    Reduções ou variações dentro do limite NÃO exigem Diretor. Se a base anterior
    é <= 0 e houve aumento, exige Diretor (aumento não mensurável em %).
    """
    va = float(valor_anterior or 0.0)
    vn = float(valor_novo or 0.0)
    if vn <= va:
        return False          # redução ou igual — nunca exige
    if va <= 0:
        return True           # partiu de zero e subiu — acima de qualquer limite %
    return (vn - va) / va > float(limite_frac)


def congelar_parcelas(parcelas_ambientes, val_cont):
    """Congela fração e valor de cada parcela (#5).

    Args:
        parcelas_ambientes: lista ORDENADA (ordem 1..N) de parcelas; cada parcela
            é a lista dos valores de contrato (valor de venda rateado p/ contrato,
            NÃO o CFO — #4/#5) dos ambientes daquela parcela.
            Ex.: [[600.0, 400.0], [2000.0]] → parcela 1 tem 2 ambientes, parcela 2 tem 1.
        val_cont: Val_Cont total do projeto (float).

    Returns:
        Lista de dicts {ordem, fracao_val_cont, val_cont_congelado}, uma por
        parcela, na mesma ordem da entrada. A última leva o resto (#5).
        Se val_cont <= 0, retorna frações/valores zerados (sem divisão por zero).
    """
    n = len(parcelas_ambientes)
    if n == 0:
        return []

    vc = round(float(val_cont or 0.0), 2)
    somas = [round(sum(float(v or 0.0) for v in amb), 2) for amb in parcelas_ambientes]

    resultado = []
    if vc <= 0:
        for i in range(n):
            resultado.append({"ordem": i + 1, "fracao_val_cont": 0.0, "val_cont_congelado": 0.0})
        return resultado

    acumulado = 0.0
    for i in range(n):
        fracao = somas[i] / vc
        if i < n - 1:
            valor = round(fracao * vc, 2)
        else:
            # última parcela absorve o resto → soma fecha exata ao centavo (#5)
            valor = round(vc - acumulado, 2)
        acumulado = round(acumulado + valor, 2)
        resultado.append({
            "ordem": i + 1,
            "fracao_val_cont": fracao,
            "val_cont_congelado": valor,
        })
    return resultado
