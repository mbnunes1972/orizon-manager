"""emissor_focus.py — implementação concreta de EmissorFiscal sobre a Focus NFe (Fase 3b).
Monta o payload (mapa_fiscal) e transmite via FocusClient (Fase 2). Sem regra fiscal aqui."""
from . import mapa_fiscal
from integracoes.emissor_fiscal import EmissorFiscal, resultado_de_focus


class EmissorFocusNfe(EmissorFiscal):
    """Recebe um FocusClient injetado (montado por mod_fiscal.focus_client_para_emitente)."""

    def __init__(self, client):
        self.client = client

    def emitir_nfe_produto(self, nota):
        payload = mapa_fiscal.montar_payload(nota)
        return resultado_de_focus(self.client.enviar_nfe(nota["ref"], payload))

    def consultar_status(self, ref):
        return resultado_de_focus(self.client.consultar_nfe(ref))

    def cancelar(self, ref, justificativa):
        return resultado_de_focus(self.client.cancelar_nfe(ref, justificativa))

    # --- NFS-e de serviço (municipal). Espelha o caminho do produto, mas via /v2/nfse. ---
    def emitir_nfse_servico(self, nota):
        payload = mapa_fiscal.montar_payload_nfse(nota)
        return resultado_de_focus(self.client.enviar_nfse(nota["ref"], payload))

    def consultar_status_nfse(self, ref):
        return resultado_de_focus(self.client.consultar_nfse(ref))

    def cancelar_nfse(self, ref, justificativa):
        return resultado_de_focus(self.client.cancelar_nfse(ref, justificativa))
