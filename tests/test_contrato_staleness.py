"""
tests/test_contrato_staleness.py — Testes para flag 'desatualizado' de contrato.

Part A pure: testa a função contrato_desatualizado() de mod_contrato.
Part A E2E: testa que GET /api/projetos/<nome>/contrato retorna desatualizado=True.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import mod_contrato


# ── Testes puros da função helper ─────────────────────────────────────────────

def test_desatualizado_tipo_diferente():
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"cartao","total_cliente":100}',
        '{"tipo":"aymore","total_cliente":100}'
    ) is True


def test_desatualizado_total_diferente():
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"cartao","total_cliente":100}',
        '{"tipo":"cartao","total_cliente":200}'
    ) is True


def test_atualizado_igual():
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"cartao","total_cliente":100}',
        '{"tipo":"cartao","total_cliente":100}'
    ) is False


def test_sem_dados_nao_acusa():
    assert mod_contrato.contrato_desatualizado(
        None,
        '{"tipo":"cartao"}'
    ) is False


def test_desatualizado_tipo_diferente_real_case():
    """Caso real: snapshot cartao, orçamento atual aymore."""
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"cartao","total_cliente":232838.74}',
        '{"tipo":"aymore","total_cliente":185700.46}'
    ) is True


def test_atualizado_arredondamento_2_casas():
    """Diferenças menores que 0.005 não devem acusar desatualizado."""
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"aymore","total_cliente":100.001}',
        '{"tipo":"aymore","total_cliente":100.002}'
    ) is False


def test_sem_snapshot_nao_acusa():
    assert mod_contrato.contrato_desatualizado(None, None) is False


def test_snapshot_invalido_nao_acusa():
    assert mod_contrato.contrato_desatualizado(
        'nao_eh_json',
        '{"tipo":"cartao","total_cliente":100}'
    ) is False


def test_forma_pagamento_atual_nula_nao_acusa():
    assert mod_contrato.contrato_desatualizado(
        '{"tipo":"cartao","total_cliente":100}',
        None
    ) is False


def test_desatualizado_aceita_dict_direto():
    """Deve funcionar também quando recebe dict (não só string JSON)."""
    assert mod_contrato.contrato_desatualizado(
        {"tipo": "cartao", "total_cliente": 100},
        {"tipo": "aymore", "total_cliente": 100}
    ) is True


# ── Teste E2E: GET /api/projetos/<nome>/contrato retorna desatualizado ─────────

def test_get_contrato_desatualizado_true(app_db, seed, servidor, http_client_factory):
    """Quando pagamento_json do contrato diverge do forma_pagamento do orçamento,
    GET /api/projetos/<nome>/contrato deve retornar desatualizado=True."""
    # Atualiza o banco diretamente: coloca pagamentos divergentes
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.forma_pagamento = '{"tipo":"cartao","total_cliente":1000}'

        ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
        ct.pagamento_json = '{"tipo":"aymore","total_cliente":2000}'

        db.commit()
    finally:
        db.close()

    # Faz login e chama o endpoint
    client = http_client_factory()
    status, body = client.login("dir_l1", "senha123")
    assert status == 200

    status, body = client.get(f"/api/projetos/{seed['projeto_l1']}/contrato")
    assert status == 200
    assert body["ok"] is True
    assert body["contrato"] is not None
    assert body["contrato"]["desatualizado"] is True
    assert body["contrato"]["orcamento_id"] == seed["orcamento_l1_id"]


def test_get_contrato_atualizado_false(app_db, seed, servidor, http_client_factory):
    """Quando pagamento_json e forma_pagamento são iguais, desatualizado=False."""
    db = app_db.get_session()
    try:
        orc = db.get(app_db.Orcamento, seed["orcamento_l1_id"])
        orc.forma_pagamento = '{"tipo":"cartao","total_cliente":1000}'

        ct = db.get(app_db.Contrato, seed["contrato_l1_id"])
        ct.pagamento_json = '{"tipo":"cartao","total_cliente":1000}'

        db.commit()
    finally:
        db.close()

    client = http_client_factory()
    client.login("dir_l1", "senha123")

    status, body = client.get(f"/api/projetos/{seed['projeto_l1']}/contrato")
    assert status == 200
    assert body["contrato"]["desatualizado"] is False
