# -*- coding: utf-8 -*-
"""Limpar a operação de uma loja — docs/db/TAREFA_LIMPAR_INSPIRIUM.md, Passo 2.

Apaga TODA a operação de uma loja (projetos, orçamentos, contratos, ciclo, conversas, leads,
triagem, financeiro/contábil de movimento, folha, clientes) e DESATIVA (nunca apaga) todos os
usuários e funcionários dela, exceto o login indicado como master que fica. A `Loja` e a
configuração dela (funções, perfil de acesso, segmentos, config do OrizonBot, emitente, modelos
de documento, plano de contas/centro de custo — GABARITO, não movimento) nunca são tocados.

CONFIGURAÇÃO fica, DADO sai — mesmo princípio de mod_implantacao_loja.py, aplicado ao inverso
(limpar em vez de clonar). `conta`/`centro_custo` são estrutura (mesma decisão de
docs/db/limpar_base.sql: apagar o gabarito da loja deixaria o plano de contas vazio); só o
MOVIMENTO (`lancamento`) é dado e sai.

Projeto não tem tabela própria — `projetos_meta.nome_safe` é a chave natural que aparece como
texto puro (`projeto_nome`/`projeto_id`) em ciclo_etapas, ciclo_documentos, medicoes,
pool_ambientes, etc. (sem FK declarada — é código de negócio, não modelagem polimórfica). A
delimitação por loja destas tabelas é sempre "projeto_nome IN (projetos desta loja)".

Guardas (mesmo padrão de clonar_loja.py):
  - afirma o NOME do banco antes de qualquer escrita (`--banco-esperado`, default
    orizon_homologacao) e recusa qualquer banco com "produc" no nome, sempre;
  - só apaga com `--aplicar`; sem ele, imprime a tabela do que apagaria, por tabela, com
    contagem — essa tabela vai para aprovação antes da execução real;
  - confirma que o login master existe, pertence à loja alvo e continua/fica ativo — recusa se
    não achar;
  - tudo numa transação: ou a limpeza inteira acontece, ou nada acontece (exceção → rollback,
    nunca commit parcial);
  - erro de chave estrangeira não é contornado com CASCADE — a ordem abaixo foi construída
    das folhas para a raiz a partir do grafo real de FKs do schema (medido 18/09). Um erro aqui
    é sinal de schema mudou desde a medição: pare e reporte, não improvise.

O único ciclo genuíno do schema que entra no caminho (`orcamentos.parcela_id` <->
`parcela_projeto.orcamento_id`, documentado em CLAUDE.md — "3 ciclos de FK bidirecional") é
quebrado explicitamente (UPDATE ... SET parcela_id = NULL) antes de apagar os dois lados —
não é CASCADE improvisado, é a mesma técnica que a própria baseline do Alembo usa
(`use_alter=True`) para poder ordenar a criação das tabelas.

Uso:
  # 1. Sempre primeiro, sem --aplicar: mostra a tabela do que apagaria, por tabela, com contagem.
  python3 scripts/limpar_loja.py --loja 1 --master-login gaf2026

  # 2. Só depois de aprovado:
  python3 scripts/limpar_loja.py --loja 1 --master-login gaf2026 --aplicar
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import Loja, Usuario, get_session


def _conferir_banco(db, banco_esperado):
    banco = db.execute(text("SELECT current_database()")).scalar()
    if "produc" in (banco or "").lower():
        sys.exit("RECUSADO: banco %r parece PRODUÇÃO. Este script não roda lá." % banco)
    if banco != banco_esperado:
        sys.exit("RECUSADO: conectou em %r, esperado %r. Confira o DATABASE_URL (ou passe "
                 "--banco-esperado se a intenção for outra)." % (banco, banco_esperado))
    print("banco: %s" % banco)
    return banco


# Cada passo: (tabela, WHERE usando :loja / :master_login, além_do_documento).
# Ordem: das folhas para a raiz, medida contra o grafo de FK real do schema em 18/09/2026
# (docs/db/TAREFA_LIMPAR_INSPIRIUM.md). "projetos desta loja" = SELECT nome_safe FROM
# projetos_meta WHERE loja_id=:loja — ver docstring do módulo.
_PROJETOS_DA_LOJA = "(SELECT nome_safe FROM projetos_meta WHERE loja_id=:loja)"
_CONVERSAS_DA_LOJA = "(SELECT id FROM conversas WHERE loja_id=:loja)"
_MENSAGENS_DA_LOJA = "(SELECT id FROM conversa_mensagens WHERE conversa_id IN %s)" % _CONVERSAS_DA_LOJA
_ORCAMENTOS_DA_LOJA = "(SELECT id FROM orcamentos WHERE loja_id=:loja)"
_CLIENTES_DA_LOJA = "(SELECT id FROM clientes WHERE loja_id=:loja)"

PASSOS = [
    # ── chat/comunicação ────────────────────────────────────────────────────────────────
    ("envios_externos",
     "mensagem_id IN %s OR triagem_id IN (SELECT id FROM triagem_entradas WHERE loja_id=:loja)"
     % _MENSAGENS_DA_LOJA, False),
    ("mensagem_anexos", "mensagem_id IN %s" % _MENSAGENS_DA_LOJA, False),
    ("conversa_participantes", "conversa_id IN %s" % _CONVERSAS_DA_LOJA, False),
    ("conversa_participantes_externos", "conversa_id IN %s" % _CONVERSAS_DA_LOJA, False),
    ("conversa_mensagens", "conversa_id IN %s" % _CONVERSAS_DA_LOJA, False),
    ("triagem_entradas", "loja_id=:loja", False),
    ("conversas", "loja_id=:loja", False),

    # ── assinaturas (filhas de contrato/aditivo/aprovação/medição) ─────────────────────
    ("aditivos_assinaturas",
     "aditivo_id IN (SELECT id FROM aditivos WHERE loja_id=:loja)", False),
    ("aprovacoes_pe_assinaturas",
     "aprovacao_id IN (SELECT id FROM aprovacoes_pe WHERE loja_id=:loja)", False),
    ("contratos_assinaturas",
     "contrato_id IN (SELECT id FROM contratos WHERE loja_id=:loja)", False),
    ("solicitacoes_medicao_assinaturas",
     "solicitacao_id IN (SELECT id FROM solicitacoes_medicao WHERE loja_id=:loja)", False),

    # ── fábrica (acordo/ajuste) ─────────────────────────────────────────────────────────
    ("acordo_movimento",
     "acordo_id IN (SELECT id FROM acordo_fabrica WHERE loja_titular_id=:loja)", False),
    ("ajuste_fabrica_aplicacao",
     "ajuste_id IN (SELECT id FROM ajuste_fabrica WHERE loja_id=:loja)", False),

    # ── ambiente/pool (sem FK — projeto_nome é texto puro) ─────────────────────────────
    ("parcela_ambiente",
     "parcela_id IN (SELECT id FROM parcela_projeto WHERE projeto_nome IN %s)" % _PROJETOS_DA_LOJA,
     False),
    ("conciliacao_pe_fase", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("sinal_retido", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("arquivo_pe", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("orcamento_ambientes", "orcamento_id IN %s" % _ORCAMENTOS_DA_LOJA, False),

    # ── assistência ──────────────────────────────────────────────────────────────────
    ("assistencia_anexos",
     "caso_id IN (SELECT id FROM assistencia_caso WHERE loja_id=:loja)", False),
    ("assistencia_executores",
     "caso_id IN (SELECT id FROM assistencia_caso WHERE loja_id=:loja)", False),

    # ── ciclo logístico ──────────────────────────────────────────────────────────────
    ("ciclo_logistico_transicao",
     "ciclo_logistico_id IN (SELECT id FROM ciclo_logistico WHERE loja_id=:loja)", False),
    ("ciclo_logistico", "loja_id=:loja", False),

    # ── nível intermediário (loja_id direto, já sem filhos pendentes) ──────────────────
    ("aditivos", "loja_id=:loja", False),
    ("aprovacoes_pe", "loja_id=:loja", False),
    ("assistencia_caso", "loja_id=:loja", False),
    ("atribuicoes_ambiente", "loja_id=:loja", False),
    ("ajuste_fabrica", "loja_id=:loja", False),
    ("acordo_fabrica", "loja_titular_id=:loja", False),
    ("solicitacoes_medicao", "loja_id=:loja", False),

    # -- aqui, entre estes dois pontos, o script quebra o ciclo orcamentos<->parcela_projeto --

    ("contratos", "loja_id=:loja", False),
    ("provisao_registro", "orcamento_id IN %s" % _ORCAMENTOS_DA_LOJA, False),
    ("recebivel", "loja_id=:loja", False),
    ("parcela_projeto", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("orcamentos", "loja_id=:loja", False),
    ("pool_ambientes", "projeto_id IN %s" % _PROJETOS_DA_LOJA, False),

    # ── tabelas de projeto puramente por texto (sem FK, folhas em relação ao resto) ────
    ("ciclo_etapas", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("ciclo_revisoes", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("documento_fiscal", "loja_id=:loja", False),
    ("ciclo_documentos", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("medicoes", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("retencao_obra", "projeto_nome IN %s" % _PROJETOS_DA_LOJA, False),
    ("briefings", "projeto_nome IN %s OR cliente_id IN %s" % (_PROJETOS_DA_LOJA, _CLIENTES_DA_LOJA),
     False),
    ("veredictos_provisao", "owner_tipo='loja' AND owner_id=:loja", False),

    ("projetos_meta", "loja_id=:loja", False),

    # ── financeiro/contábil — só MOVIMENTO; conta/centro_custo são gabarito e ficam ────
    ("lancamento", "owner_tipo='loja' AND owner_id=:loja", False),
    ("comissao_folha", "loja_id=:loja", False),
    ("folha_pagamento", "loja_id=:loja", False),
    ("adiantamento_funcionario", "loja_id=:loja", False),

    ("leads", "loja_id=:loja", False),
    ("contato_confirmacoes", "loja_id=:loja", False),

    # ── além do que o documento nomeia literalmente — cadastro operacional da loja,
    #    incluído por inferência (mesma família de "clientes da loja"); avalie antes de aprovar ──
    ("fornecedores", "loja_id=:loja", True),
    ("terceiros", "loja_id=:loja", True),
    ("simulador_autorizacoes", "loja_id=:loja", True),
    ("simulador_log_acessos", "loja_id=:loja", True),

    ("clientes", "loja_id=:loja", False),
]


def _confirmar_master(db, loja_id, login):
    m = db.execute(text("SELECT id, loja_id, ativo FROM usuarios WHERE login=:l"),
                    {"l": login}).mappings().first()
    if m is None:
        sys.exit("RECUSADO: login master %r não existe." % login)
    if m["loja_id"] != loja_id:
        sys.exit("RECUSADO: %r pertence à loja_id=%s, não à loja alvo (%s)."
                  % (login, m["loja_id"], loja_id))
    return m


def _contar(db, tabela, where, params):
    return db.execute(text("SELECT COUNT(*) FROM %s WHERE %s" % (tabela, where)),
                       params).scalar()


def _rodar(args):
    db = get_session()
    try:
        _conferir_banco(db, args.banco_esperado)

        loja = db.get(Loja, args.loja)
        if loja is None:
            sys.exit("RECUSADO: loja id=%r não existe." % args.loja)
        print("loja alvo: id=%s %r" % (loja.id, loja.nome))

        master = _confirmar_master(db, loja.id, args.master_login)
        print("master que fica ativo: %r (id=%s, ativo hoje=%s)"
              % (args.master_login, master["id"], master["ativo"]))

        params = {"loja": loja.id, "master_login": args.master_login}

        total = 0
        print("\n=== SAI (conforme docs/db/TAREFA_LIMPAR_INSPIRIUM.md) ===")
        for tabela, where, alem_do_doc in PASSOS:
            if alem_do_doc:
                continue
            n = _contar(db, tabela, where, params)
            total += n
            print("  %-38s %6d" % (tabela, n))

        print("\n=== ALÉM DO QUE O DOCUMENTO NOMEIA — avalie antes de aprovar ===")
        for tabela, where, alem_do_doc in PASSOS:
            if not alem_do_doc:
                continue
            n = _contar(db, tabela, where, params)
            total += n
            print("  %-38s %6d" % (tabela, n))

        n_desativar = _contar(db, "usuarios", "loja_id=:loja AND login <> :master_login", params)
        n_func_inativar = db.execute(text(
            "SELECT COUNT(*) FROM funcionarios WHERE loja_id=:loja AND status <> 'inativo' "
            "AND (usuario_id IS NULL OR usuario_id NOT IN "
            "(SELECT id FROM usuarios WHERE login=:master_login))"), params).scalar()
        n_quebra_ciclo = _contar(db, "orcamentos", "loja_id=:loja AND parcela_id IS NOT NULL",
                                  params)

        print("\n=== FICA (não é tocado por este script) ===")
        print("  a própria Loja, funcoes, perfil_acesso, segmento_config, triagem_config,")
        print("  emitente, documento_modelos, documento_tipos, numero_conectado,")
        print("  template_mensagem, assuntos, integracoes_clicksign, parceiro_lojas,")
        print("  usuario_lojas, conta/centro_custo (gabarito — só o lancamento sai)")

        print("\n=== DESATIVAR (ativo=0 / status='inativo'), nunca apagar ===")
        print("  %-38s %6d" % ("usuarios (loja, exceto master)", n_desativar))
        print("  %-38s %6d" % ("funcionarios (loja, exceto vínculo do master)", n_func_inativar))

        print("\n=== quebra de ciclo (orcamentos.parcela_id -> NULL antes de apagar) ===")
        print("  %-38s %6d" % ("orcamentos.parcela_id afetados", n_quebra_ciclo))

        print("\nTOTAL de linhas que SAIRIAM: %d" % total)

        if not args.aplicar:
            print("\nPLANO apenas. Rode de novo com --aplicar pra gravar.")
            return

        print("\n--aplicar: executando dentro de uma transação (tudo ou nada)...")
        try:
            # Quebra do único ciclo genuíno do schema (orcamentos.parcela_id <->
            # parcela_projeto.orcamento_id) ANTES de apagar qualquer um dos dois lados —
            # sem isto, o DELETE de parcela_projeto mais adiante no laço esbarraria em
            # RESTRICT contra um orcamentos.parcela_id ainda apontando pra ele.
            db.execute(text("UPDATE orcamentos SET parcela_id=NULL "
                             "WHERE loja_id=:loja AND parcela_id IS NOT NULL"), params)

            for tabela, where, _ in PASSOS:
                db.execute(text("DELETE FROM %s WHERE %s" % (tabela, where)), params)

            db.execute(text("UPDATE usuarios SET ativo=0 "
                             "WHERE loja_id=:loja AND login <> :master_login"), params)
            db.execute(text("UPDATE usuarios SET ativo=1 "
                             "WHERE loja_id=:loja AND login = :master_login"), params)
            db.execute(text(
                "UPDATE funcionarios SET status='inativo' WHERE loja_id=:loja "
                "AND (usuario_id IS NULL OR usuario_id NOT IN "
                "(SELECT id FROM usuarios WHERE login=:master_login))"), params)

            db.commit()
            print("APLICADO. Rode `mod_contabil.varrer_orfaos_gabarito` (R16), depois "
                  "`bash docs/db/confirmar.sh` — Passo 3 do documento.")
        except Exception:
            db.rollback()
            print("ERRO — rollback feito, NADA foi apagado. Não improvise CASCADE: reporte "
                  "a mensagem abaixo e revise a ordem contra o grafo de FK real.")
            raise
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco-esperado", default="orizon_homologacao",
                    help="nome do banco que este script aceita (default: orizon_homologacao)")
    ap.add_argument("--loja", type=int, required=True, help="id da loja a limpar")
    ap.add_argument("--master-login", required=True,
                    help="login do usuário que fica ativo (os demais da loja viram ativo=0)")
    ap.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o plano (dry-run)")
    args = ap.parse_args()
    _rodar(args)


if __name__ == "__main__":
    main()
