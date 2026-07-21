"""Validação do plano de pagamento persistido (forma_pagamento do orçamento).

Bug origem (2026-07-21): plano Total Flex digitado para um total que depois mudou
(ambiente removido) fechava a ÚLTIMA parcela negativa e era salvo assim. O frontend
foi corrigido (reinicializa o plano quando o total muda), e este validador é o cinto
de segurança do backend: nunca persistir plano com parcela/entrada negativa.
"""
from mod_fin import validar_plano_pagamento


def _plano_tf(parcelas, entrada=1000.0):
    return {"tipo": "tf", "nome_forma": "Total Flex", "entrada_valor": entrada,
            "total_cliente": entrada + sum(p.get("valor") or 0 for p in parcelas),
            "parcelas": parcelas}


def test_plano_ok_passa():
    p = _plano_tf([{"num": 1, "data": "2026-08-20", "valor": 500.0},
                   {"num": 2, "data": "2026-09-20", "valor": 512.3}])
    assert validar_plano_pagamento(p) is None


def test_ultima_parcela_negativa_rejeita():
    p = _plano_tf([{"num": 1, "data": "2026-08-20", "valor": 30000.0},
                   {"num": 2, "data": "2026-09-20", "valor": -8123.45}])
    erro = validar_plano_pagamento(p)
    assert erro and "negativ" in erro.lower()


def test_entrada_negativa_rejeita():
    p = _plano_tf([{"num": 1, "data": "2026-08-20", "valor": 100.0}], entrada=-50.0)
    erro = validar_plano_pagamento(p)
    assert erro and "entrada" in erro.lower()


def test_none_e_formatos_sem_parcelas_passam():
    # legado: forma_pagamento pode ser texto curto (não-JSON) ou plano sem lista de parcelas
    assert validar_plano_pagamento(None) is None
    assert validar_plano_pagamento({"tipo": "avista", "total_cliente": 100.0}) is None


def test_parcela_sem_valor_nao_quebra():
    p = _plano_tf([{"num": 1, "data": "2026-08-20"}])
    assert validar_plano_pagamento(p) is None


def test_valor_nao_numerico_rejeita_sem_estourar():
    # QA Vera: string não-numérica deve virar erro de validação (400), não exceção (500)
    p = _plano_tf([{"num": 1, "data": "2026-08-20", "valor": 100.0}])
    p["parcelas"][0]["valor"] = "abc"
    erro = validar_plano_pagamento(p)
    assert erro and "não numérico" in erro
    assert validar_plano_pagamento({"entrada_valor": "x", "parcelas": []}) is not None
