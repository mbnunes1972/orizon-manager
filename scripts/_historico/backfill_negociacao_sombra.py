"""Backfill das colunas SOMBRA dos orçamentos com o motor `mod_negociacao` corrigido.

Recalcula e grava SOMENTE as colunas novas (vbvo..prov_imp) de cada orçamento — espelha
o que o handler POST /api/orcamentos/<id>/margens faz (Task 6), mas para todos de uma vez.
O legado (valor_total/valor_liquido/margens) NÃO é tocado. Reversível: tudo recomputável.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento, OrcamentoAmbiente, PoolAmbiente, Projeto
import mod_negociacao


def main():
    db = get_session()
    n = 0
    print("%-24s | %10s %10s | %10s %10s %7s %7s" %
          ("Projeto/Orçamento", "v_tot", "v_liq(HOJE)", "VAVO", "Val_Liq", "Mkup", "DTot%"))
    print("-" * 100)
    try:
        for o in db.query(Orcamento).order_by(Orcamento.projeto_id, Orcamento.ordem).all():
            links = db.query(OrcamentoAmbiente).filter_by(orcamento_id=o.id).all()
            proj = db.query(Projeto).filter_by(nome_safe=o.projeto_id).first()
            params = json.loads(proj.parametros_json) if (proj and proj.parametros_json) else {}
            ambs = []
            for lk in links:
                pa = db.get(PoolAmbiente, lk.pool_ambiente_id)
                if pa:
                    ambs.append({"VBVA": pa.budget_total or 0.0, "CFA": pa.order_total or 0.0,
                                 "desc_amb_pct": lk.desconto_individual_pct or 0.0})
            d0 = mod_negociacao.calcular_orcamento(ambs, params, o.desconto_pct or 0.0)
            cust_fin = max(0.0, (o.valor_total or 0.0) - d0["VAVO"])
            d = mod_negociacao.calcular_orcamento(ambs, params, o.desconto_pct or 0.0, cust_fin=cust_fin)
            o.vbvo, o.cfo, o.vbno, o.vavo = d["VBVO"], d["CFO"], d["VBNO"], d["VAVO"]
            o.cust_ad, o.val_liq = d["Cust_Ad"], d["Val_Liq"]
            o.com_arq_orc, o.pro_fid_orc = d["Com_Arq"], d["Pro_Fid"]
            o.desc_tot_pct, o.markup, o.prov_imp = d["Desc_Tot"], d["Markup"], d["Prov_Imp"]
            o.cust_fin, o.val_cont = d["Cust_Fin"], d["Val_Cont"]
            n += 1
            if links:
                print("%-24s | %10.2f %10.2f | %10.2f %10.2f %7.3f %6.2f%%" %
                      ((o.projeto_id + "/" + o.nome)[:24], o.valor_total or 0, o.valor_liquido or 0,
                       d["VAVO"], d["Val_Liq"], d["Markup"], d["Desc_Tot"] * 100))
        db.commit()
        print("-" * 100)
        print("Backfill concluído: %d orçamentos atualizados (só colunas sombra)." % n)
    finally:
        db.close()


if __name__ == "__main__":
    main()
