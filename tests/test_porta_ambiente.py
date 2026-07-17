"""ORIZON_PORT: porta de bind parametrizável (default 8765), espelhando ORIZON_HOST.
Permite a 2ª instância (pré-homologação, :8766) no mesmo servidor. Ver Plano de Testes."""
import pytest


def test_porta_default_sem_env(servidor):
    import main
    assert main.porta_do_ambiente({}) == 8765


def test_porta_default_env_vazio(servidor):
    import main
    assert main.porta_do_ambiente({"ORIZON_PORT": ""}) == 8765


def test_porta_le_valor_valido(servidor):
    import main
    assert main.porta_do_ambiente({"ORIZON_PORT": "8766"}) == 8766


def test_porta_nao_numerica_erro_claro(servidor):
    import main
    with pytest.raises(ValueError):
        main.porta_do_ambiente({"ORIZON_PORT": "abc"})


def test_porta_fora_de_faixa_erro(servidor):
    import main
    with pytest.raises(ValueError):
        main.porta_do_ambiente({"ORIZON_PORT": "70000"})
