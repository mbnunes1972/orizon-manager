"""focus_config.py — configuração da Focus NFe (token/ambiente/CNPJ).
Config por loja é Fase 3/5; aqui é o loader central (padrão do omie_config.json)."""
import os
import json

try:
    from storage import _BASE_DIR
except Exception:  # fallback fora do app
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FOCUS_CONFIG_FILE = os.path.join(_BASE_DIR, "focus_config.json")

_BASES = {
    "homologacao": "https://homologacao.focusnfe.com.br",
    "producao":    "https://api.focusnfe.com.br",
}


def base_url_de(ambiente: str) -> str:
    try:
        return _BASES[ambiente]
    except KeyError:
        raise ValueError("ambiente inválido: %r (use 'homologacao' ou 'producao')" % (ambiente,))


def get_focus_config() -> dict:
    """Lê focus_config.json → {ambiente, token, cnpj_emitente}. FileNotFoundError se ausente."""
    if not os.path.exists(FOCUS_CONFIG_FILE):
        raise FileNotFoundError(
            "focus_config.json ausente em %s — crie com {ambiente, token, cnpj_emitente}." % FOCUS_CONFIG_FILE)
    with open(FOCUS_CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)
