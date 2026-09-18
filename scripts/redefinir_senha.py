"""scripts/redefinir_senha.py — Redefinição de senha por linha de comando (Caminho 3,
TAREFA_REDEFINICAO_DE_SENHA.md, 18/09).

Único caminho para contas sem gestor acima e sem telefone cadastrado — `super_admin`, e as
contas que a tela Admin › Usuários cria soltas (ela não tem campo de Função, medido em 17/09).
Nenhum dos outros dois caminhos (redefinição pelo gestor; autoatendimento por WhatsApp) as
alcança. Para elas o caminho certo é linha de comando: é a conta que pode tudo, e o acesso a
ela deve exigir acesso à máquina — de propósito, não por falta de tempo de fazer diferente.

Reusa a primitiva (`auth.trocar_senha` → `Usuario.set_senha` → `_hash_senha`, fonte única de
hash) e o gerador já existente (mesmo de `mod_cadastro.func_sync_acesso`: dígitos do documento
da própria conta, ou token aleatório quando não há — conserto da auditoria de 13/08 contra
senha previsível tipo "orizon123"). Não escreve um segundo gerador.

`trocar_senha` LIMPA `senha_provisoria` — é o comportamento certo para quem está trocando a
PRÓPRIA senha depois de logar. Aqui é o oposto: a conta ainda não trocou nada, então a flag é
religada logo em seguida, para a próxima tela de login exigir a troca.

Uso:
    DATABASE_URL='postgresql+psycopg2://...' python3 scripts/redefinir_senha.py --login sad2026
"""
import argparse
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import get_session, Usuario   # noqa: E402
from auth.auth import trocar_senha          # noqa: E402
import validacao_doc                        # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--login", required=True, help="login (aceita e-mail) da conta")
    args = ap.parse_args()
    login = args.login.strip()

    db = get_session()
    try:
        u = db.query(Usuario).filter_by(login=login).first()
        if u is None:
            print(f"RECUSADO: login {login!r} não existe.", file=sys.stderr)
            sys.exit(1)
        if not u.ativo:
            print(f"RECUSADO: {login!r} está inativa — reative antes de redefinir a senha.",
                  file=sys.stderr)
            sys.exit(1)
        usuario_id = u.id
        # Mesmo gerador de mod_cadastro.func_sync_acesso: dígitos do próprio documento da
        # conta, ou token aleatório quando não há (a maioria das contas deste caminho, como
        # super_admin, não tem CPF cadastrado).
        nova = validacao_doc._digitos(u.cpf) or secrets.token_urlsafe(16)
    finally:
        db.close()

    ok, erro = trocar_senha(usuario_id, nova)
    if not ok:
        print(f"RECUSADO: {erro}", file=sys.stderr)
        sys.exit(1)

    db = get_session()
    try:
        u2 = db.get(Usuario, usuario_id)
        u2.senha_provisoria = 1
        db.commit()
    finally:
        db.close()

    print(f"Senha redefinida para {login!r} (id={usuario_id}). senha_provisoria=1 — "
          "a próxima tela de login vai exigir a troca.")
    print(f"Senha nova (só aparece agora, não fica gravada em lugar nenhum): {nova}")


if __name__ == "__main__":
    main()
