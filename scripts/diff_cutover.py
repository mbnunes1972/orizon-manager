"""Compara a baseline legada (tests/golden/cutover_baseline.json) com os valores atuais,
listando os orçamentos cujo valor_total/valor_liquido mudou com o cutover (e de quanto)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento

def main():
    base_path = os.path.join(os.path.dirname(__file__), "..", "tests", "golden", "cutover_baseline.json")
    base = {b["id"]: b for b in json.load(open(base_path, encoding="utf-8"))}
    db = get_session()
    print("%-22s | %12s %12s | %12s %12s" % ("Projeto/Orç", "v_tot OLD", "v_tot NEW", "v_liq OLD", "v_liq NEW"))
    for o in db.query(Orcamento).order_by(Orcamento.id).all():
        b = base.get(o.id)
        if not b:
            continue
        if abs((b["valor_total"] or 0) - (o.valor_total or 0)) > 0.01 or \
           abs((b["valor_liquido"] or 0) - (o.valor_liquido or 0)) > 0.01:
            print("%-22s | %12.2f %12.2f | %12.2f %12.2f" % (
                (o.projeto_id + "/" + o.nome)[:22], b["valor_total"] or 0, o.valor_total or 0,
                b["valor_liquido"] or 0, o.valor_liquido or 0))
    db.close()

if __name__ == "__main__":
    main()
