# -*- coding: utf-8 -*-
"""perfil_store.py — leitura/escrita ORM de PerfilAcesso e seed idempotente por loja."""
import json
from database import PerfilAcesso
from . import mod_perfis

# Definição dos 3 perfis padrão (rev3 §2). base == slug para os de sistema.
_OPERACIONAIS = ["captacao", "cadastro", "comercial",
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


def criar_perfil(db, loja_id, nome, base, modulos, capacidades=None):
    base = base or "operador"   # 'base' é detalhe interno (fonte do desconto_max, diferido); não aparece na UI
    ok, err = mod_perfis.validar_nome(nome)
    if not ok: return None, err
    ok, err = mod_perfis.validar_base(base)
    if not ok: return None, err
    ok, err = mod_perfis.validar_modulos(modulos)
    if not ok: return None, err
    ok, caps = mod_perfis.validar_capacidades(capacidades)
    if not ok: return None, caps
    existentes = {p.slug for p in db.query(PerfilAcesso).all()}   # slug único GLOBAL
    slug = mod_perfis.gerar_slug(nome, existentes)
    p = PerfilAcesso(loja_id=loja_id, slug=slug, nome=nome.strip(), base=base,
                     modulos_json=json.dumps(list(modulos)),
                     capacidades_json=json.dumps(caps), sistema=0)
    db.add(p); db.commit()
    return p, ""


def editar_perfil(db, loja_id, slug, nome=None, modulos=None, capacidades=None):
    p = db.query(PerfilAcesso).filter_by(loja_id=loja_id, slug=slug).first()
    if not p: return None, "perfil não encontrado"
    if p.sistema: return None, "perfil de sistema não é editável"
    if nome is not None:
        ok, err = mod_perfis.validar_nome(nome)
        if not ok: return None, err
        p.nome = nome.strip()
    if modulos is not None:
        ok, err = mod_perfis.validar_modulos(modulos)
        if not ok: return None, err
        p.modulos_json = json.dumps(list(modulos))
    if capacidades is not None:
        ok, caps = mod_perfis.validar_capacidades(capacidades)
        if not ok: return None, caps
        p.capacidades_json = json.dumps(caps)
    db.commit()
    return p, ""
