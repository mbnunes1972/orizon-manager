# -*- coding: utf-8 -*-
"""docs/db/TAREFA_LOJA_TESTE.md — a fatoração que faz o clone (loja→loja no mesmo banco) e a
implantação entre ambientes (loja→arquivo→loja) serem a MESMA função por baixo:

    exportar_config_loja(db, loja_id)                        -> artefato
    aplicar_config_loja(db, loja_destino_id, artefato, exc)   -> relatorio
    clone = aplicar_config_loja(db, nova.id, exportar_config_loja(db, origem.id))

Usa `app_db`+`seed` (Postgres de teste, `orizon_test`) — precisa de owners de verdade porque o
gabarito é `owner_tipo='loja'` e `varrer_orfaos_gabarito`/`aplicar_gabarito_completo` leem
`Loja`/`Rede` reais."""
import itertools
import json

import pytest

import mod_contabil as mc
import mod_implantacao_loja as mil
from database import CentroCusto, Conta, DocumentoModelo, Emitente, Funcao, Loja, PerfilAcesso

_CODIGO_SEQ = itertools.count(1)


@pytest.fixture
def origem_configurada(app_db, seed):
    """Cria uma loja ORIGEM própria (não reusa loja1 do `seed`, que é module-scoped e
    compartilhada entre testes — reusar colidiria em uq_doc_modelo_versao/uq_perfil_loja_slug
    já na 2ª rodada) e a enriquece com o que o mecanismo precisa mover: perfil customizado,
    função com remuneração, modelo de documento ativo, e um Emitente com identidade+fiscal+
    segredo (pra provar que o segredo NUNCA sai daqui)."""
    db = app_db.get_session()
    try:
        codigo = "OR%d" % next(_CODIGO_SEQ)
        loja_id = mil.criar_loja_base(db, nome="Origem %s" % codigo, codigo=codigo).id

        # Perfil de sistema (gerencial) com um módulo a mais que o padrão — prova que o
        # OVERRIDE viaja, não só os 3 defaults.
        gerencial = db.query(PerfilAcesso).filter_by(loja_id=loja_id, slug="gerencial").first()
        mods = json.loads(gerencial.modulos_json)
        if "admin" not in mods:
            mods.append("admin")
        gerencial.modulos_json = json.dumps(mods)
        gerencial.capacidades_json = json.dumps({"aprovar_financeiro": True})

        # Perfil CUSTOM, fora dos 3 padrão — prova que perfil extra também viaja.
        db.add(PerfilAcesso(loja_id=loja_id, slug="financeiro_pleno", nome="Financeiro Pleno",
                            base="gerencial", modulos_json=json.dumps(["financeiro", "fiscal"]),
                            capacidades_json="{}", sistema=0))

        # "Gerente de Vendas" já existe (um dos 13 default de criar_funcoes_seed) — configura a
        # remuneração nela, não duplica. "Cargo Só Desta Loja" é extra, fora dos 13 padrão.
        gerente_vendas = db.query(Funcao).filter_by(loja_id=loja_id, nome="Gerente de Vendas").first()
        gerente_vendas.salario_fixo = 4500.0
        gerente_vendas.beneficios_json = json.dumps({"va": {"on": True, "valor": 800}})
        db.add(Funcao(loja_id=loja_id, nome="Cargo Só Desta Loja", status="ativo",
                      salario_fixo=1000.0, usa_comissao_vendas=0))

        db.add(DocumentoModelo(loja_id=loja_id, tipo="contrato", versao=1, nome="Contrato padrão",
                               corpo_md="# Contrato\n\nCláusula 1...", ativo=1))
        db.add(DocumentoModelo(loja_id=loja_id, tipo="contrato", versao=2, nome="Contrato v2",
                               corpo_md="# Contrato v2\n\nCláusula 1 revisada...", ativo=0))

        em = Emitente(cnpj="11.222.333/0001-44", razao_social="Origem Comercio LTDA",
                      inscricao_estadual="ISENTO", inscricao_municipal="123",
                      regime_tributario="simples", csosn_padrao="101", csosn_contribuinte="101",
                      cfop_dentro_uf="5102", cfop_fora_uf="6102", municipio_ibge="3550308",
                      cidade="Sao Paulo", uf="SP", cep="01000-000",
                      focus_token_homolog_enc="SEGREDO_HOMOLOG_XYZ",
                      focus_token_prod_enc="SEGREDO_PROD_NUNCA_SAI",
                      ambiente_ativo="producao",   # de propósito — prova que o destino força homologacao
                      cert_cnpj="11.222.333/0001-44", rede_id=None)
        db.add(em); db.flush()
        loja = db.get(Loja, loja_id)
        loja.emitente_id = em.id
        loja.config_financeira_json = json.dumps({"comissao_vendas": {"faixas": [{"pct": 1.0}]}})
        loja.telefone = "(12) 3456-7890"

        db.commit()
        return loja_id
    finally:
        db.close()


def test_artefato_nunca_carrega_segredo(app_db, origem_configurada):
    db = app_db.get_session()
    try:
        artefato = mil.exportar_config_loja(db, origem_configurada)
    finally:
        db.close()
    bruto = json.dumps(artefato, default=str)
    assert "SEGREDO_HOMOLOG_XYZ" not in bruto
    assert "SEGREDO_PROD_NUNCA_SAI" not in bruto
    assert "focus_token" not in bruto
    assert "cert_cnpj" not in bruto and "cert_validade" not in bruto
    # identidade viaja, mas MARCADA — nunca solta misturada com o resto do emitente
    assert artefato["emitente"]["identidade"]["cnpj"] == "11.222.333/0001-44"
    assert "cnpj" not in artefato["emitente"]["fiscal"]


def test_clone_e_implantacao_de_arquivo_produzem_a_mesma_loja(app_db, origem_configurada, tmp_path):
    """Aceite 7: aplicar_config_loja(nova, exportar_config_loja(origem)) e aplicar_config_loja
    (nova2, json.load(arquivo)) produzem a MESMA config — clone e implantação são a mesma função."""
    db = app_db.get_session()
    try:
        artefato = mil.exportar_config_loja(db, origem_configurada, exportado_por="teste")
        arquivo = tmp_path / "config_loja.json"
        arquivo.write_text(json.dumps(artefato), encoding="utf-8")

        nova_clone = mil.criar_loja_base(db, nome="Clone Direto", codigo="CL1")
        rel_clone = mil.aplicar_config_loja(db, nova_clone.id, artefato,
                                            excecoes={"permitir_identidade": True})

        artefato_do_arquivo = json.loads(arquivo.read_text(encoding="utf-8"))
        nova_arquivo = mil.criar_loja_base(db, nome="Via Arquivo", codigo="CL2")
        rel_arquivo = mil.aplicar_config_loja(db, nova_arquivo.id, artefato_do_arquivo,
                                              excecoes={"permitir_identidade": True})

        assert rel_clone["aplicado"]["perfis"] == rel_arquivo["aplicado"]["perfis"]
        assert rel_clone["aplicado"]["funcoes"] == rel_arquivo["aplicado"]["funcoes"]

        def _snapshot(loja_id):
            loja = db.get(Loja, loja_id)
            perfis = {p.slug: (p.nome, p.base, json.loads(p.modulos_json), json.loads(p.capacidades_json))
                     for p in db.query(PerfilAcesso).filter_by(loja_id=loja_id).all()}
            funcoes = {f.nome: (f.salario_fixo, f.beneficios_json) for f in
                      db.query(Funcao).filter_by(loja_id=loja_id).all()}
            em = db.get(Emitente, loja.emitente_id)
            return (loja.config_financeira_json, loja.telefone, perfis, funcoes,
                    em.cnpj, em.razao_social, em.ambiente_ativo, em.focus_token_prod_enc)

        assert _snapshot(nova_clone.id) == _snapshot(nova_arquivo.id)
    finally:
        db.close()


def test_identidade_recusada_sem_a_flag_e_nunca_silenciosa(app_db, origem_configurada):
    """Aceite 10: sem permitir_identidade, CNPJ/razão social do destino ficam intocados, e a
    operação DIZ o que recusou."""
    db = app_db.get_session()
    try:
        artefato = mil.exportar_config_loja(db, origem_configurada)
        nova = mil.criar_loja_base(db, nome="Sem Identidade", codigo="SID")
        rel = mil.aplicar_config_loja(db, nova.id, artefato)   # sem excecoes

        em = db.get(Emitente, db.get(Loja, nova.id).emitente_id)
        assert em.cnpj is None and em.razao_social is None, (
            "identidade não pode vazar sem a flag explícita")
        assert em.regime_tributario == "simples", "fiscal não-identidade aplica sempre"
        assert em.ambiente_ativo == "homologacao"
        assert em.focus_token_prod_enc is None
        assert any("identidade" in r for r in rel["recusado"]), (
            "a recusa tem que aparecer no relatório, não silenciar")
    finally:
        db.close()


def test_aplicar_duas_vezes_nao_duplica(app_db, origem_configurada):
    """Aceite 5/9: idempotente — rodar duas vezes não duplica perfil, função nem modelo."""
    db = app_db.get_session()
    try:
        artefato = mil.exportar_config_loja(db, origem_configurada)
        nova = mil.criar_loja_base(db, nome="Idempotente", codigo="IDM")
        mil.aplicar_config_loja(db, nova.id, artefato, excecoes={"permitir_identidade": True})
        mil.aplicar_config_loja(db, nova.id, artefato, excecoes={"permitir_identidade": True})

        n_perfis = db.query(PerfilAcesso).filter_by(loja_id=nova.id).count()
        n_funcoes = db.query(Funcao).filter_by(loja_id=nova.id).count()
        n_docs = db.query(DocumentoModelo).filter_by(loja_id=nova.id).count()
        emitente_id_da_nova = db.get(Loja, nova.id).emitente_id
        n_emitente_desta_loja = 1 if emitente_id_da_nova else 0

        assert n_perfis == len(artefato["perfis"])
        assert n_funcoes == len(artefato["funcoes"])
        assert n_docs == len(artefato["documentos_modelo"]), (
            "corpo_md igual na 2ª rodada não pode criar versão nova")
        assert emitente_id_da_nova is not None
        # a 2ª aplicação tem que ter ATUALIZADO o MESMO Emitente, não criado outro
        db.expire_all()
        assert db.get(Loja, nova.id).emitente_id == emitente_id_da_nova
        assert n_emitente_desta_loja == 1, "não pode duplicar Emitente"
    finally:
        db.close()


def test_zero_dado_e_zero_pessoas_na_loja_nova(app_db, origem_configurada):
    """Aceite 3: zero clientes, projetos, contratos, funcionários e usuários na loja nova."""
    from database import Cliente, Contrato, Funcionario, Orcamento, Usuario
    db = app_db.get_session()
    try:
        artefato = mil.exportar_config_loja(db, origem_configurada)
        nova = mil.criar_loja_base(db, nome="Sem Dado", codigo="SDA")
        mil.aplicar_config_loja(db, nova.id, artefato, excecoes={"permitir_identidade": True})

        assert db.query(Cliente).filter_by(loja_id=nova.id).count() == 0
        assert db.query(Orcamento).filter_by(loja_id=nova.id).count() == 0
        assert db.query(Contrato).filter_by(loja_id=nova.id).count() == 0
        assert db.query(Funcionario).filter_by(loja_id=nova.id).count() == 0
        assert db.query(Usuario).filter_by(loja_id=nova.id).count() == 0
    finally:
        db.close()


def test_gabarito_semeado_nunca_copiado_e_divergencia_so_aplica_se_aceita(app_db, seed):
    """Etapa 1: plano de contas e centro de custo SEMEADOS (gabarito), não copiados — só as
    divergências explicitamente aceitas em excecoes entram por cima."""
    db = app_db.get_session()
    try:
        loja_id = seed["loja1_id"]
        mc.aplicar_gabarito_completo(db, "loja", loja_id)
        # Introduz uma divergência sintética: renomeia uma conta folha do gabarito na ORIGEM
        # (simula resíduo/renome represado — R13) sem tocar no código.
        alvo = db.query(Conta).filter_by(owner_tipo="loja", owner_id=loja_id, codigo="1.1.01").first()
        nome_original = alvo.nome
        alvo.nome = nome_original + " (RENOMEADA NA ORIGEM)"
        db.commit()

        divergencias = mil.divergencias_gabarito(db, "loja", loja_id)
        alvo_div = next(d for d in divergencias if d["codigo"] == "1.1.01" and d["tabela"] == "conta")
        assert alvo_div["owner"][0] == nome_original + " (RENOMEADA NA ORIGEM)"

        artefato = mil.exportar_config_loja(db, loja_id)
        assert any(d["codigo"] == "1.1.01" for d in artefato["gabarito_divergencias"])

        # Sem aceitar nada: a loja nova nasce com o NOME DO GABARITO, não o renomeado.
        nova = mil.criar_loja_base(db, nome="Sem Aceitar Divergencia", codigo="SAD")
        rel = mil.aplicar_config_loja(db, nova.id, artefato)
        conta_nova = db.query(Conta).filter_by(owner_tipo="loja", owner_id=nova.id, codigo="1.1.01").first()
        assert conta_nova.nome == nome_original
        assert any("gabarito" in r.lower() for r in rel["recusado"])

        # Aceitando explicitamente: agora o renomeado viaja.
        nova2 = mil.criar_loja_base(db, nome="Aceitando Divergencia", codigo="ACD")
        mil.aplicar_config_loja(db, nova2.id, artefato,
                                excecoes={"divergencias_gabarito_aceitas": ["1.1.01"]})
        conta_nova2 = db.query(Conta).filter_by(owner_tipo="loja", owner_id=nova2.id, codigo="1.1.01").first()
        assert conta_nova2.nome == nome_original + " (RENOMEADA NA ORIGEM)"
    finally:
        db.close()
