import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
import focus_config as fc


def test_base_url_de():
    assert fc.base_url_de("homologacao") == "https://homologacao.focusnfe.com.br"
    assert fc.base_url_de("producao") == "https://api.focusnfe.com.br"


def test_base_url_de_invalido():
    with pytest.raises(ValueError):
        fc.base_url_de("qualquer")


def test_get_focus_config_ausente(tmp_path, monkeypatch):
    monkeypatch.setattr(fc, "FOCUS_CONFIG_FILE", str(tmp_path / "nao_existe.json"))
    with pytest.raises(FileNotFoundError):
        fc.get_focus_config()


def test_get_focus_config_le(tmp_path, monkeypatch):
    p = tmp_path / "focus_config.json"
    p.write_text(json.dumps({"ambiente": "homologacao", "token": "T", "cnpj_emitente": "19152134000156"}),
                 encoding="utf-8")
    monkeypatch.setattr(fc, "FOCUS_CONFIG_FILE", str(p))
    cfg = fc.get_focus_config()
    assert cfg["token"] == "T" and cfg["ambiente"] == "homologacao"
