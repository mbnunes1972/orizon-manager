"""Fotografa valor_total/valor_liquido LEGADOS de todos os orçamentos antes do cutover."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    db = get_session()
    out = [{"id": o.id, "projeto": o.projeto_id, "ordem": o.ordem,
            "valor_total": o.valor_total, "valor_liquido": o.valor_liquido}
           for o in db.query(Orcamento).order_by(Orcamento.id).all()]
    db.close()
    path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "cutover_baseline.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{len(out)} orçamentos -> {path}")

if __name__ == "__main__":
    main()
