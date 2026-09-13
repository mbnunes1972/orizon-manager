"""clicksign_config.py — resolve a base URL da ClickSign por ambiente (sandbox/produção).
Mesmo papel de d4sign_config.py/focus_config.py: a config real é 100% por loja/rede no banco
(IntegracaoClickSign), sem fallback de arquivo local."""
import os

_BASES = {
    "sandbox":  "https://sandbox.clicksign.com/api/v3",
    "producao": "https://app.clicksign.com/api/v3",
}


def base_url_de(ambiente: str) -> str:
    # ACHADO-69 (E2E de navegador da 11e, 13/09): único seam de teste deste arquivo — nunca
    # setada fora de tests/test_e2e_browser_termo_aditivo_clicksign.py, que sobe main.py num
    # subprocesso e precisa apontar o cliente pra um servidor ClickSign FALSO local (nunca é
    # correto um teste automatizado bater na ClickSign de verdade). Sem a variável, comportamento
    # idêntico a antes.
    override = os.environ.get("ORIZON_CLICKSIGN_BASE_URL_OVERRIDE")
    if override:
        return override
    try:
        return _BASES[ambiente]
    except KeyError:
        raise ValueError("ambiente inválido: %r (use 'sandbox' ou 'producao')" % (ambiente,))
