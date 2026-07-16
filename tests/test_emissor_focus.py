import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from fiscal import emissor_focus
from integracoes.emissor_fiscal import EmissorFiscal, StatusNota


class FakeClient:
    def __init__(self):
        self.enviado = None; self.consultado = None; self.cancelado = None
        self.enviado_nfse = None; self.consultado_nfse = None; self.cancelado_nfse = None
    def enviar_nfe(self, ref, payload):
        self.enviado = (ref, payload)
        return {"ref": ref, "status": "processando_autorizacao"}
    def consultar_nfe(self, ref, completa=False):
        self.consultado = ref
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CH"}
    def cancelar_nfe(self, ref, justificativa):
        self.cancelado = (ref, justificativa)
        return {"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"}
    def enviar_nfse(self, ref, payload):
        self.enviado_nfse = (ref, payload)
        return {"ref": ref, "status": "processando_autorizacao"}
    def consultar_nfse(self, ref, completa=False):
        self.consultado_nfse = ref
        return {"ref": ref, "status": "autorizado", "chave_nfe": "CHNFSE",
                "caminho_xml_nota_fiscal": "/nfse/x.xml", "url": "/nfse/nota.pdf"}
    def cancelar_nfse(self, ref, justificativa):
        self.cancelado_nfse = (ref, justificativa)
        return {"ref": ref, "status": "cancelado", "caminho_xml_cancelamento": "/c.xml"}


def _nota_nfse():
    return {"ref": "S1", "data_emissao": "D",
            "prestador": {"cnpj": "1", "inscricao_municipal": "IM", "codigo_municipio": "3549904",
                          "razao_social": "L"},
            "tomador": {"doc_tipo": "cpf", "doc": "2", "razao_social": "C", "logradouro": "a",
                        "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "servico": {"valor_servicos": 100.0, "aliquota": 2.0, "discriminacao": "Montagem",
                        "iss_retido": False, "item_lista_servico": "14.06",
                        "codigo_tributario_municipio": "3101"}}


def _nota():
    return {"ref": "R1", "natureza_operacao": "Venda", "data_emissao": "D",
            "emitente": {"doc_tipo": "cnpj", "doc": "1", "nome": "L", "regime": 1, "ie": "1",
                         "logradouro": "a", "numero": "1", "bairro": "b", "municipio": "c",
                         "uf": "SP", "cep": "1"},
            "destinatario": {"nome": "C", "doc_tipo": "cpf", "doc": "2", "logradouro": "a",
                             "numero": "1", "bairro": "b", "municipio": "c", "uf": "SP", "cep": "1"},
            "fiscal": {"csosn": "101", "cfop_dentro": "5102", "cfop_fora": "6102",
                       "pis_cst": "49", "cofins_cst": "49"},
            "itens": [{"cProd": "X", "xProd": "P", "ncm": "9403", "uCom": "UN",
                       "qCom": 1.0, "preco_venda_unit": 10.0}]}


def test_e_um_emissor_fiscal():
    assert issubclass(emissor_focus.EmissorFocusNfe, EmissorFiscal)


def test_emitir_nfe_produto_monta_e_envia():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).emitir_nfe_produto(_nota())
    ref, payload = fc.enviado
    assert ref == "R1"
    assert payload["cnpj_emitente"] == "1" and payload["items"][0]["cfop"] == "5102"
    assert res.status == StatusNota.PROCESSANDO and res.ref == "R1"


def test_consultar_status_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).consultar_status("R1")
    assert fc.consultado == "R1"
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CH"


def test_cancelar_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).cancelar("R1", "justificativa com mais de 15 chars")
    assert fc.cancelado == ("R1", "justificativa com mais de 15 chars")
    assert res.status == StatusNota.CANCELADO and res.xml_cancelamento_url == "/c.xml"


def test_emitir_nfse_servico_monta_e_envia():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).emitir_nfse_servico(_nota_nfse())
    ref, payload = fc.enviado_nfse
    assert ref == "S1"
    assert payload["prestador"]["cnpj"] == "1"
    assert payload["servico"]["valor_servicos"] == 100.0
    assert res.status == StatusNota.PROCESSANDO and res.ref == "S1"


def test_consultar_status_nfse_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).consultar_status_nfse("S1")
    assert fc.consultado_nfse == "S1"
    assert res.status == StatusNota.AUTORIZADO and res.chave == "CHNFSE"
    # o normalizer cobre as URLs da NFS-e (xml em caminho_xml_nota_fiscal; pdf via `url`)
    assert res.xml_url == "/nfse/x.xml" and res.danfe_url == "/nfse/nota.pdf"


def test_cancelar_nfse_delega_e_normaliza():
    fc = FakeClient()
    res = emissor_focus.EmissorFocusNfe(fc).cancelar_nfse("S1", "justificativa com mais de 15 chars")
    assert fc.cancelado_nfse == ("S1", "justificativa com mais de 15 chars")
    assert res.status == StatusNota.CANCELADO and res.xml_cancelamento_url == "/c.xml"
