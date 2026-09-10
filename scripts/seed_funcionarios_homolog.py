# -*- coding: utf-8 -*-
"""Semeia 10 funcionários + 10 usuários de teste numa loja, e configura a remuneração das
funções que eles usam. Feito para HOMOLOGAÇÃO, para exercitar a Folha de Pagamento.

Por que configura FUNÇÃO e não só funcionário: `mod_folha.calcular_folha` lê salário fixo,
benefícios, comissão e comissão fixa da **Função** (`funcoes`), nunca de `Funcionario.
remuneracao_*` (esses campos existem, mas são de planejamento — a folha não os lê). As 13
funções padrão já existem em toda loja (`database.backfill_funcoes_todas_lojas`, roda a cada
boot), mas nascem com salário/benefícios/comissão VAZIOS: sem este passo a folha sai zerada.

Por que cria usuário: `mod_folha._upsert_itens_venda` só gera item de comissão de venda se o
funcionário tiver `usuario_id`. Sem conta, consultor não comissiona.

Guardas:
  - afirma o NOME do banco antes de qualquer escrita (`--banco-esperado`, default
    orizon_homologacao) e recusa qualquer banco com "produc" no nome, sempre;
  - só escreve com `--aplicar`; sem ele, imprime o plano e sai (dry-run);
  - idempotente: funcionário por CPF, usuário por login — o que já existe é pulado;
  - remuneração das funções: só preenche campo NULO/zerado, nunca sobrescreve o que você já
    configurou na tela (use `--forcar-remuneracao` para sobrescrever).

Uso (no servidor de Homologação):
    set -a && . /root/orizon-B.env && set +a
    python3 seed_funcionarios_homolog.py --loja "<nome da loja>"            # plano
    python3 seed_funcionarios_homolog.py --loja "<nome da loja>" --aplicar  # grava

Sem --loja, lista as lojas do banco e sai.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import get_session, Loja, Funcao, Funcionario, Usuario

SENHA_PADRAO = "orizon123"

# ── Remuneração por função ────────────────────────────────────────────────────
# beneficios_json: {"at": {"on","valor"}, "va": ..., "ps": ...}  (AT=transporte, VA=alimentação,
#   PS=plano de saúde) — `_beneficios_total` soma só os que têm "on": true.
# comissao_json (não-consultor): {"por_meta": bool, "base": "liquido"|"fabrica", "pct": float}
#   ou {"por_meta": true, "base": ..., "faixas": [{"venda_ate": X|null, "pct": Y}, ...]}.
#   ATENÇÃO: para função não-consultor a BASE começa em 0 e é digitada na tela da Folha
#   (`mod_folha.editar_base`) — a parte variável só aparece depois que você informa a base.
# Consultor de Vendas NÃO usa comissao_json: `usa_comissao_vendas=1` faz a % vir das faixas de
#   comissão de vendas da LOJA (config_financeira_json), não da função.
REMUNERACAO = {
    "Gerente de Vendas": dict(
        salario_fixo=4500.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 800.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao={"por_meta": True, "base": "liquido", "faixas": [
            {"venda_ate": 150000.0, "pct": 0.5},
            {"venda_ate": 300000.0, "pct": 0.8},
            {"venda_ate": None,     "pct": 1.0}]},
    ),
    "Gerente Administrativo/Financeiro": dict(
        salario_fixo=4200.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 800.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,
    ),
    "Supervisor de Montagem": dict(
        salario_fixo=3200.0, comissao_fixa=300.0,   # fixa mensal, isenta de encargos
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 700.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,
    ),
    "Consultor de Vendas": dict(
        salario_fixo=1800.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 700.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,                               # vem da loja (usa_comissao_vendas=1)
    ),
    "Projetista Executivo": dict(
        salario_fixo=3000.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 700.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,
    ),
    "Medidor": dict(
        salario_fixo=2400.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 700.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,
    ),
    "Montador": dict(
        salario_fixo=2200.0, comissao_fixa=0.0,
        beneficios={"at": {"on": True, "valor": 300.0},
                    "va": {"on": True, "valor": 700.0},
                    "ps": {"on": True, "valor": 400.0}},
        comissao=None,
    ),
}

# ── As 10 pessoas ─────────────────────────────────────────────────────────────
# nivel: master | gerencial | operador (auth/perfis.py). `gerencial` tem aprovar_financeiro=True;
# `operador`, não — os dois gerentes servem de conta "com permissão" no percurso, o resto de
# conta "sem permissão" (itens 6.1 e 8.3.1 do PERCURSO_HOMOLOGACAO.md).
PESSOAS = [
    # (nome,                    função,                              login,      nivel)
    ("Ricardo Salgado Vieira",  "Gerente de Vendas",                 "rvieira",  "gerencial"),
    ("Adriana Peçanha Lopes",   "Gerente Administrativo/Financeiro", "alopes",   "gerencial"),
    ("Wagner Toledo Brito",     "Supervisor de Montagem",            "wbrito",   "operador"),
    ("Camila Rezende Antunes",  "Consultor de Vendas",               "cantunes", "operador"),
    ("Douglas Mariano Pinto",   "Consultor de Vendas",               "dpinto",   "operador"),
    ("Simone Vasques Leal",    "Consultor de Vendas",               "sleal",    "operador"),
    ("Henrique Bastos Furtado", "Projetista Executivo",              "hfurtado", "operador"),
    ("Elias Moreira Campos",    "Medidor",                           "ecampos",  "operador"),
    ("Jonas Ferraz Ribeiro",    "Montador",                          "jribeiro", "operador"),
    ("Anderson Melo Quintela",  "Montador",                          "aquintela", "operador"),
]


def _cpf(seq):
    """CPF sintético com dígitos verificadores válidos, a partir de um número de sequência.
    Base 900.000.000 + seq — faixa alta, sem colisão prática com CPF de teste já usado."""
    base = [int(c) for c in str(900000000 + seq).zfill(9)]
    for _ in range(2):
        peso = len(base) + 1
        soma = sum(d * (peso - i) for i, d in enumerate(base))
        dv = 11 - (soma % 11)
        base.append(0 if dv >= 10 else dv)
    n = "".join(str(d) for d in base)
    return "%s.%s.%s-%s" % (n[0:3], n[3:6], n[6:9], n[9:11])


def _primeiro_nome(nome):
    return nome.split()[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--loja", help="nome da loja (exato). Sem isto, lista as lojas e sai.")
    ap.add_argument("--banco-esperado", default="orizon_homologacao",
                    help="nome do banco que este script aceita (default: orizon_homologacao)")
    ap.add_argument("--senha", default=SENHA_PADRAO, help="senha das 10 contas")
    ap.add_argument("--aplicar", action="store_true", help="grava (sem isto, só mostra o plano)")
    ap.add_argument("--forcar-remuneracao", action="store_true",
                    help="sobrescreve salário/benefícios/comissão já configurados nas funções")
    args = ap.parse_args()

    db = get_session()
    try:
        banco = db.execute(text("SELECT current_database()")).scalar()
        if "produc" in (banco or "").lower():
            sys.exit("RECUSADO: banco %r parece PRODUÇÃO. Este script não roda lá." % banco)
        if banco != args.banco_esperado:
            sys.exit("RECUSADO: conectou em %r, esperado %r. Confira o DATABASE_URL "
                     "(ou passe --banco-esperado se a intenção for outra)." % (banco, args.banco_esperado))
        print("banco: %s" % banco)

        lojas = db.query(Loja).order_by(Loja.id).all()
        if not args.loja:
            print("\nLojas neste banco (rode de novo com --loja \"<nome>\"):")
            for l in lojas:
                print("  id=%-4s %s" % (l.id, l.nome))
            return
        alvo = [l for l in lojas if l.nome == args.loja]
        if len(alvo) != 1:
            sys.exit("RECUSADO: %d loja(s) com nome %r. Nomes: %s"
                     % (len(alvo), args.loja, ", ".join(repr(l.nome) for l in lojas)))
        loja = alvo[0]
        print("loja: id=%s %r\n" % (loja.id, loja.nome))

        # ── 1. remuneração das funções ────────────────────────────────────────
        funcoes = {f.nome: f for f in db.query(Funcao).filter_by(loja_id=loja.id).all()}
        faltando = [n for n in REMUNERACAO if n not in funcoes]
        if faltando:
            sys.exit("RECUSADO: função(ões) ausente(s) nesta loja: %s. Elas deveriam existir "
                     "(backfill_funcoes_todas_lojas roda a cada boot) — suba o serviço antes."
                     % ", ".join(faltando))

        print("── Funções (remuneração) ──")
        for nome, cfg in REMUNERACAO.items():
            f = funcoes[nome]
            mudou = []
            if args.forcar_remuneracao or not f.salario_fixo:
                mudou.append("salario_fixo=%.2f" % cfg["salario_fixo"])
                if args.aplicar:
                    f.salario_fixo = cfg["salario_fixo"]
            if args.forcar_remuneracao or not f.beneficios_json:
                tot = sum(v["valor"] for v in cfg["beneficios"].values() if v["on"])
                mudou.append("beneficios=%.2f" % tot)
                if args.aplicar:
                    f.beneficios_json = json.dumps(cfg["beneficios"])
            if cfg["comissao"] and (args.forcar_remuneracao or not f.comissao_json):
                mudou.append("comissao_json")
                if args.aplicar:
                    f.comissao_json = json.dumps(cfg["comissao"])
            if cfg["comissao_fixa"] and (args.forcar_remuneracao or not f.comissao_fixa):
                mudou.append("comissao_fixa=%.2f" % cfg["comissao_fixa"])
                if args.aplicar:
                    f.comissao_fixa = cfg["comissao_fixa"]
            print("  %-36s %s" % (nome, ", ".join(mudou) if mudou else "já configurada, intacta"))

        # ── 2. funcionários + usuários ────────────────────────────────────────
        print("\n── Funcionários e contas ──")
        criados = pulados = 0
        for i, (nome, nome_funcao, login, nivel) in enumerate(PESSOAS, start=1):
            cpf = _cpf(i)
            ja_f = db.query(Funcionario).filter_by(loja_id=loja.id, cpf=cpf).first()
            ja_u = db.query(Usuario).filter_by(login=login).first()
            if ja_f or ja_u:
                print("  PULADO  %-26s (%s)" % (nome, "funcionário já existe" if ja_f
                                                 else "login %r já existe" % login))
                pulados += 1
                continue

            email = "%s@homolog.orizonone.com.br" % login
            func = funcoes[nome_funcao]
            f = Funcionario(
                loja_id=loja.id, nome=nome, cpf=cpf, email=email,
                telefone="(12) 9%04d-%04d" % (1000 + i, 4000 + i),
                cargo=nome_funcao, funcao_id=func.id, status="ativo",
                remuneracao_tipo=("fixa_variavel" if nome_funcao in
                                  ("Consultor de Vendas", "Gerente de Vendas") else "fixa"),
                remuneracao_fixa=REMUNERACAO[nome_funcao]["salario_fixo"],
                cep="12245-000", logradouro="Rua de Teste", numero=str(100 + i),
                bairro="Centro", cidade="São José dos Campos", uf="SP",
                banco_nome="Banco de Teste", banco_codigo="001",
                agencia="0001", conta="%06d-%d" % (10000 + i, i % 10),
                pix=email,
            )
            if args.aplicar:
                db.add(f)
                db.flush()      # precisa do id pra amarrar o usuário

            u = Usuario(nome=nome, login=login, email=email, cpf=cpf, nivel=nivel,
                        loja_id=loja.id, rede_id=None, ativo=1, senha_provisoria=0,
                        funcionario_id=(f.id if args.aplicar else None),
                        funcao_id=func.id)
            u.set_senha(args.senha)
            if args.aplicar:
                db.add(u)
                db.flush()
                f.usuario_id = u.id     # 1:1 nos dois lados (ver "dívida de Onda 2" no CLAUDE.md)
            print("  criado  %-26s %-36s login=%-10s nivel=%s"
                  % (nome, nome_funcao, login, nivel))
            criados += 1

        # ── 3. o que ainda falta pra folha não sair zerada ────────────────────
        print("\n── Conferência ──")
        cfg_loja = getattr(loja, "config_financeira_json", None)
        tem_comissao_vendas = False
        try:
            tem_comissao_vendas = bool((json.loads(cfg_loja) if cfg_loja else {}).get("comissao_vendas"))
        except (ValueError, TypeError):
            pass
        print("  comissão de vendas da LOJA configurada: %s" % ("sim" if tem_comissao_vendas else
              "NÃO — os 3 consultores vão sair com parte variável 0,00 até você "
              "configurar as faixas em Configurações → Financeiro"))
        print("  base da comissão das funções não-consultor começa em 0,00 por desenho — "
              "digite na tela da Folha (mod_folha.editar_base) para ver a parte variável.")

        if args.aplicar:
            db.commit()
            print("\nGRAVADO: %d criado(s), %d pulado(s)." % (criados, pulados))
            print("Senha das contas novas: %r (homologação — trocar antes de qualquer uso real)."
                  % args.senha)
        else:
            db.rollback()
            print("\nPLANO apenas (%d seriam criados, %d pulados). Rode de novo com --aplicar."
                  % (criados, pulados))
    finally:
        db.close()


if __name__ == "__main__":
    main()
