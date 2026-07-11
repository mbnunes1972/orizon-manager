# -*- coding: utf-8 -*-
"""perfil_store.py — leitura/escrita ORM de PerfilAcesso e seed idempotente por loja."""
import json
from database import PerfilAcesso

# Definição dos 3 perfis padrão (rev3 §2). base == slug para os de sistema.
_OPERACIONAIS = ["captacao", "cadastro", "comercial", "producao",
                 "estoque", "expedicao", "montagem", "assistencias"]
PERFIS_PADRAO = [
    {"slug": "master", "nome": "Master", "base": "master",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha", "admin", "config"]},
    {"slug": "gerencial", "nome": "Gerencial", "base": "gerencial",
     "modulos": _OPERACIONAIS + ["fiscal", "financeiro", "folha"]},
    {"slug": "operador", "nome": "Operador", "base": "operador",
     "modulos": _OPERACIONAIS + ["fiscal"]},
]


def seed_perfis_loja(db, loja_id):
    """Semeia os 3 perfis padrão na loja. Idempotente por (loja_id, slug). Retorna nº criados."""
    if loja_id is None:
        return 0
    existentes = {p.slug for p in db.query(PerfilAcesso).filter_by(loja_id=loja_id).all()}
    criados = 0
    for spec in PERFIS_PADRAO:
        if spec["slug"] in existentes:
            continue
        db.add(PerfilAcesso(loja_id=loja_id, slug=spec["slug"], nome=spec["nome"],
                            base=spec["base"], modulos_json=json.dumps(spec["modulos"]),
                            sistema=1))
        criados += 1
    db.commit()
    return criados


def perfis_da_loja(db, loja_id):
    """Lista os PerfilAcesso de uma loja (ordenados: sistema primeiro, depois por nome)."""
    return (db.query(PerfilAcesso).filter_by(loja_id=loja_id)
            .order_by(PerfilAcesso.sistema.desc(), PerfilAcesso.nome).all())
