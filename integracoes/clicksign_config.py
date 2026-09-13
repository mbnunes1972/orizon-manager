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
    # correto um teste automatizado bater na ClickSign de verdade).
    #
    # Preocupação do Marcelo (13/09): uma env var isolada que redireciona assinatura eletrônica
    # de verdade pra um host arbitrário é exatamente o desvio que alguém com acesso ao .env
    # iria querer. Por isso o gate é DUPLO, e o segundo elemento não é uma segunda env var (que
    # sofreria do mesmo risco de "sobrar" num .env por engano) — é `PYTEST_CURRENT_TEST`, que o
    # PRÓPRIO pytest grava em `os.environ` só enquanto um teste está rodando (nunca escrita por
    # humano, nunca persistida em arquivo de config, impossível de "esquecer copiada" de um
    # ambiente pro outro). Um processo de Produção nunca roda sob pytest — pra este override
    # valer lá, seria preciso rodar o servidor de produção inteiro dentro de `pytest`, o que já
    # é um nível de acesso onde nenhum controle de código detém nada.
    override = os.environ.get("ORIZON_CLICKSIGN_BASE_URL_OVERRIDE")
    if override and os.environ.get("PYTEST_CURRENT_TEST"):
        return override
    try:
        return _BASES[ambiente]
    except KeyError:
        raise ValueError("ambiente inválido: %r (use 'sandbox' ou 'producao')" % (ambiente,))
