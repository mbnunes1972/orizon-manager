"""emissor_fiscal.py — contrato neutro de emissão fiscal (independe de provedor).
A implementação concreta (Focus NFe) chega na Fase 3."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class StatusNota(str, Enum):
    PROCESSANDO  = "processando"
    AUTORIZADO   = "autorizado"
    ERRO         = "erro"
    CANCELADO    = "cancelado"
    DESCONHECIDO = "desconhecido"


@dataclass
class ResultadoEmissao:
    ref: str | None
    status: StatusNota
    chave: str | None = None
    numero: str | None = None
    serie: str | None = None
    status_sefaz: str | None = None
    mensagem_sefaz: str | None = None
    xml_url: str | None = None
    danfe_url: str | None = None
    xml_cancelamento_url: str | None = None
    erros: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


class EmissorFiscal(ABC):
    """Interface de emissão. Uma implementação por provedor (Focus NFe na Fase 3)."""

    @abstractmethod
    def emitir_nfe_produto(self, nota) -> ResultadoEmissao: ...

    @abstractmethod
    def consultar_status(self, ref: str) -> ResultadoEmissao: ...

    @abstractmethod
    def cancelar(self, ref: str, justificativa: str) -> ResultadoEmissao: ...

    def emitir_nfse_servico(self, servico) -> ResultadoEmissao:
        raise NotImplementedError(
            "NFS-e será implementada quando houver 2º CNPJ + município integrado na Focus.")


_MAP_STATUS_FOCUS = {
    "processando_autorizacao": StatusNota.PROCESSANDO,
    "autorizado":              StatusNota.AUTORIZADO,
    "erro_autorizacao":        StatusNota.ERRO,
    "cancelado":               StatusNota.CANCELADO,
}


def resultado_de_focus(dados: dict) -> ResultadoEmissao:
    """Normaliza a resposta JSON da Focus NFe para ResultadoEmissao (DTO neutro)."""
    return ResultadoEmissao(
        ref=dados.get("ref"),
        status=_MAP_STATUS_FOCUS.get(dados.get("status"), StatusNota.DESCONHECIDO),
        chave=dados.get("chave_nfe"),
        numero=dados.get("numero"),
        serie=dados.get("serie"),
        status_sefaz=dados.get("status_sefaz"),
        mensagem_sefaz=dados.get("mensagem_sefaz"),
        xml_url=dados.get("caminho_xml_nota_fiscal"),
        danfe_url=dados.get("caminho_danfe"),
        xml_cancelamento_url=dados.get("caminho_xml_cancelamento"),
        erros=dados.get("erros") or [],
        raw=dados,
    )
