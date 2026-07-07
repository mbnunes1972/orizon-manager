"""Regressão do backfill de IBGE por CEP (US-39). `_ibge_por_cep` é module-level em main.py e
deve ser offline-safe: nunca lançar, degradar para None. (Pegaria o bug do `_re` indefinido:
o regex era a 1ª linha, fora do try → NameError na emissão de NFS-e p/ cliente legado.)"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_ibge_por_cep_resolve(app_db, monkeypatch):
    import main, requests

    class _R:
        status_code = 200
        def json(self): return {"ibge": "3549904"}

    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())
    assert main._ibge_por_cep("12242-800") == "3549904"


def test_ibge_por_cep_cep_invalido_sem_rede(app_db):
    # menos de 8 dígitos -> None, sem tocar a rede (e sem NameError)
    import main
    assert main._ibge_por_cep("123") is None
    assert main._ibge_por_cep("") is None
    assert main._ibge_por_cep(None) is None


def test_ibge_por_cep_offline_safe(app_db, monkeypatch):
    import main, requests

    def boom(*a, **k): raise RuntimeError("sem rede")
    monkeypatch.setattr(requests, "get", boom)
    assert main._ibge_por_cep("12242-800") is None   # degrada, não propaga


def test_ibge_por_cep_sem_ibge_no_retorno(app_db, monkeypatch):
    import main, requests

    class _R:
        status_code = 200
        def json(self): return {"erro": True}   # ViaCEP não achou o CEP

    monkeypatch.setattr(requests, "get", lambda *a, **k: _R())
    assert main._ibge_por_cep("00000-000") is None
