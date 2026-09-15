"""Relatório (SÓ LEITURA — não escreve nada) das etapas 17 (Montagem) já concluídas cuja
comissão nunca foi preparada — achado do MAPA_MODULOS.md § 2.8 (14/09/2026): antes do conserto
em main.py, a rota PATCH genérica /ciclo/<codigo> concluía a etapa 17 sem nunca chamar
mod_comissao.preparar_comissao_etapa.

Uso: aponte DATABASE_URL para o banco que quer auditar (local, homologação ou Produção) e rode:
    python3 scripts/relatorio_comissao_montagem_ausente.py

NÃO faz backfill automático — decisão explícita do Marcelo (14/09/2026): mexer em comissão
passada sem revisão caso a caso arrisca duplicar, comissionar projeto cancelado, ou comissionar
quem já foi pago por fora. Este script só lista; quem decide o que fazer com cada linha é humano.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, CicloEtapa, ComissaoFolha, Funcionario, Projeto, Loja
import mod_comissao


def _executores_da_etapa(db, etapa):
    """Mesma lógica de mod_comissao.preparar_comissao_etapa: Mapa de Atribuições primeiro,
    responsavel_funcionario_id da etapa como fallback se o Mapa estiver vazio."""
    execs = mod_comissao._executores_do_papel(db, etapa.projeto_nome, "montagem")
    if not execs and etapa.responsavel_funcionario_id:
        execs = [etapa.responsavel_funcionario_id]
    return execs


def main():
    db = get_session()
    try:
        etapas = (db.query(CicloEtapa)
                    .filter_by(etapa_codigo="17", status="concluido")
                    .order_by(CicloEtapa.concluido_em.asc().nullsfirst())
                    .all())
        linhas = []
        for et in etapas:
            execs = _executores_da_etapa(db, et)
            if not execs:
                # sem Mapa e sem responsável definido — nada pra comissionar, não é achado.
                continue
            for func_id in execs:
                ref = "%s:17:%d" % (et.projeto_nome, func_id)
                ja_existe = db.query(ComissaoFolha).filter_by(ref_etapa=ref).first()
                if ja_existe:
                    continue
                proj = db.query(Projeto).filter_by(nome_safe=et.projeto_nome).first()
                loja = db.get(Loja, proj.loja_id) if proj else None
                func = db.get(Funcionario, func_id)
                linhas.append({
                    "projeto": et.projeto_nome,
                    "loja": (loja.nome if loja else "?"),
                    "montador": (func.nome if func else ("funcionario_id=%d (removido?)" % func_id)),
                    "concluido_em": (et.concluido_em.strftime("%Y-%m-%d %H:%M")
                                     if et.concluido_em else "?"),
                })
        if not linhas:
            print("Nenhuma etapa 17 concluída ficou sem comissão preparada — nada a decidir.")
            return
        print("%-28s | %-20s | %-24s | %s" % ("Projeto", "Loja", "Montador", "Concluído em"))
        print("-" * 100)
        for l in linhas:
            print("%-28s | %-20s | %-24s | %s" %
                  (l["projeto"][:28], l["loja"][:20], l["montador"][:24], l["concluido_em"]))
        print("-" * 100)
        print("%d comissão(ões) de Montagem faltando — nenhuma escrita foi feita. "
              "Decisão caso a caso, não automática." % len(linhas))
    finally:
        db.close()


if __name__ == "__main__":
    main()
