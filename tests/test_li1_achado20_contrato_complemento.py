# -*- coding: utf-8 -*-
"""ACHADO-20/LI-1 (docs/db/LISTA_IMEDIATA.md) — A PORTA: `POST /api/projetos/<nome>/contrato`
recusa `orcamento_id` de um orçamento `complemento_pe=1`, com erro nomeado (400), ANTES de criar
o `Contrato`. É o conserto que impede o estado auto-referente de NASCER pelo caminho normal (o
"fundo do poço" em `_pe_fator_contexto`/`main.ContratoComplementoAutoReferente`, coberto em
tests/test_negociacao_breakdown_excecoes.py, protege contra o estado que já exista no banco por
outro caminho — correção manual, migração, importação).

Sobe o servidor real (fixture `servidor`) e bate via HTTP, como test_contrato_modelo_versionado_
e2e.py — a guarda é lida do dado realmente aceito na rota, não chamada direto."""
import json

import pytest


@pytest.fixture(scope="module")
def dados_l1(app_db, seed):
    """Completa o cliente da Loja 1 (seed só traz o mínimo) para o CONTROLE NEGATIVO (orçamento
    normal) conseguir passar por `validar_cliente_para_contrato` e chegar a 200 — a rejeição do
    complemento acontece bem antes dessas validações, então ela não precisa disto."""
    db = app_db.get_session()
    try:
        cliente = db.get(app_db.Cliente, seed["cliente_l1_id"])
        cliente.email = "cliente@teste.com"
        cliente.telefone = "(12) 90000-0000"
        cliente.logradouro = "Rua das Flores"
        cliente.numero = "100"
        cliente.bairro = "Centro"
        cliente.cidade = "São José dos Campos"
        cliente.estado = "SP"
        cliente.cep = "12200-000"

        pool = app_db.PoolAmbiente(
            projeto_id=seed["projeto_l1"], nome="cozinha_li1", versao=1,
            nome_exibicao="Cozinha LI-1", xml_path="x.xml", ambientes_json="{}",
            budget_total=1000.0, order_total=1000.0,
        )
        db.add(pool); db.flush()
        oa = app_db.OrcamentoAmbiente(orcamento_id=seed["orcamento_l1_id"],
                                      pool_ambiente_id=pool.id, ordem=1)
        db.add(oa)
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.valor_total = 1000.0
        db.commit()
    finally:
        db.close()
    return seed


def _confirmar_contatos(client, nome_projeto):
    # Gate de contatos (decisão 13, mini-frente 2026-07-25): roda ANTES da guarda do LI-1 —
    # sem isto o endpoint recusa por outro motivo, e o teste não provaria a guarda certa.
    status, body = client.post(f"/api/projetos/{nome_projeto}/contatos-comunicacao/confirmar",
                               {"modo": "sem_whatsapp"})
    assert status == 200, body


def test_post_contrato_recusa_orcamento_de_complemento(app_db, seed, servidor, http_client_factory):
    db = app_db.get_session()
    try:
        orc_compl = app_db.Orcamento(projeto_id=seed["projeto_l1"], nome="Complemento LI-1",
                                     ordem=99, complemento_pe=1, loja_id=seed["loja1_id"])
        db.add(orc_compl); db.commit()
        orc_compl_id = orc_compl.id
    finally:
        db.close()

    client = http_client_factory()
    status, body = client.login("dir_l1", "senha123")
    assert status == 200, body
    _confirmar_contatos(client, seed["projeto_l1"])

    status, body = client.post(
        f"/api/projetos/{seed['projeto_l1']}/contrato",
        {"orcamento_id": orc_compl_id, "confirmar_loja_incompleta": True},
    )
    assert status == 400, body
    assert body["ok"] is False, body
    assert "complemento" in body["erro"].lower(), (
        "erro nomeado precisa dizer que é complemento de PE — %r" % body)

    db = app_db.get_session()
    try:
        # não nasceu Contrato nenhum apontando para o orçamento de complemento — a porta
        # impediu o estado ANTES da criação, não depois.
        preso = db.query(app_db.Contrato).filter_by(orcamento_id=orc_compl_id).first()
        assert preso is None, "a guarda tem que recusar ANTES de criar o Contrato"
    finally:
        db.close()


def test_post_contrato_com_orcamento_normal_continua_passando(
        app_db, dados_l1, servidor, http_client_factory):
    """CONTROLE NEGATIVO (obrigatório no LI-1): a guarda nova não pode bloquear o caminho feliz
    — um orçamento comum (`complemento_pe=0`, o padrão) segue gerando contrato normalmente."""
    client = http_client_factory()
    status, body = client.login("dir_l1", "senha123")
    assert status == 200, body
    _confirmar_contatos(client, dados_l1["projeto_l1"])

    status, body = client.post(
        f"/api/projetos/{dados_l1['projeto_l1']}/contrato",
        {
            "orcamento_id": dados_l1["orcamento_l1_id"],
            "endereco_instalacao": "Rua das Flores, 100",
            "entrada_valor": 100.0,
            "parcelas_descricao": "1x",
            "forma_entrada": "pix",
            "forma_parcelas": "boleto",
            "pagamento_json": json.dumps({"tipo": "avista",
                                          "parcelas": [{"num": 1, "valor": 1000.0}]}),
            "confirmar_loja_incompleta": True,
        },
    )
    assert status == 200, body
    assert body["ok"] is True, body

    db = app_db.get_session()
    try:
        contrato = db.get(app_db.Contrato, body["contrato_id"])
        assert contrato.orcamento_id == dados_l1["orcamento_l1_id"]
    finally:
        db.close()
