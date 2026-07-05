import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from cryptography.fernet import Fernet
import fiscal_cripto as fcr


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setenv("ORIZON_FISCAL_KEY", Fernet.generate_key().decode())


def test_roundtrip():
    enc = fcr.encrypt("segredo-123")
    assert enc and enc != "segredo-123"
    assert fcr.decrypt(enc) == "segredo-123"


def test_ciphertext_muda_entre_chamadas():
    a = fcr.encrypt("igual")
    b = fcr.encrypt("igual")
    assert a != b                      # Fernet inclui IV/timestamp
    assert fcr.decrypt(a) == fcr.decrypt(b) == "igual"


def test_vazio_none():
    assert fcr.encrypt("") is None and fcr.encrypt(None) is None
    assert fcr.decrypt("") is None and fcr.decrypt(None) is None


def test_token_adulterado_levanta():
    from cryptography.fernet import InvalidToken
    with pytest.raises(InvalidToken):
        fcr.decrypt("nao-e-um-token-fernet-valido")


def test_token_definido():
    assert fcr.token_definido("x") is True
    assert fcr.token_definido(None) is False and fcr.token_definido("") is False


def test_gerar_chave_valida():
    k = fcr.gerar_chave()
    assert isinstance(k, str) and Fernet(k.encode())   # não levanta
