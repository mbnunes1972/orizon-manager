# -*- coding: utf-8 -*-
"""clicksign_config.base_url_de — o override de teste (ORIZON_CLICKSIGN_BASE_URL_OVERRIDE) só
pode valer sob pytest de verdade. Preocupação do Marcelo (13/09): uma env var isolada que
redireciona assinatura eletrônica pra um host arbitrário é o desvio que alguém com acesso ao
.env de Produção iria querer — o segundo gate (`PYTEST_CURRENT_TEST`, gravado pelo PRÓPRIO
pytest, nunca por humano) fecha essa porta sem depender de mais uma env var, que sofreria do
mesmo risco de "sobrar" copiada num .env errado."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import importlib
import integracoes.clicksign_config as cc


def test_base_url_de_default():
    assert cc.base_url_de("sandbox") == "https://sandbox.clicksign.com/api/v3"
    assert cc.base_url_de("producao") == "https://app.clicksign.com/api/v3"


def test_base_url_de_invalido():
    import pytest
    with pytest.raises(ValueError):
        cc.base_url_de("qualquer")


def test_override_exige_pytest_current_test(monkeypatch):
    monkeypatch.setenv("ORIZON_CLICKSIGN_BASE_URL_OVERRIDE", "http://127.0.0.1:9")
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert cc.base_url_de("sandbox") == "https://sandbox.clicksign.com/api/v3", (
        "sem PYTEST_CURRENT_TEST (processo fora de pytest), a env var sozinha NÃO pode "
        "redirecionar a chamada — é exatamente o cenário de um .env de Produção com a "
        "variável esquecida")


def test_override_vale_com_pytest_current_test(monkeypatch):
    monkeypatch.setenv("ORIZON_CLICKSIGN_BASE_URL_OVERRIDE", "http://127.0.0.1:9")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "algum::teste (call)")
    assert cc.base_url_de("sandbox") == "http://127.0.0.1:9"
    assert cc.base_url_de("producao") == "http://127.0.0.1:9"
