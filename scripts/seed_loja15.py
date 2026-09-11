#!/usr/bin/env python3
"""Semeia os 10 papéis + 1 conta master na LOJA TESTE (loja 15) do banco de homologação.

Complemento de `seed_funcionarios_homolog.py`: aquele semeou a Inspirium (loja 1) e checa
`login` globalmente, então não serve para uma segunda loja — os logins colidiriam. Aqui os
logins levam o sufixo `15` e os CPFs saem da faixa 910.xxx (o outro usa 900.xxx).

Idempotente por login e por CPF-dentro-da-loja: rodar de novo não duplica nada.

    PYTHONPATH=/root/orizon-homolog python3 seed_loja15.py             # plano
    PYTHONPATH=/root/orizon-homolog python3 seed_loja15.py --aplicar   # grava
"""
import sys
from sqlalchemy import text
from database import Session, Loja, Funcao, Funcionario, Usuario

LOJA_ID  = 15
SENHA    = "orizon123"
BANCO_OK = "orizon_homologacao"
VARIAVEL = ("Consultor de Vendas", "Gerente de Vendas")

# (nome, função, login, nível, seq do CPF)
PESSOAS = [
    ("Marta Ourives Bastos",    "Gerente Administrativo/Financeiro", "admtes",      "master",     1),
    ("Ricardo Salgado Vieira",  "Gerente de Vendas",                 "rvieira15",   "gerencial",  2),
    ("Camila Rezende Antunes",  "Consultor de Vendas",               "cantunes15",  "operador",   3),
    ("Adriana Pecanha Lopes",   "Gerente Administrativo/Financeiro", "alopes15",    "gerencial",  4),
    ("Wagner Toledo Brito",     "Supervisor de Montagem",            "wbrito15",    "operador",   5),
    ("Douglas Mariano Pinto",   "Consultor de Vendas",               "dpinto15",    "operador",   6),
    ("Simone Vasques Leal",     "Consultor de Vendas",               "sleal15",     "operador",   7),
    ("Henrique Bastos Furtado", "Projetista Executivo",              "hfurtado15",  "operador",   8),
    ("Elias Moreira Campos",    "Medidor",                           "ecampos15",   "operador",   9),
    ("Jonas Ferraz Ribeiro",    "Montador",                          "jribeiro15",  "operador",  10),
    ("Anderson Melo Quintela",  "Montador",                          "aquintela15", "operador",  11),
]


def cpf(seq):
    """CPF sintético com dígitos verificadores válidos. Base 910.000.000 + seq."""
    base = [int(c) for c in str(910000000 + seq).zfill(9)]
    for _ in range(2):
        peso = len(base) + 1
        soma = sum(d * (peso - i) for i, d in enumerate(base))
        dv = 11 - (soma % 11)
        base.append(0 if dv >= 10 else dv)
    n = "".join(str(d) for d in base)
    return "%s.%s.%s-%s" % (n[0:3], n[3:6], n[6:9], n[9:11])


def main():
    aplicar = "--aplicar" in sys.argv
    db = Session()
    try:
        banco = db.execute(text("SELECT current_database()")).scalar()
        if "produc" in (banco or "").lower():
            sys.exit("RECUSADO: banco %r parece PRODUCAO." % banco)
        if banco != BANCO_OK:
            sys.exit("RECUSADO: conectou em %r, esperado %r." % (banco, BANCO_OK))

        loja = db.query(Loja).filter_by(id=LOJA_ID).first()
        if not loja:
            sys.exit("RECUSADO: loja %s nao existe neste banco." % LOJA_ID)
        print("banco: %s\nloja:  id=%s %r\n" % (banco, loja.id, loja.nome))

        funcoes = {f.nome: f for f in db.query(Funcao).filter_by(loja_id=LOJA_ID).all()}
        faltando = sorted({p[1] for p in PESSOAS} - set(funcoes))
        if faltando:
            sys.exit("RECUSADO: funcao(oes) ausente(s) na loja %s: %s. Elas deveriam existir "
                     "(backfill_funcoes_todas_lojas roda a cada boot)." % (LOJA_ID, ", ".join(faltando)))

        criados = pulados = 0
        for nome, nome_funcao, login, nivel, seq in PESSOAS:
            doc = cpf(seq)
            if db.query(Usuario).filter_by(login=login).first():
                print("  PULADO  %-12s (login ja existe)" % login); pulados += 1; continue
            if db.query(Funcionario).filter_by(loja_id=LOJA_ID, cpf=doc).first():
                print("  PULADO  %-12s (cpf ja existe nesta loja)" % login); pulados += 1; continue

            func  = funcoes[nome_funcao]
            email = "%s@homolog.orizonone.com.br" % login
            f = Funcionario(
                loja_id=LOJA_ID, nome=nome, cpf=doc, email=email,
                telefone="(12) 91500-50%02d" % seq,
                cargo=nome_funcao, funcao_id=func.id, status="ativo",
                remuneracao_tipo=("fixa_variavel" if nome_funcao in VARIAVEL else "fixa"),
                remuneracao_fixa=(func.salario_fixo or 0.0),
                cep="12245-000", logradouro="Rua de Teste", numero=str(200 + seq),
                bairro="Centro", cidade="Sao Jose dos Campos", uf="SP",
                banco_nome="Banco de Teste", banco_codigo="001",
                agencia="0001", conta="%06d-%d" % (20000 + seq, seq % 10), pix=email,
            )
            if aplicar:
                db.add(f); db.flush()      # precisa do id pra amarrar o usuario
            u = Usuario(nome=nome, login=login, email=email, cpf=doc, nivel=nivel,
                        loja_id=LOJA_ID, rede_id=None, ativo=1, senha_provisoria=0,
                        funcionario_id=(f.id if aplicar else None), funcao_id=func.id)
            u.set_senha(SENHA)
            if aplicar:
                db.add(u); db.flush(); f.usuario_id = u.id   # 1:1 nos dois lados
            print("  criado  %-12s %-10s %-36s cpf=%s" % (login, nivel, nome_funcao, doc))
            criados += 1

        print("\ncriados=%d  pulados=%d" % (criados, pulados))
        if aplicar:
            db.commit(); print("GRAVADO.")
        else:
            db.rollback(); print("PLANO apenas. Rode de novo com --aplicar.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
