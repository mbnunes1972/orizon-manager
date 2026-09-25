# -*- coding: utf-8 -*-
"""Usuarios das lojas-piloto em HOMOLOGACAO (25/09/2026, pedido do Marcelo).

Cria/atualiza os 12 usuarios das 5 lojas do grupo, cria o Funcionario com Funcao SAC de cada
uma (o que o roteamento le -- usuario chamado "SAC" NAO basta, medido em 24/09), e limpa o
resto: apaga quem nao tem referencia, desativa quem tem. Preserva sad2026 e a loja 15.

Simulacao por padrao. Grava so com --aplicar. Rodar no servidor, com /root/orizon-B.env
carregado. NAO e parte da aplicacao -- e operacao, versionado so para nao ser recolado a mao."""
import sys, os

RAIZ = os.environ.get("ORIZON_RAIZ", "/root/orizon-homolog")
sys.path.insert(0, RAIZ); os.chdir(RAIZ)

import database as D
from database import Usuario, Funcao, Funcionario
from sqlalchemy.exc import IntegrityError

APLICAR = "--aplicar" in sys.argv
SENHA   = "orizon234"
MANTER_LOJAS  = {15}
MANTER_LOGINS = {"sad2026"}

DESEJADOS = [
 ("mbn1972@gmail.com",                           "Marcelo Buonocore Nunes",     "super_admin", None, False),
 ("felipe@dalmobilesjc.com.br",                  "Felipe",                      "master",   1, False),
 ("jaime@dalmobilesjc.com.br",                   "Jaime",                       "master",   1, False),
 ("sac@dalmobilesjc.com.br",                     "SAC Dalmobile SJC",           "operador", 1, True),
 ("carlar.dalmobile@gmail.com",                  "Carla Reis",                  "master",   3, False),
 ("sacrecreio.dalmobile@gmail.com",              "SAC Dalmobile Recreio",       "operador", 3, True),
 ("regiane@dalmobilecaraguatatuba.com.br",       "Regiane",                     "master",   4, False),
 ("sac@dalmobilecaraguatatuba.com.br",           "SAC Dalmobile Caraguatatuba", "operador", 4, True),
 ("eduardoluz@dalmobilesalinasfortaleza.com.br", "Eduardo Luz",                 "master",  16, False),
 ("sac@dalmobilesalinasfortaleza.com.br",        "SAC Dalmobile Salinas",       "operador",16, True),
 ("marceloroseira.dalmobile@gmail.com",          "Marcelo Roseira",             "master",  17, False),
 ("sac@dalmobilecasashopping.com",               "SAC Dalmobile Casa Shopping", "operador",17, True),
]
LOGINS_DESEJADOS = {d[0] for d in DESEJADOS}

db = D.get_session()
criados, atualizados, apagados, desativados, sacs = [], [], [], [], []

for login, nome, nivel, loja_id, eh_sac in DESEJADOS:
    u = db.query(Usuario).filter_by(login=login).first()
    novo = u is None
    if novo:
        u = Usuario(login=login); db.add(u)
    u.nome, u.nivel, u.loja_id, u.ativo = nome, nivel, loja_id, 1
    u.rede_id = None
    u.set_senha(SENHA); u.senha_provisoria = 1
    db.flush()
    (criados if novo else atualizados).append(login)
    if eh_sac:
        f = db.query(Funcao).filter_by(loja_id=loja_id, nome="SAC").first()
        if f is None:
            f = Funcao(loja_id=loja_id, nome="SAC", status="ativo"); db.add(f); db.flush()
        fc = db.query(Funcionario).filter_by(loja_id=loja_id, funcao_id=f.id).first()
        if fc is None:
            fc = Funcionario(loja_id=loja_id, nome="NOME_SAC", funcao_id=f.id); db.add(fc)
        fc.usuario_id, fc.status, fc.email, fc.nome = u.id, "ativo", login, "NOME_SAC"
        db.flush()
        sacs.append("loja %s -> %s" % (loja_id, login))

for u in db.query(Usuario).all():
    if u.login in LOGINS_DESEJADOS or u.login in MANTER_LOGINS or u.loja_id in MANTER_LOJAS:
        continue
    sp = db.begin_nested()
    try:
        db.delete(u); db.flush(); sp.commit(); apagados.append(u.login)
    except IntegrityError:
        sp.rollback()
        u2 = db.query(Usuario).filter_by(login=u.login).first()
        u2.ativo = 0; db.flush(); desativados.append(u2.login)

print("CRIADOS     (%d): %s" % (len(criados), ", ".join(criados)))
print("ATUALIZADOS (%d): %s" % (len(atualizados), ", ".join(atualizados)))
print("APAGADOS    (%d): %s" % (len(apagados), ", ".join(apagados)))
print("DESATIVADOS (%d): %s" % (len(desativados), ", ".join(desativados)))
print("FUNCAO SAC  (%d): %s" % (len(sacs), " | ".join(sacs)))
if APLICAR:
    db.commit(); print("\n>>> APLICADO")
else:
    db.rollback(); print("\n>>> SIMULACAO -- nada gravado. Rode de novo com --aplicar")
db.close()
