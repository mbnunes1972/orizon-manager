# scripts/snapshot_negociacao.py
"""Gera tests/golden/negociacao_baseline.json: para cada orçamento real, os valores
de HOJE (valor_total/valor_liquido legados) e NOVO (derivados do motor)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    db = get_session()
    out = []
    for o in db.query(Orcamento).order_by(Orcamento.id).all():
        out.append({"id": o.id, "projeto": o.projeto_id, "ordem": o.ordem,
                    "hoje": {"valor_total": o.valor_total, "valor_liquido": o.valor_liquido},
                    "novo": {"vavo": o.vavo, "val_liq": o.val_liq, "markup": o.markup,
                             "val_cont": o.val_cont, "desc_tot_pct": o.desc_tot_pct}})
    db.close()
    path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "negociacao_baseline.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{len(out)} orçamentos -> {path}")

if __name__ == "__main__":
    main()
