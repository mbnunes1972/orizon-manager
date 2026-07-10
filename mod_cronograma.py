"""mod_cronograma.py — Cronograma do Ciclo (Modulos_Orizon_v11).

Na assinatura do contrato (D0 = ambas as partes assinaram — mesmo gatilho que constitui as
Provisões, Financeiro §6.4), constitui a data prevista de conclusão de cada etapa a partir do
Cronograma de Projeto Padrão (Config): data_prevista_conclusao = D0 + prazo_dias.

data_conclusao (= CicloEtapa.concluido_em) nasce vazia — preenche quando a etapa é de fato
concluída. Idempotente por (projeto, etapa): reexecutar recomputa a data prevista a partir de D0.
"""
from datetime import timedelta

from database import CicloEtapa


def cronograma_padrao(cfg):
    """Normaliza a lista de fases do Cronograma Padrão da config: [{codigo, prazo_dias}]."""
    itens = (cfg or {}).get("cronograma_padrao") or []
    out = []
    for it in itens:
        cod = str((it or {}).get("codigo") or "").strip()
        if not cod:
            continue
        try:
            prazo = int((it or {}).get("prazo_dias") or 0)
        except (TypeError, ValueError):
            prazo = 0
        out.append({"codigo": cod, "prazo_dias": max(0, prazo)})
    return out


def gerar_cronograma_projeto(db, projeto_nome, cfg, d0):
    """Para cada fase do Cronograma Padrão, cria/atualiza a etapa do projeto com
    data_prevista_conclusao = d0 + prazo_dias. Não toca data de conclusão. Idempotente.
    Retorna a lista de CicloEtapa afetadas."""
    afetadas = []
    for fase in cronograma_padrao(cfg):
        prevista = d0 + timedelta(days=fase["prazo_dias"])
        reg = (db.query(CicloEtapa)
               .filter_by(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"]).first())
        if reg is None:
            reg = CicloEtapa(projeto_nome=projeto_nome, etapa_codigo=fase["codigo"])
            db.add(reg)
        reg.data_prevista_conclusao = prevista
        afetadas.append(reg)
    db.flush()
    return afetadas
