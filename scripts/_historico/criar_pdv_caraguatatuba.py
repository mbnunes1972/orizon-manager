# -*- coding: utf-8 -*-
"""Fatia 4 da frente PDV (spec _geral/2026-07-22-ponto-de-venda-design.md):
cria o Ponto de Venda REAL de Caraguatatuba vinculado à Inspirium (São José dos Campos).

Uso (na máquina que enxerga o banco alvo, com DATABASE_URL no ambiente/.env):
    python3 scripts/criar_pdv_caraguatatuba.py            # usa a Inspirium (código INS)
    python3 scripts/criar_pdv_caraguatatuba.py --mae ABC  # outra mãe, pelo código

IDEMPOTENTE: se já existe loja com o código CAR, não faz nada.
NÃO migra projetos nem lançamentos históricos — decisão da spec: o histórico de
Caraguá fica na mãe (razão já constituído, refs amarradas ao owner); apenas as
vendas NOVAS nascem no PDV.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CODIGO_PDV = "CAR"
NOME_PDV = "Inspirium — Ponto de Venda Caraguatatuba"


def main():
    ap = argparse.ArgumentParser(description="Cria o PDV Caraguatatuba (idempotente).")
    ap.add_argument("--mae", default="INS", help="código da loja-mãe (default: INS/Inspirium)")
    args = ap.parse_args()

    import database
    from database import get_session, init_db, Loja
    init_db()
    db = get_session()
    try:
        ja = db.query(Loja).filter(Loja.codigo == CODIGO_PDV).first()
        if ja is not None:
            print("Nada a fazer: loja com código %s já existe (id=%s, %s)."
                  % (CODIGO_PDV, ja.id, ja.nome))
            return 0
        mae = db.query(Loja).filter(Loja.codigo == args.mae.upper()).first()
        if mae is None:
            print("ERRO: loja-mãe com código %r não encontrada." % args.mae, file=sys.stderr)
            return 1
        if mae.loja_mae_id:
            print("ERRO: a loja %s já é um PDV — PDV não tem PDVs." % mae.nome, file=sys.stderr)
            return 1
        pdv = Loja(
            nome=NOME_PDV,
            codigo=CODIGO_PDV,
            tipo="ponto_venda",
            loja_mae_id=mae.id,
            rede_id=mae.rede_id,                                  # herdado, não editável
            config_financeira_json=mae.config_financeira_json,    # seed = cópia da mãe
            pct_mercadoria=mae.pct_mercadoria,
            pct_servico=mae.pct_servico,
            cidade="Caraguatatuba", estado="SP",
            ativo=1,
        )
        db.add(pdv)
        db.flush()
        from auth import perfil_store, perfis
        perfil_store.seed_perfis_loja(db, pdv.id)                 # master/gerencial/operador
        db.commit()
        perfis.recarregar()
        print("PDV criado: id=%s codigo=%s mãe=%s (id=%s, rede=%s)."
              % (pdv.id, pdv.codigo, mae.nome, mae.id, mae.rede_id))
        print("Sem migração de histórico (projetos/lançamentos ficam na mãe); "
              "vendas novas nascem no PDV. Endereço/telefone/testemunhas/equipe: "
              "completar no painel Admin (super_admin), seção Pontos de Venda.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
