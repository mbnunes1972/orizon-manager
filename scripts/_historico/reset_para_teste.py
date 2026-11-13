"""DESTRUTIVO: cancela contratos, volta o ciclo de TODOS os projetos à fase de orçamento e
recalcula valor_total/valor_liquido pelo motor. FAÇA BACKUP do orizon.db antes de rodar."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Orcamento, Contrato, ContratoAssinatura, CicloEtapa

def main():
    db = get_session()
    # 1) cancelar contratos (assinaturas primeiro — FK)
    db.query(ContratoAssinatura).delete()
    n_ct = db.query(Contrato).delete()
    # 2) ciclo: remover etapas posteriores ao orçamento (mantém 1..4)
    n_et = db.query(CicloEtapa).filter(
        ~CicloEtapa.etapa_codigo.in_(["1", "2", "3", "4"])).delete(synchronize_session=False)
    # 3) recalcular todos pelo motor (helper do main)
    import main as _m
    for o in db.query(Orcamento).all():
        try:
            _m._recalcular_orcamento(o, db)
        except Exception as e:
            print("recalc falhou orc", o.id, e)
    db.commit()
    db.close()
    print(f"reset: {n_ct} contratos removidos, {n_et} etapas pós-orçamento limpas, orçamentos recalculados.")

if __name__ == "__main__":
    main()
