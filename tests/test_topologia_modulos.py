import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mod_tenancy as mt
from types import SimpleNamespace


def _loja(modulos_ativos=None):
    return SimpleNamespace(id=1, modulos_ativos=modulos_ativos)


def test_default_tudo_ligado():
    loja = _loja(None)
    assert mt.modulo_ativo(loja, "fiscal") is True
    assert mt.modulo_ativo(loja, "comercial") is True


def test_nucleo_sempre_ativo():
    loja = _loja(json.dumps(["comercial"]))
    assert mt.modulo_ativo(loja, "auth") is True
    assert mt.modulo_ativo(loja, "tenancy") is True


def test_dominio_desligado():
    loja = _loja(json.dumps(["cadastro", "comercial", "financeiro"]))
    assert mt.modulo_ativo(loja, "fiscal") is False
    assert mt.modulo_ativo(loja, "comercial") is True


def test_lista_ativa_resolve():
    loja = _loja(json.dumps(["cadastro"]))
    assert "cadastro" in mt.modulos_ativos_da_loja(loja)
    assert "fiscal" not in mt.modulos_ativos_da_loja(loja)
