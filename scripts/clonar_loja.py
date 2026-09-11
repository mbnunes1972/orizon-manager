# -*- coding: utf-8 -*-
"""Perfil de implantação de loja — docs/db/TAREFA_LOJA_TESTE.md, Etapas 1 e 1b.

Mesmo mecanismo (`mod_implantacao_loja.py`) serve dois casos:
  - CLONE: loja → loja no MESMO banco (Etapa 1 — nasce a Loja Teste a partir da Inspirium).
  - EXPORTAR/IMPORTAR: loja → arquivo JSON → loja, entre bancos diferentes (Etapa 1b — o caso
    de Produção). O clone é só o caso em que o artefato não chega a tocar o disco.

CONFIGURAÇÃO viaja, DADO não. Segredo (tokens, certificado) nunca sai do banco de origem —
nem no clone, nem no artefato exportado. Identidade (CNPJ, razão social, inscrições) só é
ESCRITA no destino com `--permitir-identidade` — sem a flag, o script diz o que recusou.
Remuneração em dinheiro da Função (salário, benefícios, comissão fixa) só é ESCRITA com
`--copiar-remuneracao` — sem a flag, viaja só a estrutura (percentual de comissão/faixas), e o
script diz que a remuneração não copiou (DECIDIDO 11/09: salário é decisão de cada loja).

A REFERÊNCIA é Homologação, não a bancada local — medido 11/09, ver mod_implantacao_loja.py.
Contra a bancada isto é ENSAIO do mecanismo, não a operação real.

Guardas (mesmo padrão de seed_funcionarios_homolog.py):
  - afirma o NOME do banco antes de qualquer escrita (`--banco-esperado`, default
    orizon_homologacao) e recusa qualquer banco com "produc" no nome, sempre;
  - só escreve com `--aplicar`; sem ele, imprime o plano e sai (dry-run) — inclusive a lista de
    divergências do plano de contas/centro de custo contra o gabarito, ANTES de decidir
    aplicar qualquer uma (--aceitar-divergencia);
  - idempotente: rodar duas vezes não duplica perfil, função nem modelo.

Uso:
  # 1. Sempre primeiro, sem --aplicar: mostra o plano e a lista de divergências do gabarito.
  python3 scripts/clonar_loja.py clone --origem-loja 1 --nome "Loja Teste" --codigo TES

  # 2. Decidido quais divergências (se houver) são config legítima, roda de novo aceitando-as
  #    e gravando. --permitir-identidade é a decisão do Marcelo (11/09) de copiar cnpj/razão
  #    social da Inspirium — condicional a este ambiente (só há credencial de homologação em
  #    uso); em Produção esta flag não se liga (ver docstring de aplicar_config_loja).
  #    --copiar-remuneracao é ESPECÍFICO da Loja Teste: ela herda a folha de teste montada em
  #    10/09 pra não obrigar refazer esse trabalho — loja real em Produção nunca liga isto.
  python3 scripts/clonar_loja.py clone --origem-loja 1 --nome "Loja Teste" --codigo TES \\
      --permitir-identidade --copiar-remuneracao --aceitar-divergencia 1.1.09 --aplicar

  # Exportar (Etapa 1b) — o artefato pode ser versionado no git (sem segredo, ver docstring
  # do módulo):
  python3 scripts/clonar_loja.py exportar --origem-loja 1 --arquivo docs/db/config_loja_1.json

  # Importar num banco DIFERENTE (Produção) — mesmo padrão de plano/--aplicar/divergências:
  python3 scripts/clonar_loja.py importar --arquivo docs/db/config_loja_1.json \\
      --nome "Loja Nova" --codigo NOV --aplicar
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import Loja, get_session
import mod_implantacao_loja as mil


def _conferir_banco(db, banco_esperado):
    banco = db.execute(text("SELECT current_database()")).scalar()
    if "produc" in (banco or "").lower():
        sys.exit("RECUSADO: banco %r parece PRODUÇÃO. Este script não roda lá." % banco)
    if banco != banco_esperado:
        sys.exit("RECUSADO: conectou em %r, esperado %r. Confira o DATABASE_URL (ou passe "
                 "--banco-esperado se a intenção for outra)." % (banco, banco_esperado))
    print("banco: %s" % banco)
    return banco


def _imprimir_divergencias(divergencias):
    if not divergencias:
        print("\ndivergências do plano de contas/centro de custo contra o gabarito: NENHUMA.")
        return
    print("\n=== %d divergência(s) do gabarito — decida quais são config legítima e quais são "
          "resíduo (não é decisão do script) ===" % len(divergencias))
    for d in divergencias:
        print("  [%s] %-10s gabarito=%r" % (d["tabela"], d["codigo"], d["gabarito"]))
        print("  %s%-10s origem  =%r" % (" " * (len(d["tabela"]) + 3), "", d["owner"]))
    print("Rode de novo com --aceitar-divergencia <codigo> (repetível) pra aplicar alguma; "
          "sem isso, a loja nova fica só com o gabarito, nenhuma divergência entra.")


def _relatorio(rel):
    print("\n=== aplicado ===")
    for k, v in rel["aplicado"].items():
        print("  %s: %s" % (k, v))
    if rel["recusado"]:
        print("=== recusado ===")
        for r in rel["recusado"]:
            print("  - %s" % r)


def cmd_clone(args):
    db = get_session()
    try:
        _conferir_banco(db, args.banco_esperado)
        origem = db.get(Loja, args.origem_loja)
        if origem is None:
            sys.exit("RECUSADO: loja origem id=%r não existe." % args.origem_loja)
        print("origem: id=%s %r" % (origem.id, origem.nome))

        artefato = mil.exportar_config_loja(db, origem.id, exportado_por=os.environ.get("USER"))
        _imprimir_divergencias(artefato["gabarito_divergencias"])

        print("\nplano: nova loja nome=%r codigo=%r rede_id=%r" %
              (args.nome, args.codigo, args.rede_id))
        print("  perfis a aplicar: %d (%s)" % (len(artefato["perfis"]),
              ", ".join(p["slug"] for p in artefato["perfis"])))
        print("  funções a aplicar: %d" % len(artefato["funcoes"]))
        print("  documentos-modelo (versão ativa) a aplicar: %d (%s)" %
              (len(artefato["documentos_modelo"]),
               ", ".join(d["tipo"] for d in artefato["documentos_modelo"])))
        print("  emitente: %s" % ("sim" if artefato["emitente"] else "não (origem sem Emitente)"))
        print("  identidade (cnpj/razão social) será aplicada: %s" %
              ("sim" if args.permitir_identidade else "NÃO — falta --permitir-identidade"))
        print("  remuneração (salario_fixo/beneficios/comissao_fixa) será copiada: %s" %
              ("sim" if args.copiar_remuneracao else
               "NÃO — configure na tela de Funções (falta --copiar-remuneracao)"))

        if not args.aplicar:
            print("\nPLANO apenas. Rode de novo com --aplicar pra gravar.")
            return

        nova = db.query(Loja).filter_by(codigo=args.codigo).first()
        if nova is None:
            nova = mil.criar_loja_base(db, nome=args.nome, codigo=args.codigo,
                                       rede_id=args.rede_id)
            print("\nloja criada: id=%s" % nova.id)
        else:
            print("\nloja já existe (id=%s) — reaplicando config por cima (idempotente)." % nova.id)

        rel = mil.aplicar_config_loja(db, nova.id, artefato, excecoes={
            "permitir_identidade": args.permitir_identidade,
            "divergencias_gabarito_aceitas": args.aceitar_divergencia,
            "copiar_remuneracao": args.copiar_remuneracao,
        })
        _relatorio(rel)
        print("\nGRAVADO. Rode `mod_contabil.varrer_orfaos_gabarito` (R16) antes de considerar concluído.")
    finally:
        db.close()


def cmd_exportar(args):
    db = get_session()
    try:
        _conferir_banco(db, args.banco_esperado)
        origem = db.get(Loja, args.origem_loja)
        if origem is None:
            sys.exit("RECUSADO: loja origem id=%r não existe." % args.origem_loja)
        banco = db.execute(text("SELECT current_database()")).scalar()
        artefato = mil.exportar_config_loja(db, origem.id, exportado_por=os.environ.get("USER"),
                                            ambiente_origem=banco)
        _imprimir_divergencias(artefato["gabarito_divergencias"])
        bruto = json.dumps(artefato, ensure_ascii=False, indent=2, default=str)
        for alerta in ("token", "focus_", "cert_"):
            if alerta in bruto.lower():
                sys.exit("RECUSADO: o artefato contém %r — isto NUNCA pode sair do banco. "
                         "Não escrevi o arquivo. Isto é bug em exportar_config_loja, avise." % alerta)
        if not args.aplicar:
            print("\nPLANO apenas — %d bytes seriam escritos em %r. Rode de novo com --aplicar."
                  % (len(bruto), args.arquivo))
            return
        with open(args.arquivo, "w", encoding="utf-8") as f:
            f.write(bruto)
        print("\nESCRITO: %r (%d bytes). Sem segredo, sem identidade solta, sem dado — "
              "pode versionar no git." % (args.arquivo, len(bruto)))
    finally:
        db.close()


def cmd_importar(args):
    with open(args.arquivo, encoding="utf-8") as f:
        artefato = json.load(f)
    print("artefato: versao_formato=%s origem=%s (%s) exportado_em=%s por=%s" % (
        artefato.get("versao_formato"), artefato["loja_origem"]["nome"],
        artefato.get("ambiente_origem"), artefato.get("exportado_em"), artefato.get("exportado_por")))

    db = get_session()
    try:
        _conferir_banco(db, args.banco_esperado)
        _imprimir_divergencias(artefato["gabarito_divergencias"])
        print("\nplano: nova loja nome=%r codigo=%r rede_id=%r" %
              (args.nome, args.codigo, args.rede_id))
        print("  identidade (cnpj/razão social) será aplicada: %s" %
              ("sim" if args.permitir_identidade else "NÃO — falta --permitir-identidade"))
        print("  remuneração (salario_fixo/beneficios/comissao_fixa) será copiada: %s" %
              ("sim" if args.copiar_remuneracao else
               "NÃO — configure na tela de Funções (falta --copiar-remuneracao)"))
        if not args.aplicar:
            print("\nPLANO apenas. Rode de novo com --aplicar pra gravar.")
            return
        nova = db.query(Loja).filter_by(codigo=args.codigo).first()
        if nova is None:
            nova = mil.criar_loja_base(db, nome=args.nome, codigo=args.codigo,
                                       rede_id=args.rede_id)
            print("\nloja criada: id=%s" % nova.id)
        else:
            print("\nloja já existe (id=%s) — reaplicando config por cima (idempotente)." % nova.id)
        rel = mil.aplicar_config_loja(db, nova.id, artefato, excecoes={
            "permitir_identidade": args.permitir_identidade,
            "divergencias_gabarito_aceitas": args.aceitar_divergencia,
            "copiar_remuneracao": args.copiar_remuneracao,
        })
        _relatorio(rel)
        print("\nGRAVADO. Rode `mod_contabil.varrer_orfaos_gabarito` (R16) antes de considerar concluído.")
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--banco-esperado", default="orizon_homologacao",
                    help="nome do banco que este script aceita (default: orizon_homologacao)")
    sub = ap.add_subparsers(dest="comando", required=True)

    p_clone = sub.add_parser("clone", help="loja -> loja no MESMO banco (Etapa 1)")
    p_clone.add_argument("--origem-loja", type=int, required=True)
    p_clone.add_argument("--nome", required=True)
    p_clone.add_argument("--codigo", required=True, help="3 letras, unique (ex.: TES)")
    p_clone.add_argument("--rede-id", type=int, default=None)
    p_clone.add_argument("--permitir-identidade", action="store_true")
    p_clone.add_argument("--copiar-remuneracao", action="store_true",
                         help="copia salario_fixo/beneficios_json/comissao_fixa das Funções "
                              "(default: NÃO copia — salário é decisão de cada loja)")
    p_clone.add_argument("--aceitar-divergencia", action="append", default=[],
                         metavar="CODIGO", help="repetível — código de conta/centro de custo")
    p_clone.add_argument("--aplicar", action="store_true")
    p_clone.set_defaults(func=cmd_clone)

    p_exp = sub.add_parser("exportar", help="loja -> arquivo JSON (Etapa 1b)")
    p_exp.add_argument("--origem-loja", type=int, required=True)
    p_exp.add_argument("--arquivo", required=True)
    p_exp.add_argument("--aplicar", action="store_true", help="sem isto, só mostra o tamanho/plano")
    p_exp.set_defaults(func=cmd_exportar)

    p_imp = sub.add_parser("importar", help="arquivo JSON -> loja, banco diferente (Etapa 1b)")
    p_imp.add_argument("--arquivo", required=True)
    p_imp.add_argument("--nome", required=True)
    p_imp.add_argument("--codigo", required=True)
    p_imp.add_argument("--rede-id", type=int, default=None)
    p_imp.add_argument("--permitir-identidade", action="store_true")
    p_imp.add_argument("--copiar-remuneracao", action="store_true",
                       help="copia salario_fixo/beneficios_json/comissao_fixa das Funções "
                            "(default: NÃO copia — salário é decisão de cada loja)")
    p_imp.add_argument("--aceitar-divergencia", action="append", default=[], metavar="CODIGO")
    p_imp.add_argument("--aplicar", action="store_true")
    p_imp.set_defaults(func=cmd_importar)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
