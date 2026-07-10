"""
seed.py — Cria os usuários iniciais no banco de dados
Orizon Manager | Dalmóbile

Uso: python3 seed.py
"""

import database
from database import init_db, get_session, Usuario, Funcao, loja_seed_id, FUNCOES_PADRAO

USUARIOS = [
    {"nome": "Pedro da Mota",        "login": "pdm2026", "senha": "teste123", "nivel": "diretor"},
    {"nome": "Luiz da Silva",        "login": "lds2026", "senha": "teste234", "nivel": "gerente_vendas"},
    {"nome": "Marcia dos Santos",    "login": "mds2026", "senha": "teste345", "nivel": "consultor"},
    {"nome": "Gabriela Adm/Fin",     "login": "gaf2026", "senha": "teste456", "nivel": "gerente_adm_fin"},
    {"nome": "Alex Logistica",       "login": "alg2026", "senha": "teste567", "nivel": "assistente_logistico"},
    {"nome": "Carla Conferente",     "login": "ccf2026", "senha": "teste678", "nivel": "conferente"},
    {"nome": "Sergio Montagem",      "login": "smt2026", "senha": "teste789", "nivel": "supervisor_montagem"},
    {"nome": "Aline Administrativo", "login": "aad2026", "senha": "teste890", "nivel": "assistente_administrativo"},
    {"nome": "Paulo Projetista",     "login": "ppe2026", "senha": "teste901", "nivel": "projetista_executivo"},
    {"nome": "Marcos Medidor",       "login": "med2026", "senha": "teste012", "nivel": "medidor"},
]


def criar_usuarios_seed(db, usuarios, loja_id):
    """Cria os usuários que ainda não existem, vinculados à loja `loja_id`.
    Idempotente: pula logins já existentes. Retorna o nº de usuários criados."""
    criados = 0
    for dados in usuarios:
        if db.query(Usuario).filter_by(login=dados["login"]).first():
            print(f"  [ja existe] {dados['login']} ({dados['nivel']})")
            continue
        u = Usuario(nome=dados["nome"], login=dados["login"],
                    nivel=dados["nivel"], loja_id=loja_id)
        u.set_senha(dados["senha"])
        db.add(u)
        criados += 1
        print(f"  [criado]    {dados['login']} ({dados['nivel']}) - {dados['nome']}")
    db.commit()
    return criados


def criar_funcoes_seed(db, loja_id):
    """Semeia a Tabela de Funções da loja com os cargos padrão (Regras_Funcoes_Perfis §0b).
    Idempotente por (loja_id, nome): pula os que já existem. Retorna o nº de funções criadas."""
    if loja_id is None:
        return 0
    existentes = {f.nome for f in db.query(Funcao).filter_by(loja_id=loja_id).all()}
    criadas = 0
    for nome in FUNCOES_PADRAO:
        if nome in existentes:
            continue
        db.add(Funcao(loja_id=loja_id, nome=nome, status="ativo"))
        criadas += 1
    db.commit()
    return criadas


def seed():
    init_db()                         # cria schema + tenancy_v1 (loja seed) + tenancy_v2 (super_admin)
    db = get_session()
    try:
        if not db.query(Usuario).filter_by(nivel="super_admin").first():
            sa = Usuario(nome=database._SEED_SA_NOME, login=database._SEED_SA_LOGIN,
                         nivel="super_admin", loja_id=None, rede_id=None)
            sa.set_senha(database._SEED_SA_SENHA)
            db.add(sa); db.commit()
            print(f"  [criado]    {database._SEED_SA_LOGIN} (super_admin)")

        loja_id = loja_seed_id(db)    # a loja seed já existe pela migração
        if loja_id is None:
            print("  [aviso] loja seed nao encontrada; usuarios serao criados sem loja_id.")
        criados = criar_usuarios_seed(db, USUARIOS, loja_id)
        existentes = len(USUARIOS) - criados
        funcoes = criar_funcoes_seed(db, loja_id)
        print(f"\n  OK: {criados} usuario(s) criado(s), {existentes} ja existia(m); "
              f"{funcoes} funcao(oes) semeada(s); loja seed id={loja_id}.")
    finally:
        db.close()


if __name__ == "__main__":
    print("\nCriando usuarios iniciais...\n")
    seed()
